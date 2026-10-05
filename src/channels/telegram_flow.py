"""A Telegram question flow generated from a Workflow's parameter declaration.

rs_workflow_system's bot asked a workflow's fields one at a time from its
`PARAMS_SCHEMA` (`telegram_pack.questions_from_schema`). This is the same
idea over AEP's `WorkflowParameter`: the fields shown on the `telegram`
channel, in form order, each converted from a reply or a button tap and
checked by the shared field rules. The flow is pure state; the ingress
sends its prompts and runs the Workflow once the person confirms.
"""

from __future__ import annotations

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
from common.workflow_forms import ordered_fields
from common.workflow_parameters import WorkflowParameterError, validate_run_parameters

FLOW_TTL_SECONDS = 15 * 60
BUTTONS_PER_ROW = 3
MAX_BUTTONS = 24
_YES = {"yes", "y", "true", "1", "是", "對", "好", "確認"}
_NO = {"no", "n", "false", "0", "否", "不", "不要", "取消"}
_SPLIT = re.compile(r"[\n,，、;；]+")

Button = tuple[str, str]


@dataclass
class FlowPrompt:
    text: str
    buttons: list[list[Button]] = field(default_factory=list)


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
) -> FlowState | str:
    """A new flow, or why this Workflow cannot be filled in from Telegram."""
    fields = ordered_fields(manifest, "telegram")
    for item in fields:
        if item.kind == "upload" and item.required:
            return (f"{item.label} needs a file upload, which Telegram does not accept here; "
                    "run this Workflow from Agent Web.")
    # Optional uploads are skipped: attachments are not accepted on this channel.
    return FlowState(
        manifest, effect, tuple(item for item in fields if item.kind != "upload"), choices,
    )


def _title(state: FlowState) -> str:
    return state.manifest.metadata.identity.name


def _dynamic_values(state: FlowState, item: WorkflowParameter) -> list[str] | None:
    source = item.choices_source
    if not source or state.choices is None:
        return None
    return state.choices(state.manifest, source, state.answers)


def _choice_buttons(state: FlowState, item: WorkflowParameter) -> list[list[Button]]:
    if item.kind == "boolean":
        return [[("Yes", "yes"), ("No", "no")]]
    dynamic = _dynamic_values(state, item)
    if item.kind == "select" and dynamic and not item.multiple:
        buttons = [(value, value) for value in dynamic[:MAX_BUTTONS]]
        return [buttons[i:i + BUTTONS_PER_ROW] for i in range(0, len(buttons), BUTTONS_PER_ROW)]
    if item.kind != "select" or item.choices_source or item.multiple:
        return []
    labels = {choice.value: (choice.label or choice.value) for choice in item.choices}
    values = item.choice_values[:MAX_BUTTONS]
    buttons = [(labels.get(value, value), value) for value in values]
    return [buttons[i:i + BUTTONS_PER_ROW] for i in range(0, len(buttons), BUTTONS_PER_ROW)]


def prompt(state: FlowState) -> FlowPrompt:
    if state.confirming:
        return _confirmation(state)
    item = state.fields[state.index]
    lines = [f"{_title(state)} ({state.index + 1}/{len(state.fields)})", item.label
             + (" *" if item.required else "")]
    if item.help or item.description:
        lines.append(item.help or item.description or "")
    if item.kind in ("text_list", "emails") or item.multiple:
        lines.append("Several values: separate them with commas or new lines.")
    if item.kind == "select" and (item.choices_source or item.multiple) and item.choice_values:
        lines.append("Choices: " + ", ".join(item.choice_values))
    if item.choices_source:
        dynamic = _dynamic_values(state, item)
        if dynamic is None:
            lines.append("Its choice list is not available yet; type the value.")
        elif item.multiple and dynamic:
            lines.append("Choices: " + ", ".join(dynamic[:MAX_BUTTONS]))
    if item.default is not None:
        lines.append(f"Default: {item.default}")
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
            shown.append(f"- {item.label}{mark}: {state.answers[item.name]}")
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
    """A declared or published value, its label, or its 1-based position."""
    if dynamic is not None:
        if value in dynamic:
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
    if value.isdigit() and 1 <= int(value) <= len(item.choice_values):
        return item.choice_values[int(value) - 1]
    raise ValueError("choose one of the listed values")


def _next(state: FlowState) -> FlowStep:
    state.index += 1
    if state.index < len(state.fields):
        return FlowStep("ask", prompt(state))
    return _finish(state)


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
        reprompt = prompt(state)
        return FlowStep("ask", FlowPrompt(f"{error}.\n\n{reprompt.text}", reprompt.buttons))
    if needs_confirmation(state) and not state.confirming:
        state.confirming = True
        return FlowStep("ask", prompt(state))
    return FlowStep("ready", arguments=arguments)


def begin(state: FlowState) -> FlowStep:
    """The first prompt, or straight to confirmation when nothing is asked."""
    if state.fields:
        return FlowStep("ask", prompt(state))
    return _finish(state)


def answer(state: FlowState, text: str) -> FlowStep:
    reply = text.strip()
    if reply.casefold() in ("/cancel", "run:no"):
        return FlowStep("cancelled")
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
        return _next(state)
    try:
        value = _convert(item, reply, _dynamic_values(state, item))
    except ValueError as error:
        problem: str | None = str(error)
    else:
        problem = parameter_value_problem(item, value)
    if problem:
        again = prompt(state)
        message = f"{item.label} {problem}.\n\n{again.text}"
        return FlowStep("ask", FlowPrompt(message, again.buttons))
    state.answers[item.name] = value
    return _next(state)
