"""Source-control preparation boundary; the CI adapter performs no external write."""

import hashlib
from typing import Protocol

from common.execution import TraceIdentifiers
from harness.contracts import CodingHarnessResult
from software.evolution import PullRequestCandidate, SoftwareImprovementRequest


class SourceControlAdapter(Protocol):
    def prepare(
        self,
        trace: TraceIdentifiers,
        improvement: SoftwareImprovementRequest,
        result: CodingHarnessResult,
    ) -> PullRequestCandidate: ...


class InertSourceControlAdapter:
    """Records review artifacts in memory and never calls Git or a remote API."""

    def __init__(self) -> None:
        self._prepared: list[PullRequestCandidate] = []
        self.external_writes = 0

    @property
    def prepared(self) -> tuple[PullRequestCandidate, ...]:
        return tuple(self._prepared)

    def prepare(
        self,
        trace: TraceIdentifiers,
        improvement: SoftwareImprovementRequest,
        result: CodingHarnessResult,
    ) -> PullRequestCandidate:
        if result.status != "validated" or not result.changes:
            raise ValueError("a PR candidate requires a validated change set")
        validation_sha = hashlib.sha256(result.model_dump_json().encode("utf-8")).hexdigest()
        candidate = PullRequestCandidate(
            candidate_id=f"software-change-{len(self._prepared) + 1}",
            trace=trace,
            target=improvement.target,
            repository=improvement.repository,
            title=f"Fix {improvement.target.name}: {improvement.report.actual_behavior}",
            body=(
                f"Issue {improvement.request_id}. Expected: "
                f"{improvement.report.expected_behavior} Validation: {validation_sha}"
            ),
            changes=result.changes,
            validation_sha256=validation_sha,
        )
        self._prepared.append(candidate)
        return candidate
