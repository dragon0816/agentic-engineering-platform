"""Restricted Windows execution for generated code (CODING_ON_BRIDGE C2)."""

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows execution limits")

from harness.restricted_runner import (  # noqa: E402
    RestrictedRunner,
    RunnerError,
    RunnerLimits,
    is_venv_launcher,
)

BASE_PYTHON = Path(getattr(sys, "_base_executable", sys.executable))


def runner(timeout: int = 30) -> RestrictedRunner:
    return RestrictedRunner(BASE_PYTHON, RunnerLimits(timeout_seconds=timeout))


def run_code(tmp_path: Path, code: str, timeout: int = 30) -> tuple[int | None, bool, str]:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    result = runner(timeout).run(["-c", code], cwd=run_dir, run_dir=run_dir)
    return result.exit_code, result.timed_out, result.output


def test_no_credential_reaches_the_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AEP_SECRET_PROBE", "should-not-leak")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "should-not-leak")
    code, _, output = run_code(
        tmp_path, "import os; print(sorted(k for k in os.environ if 'SECRET' in k or "
        "k.startswith(('AEP', 'LITELLM'))))",
    )
    assert code == 0 and output.strip() == "[]"


def test_it_writes_in_its_run_folder_and_nowhere_else(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    code, _, output = run_code(tmp_path, (
        "import os, pathlib\n"
        "pathlib.Path(os.getcwd(), 'inside.txt').write_text('ok')\n"
        "try:\n"
        f"    open(r'{outside}', 'w').write('x'); print('outside written')\n"
        "except PermissionError:\n"
        "    print('outside refused')\n"
    ))
    assert code == 0 and "outside refused" in output
    assert (tmp_path / "run" / "inside.txt").read_text() == "ok"
    assert not outside.exists()


def test_it_cannot_start_another_process(tmp_path: Path) -> None:
    code, _, output = run_code(tmp_path, (
        "import subprocess, sys\n"
        "try:\n"
        "    subprocess.run([sys.executable, '-c', 'pass'], check=True); print('child ran')\n"
        "except OSError:\n"
        "    print('child refused')\n"
    ))
    assert code == 0 and "child refused" in output


def test_the_timeout_ends_the_run(tmp_path: Path) -> None:
    code, timed_out, _ = run_code(tmp_path, "import time; time.sleep(60)", timeout=5)
    assert timed_out and code is None


def test_exit_codes_and_output_come_back(tmp_path: Path) -> None:
    code, timed_out, output = run_code(tmp_path, "print('hello'); raise SystemExit(3)")
    assert (code, timed_out) == (3, False) and "hello" in output


def test_a_venv_launcher_or_missing_interpreter_is_refused(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    (venv / "Scripts").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = x\n")
    launcher = venv / "Scripts" / "python.exe"
    launcher.write_bytes(b"")
    assert is_venv_launcher(launcher)
    with pytest.raises(RunnerError) as refused:
        RestrictedRunner(launcher)
    assert refused.value.code == "runner_python_is_venv_launcher"
    with pytest.raises(RunnerError) as missing:
        RestrictedRunner(tmp_path / "nothing.exe")
    assert missing.value.code == "runner_python_missing"


def test_the_firewall_rule_check_reads_powershell_and_names_the_program() -> None:
    import subprocess

    from harness.network_block import RULE_NAME, create_rule_command, outbound_rule_present

    seen: list[list[str]] = []

    def answering(text: str):  # noqa: ANN202 - test double
        def run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            seen.append(args)
            return subprocess.CompletedProcess(args, 0, stdout=text + "\n", stderr="")
        return run

    python = Path(r"C:\runner\python.exe")
    assert outbound_rule_present(python, answering("blocked"))
    assert not outbound_rule_present(python, answering("open"))
    assert seen[0][-1] == str(python)
    command = create_rule_command(python)
    assert RULE_NAME in command and "-Direction Outbound" in command and str(python) in command


def test_the_probe_reports_a_reachable_host_as_not_blocked(tmp_path: Path) -> None:
    """The test interpreter has no firewall rule, so a local listener is
    reachable: the probe must say so rather than claim a block."""
    import socket
    import threading

    from harness.network_block import probe_blocked

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    threading.Thread(target=lambda: server.accept()[0].close(), daemon=True).start()
    try:
        assert not probe_blocked(runner(), "127.0.0.1", server.getsockname()[1], tmp_path / "p")
    finally:
        server.close()
