"""The Knowledge Harness, shared by both routes (harness unification U5, owner 2026-10-09).

Moved out of Agent Web so the conversation's tool route runs exactly what the
direct route runs: plan from the Knowledge Skill, the Bridge capability, the
Host checks (answer_nonempty, facet_coverage, claim_support), and the visible
answer that only says what the evidence supports. The owner decided the tool
route returns this validated answer instead of the conversation model's
rewrite of the Bridge record.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from agent.harness_plan import plan_task
from agent.harness_runner import run_harness
from agent.task_contract import (
    CompletionCheck,
    ExpectedOutput,
    TaskContract,
    TaskExecutionConstraints,
)
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from common.execution import TraceIdentifiers
from common.local_agent import LocalCapabilityRequest
from host_runtime.answers import readable
from host_runtime.contracts import KnowledgeAskRequest
from host_runtime.knowledge_observation import KnowledgeBridgeActions
from knowledge.evidence import connected_facets, evidence_excerpt
from knowledge.evolution import KnowledgeAnswerRecord, KnowledgeQueryRequest
from knowledge.procedure import KnowledgeProcedure
from knowledge.query import cited_numbers


def _trace() -> TraceIdentifiers:
    value = uuid.uuid4().hex
    return TraceIdentifiers(
        trace_id=f"trace-{value}", request_id=f"request-{value}", span_id=f"span-{value}"
    )


def knowledge_source_lines(record: dict[str, Any]) -> list[str]:
    """List cited sources: Raw paths, or Wiki pages with their Raw provenance."""
    answer = record.get("answer") or {}
    passages = answer.get("passages") or []
    provenance = {
        item.get("wiki_page"): tuple(item.get("raw_refs") or ())
        for item in record.get("wiki_provenance") or []
    }
    lines = []
    for number in sorted(cited_numbers(answer.get("text") or "")):
        if number < 1 or number > len(passages):
            continue
        citation = passages[number - 1].get("citation") or {}
        if citation.get("kind") == "wiki" and citation.get("wiki_page"):
            page = citation["wiki_page"]
            refs = provenance.get(page, ())
            backing = (
                "來源：" + "、".join(f"`{Path(ref).name}`" for ref in refs[:3])
                + ("…" if len(refs) > 3 else "")
                if refs else "缺來源連結"
            )
            lines.append(f"[{number}] Wiki：{Path(page).stem}（{backing}）")
        elif citation.get("raw_ref"):
            lines.append(f"[{number}] `{citation['raw_ref']}`")
    return lines


def harness_skill(skills: Any) -> Any:
    """The installed Knowledge Skill the Harness plans with: published or
    validated, Knowledge harness guidance, and the exact query command."""
    for manifest in skills.manifests():
        guidance = manifest.harness_guidance
        if (manifest.metadata.lifecycle in {"validated", "published"}
                and guidance is not None and "knowledge" in guidance.domains
                and any(command.kind == "capability"
                        and command.target == KNOWLEDGE_QUERY_SPEC.identity
                        for command in manifest.commands)):
            return manifest.metadata.identity
    return None


def broaden(procedure: KnowledgeProcedure, attempt: int) -> KnowledgeProcedure:
    """Wider retrieval for a retry: every facet query, more passages per
    facet, more Wiki index hits. The Skill's rules and policy are unchanged."""
    return procedure.model_copy(update={
        "facets": tuple(facet.model_copy(update={
            "collect_all_queries": True,
            "max_passages": min(6, facet.max_passages + 2 * attempt)})
            for facet in procedure.facets),
        "wiki_index_hits": min(32, procedure.wiki_index_hits * 2 ** attempt),
    })


class KnowledgeHarness:
    def __init__(self, runtime: Any, namespace: str | None) -> None:
        self.runtime = runtime
        self.namespace = namespace

    def for_tool(self, question: str, asset: Any) -> dict[str, Any]:
        """The conversation tool route: the same Harness as the direct route."""
        skill = harness_skill(self.runtime.agent.gateway.router.commands.skills)
        return self.ask(KnowledgeAskRequest(asset=asset, question=question, skill=skill))

    def ask(self, request: KnowledgeAskRequest) -> dict[str, Any]:
        item = KnowledgeAskRequest.model_validate(request)
        if item.skill is None:
            return self._ask_knowledge_bridge(item, _trace())
        installed = self.runtime.agent.gateway.router.commands.skills.discover(
            item.skill.namespace
        )
        skill = next(
            (candidate for candidate in installed if candidate.metadata.identity == item.skill),
            None,
        )
        if (
            skill is None
            or skill.metadata.lifecycle not in {"validated", "published"}
            or skill.harness_guidance is None
            or "knowledge" not in skill.harness_guidance.domains
            or not any(
                command.kind == "capability" and command.target == KNOWLEDGE_QUERY_SPEC.identity
                for command in skill.commands
            )
        ):
            return {
                "ok": False,
                "answer": (
                    "Select an installed Knowledge Asking Skill with the exact query command."
                ),
                "record": None,
                "outcome": None,
                "harness": None,
            }
        try:
            procedure = (
                KnowledgeProcedure.model_validate(skill.procedure)
                if skill.procedure else None
            )
        except ValueError:
            return {
                "ok": False,
                "answer": "The installed Knowledge Skill procedure is invalid.",
                "record": None,
                "outcome": None,
                "harness": None,
            }
        required_facets = (
            tuple(facet.name for facet in procedure.requested_facets(item.question))
            if procedure is not None else ()
        )
        relation_required = bool(
            procedure is not None
            and procedure.require_relation_for_combination
            and len(required_facets) > 1
        )
        trace = _trace()
        task = TaskContract(
            task_id=f"knowledge-{uuid.uuid4().hex}",
            trace=trace,
            actor=self.runtime.actor,
            namespace=self.namespace or skill.metadata.identity.namespace,
            task_type="knowledge",
            objective=item.question,
            skills=(skill.metadata.identity,),
            resource_refs=("knowledge_asset",),
            allowed_capabilities=(KNOWLEDGE_QUERY_SPEC.identity,),
            expected_outputs=(
                ExpectedOutput(output_id="answer", artifact_ref="bridge_raw_record"),
            ),
            checks=(
                CompletionCheck(
                    check_id="answer_nonempty", output_id="answer", kind="nonempty"
                ),
                *(
                    (
                        CompletionCheck(
                            check_id="facet_coverage", output_id="answer", kind="nonempty"
                        ),
                        CompletionCheck(
                            check_id="claim_support", output_id="answer", kind="nonempty"
                        ),
                    )
                    if required_facets else ()
                ),
            ),
            # The Knowledge Skill decides how many retries (U5), up to the cap.
            constraints=TaskExecutionConstraints(
                max_retries=min(3, skill.harness_guidance.max_retries)),
        )
        plan = plan_task(task, skill, "knowledge")
        actions = KnowledgeBridgeActions(
            lambda: self._ask_knowledge_bridge(item, trace, procedure=procedure),
            required_evidence=plan.skill_evidence,
            required_facets=required_facets,
            relation_required=relation_required,
            required_subject=procedure.subject(item.question) if procedure else None,
            procedure=procedure,
            broadened=None if procedure is None else (
                lambda attempt: self._ask_knowledge_bridge(
                    item, trace, procedure=broaden(procedure, attempt))),
            retry_budget=plan.retry_budget,
        )
        run = run_harness(plan, actions)
        base = actions.result or {
            "ok": False, "answer": "The Knowledge query did not run.",
            "record": None, "outcome": None,
        }
        facet_report = actions.facet_report()
        incomplete = run.phase != "validated" and base["ok"] and required_facets
        assessment = (base.get("record") or {}).get("assessment") or {}
        if incomplete and assessment.get("status") == "missing":
            record_answer = (base["record"].get("answer") or {}).get("text") or ""
            visible_answer = (
                self._knowledge_partial_preview(base["record"], assessment)
                if record_answer and facet_report.get("claim_status") == "supported"
                else self._knowledge_gap_preview(base["record"], assessment, procedure)
            )
        elif incomplete and facet_report["facet_status"] == "missing":
            missing = facet_report["missing_facets"]
            gaps = list(missing) if isinstance(missing, list) else []
            if facet_report["relation_status"] == "missing":
                gaps.append("direct_relationship")
            record = base.get("record") or {}
            record_answer = ((record.get("answer") or {}).get("text") or "").strip()
            if record_answer and facet_report.get("claim_status") == "supported":
                # Keep what the evidence supports and name the gap, rather than
                # discarding a verified answer (owner 2026-10-07).
                sources = knowledge_source_lines(record)
                visible_answer = (
                    "已查到可引用的部分資料：\n\n" + record_answer
                    + ("\n\n來源：\n" + "\n".join(sources) if sources else "")
                    + "\n\n未能以證據支持：" + ", ".join(gaps)
                    + "。因此不能把上列資料當成完整的推薦或比較。"
                )
            else:
                kind = "Knowledge" if record.get("citation_policy") == "wiki_primary" else "Raw"
                visible_answer = (
                    f"The retrieved {kind} evidence does not validate the complete answer. "
                    f"Missing: {', '.join(gaps)}. No cross-facet recommendation is accepted."
                )
        elif run.phase == "needs_input" and required_facets and not base["ok"]:
            visible_answer = (
                "The Knowledge query did not produce a validated answer. "
                "Unverified requested facets: " + ", ".join(required_facets) + "."
            )
        elif run.phase == "validated" or not base["ok"] or actions.no_support:
            # A reply that only says nothing supports an answer is shown as it
            # is, but it is not a validated answer.
            visible_answer = base["answer"]
            record = base.get("record") or {}
            if run.phase == "validated" and record.get("citation_policy") == "wiki_primary":
                visible_answer += "\n\n來源：\n" + "\n".join(knowledge_source_lines(record))
        else:
            visible_answer = "The selected Skill requires evidence this Host cannot yet verify."
        return {
            **base,
            "ok": run.phase == "validated" and base["ok"],
            "answer": visible_answer,
            "harness": run.model_dump(mode="json"),
            "evidence": {
                "raw_citations": len((base.get("record") or {}).get("cited_passages") or ()),
                **(
                    facet_report
                    if required_facets
                    else {"facet_status": "not_assessed", "missing_facets": None}
                ),
            },
        }

    @staticmethod
    def _knowledge_partial_preview(record: dict[str, Any], assessment: dict[str, Any]) -> str:
        """Show cited facts with their source paths while keeping gaps visible."""
        answer = record.get("answer") or {}
        text = (answer.get("text") or "").strip()
        sources = knowledge_source_lines(record)
        gaps = list(assessment.get("missing_facets") or [])
        if assessment.get("relation_required") and not connected_facets(
            tuple(item["name"] for item in assessment.get("facets") or []),
            tuple(
                (item["left"], item["right"])
                for item in assessment.get("relations") or []
            ),
        ):
            gaps.append("direct_relationship")
        return (
            "已查到可引用的部分資料：\n\n" + text +
            ("\n\n來源：\n" + "\n".join(sources) if sources else "") +
            "\n\n尚未證實：" + ", ".join(gaps) +
            "。因此不能把上列資料當成完整的推薦或比較。"
        )

    @staticmethod
    def _knowledge_gap_preview(
        record: dict[str, Any], assessment: dict[str, Any],
        procedure: KnowledgeProcedure | None,
    ) -> str:
        """Expose cited Raw candidates without presenting them as a recommendation."""
        passages = (record.get("answer") or {}).get("passages") or []
        lines = ["已找到以下原始資料片段，但完整比較仍未通過證據檢查："]
        question = (record.get("answer") or {}).get("question") or ""
        subject = procedure.subject(question) if procedure else None
        facet_terms = {facet.name: facet.support_terms + facet.link_terms
                       for facet in procedure.facets} if procedure else {}
        priority = {
            facet.name: tuple(
                pattern
                for requirement in facet.evidence_requirements
                if re.search(requirement.question_pattern, question, re.IGNORECASE)
                for pattern in requirement.evidence_patterns
            )
            for facet in procedure.facets
        } if procedure else {}
        for facet in assessment.get("facets") or []:
            citations = facet.get("citations") or []
            if not citations:
                continue
            for passage in passages:
                if passage.get("citation") != citations[0]:
                    continue
                excerpt = evidence_excerpt(
                    passage.get("text") or "", subject=subject,
                    terms=facet_terms.get(facet["name"], ()),
                    priority_patterns=priority.get(facet["name"], ()),
                )
                source = (passage.get("citation") or {}).get("raw_ref") or "Raw"
                lines.append(f"- {facet['name']}：{excerpt}（來源：`{source}`）")
                break
        missing = list(assessment.get("missing_facets") or [])
        if assessment.get("relation_required") and not connected_facets(
            tuple(item["name"] for item in assessment.get("facets") or []),
            tuple(
                (item["left"], item["right"])
                for item in assessment.get("relations") or []
            ),
        ):
            missing.append("direct_relationship")
        lines.append("仍缺：" + ", ".join(missing) + "。目前不能把這些片段當成已證實的推薦或比較。")
        return "\n".join(lines)

    def _ask_knowledge_bridge(
        self, item: KnowledgeAskRequest, trace: TraceIdentifiers,
        *, procedure: KnowledgeProcedure | None = None,
    ) -> dict[str, Any]:
        device = self.runtime.config.device
        local = LocalCapabilityRequest(
            ingress="local",
            actor=self.runtime.actor,
            bridge_id=device.bridge_id,
            target=KNOWLEDGE_QUERY_SPEC.identity,
            arguments=KnowledgeQueryRequest(
                asset=item.asset, question=item.question, procedure=procedure
            ).model_dump(
                mode="json", exclude_none=True
            ),
            trace=trace,
        )
        import asyncio

        # Knowledge asking is a read-only capability; it runs concurrently.
        outcome = asyncio.run(self.runtime.agent.execute_capability(local))
        record: KnowledgeAnswerRecord | None = None
        if (
            outcome.refusal is None
            and outcome.capability is not None
            and outcome.capability.status == "succeeded"
        ):
            record = KnowledgeAnswerRecord.model_validate(outcome.capability.data)
        return {
            "ok": record is not None,
            "answer": (
                record.answer.text
                if record is not None
                else self._knowledge_failure_text(outcome)
            ),
            "record": (None if record is None else json.loads(record.model_dump_json())),
            "outcome": json.loads(outcome.model_dump_json()),
        }

    @staticmethod
    def _knowledge_failure_text(outcome: Any) -> str:
        failure = outcome.capability.failure if outcome.capability is not None else None
        if failure is None:
            return readable(outcome)
        explanations = {
            "knowledge_insufficient_evidence": (
                "No sufficient evidence was found in the selected Knowledge asset."
            ),
            "knowledge_not_grounded": (
                "The model answer could not be verified against its citations."
            ),
            "knowledge_model_failed": (
                "The configured LLM Gateway could not synthesize an answer from the "
                "retrieved evidence."
            ),
            "permission_denied": "This user is not granted the Knowledge query capability.",
        }
        explanation = explanations.get(failure.code, "The Knowledge query did not complete.")
        return f"{explanation} ({failure.code})"

