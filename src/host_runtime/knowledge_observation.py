"""Map an exact Bridge Knowledge query into the shared harness observations.

The selected Skill owns procedural guidance. This adapter only reports the
Bridge outcome and revalidates Raw citations; it grants no new capability.
"""

from collections.abc import Callable
from typing import Any

from agent.harness_run import HarnessCheckResult
from agent.harness_runner import HarnessActionFailure
from knowledge.evidence import answer_claims_overlap_raw, connected_facets
from knowledge.evolution import KnowledgeAnswerRecord


class KnowledgeBridgeActions:
    def __init__(
        self,
        invoke: Callable[[], dict[str, Any]],
        *,
        required_evidence: tuple[str, ...],
        required_facets: tuple[str, ...] = (),
        relation_required: bool = False,
    ) -> None:
        self.invoke = invoke
        self.required_evidence = required_evidence
        self.required_facets = required_facets
        self.relation_required = relation_required
        self.result: dict[str, Any] | None = None

    def collect_context(self) -> str:
        # The exact asset was selected by the Host. Retrieval is still owned
        # by the authorized Bridge capability invoked in execute().
        return "knowledge_asset_selected"

    def execute(self) -> str:
        self.result = self.invoke()
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
                        "passed" if checked is not None
                        and answer_claims_overlap_raw(checked.answer) else "failed"
                    ),
                    evidence_ref="bridge_claim_overlap",
                )
            )
        return tuple(checks)

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
        missing = [
            facet for facet in self.required_facets
            if facet not in observations
            or not (
                any(
                    citation.model_dump_json() in cited
                    for citation in observations[facet].citations
                )
                or any(
                    facet in (relation.left, relation.right)
                    for relation in cited_relations
                )
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
                "supported" if answer_claims_overlap_raw(checked.answer) else "unverified"
            ),
        }
