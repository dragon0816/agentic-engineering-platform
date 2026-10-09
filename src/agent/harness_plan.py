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
# Where a retry resumes (harness unification U1, owner 2026-10-09): "first"
# collects again (Knowledge re-retrieves); "execute" keeps the collected
# context and executes again with the failed checks as feedback (a coding
# repair keeps its plan).
RetryFrom = Literal["first", "execute"]


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
    retry_from: RetryFrom = "first"
    # The failure code when checks still fail and no retry is left; an
    # adapter names its own (coding: repair_budget_exceeded).
    exhausted_code: Symbol = "host_check_failed"

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


def build_plan(
    *,
    task_id: str,
    task_sha256: str,
    domain: HarnessDomain,
    skill: AssetIdentity,
    guidance: SkillHarnessGuidance | None,
    host_checks: tuple[str, ...],
    max_retries: int,
    requested_capabilities: tuple[AssetIdentity, ...] = (),
    retry_from: RetryFrom = "first",
    exhausted_code: str = "host_check_failed",
) -> AgentHarnessPlan:
    """A plan from a Skill's guidance and the Host's own checks and budget,
    for adapters whose Host request is not a TaskContract (coding, Workflow,
    conversation). The Skill narrows: its retries never exceed the Host's."""
    guidance = guidance or SkillHarnessGuidance(domains=(domain,))
    if domain not in guidance.domains:
        raise ValueError("selected Skill does not support this harness domain")
    retry_budget = min(max_retries, guidance.max_retries)
    fallback: Fallback = guidance.fallback
    if fallback == "retry" and retry_budget == 0:
        fallback = "needs_input"
    collect = domain in ("knowledge", "coding") or guidance.context_required
    return AgentHarnessPlan(
        task_id=task_id, task_sha256=task_sha256, domain=domain, skill=skill,
        stages=("collect_context", "execute", "validate") if collect
        else ("execute", "validate"),
        requested_capabilities=requested_capabilities, host_checks=host_checks,
        skill_evidence=guidance.required_evidence, fallback=fallback,
        retry_budget=retry_budget, retry_from=retry_from, exhausted_code=exhausted_code,
    )


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
