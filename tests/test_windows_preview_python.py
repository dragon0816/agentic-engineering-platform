"""What install.ps1 does about the Python it finds and the venvs it finds.

These run the real script in Windows PowerShell, in a small bundle with no
wheels, so it stops at "exactly one platform wheel" right after the part under
test. -NoGateway -NoShortcut -NoAgentSkills and a temporary LOCALAPPDATA keep it
out of the user's settings. Fake Pythons are .cmd files that print what
Get-PythonIdentity asks for; the real Pythons are this test's own.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parents[1] / "deploy" / "windows-preview"
MINOR = f"{sys.version_info.major}.{sys.version_info.minor}"
NO_WHEEL = "Bundle must contain exactly one platform wheel"

pytestmark = pytest.mark.skipif(
    shutil.which("powershell.exe") is None, reason="needs Windows PowerShell"
)


def _fake_python(folder: Path, name: str, version: str, bits: int) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(
        f"@echo off\r\necho {version}\r\necho {path}\r\necho amd64\r\necho {bits}\r\n",
        encoding="ascii",
    )
    return path


def _fake_launcher(folder: Path, *listed: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    lines = "".join(f"echo {line}\r\n" for line in listed)
    (folder / "py.cmd").write_text(f"@echo off\r\n{lines}", encoding="ascii")


def _install(
    tmp_path: Path, *arguments: str, minor: str = "3.12", path: tuple[Path, ...] = ()
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the real install.ps1; the PATH holds only `path` and Windows."""
    bundle = tmp_path / "bundle"
    (bundle / "wheels").mkdir(parents=True)
    shutil.copy2(TEMPLATE / "install.ps1", bundle / "install.ps1")
    (bundle / "manifest.json").write_text(
        json.dumps({"files": [], "python_minor": minor}), encoding="utf-8"
    )
    root = tmp_path / "install root"
    system = Path(os.environ["SystemRoot"]) / "System32"
    env = dict(os.environ)
    env.update(
        PATH=os.pathsep.join(
            str(item) for item in (*path, system, system / "WindowsPowerShell" / "v1.0")
        ),
        LOCALAPPDATA=str(tmp_path / "local"),
    )
    for name in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH"):
        env.pop(name, None)
    done = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(bundle / "install.ps1"),
            "-Actor",
            "tester",
            "-BridgeId",
            "bridge-test",
            "-InstallRoot",
            str(root),
            "-NoGateway",
            "-NoShortcut",
            "-NoAgentSkills",
            *arguments,
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return done, root


def _words(done: subprocess.CompletedProcess[str]) -> str:
    """The output with the console's line wrapping taken out."""
    return "".join((done.stdout + done.stderr).split())


def _says(done: subprocess.CompletedProcess[str], text: str) -> bool:
    return "".join(text.split()) in _words(done)


def _venv(root: Path, *options: str) -> Path:
    venv = root / ".venv"
    subprocess.run([sys.executable, "-m", "venv", *options, str(venv)], check=True, timeout=300)
    (venv / "left-by-the-earlier-venv").write_text("x", encoding="utf-8")
    return venv


def _has_pip(venv: Path) -> bool:
    done = subprocess.run(
        [str(venv / "Scripts" / "python.exe"), "-m", "pip", "--version"],
        capture_output=True,
        timeout=120,
    )
    return done.returncode == 0


def test_a_32_bit_python_3_12_is_refused_and_named(tmp_path: Path) -> None:
    """Before: its platform.machine() says AMD64, so it passed the checks and
    every later attempt failed at pip with `No matching distribution`."""
    fake = _fake_python(tmp_path / "fake", "python.cmd", "3.12", 32)
    done, root = _install(tmp_path, path=(fake.parent,))
    assert done.returncode != 0
    assert _says(done, "This bundle requires 64-bit Python 3.12")
    assert _says(done, f"Found 32-bit Python 3.12 at {fake}")
    assert _says(done, "Install 64-bit Python 3.12 from")
    assert not root.exists()


def test_a_32_bit_python_given_with_python_exe_is_refused_too(tmp_path: Path) -> None:
    fake = _fake_python(tmp_path / "fake", "other.cmd", "3.12", 32)
    good = _fake_python(tmp_path / "fake", "good.cmd", "3.12", 64)
    _fake_launcher(tmp_path / "fake", f" -V:3.12 *  {good}")
    done, root = _install(tmp_path, "-PythonExe", str(fake), path=(fake.parent,))
    assert done.returncode != 0
    assert _says(done, "Found 32-bit Python 3.12")
    assert _says(done, f'-PythonExe "{good}"')
    assert not root.exists()


def test_a_32_bit_python_falls_back_to_the_launchers_64_bit_one(tmp_path: Path) -> None:
    fake = _fake_python(tmp_path / "fake", "python.cmd", "3.12", 32)
    good = _fake_python(tmp_path / "other", "good.cmd", "3.12", 64)
    _fake_launcher(tmp_path / "fake", f" -V:3.12-32 *  {fake}", f" -V:3.12  {good}")
    done, _root = _install(tmp_path, path=(fake.parent,))
    assert _says(done, f"'python' is 32-bit Python 3.12 ({fake})")
    assert _says(done, f"using Python 3.12 from the py launcher instead: {good}")
    assert _says(done, NO_WHEEL), done.stdout + done.stderr


def test_a_launcher_with_only_a_32_bit_python_is_no_fallback(tmp_path: Path) -> None:
    fake = _fake_python(tmp_path / "fake", "python.cmd", "3.14", 64)
    other = _fake_python(tmp_path / "other", "python32.cmd", "3.12", 32)
    _fake_launcher(tmp_path / "fake", f" -V:3.12-32 *  {other}")
    done, root = _install(tmp_path, path=(fake.parent,))
    assert done.returncode != 0
    assert _says(done, f"Found Python 3.14 at {fake}")
    assert not _says(done, "from the py launcher instead")
    assert not root.exists()


def test_a_launcher_entry_that_turns_out_32_bit_is_no_fallback(tmp_path: Path) -> None:
    """`py -0p` can list a 32-bit Python without the -32 suffix's help."""
    fake = _fake_python(tmp_path / "fake", "python.cmd", "3.14", 64)
    other = _fake_python(tmp_path / "other", "odd.cmd", "3.12", 32)
    _fake_launcher(tmp_path / "fake", f" -V:3.12 *  {other}")
    done, root = _install(tmp_path, path=(fake.parent,))
    assert done.returncode != 0
    assert not _says(done, "from the py launcher instead")
    assert not root.exists()


def test_a_64_bit_python_3_12_is_not_held_up(tmp_path: Path) -> None:
    fake = _fake_python(tmp_path / "fake", "python.cmd", "3.12", 64)
    done, _root = _install(tmp_path, path=(fake.parent,))
    assert not _says(done, "This bundle requires")
    assert _says(done, NO_WHEEL), done.stdout + done.stderr


def test_a_venv_without_pip_is_rebuilt_and_said_so(tmp_path: Path) -> None:
    """A failed attempt leaves one; each retry then ended in `No module named pip`."""
    root = tmp_path / "install root"
    venv = _venv(root, "--without-pip")
    done, _root = _install(tmp_path, "-PythonExe", sys.executable, minor=MINOR)
    assert _says(done, "cannot be used: it has no working pip")
    assert _says(done, NO_WHEEL), done.stdout + done.stderr
    assert not (venv / "left-by-the-earlier-venv").exists()
    assert _has_pip(venv)


def test_a_venv_whose_python_was_removed_is_rebuilt(tmp_path: Path) -> None:
    root = tmp_path / "install root"
    venv = _venv(root)
    config = venv / "pyvenv.cfg"
    lines = config.read_text(encoding="utf-8").splitlines()
    gone = str(tmp_path / "removed python")
    config.write_text(
        "\n".join(
            f"home = {gone}" if line.startswith("home") else line
            for line in lines
            if not line.startswith("executable")
        ),
        encoding="utf-8",
    )
    done, _root = _install(tmp_path, "-PythonExe", sys.executable, minor=MINOR)
    assert _says(done, "cannot be used: its Python does not run")
    assert _says(done, NO_WHEEL), done.stdout + done.stderr
    assert not (venv / "left-by-the-earlier-venv").exists()
    assert _has_pip(venv)


def test_a_working_venv_is_left_as_it_is(tmp_path: Path) -> None:
    root = tmp_path / "install root"
    venv = _venv(root)
    done, _root = _install(tmp_path, "-PythonExe", sys.executable, minor=MINOR)
    assert not _says(done, "cannot be used")
    assert _says(done, NO_WHEEL), done.stdout + done.stderr
    assert (venv / "left-by-the-earlier-venv").exists()


def _venv_block(tmp_path: Path, *lines: str) -> subprocess.CompletedProcess[str]:
    """Run the installer's venv functions on their own."""
    text = (TEMPLATE / "install.ps1").read_text(encoding="utf-8")
    block = text[text.index("# VENV-CHECK-BEGIN") : text.index("# VENV-CHECK-END")]
    script = tmp_path / "block.ps1"
    script.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        "function ConvertFrom-Escaped([string]$Text) { return [regex]::Unescape($Text) }\n"
        f"{block}\n" + "\n".join(lines) + "\n",
        encoding="ascii",
    )
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )


def test_a_venv_of_another_python_version_is_a_problem(tmp_path: Path) -> None:
    """The same branch a 32-bit venv takes; CI has no 32-bit Python to make one."""
    venv = _venv(tmp_path / "root")
    done = _venv_block(tmp_path, f"Get-VenvProblem '{venv}' '3.1'")
    assert done.returncode == 0, done.stderr
    assert f"-bit Python {MINOR}, not 64-bit Python 3.1" in done.stdout


def test_only_the_expected_venv_is_ever_removed(tmp_path: Path) -> None:
    root = tmp_path / "root"
    other = tmp_path / "another"
    other.mkdir()
    (other / "pyvenv.cfg").write_text("home = x", encoding="utf-8")
    done = _venv_block(tmp_path, f"Remove-InstallVenv '{other}' '{root}' '.venv'")
    assert done.returncode != 0
    assert "Refusingtoremove" in "".join(done.stderr.split())
    assert (other / "pyvenv.cfg").exists()


def test_a_folder_that_is_no_venv_is_not_removed(tmp_path: Path) -> None:
    root = tmp_path / "root"
    folder = root / ".venv"
    folder.mkdir(parents=True)
    (folder / "something-of-theirs").write_text("x", encoding="utf-8")
    done = _venv_block(tmp_path, f"Remove-InstallVenv '{folder}' '{root}' '.venv'")
    assert done.returncode != 0
    assert "pyvenv.cfg" in "".join(done.stderr.split())
    assert (folder / "something-of-theirs").exists()


def _junction(link: Path, target: Path) -> None:
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, timeout=60)


def test_a_venv_that_is_a_link_is_not_followed(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "pyvenv.cfg").write_text("home = x", encoding="utf-8")
    link = root / ".venv"
    _junction(link, target)
    done = _venv_block(tmp_path, f"Remove-InstallVenv '{link}' '{root}' '.venv'")
    assert done.returncode != 0
    assert "link" in done.stderr
    assert (target / "pyvenv.cfg").exists()


def test_a_link_inside_the_venv_is_not_followed(tmp_path: Path) -> None:
    """Windows PowerShell's Directory.Delete stops at the link with an error."""
    root = tmp_path / "root"
    venv = root / "gateway-venv"
    venv.mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = x", encoding="utf-8")
    (root / "host.json").write_text("{}", encoding="utf-8")
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "keep").write_text("x", encoding="utf-8")
    _junction(venv / "inner", target)
    done = _venv_block(tmp_path, f"Remove-InstallVenv '{venv}' '{root}' 'gateway-venv'")
    assert done.returncode != 0
    assert "Couldnotremovetheunusablevenv" in "".join(done.stderr.split())
    assert (target / "keep").exists()
    assert (root / "host.json").exists()


def test_the_venv_is_removed_and_nothing_beside_it(tmp_path: Path) -> None:
    root = tmp_path / "root"
    venv = root / "gateway-venv"
    (venv / "Lib").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = x", encoding="utf-8")
    (venv / "Lib" / "module.py").write_text("x", encoding="utf-8")
    (root / "host.json").write_text("{}", encoding="utf-8")
    done = _venv_block(tmp_path, f"Remove-InstallVenv '{venv}' '{root}' 'gateway-venv'")
    assert done.returncode == 0, done.stderr
    assert not venv.exists()
    assert (root / "host.json").exists()


def test_both_venvs_go_through_the_check() -> None:
    """The gateway's branch needs a real gateway install: CI's -GatewayInstallOnly
    run covers a healthy one, and this holds the unhealthy one to the same check."""
    text = (TEMPLATE / "install.ps1").read_text(encoding="utf-8")
    assert 'Repair-InstallVenv $Venv $InstallRoot ".venv" $Wanted' in text
    assert 'Repair-InstallVenv $GatewayVenv $InstallRoot "gateway-venv" $Wanted' in text
    assert text.index("# A running gateway holds the files this replaces.") < text.index(
        "Repair-InstallVenv $GatewayVenv"
    )
