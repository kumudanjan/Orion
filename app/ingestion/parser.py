"""
Log Ingestion & Parsing Pipeline
---------------------------------
Supports:
  - Plain-text logs
  - JSON / NDJSON structured logs
  - OpenTelemetry formatted logs
  - Common web-server formats (Apache/Nginx Combined Log Format)

Steps:
  1. Read raw log file
  2. Detect & parse format
  3. PII / credential scrubbing (RAI guardrail)
  4. Semantic chunking
  5. Embed + upsert into vector store
"""

import re
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Dict, Any, Optional

from app.config import CONFIG
from app.guardrails.pii_masker import mask_pii

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Log line dataclass
# ---------------------------------------------------------------------------

class LogEntry:
    def __init__(
        self,
        raw: str,
        timestamp: Optional[datetime] = None,
        level: str = "INFO",
        service: str = "unknown",
        message: str = "",
        attributes: Optional[Dict[str, Any]] = None,
        line_no: int = 0,
    ):
        self.raw = raw
        self.timestamp = timestamp or datetime.utcnow()
        self.level = level.upper()
        self.service = service
        self.message = message
        self.attributes = attributes or {}
        self.line_no = line_no
        self.id = hashlib.md5(f"{line_no}:{raw}".encode()).hexdigest()[:12]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "raw": self.raw,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "service": self.service,
            "message": self.message,
            "attributes": self.attributes,
            "line_no": self.line_no,
        }


# ---------------------------------------------------------------------------
# Format detectors & parsers
# ---------------------------------------------------------------------------

_COMMON_LOG_RE = re.compile(
    r'(?P<host>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<request>[^"]*)" '
    r'(?P<status>\d{3}) (?P<size>\S+)'
)
_SYSLOG_RE = re.compile(
    r'(?P<month>\w{3})\s+(?P<day>\d+)\s+(?P<time>\d{2}:\d{2}:\d{2})\s+'
    r'(?P<host>\S+)\s+(?P<service>\S+):\s+(?P<message>.*)'
)
_LEVEL_RE = re.compile(
    r'(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)'
    r'\s+(?P<level>DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)'
    r'\s+(?P<message>.*)',
    re.IGNORECASE,
)


def _parse_json_line(line: str, line_no: int) -> Optional[LogEntry]:
    try:
        obj = json.loads(line)
        ts_raw = obj.get("timestamp") or obj.get("time") or obj.get("ts") or ""
        ts = _parse_timestamp(ts_raw)
        level = obj.get("level") or obj.get("severity") or obj.get("log.level") or "INFO"
        message = obj.get("message") or obj.get("msg") or obj.get("body", {}).get("stringValue", "") or line
        service = obj.get("service") or obj.get("resource", {}).get("service.name", "unknown")
        attrs = {k: v for k, v in obj.items() if k not in ("timestamp", "time", "ts", "level", "severity", "message", "msg")}
        return LogEntry(raw=line, timestamp=ts, level=str(level), service=str(service), message=str(message), attributes=attrs, line_no=line_no)
    except (json.JSONDecodeError, Exception):
        return None


def _parse_timestamp(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts[:26], fmt)
        except ValueError:
            continue
    return None


def _parse_text_line(line: str, line_no: int) -> LogEntry:
    # Try structured text pattern
    m = _LEVEL_RE.match(line)
    if m:
        ts = _parse_timestamp(m.group("ts")) or datetime.utcnow()
        level = m.group("level").upper()
        level = "WARNING" if level == "WARN" else level
        return LogEntry(raw=line, timestamp=ts, level=level, message=m.group("message"), line_no=line_no)

    # Apache / Nginx combined log
    m = _COMMON_LOG_RE.match(line)
    if m:
        status = m.group("status")
        level = "ERROR" if status.startswith("5") else ("WARNING" if status.startswith("4") else "INFO")
        return LogEntry(raw=line, level=level, message=m.group("request"), attributes={"status": status, "host": m.group("host")}, line_no=line_no)

    # Syslog
    m = _SYSLOG_RE.match(line)
    if m:
        return LogEntry(raw=line, service=m.group("service"), message=m.group("message"), line_no=line_no)

    # Fallback
    return LogEntry(raw=line, message=line, line_no=line_no)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_log_stream(lines: List[str], source: str = "uploaded") -> List[LogEntry]:
    """Parse a list of raw log lines into LogEntry objects."""
    entries: List[LogEntry] = []
    for i, line in enumerate(lines):
        line = line.rstrip("\n\r")
        if not line.strip():
            continue

        # Apply PII/credential masking before any storage
        if CONFIG.enable_pii_masking:
            line = mask_pii(line)

        entry = _parse_json_line(line, i) or _parse_text_line(line, i)
        entry.attributes["source"] = source
        entries.append(entry)

    logger.info("Parsed %d log entries from '%s'", len(entries), source)
    return entries


def semantic_chunk(entries: List[LogEntry], chunk_size: int = None, overlap: int = None) -> List[Dict[str, Any]]:
    """
    Group log entries into overlapping semantic chunks for embedding.
    Each chunk is a dict with 'text' and 'metadata'.
    """
    chunk_size = chunk_size or CONFIG.chunk_size
    overlap = overlap or CONFIG.chunk_overlap
    chunks = []

    i = 0
    while i < len(entries):
        window = entries[i: i + chunk_size]
        text = "\n".join(e.raw for e in window)
        metadata = {
            "start_line": window[0].line_no,
            "end_line": window[-1].line_no,
            "start_ts": window[0].timestamp.isoformat() if window[0].timestamp else "",
            "end_ts": window[-1].timestamp.isoformat() if window[-1].timestamp else "",
            "levels": list({e.level for e in window}),
            "services": list({e.service for e in window}),
            "has_error": any(e.level in ("ERROR", "CRITICAL", "FATAL") for e in window),
        }
        chunks.append({"text": text, "metadata": metadata})
        i += chunk_size - overlap

    return chunks


def parse_uploaded_file(file_bytes: bytes, filename: str) -> List[LogEntry]:
    """High-level helper for Streamlit file uploads."""
    text = file_bytes.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) == 0:
        return []
    return parse_log_stream(lines, source=filename)
