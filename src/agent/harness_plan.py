"""Shared, provider-neutral plan envelope for Workflow, Knowledge and Coding.

This is a planning contract, not a new executor. The host's TaskContract and
Bridge policy retain authority over capability scope and completion checks.
"""

from typing import Literal, Self

from pydantic import Field, model_validator

from agent.skills import HarnessDomain, SkillHarnessGuidance, SkillManifest
from agent.task_contract import TaskContract
from common.assets import AssetIdentity
from common.base import Contract, Sha256, Symbol

HarnessStage = Literal["collect_context", "execute", "validate"]
Fallback = Literal["needs_input", "stop", "retry"]


class AgentHarnessPlan(Contract):
    task_id: Symbol
    task_sha256: Sha256
    domain: HarnessDomain
    skill: AssetIdentity
    stages: tuple[HarnessStage, ...]
    requested_capabilities: tuple[AssetIdentity, ...] = Field(max_length=30)
    host_checks: tuple[Symbol, ...] = Field(min_length=1, max_length=40)
    skill_evidence: tuple[Symbol, ...] = Field(max_length=20)
    fallback: Fallback
    retry_budget: int = Field(ge=0, le=3, strict=True)

    @model_validator(mode="after")
    def closed_plan(self) -> Self:
        if self.stages not in (
            ("execute", "validate"),
            ("collect_context", "execute", "validate"),
        ):
            raise ValueError("harness stages must end in independent validation")
        if self.fallback == "retry" and self.retry_budget == 0:
            raise ValueError("retry fallback requires a positive task budget")
        if len(self.host_checks) != len(set(self.host_checks)):
            raise ValueError("host checks must be unique")
        scope = {item.key for item in self.requested_capabilities}
        if len(self.requested_capabilities) != len(scope):
            raise ValueError("requested capability references must be unique")
        return self


def plan_task(
    task: TaskContract, skill: SkillManifest, domain: HarnessDomain
) -> AgentHarnessPlan:
    """Apply installed Skill guidance without widening the host task scope."""
    if skill.metadata.identity not in task.skills:
        raise ValueError("selected Skill is not declared by the task")
    guidance = skill.harness_guidance
    if guidance is None:
        guidance = SkillHarnessGuidance(domains=(domain,))
    if domain not in guidance.domains:
        raise ValueError("selected Skill does not support this harness domain")
    retry_budget = min(task.constraints.max_retries, guidance.max_retries)
    fallback: Fallback = guidance.fallback
    if fallback == "retry" and retry_budget == 0:
        fallback = "needs_input"
    collect = domain in ("knowledge", "coding") or guidance.context_required
    stages: tuple[HarnessStage, ...] = (
        ("collect_context", "execute", "validate")
        if collect else ("execute", "validate")
    )
    return AgentHarnessPlan(
        task_id=task.task_id,
        task_sha256=task.digest,
        domain=domain,
        skill=skill.metadata.identity,
        stages=stages,
        requested_capabilities=task.allowed_capabilities,
        host_checks=tuple(check.check_id for check in task.checks),
        skill_evidence=guidance.required_evidence,
        fallback=fallback,
        retry_budget=retry_budget,
    )
