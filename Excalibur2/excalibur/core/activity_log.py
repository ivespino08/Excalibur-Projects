"""Shared activity log sink for agent and router events."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_ACTIVITY_LOG_PATH = Path("/tmp/excalibur-activity.log")
_activity_log_lock = threading.Lock()


def activity_log_path() -> Path:
    """Return the configured activity log path."""
    raw_path = os.environ.get("EXCALIBUR_ACTIVITY_LOG")
    if not raw_path:
        return DEFAULT_ACTIVITY_LOG_PATH
    return Path(raw_path)


def append_activity_record(
    record_type: str,
    payload: Mapping[str, Any],
    timestamp: datetime | None = None,
) -> None:
    """Append a single activity record to the shared log file."""
    record_timestamp = timestamp or datetime.now()
    line = _format_record(record_type, payload, record_timestamp)
    path = activity_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _activity_log_lock, path.open("a", encoding="utf-8") as log_file:
            log_file.write(line)
            log_file.write("\n")
    except OSError:
        return


def _format_record(record_type: str, payload: Mapping[str, Any], timestamp: datetime) -> str:
    stamp = timestamp.isoformat(timespec="seconds")
    encoded_payload = json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
    return f"{stamp} [{record_type}] {encoded_payload}"
