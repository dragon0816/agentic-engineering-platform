"""AEP script-tool adapter for rs_workflow_system Workflow 90 (bundle_smoke).

The job itself is carried unchanged under vendor/jobs, byte-identical to
dragon0816/rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43
(strategy WRAP). This adapter verifies those files before importing them,
reads the run's arguments as one JSON object on stdin, calls the job's own
`run(params, log)` with its log lines on stderr, and writes the job's result
as JSON on stdout. A job that raises exits non-zero, so the Bridge reports the
run as failed exactly as the source relay did.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor"
PINNED = {
    "jobs/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "jobs/bundle_smoke.py": "65bc5c9db0b5e14250f5f4102e03319fb41fa2366e154bd2d06937943128f469",
    "jobs/_bundle_smoke_rules.py": (
        "ce1b35238b25f04f7c84c744b94805c5f1eff65adb13bf9ea245aa11389895b1"
    ),
}


def main() -> int:
    for relative, digest in PINNED.items():
        if hashlib.sha256((VENDOR / relative).read_bytes()).hexdigest() != digest:
            print(f"vendored source changed: {relative}", file=sys.stderr)
            return 3
    # `python -I` puts neither the script's folder nor site-packages on the path.
    sys.path.insert(0, str(VENDOR))
    from jobs import bundle_smoke

    params = json.loads(sys.stdin.read() or "{}")
    if not isinstance(params, dict):
        print("arguments must be one JSON object", file=sys.stderr)
        return 2
    try:
        result = bundle_smoke.run(params, log=lambda line: print(line, file=sys.stderr))
    except Exception as error:  # noqa: BLE001 - the job's failure is the run's failure
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
