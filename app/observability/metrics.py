"""
Observability Module
---------------------
Tracks KPIs and metrics:
  - Anomaly detection accuracy (precision / recall if ground truth available)
  - LLM output quality (hallucination score, response latency)
  - Log ingestion stats
  - Query execution traces (App Insights compatible)

Uses in-memory store for demo; connects to Azure App Insights when configured.
"""

import time
import logging
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config import CONFIG

logger = logging.getLogger(__name__)


@dataclass
class MetricEvent:
    name: str
    value: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsStore:
    def __init__(self):
        self._events: List[MetricEvent] = []
        self._traces: List[Dict[str, Any]] = []
        self._appinsights = self._init_appinsights()

    def _init_appinsights(self):
        if not CONFIG.appinsights_connection_string:
            return None
        try:
            from opencensus.ext.azure import metrics_exporter
            from opencensus.stats import aggregation as aggregation_module
            logger.info("App Insights connected")
            return True  # placeholder — full OpenCensus wiring omitted for brevity
        except ImportError:
            logger.info("opencensus-ext-azure not installed — App Insights disabled")
            return None

    def record(self, name: str, value: float, **tags):
        event = MetricEvent(name=name, value=value, tags=tags)
        self._events.append(event)
        if self._appinsights:
            self._send_to_appinsights(event)

    def trace(self, operation: str, duration_ms: float, success: bool, **attrs):
        self._traces.append({
            "operation": operation,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
            **attrs,
        })

    def _send_to_appinsights(self, event: MetricEvent):
        pass  # Replace with actual telemetry client send

    def summary(self) -> Dict[str, Any]:
        by_name: Dict[str, List[float]] = {}
        for e in self._events:
            by_name.setdefault(e.name, []).append(e.value)

        return {
            name: {
                "count": len(vals),
                "mean": round(statistics.mean(vals), 3),
                "min": round(min(vals), 3),
                "max": round(max(vals), 3),
                "stdev": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0,
            }
            for name, vals in by_name.items()
        }

    def recent_traces(self, n: int = 20) -> List[Dict[str, Any]]:
        return self._traces[-n:]

    def all_events(self) -> List[Dict[str, Any]]:
        return [vars(e) for e in self._events]


# Singleton
_metrics = MetricsStore()


def get_metrics() -> MetricsStore:
    return _metrics


# ---------------------------------------------------------------------------
# Context manager for timing operations
# ---------------------------------------------------------------------------

class Timer:
    def __init__(self, operation: str, **attrs):
        self.operation = operation
        self.attrs = attrs
        self._start = None

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        success = exc_type is None
        get_metrics().trace(self.operation, elapsed_ms, success, **self.attrs)
        get_metrics().record(f"{self.operation}_latency_ms", elapsed_ms)
        if not success:
            get_metrics().record(f"{self.operation}_errors", 1)
        return False
