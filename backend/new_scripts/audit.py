from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def log_event(event_type: str, payload: dict[str, Any], output_path: str = "data/audit/audit_log.jsonl") -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "payload": payload,
    }

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
