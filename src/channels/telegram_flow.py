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
CHECK = "✓ "

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
    index: int = 0
    answers: dict[str, Any] = field(default_factory=dict)
    confirming: bool = False
    started: float = field(default_factory=time.monotonic)
    # Identity values from last time, offered before the first question.
    preset: dict[str, Any] = field(default_factory=dict)
    asking_preset: bool = False
    # Values ticked so far on the current multi-select.
    picked: list[str] = field(default_factory=list)
    # The upload set this flow stores documents in (set by the ingress).
    upload_set: str | None = None
    # Run values given with the request ("run X company=Foxconn", or by the
    # model for its own fields): answered already, never asked, always shown
    # in a confirmation before the run (owner 2026-10-15).
    prefilled: frozenset[str] = frozenset()
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
    manifest: WorkflowManifest, effect: str | None, choices: ChoicesProvider | None = None,
    *, uploads: bool = False, preset: Mapping[str, Any] | None = None,
    prefill: Mapping[str, Any] | None = None,
) -> FlowState | str:
    """A new flow, or why this Workflow cannot be filled in from Telegram.

    `uploads` says the ingress can store documents for `upload` fields; without
    it a required upload is refused and an optional one skipped, as before.
    """
    fields = ordered_fields(manifest, "telegram")
    if not uploads:
        for item in fields:
            if item.kind == "upload" and item.required:
                return (f"{item.label} needs a file upload, which Telegram does not accept "
                        "here; run this Workflow from Agent Web.")
        fields = tuple(item for item in fields if item.kind != "upload")
    shown = {item.name for item in fields}
    given = {name: value for name, value in (prefill or {}).items() if name in shown}
    identity = {item.name for item in fields if item.group == IDENTITY_GROUP}
    remembered = {name: value for name, value in (preset or {}).items()
                  if name in identity and name not in given}
    return FlowState(
        manifest, effect, fields, choices, answers=dict(given),
        preset=remembered, asking_preset=bool(remembered), prefilled=frozenset(given),
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


def _rows(buttons: list[Button]) -> list[list[Button]]:
    return [buttons[i:i + BUTTONS_PER_ROW] for i in range(0, len(buttons), BUTTONS_PER_ROW)]


def _choice_buttons(state: FlowState, item: WorkflowParameter) -> list[list[Button]]:
    if item.kind == "boolean":
        return [[("Yes", "yes"), ("No", "no")]]
    if item.kind == "upload":
        return [[("Done", "/done")]] if item.multiple else []
    listed = _choices(state, item)[:MAX_BUTTONS]
    if not listed:
        return []
    if item.multiple:
        rows = _rows([
            ((CHECK if value in state.picked else "") + label, f"pick:{position}")
            for position, (value, label) in enumerate(listed, start=1)
        ])
        return [*rows, [("Done", "pick:done")]]
    return _rows([
        (label, value if len(value.encode("utf-8")) <= MAX_CALLBACK_BYTES else f"#{position}")
        for position, (value, label) in enumerate(listed, start=1)
    ])


def _preset_prompt(state: FlowState) -> FlowPrompt:
    labels = {item.name: item.label for item in state.fields}
    shown = [f"{_title(state)}: same as last time?"]
    shown.extend(f"- {labels.get(name, name)}: {_shown(value)}"
                 for name, value in state.preset.items())
    return FlowPrompt("\n".join(shown), [[("Yes", "preset:yes"), ("Change", "preset:no")]])


def _shown(value: Any) -> str:
    return ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)


def prompt(state: FlowState) -> FlowPrompt:
    if state.asking_preset:
        return _preset_prompt(state)
    if state.confirming:
        return _confirmation(state)
    item = state.fields[state.index]
    lines = [f"{_title(state)} ({state.index + 1}/{len(state.fields)})", item.label
             + (" *" if item.required else "")]
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
        lines.append("Tap to tick, then Done. You can also type the values, separated "
                     "by commas.")
        if len(listed) > MAX_BUTTONS:
            lines.append("More choices than buttons: " + ", ".join(
                value for value, _ in listed[MAX_BUTTONS:]))
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
    return FlowPrompt("\n".join(lines), _choice_buttons(state, item))


def _confirmation(state: FlowState) -> FlowPrompt:
    shown = [f"Run {_title(state)}" + (f" (effects: {state.effect})" if state.effect else "") + "?"]
    for item in state.fields:
        if item.name in state.answers:
            mark = " (privileged)" if item.confirm else ""
            value = state.answers[item.name]
            if item.kind == "upload":
                files = value if isinstance(value, list) else [value]
                value = [str(path).replace("\\", "/").rsplit("/", 1)[-1] for path in files]
            shown.append(f"- {item.label}{mark}: {_shown(value)}")
    return FlowPrompt("\n".join(shown), [[("Run", "run:yes"), ("Cancel", "run:no")]])


def needs_confirmation(state: FlowState) -> bool:
    """Owner decision 2026-10-05: a run that can change or send something, or
    a privileged field the person set, is confirmed with a tap every time."""
    privileged = any(
        item.confirm and state.answers.get(item.name) not in (None, False, item.default)
        for item in state.fields
    )
    return state.effect != "read" or privileged


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
    if number.isdigit() and 1 <= int(number) <= len(item.choice_values) and (
        position is not None or not item.allow_other
    ):
        return item.choice_values[int(number) - 1]
    if item.allow_other:
        return value
    raise ValueError("choose one of the listed values")


def _next(state: FlowState) -> FlowStep:
    state.index += 1
    state.picked = []
    while state.index < len(state.fields) and _given(state, state.fields[state.index].name):
        state.index += 1
    if state.index < len(state.fields):
        return FlowStep("ask", prompt(state))
    return _finish(state)


def _given(state: FlowState, name: str) -> bool:
    """Answered by last time's values or with the request: not asked."""
    return name in state.answers and (name in state.preset or name in state.prefilled)


def _finish(state: FlowState) -> FlowStep:
    try:
        arguments = validate_run_parameters(state.manifest, state.answers)
    except WorkflowParameterError as error:
        # Ask again from the field the shared rules refused.
        name = str(error).split(" ", 1)[0]
        state.index = next(
            (index for index, item in enumerate(state.fields) if item.name == name), 0
        )
        state.answers.pop(name, None)
        state.picked = []
        reprompt = prompt(state)
        return FlowStep("ask", FlowPrompt(f"{error}.\n\n{reprompt.text}", reprompt.buttons))
    if (needs_confirmation(state) or state.prefilled) and not state.confirming:
        state.confirming = True
        return FlowStep("ask", prompt(state))
    return FlowStep("ready", arguments=arguments)


def begin(state: FlowState) -> FlowStep:
    """The first prompt, or straight to confirmation when nothing is asked."""
    if state.asking_preset:
        return FlowStep("ask", prompt(state))
    state.index = -1
    return _next(state)


def current_upload(state: FlowState) -> WorkflowParameter | None:
    """The upload field the flow is waiting on, if any."""
    if state.asking_preset or state.confirming or state.index >= len(state.fields):
        return None
    item = state.fields[state.index]
    return item if item.kind == "upload" else None


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


def _answer_preset(state: FlowState, reply: str) -> FlowStep:
    lowered = reply.casefold()
    if lowered in ("preset:yes", *_YES):
        state.asking_preset = False
        state.answers.update(state.preset)
        state.index = -1
        return _next(state)
    if lowered in ("preset:no", "change", "改", "修改", *_NO):
        state.asking_preset = False
        state.preset = {}
        return begin(state)
    return _again(state, "Tap Yes or Change.")


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
        state.answers[item.name] = ticked
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


def answer(state: FlowState, text: str) -> FlowStep:
    reply = text.strip()
    if reply.casefold() in ("/cancel", "run:no"):
        return FlowStep("cancelled")
    if state.asking_preset:
        return _answer_preset(state, reply)
    if state.confirming:
        if reply.casefold() in ("run:yes", *_YES):
            state.confirming = False
            arguments = validate_run_parameters(state.manifest, state.answers)
            return FlowStep("ready", arguments=arguments)
        return FlowStep("ask", FlowPrompt("Tap Run or Cancel.\n\n" + prompt(state).text,
                                          prompt(state).buttons))
    item = state.fields[state.index]
    if reply.casefold() == "/skip":
        if item.required:
            return FlowStep("ask", FlowPrompt("This field is required.\n\n" + prompt(state).text,
                                              prompt(state).buttons))
        state.answers.pop(item.name, None)
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
    state.answers[item.name] = value
    return _next(state)
