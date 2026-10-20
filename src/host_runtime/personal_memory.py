"""Preferences and notes in a conversation (accumulated memory M3).

docs/phases/ACCUMULATED_MEMORY.md §5 and §3.9; owner decisions 2026-10-20
(§10.3 「按一下才存、Agent Web 可管理」, §10.8 notes).

The model never saves anything. It gets:

- `memory__propose_preference(rule, skill)`: a card 「要把這條記成『<Skill>』
  的偏好嗎？」 with 存成偏好 / 不用. The press saves it; a contradiction with
  an active preference of the same scope is asked about first, both shown
  (取代舊的 / 兩條都留 / 不用).
- `memory__propose_note(text, tags, entities)`: a card 「要存成筆記嗎？」,
  at most once per conversation (the Host counts; a Telegram chat counts per
  day).
- `notes__search(query, tag, entity, since, until)`: only in a turn whose
  Skills declare a read of `personal/notes`, or whose message asks about
  earlier notes (`memory.notes.notes_asked`). Results carry note ids to cite.

The cards do not end the turn (`ActionCard.ends_turn` false): the answer
goes on and the card shows under it, in Agent Web and Telegram alike.

Each turn the Host gives the model the active preferences of the Skills it
offers (bounded, labelled as the person's) and records their ids on the
answer (`preferences_used`).

Agent Web also saves a note in one click, an answer or a selection of it
(`/api/memory/notes/save`), and has minimal list, delete and undo routes;
the memory page is M4.
"""

from __future__ import annotations

import asyncio
import unicodedata
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import Field

from agent.gateway import HostTool, HostToolOutcome, TurnMemory
from agent.skills import SkillManifest
from common.action_cards import CARD_KEY, ActionCard, CardButton, CardRow
from common.execution import Failure, RequestContext
from host_runtime.card_store import CardStore, PendingRecord, new_card_id
from memory import personal
from memory.notes import Notes, clean_entities, clean_tags, notes_asked
from memory.preferences import MAX_TEXT as MAX_RULE
from memory.preferences import Preference, PreferenceConflict, Preferences, normalise
from memory.service import MemoryService, MemoryServiceError
from models.contracts import ModelTool

CARDS_FILE = Path("memory") / "memory-cards.json"
#: A memory card waits a day; then 「請再請 Agent 提一次」.
EXPIRY = timedelta(hours=24)
PROPOSE_PREFERENCE = "memory__propose_preference"
PROPOSE_NOTE = "memory__propose_note"
SEARCH_NOTES = "notes__search"
#: What a turn's system prompt carries of the person's preferences.
MAX_INJECTED = 12
MAX_INJECTED_CHARS = 1_600
MAX_NOTE_PROPOSAL = 4_000
LOCAL_ZONE = ZoneInfo("Asia/Taipei")
#: How a Skill is named on a card and in the prompt; else its name.
SKILL_LABELS = {"engineering/business-cards": "名片／組織圖"}

STATUS_LABELS = {
    "saved": "已儲存",
    "declined": "沒有存",
    "duplicate": "已經有相同的偏好",
    "expired": "已過期：要存請再請 Agent 提一次",
    "failed": "沒有存",
}
#: What a refusal means, for the person (Agent Web routes).
ROUTE_MESSAGES = {
    "conversation_unknown": "找不到這段對話",
    "message_unknown": "找不到這則回答",
    "selection_not_in_answer": "選取的內容不在這則回答裡",
    "note_text_empty": "沒有可存的內容",
    "note_unknown": "找不到這則筆記",
    "preference_unknown": "找不到這條偏好",
    "change_unknown": "找不到這個變更",
    "change_already_undone": "這個變更已經復原過了",
    "undo_conflict": "之後又有變更動到同一筆，無法直接復原",
    "memory_kind_unknown": "只能復原筆記或偏好的變更",
}

PREFERENCE_GUIDANCE = (
    f"When the person states a lasting rule for how a Skill should work (以後…, 執行時不需要問…, "
    f"always/never …), apply it in this conversation and call {PROPOSE_PREFERENCE} once with the "
    "rule in their words and the Skill it is for; a card asks them to save it (存成偏好). Nothing "
    "is saved before they press it: never say it is saved or that you changed a rule."
)
NOTE_GUIDANCE = (
    f"You may call {PROPOSE_NOTE} at most once in a conversation, when a conclusion is clearly "
    "worth keeping for later (a decision, a finding, a to-check item); the person presses "
    "存成筆記 to save it. Every answer already has its own 存成筆記 button, so do not ask in "
    "words and do not propose small talk."
)
SEARCH_GUIDANCE = (
    f"{SEARCH_NOTES} searches the notes the person saved. Use it only for what they ask; cite "
    "every note you use as [筆記 <note_id>], and never say a note says what its result does not."
)


class MemoryRefused(Exception):
    """Why a proposal or search cannot be made; said to the model."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class MemoryCard(PendingRecord):
    """One preference or note the Agent proposed; holds the person's words."""

    kind: Literal["preference", "note"]
    stage: Literal["propose", "conflict"] = "propose"
    actor: str = Field(max_length=120)
    channel: str = Field(default="local", max_length=40)
    session_id: str = Field(default="", max_length=200)
    # The conversation the per-conversation note limit counts in.
    conversation: str = Field(default="", max_length=240)
    request_id: str = Field(default="", max_length=200)
    scope: str = Field(default="", max_length=200)
    scope_label: str = Field(default="", max_length=120)
    text: str = Field(max_length=20_000)
    subject: str = Field(default="", max_length=200)
    tags: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    # A contradiction found at save: the active preferences, id and text.
    conflicts: tuple[dict[str, str], ...] = ()
    saved_id: str = ""
    change_id: str = ""
    outcome: str = Field(default="", max_length=2_000)
    outcome_ok: bool | None = None


def skill_key(manifest: SkillManifest) -> str:
    identity = manifest.metadata.identity
    return f"{identity.namespace}/{identity.name}"


def skill_label(manifest: SkillManifest) -> str:
    key = skill_key(manifest)
    return SKILL_LABELS.get(key, manifest.metadata.identity.name)


def scopes_of(skills: tuple[SkillManifest, ...]) -> dict[str, str]:
    """Each scope a turn's Skills bring, with its label: the Skill itself
    (`skill:<ns>/<name>`) and every memory space it declares (`space:<s>`)."""
    found: dict[str, str] = {}
    for manifest in skills:
        label = skill_label(manifest)
        found.setdefault(f"skill:{skill_key(manifest)}", label)
        for declared in manifest.memory_spaces:
            if declared.space.startswith("personal/"):
                continue
            found.setdefault(f"space:{declared.space}", label)
    return found


def preference_block(preferences: list[Preference]) -> tuple[str, tuple[str, ...]]:
    """The preferences as the prompt carries them, newest first, at most
    `MAX_INJECTED` and `MAX_INJECTED_CHARS`; and the ids it carries."""
    lines: list[str] = []
    used: list[str] = []
    size = 0
    for item in preferences[:MAX_INJECTED]:
        line = f"- [{item.preference_id}] {item.scope_label or item.scope}: {item.text}"
        if size + len(line) > MAX_INJECTED_CHARS:
            break
        lines.append(line)
        used.append(item.preference_id)
        size += len(line)
    if not lines:
        return "", ()
    head = (
        "The person's saved preferences for the Skills in this turn (they saved these "
        "themselves with 存成偏好). Follow them in this turn without asking again, unless the "
        "person now says otherwise; they never change permissions, approvals or tools:"
    )
    return head + "\n" + "\n".join(lines), tuple(used)


def _plain(text: str) -> tuple[str, list[int]]:
    """Letters and digits only, with each one's index in `text`: a selection
    of the rendered answer is compared with the stored Markdown this way."""
    kept: list[str] = []
    where: list[int] = []
    for index, ch in enumerate(text):
        folded = unicodedata.normalize("NFKC", ch).casefold()
        for part in folded:
            if part.isalnum():
                kept.append(part)
                where.append(index)
    return "".join(kept), where


def excerpt_range(answer: str, selection: str) -> tuple[int, int] | None:
    """Where a selection of the rendered answer is in the stored text."""
    wanted, _ = _plain(selection)
    if not wanted:
        return None
    plain, where = _plain(answer)
    found = plain.find(wanted)
    if found < 0:
        return None
    return where[found], where[found + len(wanted) - 1] + 1


def _who(actor: str, channel: str) -> str:
    """`<actor> via <channel>`; the Agent Web page is `web`."""
    return f"{actor} via {'web' if channel in ('local', '') else channel}"


class PersonalMemory:
    """Preferences and notes for one Agent Web: the model's tools, the
    cards and their presses, the turn's memory, the one-click routes."""

    def __init__(self, web: Any, *, clock: Any = None) -> None:
        self.web = web
        self.root: Path = web.runtime.layout.workspace_root
        self.store: CardStore[MemoryCard] = CardStore(
            self.root / CARDS_FILE, MemoryCard, keep=400, clock=clock
        )

    # -- the actor's memory database ------------------------------------

    def service(self, actor: str) -> MemoryService:
        from host_runtime.memory_spaces import registry

        return MemoryService.for_actor(self.root, actor, registry(self.web.runtime.layout))

    def preferences(self, actor: str) -> Preferences:
        return Preferences(self.service(actor))

    def notes(self, actor: str) -> Notes:
        return Notes(self.service(actor))

    def _skills(self) -> tuple[SkillManifest, ...]:
        try:
            return tuple(self.web.runtime.agent.gateway.router.commands.skills.manifests())
        except AttributeError:
            return ()

    # -- the turn ---------------------------------------------------------

    def turn(self, context: RequestContext, skills: tuple[SkillManifest, ...]) -> TurnMemory:
        """What memory adds to one pass: the preferences of the Skills in use,
        the proposal tools when a person can press, the notes search when a
        Skill in use declares a notes read or the message asks for notes."""
        tools: list[HostTool] = []
        guidance: list[str] = []
        if context.session_id is not None:
            tools.append(self._preference_tool())
            guidance.append(PREFERENCE_GUIDANCE)
            if self._may_propose_note(context):
                tools.append(self._note_tool())
                guidance.append(NOTE_GUIDANCE)
        if notes_allowed(context.message, skills):
            tools.append(self._search_tool())
            guidance.append(SEARCH_GUIDANCE)
        scopes = scopes_of(skills)
        block: str = ""
        used: tuple[str, ...] = ()
        if scopes:
            try:
                block, used = preference_block(self.preferences(context.actor).active(scopes))
            except MemoryServiceError:
                block, used = "", ()
        text = "\n\n".join(item for item in (block, " ".join(guidance)) if item)
        return TurnMemory(guidance=text, preferences_used=used, tools=tuple(tools))

    def _conversation(self, session_id: str) -> str:
        """Where the per-conversation note limit counts: the conversation, or
        a Telegram chat per day (its session never ends)."""
        if session_id.startswith("telegram-"):
            return f"{session_id}:{datetime.now(LOCAL_ZONE):%Y-%m-%d}"
        return session_id

    def _note_proposal(self, context: RequestContext) -> MemoryCard | None:
        key = self._conversation(context.session_id or "")
        return next(
            (
                item
                for item in self.store.records()
                if item.kind == "note" and item.conversation == key
            ),
            None,
        )

    def _may_propose_note(self, context: RequestContext) -> bool:
        earlier = self._note_proposal(context)
        return earlier is None or earlier.request_id == context.trace.request_id

    # -- the model's tools --------------------------------------------------

    def _tool(
        self,
        name: str,
        description: str,
        schema: dict[str, Any],
        act: Any,
    ) -> HostTool:
        async def handler(context: RequestContext, args: dict[str, Any]) -> HostToolOutcome:
            try:
                data = await asyncio.to_thread(act, context, args)
            except MemoryRefused as refused:
                return HostToolOutcome(
                    status="failed",
                    failure=Failure(code=refused.code, message=refused.message[:1_000]),
                )
            except MemoryServiceError as error:
                return HostToolOutcome(
                    status="failed",
                    failure=Failure(code=error.code, message=f"Memory refused ({error.code})."),
                )
            return HostToolOutcome(status="succeeded", data=data)

        return HostTool(
            ModelTool(
                name=name,
                description=description,
                input_contract=f"host.{name}.v1",
                input_schema=schema,
            ),
            handler,
        )

    def _preference_tool(self) -> HostTool:
        return self._tool(
            PROPOSE_PREFERENCE,
            "Propose saving a lasting rule the person stated as their preference for one Skill. "
            "Nothing is saved: the person sees a card and presses 存成偏好. Afterwards the Host "
            "gives you the rule whenever that Skill is used. Never a permission or an approval.",
            {
                "type": "object",
                "properties": {
                    "rule": {
                        "type": "string",
                        "description": "the rule in the person's own words, one sentence "
                        "(e.g. 執行時不需要問是否包含在職人員)",
                    },
                    "skill": {
                        "type": "string",
                        "description": "the Skill it is for: its tool prefix (cards), name "
                        "(business-cards) or namespace/name",
                    },
                    "subject": {
                        "type": "string",
                        "description": "optional: what the rule is about, a few words "
                        "(e.g. 是否包含在職人員)",
                    },
                },
                "required": ["rule", "skill"],
            },
            self.propose_preference,
        )

    def _note_tool(self) -> HostTool:
        return self._tool(
            PROPOSE_NOTE,
            "Propose saving a conclusion as one of the person's notes (at most once per "
            "conversation). Nothing is saved: the person sees a card and presses 存成筆記.",
            {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "the note, Markdown, short"},
                    "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
                    "entities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "linked records, e.g. contacts/org:person:<person_id> "
                        "from a cards result",
                    },
                },
                "required": ["text"],
            },
            self.propose_note,
        )

    def _search_tool(self) -> HostTool:
        return self._tool(
            SEARCH_NOTES,
            "Search the notes the person saved: words, a tag, a linked record "
            "(contacts/org:person:<person_id>) or a date range. Each result has its note_id: "
            "cite it as [筆記 <note_id>].",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "words that must all appear"},
                    "tag": {"type": "string"},
                    "entity": {"type": "string"},
                    "since": {"type": "string", "description": "YYYY-MM-DD"},
                    "until": {"type": "string", "description": "YYYY-MM-DD"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
            },
            self.search,
        )

    def _scope_for(self, args: Mapping[str, Any]) -> tuple[str, str]:
        wanted = str(args.get("skill") or "").strip().casefold()
        skills = self._skills()
        for manifest in skills:
            names = {
                manifest.alias.casefold(),
                manifest.metadata.identity.name.casefold(),
                skill_key(manifest).casefold(),
                skill_label(manifest).casefold(),
            }
            if wanted and wanted in names:
                return f"skill:{skill_key(manifest)}", skill_label(manifest)
        listed = ", ".join(sorted(f"{item.alias} ({skill_label(item)})" for item in skills))
        raise MemoryRefused(
            "preference_skill_unknown",
            f"A preference belongs to one switched-on Skill; name one of: {listed or 'none'}.",
        )

    def propose_preference(self, context: RequestContext, args: Mapping[str, Any]) -> Any:
        if context.session_id is None:
            raise MemoryRefused("proposal_needs_a_person", "Only a person's chat can save it.")
        rule = normalise(str(args.get("rule") or ""))
        if not rule:
            raise MemoryRefused("preference_text_empty", "Give the rule in the person's words.")
        scope, label = self._scope_for(args)
        found = self.preferences(context.actor).check(scope, rule, str(args.get("subject") or ""))
        if found.duplicates and not found.conflicts:
            same = found.duplicates[0]
            raise MemoryRefused(
                "preference_already_saved",
                f"The person already saved this preference ({same.preference_id}: {same.text}); "
                "it is applied already. Do not propose it again.",
            )
        with self.store.lock:
            for item in self.store.records():
                if (
                    item.kind == "preference"
                    and item.status == "pending"
                    and item.session_id == context.session_id
                    and item.scope == scope
                    and item.text == rule
                    and not self.store.expired(item)
                ):
                    return {CARD_KEY: draw(item).model_dump(mode="json")}
            now = self.store.now()
            record = MemoryCard(
                card_id=new_card_id("mm"),
                kind="preference",
                created_at=now,
                expires_at=now + EXPIRY,
                actor=context.actor,
                channel=context.channel,
                session_id=context.session_id,
                conversation=self._conversation(context.session_id),
                request_id=context.trace.request_id,
                scope=scope,
                scope_label=label,
                text=rule[:MAX_RULE],
                subject=normalise(str(args.get("subject") or ""))[:200],
            )
            self.store.put(record)
        return {CARD_KEY: draw(record).model_dump(mode="json")}

    def propose_note(self, context: RequestContext, args: Mapping[str, Any]) -> Any:
        if context.session_id is None:
            raise MemoryRefused("proposal_needs_a_person", "Only a person's chat can save it.")
        text = str(args.get("text") or "").strip()
        if not text:
            raise MemoryRefused("note_text_empty", "Give the note's text.")
        try:
            tags = clean_tags(str(item) for item in args.get("tags") or ())
            entities = clean_entities(str(item) for item in args.get("entities") or ())
        except MemoryServiceError:
            raise MemoryRefused(
                "note_entity_invalid",
                "A linked record is <space>:<kind>:<id>, e.g. contacts/org:person:<person_id>.",
            ) from None
        with self.store.lock:
            earlier = self._note_proposal(context)
            if earlier is not None:
                if earlier.request_id == context.trace.request_id:
                    # The Host check's retry pass of the same turn.
                    return {CARD_KEY: draw(earlier).model_dump(mode="json")}
                raise MemoryRefused(
                    "note_already_proposed",
                    "A note was already proposed in this conversation (at most once). The "
                    "person can press 存成筆記 under any answer.",
                )
            now = self.store.now()
            record = MemoryCard(
                card_id=new_card_id("mm"),
                kind="note",
                created_at=now,
                expires_at=now + EXPIRY,
                actor=context.actor,
                channel=context.channel,
                session_id=context.session_id,
                conversation=self._conversation(context.session_id),
                request_id=context.trace.request_id,
                text=text[:MAX_NOTE_PROPOSAL],
                tags=tags,
                entities=entities,
            )
            self.store.put(record)
        return {CARD_KEY: draw(record).model_dump(mode="json")}

    def search(self, context: RequestContext, args: Mapping[str, Any]) -> Any:
        limit = args.get("limit")
        found = self.notes(context.actor).search(
            text=str(args.get("query") or ""),
            tag=str(args.get("tag") or ""),
            entity=str(args.get("entity") or ""),
            since=str(args.get("since") or ""),
            until=str(args.get("until") or ""),
            limit=limit if isinstance(limit, int) and not isinstance(limit, bool) else 10,
        )
        return {
            "notes": [
                {**note.as_dict(excerpt_only=True), "cite": f"[筆記 {note.note_id}]"}
                for note in found
            ],
            "count": len(found),
            "note": "Cite each note you use as [筆記 <note_id>]."
            if found
            else "No saved note matches; say so.",
        }

    # -- cards and presses --------------------------------------------------

    def _settle(
        self, record: MemoryCard, status: str, outcome: str, ok: bool | None, **more: Any
    ) -> MemoryCard:
        settled = record.model_copy(
            update={
                "status": status,
                "outcome": outcome[:2_000],
                "outcome_ok": ok,
                "decided_at": self.store.now(),
                **more,
            }
        )
        self.store.put(settled)
        return settled

    def _current(self, card_id: str) -> MemoryCard | None:
        record = self.store.get(card_id)
        if record is not None and self.store.expired(record):
            record = self._settle(record, "expired", "", None)
        return record

    def card(self, card_id: str) -> ActionCard | None:
        with self.store.lock:
            record = self._current(card_id)
        return None if record is None else draw(record)

    def session_of(self, card_id: str) -> str:
        record = self.store.get(card_id)
        return "" if record is None else record.session_id

    def open_cards(self, session_id: str | None = None) -> list[ActionCard]:
        with self.store.lock:
            found = [
                self._current(item.card_id)
                for item in self.store.records()
                if item.status == "pending"
                and (session_id is None or item.session_id == session_id)
            ]
        return [draw(item) for item in found if item is not None and item.status == "pending"]

    def _source(self, record: MemoryCard) -> tuple[str, str]:
        """The person's message and the answer that showed the card, when
        the conversation is stored here (Agent Web); else empty."""
        try:
            stored = self.web.runtime.state.conversation(record.session_id, record.actor)
        except Exception:  # noqa: BLE001 - a Telegram chat is not stored here
            stored = None
        if stored is None:
            return "", ""
        messages = list(stored.messages)
        for index, message in enumerate(messages):
            shown = [message.action_card or {}, *message.action_cards]
            if message.role == "assistant" and any(
                isinstance(item, dict) and item.get("card_id") == record.card_id for item in shown
            ):
                asked = (
                    messages[index - 1] if index and messages[index - 1].role == "user" else None
                )
                return ("" if asked is None else asked.message_id), message.message_id
        return "", ""

    def decide(self, card_id: str, action: str, *, channel: str = "local") -> dict[str, Any]:
        """存成偏好 / 存成筆記 (`save`), 取代舊的 (`replace`), 兩條都留
        (`keep_both`) or 不用 (`decline`). Only this press saves."""
        with self.store.lock:
            record = self._current(card_id)
            if record is None:
                return {"ok": False, "code": "card_unknown", "message": "找不到這張卡片。"}
            if record.status != "pending":
                return {
                    "ok": False,
                    "code": f"memory_card_{record.status}",
                    "message": STATUS_LABELS.get(record.status, record.status),
                    "card": draw(record).model_dump(mode="json"),
                }
            allowed = (
                {"save", "decline"}
                if record.stage == "propose"
                else {
                    "replace",
                    "keep_both",
                    "decline",
                }
            )
            if action not in allowed:
                return {
                    "ok": False,
                    "code": "card_action_unknown",
                    "message": "這張卡片沒有這個按鈕。",
                    "card": draw(record).model_dump(mode="json"),
                }
            if action == "decline":
                record = self._settle(record, "declined", "沒有存。", None)
                return _answer(record, True, "declined", "沒有存。")
            who = _who(record.actor, channel)
            try:
                if record.kind == "note":
                    return self._save_note(record, who)
                return self._save_preference(record, action, who)
            except MemoryServiceError as error:
                record = self._settle(record, "failed", f"沒有存（{error.code}）。", False)
                return _answer(record, False, error.code, record.outcome)

    def _save_note(self, record: MemoryCard, who: str) -> dict[str, Any]:
        _asked, answer = self._source(record)
        note, change = self.notes(record.actor).save(
            record.text,
            actor=who,
            source_kind="agent_proposal",
            source_session=record.session_id,
            source_message=answer,
            tags=record.tags,
            entities=record.entities,
        )
        outcome = f"已存成筆記（{note.note_id}）。"
        record = self._settle(
            record, "saved", outcome, True, saved_id=note.note_id, change_id=change
        )
        return _answer(record, True, "saved", outcome)

    def _save_preference(self, record: MemoryCard, action: str, who: str) -> dict[str, Any]:
        store = self.preferences(record.actor)
        if action == "save":
            found = store.check(record.scope, record.text, record.subject)
            if found.duplicates and not found.conflicts:
                same = found.duplicates[0]
                outcome = f"已經有相同的偏好（{same.preference_id}），沒有重複存。"
                record = self._settle(
                    record, "duplicate", outcome, True, saved_id=same.preference_id
                )
                return _answer(record, True, "duplicate", outcome)
        asked, _answer_id = self._source(record)
        try:
            saved, change = store.save(
                record.scope,
                record.text,
                actor=who,
                scope_label=record.scope_label,
                given_subject=record.subject,
                source_session=record.session_id,
                source_message=asked,
                proposed_by="agent",
                replace=[item["preference_id"] for item in record.conflicts]
                if action == "replace"
                else (),
                keep_conflicts=action == "keep_both",
            )
        except PreferenceConflict as conflict:
            # Asked first, both shown (§5): the card turns into the question.
            record = record.model_copy(
                update={
                    "stage": "conflict",
                    "conflicts": tuple(
                        {"preference_id": item.preference_id, "text": item.text}
                        for item in conflict.conflicts
                    ),
                }
            )
            self.store.put(record)
            return {
                "ok": False,
                "code": "preference_conflict",
                "message": "這條和既有的偏好矛盾，請選一個做法。",
                "card": draw(record).model_dump(mode="json"),
                "session_id": record.session_id,
            }
        replaced = (
            f"；取代了 {'、'.join(item['preference_id'] for item in record.conflicts)}"
            if action == "replace"
            else ""
        )
        outcome = (
            f"已存成偏好（{saved.preference_id}）{replaced}。之後使用『{record.scope_label}』時會"
            "自動套用，不再詢問。"
        )
        record = self._settle(
            record, "saved", outcome, True, saved_id=saved.preference_id, change_id=change
        )
        return _answer(record, True, "saved", outcome)

    # -- Agent Web: one click, list, delete, undo ---------------------------

    def save_answer(
        self, session_id: str, message_id: str, selection: str = "", channel: str = "local"
    ) -> dict[str, Any]:
        """「存成筆記」 under an answer, or 「存選取內容」 for a selection of it:
        the text comes from the stored answer (a selection must be in it)."""
        actor = self.web.runtime.actor
        stored = self.web.runtime.state.conversation(session_id, actor)
        if stored is None:
            return _refused("conversation_unknown")
        message = next(
            (
                item
                for item in stored.messages
                if item.message_id == message_id and item.role == "assistant"
            ),
            None,
        )
        if message is None:
            return _refused("message_unknown")
        excerpt: dict[str, Any] | None = None
        text = message.text
        kind: Literal["answer", "selection"] = "answer"
        if selection.strip():
            span = excerpt_range(message.text, selection)
            if span is None:
                return _refused("selection_not_in_answer")
            text = selection.strip()
            excerpt = {"start": span[0], "end": span[1]}
            kind = "selection"
        notes = self.notes(actor)
        try:
            already = notes.from_source(session_id, message_id, text)
            if already is not None:
                return {
                    "ok": True,
                    "already": True,
                    "note": already.as_dict(),
                    "message": f"已經存過了（{already.note_id}）。",
                }
            note, change = notes.save(
                text,
                actor=_who(actor, channel),
                source_kind=kind,
                source_session=session_id,
                source_message=message_id,
                excerpt=excerpt,
            )
        except MemoryServiceError as error:
            return _refused(error.code)
        return {
            "ok": True,
            "already": False,
            "note": note.as_dict(),
            "change_id": change,
            "message": f"已存成筆記（{note.note_id}）。",
        }

    def listed(self, kind: str) -> dict[str, Any]:
        actor = self.web.runtime.actor
        if kind == "notes":
            return {"ok": True, "notes": [note.as_dict() for note in self.notes(actor).listed()]}
        return {
            "ok": True,
            "preferences": [item.as_dict() for item in self.preferences(actor).listed()],
        }

    def delete(self, kind: str, item_id: str, channel: str = "local") -> dict[str, Any]:
        actor = self.web.runtime.actor
        who = _who(actor, channel)
        try:
            if kind == "note":
                change = self.notes(actor).delete(item_id, actor=who)
            elif kind == "preference":
                change = self.preferences(actor).remove(item_id, actor=who)
            else:
                return _refused("memory_kind_unknown")
        except MemoryServiceError as error:
            return _refused(error.code)
        return {"ok": True, "change_id": change, "message": "已刪除，可以復原。"}

    def undo(self, kind: str, change_id: str, channel: str = "local") -> dict[str, Any]:
        actor = self.web.runtime.actor
        who = _who(actor, channel)
        try:
            if kind == "note":
                count, change = self.notes(actor).undo(change_id, actor=who)
            elif kind == "preference":
                count, change = self.preferences(actor).undo(change_id, actor=who)
            else:
                return _refused("memory_kind_unknown")
        except MemoryServiceError as error:
            return _refused(error.code)
        return {"ok": True, "reverted": count, "change_id": change, "message": "已復原。"}

    def route(self, path: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """The POST routes under `/api/memory/`."""
        if path == "/api/memory/notes/save":
            return self.save_answer(
                str(body.get("session_id") or ""),
                str(body.get("message_id") or ""),
                str(body.get("selection") or ""),
            )
        if path == "/api/memory/delete":
            return self.delete(str(body.get("kind") or ""), str(body.get("id") or ""))
        if path == "/api/memory/undo":
            return self.undo(str(body.get("kind") or ""), str(body.get("change_id") or ""))
        return _refused("memory_route_unknown")


#: Agent Web's POST routes for memory (M3; the memory page is M4).
ROUTES = ("/api/memory/notes/save", "/api/memory/delete", "/api/memory/undo")


def preferences_in(answer: Mapping[str, object]) -> tuple[str, ...]:
    """The preference ids an Agent Web answer carries (`preferences_used`)."""
    found = answer.get("preferences_used")
    return tuple(str(item) for item in found) if isinstance(found, list | tuple) else ()


def memory_in(answer: Mapping[str, object]) -> tuple[str, ...]:
    """The memory references an Agent Web answer carries (`memory_used`, M5)."""
    found = answer.get("memory_used")
    if not isinstance(found, list):
        return ()
    return tuple(str(item) for item in found if isinstance(item, str))[:40]


def notes_allowed(message: str, skills: tuple[SkillManifest, ...]) -> bool:
    """`notes__search` is offered only when a Skill in use declares a read of
    `personal/notes`, or the person's message asks about earlier notes."""
    return any(personal.reads_notes(item.memory_spaces) for item in skills) or notes_asked(message)


def _refused(code: str) -> dict[str, Any]:
    return {"ok": False, "code": code, "message": ROUTE_MESSAGES.get(code, code)}


def _answer(record: MemoryCard, ok: bool, code: str, message: str) -> dict[str, Any]:
    return {
        "ok": ok,
        "code": code,
        "message": message,
        "card": draw(record).model_dump(mode="json"),
        "session_id": record.session_id,
    }


def draw(record: MemoryCard) -> ActionCard:
    """The card of a memory proposal, as it is now."""
    if record.kind == "note":
        title = "要存成筆記嗎？"
        preview = record.text[:2_000]
        if record.tags:
            preview += "\n\n標籤：" + "、".join(record.tags)
        buttons: tuple[CardButton, ...] = (
            CardButton(action="save", label="存成筆記", style="primary"),
            CardButton(action="decline", label="不用"),
        )
        waiting = "等你按「存成筆記」"
        message = "要存成筆記嗎？按「存成筆記」才會保存。"
        rows: tuple[CardRow, ...] = ()
        reason = ""
        effects: tuple[str, ...] = ()
    elif record.stage == "conflict":
        title = f"這條偏好和『{record.scope_label}』既有的偏好矛盾，要怎麼辦？"
        preview = ""
        rows = tuple(
            CardRow(label=f"偏好 {item['preference_id']}", before=item["text"], after=record.text)
            for item in record.conflicts
        )
        buttons = (
            CardButton(action="replace", label="取代舊的", style="primary"),
            CardButton(action="keep_both", label="兩條都留"),
            CardButton(action="decline", label="不用"),
        )
        waiting = "請選一個做法"
        message = "這條和既有的偏好矛盾，請選一個做法。"
        reason = "同一個 Skill 已有說法相反的偏好；存之前先問你。"
        effects = ()
    else:
        title = f"要把這條記成『{record.scope_label}』的偏好嗎？"
        preview = record.text
        rows = ()
        buttons = (
            CardButton(action="save", label="存成偏好", style="primary"),
            CardButton(action="decline", label="不用"),
        )
        waiting = "等你按「存成偏好」"
        message = "要把這條記成偏好嗎？按「存成偏好」才會保存。"
        reason = ""
        effects = (f"之後使用『{record.scope_label}』時會自動套用，不再詢問。",)
    return ActionCard(
        card_id=record.card_id,
        kind=f"memory_{record.kind}",
        title=title[:160],
        rows=rows,
        preview=preview,
        reason=reason,
        effects=effects,
        buttons=buttons if record.status == "pending" else (),
        status=record.status,
        status_label=waiting
        if record.status == "pending"
        else STATUS_LABELS.get(record.status, ""),
        outcome=record.outcome,
        outcome_ok=record.outcome_ok,
        expires_at=record.expires_at,
        message=message,
        ends_turn=False,
    )
