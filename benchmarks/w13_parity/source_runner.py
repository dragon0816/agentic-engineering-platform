"""Run the original Workflow 13 job once, against an isolated repository.

Started by parity.py with a Python that has `requests`. It imports
`host-bridge/jobs/release_package.py` from the rs_workflow_system checkout
unchanged and replaces only the machine around it:

- the Bridge's `/terminal/run` becomes PowerShell on this machine, as the Bridge
  runs it, refused outside the isolated root and refused for `push`;
- the config file, the ops dashboard and the state folder are blanked, so the
  real `config/workflow-13.json` (which names the real GitLab) is never read.

    python source_runner.py <source checkout> <job.json> <result.json>
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    source, job_path, result_path = (Path(arg) for arg in sys.argv[1:4])
    job = json.loads(job_path.read_text(encoding="utf-8"))
    root = Path(job["root"]).resolve()
    sys.path.insert(0, str(source / "host-bridge"))
    import jobs.release_package as release  # noqa: PLC0415 - the source under test

    class IsolatedBridge:
        base = "isolated"

        def terminal_run(
            self, command: str, *, shell: str, cwd: str, timeoutSec: int
        ) -> dict[str, object]:  # noqa: N803 - source API
            if not Path(cwd).resolve().is_relative_to(root):
                raise RuntimeError(f"refused outside the isolated root: {cwd}")
            if command.split()[:2] == ["git", "push"]:
                raise RuntimeError("push is refused in the parity run")
            done = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeoutSec,
            )
            return {
                "data": {"exitCode": done.returncode, "stdout": done.stdout, "stderr": done.stderr}
            }

    release.Bridge = IsolatedBridge  # type: ignore[assignment,misc]
    release.load_file_defaults = lambda: {}
    release.OPS.resolve = lambda config, log: {}
    release.STATE_DIR = root / "source-state"
    log: list[str] = []
    try:
        result = release.run(job["params"], log=log.append)
        outcome = {"ok": True, "result": result, "log": log}
    except release.JobError as error:
        outcome = {"ok": False, "error": str(error), "log": log}
    result_path.write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
