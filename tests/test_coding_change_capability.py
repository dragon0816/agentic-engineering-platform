"""`coding/change@1.0.0` on a real repository (CODING_ON_BRIDGE C5)."""

import importlib.util
import json
import sys
import sysconfig
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows execution limits")

from test_coding_worktree_pytest import RIGHT, WRONG, git, repository  # noqa: E402

from capabilities.coding_change.contracts import (  # noqa: E402
    CodingChangeRequest,
    CodingChangeStepInput,
    CodingHostBinding,
)
from capabilities.coding_change.handlers import CodingChangeHandler, is_test_path  # noqa: E402
from capabilities.coding_change.manifest import coding_skill, coding_workflow  # noqa: E402
from capabilities.runtime import CapabilityRefused  # noqa: E402
from common.execution import TraceIdentifiers  # noqa: E402
from models.contracts import ModelRequest, ModelResponse  # noqa: E402

requires_win32 = pytest.mark.skipif(
    importlib.util.find_spec("win32api") is None,
    reason="needs pywin32 (the windows extra); CI installs only dev,office",
)


TRACE = TraceIdentifiers(trace_id="coding", request_id="coding", span_id="coding")
SITE = {"PYTHONPATH": sysconfig.get_paths()["purelib"]}
BASE_PYTHON = str(Path(getattr(sys, "_base_executable", sys.executable)))


class Replies:
    def __init__(self, *answers: dict[str, Any]) -> None:
        self.answers = list(answers)

    def generate(self, request: ModelRequest) -> ModelResponse:
        answer = self.answers.pop(0)
        return ModelResponse(trace=request.trace, model_alias=request.model_alias,
                             text=json.dumps(answer), structured_output=answer)


PLAN = {"summary": "Add double", "purpose": "implement double"}


def handler(tmp_path: Path, model: Replies | None, *, blocked: bool = True,
            python: str = BASE_PYTHON) -> tuple[CodingChangeHandler, Path]:
    repo = repository(tmp_path)
    binding = CodingHostBinding.model_validate({
        "runner_python": python,
        "repositories": [{"name": "practice", "path": str(repo), "writable": ["src/**/*.py"]}],
        "timeout_seconds": 60,
    })
    return CodingChangeHandler(
        binding, tmp_path / "runs", model=model, model_alias="gateway",
        rule_present=lambda _python: blocked, extra_env=SITE,
    ), repo


def ask(**changes: Any) -> CodingChangeStepInput:
    request = {"repository": "practice", "requirement": "Add double(value).",
               "file": "src/calc/double.py", "tests": ["tests/test_double.py"],
               "max_repairs": 1, **changes}
    return CodingChangeStepInput(request=CodingChangeRequest.model_validate(request))


@requires_win32
def test_a_wrong_first_version_is_repaired_and_left_uncommitted_for_review(
    tmp_path: Path,
) -> None:
    run, repo = handler(tmp_path, Replies(PLAN, {"content": WRONG}, {"content": RIGHT}))
    result = run.change(TRACE, ask())
    assert result.summary == "Add double" and result.attempts == 2 and not result.committed
    assert [(item.command, item.status) for item in result.commands] == [
        ("pytest-new", "failed"), ("pytest-new", "passed"), ("pytest-suite", "passed")]
    assert "+    return value * 2" in result.diff
    worktree = Path(result.worktree)
    assert (worktree / "src" / "calc" / "double.py").read_text() == RIGHT
    evidence = json.loads(Path(result.evidence).read_text(encoding="utf-8"))
    assert evidence["result"]["status"] == "validated"
    assert not (repo / "src" / "calc" / "double.py").exists()
    assert git("rev-list", "--count", "HEAD", cwd=repo).strip() == "1"


@requires_win32
def test_a_run_that_never_passes_is_refused_with_its_evidence_kept(tmp_path: Path) -> None:
    still_wrong = WRONG.replace("+ 2", "+ 3")
    run, _ = handler(tmp_path, Replies(PLAN, {"content": WRONG}, {"content": still_wrong}))
    with pytest.raises(CapabilityRefused) as refused:
        run.change(TRACE, ask())
    assert refused.value.code == "repair_budget_exceeded"
    (evidence,) = (tmp_path / "runs").glob("*/result.json")
    assert json.loads(evidence.read_text(encoding="utf-8"))["result"]["status"] == "failed"


@pytest.mark.parametrize(("changes", "code"), [
    ({"repository": "elsewhere"}, "coding_repository_unknown"),
    ({"file": "tests/test_double.py"}, "coding_file_is_a_test"),
    ({"file": "src/calc/conftest.py"}, "coding_file_is_a_test"),
    ({"file": "pyproject.toml"}, "coding_file_not_writable"),
    ({"file": "../outside.py"}, "coding_path_invalid"),
    ({"file": "C:/Windows/x.py"}, "coding_path_invalid"),
    ({"tests": ["tests/test_missing.py"]}, "coding_test_not_found"),
    ({"tests": ["src/calc/ops.py"]}, "coding_test_not_a_test_file"),
])
def test_what_a_person_can_fix_is_refused_before_anything_runs(
    tmp_path: Path, changes: dict[str, Any], code: str
) -> None:
    run, _ = handler(tmp_path, Replies())
    with pytest.raises(CapabilityRefused) as refused:
        run.change(TRACE, ask(**changes))
    assert refused.value.code == code
    assert not (tmp_path / "runs").exists()


def test_no_model_no_network_block_or_a_venv_runner_is_refused(tmp_path: Path) -> None:
    for kwargs, code in (
        ({"model": None}, "coding_model_unavailable"),
        ({"model": Replies(), "blocked": False}, "coding_network_block_missing"),
        ({"model": Replies(), "python": sys.executable}, "runner_python_is_venv_launcher"),
    ):
        run, _ = handler(tmp_path / code, **kwargs)  # type: ignore[arg-type]
        with pytest.raises(CapabilityRefused) as refused:
            run.change(TRACE, ask())
        assert refused.value.code == code


def test_test_paths_are_never_writable() -> None:
    assert is_test_path("tests/unit/helpers.py") and is_test_path("src/a/test_b.py")
    assert is_test_path("src/a/b_test.py") and is_test_path("conftest.py")
    assert not is_test_path("src/practice/durations.py")


def test_the_workflow_offers_typed_fields_and_the_skill_binds_to_it() -> None:
    workflow, skill = coding_workflow(), coding_skill()
    names = [field.name for field in workflow.parameters]
    assert names == ["repository", "requirement", "file", "tests", "max_repairs"]
    assert skill.commands[0].target == workflow.metadata.identity


def test_a_host_with_coding_installs_the_capability_and_lists_its_repositories(
    tmp_path: Path,
) -> None:
    from test_host_wiring import ready

    from capabilities.coding_change.manifest import CHANGE_SPEC, REPOSITORIES_FUNCTION
    from host_runtime.host import build_runtime, choice_sources

    binding = CodingHostBinding.model_validate({"runner_python": BASE_PYTHON, "repositories": [
        {"name": "practice", "path": str(tmp_path / "repo"), "writable": ["src/**/*.py"]}]})
    plain, layout = ready(tmp_path)
    config = plain.model_copy(update={"coding": binding})
    with build_runtime(config, layout=layout) as runtime:
        assert runtime.agent.gateway.bridge.installed.get(CHANGE_SPEC.identity) is not None
    listed = choice_sources(config, layout).functions[REPOSITORIES_FUNCTION]({}, {})
    assert [item.value for item in listed] == ["practice"]
    assert REPOSITORIES_FUNCTION not in choice_sources(plain, layout).functions


@requires_win32
def test_doctor_names_what_coding_still_needs(tmp_path: Path) -> None:
    from test_host_wiring import ready

    from host_runtime.host import inspect_coding

    repo = repository(tmp_path)
    plain, _ = ready(tmp_path / "host")
    binding = {"runner_python": BASE_PYTHON, "repositories": [
        {"name": "practice", "path": str(repo), "writable": ["src/**/*.py"]},
        {"name": "plain", "path": str(tmp_path), "writable": ["*.py"]}]}
    config = plain.model_copy(update={"coding": CodingHostBinding.model_validate(binding)})
    check = inspect_coding(config, rule_present=lambda _python: False)
    assert check.status == "failed"
    assert "New-NetFirewallRule" in check.detail and "plain is not a git checkout" in check.detail
    launcher = plain.model_copy(update={"coding": CodingHostBinding.model_validate(
        {**binding, "runner_python": sys.executable})})
    assert "venv launcher" in inspect_coding(launcher).detail
