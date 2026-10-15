"""The two declared validation commands of coding on the Bridge.

`pytest-new` runs the tests that define the requested change; `pytest-suite`
runs the whole test folder as the regression corpus. Both run under the
restricted runner, and pytest's JUnit report, not the model, decides what
passed. Output is scrubbed of anything credential-shaped before it becomes
evidence.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from collections.abc import Mapping
from itertools import count
from pathlib import Path
from typing import Literal

from common.assets import REDACTED, SECRET_PATTERN
from harness.contracts import CodingHarnessRequest, ValidationCase, ValidationFailure
from harness.restricted_runner import RestrictedRunner
from harness.workspace import BoundedWorkspace

NEW_COMMAND = "pytest-new"
SUITE_COMMAND = "pytest-suite"
SUITE_CASE = "suite"
MAX_FAILURE_CHARS = 3_000
MAX_FAILURES = 10
_EXIT_CODES = {
    2: "pytest_interrupted",
    3: "pytest_internal_error",
    4: "pytest_usage_error",
    5: "no_tests_collected",
}


def _scrub(text: str) -> str:
    return SECRET_PATTERN.sub(REDACTED, text)[-MAX_FAILURE_CHARS:]


def new_cases(node_ids: tuple[str, ...]) -> tuple[ValidationCase, ...]:
    return tuple(
        ValidationCase(name=f"new-{index}", kind="new", input=node, expected="passed")
        for index, node in enumerate(node_ids, start=1)
    )


def suite_case(suite: str = "tests") -> ValidationCase:
    return ValidationCase(name=SUITE_CASE, kind="regression", input=suite, expected="passed")


class PytestCommand:
    """A `harness.runtime.ValidationCommand` running pytest restrictedly."""

    def __init__(
        self,
        which: Literal["new", "suite"],
        runner: RestrictedRunner,
        run_dir: Path,
        extra_env: Mapping[str, str] | None = None,
    ) -> None:
        self.which = which
        self.runner = runner
        self.run_dir = run_dir
        self.extra_env = dict(extra_env or {})
        self._serial = count(1)

    def __call__(
        self, workspace: BoundedWorkspace, request: CodingHarnessRequest
    ) -> tuple[ValidationFailure, ...]:
        kind = "new" if self.which == "new" else "regression"
        cases = [case for case in request.cases if case.kind == kind]
        targets = [str(case.input) for case in cases]
        results = self.run_dir / "results"
        results.mkdir(parents=True, exist_ok=True)
        report = results / f"{self.which}-{next(self._serial)}.xml"
        outcome = self.runner.run(
            [
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "-o",
                "addopts=",
                f"--junitxml={report}",
                *targets,
            ],
            cwd=workspace.root,
            run_dir=self.run_dir,
            extra_env=self.extra_env,
        )
        first = cases[0].name
        if outcome.timed_out:
            return (
                ValidationFailure(
                    case=first,
                    code="test_timeout",
                    message="pytest did not finish within the time limit",
                ),
            )
        if outcome.exit_code in _EXIT_CODES or not report.is_file():
            code = _EXIT_CODES.get(outcome.exit_code or 0, "pytest_report_missing")
            return (ValidationFailure(case=first, code=code, message=_scrub(outcome.output)),)
        failures = self._failures(report, cases)
        if outcome.exit_code != 0 and not failures:
            return (
                ValidationFailure(case=first, code="pytest_failed", message=_scrub(outcome.output)),
            )
        return failures

    @staticmethod
    def _failures(report: Path, cases: list[ValidationCase]) -> tuple[ValidationFailure, ...]:
        found: list[ValidationFailure] = []
        for testcase in ElementTree.parse(report).getroot().iter("testcase"):
            problem = testcase.find("failure")
            if problem is None:
                problem = testcase.find("error")
            if problem is None:
                continue
            name = f"{testcase.get('classname', '')}::{testcase.get('name', '')}"
            found.append(
                ValidationFailure(
                    case=_case_for(name, cases),
                    code="test_failed" if problem.tag == "failure" else "test_error",
                    message=_scrub(f"{name}: {problem.get('message', '')}\n{problem.text or ''}"),
                )
            )
            if len(found) >= MAX_FAILURES:
                break
        return tuple(found)


def _case_for(test: str, cases: list[ValidationCase]) -> str:
    """The case whose node id names this test; else the first case."""
    module, _, function = test.partition("::")
    for case in cases:
        node = str(case.input).replace("\\", "/")
        path, _, selected = node.partition("::")
        dotted = path.removesuffix(".py").replace("/", ".")
        if module.endswith(dotted.split(".")[-1]) or module == dotted:
            if not selected or selected.split("::")[-1].split("[")[0] == function.split("[")[0]:
                return case.name
    return cases[0].name
