"""A conversation turn on the shared Harness (unification U4, owner 2026-10-09).

The Gateway's tool loop is the `execute` stage. The Host then checks the answer
against what actually happened in the turn, never against the model's word:

- `no_unbacked_action_claim`: an answer that says it ran, wrote, created,
  installed or downloaded something needs a tool call that succeeded in this
  turn; an answer that says it made a lasting change (a rule, a setting,
  something remembered for later: 「規則我已改成」, 「以後都會」, "I've updated
  the rule") needs a tool that changes something, not only reads, to have
  succeeded in this turn (owner 2026-10-20: after a read tool the Agent
  answered 「規則我已改成…」 with nothing saved); a memory proposal (M3) is
  not such a tool, since nothing is saved before the person's press;
- `named_outputs_exist`: every file the answer names under a task folder
  (`coding.workspace_roots`) exists and is not empty;
- `reusable_request_drafted`: when the person asked for something reusable
  (「做成可以重複用的」, 「做成 workflow」, 「以後都用這個」, 「建立一個工具」)
  and the turn ran one-off code (`coding__…`) but drafted no Workflow, the
  answer fails while a draft tool is offered: the person gets the install
  card only from a draft (owner 2026-10-20: an org-chart script ran once and
  nothing reached Capabilities).

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
import logging
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

_LOG = logging.getLogger(__name__)

CLAIM_CHECK = "no_unbacked_action_claim"
OUTPUT_CHECK = "named_outputs_exist"
REUSE_CHECK = "reusable_request_drafted"
#: The tools that give the person a Workflow draft and its install card.
DRAFT_TOOLS = frozenset({"authoring__draft_workflow", "authoring__revise_workflow"})
#: Memory proposals (accumulated memory M3): a card the person presses; until
#: then nothing is saved, so they never back a claim of a lasting change.
PROPOSAL_ONLY_TOOLS = frozenset({"memory__propose_preference", "memory__propose_note"})
TURN_SKILL = AssetIdentity(namespace="host", name="conversation-turn", version="1.0.0")

# A completed action on something concrete, in Chinese or English. 「已」 used
# as an adjective (「已安裝的 Workflow」, 「已完成的步驟」) is not a claim.
_CLAIM = re.compile(
    r"(已經?|已)(成功)?(幫你|替你|為你)?(執行|跑完|產生|生成|建立|寫入|寫好|存檔|儲存|輸出|安裝|"
    r"下載|送出|上傳|更新|完成|做好|處理好|處理完|寄出|發送|刪除)(?![的之])"
    r"|已經(幫你|替你|為你)"
    r"|\b(I|I've|I have|we|we've|we have)\s+(have\s+)?(ran|run|executed|created|generated|"
    r"wrote|written|saved|installed|downloaded|uploaded|submitted|done|completed|finished)\b",
    re.IGNORECASE,
)
# What ends the part of an answer a claim is read in: a sentence or a clause
# introduced by a colon.
_SENTENCE_BREAK = re.compile(r"[。！!？?；;：:\n]")
# A condition, an offer or something still to come before the claim in its
# sentence: 「如果是已安裝 Workflow，我會開…」, 「我可以…」, 「要的話我會…」,
# "I can…", "if …, I will…" say what would happen, not what did (owner
# report 2026-10-25).
_NOT_DONE = re.compile(
    r"如果|假如|要是|倘若|若是|若|萬一|一旦|只要|如需|的話|等你|待你|"
    r"我可以|可以幫|可以替|我能|我會|我將|將會|會幫|會替|是否|要不要"
    r"|\b(?:if|unless|once|whether|can|could|may|might|shall|should|would|will|want\s+me)\b",
    re.IGNORECASE,
)
#: Why a claim failed, as the model is told on the retry and the log keeps.
CLAIM_REASON = (
    "the answer says an action was completed, but no tool call succeeded "
    "in this turn; do it with a tool, or do not say it was done"
)
PERSISTENT_REASON = (
    "the answer says a lasting change was made (a rule, a setting, something "
    "remembered for later), but no tool that changes anything succeeded in this "
    "turn. You keep no rules between conversations unless a tool saves them: say it "
    "applies to this conversation only, and propose it as a preference "
    "(memory__propose_preference: saved only when the person presses 存成偏好), a "
    "Workflow draft or a settings proposal for the person to apply instead"
)
MISSING_REASON = "files the answer names are not there: "
REUSE_REASON = (
    "the person asked for something reusable, but this turn only ran one-off code and "
    "drafted no Workflow, so nothing reaches Capabilities. Draft it with "
    "authoring__draft_workflow: a coding/run-python@1.0.0 step with the script as a fixed "
    "input and the values that change as typed parameters; the person installs it from "
    "the card"
)
#: What the person reads under an answer that still failed a check: short
#: Traditional Chinese, the same in Agent Web and Telegram (both take the
#: Gateway's answer). The English reasons stay in the log and the retry.
NOTE_MARK = "（系統檢查："
CLAIM_NOTE = NOTE_MARK + "這一輪沒有成功執行任何工具，回答中『已完成』的說法未經驗證）"
PERSISTENT_NOTE = (
    NOTE_MARK + "這一輪沒有儲存任何規則或設定，回答中『已改好』『以後都會』的說法未經驗證，"
    "只適用於這次對話）"
)
MISSING_NOTE = NOTE_MARK + "回答提到的檔案不存在或是空的：{files}）"
REUSE_NOTE = NOTE_MARK + "這一輪只執行了一次性的程式，沒有建立可重複使用的 Workflow 草稿）"
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
# The person asks for something to keep and reuse, not a one-off result.
_REUSABLE = re.compile(
    r"可以?(?:重複|重覆)(?:使)?用|可重用|重複使用|重覆使用"
    r"|(?:做成|建立|建成|變成|存成|弄成|寫成|做一個|建一個|做個|建個)\s*(?:一個|一個新的)?\s*"
    r"(?:workflow|工作流程|工具)"
    r"|以後都(?:用|照|跑)(?:這個|這樣|這套|這支|這份)"
    r"|(?:建立|做|寫|建)(?:一)?個(?:小)?工具"
    r"|\breusable\b|\breuse\s+(?:it|this)\b"
    r"|\b(?:make|turn|save|build)\s+(?:it|this|that)?\s*(?:into|as)?\s*(?:a\s+)?"
    r"(?:workflow|tool)\b",
    re.IGNORECASE,
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


def claims_done(text: str) -> bool:
    """Whether `text` says, as done, an action on something concrete. A
    match inside a condition, an offer or a promise (a marker earlier in its
    sentence) does not count."""
    for match in _CLAIM.finditer(text):
        start = max(
            (found.end() for found in _SENTENCE_BREAK.finditer(text, 0, match.start())),
            default=0,
        )
        if not _NOT_DONE.search(text, start, match.start()):
            return True
    return False


def person_notes(reasons: list[str]) -> list[str]:
    """The short Traditional Chinese note for each failed check's reason."""
    notes: list[str] = []
    for reason in reasons:
        if reason == CLAIM_REASON:
            note = CLAIM_NOTE
        elif reason == PERSISTENT_REASON:
            note = PERSISTENT_NOTE
        elif reason == REUSE_REASON:
            note = REUSE_NOTE
        elif reason.startswith(MISSING_REASON):
            files = (
                reason.removeprefix(MISSING_REASON)
                .replace(" does not exist", "（不存在）")
                .replace(" is empty", "（是空的）")
                .replace("; ", "、")
            )
            note = MISSING_NOTE.format(files=files)
        else:
            note = NOTE_MARK + "回答未通過檢查）"
        if note not in notes:
            notes.append(note)
    return notes


def check_answer(
    text: str, tools: tuple[Any, ...], roots: tuple[str, ...]
) -> tuple[list[HarnessCheckResult], list[str]]:
    """The two Host checks, with a plain reason for each one that failed."""
    reasons: list[str] = []
    succeeded = any(_succeeded(item) for item in tools)
    claim_ok = succeeded or not claims_done(text or "")
    if not claim_ok:
        reasons.append(CLAIM_REASON)
    elif not any(_succeeded(item) and not _reads_only(item) for item in tools) and (
        _PERSISTENT.search(text or "")
    ):
        claim_ok = False
        reasons.append(PERSISTENT_REASON)
    missing = []
    for path in named_files(text, roots):
        if not path.is_file():
            missing.append(f"{path} does not exist")
        elif path.stat().st_size == 0:
            missing.append(f"{path} is empty")
    if missing:
        reasons.append(MISSING_REASON + "; ".join(missing[:5]))
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


def check_reuse(
    person: str, tools: tuple[Any, ...], can_draft: bool
) -> tuple[HarnessCheckResult, str | None]:
    """A reusable request answered with one-off code and no Workflow draft."""
    one_off = any(_succeeded(item) and str(item.name).startswith("coding__") for item in tools)
    drafted = any(_succeeded(item) and item.name in DRAFT_TOOLS for item in tools)
    failed = can_draft and one_off and not drafted and bool(_REUSABLE.search(person or ""))
    reason = REUSE_REASON if failed else None
    return HarnessCheckResult(
        check_id=REUSE_CHECK,
        status="failed" if failed else "passed",
        evidence_ref="drafts-checked",
    ), reason


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
    """A Knowledge answer, a tool whose command is a read verb, a memory
    proposal (nothing is saved before the person's press), or a delegation
    whose sub-agent had read tools only."""
    if str(getattr(item, "name", "")) in PROPOSAL_ONLY_TOOLS:
        return True
    host = getattr(item, "host", None)
    if host is not None and isinstance(host.data, dict) and "knowledge_harness" in host.data:
        return True
    if (
        host is not None
        and isinstance(host.data, dict)
        and "delegation" in host.data
        and host.data.get("read_only") is True
    ):
        # A sub-agent with read tools only (multi-agent V1) changed nothing.
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
        person: str = "",
        can_draft: Callable[[], bool] = lambda: False,
    ) -> None:
        self.run_turn, self.history, self.roots, self.message = run_turn, history, roots, message
        # The person's own message, and whether this turn offered a draft tool.
        self.person, self.can_draft = person, can_draft
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
        reuse, reason = check_reuse(self.person, self.result.tools, self.can_draft())
        checks.append(reuse)
        if reason is not None:
            self.reasons.append(reason)
        if self.reasons:
            self.checked, self.checked_reasons = self.result, list(self.reasons)
        return tuple(checks)


async def checked_turn(
    run_turn: RunTurn,
    history: tuple[Any, ...],
    roots: tuple[str, ...],
    message: Callable[[str, str], Any],
    request_id: str,
    *,
    person: str = "",
    can_draft: Callable[[], bool] = lambda: False,
) -> Any:
    """Run the turn, check it, retry once on a failed check."""
    actions = ConversationActions(run_turn, history, roots, message, person, can_draft)
    plan = build_plan(
        task_id="turn-" + hashlib.sha256(request_id.encode()).hexdigest()[:12],
        task_sha256=hashlib.sha256(request_id.encode()).hexdigest(),
        domain="conversation",
        skill=TURN_SKILL,
        guidance=SkillHarnessGuidance(domains=("conversation",), fallback="retry", max_retries=1),
        host_checks=(CLAIM_CHECK, OUTPUT_CHECK, REUSE_CHECK),
        max_retries=1,
    )
    run = await run_harness_async(plan, actions)
    result = actions.result
    if run.phase != "validated" and actions.reasons and result is not None:
        result = _with_note(result, actions.reasons, request_id)
    elif (
        result is not None
        and result.status == "failed"
        and actions.checked is not None
        and actions.checked is not result
    ):
        # The retry pass failed outright: the first answer, marked by the Host.
        result = _with_note(actions.checked, actions.checked_reasons, request_id)
    return result


def _with_note(result: Any, reasons: list[str], request_id: str = "") -> Any:
    """The answer with the person's short note; the English reasons go to
    the log (telemetry records which check failed)."""
    _LOG.warning("Host check failed for %s: %s", request_id or "a turn", " | ".join(reasons))
    note = "\n\n" + "\n".join(person_notes(reasons))
    return result.model_copy(update={"text": (result.text or "") + note})
