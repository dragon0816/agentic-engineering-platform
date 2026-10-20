"""A conversation turn on the shared Harness (unification U4, owner 2026-10-09).

The Gateway's tool loop is the `execute` stage. The Host then checks the answer
against what actually happened in the turn, never against the model's word:

- `no_unbacked_action_claim`: an answer that says it ran, wrote, created,
  installed or downloaded something needs a tool call that succeeded in this
  turn; an answer that says it made a lasting change (a rule, a setting,
  something remembered for later: 「規則我已改成」, 「以後都會」, "I've updated
  the rule") needs a tool that changes something, not only reads, to have
  succeeded in this turn (owner 2026-10-20: after a read tool the Agent
  answered 「規則我已改成…」 with nothing saved);
- `named_outputs_exist`: every file the answer names under a task folder
  (`coding.workspace_roots`) exists and is not empty.

A failed check gets one retry: the model sees which check failed and why. If it
still fails, the answer is returned with the Host's note, so the person is
never told about work that did not happen. If the retry pass itself fails (a
stopped loop, a model failure), the person gets the first answer with the
Host's note rather than a bare failure.

The retry pair (the answer and the Host's note) is passed to the turn apart
from the person's history: pictures the person attached stay on their own
message, sent once, and the retry pair is text (live test 2026-10-20).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from agent.harness_plan import build_plan
from agent.harness_run import HarnessCheckResult
from agent.harness_runner import HarnessActionFailure, run_harness_async
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
    re.IGNORECASE,
)
# A lasting change: a rule, a setting or preference, something remembered for
# later. First person or at a clause start, so a description of the person's
# own settings (「資料夾已設定為…」) or of what a button will do is not one.
_CN_START = r"(?:^|[。！!？?，,、；;：:\s]|我|規則|設定|偏好|預設|做法)"
_PERSISTENT = re.compile(
    _CN_START + r"(?:也|都)?(?:已經|已)(?:把.{0,20}?)?"
    r"(?:改成|改為|設定為|設定成|設定好|設好|設定|記住|記下|更新規則|更新設定|"
    r"更新了規則|調整規則|調整了規則|修改規則|修改了規則)(?![的過])"
    r"|我(?:會|將)(?:記住|記得)"
    r"|(?:^|[。！!？?，,；;：:\s]|我)(?:以後|往後|今後|從今以後|從現在起|從現在開始|"
    r"下次起|下次開始)(?:我)?(?:都|一律|就)?會"
    r"|\b(?:I've|I\s+have|I)\s+(?:updated|changed|set|saved|adjusted|modified)\s+"
    r"(?:the\s+|your\s+|this\s+|that\s+|my\s+)?(?:rules?|settings?|preferences?|defaults?|"
    r"behaviou?r)\b"
    r"|\bI(?:'ll|\s+will)\s+(?:always\s+)?remember\b"
    r"|\b(?:from\s+now\s+on|going\s+forward|in\s+(?:the\s+)?future|next\s+time)\s*,?\s+"
    r"I(?:'ll|\s+will)\b"
    r"|\bI(?:'ve|\s+have)\s+(?:noted|remembered|memori[sz]ed)\b",
    re.IGNORECASE | re.MULTILINE,
)
# A tool whose command only reads (`cards__list`, `authoring__get_workflow`)
# cannot back a lasting change.
_READ_COMMANDS = (
    "list",
    "get",
    "show",
    "preview",
    "search",
    "read",
    "find",
    "lookup",
    "view",
    "history",
    "proposals",
    "inspect",
    "query",
    "ask",
)
_PATH = re.compile(
    r"[A-Za-z]:[\\/][^\s\"'<>|*?`，。、）)]+?\.[A-Za-z0-9]{1,8}(?=[\s\"'`，。、）)]|$)"
)


def named_files(text: str, roots: tuple[str, ...]) -> list[Path]:
    found: list[Path] = []
    for match in _PATH.findall(text or ""):
        resolved = containing_root(match.rstrip(".,;:"), roots)
        if resolved is not None and resolved not in found:
            found.append(resolved)
    return found


def check_answer(
    text: str, tools: tuple[Any, ...], roots: tuple[str, ...]
) -> tuple[list[HarnessCheckResult], list[str]]:
    """The two Host checks, with a plain reason for each one that failed."""
    reasons: list[str] = []
    succeeded = any(_succeeded(item) for item in tools)
    claim_ok = succeeded or not _CLAIM.search(text or "")
    if not claim_ok:
        reasons.append(
            "the answer says an action was completed, but no tool call succeeded "
            "in this turn; do it with a tool, or do not say it was done"
        )
    elif not any(_succeeded(item) and not _reads_only(item) for item in tools) and (
        _PERSISTENT.search(text or "")
    ):
        claim_ok = False
        reasons.append(
            "the answer says a lasting change was made (a rule, a setting, something "
            "remembered for later), but no tool that changes anything succeeded in this "
            "turn. You keep no rules between conversations unless a tool saves them: say it "
            "applies to this conversation only, and offer a Workflow or Skill draft or a "
            "settings proposal for the person to apply instead"
        )
    missing = []
    for path in named_files(text, roots):
        if not path.is_file():
            missing.append(f"{path} does not exist")
        elif path.stat().st_size == 0:
            missing.append(f"{path} is empty")
    if missing:
        reasons.append("files the answer names are not there: " + "; ".join(missing[:5]))
    return [
        HarnessCheckResult(
            check_id=CLAIM_CHECK,
            status="passed" if claim_ok else "failed",
            evidence_ref="tools-" + str(len(tools)),
        ),
        HarnessCheckResult(
            check_id=OUTPUT_CHECK,
            status="failed" if missing else "passed",
            evidence_ref="files-checked",
        ),
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


def _reads_only(item: Any) -> bool:
    """A Knowledge answer, or a tool whose command is a read verb."""
    host = getattr(item, "host", None)
    if host is not None and isinstance(host.data, dict) and "knowledge_harness" in host.data:
        return True
    command = str(getattr(item, "name", "")).rsplit("__", 1)[-1].lower()
    return command.startswith(_READ_COMMANDS)


#: `run_turn(history, retry)`: the person's history, and the Host check's retry
#: pair to put after it (empty on the first pass).
RunTurn = Callable[[tuple[Any, ...], tuple[Any, ...]], Awaitable[Any]]


class ConversationActions:
    def __init__(
        self,
        run_turn: RunTurn,
        history: tuple[Any, ...],
        roots: tuple[str, ...],
        message: Callable[[str, str], Any],
    ) -> None:
        self.run_turn, self.history, self.roots, self.message = run_turn, history, roots, message
        self.result: Any = None
        self.reasons: list[str] = []
        # The answer that failed a check, and why: what the person gets with
        # the Host's note when the retry pass does not produce an answer.
        self.checked: Any = None
        self.checked_reasons: list[str] = []

    async def execute(self) -> str:
        retry: tuple[Any, ...] = ()
        if self.result is not None and self.reasons:
            # The retry: the model sees its answer and what the Host found.
            retry = (
                self.message("assistant", self.result.text or ""),
                self.message(
                    "user",
                    "[Host check failed] "
                    + " | ".join(self.reasons)
                    + ". Fix this and answer again.",
                ),
            )
        self.result = await self.run_turn(self.history, retry)
        if self.result.status != "answered":
            # No answer to check: the run stops where the turn did, failed or
            # waiting for the person (a question, a guard stop), never
            # `validated` (live test 2026-10-20).
            self.reasons = []
            code = self.result.failure.code if self.result.failure is not None else "not_answered"
            raise HarnessActionFailure(code, needs_input=self.result.status == "needs_input")
        return f"turn-{self.result.model_turns}"

    def validate(self) -> tuple[HarnessCheckResult, ...]:
        checks, self.reasons = check_answer(self.result.text, self.result.tools, self.roots)
        if self.reasons:
            self.checked, self.checked_reasons = self.result, list(self.reasons)
        return tuple(checks)


async def checked_turn(
    run_turn: RunTurn,
    history: tuple[Any, ...],
    roots: tuple[str, ...],
    message: Callable[[str, str], Any],
    request_id: str,
) -> Any:
    """Run the turn, check it, retry once on a failed check."""
    actions = ConversationActions(run_turn, history, roots, message)
    plan = build_plan(
        task_id="turn-" + hashlib.sha256(request_id.encode()).hexdigest()[:12],
        task_sha256=hashlib.sha256(request_id.encode()).hexdigest(),
        domain="conversation",
        skill=TURN_SKILL,
        guidance=SkillHarnessGuidance(domains=("conversation",), fallback="retry", max_retries=1),
        host_checks=(CLAIM_CHECK, OUTPUT_CHECK),
        max_retries=1,
    )
    run = await run_harness_async(plan, actions)
    result = actions.result
    if run.phase != "validated" and actions.reasons and result is not None:
        result = _with_note(result, actions.reasons)
    elif (
        result is not None
        and result.status == "failed"
        and actions.checked is not None
        and actions.checked is not result
    ):
        # The retry pass failed outright: the first answer, marked by the Host.
        result = _with_note(actions.checked, actions.checked_reasons)
    return result


def _with_note(result: Any, reasons: list[str]) -> Any:
    note = "\n\n（Host 檢查未通過：" + "；".join(reasons) + "）"
    return result.model_copy(update={"text": (result.text or "") + note})
