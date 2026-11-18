"""What an Agent's outcome says, in the words a person reads.

Kept apart from any one way in. The window, the web page and the command
line show the same answer to the same request, and an ingress that rendered
its own would be a second place where the platform appears to have said
something different.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from capabilities.workflow_author.contracts import WorkflowDraft
from host_runtime.agent import LocalAgentOutcome


def capability_details(outcome: LocalAgentOutcome, *, preview: bool = False) -> list[str]:
    """Closed failure details, plus an explicitly known draft's refusal.

    Do not infer task status from arbitrary output keys or echo a capability
    payload. Telegram uses codes only; local ingresses may show the draft's
    intended refusal preview, never its echoed request or SOP.
    """
    result = outcome.capability
    if result is None:
        return []
    lines: list[str] = []
    if result.failure is not None:
        lines.append(f"failure: {result.failure.code}")
        if result.failure.code == "timeout" and result.handler_invoked:
            lines.append("Execution may still be running; do not repeat it before reconciliation.")
    for warning in result.warnings:
        if re.fullmatch(r"operation_id=operation-[0-9a-f]{32}", warning):
            lines.append(warning)
    decision = outcome.decision
    if (
        result.status == "succeeded"
        and decision is not None
        and decision.target is not None
        and decision.target.key == ("workflow-author", "draft", "1.0.0")
    ):
        try:
            draft = WorkflowDraft.model_validate(result.data)
        except (ValidationError, TypeError, ValueError):
            return lines
        if draft.refusal is not None:
            lines.append(f"draft: not produced ({draft.refusal})")
            if preview and draft.preview.strip():
                lines.append(draft.preview)
    return lines


def readable(outcome: LocalAgentOutcome) -> str:
    """What to show a person.

    A workflow's last step often carries a rendering meant for reading --
    the weekly report's plan is the whole dry run in words. Where there is
    one it is shown, because the alternative is a person reading JSON to
    find out what a run would do. Where there is not, the step's own data is
    shown as it stands rather than summarised into something that might be
    wrong.
    """
    if outcome.refusal is not None:
        return f"Refused: {outcome.refusal}"
    lines: list[str] = []
    decision = outcome.decision
    if decision is not None and decision.target is not None:
        target = decision.target
        lines.append(f"{decision.kind}: {target.namespace}/{target.name}@{target.version}")
    if outcome.capability is not None:
        lines.append(f"capability: {outcome.capability.status}")
        lines.extend(capability_details(outcome, preview=True))
    if outcome.workflow is not None:
        run = outcome.workflow.run
        lines.append(f"{run.status}, {run.completed_steps} step(s)")
        if run.failure is not None:
            lines.append(f"failure: {run.failure.code}")
        results = outcome.workflow.step_results
        if results:
            data = results[-1].data
            if isinstance(data, dict):
                shown = data.get("preview")
                if isinstance(shown, str) and shown.strip():
                    lines.append("")
                    lines.append(shown)
                else:
                    lines.append("")
                    lines.append(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    if outcome.unrecorded is not None:
        lines.append(f"the run record could not be written: {outcome.unrecorded}")
    return "\n".join(lines) or "nothing came back"


#: Keys a Workflow's last step may carry for the channels (loan replies,
#: owner 2026-10-20): a Workflow the person may start next, and the ids of
#: action cards the run made. Both are offers; nothing runs or sends by them.
FOLLOW_UP_KEY = "follow_up"
CARDS_KEY = "action_cards"


def run_follow_up(outcome: LocalAgentOutcome) -> dict[str, object] | None:
    """The `follow_up` of a succeeded Workflow run's last step, if any."""
    data = _last_step_data(outcome)
    offered = data.get(FOLLOW_UP_KEY) if data is not None else None
    if isinstance(offered, dict) and isinstance(offered.get("workflow"), dict):
        return offered
    return None


def run_cards(outcome: LocalAgentOutcome) -> list[str]:
    """The action card ids a Workflow run's last step made."""
    data = _last_step_data(outcome)
    listed = data.get(CARDS_KEY) if data is not None else None
    if not isinstance(listed, list):
        return []
    return [item for item in listed if isinstance(item, str)]


def _last_step_data(outcome: LocalAgentOutcome) -> dict[str, object] | None:
    workflow = outcome.workflow
    if outcome.refusal is not None or workflow is None or workflow.run.status != "succeeded":
        return None
    if not workflow.step_results:
        return None
    data = workflow.step_results[-1].data
    return dict(data) if isinstance(data, dict) else None
