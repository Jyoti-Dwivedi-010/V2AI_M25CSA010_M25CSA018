from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from app.monitoring.request_logger import read_recent_requests


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(mean(values))


def _relative_shift(current: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0
    return (current - baseline) / baseline


def run_drift_check(window_size: int = 50) -> dict[str, Any]:
    records = read_recent_requests(limit=1000)

    if len(records) < window_size * 2:
        report = {
            "status": "insufficient_data",
            "message": "Need at least 2x window_size records for drift check",
            "records_available": len(records),
            "window_size": window_size,
            "drift_flags": [],
        }
    else:
        baseline = records[:-window_size]
        recent = records[-window_size:]

        baseline_latency = _safe_mean([float(item.get("latency_ms", 0.0)) for item in baseline])
        recent_latency = _safe_mean([float(item.get("latency_ms", 0.0)) for item in recent])

        baseline_q_len = _safe_mean(
            [float(item.get("question_length", 0.0)) for item in baseline]
        )
        recent_q_len = _safe_mean(
            [float(item.get("question_length", 0.0)) for item in recent]
        )

        latency_shift = _relative_shift(recent_latency, baseline_latency)
        question_length_shift = _relative_shift(recent_q_len, baseline_q_len)

        drift_flags: list[str] = []
        if abs(latency_shift) > 0.30:
            drift_flags.append("latency_shift")
        if abs(question_length_shift) > 0.40:
            drift_flags.append("question_distribution_shift")

        report = {
            "status": "ok" if not drift_flags else "alert",
            "window_size": window_size,
            "baseline_count": len(baseline),
            "recent_count": len(recent),
            "baseline_latency_ms": round(baseline_latency, 2),
            "recent_latency_ms": round(recent_latency, 2),
            "latency_shift": round(latency_shift, 4),
            "baseline_question_length": round(baseline_q_len, 2),
            "recent_question_length": round(recent_q_len, 2),
            "question_length_shift": round(question_length_shift, 4),
            "drift_flags": drift_flags,
        }

    output_path = Path("artifacts/monitoring/drift_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report


if __name__ == "__main__":
    print(json.dumps(run_drift_check(), indent=2))
