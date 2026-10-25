"""A Telegram question flow generated from a Workflow's parameter declaration.

rs_workflow_system's bot asked a workflow's fields one at a time from its
`PARAMS_SCHEMA` (`telegram_pack.questions_from_schema`). This is the same
idea over AEP's `WorkflowParameter`: the fields shown on the `telegram`
channel, in form order, each converted from a reply or a button tap and
checked by the shared field rules. The flow is pure state; the ingress
sends its prompts and runs the Workflow once the person confirms.

Forms v2 (owner 2026-10-15): a multi-select is a set of toggle buttons and a
Done button; a pick-or-type list (`allow_other`) takes a typed value; an
upload field takes documents one by one, then /done (when the ingress has an
upload store); and identity fields may be filled from last time.

Fewer questions (owner 2026-10-25, 「有輸入過的參數能不能自己填啊？」): values
given with the request (or by the model's run form), last time's identity
values and declared defaults are used and never asked; optional fields are
not asked one by one. Only required fields still missing are asked, then
one confirmation card lists every value with where it came from. The card
has 確認執行 and 修改; 修改, or free text such as 「Dry run 改成否」 or
「From date 2026-10-19」, changes a value and shows the card again.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from common.assets import (
    AssetIdentity,
    WorkflowManifest,
    WorkflowParameter,
    parameter_value_problem,
)
from common.workflow_forms import IDENTITY_GROUP, ordered_fields
from common.workflow_parameters import WorkflowParameterError, validate_run_parameters

FLOW_TTL_SECONDS = 15 * 60
BUTTONS_PER_ROW = 3
#: Choice buttons on one keyboard; Telegram allows 100 buttons, and a
#: multi-select needs one more for Done.
MAX_BUTTONS = 96
#: Telegram's limit on a button's callback data, in bytes.
MAX_CALLBACK_BYTES = 64
_YES = {"yes", "y", "true", "1", "是", "對", "好", "確認"}
_NO = {"no", "n", "false", "0", "否", "不", "不要", "取消"}
_SPLIT = re.compile(r"[\n,，、;；]+")
_PICK = re.compile(r"^pick:(\d{1,3})$")
_POSITION = re.compile(r"^#(\d{1,3})$")
_EDIT = re.compile(r"^edit:(\d{1,3})$")
CHECK = "✓ "
#: The confirmation card's buttons (owner 2026-10-25).
RUN_BUTTON = ("確認執行", "run:yes")
EDIT_BUTTON = ("修改", "run:edit")
BACK_BUTTON = ("返回", "edit:back")
_RUN_WORDS = {"run:yes", "確認執行", "執行", "run", *_YES}
_EDIT_WORDS = {"run:edit", "修改", "改", "edit", "change"}
_CANCEL_WORDS = {"/cancel", "run:no", "取消", "cancel"}
#: Where a value on the card came from.
FROM_MESSAGE = "（從你的訊息）"
FROM_DEFAULT = "（預設）"
FROM_LAST_TIME = "（上次的值）"
# What joins a field and its new value in a typed edit.
_EDIT_JOIN = re.compile(
    r"^\s*(?:改成|改為|改为|設為|设为|設成|设成|換成|换成|用|=|:|：|->|→|to\b|is\b)?\s*",
    re.IGNORECASE,
)
_LABEL_HEAD = re.compile(r"[:：,，(（;；]")

Button = tuple[str, str]


@dataclass
class FlowPrompt:
    text: str
    buttons: list[list[Button]] = field(default_factory=list)
    # Replace the message the tapped button sits on (a multi-select toggle)
    # instead of sending a new one.
    edit: bool = False


ChoicesProvider = Callable[[WorkflowManifest, str, Mapping[str, Any]], "list[str] | None"]


@dataclass
class FlowState:
    manifest: WorkflowManifest
    effect: str | None
    fields: tuple[WorkflowParameter, ...]
    # Current `ref:` / `fn:` choices, from the same provider the engine checks.
    choices: ChoicesProvider | None = None
    # The field being asked (an index into `fields`), -1 before the first.
    index: int = -1
    answers: dict[str, Any] = field(default_factory=dict)
    confirming: bool = False
    started: float = field(default_factory=time.monotonic)
    # Identity values from last time: used, marked on the card, never asked.
    preset: dict[str, Any] = field(default_factory=dict)
    # Values ticked so far on the current multi-select.
    picked: list[str] = field(default_factory=list)
    # The upload set this flow stores documents in (set by the ingress).
    upload_set: str | None = None
    # Run values given with the request ("run X company=Foxconn", 「43W」, or
    # by the model for its own fields): answered already, never asked, always
    # shown on the card before the run (owner 2026-10-15, 2026-10-25).
    prefilled: frozenset[str] = frozenset()
    # Indexes of the fields asked one by one: required ones still missing.
    queue: tuple[int, ...] = ()
    # Position in `queue` of the field being asked.
    position: int = 0
    # Asking one field from the card (修改): the card comes back after it.
    editing: bool = False
    # The card's 修改 menu is showing.
    choosing: bool = False
    # The Telegram message the current question was sent as; a button tapped
    # on any other message belongs to an earlier question (set by the ingress).
    prompt_message_id: int | None = None
    _cache: dict[str, list[str] | None] = field(default_factory=dict)

    @property
    def workflow(self) -> AssetIdentity:
        return self.manifest.metadata.identity

    def expired(self, now: float | None = None) -> bool:
        return (now if now is not None else time.monotonic()) - self.started > FLOW_TTL_SECONDS


@dataclass
class FlowStep:
    kind: Literal["ask", "cancelled", "ready"]
    prompt: FlowPrompt | None = None
    arguments: dict[str, Any] | None = None


def start(
    manifest: WorkflowManifest,
    effect: str | None,
    choices: ChoicesProvider | None = None,
    *,
    uploads: bool = False,
    preset: Mapping[str, Any] | None = None,
    prefill: Mapping[str, Any] | None = None,
) -> FlowState | str:
    """A new flow, or why this Workflow cannot be filled in from Telegram.

    `uploads` says the ingress can store documents for `upload` fields; without
    it a required upload is refused and an optional one left out, as before.
    """
    fields = ordered_fields(manifest, "telegram")
    if not uploads:
        for item in fields:
            if item.kind == "upload" and item.required:
                return (
                    f"{item.label} needs a file upload, which Telegram does not accept "
                    "here; run this Workflow from Agent Web."
                )
        fields = tuple(item for item in fields if item.kind != "upload")
    shown = {item.name for item in fields}
    given = {name: value for name, value in (prefill or {}).items() if name in shown}
    identity = {item.name for item in fields if item.group == IDENTITY_GROUP}
    remembered = {
        name: value
        for name, value in (preset or {}).items()
        if name in identity and name not in given
    }
    return FlowState(
        manifest,
        effect,
        fields,
        choices,
        answers={**remembered, **given},
        preset=remembered,
        prefilled=frozenset(given),
    )


def _title(state: FlowState) -> str:
    return state.manifest.metadata.identity.name


def _dynamic_values(state: FlowState, item: WorkflowParameter) -> list[str] | None:
    source = item.choices_source
    if not source or state.choices is None:
        return None
    # A slow list (a package index) is read once per question, not per reply.
    key = item.name + "\0" + json.dumps(state.answers, sort_keys=True, default=str)
    if key not in state._cache:
        state._cache = {key: state.choices(state.manifest, source, state.answers)}
    return state._cache[key]


def _choices(state: FlowState, item: WorkflowParameter) -> list[tuple[str, str]]:
    """(value, label) pairs for a select, from its source or its declaration."""
    if item.kind != "select":
        return []
    if item.choices_source:
        return [(value, value) for value in _dynamic_values(state, item) or []]
    labels = {choice.value: (choice.label or choice.value) for choice in item.choices}
    return [(value, labels.get(value, value)) for value in item.choice_values]


def _rows(buttons: list[Button], width: int = BUTTONS_PER_ROW) -> list[list[Button]]:
    return [buttons[i : i + width] for i in range(0, len(buttons), width)]


def _choice_buttons(state: FlowState, item: WorkflowParameter) -> list[list[Button]]:
    if item.kind == "boolean":
        return [[("Yes", "yes"), ("No", "no")]]
    if item.kind == "upload":
        return [[("Done", "/done")]] if item.multiple else []
    listed = _choices(state, item)[:MAX_BUTTONS]
    if not listed:
        return []
    if item.multiple:
        rows = _rows(
            [
                ((CHECK if value in state.picked else "") + label, f"pick:{position}")
                for position, (value, label) in enumerate(listed, start=1)
            ]
        )
        return [*rows, [("Done", "pick:done")]]
    return _rows(
        [
            (label, value if len(value.encode("utf-8")) <= MAX_CALLBACK_BYTES else f"#{position}")
            for position, (value, label) in enumerate(listed, start=1)
        ]
    )


def _shown(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    return ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)


def prefill_note(state: FlowState) -> str | None:
    """「已從你的訊息帶入：…」 for the values given with the request."""
    given = [item for item in state.fields if item.name in state.prefilled]
    if not given:
        return None
    return "已從你的訊息帶入：" + "；".join(
        f"{item.label} = {_shown(state.answers.get(item.name))}"
        for item in given
        if item.name in state.answers
    )


def _preset_note(state: FlowState) -> str | None:
    """「沿用上次的值：…」 for the identity values taken from last time."""
    kept = [item for item in state.fields if item.name in state.preset]
    if not kept:
        return None
    return "沿用上次的值：" + "；".join(
        f"{item.label} = {_shown(state.preset[item.name])}" for item in kept
    )


def _current(state: FlowState) -> WorkflowParameter | None:
    if state.confirming or state.choosing or not 0 <= state.index < len(state.fields):
        return None
    return state.fields[state.index]


def prompt(state: FlowState) -> FlowPrompt:
    if state.choosing:
        return _edit_menu(state)
    if state.confirming:
        return _confirmation(state)
    item = state.fields[state.index]
    if state.editing:
        header = f"{_title(state)} (修改)"
    else:
        header = f"{_title(state)} ({state.position + 1}/{len(state.queue)})"
    lines = [header, item.label + (" *" if item.required else "")]
    if item.help or item.description:
        lines.append(item.help or item.description or "")
    listed = _choices(state, item)
    if item.kind == "upload":
        kinds = f" ({', '.join(item.accept)})" if item.accept else ""
        if item.multiple:
            received = state.answers.get(item.name) or []
            lines.append(f"Send the files{kinds} as documents, one by one, then /done.")
            if received:
                lines.append(f"Received {len(received)} so far.")
        else:
            lines.append(f"Send the file{kinds} as a document.")
    elif item.multiple and listed:
        lines.append("Tap to tick, then Done. You can also type the values, separated by commas.")
        if len(listed) > MAX_BUTTONS:
            lines.append(
                "More choices than buttons: "
                + ", ".join(value for value, _ in listed[MAX_BUTTONS:])
            )
    elif item.kind in ("text_list", "emails") or item.multiple:
        lines.append("Several values: separate them with commas or new lines.")
    if item.choices_source and item.kind == "select" and not listed:
        if item.allow_other:
            lines.append("Its choice list is not available right now; type the value.")
        elif _dynamic_values(state, item) is None:
            lines.append("Its choice list is not available yet; type the value.")
        else:
            lines.append("Its choice list is empty.")
    elif item.allow_other:
        lines.append("Tap one, or type another value.")
    if item.default is not None:
        lines.append(f"Default: {_shown(item.default)}")
    if item.confirm:
        lines.append("This is a privileged setting; it is confirmed before the run.")
    lines.append("/skip uses the default" if not item.required else "Required.")
    lines.append("/cancel stops.")
    if not state.editing and state.position == 0:
        lines[:0] = [note for note in (prefill_note(state), _preset_note(state)) if note]
    return FlowPrompt("\n".join(lines), _choice_buttons(state, item))


def _value_line(state: FlowState, item: WorkflowParameter) -> str | None:
    mark = " (privileged)" if item.confirm else ""
    if item.name in state.answers:
        value = state.answers[item.name]
        if item.kind == "upload":
            files = value if isinstance(value, list) else [value]
            value = [str(path).replace("\\", "/").rsplit("/", 1)[-1] for path in files]
        source = (
            FROM_MESSAGE
            if item.name in state.prefilled
            else FROM_LAST_TIME
            if item.name in state.preset and state.preset.get(item.name) == value
            else ""
        )
        return f"- {item.label}{mark}：{_shown(value)}{source}"
    if item.default is not None:
        return f"- {item.label}{mark}：{_shown(item.default)}{FROM_DEFAULT}"
    return None


def _confirmation(state: FlowState) -> FlowPrompt:
    shown = [
        f"執行 {_title(state)}？"
        + (f"（effects: {state.effect}）" if state.effect and state.effect != "read" else "")
    ]
    unset: list[str] = []
    for item in state.fields:
        line = _value_line(state, item)
        if line is None:
            unset.append(item.label)
        else:
            shown.append(line)
    if unset:
        shown.append("未填（不使用）：" + "、".join(unset))
    if state.fields:
        shown.append(f"要改值：點「修改」，或直接輸入，例如{_edit_examples(state)}。")
    shown.append("/cancel 取消。")
    buttons = [[RUN_BUTTON, EDIT_BUTTON]] if state.fields else [[RUN_BUTTON, ("取消", "run:no")]]
    return FlowPrompt("\n".join(shown), buttons)


def _short_label(item: WorkflowParameter) -> str:
    """The label's head: 「Dry run」 of 「Dry run: show the plan only」,
    「只試跑」 of 「只試跑？」."""
    head = _LABEL_HEAD.split(item.label, 1)[0].strip().rstrip("?？").strip()
    return head or item.label


def _edit_examples(state: FlowState) -> str:
    switch = next((item for item in state.fields if item.kind == "boolean"), None)
    other = next(
        (item for item in state.fields if item.kind in ("date", "text", "integer", "select")),
        None,
    )
    examples = []
    if switch is not None:
        examples.append(f"「{_short_label(switch)} 改成否」")
    if other is not None:
        sample = {"date": "2026-10-19", "integer": "10"}.get(other.kind, "…")
        examples.append(f"「{_short_label(other)} {sample}」")
    return "、".join(examples) or "「欄位名稱 新的值」"


def _edit_menu(state: FlowState) -> FlowPrompt:
    buttons = [
        (_short_label(item)[:40], f"edit:{position}")
        for position, item in enumerate(state.fields[:MAX_BUTTONS])
    ]
    return FlowPrompt(
        "要修改哪一項？也可以直接輸入，例如" + _edit_examples(state) + "。",
        [*_rows(buttons, 2), [BACK_BUTTON]],
    )


def _convert(item: WorkflowParameter, text: str, dynamic: list[str] | None = None) -> Any:
    raw = text.strip()
    if item.kind == "boolean":
        lowered = raw.casefold()
        if lowered in _YES:
            return True
        if lowered in _NO:
            return False
        raise ValueError("answer yes or no")
    if item.kind == "integer":
        if not re.fullmatch(r"-?\d+", raw):
            raise ValueError("enter a whole number")
        return int(raw)
    if item.kind == "number":
        try:
            return float(raw) if "." in raw else int(raw)
        except ValueError:
            raise ValueError("enter a number") from None
    if item.kind in ("text_list", "emails") or item.multiple:
        values = [part.strip() for part in _SPLIT.split(raw) if part.strip()]
        return [_match_choice(item, value, dynamic) for value in values]
    if item.kind == "select":
        return _match_choice(item, raw, dynamic)
    return raw


def _match_choice(item: WorkflowParameter, value: str, dynamic: list[str] | None = None) -> str:
    """A declared or published value, its label, its 1-based position (or the
    `#n` a long value's button sends), or, when the list allows it, any text."""
    position = _POSITION.match(value)
    if dynamic is not None:
        if value in dynamic:
            return value
        if position is not None and 1 <= int(position.group(1)) <= len(dynamic):
            return dynamic[int(position.group(1)) - 1]
        if item.allow_other:
            return value
        if value.isdigit() and 1 <= int(value) <= len(dynamic):
            return dynamic[int(value) - 1]
        raise ValueError("choose one of the listed values")
    if not item.choice_values or item.choices_source:
        return value
    if value in item.choice_values:
        return value
    for choice in item.choices:
        if (choice.label or "").casefold() == value.casefold():
            return choice.value
    number = position.group(1) if position is not None else value
    if (
        number.isdigit()
        and 1 <= int(number) <= len(item.choice_values)
        and (position is not None or not item.allow_other)
    ):
        return item.choice_values[int(number) - 1]
    if item.allow_other:
        return value
    raise ValueError("choose one of the listed values")


def _needs_asking(state: FlowState, item: WorkflowParameter) -> bool:
    """Only a required field with no value and no default is asked."""
    return item.required and item.name not in state.answers and item.default is None


def _ask(state: FlowState, index: int, *, editing: bool = False) -> FlowStep:
    state.index = index
    state.editing = editing
    state.confirming = False
    state.choosing = False
    state.picked = []
    return FlowStep("ask", prompt(state))


def _next(state: FlowState) -> FlowStep:
    """After an answer: the next missing required field, else the card."""
    state.picked = []
    if state.editing:
        state.editing = False
        return _finish(state)
    state.position += 1
    while state.position < len(state.queue) and not _needs_asking(
        state, state.fields[state.queue[state.position]]
    ):
        state.position += 1
    if state.position < len(state.queue):
        return _ask(state, state.queue[state.position])
    return _finish(state)


def _finish(state: FlowState) -> FlowStep:
    try:
        validate_run_parameters(state.manifest, state.answers)
    except WorkflowParameterError as error:
        # Ask again the field the shared rules refused.
        name = str(error).split(" ", 1)[0]
        index = next((index for index, item in enumerate(state.fields) if item.name == name), 0)
        state.answers.pop(name, None)
        state.prefilled = state.prefilled - {name}
        asked = _ask(state, index, editing=True)
        assert asked.prompt is not None
        return FlowStep("ask", FlowPrompt(f"{error}.\n\n{asked.prompt.text}", asked.prompt.buttons))
    if not state.fields and state.effect == "read":
        # Nothing to show or change: a read-only run with no fields just runs.
        return FlowStep("ready", arguments=validate_run_parameters(state.manifest, state.answers))
    state.confirming = True
    state.choosing = False
    state.editing = False
    return FlowStep("ask", prompt(state))


def begin(state: FlowState) -> FlowStep:
    """The first missing required question, or the card when none is missing."""
    state.queue = tuple(
        index for index, item in enumerate(state.fields) if _needs_asking(state, item)
    )
    state.position = 0
    if state.queue:
        return _ask(state, state.queue[0])
    return _finish(state)


def current_upload(state: FlowState) -> WorkflowParameter | None:
    """The upload field the flow is waiting on, if any."""
    item = _current(state)
    return item if item is not None and item.kind == "upload" else None


def add_upload(state: FlowState, path: str) -> FlowStep:
    """A stored document for the current upload field."""
    item = current_upload(state)
    if item is None:
        return FlowStep("ask", prompt(state))
    if not item.multiple:
        state.answers[item.name] = path
        return _next(state)
    state.answers.setdefault(item.name, []).append(path)
    return FlowStep("ask", prompt(state))


def _again(state: FlowState, message: str, *, edit: bool = False) -> FlowStep:
    again = prompt(state)
    return FlowStep("ask", FlowPrompt(f"{message}\n\n{again.text}", again.buttons, edit))


def _answer_pick(state: FlowState, item: WorkflowParameter, reply: str) -> FlowStep | None:
    """A tap on a multi-select: toggle one value, or Done. None: not a tap."""
    if reply == "pick:done":
        if not state.picked:
            if item.required:
                return _again(state, "Tick at least one.")
            state.answers.pop(item.name, None)
            return _next(state)
        ticked = list(state.picked)
        problem = parameter_value_problem(item, ticked)
        if problem:
            return _again(state, f"{item.label} {problem}.")
        _set(state, item, ticked)
        return _next(state)
    tapped = _PICK.match(reply)
    if tapped is None:
        return None
    listed = _choices(state, item)[:MAX_BUTTONS]
    position = int(tapped.group(1))
    if not 1 <= position <= len(listed):
        return _again(state, "That choice is no longer listed.")
    value = listed[position - 1][0]
    if value in state.picked:
        state.picked.remove(value)
    else:
        state.picked.append(value)
    again = prompt(state)
    return FlowStep("ask", FlowPrompt(again.text, again.buttons, edit=True))


def _set(state: FlowState, item: WorkflowParameter, value: Any) -> None:
    """A value the person chose now: no longer marked as given or last time's."""
    state.answers[item.name] = value
    state.prefilled = state.prefilled - {item.name}
    state.preset.pop(item.name, None)


def _key_pattern(key: str) -> re.Pattern[str] | None:
    parts = [re.escape(part) for part in re.split(r"[\s_\-]+", key.strip()) if part]
    if not parts:
        return None
    return re.compile(r"^\s*" + r"[\s_\-]*".join(parts) + r"(?![A-Za-z0-9])", re.IGNORECASE)


def _edit_target(state: FlowState, reply: str) -> tuple[WorkflowParameter, str] | None:
    """The field a typed edit names at its start (its label, the label's head
    or its name; spaces, `_` and `-` alike), and the rest of the text."""
    best: tuple[int, WorkflowParameter] | None = None
    for item in state.fields:
        for key in (item.label, _short_label(item), item.name):
            pattern = _key_pattern(key)
            found = pattern.match(reply) if pattern is not None else None
            if found is not None and (best is None or found.end() > best[0]):
                best = (found.end(), item)
    if best is None:
        return None
    return best[1], reply[best[0] :]


def _typed_edit(state: FlowState, reply: str) -> FlowStep | None:
    """「Dry run 改成否」, 「From date 2026-10-19」, 「week=2026_44W」, or a
    switch's name alone (it flips): the card again, or None when the text
    names no field."""
    target = _edit_target(state, reply)
    if target is None:
        return None
    item, rest = target
    value_text = _EDIT_JOIN.sub("", rest, count=1).strip()
    if item.kind == "upload":
        return _ask(state, state.fields.index(item), editing=True)
    if not value_text:
        if item.kind == "boolean":
            current = state.answers.get(item.name, item.default)
            _set(state, item, not bool(current))
            return _finish_with(state, f"已改：{item.label} = {_shown(not bool(current))}")
        return _ask(state, state.fields.index(item), editing=True)
    try:
        value = _convert(item, value_text, _dynamic_values(state, item))
    except ValueError as error:
        problem: str | None = str(error)
    else:
        problem = parameter_value_problem(item, value)
    if problem:
        return _finish_with(state, f"{item.label} {problem}；沒有改。")
    _set(state, item, value)
    return _finish_with(state, f"已改：{item.label} = {_shown(value)}")


def _finish_with(state: FlowState, message: str) -> FlowStep:
    step = _finish(state)
    if step.prompt is None:
        return step
    return FlowStep("ask", FlowPrompt(f"{message}\n\n{step.prompt.text}", step.prompt.buttons))


def _answer_card(state: FlowState, reply: str) -> FlowStep:
    lowered = reply.casefold()
    if lowered in _RUN_WORDS:
        try:
            arguments = validate_run_parameters(state.manifest, state.answers)
        except WorkflowParameterError:
            return _finish(state)
        state.confirming = False
        return FlowStep("ready", arguments=arguments)
    if lowered in _EDIT_WORDS and state.fields:
        state.confirming = False
        state.choosing = True
        return FlowStep("ask", prompt(state))
    edited = _typed_edit(state, reply)
    if edited is not None:
        return edited
    return _again(state, "看不懂要改哪一項。")


def _answer_menu(state: FlowState, reply: str) -> FlowStep:
    if reply.casefold() in ("edit:back", "返回", "back"):
        state.choosing = False
        return _finish(state)
    tapped = _EDIT.match(reply)
    if tapped is not None and int(tapped.group(1)) < len(state.fields):
        return _ask(state, int(tapped.group(1)), editing=True)
    edited = _typed_edit(state, reply)
    if edited is not None:
        return edited
    return _again(state, "點要修改的那一項，或點「返回」。")


def answer(state: FlowState, text: str) -> FlowStep:
    reply = text.strip()
    if reply.casefold() in _CANCEL_WORDS:
        return FlowStep("cancelled")
    if state.choosing:
        return _answer_menu(state, reply)
    if state.confirming:
        return _answer_card(state, reply)
    item = state.fields[state.index]
    if reply.casefold() == "/skip":
        if item.required:
            return FlowStep(
                "ask",
                FlowPrompt(
                    "This field is required.\n\n" + prompt(state).text, prompt(state).buttons
                ),
            )
        state.answers.pop(item.name, None)
        state.prefilled = state.prefilled - {item.name}
        return _next(state)
    if item.kind == "upload":
        if reply.casefold() == "/done" and item.multiple:
            if item.required and not state.answers.get(item.name):
                return _again(state, "Send at least one file first.")
            return _next(state)
        return _again(state, "Send the file as a document (not as text or a photo).")
    if item.multiple and item.kind == "select":
        tapped = _answer_pick(state, item, reply)
        if tapped is not None:
            return tapped
    try:
        value = _convert(item, reply, _dynamic_values(state, item))
    except ValueError as error:
        problem: str | None = str(error)
    else:
        problem = parameter_value_problem(item, value)
    if problem:
        return _again(state, f"{item.label} {problem}.")
    _set(state, item, value)
    return _next(state)


def answer_field(state: FlowState, name: str, text: str) -> FlowStep:
    """A reply to an earlier question of this flow (a Telegram Reply on it):
    sets that field, checked like a typed answer, then carries on where the
    flow was. An invalid value is said and the current question asked."""
    item = next((entry for entry in state.fields if entry.name == name), None)
    if item is None:
        return _again(state, "That question is not part of this run any more.")
    try:
        value = _convert(item, text, _dynamic_values(state, item))
    except ValueError as error:
        problem: str | None = str(error)
    else:
        problem = parameter_value_problem(item, value)
    if problem:
        return _again(state, f"{item.label} {problem}.")
    _set(state, item, value)
    if state.confirming or state.choosing or state.editing or state.index == -1:
        return _finish(state)
    if state.fields[state.index].name == name:
        return _next(state)
    return FlowStep("ask", prompt(state))


#: The first two lines of a question this flow sends: 「<name> (2/9)」 or
#: 「<name> (修改)」, then the field's label (with 「 *」 when required).
_QUESTION = re.compile(r"^(?P<workflow>\S+) \((?:\d+/\d+|修改)\)$")


def quoted_question(quoted: str) -> tuple[str, str] | None:
    """(Workflow name, field label) when `quoted` is one of this flow's
    questions, as a Reply or a tapped button carries it; else None."""
    lines = [line.strip() for line in quoted.splitlines() if line.strip()]
    for position, line in enumerate(lines[:-1]):
        found = _QUESTION.match(line)
        if found is not None:
            label = lines[position + 1]
            label = label[:-2] if label.endswith(" *") else label
            return found.group("workflow"), label
    return None


def current_field(state: FlowState) -> WorkflowParameter | None:
    """The field the flow is asking now, None on the card or its menu."""
    return _current(state)


def convert_reply(item: WorkflowParameter, text: str) -> Any:
    """`text` as a value of `item`, as a typed answer is read; None when it
    is not one (the flow then asks the field normally)."""
    try:
        value = _convert(item, text)
    except ValueError:
        return None
    return None if parameter_value_problem(item, value) else value
