"""Set the three mocks' fault scenarios before a task.

  python operator/reset.py                      # everything back to normal
  python operator/reset.py --sap expire_session_once
  python operator/reset.py --expense export_fail_once
  python operator/reset.py --quote transient_once   (or force_exit2)

Event logs are append-only; each reset writes a marker line so a task's
events can be cut out of the log by position.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

STATE = Path(__file__).resolve().parent / "state"
MODES = {
    "sap": ("normal", "expire_session_once", "delay_once"),
    "expense": ("normal", "export_fail_once"),
    "quote": ("normal", "transient_once", "force_exit2"),
}


def reset(sap: str = "normal", expense: str = "normal", quote: str = "normal", label: str = "") -> dict[str, int]:
    """Write the fault files and return each event log's size, the task's start offset."""
    STATE.mkdir(parents=True, exist_ok=True)
    offsets = {}
    for system, mode in {"sap": sap, "expense": expense, "quote": quote}.items():
        if mode not in MODES[system]:
            raise ValueError(f"{system}: unknown mode {mode}")
        (STATE / f"{system}_fault.json").write_text(json.dumps({"mode": mode}), encoding="utf-8")
        log = STATE / f"{system}_events.jsonl"
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": datetime.now().isoformat(timespec="milliseconds"),
                                     "event": "operator_reset", "mode": mode, "label": label}) + "\n")
        offsets[system] = log.stat().st_size
        if system == "quote" and sys.platform == "win32":
            # The Agent runs the CLI from its low-integrity runner; let that
            # process record its events and consume a one-time fault.
            for name in ("quote_fault.json", "quote_events.jsonl"):
                subprocess.run(["icacls", str(STATE / name), "/setintegritylevel", "low", "/Q"],
                               capture_output=True, check=False)
    return offsets


def events(system: str, offset: int) -> list[dict[str, object]]:
    log = STATE / f"{system}_events.jsonl"
    if not log.exists():
        return []
    with log.open("rb") as handle:
        handle.seek(offset)
        return [json.loads(line) for line in handle.read().decode("utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for system, modes in MODES.items():
        parser.add_argument(f"--{system}", choices=modes, default="normal")
    args = parser.parse_args()
    print(json.dumps(reset(args.sap, args.expense, args.quote, "manual")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
