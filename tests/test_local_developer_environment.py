import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _ps_quote(path: Path) -> str:
    return str(path).replace("'", "''")


def test_local_environment_file_is_ignored_but_the_example_is_tracked() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert ".env/*" in ignore
    assert "!.env/example.yaml" in ignore
    assert "!.env/README.md" in ignore

    example = (ROOT / ".env" / "example.yaml").read_text(encoding="utf-8")
    assignments = [line for line in example.splitlines() if line and not line.startswith("#")]
    assert assignments
    assert all(line.endswith(': ""') for line in assignments)


def test_loader_is_explicit_and_does_not_print_secret_values() -> None:
    loader = (ROOT / "scripts" / "import-local-env.ps1").read_text(encoding="utf-8")

    assert '"GH_TOKEN"' in loader
    assert '"AEP_GITHUB_TOKEN"' in loader
    assert '"OPENAI_API_KEY"' not in loader
    assert "Unsupported local environment variable" in loader
    assert "Write-Output $value" not in loader
    assert "Write-Host $value" not in loader
    assert "Get-Content" in loader


def test_local_codex_worker_uses_pro_login_and_a_single_logon_task() -> None:
    runner = (ROOT / "scripts" / "run-local-codex-worker.ps1").read_text(encoding="utf-8")
    installer = (ROOT / "scripts" / "install-local-codex-worker-task.ps1").read_text(
        encoding="utf-8"
    )

    assert "import-local-env.ps1" in runner
    assert "gh auth setup-git --hostname github.com" in runner
    assert "codex login status" in runner
    assert "--loop" in runner
    assert "OPENAI_API_KEY" not in runner
    assert "New-ScheduledTaskTrigger -AtLogOn" in installer
    assert "-MultipleInstances IgnoreNew" in installer
    assert "Start-ScheduledTask" in installer


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell 7 is unavailable")
def test_loader_sets_only_allowlisted_values_without_echoing_them(tmp_path: Path) -> None:
    token = "fixture-secret-value"
    local = tmp_path / "local.yaml"
    example = (ROOT / ".env" / "example.yaml").read_text(encoding="utf-8")
    local.write_text(example.replace('GH_TOKEN: ""', f'GH_TOKEN: "{token}"'), encoding="utf-8")
    script = ROOT / "scripts" / "import-local-env.ps1"
    command = (
        f". '{_ps_quote(script)}' -Path "
        f"'{_ps_quote(local)}'; "
        f"if ($env:GH_TOKEN -ne '{token}') {{ exit 9 }}"
    )

    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "GH_TOKEN" in result.stdout
    assert token not in result.stdout
    assert token not in result.stderr


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell 7 is unavailable")
def test_loader_rejects_unknown_names_without_setting_them(tmp_path: Path) -> None:
    local = tmp_path / "local.yaml"
    local.write_text('UNRELATED_PROCESS_SETTING: "fixture-value"\n', encoding="utf-8")
    script = ROOT / "scripts" / "import-local-env.ps1"
    command = f". '{_ps_quote(script)}' -Path '{_ps_quote(local)}'"

    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Unsupported local environment variable" in result.stderr
    assert "fixture-value" not in result.stdout
    assert "fixture-value" not in result.stderr
