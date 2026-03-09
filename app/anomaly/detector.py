"""
Anomaly Detector
-----------------
Two-layer detection:
  1. Statistical baseline — Z-score on error-rate time series
  2. LLM pattern matcher — sends log windows to GPT for semantic anomaly detection

Returns a list of AnomalyResult objects with severity, explanation, and line references.
"""

import re
import json
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from app.ingestion.parser import LogEntry
from app.llm.client import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    anomaly_id: str
    type: str                    # "statistical" | "llm_pattern" | "temporal"
    severity: str                # "low" | "medium" | "high" | "critical"
    title: str
    description: str
    affected_lines: List[int] = field(default_factory=list)
    affected_entries: List[Dict] = field(default_factory=list)
    timestamp: Optional[str] = None
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_id": self.anomaly_id,
            "type": self.type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "affected_lines": self.affected_lines,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
        }


# ---------------------------------------------------------------------------
# Statistical detector
# ---------------------------------------------------------------------------

def _bucket_by_minute(entries: List[LogEntry]) -> Dict[str, Dict[str, int]]:
    """Group entries by minute-bucket, count by level."""
    buckets: Dict[str, Dict[str, int]] = {}
    for e in entries:
        if e.timestamp is None:
            continue
        key = e.timestamp.strftime("%Y-%m-%dT%H:%M")
        if key not in buckets:
            buckets[key] = {"ERROR": 0, "WARNING": 0, "INFO": 0, "CRITICAL": 0, "total": 0}
        buckets[key][e.level] = buckets[key].get(e.level, 0) + 1
        buckets[key]["total"] += 1
    return buckets


def statistical_anomaly_detection(entries: List[LogEntry], z_threshold: float = 2.5) -> List[AnomalyResult]:
    """Detect spikes using Z-score on per-minute error counts."""
    anomalies: List[AnomalyResult] = []
    buckets = _bucket_by_minute(entries)
    if len(buckets) < 3:
        return anomalies

    times = sorted(buckets.keys())
    error_counts = [buckets[t].get("ERROR", 0) + buckets[t].get("CRITICAL", 0) for t in times]
    total_counts = [buckets[t]["total"] for t in times]

    if len(error_counts) < 2:
        return anomalies

    mean_err = statistics.mean(error_counts)
    stdev_err = statistics.stdev(error_counts) if len(error_counts) > 1 else 0

    for i, (t, count) in enumerate(zip(times, error_counts)):
        if stdev_err == 0:
            continue
        z = (count - mean_err) / stdev_err
        if z >= z_threshold:
            severity = "critical" if z > 4 else "high" if z > 3 else "medium"
            # Find affected entries
            affected = [e for e in entries if e.timestamp and e.timestamp.strftime("%Y-%m-%dT%H:%M") == t]
            anomalies.append(AnomalyResult(
                anomaly_id=f"stat-{i}",
                type="statistical",
                severity=severity,
                title=f"Error rate spike at {t}",
                description=(
                    f"Detected {count} errors in 1-minute window (z-score={z:.2f}). "
                    f"Baseline mean={mean_err:.1f}, stdev={stdev_err:.1f}."
                ),
                affected_lines=[e.line_no for e in affected],
                affected_entries=[e.to_dict() for e in affected[:5]],
                timestamp=t,
                confidence=min(0.99, z / 5),
            ))

    logger.info("Statistical detection found %d anomalies", len(anomalies))
    return anomalies


# ---------------------------------------------------------------------------
# LLM pattern matcher
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an expert SRE log analyst. Analyze the provided log window and identify anomalies, errors, or suspicious patterns. Respond ONLY in valid JSON as:
{
  "anomalies": [
    {
      "title": "...",
      "description": "...",
      "severity": "low|medium|high|critical",
      "lines_mentioned": [<line numbers as integers>],
      "confidence": <0.0-1.0>
    }
  ]
}
If no anomalies, return {"anomalies": []}. Do NOT include credentials or sensitive tokens in your output."""

def llm_anomaly_detection(entries: List[LogEntry], window_size: int = 50) -> List[AnomalyResult]:
    """Send log windows to LLM for semantic anomaly pattern matching."""
    client = get_llm_client()
    if client is None:
        logger.warning("LLM client unavailable — skipping LLM anomaly detection")
        return []

    anomalies: List[AnomalyResult] = []
    # Only send error-heavy windows to save tokens
    error_entries = [e for e in entries if e.level in ("ERROR", "CRITICAL", "FATAL", "WARNING")]
    if not error_entries:
        error_entries = entries[:window_size]  # fallback to first window

    window = error_entries[:window_size]
    log_text = "\n".join(
        f"[Line {e.line_no}] [{e.level}] {e.message or e.raw[:200]}"
        for e in window
    )

    try:
        response_text = client.complete(
            system=_SYSTEM_PROMPT,
            user=f"Analyze the following log window:\n\n{log_text}",
        )
        data = json.loads(response_text)
        for i, a in enumerate(data.get("anomalies", [])):
            anomalies.append(AnomalyResult(
                anomaly_id=f"llm-{i}",
                type="llm_pattern",
                severity=a.get("severity", "medium"),
                title=a.get("title", "Unnamed anomaly"),
                description=a.get("description", ""),
                affected_lines=a.get("lines_mentioned", []),
                timestamp=None,
                confidence=float(a.get("confidence", 0.7)),
            ))
    except (json.JSONDecodeError, Exception) as e:
        logger.error("LLM anomaly detection failed: %s", e)

    logger.info("LLM detection found %d anomalies", len(anomalies))
    return anomalies


# ---------------------------------------------------------------------------
# Combined entry point
# ---------------------------------------------------------------------------

def run_anomaly_detection(entries: List[LogEntry]) -> List[AnomalyResult]:
    """Run both statistical and LLM detectors, deduplicate, sort by severity."""
    results = []
    results.extend(statistical_anomaly_detection(entries))
    results.extend(llm_anomaly_detection(entries))

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    results.sort(key=lambda x: severity_order.get(x.severity, 99))
    return results
