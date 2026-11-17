"""Python execution follows IT/OS access, retaining real artifacts and failures."""

import sys
from pathlib import Path

from capabilities.coding_change.contracts import CodingHostBinding
from capabilities.coding_change.run_python import RunPythonHandler, RunPythonRequest


def test_python_has_no_aep_root_or_firewall_admission_and_accepts_venv(tmp_path: Path) -> None:
    binding = CodingHostBinding.model_validate(
        {
            "runner_python": sys.executable,
            "timeout_seconds": 10,
            "repositories": [{"name": "fixture", "path": str(tmp_path), "writable": ["*.py"]}],
            "workspace_roots": [str(tmp_path / "legacy-root")],
            "require_network_block": True,
        }
    )
    handler = RunPythonHandler(binding, rule_present=lambda _python: False)
    outside = tmp_path / "outside.txt"
    workspace = tmp_path / "new-task"
    script = (
        "from pathlib import Path\nimport json\n"
        f"Path({str(outside)!r}).write_text('IT fixture', encoding='utf-8')\n"
        "Path('output/result.txt').write_text('artifact', encoding='utf-8')\n"
        "print(json.dumps({'rows': 1}))\n"
    )
    result = handler.run(RunPythonRequest(workspace=str(workspace), script=script))
    assert result.exit_code == 0 and not result.timed_out
    assert outside.read_text(encoding="utf-8") == "IT fixture"
    assert result.data == {"rows": 1}
    assert [item.path for item in result.files] == ["output/result.txt"]
    assert (workspace / result.script_path).read_text(encoding="utf-8") == script


def test_python_runs_without_a_coding_repository_configuration(tmp_path: Path) -> None:
    result = RunPythonHandler(None).run(
        RunPythonRequest(
            workspace=str(tmp_path / "task"),
            script="print('fixture')",
        )
    )
    assert result.exit_code == 0 and result.output.strip() == "fixture"
