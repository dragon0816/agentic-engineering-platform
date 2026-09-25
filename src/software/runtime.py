"""Reproduce a Software issue, run the Coding Harness, and prepare review evidence."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Self

from pydantic import Field, field_validator, model_validator

from common.assets import reject_embedded_secrets
from common.base import Contract, Symbol, Text
from common.execution import Failure, TraceIdentifiers
from harness.contracts import (
    CodingHarnessRequest,
    HarnessBudget,
    PlannedChange,
    ValidationCase,
    WorkspaceSnapshot,
)
from harness.runtime import CodingHarness
from harness.workspace import BoundedWorkspace, WorkspaceRefused
from software.evolution import (
    SoftwareCatalog,
    SoftwareDevelopmentRequest,
    SoftwareDevelopmentResult,
)
from software.source_control import SourceControlAdapter


class SoftwareDevelopmentRefused(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class InstalledRepository(Contract):
    """Trusted host configuration, separate from shared Software metadata."""

    locator: Text
    workspace_root: Text
    artifact_path: Text
    allowed_paths: tuple[Text, ...] = Field(min_length=1)
    validation_command: Symbol
    regression_cases: tuple[ValidationCase, ...] = Field(min_length=1)
    skill_versions: tuple[Text, ...] = Field(min_length=1)

    @field_validator("workspace_root")
    @classmethod
    def absolute_workspace(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if not (
            PurePosixPath(normalized).is_absolute()
            or (len(normalized) > 2 and normalized[1:3] == ":/")
        ):
            raise ValueError("installed repository workspace must be absolute")
        return value

    @model_validator(mode="after")
    def bounded_repository(self) -> Self:
        artifact = PlannedChange(path=self.artifact_path, purpose="artifact").path
        allowed = tuple(
            PlannedChange(path=path, purpose="allowed").path for path in self.allowed_paths
        )
        if artifact not in allowed or len(allowed) != len(set(allowed)):
            raise ValueError("artifact must be in a unique repository path allowlist")
        if any(case.kind != "regression" for case in self.regression_cases):
            raise ValueError("installed repository cases must be regressions")
        names = tuple(case.name for case in self.regression_cases)
        if len(names) != len(set(names)):
            raise ValueError("repository regression case names must be unique")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class InstalledRepositories:
    def __init__(self) -> None:
        self._items: dict[str, InstalledRepository] = {}

    def register(self, repository: InstalledRepository) -> None:
        checked = InstalledRepository.model_validate(repository)
        if checked.locator in self._items:
            raise ValueError("repository workspace already installed")
        self._items[checked.locator] = checked

    def get(self, locator: str) -> InstalledRepository | None:
        return self._items.get(locator)


class SoftwareDevelopmentService:
    def __init__(
        self,
        catalog: SoftwareCatalog,
        repositories: InstalledRepositories,
        harness: CodingHarness,
        source_control: SourceControlAdapter,
    ) -> None:
        self.catalog = catalog
        self.repositories = repositories
        self.harness = harness
        self.source_control = source_control

    def run(
        self, trace: TraceIdentifiers, request: SoftwareDevelopmentRequest
    ) -> SoftwareDevelopmentResult:
        checked = SoftwareDevelopmentRequest.model_validate(request)
        improvement = checked.improvement
        if improvement.development_approval.status != "approved":
            raise SoftwareDevelopmentRefused("development_not_approved")
        manifest = self.catalog.get(improvement.target)
        if manifest is None:
            raise SoftwareDevelopmentRefused("software_version_not_found")
        if (
            manifest.metadata.owner != improvement.owner
            or manifest.repository != improvement.repository
        ):
            raise SoftwareDevelopmentRefused("software_route_changed")
        installed = self.repositories.get(manifest.repository.locator)
        if installed is None:
            raise SoftwareDevelopmentRefused("repository_not_installed")
        workspace = BoundedWorkspace(installed.workspace_root, installed.allowed_paths)
        if workspace.revision() != manifest.repository.revision:
            raise SoftwareDevelopmentRefused("repository_revision_changed")
        new_case = ValidationCase(
            name="reported-failure-acceptance",
            kind="new",
            input=improvement.report.example_input,
            expected=improvement.report.expected_output,
        )
        harness_request = CodingHarnessRequest(
            workspace=WorkspaceSnapshot(
                root=installed.workspace_root,
                starting_revision=manifest.repository.revision,
            ),
            requirement=(
                f"Expected: {improvement.report.expected_behavior} "
                f"Actual: {improvement.report.actual_behavior}"
            ),
            artifact_path=installed.artifact_path,
            allowed_paths=installed.allowed_paths,
            allowed_commands=(installed.validation_command,),
            cases=(new_case, *installed.regression_cases),
            skill_versions=installed.skill_versions,
            budget=HarnessBudget(max_repair_attempts=0, max_commands=1),
        )
        try:
            reproduction = self.harness.commands.run(
                installed.validation_command, workspace, harness_request
            )
        except WorkspaceRefused as error:
            raise SoftwareDevelopmentRefused(error.code) from error
        if reproduction.status == "passed":
            return SoftwareDevelopmentResult(
                trace=trace,
                improvement=improvement,
                status="unreproduced",
                reproduction=reproduction,
                failure=Failure(
                    code="issue_not_reproduced",
                    message="The supplied example did not reproduce before any change",
                ),
            )
        issue_failure = next(
            (item for item in reproduction.failures if item.case == new_case.name), None
        )
        if issue_failure is None or issue_failure.observed != improvement.report.observed_output:
            raise SoftwareDevelopmentRefused("reproduction_evidence_mismatch")
        regression_failures = tuple(
            item for item in reproduction.failures if item.case != new_case.name
        )
        if regression_failures:
            return SoftwareDevelopmentResult(
                trace=trace,
                improvement=improvement,
                status="failed",
                reproduction=reproduction,
                failure=Failure(
                    code="repository_baseline_failed",
                    message="Repository regressions already fail before the proposed change",
                ),
            )
        result = self.harness.run(trace, harness_request)
        if result.status != "validated":
            return SoftwareDevelopmentResult(
                trace=trace,
                improvement=improvement,
                status="failed",
                reproduction=reproduction,
                harness=result,
                failure=result.failure
                or Failure(code="validation_failed", message="Software validation failed"),
            )
        candidate = self.source_control.prepare(trace, improvement, result)
        return SoftwareDevelopmentResult(
            trace=trace,
            improvement=improvement,
            status="validated",
            reproduction=reproduction,
            harness=result,
            pull_request=candidate,
        )
