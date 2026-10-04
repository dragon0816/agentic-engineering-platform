"""Map an exact Bridge Knowledge query into the shared harness observations.

The selected Skill owns procedural guidance. This adapter only reports the
Bridge outcome and revalidates Raw citations; it grants no new capability.
"""

from collections.abc import Callable
from typing import Any

from agent.harness_run import HarnessCheckResult
from agent.harness_runner import HarnessActionFailure
from knowledge.evolution import KnowledgeAnswerRecord


class KnowledgeBridgeActions:
    def __init__(
        self,
        invoke: Callable[[], dict[str, Any]],
        *,
        required_evidence: tuple[str, ...],
    ) -> None:
        self.invoke = invoke
        self.required_evidence = required_evidence
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
        return (
            HarnessCheckResult(
                check_id="answer_nonempty",
                status=status,
                evidence_ref=(
                    "unmet_skill_evidence" if set(self.required_evidence) - {"raw_citations"}
                    else "bridge_raw_record"
                ),
            ),
        )
