from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import load_settings


def _ensure_parent_exists(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def log_request(record: dict[str, Any]) -> None:
    settings = load_settings()
    path = settings.request_log_path
    _ensure_parent_exists(path)

    payload = {
        **record,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_recent_requests(limit: int = 200) -> list[dict[str, Any]]:
    settings = load_settings()
    path = settings.request_log_path
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    selected = lines[-limit:]

    records: list[dict[str, Any]] = []
    for line in selected:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records
