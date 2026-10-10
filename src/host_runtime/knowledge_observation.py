"""Map an exact Bridge Knowledge query into the shared harness observations.

The selected Skill owns procedural guidance. This adapter only reports the
Bridge outcome and revalidates Raw citations; it grants no new capability.
"""

from collections.abc import Callable
from typing import Any

import telemetry.recorder as telemetry
from agent.harness_run import HarnessCheckResult
from agent.harness_runner import HarnessActionFailure
from knowledge.evidence import (
    answer_claims_overlap_raw,
    answer_concerns_subject,
    connected_facets,
    facet_supported_by,
    unsupported_product_recommendations,
)
from knowledge.evolution import KnowledgeAnswerRecord
from knowledge.procedure import KnowledgeProcedure


class KnowledgeBridgeActions:
    def __init__(
        self,
        invoke: Callable[[], dict[str, Any]],
        *,
        required_evidence: tuple[str, ...],
        required_facets: tuple[str, ...] = (),
        relation_required: bool = False,
        required_subject: str | None = None,
        procedure: KnowledgeProcedure | None = None,
        broadened: Callable[[int], dict[str, Any]] | None = None,
        retry_budget: int = 0,
    ) -> None:
        self.invoke = invoke
        # A retry asks again with wider retrieval (harness unification U5);
        # the plan's budget, from the Knowledge Skill, bounds every attempt.
        self.broadened = broadened
        self.retry_budget = retry_budget
        self.attempt = 0
        self.required_evidence = required_evidence
        self.required_facets = required_facets
        self.relation_required = relation_required
        self.required_subject = required_subject
        self.procedure = procedure
        self.result: dict[str, Any] | None = None

    def collect_context(self) -> str:
        # The exact asset was selected by the Host. Retrieval is still owned
        # by the authorized Bridge capability invoked in execute().
        return "knowledge_asset_selected"

    def _ask(self) -> dict[str, Any]:
        attempt, self.attempt = self.attempt, self.attempt + 1
        if attempt and self.broadened is not None:
            return self.broadened(attempt)
        return self.invoke()

    def execute(self) -> str:
        self.result = self._ask()
        code = self._code(self.result)
        if (not self.result["ok"] and self.broadened is not None
                and code in {"knowledge_insufficient_evidence", "knowledge_not_grounded"}
                and self.attempt - 1 < self.retry_budget):
            telemetry.emit("retry.scheduled", state="executing", attributes={
                "retry_reason": code, "loop_index": self.attempt})
            self.result = self._ask()
        if not self.result["ok"]:
            outcome = self.result.get("outcome") or {}
            capability = outcome.get("capability") or {}
            failure = capability.get("failure") or {}
            code = failure.get("code") or "knowledge_query_failed"
            raise HarnessActionFailure(
                code,
                needs_input=code in {
                    "knowledge_insufficient_evidence", "knowledge_not_grounded"
                },
            )
        return "bridge_knowledge_answer"

    def validate(self) -> tuple[HarnessCheckResult, ...]:
        record = None if self.result is None else self.result.get("record")
        checked: KnowledgeAnswerRecord | None = None
        try:
            checked = KnowledgeAnswerRecord.model_validate(record)
        except ValueError:
            status = "failed"
        else:
            status = (
                "passed" if checked.answer.text.strip() and checked.cited_passages
                and checked.citation_policy == self._citation_policy()
                else "failed"
            )
        if set(self.required_evidence) - {"raw_citations"}:
            status = "failed"
        checks = [
            HarnessCheckResult(
                check_id="answer_nonempty",
                status=status,
                evidence_ref=(
                    "unmet_skill_evidence" if set(self.required_evidence) - {"raw_citations"}
                    else "bridge_raw_record"
                ),
            ),
        ]
        if self.required_facets:
            report = self.facet_report()
            checks.append(
                HarnessCheckResult(
                    check_id="facet_coverage",
                    status=("passed" if report["facet_status"] == "covered" else "failed"),
                    evidence_ref="bridge_facet_assessment",
                )
            )
            checks.append(
                HarnessCheckResult(
                    check_id="claim_support",
                    status=(
                        "passed" if checked is not None and self._claims_supported(checked)
                        else "failed"
                    ),
                    evidence_ref="bridge_claim_overlap",
                )
            )
        return tuple(checks)

    def _inference_label(self) -> str | None:
        return None if self.procedure is None else self.procedure.inference_label

    def _citation_policy(self) -> str:
        return "raw_only" if self.procedure is None else self.procedure.citation_policy

    def _claims_supported(self, checked: KnowledgeAnswerRecord) -> bool:
        """Host-check cited claims under the citation policy the Skill declared.

        A record whose policy differs from the installed Skill's is refused,
        so the Bridge cannot widen what counts as citable evidence.
        """
        if checked.citation_policy != self._citation_policy():
            return False
        allow_wiki = checked.citation_policy == "wiki_primary"
        return (
            answer_claims_overlap_raw(
                checked.answer, inference_label=self._inference_label(),
                allow_wiki=allow_wiki,
            )
            and (
                self.procedure is None
                or not unsupported_product_recommendations(
                    checked.answer, checked.answer.question, self.procedure,
                    allow_wiki=allow_wiki,
                )
            )
            and (
                self.required_subject is None
                or answer_concerns_subject(
                    checked.answer, self.required_subject, allow_wiki=allow_wiki
                )
            )
        )

    def facet_report(self) -> dict[str, object]:
        """Host-check cited facet and relationship observations independently."""
        record = None if self.result is None else self.result.get("record")
        try:
            checked = KnowledgeAnswerRecord.model_validate(record)
        except ValueError:
            return {
                "facet_status": "missing" if self.required_facets else "not_assessed",
                "missing_facets": list(self.required_facets) if self.required_facets else None,
                "relation_status": "missing" if self.relation_required else "not_requested",
                "retrieval_attempts": {},
            }
        assessment = checked.assessment
        if not self.required_facets or assessment is None:
            return {
                "facet_status": "not_assessed",
                "missing_facets": None,
                "relation_status": "not_requested",
                "retrieval_attempts": {},
            }
        cited = {item.citation.model_dump_json() for item in checked.cited_passages}
        observations = {item.name: item for item in assessment.facets}
        cited_relations = tuple(
            item for item in assessment.relations
            if item.citation.model_dump_json() in cited
        )
        allow_wiki = checked.citation_policy == "wiki_primary"

        def cited_support(facet: str) -> bool:
            # Any cited passage that meets the Skill's own facet rule counts,
            # under the citation policy the Skill declared (owner 2026-10-07).
            return (
                self.procedure is not None
                and checked.citation_policy == self._citation_policy()
                and any(
                    facet_supported_by(
                        passage, facet, self.procedure, checked.answer.question,
                        allow_wiki=allow_wiki,
                    )
                    for passage in checked.cited_passages
                )
            )

        missing = [
            facet for facet in self.required_facets
            if not (
                (
                    facet in observations
                    and any(
                        citation.model_dump_json() in cited
                        for citation in observations[facet].citations
                    )
                )
                or any(
                    facet in (relation.left, relation.right)
                    for relation in cited_relations
                )
                or cited_support(facet)
            )
        ]
        linked = connected_facets(
            self.required_facets,
            tuple(
                (item.left, item.right) for item in cited_relations
            ),
        )
        relation_status = (
            "supported" if self.relation_required and linked
            else ("missing" if self.relation_required else "not_requested")
        )
        return {
            "facet_status": (
                "covered" if not missing and relation_status != "missing" else "missing"
            ),
            "missing_facets": missing,
            "relation_status": relation_status,
            "retrieval_attempts": {
                item.name: item.attempts for item in assessment.facets
            },
            "claim_status": (
                "supported" if self._claims_supported(checked) else "unverified"
            ),
        }

    @staticmethod
    def _code(result: dict[str, Any]) -> str:
        outcome = result.get("outcome") or {}
        failure = (outcome.get("capability") or {}).get("failure") or {}
        return str(failure.get("code") or "")
