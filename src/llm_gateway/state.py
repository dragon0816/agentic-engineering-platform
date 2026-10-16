"""state.json in the gateway home: facts for the status card, never values.

pid, started_at        written by the launcher when it starts
last_refresh_at        the last successful token refresh
last_refresh_error     why the last refresh failed, if it did
last_test              the last `test` summary (model -> ok / error)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from llm_gateway.config import write_atomically


def now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def read(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def update(path: Path, **changes: object) -> dict[str, object]:
    data = read(path)
    for name, value in changes.items():
        if value is None:
            data.pop(name, None)
        else:
            data[name] = value
    write_atomically(path, json.dumps(data, indent=2, sort_keys=True) + "\n")
    return data
