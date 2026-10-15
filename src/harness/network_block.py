"""Is the coding runner interpreter cut off from the network?

The block is an outbound Windows Firewall rule on the dedicated runner
interpreter, created once by the owner with administrator rights. Two checks:

- `outbound_rule_present`: an enabled outbound Block rule names the program.
  Cheap (about two seconds), run before every coding run.
- `probe_blocked`: the restricted runner itself tries to reach a host this
  machine can otherwise reach. Group Policy can make a domain machine ignore
  local rules, so only this proves the block; run at install and by doctor.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from harness.restricted_runner import RestrictedRunner

RULE_NAME = "AEP coding runner - block outbound"

# The program path arrives in an environment variable: arguments after
# `-Command` are appended to the script text, not bound to `$args`, which
# made the first version of this check look up an empty path.
_PROGRAM_VARIABLE = "AEP_RUNNER_PROGRAM"
_RULE_SCRIPT = (
    f"$p = $env:{_PROGRAM_VARIABLE}; "
    "$r = Get-NetFirewallApplicationFilter -Program $p -ErrorAction SilentlyContinue "
    "| Get-NetFirewallRule | Where-Object { $_.Enabled -eq 'True' -and "
    "$_.Direction -eq 'Outbound' -and $_.Action -eq 'Block' }; "
    "if ($r) { 'blocked' } else { 'open' }"
)

Run = Callable[..., subprocess.CompletedProcess[str]]


def outbound_rule_present(python: Path, run: Run = subprocess.run) -> bool:
    result = run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", _RULE_SCRIPT],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, _PROGRAM_VARIABLE: str(python)},
    )
    return result.returncode == 0 and result.stdout.strip().endswith("blocked")


def create_rule_command(python: Path) -> str:
    """What the owner runs once, in an elevated PowerShell."""
    return (
        f'New-NetFirewallRule -DisplayName "{RULE_NAME}" -Direction Outbound '
        f'-Program "{python}" -Action Block -Profile Any'
    )


def probe_blocked(runner: RestrictedRunner, host: str, port: int, run_dir: Path) -> bool:
    """True when the runner cannot open a TCP connection to `host:port`."""
    run_dir.mkdir(parents=True, exist_ok=True)
    code = (
        "import socket\n"
        "try:\n"
        f"    socket.create_connection(({host!r}, {int(port)}), timeout=5).close()\n"
        "    print('connected')\n"
        "except OSError:\n"
        "    print('blocked')\n"
    )
    result = runner.run(["-c", code], cwd=run_dir, run_dir=run_dir)
    return result.exit_code == 0 and result.output.strip().endswith("blocked")
