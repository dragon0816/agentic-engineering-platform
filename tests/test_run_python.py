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
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "a-file").write_text("x", encoding="utf-8")
    for raw, code in (
        (str(tmp_path / "elsewhere"), "coding_workspace_not_allowed"),
        (str(tmp_path / "elsewhere" / "new-task"), "coding_workspace_not_allowed"),
        ("relative/path", "coding_workspace_not_absolute"),
        (str(tmp_path / "tasks" / "a-file"), "coding_workspace_not_a_folder"),
    ):
        with pytest.raises(CapabilityRefused) as refused:
            handler(tmp_path / "tasks").run(RunPythonRequest(workspace=raw, script="print(1)"))
        assert refused.value.code == code
    assert not (tmp_path / "elsewhere" / "new-task").exists()


def test_a_path_that_climbs_out_of_the_root_is_refused_and_creates_nothing(
    tmp_path: Path,
) -> None:
    """Owner 2026-10-20: never create a folder outside the roots; `..` is
    refused even when it would land back inside one."""
    (tmp_path / "tasks").mkdir()
    for raw in (
        str(tmp_path / "tasks") + r"\..\escaped",
        str(tmp_path / "tasks") + "/../escaped",
        str(tmp_path / "tasks") + r"\sub\..\inside",
    ):
        with pytest.raises(CapabilityRefused) as refused:
            handler(tmp_path / "tasks").run(RunPythonRequest(workspace=raw, script="print(1)"))
        assert refused.value.code == "coding_workspace_not_allowed"
    assert not (tmp_path / "escaped").exists()
    assert not (tmp_path / "tasks" / "inside").exists()
    assert not (tmp_path / "tasks" / "sub").exists()


def test_a_missing_folder_under_a_root_is_checked_but_made_only_when_the_run_starts(
    tmp_path: Path,
) -> None:
    """Live test 2026-10-20: `coding_workspace_missing` made the Agent ask the
    person to create the folder by hand. A refusal before the run (here the
    network block) leaves nothing behind."""
    root = tmp_path / "aep-workflows"
    target = root / "interactive-org-chart"
    runner = handler(root)
    assert runner._workspace(str(target)) == target.resolve()
    assert not target.exists()
    runner.rule_present = lambda _python: False
    with pytest.raises(CapabilityRefused) as refused:
        runner.run(RunPythonRequest(workspace=str(target), script="print(1)"))
    assert refused.value.code == "coding_network_block_missing"
    assert not target.exists()


@requires_win32
def test_a_missing_folder_under_a_root_is_created_and_the_run_goes_on(tmp_path: Path) -> None:
    root = tmp_path / "aep-workflows"
    root.mkdir()
    target = root / "interactive-org-chart"
    run = handler(root).run(
        RunPythonRequest(
            workspace=str(target), script="open('output/chart.html', 'w').write('<p>ok</p>')\n"
        )
    )
    assert run.exit_code == 0, run.output
    assert run.workspace_created is True
    assert (target / "input").is_dir() and (target / "output" / "chart.html").is_file()
    assert [item.path for item in run.files] == ["output/chart.html"]


@requires_win32
def test_an_existing_folder_is_used_as_it_is(tmp_path: Path) -> None:
    workspace = task(tmp_path)
    before = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
    run = handler(tmp_path / "tasks").run(
        RunPythonRequest(workspace=str(workspace), script="print('hi')\n")
    )
    assert run.exit_code == 0 and run.workspace_created is False
    assert (workspace / "input" / "data.csv").read_text(encoding="utf-8") == "a,b\n1,2\n"
    after = {path.relative_to(workspace) for path in workspace.rglob("*")}
    # Only what every run adds: output/ and the run's evidence under .aep-run/.
    added = {path for path in after - set(before) if path.parts[0] not in {"output", ".aep-run"}}
    assert set(before) <= after and added == set()


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


@requires_win32
@pytest.mark.parametrize(
    ("script", "failure_code", "exit_code", "timed_out"),
    [
        (
            "print('missing headers', flush=True)\nraise SystemExit(3)",
            "coding_program_failed",
            3,
            False,
        ),
        ("print('started', flush=True)\nwhile True: pass", "coding_program_timeout", None, True),
    ],
    ids=["nonzero", "timeout"],
)
def test_failed_program_cannot_pass_with_an_old_workbook(
    tmp_path: Path, script: str, failure_code: str, exit_code: int | None, timed_out: bool
) -> None:
    import asyncio

    from test_workflow_harness import context

    from capabilities.coding_change.run_python import RUN_SPEC, RunPythonResult, RunPythonStepInput
    from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
    from common.assets import ExecutionDependencies, WorkflowOutputCheck
    from host_runtime.session_artifacts import SessionArtifacts
    from workflow.dispatch import BridgeExecutor
    from workflow.engine import InstalledWorkflows, WorkflowEngine
    from workflow.harness import output_check, run_workflow_checked

    workspace = task(tmp_path)
    (workspace / "output").mkdir()
    (workspace / "output" / "old.xlsx").write_bytes(b"previous report")
    runner = handler(tmp_path / "tasks")
    runner.binding = runner.binding.model_copy(update={"timeout_seconds": 5})
    installed = InstalledCapabilities()
    installed.register(
        RUN_SPEC,
        runner,
        RunPythonStepInput,
        RunPythonResult,
        ExecutionDependencies(central_required=False),
    )
    grant = CapabilityGrant(
        actor="owner",
        asset=RUN_SPEC.identity,
        permissions=("coding.run-python",),
        policy_refs=("coding-restricted-execution-policy",),
        approval_ref="test-approval",
    )
    check = WorkflowOutputCheck(
        check_id="report", step_index=0, kind="files_nonempty", pattern="*.xlsx"
    )
    manifest = run_python_workflow().model_copy(update={"checks": (check,)})
    workflows = InstalledWorkflows()
    workflows.register(manifest)
    engine = WorkflowEngine(workflows, BridgeExecutor(installed, LocalPolicy((grant,))))
    done = asyncio.run(
        run_workflow_checked(
            engine,
            context(),
            manifest.metadata.identity,
            {"workspace": str(workspace), "script": script},
        )
    )
    assert done.run.status == "failed"
    assert done.run.failure is not None and done.run.failure.code == failure_code
    assert done.run.completed_steps == 0
    result = done.step_results[0]
    assert result.status == "failed" and result.handler_invoked
    assert isinstance(result.data, dict)
    assert result.data["exit_code"] == exit_code and result.data["timed_out"] is timed_out
    assert result.data["output"] and result.data["files"] == []
    assert not output_check(check, done)
    summary = SessionArtifacts(tmp_path / "history").finish_run("chat-1", "owner", done).summary
    assert summary is not None and summary.status == "failed"
    assert "失敗" in summary.block()


@requires_win32
def test_outputs_are_new_or_content_changed_in_this_invocation(tmp_path: Path) -> None:
    workspace = task(tmp_path)
    output = workspace / "output"
    output.mkdir()
    (output / "unchanged.txt").write_bytes(b"same")
    (output / "changed.txt").write_bytes(b"old!")
    result = handler(tmp_path / "tasks").run(
        RunPythonRequest(
            workspace=str(workspace),
            script=(
                "import os\nfrom pathlib import Path\n"
                "p = Path('output/changed.txt'); stamp = p.stat().st_mtime_ns\n"
                "p.write_bytes(b'new!'); os.utime(p, ns=(stamp, stamp))\n"
                "Path('output/unchanged.txt').write_bytes(b'same')\n"
                "Path('output/new.txt').write_bytes(b'new')\n"
            ),
        )
    )
    assert result.exit_code == 0, result.output
    assert [item.path for item in result.files] == ["output/changed.txt", "output/new.txt"]


@requires_win32
@pytest.mark.parametrize("limit", ["MAX_SCAN_FILES", "MAX_SCAN_BYTES", "MAX_SCAN_ENTRIES"])
def test_oversized_history_refuses_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    from capabilities.coding_change import run_python
    from harness.restricted_runner import RestrictedRunner

    workspace = task(tmp_path)
    output = workspace / "output"
    output.mkdir()
    (output / "old.xlsx").write_bytes(b"previous report")
    monkeypatch.setattr(run_python, limit, 0, raising=False)
    calls: list[str] = []

    def unexpected_run(*args: object, **kwargs: object) -> None:
        calls.append("run")
        raise AssertionError("output evidence must be bounded before launch")

    monkeypatch.setattr(RestrictedRunner, "run", unexpected_run)
    with pytest.raises(CapabilityRefused, match="coding_output_scan_limit"):
        handler(tmp_path / "tasks").run(
            RunPythonRequest(workspace=str(workspace), script="print('never starts')")
        )
    assert calls == []


@pytest.mark.parametrize("ticks_before_expiry", [1, 3], ids=["before-scan", "during-hash"])
def test_output_fingerprint_deadline_is_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ticks_before_expiry: int
) -> None:
    from capabilities.coding_change import run_python

    (tmp_path / "old.xlsx").write_bytes(b"previous report")
    ticks = iter([0.0] * ticks_before_expiry + [11.0])
    monkeypatch.setattr(run_python, "monotonic", lambda: next(ticks), raising=False)
    with pytest.raises(CapabilityRefused, match="coding_output_scan_limit"):
        run_python._output_fingerprints(tmp_path)


@requires_win32
def test_post_run_scan_overflow_retains_failure_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from capabilities.coding_change import run_python
    from capabilities.runtime import CapabilityExecutionFailed

    workspace = task(tmp_path)
    monkeypatch.setattr(run_python, "MAX_SCAN_BYTES", 1, raising=False)
    with pytest.raises(CapabilityExecutionFailed, match="coding_output_scan_limit") as failure:
        handler(tmp_path / "tasks").run(
            RunPythonRequest(
                workspace=str(workspace),
                script="open('output/new.txt', 'w').write('xx')\nprint('created')",
            )
        )
    data = run_python.RunPythonResult.model_validate(failure.value.data)
    assert data.exit_code == 0 and "created" in data.output
    assert data.files == ()


@requires_win32
@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ('{"date":"09.11.2026","nested":[1,true]}', {"date": "09.11.2026", "nested": [1, True]}),
        ('["09.11.2026"]', None),
        ('log line\n{"date":"09.11.2026"}', None),
        ('{"date":', None),
        ('{"value":NaN}', None),
        ('{"value":1e999}', None),
        (" " * 12_001 + '{"date":"09.11.2026"}', None),
        ('{"nested":' + "[" * 1100 + "0" + "]" * 1100 + "}", None),
    ],
    ids=["object", "nonobject", "noisy", "partial", "nan", "overflow", "truncated", "recursive"],
)
def test_program_stdout_binds_only_an_exact_bounded_json_object(
    tmp_path: Path, stdout: str, expected: dict[str, object] | None
) -> None:
    workspace = task(tmp_path)
    result = handler(tmp_path / "tasks").run(
        RunPythonRequest(
            workspace=str(workspace),
            script=f"print({stdout!r})",
        )
    )
    assert result.exit_code == 0, result.output
    assert result.data == expected
    assert result.output == (stdout + "\n")[-12_000:]


@requires_win32
def test_nonzero_program_json_is_diagnostic_data_and_never_success(tmp_path: Path) -> None:
    import asyncio

    from capabilities.coding_change.run_python import RunPythonResult, RunPythonStepInput
    from capabilities.runtime import CapabilityExecutionFailed

    workspace = task(tmp_path)
    (workspace / "output").mkdir()
    (workspace / "output" / "old.xlsx").write_bytes(b"previous report")
    request = RunPythonRequest(
        workspace=str(workspace),
        script='print(\'{"date":"09.11.2026"}\')\nraise SystemExit(3)',
    )
    with pytest.raises(CapabilityExecutionFailed, match="coding_program_failed") as failure:
        asyncio.run(handler(tmp_path / "tasks")(None, RunPythonStepInput(request=request)))  # type: ignore[arg-type]
    data = RunPythonResult.model_validate(failure.value.data)
    assert data.exit_code == 3 and data.data == {"date": "09.11.2026"}
    assert data.files == ()
