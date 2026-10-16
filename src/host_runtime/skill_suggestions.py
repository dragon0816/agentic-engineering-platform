"""Suggested Skills from experience, slice S1: detection, report only.

`docs/phases/SKILL_SUGGESTIONS.md` with the owner decisions of 2026-10-16:

- A *request* is a user message that opened a piece of work (not a short
  follow-up), with its answer's status and tool shape, from ONE actor's own
  conversations inside the retention window. Another actor's records are
  never read.
- A deterministic score (weighted Jaccard over `knowledge.query.tokens` plus
  a tool-shape score) is only a pre-filter: it drops obvious one-offs, caps
  the batch and gives the explanation words. It never joins requests.
- The model groups: one structured call per night through the experience
  review's endpoint and alias, over the requests new since the last pass plus
  the stored groups they resemble. Its output is validated strictly (unknown
  ids ignored, counts never trusted) and the groups are persisted so the next
  night sends only new requests.
- A group qualifies at 3 requests in 3 sessions over 2 calendar days; at most
  3 new suggestions a night; installed Skills and Workflows, pending
  candidates and earlier suggestions are deduplicated with a reason.

S1 only writes the nightly report. The model creates, installs and approves
nothing, and no candidate is made here.
"""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import threading
import uuid
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from common.assets import REDACTED, SECRET_PATTERN
from common.base import Contract
from common.execution import TraceIdentifiers
from host_runtime.experience import STORE_FILE, ExperienceSettings, load_settings
from knowledge.query import tokens
from models.contracts import ModelClient

MIN_REQUESTS = 3
MIN_SESSIONS = 3
MIN_DAYS = 2
MAX_NEW_PER_NIGHT = 3
# Pre-filter: a request with no other request this close in another session
# is a one-off and is not sent (it stays pending for a later night).
PREFILTER_FLOOR = 0.2
TEXT_WEIGHT, TOOL_WEIGHT = 0.6, 0.4
# Task-name similarity for dedupe (Normal sensitivity, section 5).
DEDUPE_SIMILARITY = 0.5
EXCERPT_CHARS = 300
EVIDENCE_CHARS = 160
GROUP_EXAMPLES = 2
MAX_EVIDENCE = 20
TASK_CHARS = 120
OUTPUT_CONTRACT = "skill_suggestion_groups"
CHAT_AUTHORING = Path("authoring") / "chat"

_FOLLOW_UPS = {
    "ok",
    "okay",
    "k",
    "yes",
    "no",
    "y",
    "n",
    "thanks",
    "thank you",
    "thx",
    "ty",
    "continue",
    "go on",
    "go ahead",
    "next",
    "retry",
    "again",
    "try again",
    "sure",
    "great",
    "good",
    "done",
    "繼續",
    "继续",
    "好",
    "好的",
    "好喔",
    "好啊",
    "謝謝",
    "谢谢",
    "感謝",
    "對",
    "是",
    "是的",
    "可以",
    "嗯",
    "沒錯",
    "再試一次",
    "重試",
    "然後呢",
    "繼續做",
}
_STOP = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "from",
    "by",
    "at",
    "is",
    "are",
    "be",
    "it",
    "this",
    "that",
    "me",
    "my",
    "i",
    "you",
    "your",
    "we",
    "our",
    "please",
    "can",
    "could",
    "would",
    "will",
    "do",
    "does",
    "what",
    "how",
    "which",
    "who",
    "as",
    "into",
    "about",
    "help",
    "的",
    "了",
    "是",
    "我",
    "你",
    "他",
    "她",
    "們",
    "们",
    "請",
    "请",
    "幫",
    "帮",
    "嗎",
    "吗",
    "呢",
    "吧",
    "啊",
    "一",
    "個",
    "个",
    "在",
    "和",
    "與",
    "与",
    "要",
    "把",
    "這",
    "这",
    "那",
    "有",
    "也",
    "就",
    "都",
    "及",
    "或",
    "給",
    "给",
    "下",
    "並",
    "并",
    "跟",
    "從",
    "从",
    "被",
    "讓",
    "让",
    "幫我",
    "帮我",
    "請幫",
    "一下",
}
_NUMBER = re.compile(r"^[\d._:/-]+$")
_CJK_CHAR = re.compile(r"^[぀-ヿ㐀-鿿豈-﫿]$")
_TOOL_LINE = re.compile(r"^-\s+([A-Za-z0-9_.:-]+):", re.MULTILINE)
_SPACE = re.compile(r"\s+")


# -- requests ---------------------------------------------------------------------


@dataclass(frozen=True)
class Request:
    """One request: an opening user message with its answer's outcome."""

    request_id: str
    session_id: str
    message_id: str
    created_at: datetime
    text: str  # an excerpt of the (already redacted) user message
    status: str  # the answer's status, "unanswered" when there was none
    tools: tuple[str, ...] = ()  # ordered, unique tool names from tool_summary
    workflows: tuple[str, ...] = ()  # namespace/name of a Workflow the answer ran
    terms: frozenset[str] = field(default_factory=frozenset)

    @property
    def day(self) -> date:
        return self.created_at.astimezone().date()


@dataclass
class Harvest:
    requests: list[Request]
    secret_dropped: int = 0


def request_id(session_id: str, message_id: str) -> str:
    digest = hashlib.sha256(f"{session_id}\0{message_id}".encode()).hexdigest()
    return "req-" + digest[:16]


def terms(text: str) -> frozenset[str]:
    """Comparable words: `tokens` minus stop words, numbers, dates and other
    mostly-digit values."""
    return frozenset(
        token
        for token in tokens(text)
        if token not in _STOP
        and not _NUMBER.match(token)
        # A value such as 2026_w30 or w31 (mostly digits) differs between runs
        # of one task; it is not what makes two requests alike.
        and sum(c.isdigit() for c in token) * 2 < len(token)
        and (len(token) > 1 or _CJK_CHAR.match(token))
        and not _stop_bigram(token)
    )


def _stop_bigram(token: str) -> bool:
    """A CJK bigram with a function character in it ("的週", "我整") straddles
    two words; it would only add noise."""
    return (
        len(token) == 2
        and bool(_CJK_CHAR.match(token[0]) and _CJK_CHAR.match(token[1]))
        and (token[0] in _STOP or token[1] in _STOP)
    )


def _words(found: Iterable[str]) -> set[str]:
    """Terms worth showing or matching on their own: no single CJK character."""
    return {term for term in found if not _CJK_CHAR.match(term)}


def _short_follow_up(text: str) -> bool:
    cleaned = _SPACE.sub(" ", text.strip().lower()).strip(" .!?,。！？，~～")
    if cleaned in _FOLLOW_UPS or len(cleaned) < 4:
        return True
    return len(_words(terms(cleaned))) < 1


def _tool_shape(summary: str | None) -> tuple[str, ...]:
    names: list[str] = []
    for name in _TOOL_LINE.findall(summary or ""):
        if name not in names:
            names.append(name)
    return tuple(names)


def _form_workflow(form: Any) -> tuple[str, ...]:
    if not isinstance(form, dict):
        return ()
    found = form.get("workflow")
    if isinstance(found, dict) and found.get("namespace") and found.get("name"):
        return (f"{found['namespace']}/{found['name']}",)
    return ()


def from_reuse(
    records: Iterable[Any], actor: str, *, retention_days: int, now: datetime | None = None
) -> Harvest:
    """The actor's requests inside the retention window. Records of anybody
    else are skipped, whatever the caller passed in."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=retention_days)
    found: list[Request] = []
    dropped = 0
    for record in records:
        if record.actor != actor:
            continue
        messages = list(record.messages)
        first_user = True
        for index, message in enumerate(messages):
            if message.role != "user":
                continue
            opening = first_user or message.reply_to is None
            first_user = False
            if not opening or _short_follow_up(message.text):
                continue
            if message.created_at < cutoff:
                continue
            if SECRET_PATTERN.search(message.text) or REDACTED in message.text:
                dropped += 1
                continue
            following = messages[index + 1] if index + 1 < len(messages) else None
            answer = following if following is not None and following.role == "assistant" else None
            excerpt = _SPACE.sub(" ", message.text.strip())[:EXCERPT_CHARS]
            found.append(
                Request(
                    request_id=request_id(record.session_id, message.message_id),
                    session_id=record.session_id,
                    message_id=message.message_id,
                    created_at=message.created_at,
                    text=excerpt,
                    status=answer.status if answer is not None else "unanswered",
                    tools=_tool_shape(answer.tool_summary) if answer is not None else (),
                    workflows=_form_workflow(answer.workflow_form) if answer is not None else (),
                    terms=terms(message.text),
                )
            )
    found.sort(key=lambda item: (item.created_at, item.request_id))
    return Harvest(found, dropped)


# -- the deterministic score (pre-filter and explanation only) --------------------


class Scorer:
    """Weighted Jaccard (IDF over the actor's own requests) plus tool shape."""

    def __init__(self, requests: Sequence[Request]) -> None:
        count = max(1, len(requests))
        df: Counter[str] = Counter()
        for item in requests:
            df.update(item.terms)
        self.idf = {term: math.log(1 + count / n) for term, n in df.items()}

    def text(self, a: Request, b: Request) -> float:
        union = a.terms | b.terms
        if not union:
            return 0.0
        shared = sum(self.idf.get(t, 1.0) for t in a.terms & b.terms)
        return shared / sum(self.idf.get(t, 1.0) for t in union)

    @staticmethod
    def tools(a: Request, b: Request) -> float:
        if set(a.workflows) & set(b.workflows):
            return 1.0
        if not a.tools or not b.tools:
            return 0.0
        if a.tools == b.tools:
            return 1.0
        left, right = set(a.tools), set(b.tools)
        return len(left & right) / len(left | right)

    def score(self, a: Request, b: Request) -> float:
        return TEXT_WEIGHT * self.text(a, b) + TOOL_WEIGHT * self.tools(a, b)


def explain(members: Sequence[Request], scorer: Scorer) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The words two or more members share (most shared first) and the most
    common tool shape: what the report shows as the reason for a group."""
    seen: Counter[str] = Counter()
    for item in members:
        seen.update(_words(item.terms))
    shared = sorted((t for t, n in seen.items() if n >= 2), key=lambda t: (len(t), t))
    # A longer CJK run that only adds a character to a shared word ("的週報"
    # beside "週報") says less than the word: keep the shorter one.
    chosen: list[str] = []
    for term in shared:
        if not any(part in term and seen[part] >= seen[term] for part in chosen):
            chosen.append(term)
    # A bigram straddling two chosen words ("理週" in "整理週報") is noise.
    picked = [
        term
        for term in chosen
        if not (
            len(term) == 2
            and _CJK_CHAR.match(term[0])
            and any(o != term and len(o) >= 2 and o.endswith(term[0]) for o in chosen)
            and any(o != term and len(o) >= 2 and o.startswith(term[1]) for o in chosen)
        )
    ]
    picked.sort(key=lambda t: (-seen[t], -scorer.idf.get(t, 0.0), t))
    words = picked
    shapes = Counter(item.tools for item in members if item.tools)
    shape = shapes.most_common(1)[0][0] if shapes else ()
    return tuple(words[:8]), shape


# -- persistence ------------------------------------------------------------------


GroupStatus = Literal["open", "reported", "dropped"]


class SuggestionGroup(Contract):
    """A group the model formed; request ids only, never request text."""

    group_id: str
    actor: str
    task: str = ""
    request_ids: tuple[str, ...]
    status: GroupStatus = "open"
    reason: str = ""
    created_at: str
    updated_at: str
    reported_at: str | None = None


@dataclass
class SuggestionState:
    sent: dict[str, str]  # request id -> request created_at (ISO)
    groups: dict[str, SuggestionGroup]


class SuggestionStore:
    """Requests already sent and the groups they formed, in `experience.sqlite`.
    Read-only mode (the CLI dry run) never creates or changes the file."""

    def __init__(self, workspace: Path, *, read_only: bool = False) -> None:
        self.path = workspace / STORE_FILE
        self.read_only = read_only
        self._lock = threading.Lock()
        if not read_only:
            with self._connect() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS suggestion_sent (actor TEXT NOT NULL,"
                    " request_id TEXT NOT NULL, created_at TEXT NOT NULL,"
                    " PRIMARY KEY (actor, request_id))"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS suggestion_groups (group_id TEXT PRIMARY KEY,"
                    " actor TEXT NOT NULL, record TEXT NOT NULL)"
                )

    def _connect(self) -> sqlite3.Connection:
        if self.read_only:
            return sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True, timeout=10)
        return sqlite3.connect(str(self.path), timeout=10)

    def load(self, actor: str) -> SuggestionState:
        state = SuggestionState({}, {})
        if self.read_only and not self.path.is_file():
            return state
        conn = self._connect()
        try:
            sent = conn.execute(
                "SELECT request_id, created_at FROM suggestion_sent WHERE actor = ?", (actor,)
            ).fetchall()
            groups = conn.execute(
                "SELECT record FROM suggestion_groups WHERE actor = ?", (actor,)
            ).fetchall()
        except sqlite3.Error:
            return state
        finally:
            conn.close()
        state.sent = {str(rid): str(at) for rid, at in sent}
        for (record,) in groups:
            try:
                group = SuggestionGroup.model_validate_json(record)
            except ValueError:
                continue
            if group.actor == actor:
                state.groups[group.group_id] = group
        return state

    def save(
        self, actor: str, state: SuggestionState, removed: Iterable[str], *, cutoff: str
    ) -> None:
        if self.read_only:
            raise RuntimeError("a dry run writes nothing")
        with self._lock, self._connect() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO suggestion_sent (actor, request_id, created_at)"
                " VALUES (?, ?, ?)",
                [(actor, rid, at) for rid, at in state.sent.items()],
            )
            conn.execute(
                "DELETE FROM suggestion_sent WHERE actor = ? AND created_at < ?", (actor, cutoff)
            )
            for group_id in removed:
                conn.execute(
                    "DELETE FROM suggestion_groups WHERE group_id = ? AND actor = ?",
                    (group_id, actor),
                )
            for group in state.groups.values():
                conn.execute(
                    "INSERT INTO suggestion_groups (group_id, actor, record) VALUES (?, ?, ?)"
                    " ON CONFLICT(group_id) DO UPDATE SET record = excluded.record",
                    (group.group_id, actor, group.model_dump_json()),
                )


# -- what is installed or pending (dedupe) ----------------------------------------


@dataclass(frozen=True)
class Known:
    """Something that already covers a task: its label and comparable words."""

    label: str
    words: frozenset[str]
    # A Workflow's normalized name (found inside a tool name) and the exact
    # tool names of the Skill commands that run it.
    names: tuple[str, ...] = ()


@dataclass
class Catalog:
    workflows: list[Known] = field(default_factory=list)
    skills: list[Known] = field(default_factory=list)
    candidates: list[Known] = field(default_factory=list)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def load_catalog(*, workflows_dir: Path, skills_dir: Path, chat_root: Path, actor: str) -> Catalog:
    """Installed Workflows and Skills, and the actor's pending candidates."""
    from common.assets import WorkflowManifest
    from host_runtime.chat_authoring import ChatCandidate
    from host_runtime.skill_authoring import SkillCandidate, installed_skills

    catalog = Catalog()
    skills = installed_skills(skills_dir)
    # The model calls a Workflow through a Skill command: `<alias>__<command>`.
    runs: dict[str, list[str]] = {}
    for skill in skills:
        for command in skill.commands:
            if command.kind == "workflow":
                target = f"{command.target.namespace}/{command.target.name}"
                runs.setdefault(target, []).append(_norm(f"{skill.alias}__{command.name}"))
    for path in sorted(workflows_dir.glob("*.json")) if workflows_dir.is_dir() else []:
        try:
            manifest = WorkflowManifest.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        identity = manifest.metadata.identity
        label = f"{identity.namespace}/{identity.name}"
        catalog.workflows.append(
            Known(
                label=label,
                words=frozenset(_words(terms(f"{identity.name} {manifest.description}"))),
                names=(_norm(identity.name), *runs.get(label, ())),
            )
        )
    for skill in skills:
        identity = skill.metadata.identity
        text = " ".join(
            (
                identity.name.replace("-", " "),
                skill.alias.replace("_", " "),
                skill.selector_hint or "",
                skill.instructions,
            )
        )
        catalog.skills.append(
            Known(
                label=f"{identity.namespace}/{identity.name}", words=frozenset(_words(terms(text)))
            )
        )
    for path in sorted((chat_root / "candidates").glob("*.json")):
        try:
            item = ChatCandidate.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if item.actor != actor or item.status == "installed":
            continue
        text = f"{item.title} {item.draft.metadata.identity.name} {item.draft.description}"
        catalog.candidates.append(
            Known(f"candidate {item.candidate_id}", frozenset(_words(terms(text))))
        )
    for path in sorted((chat_root / "skill-candidates").glob("*.json")):
        try:
            skill_item = SkillCandidate.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if skill_item.actor != actor or skill_item.status == "installed":
            continue
        draft = skill_item.draft
        text = " ".join(
            (skill_item.title, draft.selector_hint or "", draft.instructions, draft.alias)
        )
        catalog.candidates.append(
            Known(f"skill candidate {skill_item.candidate_id}", frozenset(_words(terms(text))))
        )
    return catalog


def _covered(task_words: set[str], other: Iterable[str]) -> bool:
    """Most of a task's words appear in the other text."""
    if not task_words:
        return False
    shared = task_words & set(other)
    return len(shared) >= min(2, len(task_words)) and (
        len(shared) / len(task_words) >= DEDUPE_SIMILARITY
    )


def _same_task(left: set[str], right: set[str]) -> bool:
    if not left or not right:
        return False
    shared = left & right
    return len(shared) >= min(2, len(left), len(right)) and (
        len(shared) / min(len(left), len(right)) >= DEDUPE_SIMILARITY
    )


# -- the report -------------------------------------------------------------------


class SuggestionEvidence(Contract):
    session_id: str
    message_id: str
    date: str
    excerpt: str


class SuggestionItem(Contract):
    group_id: str
    task: str = ""
    status: Literal["qualified", "considered", "deferred", "dropped"]
    reason: str = ""
    requests: int
    sessions: int
    days: int
    matched_words: tuple[str, ...] = ()
    tool_shape: tuple[str, ...] = ()
    evidence: tuple[SuggestionEvidence, ...] = ()


class SuggestionCounts(Contract):
    """What one pass did: counts and ids only, never request text."""

    pass_id: str
    actor: str
    started_at: str
    enabled: bool = True
    dry_run: bool = False
    harvested: int = 0
    new_requests: int = 0
    one_offs: int = 0
    secret_dropped: int = 0
    sent_requests: int = 0
    sent_groups: int = 0
    left_for_next: int = 0
    model_called: bool = False
    qualified: int = 0
    dropped: int = 0
    deferred: int = 0
    error: str | None = None


class SuggestionPass(Contract):
    counts: SuggestionCounts
    suggestions: tuple[SuggestionItem, ...] = ()

    def markdown(self) -> str:
        c = self.counts
        if not c.enabled:
            return "## Suggested Skills\n\nSuggestions are off.\n"
        lines = [
            "## Suggested Skills",
            "",
            f"{c.harvested} requests in the window, {c.new_requests} new, {c.one_offs} one-offs "
            f"kept back, {c.sent_requests} requests and {c.sent_groups} groups sent to the model"
            + (f", {c.left_for_next} left for the next night" if c.left_for_next else "")
            + (f", {c.secret_dropped} dropped for secret-shaped text" if c.secret_dropped else "")
            + ".",
        ]
        if c.error:
            lines += ["", f"Grouping failed: {c.error}"]
        for item in self.suggestions:
            lines += [
                "",
                f"### {item.status}: {item.task or '(unnamed)'} ({item.requests} requests, "
                f"{item.sessions} sessions, {item.days} days)",
            ]
            if item.reason:
                lines.append(f"- Reason: {item.reason}")
            if item.matched_words:
                lines.append(f"- Matched words: {', '.join(item.matched_words)}")
            if item.tool_shape:
                lines.append(f"- Tools: {' → '.join(item.tool_shape)}")
            lines += [
                f"- {e.date} {e.session_id}/{e.message_id}: {e.excerpt}" for e in item.evidence
            ]
        return "\n".join(lines) + "\n"


# -- the model's grouping pass ----------------------------------------------------

PROMPT = """You group one person's requests to a company AI assistant by task, to find
work they repeat. You get groups found earlier (G ids, each with a task name and
example requests) and new requests (R ids); each item lists the tools its answer used.
Reply with one JSON object:
{"groups": [{"ids": ["G1", "R3", "R7"], "task": "one line naming the repeated task"}]}
Rules:
- Put items in one group only when they are the same repeatable task: the same kind
  of work, possibly with different values (a date, a week, a file, a name, a model).
- A shared topic is not enough: different questions about one product are different tasks.
- Use each id at most once and only ids from the input. Leave out items that match
  nothing else.
- To add new requests to an earlier group, put its G id in the group; to merge earlier
  groups, list their G ids together.
- The task line is short, in the language of the requests, and holds no person's name,
  password, token or other secret."""


def _clean_task(value: object) -> str:
    text = _SPACE.sub(" ", str(value or "")).strip()
    return SECRET_PATTERN.sub(REDACTED, text)[:TASK_CHARS]


def parse_groups(data: object, known: set[str]) -> list[tuple[list[str], str]]:
    """The model's groups, checked: only known ids, each id once, at least two
    items. Anything else in the reply (counts, reasons) is ignored."""
    if not isinstance(data, dict) or not isinstance(data.get("groups"), list):
        raise ValueError("the reply has no groups list")
    used: set[str] = set()
    found = []
    for raw in data["groups"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("ids"), list):
            continue
        ids: list[str] = []
        for item in raw["ids"]:
            key = str(item).strip()
            if key in known and key not in used and key not in ids:
                ids.append(key)
        # A group left with one item is ignored and uses up nothing.
        if len(ids) >= 2:
            used.update(ids)
            found.append((ids, _clean_task(raw.get("task"))))
    return found


def _render(new: Sequence[Request], groups: Sequence[tuple[SuggestionGroup, list[Request]]]) -> str:
    def tools(item: Request) -> str:
        return " → ".join(item.tools) or "none"

    lines = ["===== earlier groups ====="]
    if not groups:
        lines.append("(none)")
    for number, (group, members) in enumerate(groups, 1):
        lines.append(f"G{number} task: {group.task or '(not named yet)'}")
        for item in members[-GROUP_EXAMPLES:]:
            lines.append(f'  - ({item.day.isoformat()}, tools: {tools(item)}) "{item.text}"')
    lines += ["", "===== new requests ====="]
    for number, item in enumerate(new, 1):
        lines.append(f'R{number} ({item.day.isoformat()}, tools: {tools(item)}) "{item.text}"')
    return "\n".join(lines)


def _ask_groups(model: ModelClient, alias: str, text: str, trace: TraceIdentifiers) -> object:
    from host_runtime.experience_review import structured_call

    return structured_call(
        model,
        alias,
        system=PROMPT,
        user=text,
        trace=trace,
        output_contract=OUTPUT_CONTRACT,
        max_output_tokens=4000,
    )


# -- one pass ---------------------------------------------------------------------


def _group_id(actor: str, first: str) -> str:
    return "sg-" + hashlib.sha256(f"{actor}\0{first}".encode()).hexdigest()[:16]


def _stats(members: Sequence[Request]) -> tuple[int, int, int]:
    return len(members), len({m.session_id for m in members}), len({m.day for m in members})


def qualifies(members: Sequence[Request]) -> bool:
    """3 requests in 3 sessions over 2 calendar days (Normal). Requests inside
    one session never qualify on their own."""
    count, sessions, days = _stats(members)
    return count >= MIN_REQUESTS and sessions >= MIN_SESSIONS and days >= MIN_DAYS


def _item(
    group: SuggestionGroup,
    members: Sequence[Request],
    scorer: Scorer,
    status: Literal["qualified", "considered", "deferred", "dropped"],
    reason: str = "",
) -> SuggestionItem:
    count, sessions, days = _stats(members)
    words, shape = explain(members, scorer)
    return SuggestionItem(
        group_id=group.group_id,
        task=group.task,
        status=status,
        reason=reason,
        requests=count,
        sessions=sessions,
        days=days,
        matched_words=words,
        tool_shape=shape,
        evidence=tuple(
            SuggestionEvidence(
                session_id=m.session_id,
                message_id=m.message_id,
                date=m.day.isoformat(),
                excerpt=m.text[:EVIDENCE_CHARS],
            )
            for m in list(members)[-MAX_EVIDENCE:]
        ),
    )


def _duplicate_reason(
    group: SuggestionGroup,
    members: Sequence[Request],
    catalog: Catalog,
    reported: Sequence[SuggestionGroup],
) -> str | None:
    used_tools = {_norm(tool) for m in members for tool in m.tools}
    ran = {workflow for m in members for workflow in m.workflows}
    for known in catalog.workflows:
        name, *commands = known.names or ("",)
        if (
            known.label in ran
            or used_tools & set(commands)
            or (len(name) >= 4 and any(name in tool for tool in used_tools))
        ):
            return f"installed Workflow {known.label} was run in the evidence"
    task_words = _words(terms(group.task))
    for known in catalog.skills:
        if _covered(task_words, known.words):
            return f"installed Skill {known.label} covers this task"
    for known in catalog.workflows:
        if _covered(task_words, known.words):
            return f"installed Workflow {known.label} covers this task"
    for known in catalog.candidates:
        if _covered(task_words, known.words):
            return f"a draft already exists: {known.label}"
    for other in reported:
        if other.group_id != group.group_id and _same_task(task_words, _words(terms(other.task))):
            return f"already reported as {other.group_id}"
    return None


def pending(
    harvest: Harvest, state: SuggestionState, scorer: Scorer
) -> tuple[list[tuple[float, Request]], int]:
    """New requests that pass the pre-filter (best score against any request in
    another session), with their score, and how many were one-offs."""
    new = [r for r in harvest.requests if r.request_id not in state.sent]
    kept: list[tuple[float, Request]] = []
    one_offs = 0
    for item in new:
        best = max(
            (
                scorer.score(item, other)
                for other in harvest.requests
                if other.session_id != item.session_id
            ),
            default=0.0,
        )
        if best >= PREFILTER_FLOOR:
            kept.append((best, item))
        else:
            one_offs += 1
    kept.sort(key=lambda pair: (-pair[0], pair[1].created_at, pair[1].request_id))
    return kept, one_offs


def run_suggestions(
    records: Iterable[Any],
    *,
    actor: str,
    model: ModelClient,
    alias: str,
    store: SuggestionStore,
    catalog: Catalog,
    settings: ExperienceSettings,
    now: datetime | None = None,
    dry_run: bool = False,
) -> SuggestionPass:
    """One pass for one actor: harvest, pre-filter, one grouping call,
    thresholds, dedupe. Writes the store unless this is a dry run."""
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    pass_id = f"suggest-{moment.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:4]}"
    counts: dict[str, Any] = {
        "pass_id": pass_id,
        "actor": actor,
        "started_at": moment.isoformat(timespec="seconds"),
        "dry_run": dry_run,
    }
    if not settings.suggestions:
        return SuggestionPass(counts=SuggestionCounts(**counts, enabled=False))
    harvest = from_reuse(records, actor, retention_days=settings.retention_days, now=moment)
    by_id = {r.request_id: r for r in harvest.requests}
    state = store.load(actor)
    scorer = Scorer(harvest.requests)
    candidates, one_offs = pending(harvest, state, scorer)
    counts.update(
        harvested=len(harvest.requests),
        new_requests=len([r for r in harvest.requests if r.request_id not in state.sent]),
        one_offs=one_offs,
        secret_dropped=harvest.secret_dropped,
    )

    def members_of(group: SuggestionGroup) -> list[Request]:
        return sorted(
            (by_id[rid] for rid in group.request_ids if rid in by_id),
            key=lambda r: (r.created_at, r.request_id),
        )

    # The earlier groups that resemble a candidate; at most half the cap.
    cap = settings.suggestion_max_requests
    partner_groups: list[tuple[float, SuggestionGroup, list[Request]]] = []
    for group in state.groups.values():
        members = members_of(group)
        if not members:
            continue
        best = max(
            (scorer.score(m, c) for m in members for _, c in candidates),
            default=0.0,
        )
        if best >= PREFILTER_FLOOR:
            partner_groups.append((best, group, members))
    partner_groups.sort(key=lambda t: (-t[0], t[1].created_at, t[1].group_id))
    shown_groups: list[tuple[SuggestionGroup, list[Request]]] = []
    used = 0
    for _, group, members in partner_groups:
        cost = min(GROUP_EXAMPLES, len(members))
        if used + cost > cap // 2:
            break
        shown_groups.append((group, members))
        used += cost
    sent = [item for _, item in candidates[: max(0, cap - used)]]
    counts["left_for_next"] = len(candidates) - len(sent)
    removed: list[str] = []
    stamp = moment.isoformat(timespec="seconds")
    if sent:
        shown_groups = [
            (g, ms)
            for g, ms in shown_groups
            if any(scorer.score(m, s) >= PREFILTER_FLOOR for m in ms for s in sent)
        ]
        keys = {f"R{n}": r for n, r in enumerate(sent, 1)}
        group_keys = {f"G{n}": g for n, (g, _) in enumerate(shown_groups, 1)}
        counts.update(sent_requests=len(sent), sent_groups=len(shown_groups), model_called=True)
        try:
            data = _ask_groups(
                model,
                alias,
                _render(sent, shown_groups),
                TraceIdentifiers(trace_id=pass_id, request_id="group", span_id="suggest"),
            )
            parsed = parse_groups(data, set(keys) | set(group_keys))
        except (RuntimeError, ValueError, ValidationError) as error:
            counts["error"] = type(error).__name__ + ": " + str(error)[:120]
            parsed = None
        if parsed is not None:
            grouped: set[str] = set()
            for ids, task in parsed:
                existing = sorted(
                    (group_keys[k] for k in ids if k in group_keys),
                    key=lambda g: (g.created_at, g.group_id),
                )
                new_ids = [keys[k].request_id for k in ids if k in keys]
                grouped.update(new_ids)
                if existing:
                    keep = existing[0]
                    merged = list(keep.request_ids)
                    for other in existing[1:]:
                        merged += [r for r in other.request_ids if r not in merged]
                        if other.status != "open" and keep.status == "open":
                            keep = keep.model_copy(
                                update={"status": other.status, "reason": other.reason}
                            )
                        state.groups.pop(other.group_id, None)
                        removed.append(other.group_id)
                    merged += [r for r in new_ids if r not in merged]
                    state.groups[keep.group_id] = keep.model_copy(
                        update={
                            "request_ids": tuple(merged),
                            "task": keep.task if keep.status != "open" else task or keep.task,
                            "updated_at": stamp,
                        }
                    )
                else:
                    state.groups[_group_id(actor, new_ids[0])] = SuggestionGroup(
                        group_id=_group_id(actor, new_ids[0]),
                        actor=actor,
                        task=task,
                        request_ids=tuple(new_ids),
                        created_at=stamp,
                        updated_at=stamp,
                    )
            # Sent but matched with nothing: kept as a group of one, so a later
            # request of the same task can still join it.
            for item in sent:
                if item.request_id not in grouped:
                    gid = _group_id(actor, item.request_id)
                    state.groups[gid] = SuggestionGroup(
                        group_id=gid,
                        actor=actor,
                        request_ids=(item.request_id,),
                        created_at=stamp,
                        updated_at=stamp,
                    )
            for item in sent:
                state.sent[item.request_id] = item.created_at.astimezone(UTC).isoformat()

    # Thresholds and dedupe over the open groups.
    items: list[SuggestionItem] = []
    reported = [g for g in state.groups.values() if g.status == "reported"]
    ready: list[tuple[SuggestionGroup, list[Request]]] = []
    for group in sorted(state.groups.values(), key=lambda g: (g.created_at, g.group_id)):
        if group.status != "open":
            continue
        members = members_of(group)
        if len(members) < 2:
            continue
        if not qualifies(members):
            count, sessions, days = _stats(members)
            items.append(
                _item(
                    group,
                    members,
                    scorer,
                    "considered",
                    f"below the threshold: {count} requests in {sessions} sessions over "
                    f"{days} days (needs {MIN_REQUESTS} in {MIN_SESSIONS} over {MIN_DAYS})",
                )
            )
            continue
        reason = _duplicate_reason(group, members, catalog, reported)
        if reason is not None:
            state.groups[group.group_id] = group.model_copy(
                update={"status": "dropped", "reason": reason, "updated_at": stamp}
            )
            items.append(_item(group, members, scorer, "dropped", reason))
            continue
        ready.append((group, members))
    ready.sort(
        key=lambda pair: (
            -_stats(pair[1])[0],
            -_stats(pair[1])[1],
            -pair[1][-1].created_at.timestamp(),
            pair[0].group_id,
        )
    )
    for number, (group, members) in enumerate(ready):
        if number >= MAX_NEW_PER_NIGHT:
            items.append(
                _item(
                    group,
                    members,
                    scorer,
                    "deferred",
                    f"at most {MAX_NEW_PER_NIGHT} new suggestions a night; next night",
                )
            )
            continue
        # A group qualified earlier in this pass is compared with it too.
        reason = _duplicate_reason(group, members, Catalog(), reported)
        if reason is not None:
            state.groups[group.group_id] = group.model_copy(
                update={"status": "dropped", "reason": reason, "updated_at": stamp}
            )
            items.append(_item(group, members, scorer, "dropped", reason))
            continue
        done = group.model_copy(
            update={"status": "reported", "reported_at": stamp, "updated_at": stamp}
        )
        state.groups[group.group_id] = done
        reported.append(done)
        items.append(_item(done, members, scorer, "qualified"))
    order = {"qualified": 0, "deferred": 1, "dropped": 2, "considered": 3}
    items.sort(key=lambda i: (order[i.status], -i.requests, i.group_id))
    counts.update(
        qualified=sum(i.status == "qualified" for i in items),
        dropped=sum(i.status == "dropped" for i in items),
        deferred=sum(i.status == "deferred" for i in items),
    )
    if not dry_run:
        cutoff = (moment - timedelta(days=settings.retention_days)).astimezone(UTC)
        for group in list(state.groups.values()):
            if not members_of(group) and group.updated_at < cutoff.isoformat():
                state.groups.pop(group.group_id)
                removed.append(group.group_id)
        store.save(actor, state, removed, cutoff=cutoff.isoformat())
    return SuggestionPass(counts=SuggestionCounts(**counts), suggestions=tuple(items))


def due(records: Iterable[Any], *, actor: str, store: SuggestionStore, settings: Any) -> bool:
    """Whether a pass would send anything: suggestions on and at least one new
    request past the pre-filter. No model call."""
    if not settings.suggestions:
        return False
    harvest = from_reuse(records, actor, retention_days=settings.retention_days)
    candidates, _ = pending(harvest, store.load(actor), Scorer(harvest.requests))
    return bool(candidates)


# -- the host's entry point (nightly job and CLI dry run) -------------------------


def suggest_for_runtime(
    runtime: Any,
    model: ModelClient,
    alias: str,
    *,
    actor: str | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> SuggestionPass:
    """The same pass for the nightly job and `aep-host experience suggest`."""
    workspace = runtime.layout.workspace_root
    who = actor or runtime.actor
    settings = load_settings(workspace)
    store = SuggestionStore(workspace, read_only=dry_run)
    if not settings.suggestions:
        return run_suggestions(
            (),
            actor=who,
            model=model,
            alias=alias,
            store=store,
            catalog=Catalog(),
            settings=settings,
            now=now,
            dry_run=dry_run,
        )
    # Only this actor's conversations are read (the state filters by actor).
    records = runtime.state.conversations(who, limit=100)
    catalog = load_catalog(
        workflows_dir=runtime.layout.workflows,
        skills_dir=runtime.layout.skills,
        chat_root=workspace / CHAT_AUTHORING,
        actor=who,
    )
    return run_suggestions(
        records,
        actor=who,
        model=model,
        alias=alias,
        store=store,
        catalog=catalog,
        settings=settings,
        now=now,
        dry_run=dry_run,
    )
