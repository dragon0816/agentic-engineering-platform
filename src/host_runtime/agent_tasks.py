"""Installed Agent Task templates: exact versions a schedule may target.

An Agent Task is a portable `TaskContract` executed by
`LocalAgent.run_task` -- the same admission, `GatewayTaskExecutor` scope and
data-egress checks, Bridge policy on every tool call and host-side completion
validation that `aep-host run-task` uses. There is no Registry asset kind or
installer for one yet, so the first release reads owner-installed templates
from `assets/agent-tasks/*.json` in the workspace, beside installed
Workflows. A template carries intent and exact references only. It names no
actor, grant or approval: the Host supplies the bound member as actor, and a
schedule execution grant remains a separate owner decision.

A template declares no runtime parameters in this release, so a scheduled
Agent Task takes no runtime inputs and nothing is interpolated into its
objective.
"""

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from agent.data_policy import DataClass
from agent.task_contract import (
    CompletionCheck,
    ExpectedOutput,
    TaskContract,
    TaskExecutionConstraints,
)
from common.assets import AssetIdentity, RegistryContract
from common.base import Symbol, Text
from common.execution import TraceIdentifiers
from host_runtime.workspace import documents

AGENT_TASK_DIRECTORY = Path("assets") / "agent-tasks"


class AgentTaskTemplate(RegistryContract):
    """One exact Agent Task version, without actor, trace or authority."""

    kind: Literal["agent_task"] = "agent_task"
    identity: AssetIdentity
    description: Text
    task_type: Symbol = "general"
    objective: Text = Field(max_length=20000, repr=False)
    declared_classification: DataClass = "UNCLASSIFIED"
    classified_by: Symbol | None = None
    skills: tuple[AssetIdentity, ...] = Field(default=(), max_length=20)
    allowed_capabilities: tuple[AssetIdentity, ...] = Field(default=(), max_length=30)
    prohibited_capabilities: tuple[AssetIdentity, ...] = Field(default=(), max_length=30)
    expected_outputs: tuple[ExpectedOutput, ...] = Field(min_length=1, max_length=20)
    checks: tuple[CompletionCheck, ...] = Field(min_length=1, max_length=40)
    constraints: TaskExecutionConstraints = TaskExecutionConstraints()

    @model_validator(mode="after")
    def builds_a_valid_task(self) -> Self:
        # The TaskContract's own rules (unique outputs, a check per output,
        # classification, no credentials) apply to every template.
        self.to_task(
            actor="template-check",
            task_id="template-check",
            trace=TraceIdentifiers(
                trace_id="template-check", request_id="template-check", span_id="template-check"
            ),
        )
        return self

    def to_task(self, *, actor: str, task_id: str, trace: TraceIdentifiers) -> TaskContract:
        return TaskContract(
            task_id=task_id,
            trace=trace,
            actor=actor,
            namespace=self.identity.namespace,
            task_type=self.task_type,
            objective=self.objective,
            declared_classification=self.declared_classification,
            classified_by=self.classified_by,
            skills=self.skills,
            allowed_capabilities=self.allowed_capabilities,
            prohibited_capabilities=self.prohibited_capabilities,
            expected_outputs=self.expected_outputs,
            checks=self.checks,
            constraints=self.constraints,
        )


def installed_agent_tasks(workspace_root: Path) -> dict[tuple[str, str, str], AgentTaskTemplate]:
    """Templates that read cleanly; an identity installed twice is refused."""
    directory = Path(workspace_root) / AGENT_TASK_DIRECTORY
    found: dict[tuple[str, str, str], AgentTaskTemplate] = {}
    duplicates: set[tuple[str, str, str]] = set()
    if not directory.is_dir():
        return {}
    for path in sorted(directory.glob("*.json")):
        try:
            items = [AgentTaskTemplate.model_validate(item) for item in documents(path)]
        except Exception:  # noqa: BLE001 - an unreadable template is not installed
            continue
        for item in items:
            key = item.identity.key
            if key in found:
                duplicates.add(key)
            found[key] = item
    return {key: value for key, value in found.items() if key not in duplicates}
