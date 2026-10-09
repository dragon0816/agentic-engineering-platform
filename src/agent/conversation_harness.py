"""A conversation turn on the shared Harness (unification U4, owner 2026-10-09).

The Gateway's tool loop is the `execute` stage. The Host then checks the answer
against what actually happened in the turn, never against the model's word:

- `no_unbacked_action_claim`: an answer that says it ran, wrote, created,
  installed or downloaded something needs a tool call that succeeded in this
  turn;
- `named_outputs_exist`: every file the answer names under a task folder
  (`coding.workspace_roots`) exists and is not empty.

A failed check gets one retry: the model sees which check failed and why. If it
still fails, the answer is returned with the Host's note, so the person is
never told about work that did not happen.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from agent.harness_plan import build_plan
from agent.harness_run import HarnessCheckResult
from agent.harness_runner import run_harness_async
from agent.skills import SkillHarnessGuidance
from capabilities.coding_change.workspaces import containing_root
from common.assets import AssetIdentity

CLAIM_CHECK = "no_unbacked_action_claim"
OUTPUT_CHECK = "named_outputs_exist"
TURN_SKILL = AssetIdentity(namespace="host", name="conversation-turn", version="1.0.0")

# A completed action on something concrete, in Chinese or English.
_CLAIM = re.compile(
    r"(已經?|已)(成功)?(執行|跑完|產生|生成|建立|寫入|寫好|存檔|儲存|輸出|安裝|下載|送出|上傳|更新)"
    r"|\b(I|I've|I have|we)\s+(have\s+)?(ran|run|executed|created|generated|wrote|written|"
    r"saved|installed|downloaded|uploaded|submitted)\b",
    re.IGNORECASE)
_PATH = re.compile(
    r"[A-Za-z]:[\\/][^\s\"'<>|*?`，。、）)]+?\.[A-Za-z0-9]{1,8}(?=[\s\"'`，。、）)]|$)")


def named_files(text: str, roots: tuple[str, ...]) -> list[Path]:
    found: list[Path] = []
    for match in _PATH.findall(text or ""):
        resolved = containing_root(match.rstrip(".,;:"), roots)
        if resolved is not None and resolved not in found:
            found.append(resolved)
    return found


def check_answer(text: str, tools: tuple[Any, ...], roots: tuple[str, ...]
                 ) -> tuple[list[HarnessCheckResult], list[str]]:
    """The two Host checks, with a plain reason for each one that failed."""
    reasons: list[str] = []
    succeeded = any(_succeeded(item) for item in tools)
    claim_ok = succeeded or not _CLAIM.search(text or "")
    if not claim_ok:
        reasons.append("the answer says an action was completed, but no tool call succeeded "
                       "in this turn; do it with a tool, or do not say it was done")
    missing = []
    for path in named_files(text, roots):
        if not path.is_file():
            missing.append(f"{path} does not exist")
        elif path.stat().st_size == 0:
            missing.append(f"{path} is empty")
    if missing:
        reasons.append("files the answer names are not there: " + "; ".join(missing[:5]))
    return [
        HarnessCheckResult(check_id=CLAIM_CHECK, status="passed" if claim_ok else "failed",
                           evidence_ref="tools-" + str(len(tools))),
        HarnessCheckResult(check_id=OUTPUT_CHECK, status="failed" if missing else "passed",
                           evidence_ref="files-checked"),
    ], reasons


def _succeeded(item: Any) -> bool:
    """As the Gateway counts it: a host tool that did not fail (awaiting the
    owner's approval is a real outcome), or a capability or Workflow that ran."""
    if getattr(item, "failure", None) is not None:
        return False
    if getattr(item, "host", None) is not None:
        return bool(item.host.status != "failed")
    if getattr(item, "capability", None) is not None:
        return bool(item.capability.status == "succeeded")
    workflow = getattr(item, "workflow", None)
    return workflow is not None and workflow.run.status == "succeeded"


class ConversationActions:
    def __init__(self, run_turn: Callable[[tuple[Any, ...]], Awaitable[Any]],
                 history: tuple[Any, ...], roots: tuple[str, ...],
                 message: Callable[[str, str], Any]) -> None:
        self.run_turn, self.history, self.roots, self.message = run_turn, history, roots, message
        self.result: Any = None
        self.reasons: list[str] = []

    async def execute(self) -> str:
        history = self.history
        if self.result is not None and self.reasons:
            # The retry: the model sees its answer and what the Host found.
            history = (*history, self.message("assistant", self.result.text or ""),
                       self.message("user", "[Host check failed] " + " | ".join(self.reasons)
                                    + ". Fix this and answer again."))
        self.result = await self.run_turn(history)
        return f"turn-{self.result.model_turns}"

    def validate(self) -> tuple[HarnessCheckResult, ...]:
        if self.result.status != "answered":
            # A question to the person, or a stopped loop: nothing was claimed.
            self.reasons = []
            return (HarnessCheckResult(check_id=CLAIM_CHECK, status="passed",
                                       evidence_ref="not-answered"),
                    HarnessCheckResult(check_id=OUTPUT_CHECK, status="passed",
                                       evidence_ref="not-answered"))
        checks, self.reasons = check_answer(self.result.text, self.result.tools, self.roots)
        return tuple(checks)


async def checked_turn(run_turn: Callable[[tuple[Any, ...]], Awaitable[Any]],
                       history: tuple[Any, ...], roots: tuple[str, ...],
                       message: Callable[[str, str], Any], request_id: str) -> Any:
    """Run the turn, check it, retry once on a failed check."""
    actions = ConversationActions(run_turn, history, roots, message)
    plan = build_plan(
        task_id="turn-" + hashlib.sha256(request_id.encode()).hexdigest()[:12],
        task_sha256=hashlib.sha256(request_id.encode()).hexdigest(),
        domain="conversation", skill=TURN_SKILL,
        guidance=SkillHarnessGuidance(domains=("conversation",), fallback="retry",
                                      max_retries=1),
        host_checks=(CLAIM_CHECK, OUTPUT_CHECK), max_retries=1)
    run = await run_harness_async(plan, actions)
    result = actions.result
    if run.phase != "validated" and actions.reasons and result is not None:
        note = "\n\n（Host 檢查未通過：" + "；".join(actions.reasons) + "）"
        result = result.model_copy(update={"text": (result.text or "") + note})
    return result
