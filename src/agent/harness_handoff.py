"""How a domain Harness result leaves the conversation loop (G1, G4; owner 2026-10-18).

Generic for every domain; the Knowledge, Workflow and Coding adapters only
supply their verdicts.

G1, a result that failed Host checks is not rewritten by the model:

- A Harness tool whose data says `harness_verdict` is `validated`, or
  `not_validated` with `harness_output`, ends the turn with the Harness's own
  text (its Host note included). Its record and evidence stay on the tool.
- Otherwise the model writes the answer. If any Harness result of the turn
  failed its Host checks and no later call of the same tool succeeded (a
  repair), the Host appends a visible note naming it. The note is the Host's,
  not the prompt's: the model cannot remove or soften it.

Which results carry a verdict (everything else, such as a plain capability or
an authoring tool, is ordinary conversation and is left alone):

- a Knowledge tool: `harness_verdict` in its host data;
- a Workflow tool: the run on the shared Harness (`run_workflow_checked`),
  failed when a step or a declared output check failed;
- a Workflow run started by a host tool (a draft's trial run): host data with
  a `run_id` and `status: failed`;
- a capability whose result is a Host validator's verdict (the Coding Harness,
  DUT validation evidence): data with `status: failed`;
- a capability that ran and was refused because its Host checks failed: the
  Coding Harness refuses with `repair_budget_exceeded` when its declared
  commands still fail after every repair (G5, 2026-10-27: the model's "the
  change passed" used to carry no note);
- a delegated sub-agent's result (multi-agent V1) whose answer did not pass
  its own Host checks: host data `delegation_verdict: not_validated`, with
  its `host_note`. Such results are told apart by `harness_key` (one per
  profile and objective), so another delegation's success does not clear it.

G4, consistent output length: a Harness result leaves the loop at the limit
its domain declares (`output_limit_chars`); a cut says so and where the full
result is (`full_result_hint`), never silently.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

#: Failure codes that mean a domain Harness ran and its Host checks failed
#: (the shared runner's default exhausted code and the Coding Harness's), as
#: opposed to a refusal before anything ran.
HOST_CHECK_FAILURE_CODES = frozenset({"host_check_failed", "repair_budget_exceeded"})

UNVERIFIED_NOTE = (
    "\n\n（Host 註記：以下結果未通過 Host 檢查，上面的說明不能把它當成已通過或已驗證——"
)


def harness_reply(data: Any) -> str | None:
    """The turn's answer when a domain Harness returned text (G1); None hands
    the turn back to the model."""
    if not isinstance(data, dict):
        return None
    verdict = data.get("harness_verdict")
    if verdict == "validated" or (verdict == "not_validated" and data.get("harness_output")):
        return str(data.get("answer") or "")
    return None


def _failed_verdict(item: Any) -> str | None:
    """Why this tool result failed its Host checks, or None."""
    if getattr(item, "failure", None) is not None:
        return None  # refused before anything ran: no Harness result
    host = getattr(item, "host", None)
    if host is not None:
        data = host.data if isinstance(host.data, dict) else {}
        if data.get("delegation_verdict") == "not_validated" and host.status == "succeeded":
            return str(data.get("host_note") or "the sub-agent's result was not validated")
        if data.get("harness_verdict") == "not_validated" and not data.get("harness_output"):
            return str(data.get("host_note") or data.get("failure_code") or "not validated")
        if data.get("run_id") and data.get("status") == "failed":
            failure = data.get("failure")
            code = failure.get("code") if isinstance(failure, dict) else None
            return f"Workflow run {data['run_id']} failed" + (f" ({code})" if code else "")
        return None
    workflow = getattr(item, "workflow", None)
    if workflow is not None:
        run = workflow.run
        if run.status != "failed":
            return None
        code = run.failure.code if run.failure is not None else None
        return f"Workflow run {run.run_id} failed" + (f" ({code})" if code else "")
    capability = getattr(item, "capability", None)
    if capability is not None and capability.status == "succeeded":
        data = capability.data
        if isinstance(data, dict) and data.get("status") == "failed":
            return "the Host's validator reported status failed"
    elif capability is not None and capability.failure is not None:
        if capability.failure.code in HOST_CHECK_FAILURE_CODES:
            return f"Host checks failed ({capability.failure.code})"
    return None


def _ran(item: Any) -> bool:
    if getattr(item, "failure", None) is not None:
        return False
    host = getattr(item, "host", None)
    if host is not None:
        return bool(host.status != "failed")
    capability = getattr(item, "capability", None)
    if capability is not None:
        return bool(capability.status == "succeeded")
    workflow = getattr(item, "workflow", None)
    return workflow is not None and workflow.run.status == "succeeded"


def unverified(tools: Sequence[Any]) -> list[str]:
    """Each Harness result of the turn that failed its Host checks and that no
    later successful call of the same tool replaced."""
    open_failures: dict[str, tuple[str, str]] = {}
    for item in tools:
        key = _result_key(item)
        reason = _failed_verdict(item)
        if reason is not None:
            open_failures[key] = (item.name, reason)
        elif _ran(item):
            open_failures.pop(key, None)
    return [f"{name}：{reason}" for name, reason in open_failures.values()]


def _result_key(item: Any) -> str:
    """Which earlier result a later one repairs: the tool, or the result's own
    `harness_key` when it gives one (a delegation per profile and objective)."""
    host = getattr(item, "host", None)
    data = host.data if host is not None and isinstance(host.data, dict) else {}
    key = data.get("harness_key")
    return str(key) if isinstance(key, str) and key else str(item.name)


def with_unverified_note(text: str, tools: Sequence[Any]) -> str:
    lines = unverified(tools)
    if not lines:
        return text
    return text + UNVERIFIED_NOTE + "；".join(lines) + "。）"


# G4: what a Harness that declares no output limit gets. It equals the
# Knowledge default (4,000 synthesis tokens at 4 characters per token).
DEFAULT_OUTPUT_LIMIT_CHARS = 16_000


def capped(
    text: str, limit: Any, full_result: str | None = None
) -> tuple[str, dict[str, int] | None]:
    """Cut at the domain's declared limit, never silently (G4)."""
    bound = limit if isinstance(limit, int) and not isinstance(limit, bool) and limit > 0 else None
    bound = bound or DEFAULT_OUTPUT_LIMIT_CHARS
    if len(text) <= bound:
        return text, None
    where = full_result or "完整結果保留在這次工具紀錄（record）中。"
    note = f"\n\n…（Host 註記：結果超過這個領域宣告的輸出上限 {bound} 字，已在此截斷。{where}）"
    return text[:bound] + note, {"limit_chars": bound, "full_chars": len(text)}
