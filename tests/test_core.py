"""
Unit Tests — Log Intelligence Assistant
Run with: pytest tests/ -v
"""

import pytest
from datetime import datetime

# -------------------------------------------------------------------------
# Parser tests
# -------------------------------------------------------------------------

def test_parse_json_log_line():
    from app.ingestion.parser import parse_log_stream
    line = '{"timestamp": "2024-01-15T14:00:00Z", "level": "ERROR", "message": "DB timeout", "service": "web"}'
    entries = parse_log_stream([line], source="test")
    assert len(entries) == 1
    e = entries[0]
    assert e.level == "ERROR"
    assert "DB timeout" in e.message
    assert e.service == "web"


def test_parse_structured_text_log():
    from app.ingestion.parser import parse_log_stream
    line = "2024-01-15 14:00:00 ERROR Connection refused to database"
    entries = parse_log_stream([line], source="test")
    assert len(entries) == 1
    assert entries[0].level == "ERROR"


def test_parse_apache_log():
    from app.ingestion.parser import parse_log_stream
    line = '192.168.1.1 - - [15/Jan/2024:14:00:00 +0000] "GET /api/health HTTP/1.1" 500 1234'
    entries = parse_log_stream([line], source="test")
    assert len(entries) == 1
    assert entries[0].level == "ERROR"   # 5xx → ERROR


def test_empty_lines_skipped():
    from app.ingestion.parser import parse_log_stream
    lines = ["", "   ", "\n", "2024-01-15 14:00:00 INFO Hello"]
    entries = parse_log_stream(lines)
    assert len(entries) == 1


def test_semantic_chunking():
    from app.ingestion.parser import parse_log_stream, semantic_chunk
    lines = [f"2024-01-15 14:00:{i:02d} INFO msg {i}" for i in range(20)]
    entries = parse_log_stream(lines)
    chunks = semantic_chunk(entries, chunk_size=5, overlap=1)
    assert len(chunks) > 1
    # Each chunk has text and metadata
    assert all("text" in c and "metadata" in c for c in chunks)


# -------------------------------------------------------------------------
# PII Masker tests
# -------------------------------------------------------------------------

def test_password_masked():
    from app.guardrails.pii_masker import mask_pii
    result = mask_pii("login failed password=supersecret123")
    assert "supersecret123" not in result
    assert "MASKED" in result


def test_email_masked():
    from app.guardrails.pii_masker import mask_pii
    result = mask_pii("user john.doe@example.com logged in")
    assert "john.doe@example.com" not in result
    assert "EMAIL" in result


def test_jwt_masked():
    from app.guardrails.pii_masker import mask_pii
    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyMSJ9.signature123"
    result = mask_pii(f"Authorization header: {jwt}")
    assert jwt not in result


def test_clean_text_unchanged():
    from app.guardrails.pii_masker import mask_pii
    text = "2024-01-15 14:00:00 INFO Service started successfully"
    assert mask_pii(text) == text


def test_validate_llm_output_safe():
    from app.guardrails.pii_masker import validate_llm_output
    safe, violations = validate_llm_output("The database connection timed out. Check the connection pool settings.")
    assert safe is True
    assert len(violations) == 0


def test_hallucination_check():
    from app.guardrails.pii_masker import hallucination_check
    answer = "The database connection pool was exhausted"
    sources = ["connection pool exhausted max_connections=100"]
    score = hallucination_check(answer, sources)
    assert score > 0.0


# -------------------------------------------------------------------------
# Statistical anomaly detector tests
# -------------------------------------------------------------------------

def test_no_anomaly_on_uniform_errors():
    from app.ingestion.parser import parse_log_stream
    from app.anomaly.detector import statistical_anomaly_detection
    # Uniform error rate — no spike
    lines = []
    for i in range(60):
        minute = i // 10
        lines.append(f"2024-01-15 14:{minute:02d}:{(i%10)*6:02d} ERROR msg {i}")
    entries = parse_log_stream(lines)
    anomalies = statistical_anomaly_detection(entries, z_threshold=2.5)
    assert len(anomalies) == 0


def test_spike_detected():
    from app.ingestion.parser import parse_log_stream
    from app.anomaly.detector import statistical_anomaly_detection
    lines = []
    # 2 errors per minute for 5 mins
    for m in range(5):
        for j in range(2):
            lines.append(f"2024-01-15 14:{m:02d}:{j*30:02d} ERROR base error")
    # Spike at minute 5: 20 errors
    for j in range(20):
        lines.append(f"2024-01-15 14:05:{j*2:02d} ERROR spike error")
    entries = parse_log_stream(lines)
    anomalies = statistical_anomaly_detection(entries, z_threshold=2.0)
    assert len(anomalies) >= 1
    assert any(a.severity in ("high", "critical") for a in anomalies)


# -------------------------------------------------------------------------
# RCA Agent tool tests
# -------------------------------------------------------------------------

def test_count_errors_tool():
    from app.ingestion.parser import parse_log_stream
    from app.rca.agent import _tool_count_errors
    lines = [
        "2024-01-15 14:00:00 ERROR err1",
        "2024-01-15 14:00:01 INFO info1",
        "2024-01-15 14:00:02 ERROR err2",
    ]
    entries = parse_log_stream(lines)
    result = _tool_count_errors("ERROR", entries)
    assert "2" in result


def test_get_error_context():
    from app.ingestion.parser import parse_log_stream
    from app.rca.agent import _tool_get_error_context
    lines = [f"2024-01-15 14:00:{i:02d} INFO line {i}" for i in range(30)]
    entries = parse_log_stream(lines)
    result = _tool_get_error_context("15", entries)
    assert "line" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
