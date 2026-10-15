"""`coding/run-python`: a conversation task's script under restricted execution."""

from __future__ import annotations

import importlib.util
import sys
import sysconfig
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows execution limits")

from capabilities.coding_change.contracts import CodingHostBinding  # noqa: E402
from capabilities.coding_change.manifest import coding_skill, run_python_workflow  # noqa: E402
from capabilities.coding_change.run_python import RunPythonHandler, RunPythonRequest  # noqa: E402
from capabilities.runtime import CapabilityRefused  # noqa: E402

requires_win32 = pytest.mark.skipif(
    importlib.util.find_spec("win32api") is None,
    reason="needs pywin32 (the windows extra); CI installs only dev,office",
)


BASE_PYTHON = str(Path(getattr(sys, "_base_executable", sys.executable)))
SITE = {"PYTHONPATH": sysconfig.get_paths()["purelib"]}


def handler(root: Path) -> RunPythonHandler:
    binding = CodingHostBinding.model_validate(
        {
            "runner_python": BASE_PYTHON,
            "timeout_seconds": 60,
            "repositories": [{"name": "x", "path": str(root), "writable": ["*.py"]}],
            "workspace_roots": [str(root)],
        }
    )
    return RunPythonHandler(binding, rule_present=lambda _python: True, extra_env=SITE)


def task(tmp_path: Path) -> Path:
    workspace = tmp_path / "tasks" / "T01"
    (workspace / "input").mkdir(parents=True)
    (workspace / "input" / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    return workspace


@requires_win32
def test_a_script_reads_input_writes_output_and_its_result_comes_back(tmp_path: Path) -> None:
    workspace = task(tmp_path)
    run = handler(tmp_path / "tasks").run(
        RunPythonRequest(
            workspace=str(workspace),
            script=(
                "from openpyxl import Workbook\n"
                "rows = open('input/data.csv', encoding='utf-8').read().split()\n"
                "book = Workbook(); book.active.append(rows); book.save('output/out.xlsx')\n"
                "print('rows', len(rows))\n"
            ),
        )
    )
    assert run.exit_code == 0 and "rows 2" in run.output
    assert [item.path for item in run.files] == ["output/out.xlsx"]
    assert (workspace / run.script_path).is_file()


@requires_win32
def test_input_and_other_folders_are_not_writable_and_a_failure_is_returned(tmp_path: Path) -> None:
    workspace = task(tmp_path)
    outside = tmp_path / "outside.txt"
    run = handler(tmp_path / "tasks").run(
        RunPythonRequest(
            workspace=str(workspace),
            script=(
                "import pathlib\n"
                "for target in ('input/data.csv', r'" + str(outside) + "'):\n"
                "    try:\n"
                "        pathlib.Path(target).write_text('x')\n"
                "        print('wrote', target)\n"
                "    except PermissionError:\n"
                "        print('refused', target)\n"
                "raise SystemExit(3)\n"
            ),
        )
    )
    assert run.exit_code == 3 and run.output.count("refused") == 2
    assert (workspace / "input" / "data.csv").read_text(encoding="utf-8") == "a,b\n1,2\n"
    assert not outside.exists()


def test_only_workspaces_under_an_allowed_root(tmp_path: Path) -> None:
    (tmp_path / "elsewhere").mkdir()
    for raw, code in (
        (str(tmp_path / "elsewhere"), "coding_workspace_not_allowed"),
        ("relative/path", "coding_workspace_not_absolute"),
        (str(tmp_path / "tasks" / "missing"), "coding_workspace_missing"),
    ):
        (tmp_path / "tasks").mkdir(exist_ok=True)
        with pytest.raises(CapabilityRefused) as refused:
            handler(tmp_path / "tasks").run(RunPythonRequest(workspace=raw, script="print(1)"))
        assert refused.value.code == code


def test_the_skill_says_when_not_to_use_it() -> None:
    skill = coding_skill()
    assert {command.name for command in skill.commands} == {"change", "run"}
    assert "Never use it to answer a question" in skill.instructions
    names = [field.name for field in run_python_workflow().parameters]
    assert names == ["workspace", "script"]


@requires_win32
def test_a_workflow_step_gives_the_same_script_new_values(tmp_path: Path) -> None:
    """G4: a saved script reruns with new run values and unchanged code."""
    import asyncio

    from capabilities.coding_change.run_python import RunPythonStepInput

    workspace = task(tmp_path)
    script = (
        "import json, os\n"
        "params = json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], encoding='utf-8'))\n"
        "open('output/' + params['name'] + '.txt', 'w').write(params['month'])\n"
    )
    runner = handler(tmp_path / "tasks")
    request = RunPythonRequest(workspace=str(workspace), script=script)
    for month in ("2026-09", "2026-08"):
        step = RunPythonStepInput(request=request, arguments={"name": f"m{month}", "month": month})
        run = asyncio.run(runner(None, step))  # type: ignore[arg-type]
        assert run.exit_code == 0, run.output  # type: ignore[attr-defined]
    assert (workspace / "output" / "m2026-08.txt").read_text() == "2026-08"
    scripts = sorted((workspace / ".aep-run").glob("run-*/script.py"))
    assert len(scripts) == 2 and scripts[0].read_bytes() == scripts[1].read_bytes()
