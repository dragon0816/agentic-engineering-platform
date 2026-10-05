"""Prove an imported bundle really landed and can run. Touches nothing.

Deliberately has no side effects: no Excel, no Outlook, no browser, no writes
outside the job's own return value. Importing a stranger's bundle should be
testable without giving that stranger your workbooks -- so this job reports
what it can see and stops there.

Run standalone (every job must be able to, see CLAUDE.md)::

    python -m jobs.bundle_smoke --config config/workflow-bundle-smoke.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import platform
import socket
import sys
from pathlib import Path
from typing import Any, Callable

from jobs import _bundle_smoke_rules as rules

REPO_ROOT = Path(__file__).resolve().parents[2]

PARAMS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "greeting": {
            "type": ["string", "null"],
            "description": "Text echoed back, so you can tell one run from another.",
        },
        "fail": {
            "type": "boolean",
            "default": False,
            "description": "Raise on purpose, to see how a failing job is reported end to end.",
        },
    },
}

DEFAULT_GREETING = "hello"


def load_config(path: str | None) -> dict[str, Any]:
    """Optional here: this job works with no config at all."""
    if not path:
        return {}
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = REPO_ROOT / resolved
    if not resolved.is_file():
        return {}
    return json.loads(resolved.read_text(encoding="utf-8"))


def run(params: dict[str, Any], log: Callable[[str], None] = print) -> dict[str, Any]:
    params = dict(params or {})
    cfg = load_config(params.pop("configPath", None) or os.environ.get("BUNDLE_SMOKE_CONFIG"))
    greeting = params.get("greeting") or cfg.get("greeting") or DEFAULT_GREETING

    if params.get("fail"):
        # An explicit way to see a failure travel back through the relay, n8n
        # and the dashboard without breaking anything real.
        raise RuntimeError("bundle_smoke was asked to fail (params.fail = true)")

    installed = [
        "host-bridge/jobs/bundle_smoke.py",
        "host-bridge/jobs/_bundle_smoke_rules.py",
        "config/workflow-bundle-smoke.example.json",
    ]
    steps = rules.checklist(installed)
    host = socket.gethostname()
    summary = rules.summarise(host, greeting, steps)

    log(summary)
    log(f"running from {REPO_ROOT}")
    for step in steps:
        log(f"  [ok] {step['step']} -- {step['where']}")

    return {
        "summary": summary,
        "greeting": greeting,
        "host": host,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "repoRoot": str(REPO_ROOT),
        "ranAt": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "checks": steps,
        "installedAssets": installed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobs.bundle_smoke", description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--greeting", default=None)
    parser.add_argument("--fail", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(
            {"configPath": args.config, "greeting": args.greeting, "fail": args.fail},
            log=lambda m: print(m),
        )
    except Exception as exc:  # noqa: BLE001 - CLI reports, does not traceback
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
