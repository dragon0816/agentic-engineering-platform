"""A card in a conversation that waits for a person's button (owner 2026-10-15).

One component for every "the Agent asks, the person decides" moment:

- a change proposal (`docs/phases/AI_PROPOSED_CHANGES.md`): a before -> after
  table, the reason, the effects, **Apply** / **Cancel**;
- agent mode (`docs/phases/AGENT_MODE_BACKENDS.md`): a write, a command or an
  email, with a preview body and **Allow** / **Allow for this conversation** /
  **Deny** or **Send** / **Keep as draft** / **Cancel**.

The server keeps the pending record (status, expiry) and decides; a card is
only its picture. Agent Web draws it with one renderer (`renderActionCard` in
`web_page.py`), Telegram with `telegram_card` below. A button's `action` is
what the server is told; its label is what the person reads.

This module is pure: contracts, the Telegram text and the lookup of a card in
a conversation turn's tool results.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from common.base import Contract, Symbol, Text

#: The host tool data key a card travels under; the Gateway ends the turn on it.
CARD_KEY = "action_card"
#: A card id: a two-letter kind prefix and twelve hex digits (`cp-…` proposals).
CARD_ID = r"[a-z]{2}-[0-9a-f]{12}"
#: The callback data of a Telegram card button: `card:<id>:<action>` (≤ 64 bytes).
CARD_TAP = re.compile(rf"^card:({CARD_ID}):([a-z_]{{1,24}})$")
#: Statuses in which the buttons still act.
OPEN_STATUSES = frozenset({"pending"})


class CardButton(Contract):
    """One button. `action` is sent to the server; `label` is shown."""

    action: str = Field(pattern=r"^[a-z_]{1,24}$")
    label: Text = Field(max_length=60)
    style: Literal["primary", "secondary", "danger"] = "secondary"


class CardRow(Contract):
    """One line of the before -> after table: only fields that change."""

    label: Text = Field(max_length=120)
    before: str = Field(default="", max_length=400)
    after: str = Field(default="", max_length=400)


class CardLink(Contract):
    """Where the matching page or card is in Agent Web."""

    label: Text = Field(max_length=120)
    # A primary tab: settings, installed (Capabilities), tasks.
    view: Literal["settings", "installed", "tasks"]
    # An element id on that tab to scroll to (a Settings card's form).
    anchor: str = Field(default="", max_length=80, pattern=r"^[a-z0-9-]*$")
    # A Capabilities entry to open: `skills` or `workflows`, and `ns/name@version`.
    capability_kind: Literal["", "skills", "workflows"] = ""
    asset: str = Field(default="", max_length=200)


class ActionCard(Contract):
    """What a person sees and presses. Never carries a secret value."""

    card_id: str = Field(pattern=rf"^{CARD_ID}$")
    # Which server-side handler decides it: `change_proposal`, later
    # `permission` or `email_send`.
    kind: Symbol
    title: Text = Field(max_length=160)
    rows: tuple[CardRow, ...] = Field(default=(), max_length=40)
    # A body shown as written: a command line, a file diff, an email.
    preview: str = Field(default="", max_length=20_000)
    reason: str = Field(default="", max_length=1_000)
    effects: tuple[Text, ...] = Field(default=(), max_length=10)
    buttons: tuple[CardButton, ...] = Field(default=(), max_length=4)
    status: Symbol = "pending"
    # A short word for the status, shown on the card: "Waiting", "Applied".
    status_label: str = Field(default="", max_length=200)
    # The result in place after a decision (the writer's own message).
    outcome: str = Field(default="", max_length=2_000)
    outcome_ok: bool | None = None
    link: CardLink | None = None
    expires_at: datetime | None = None
    # Decided only in Agent Web: Telegram shows the card and says where.
    web_only: bool = False
    # The answer text of the turn that showed the card.
    message: Text = Field(max_length=600)

    @model_validator(mode="after")
    def distinct_actions(self) -> Self:
        actions = [button.action for button in self.buttons]
        if len(actions) != len(set(actions)):
            raise ValueError("each button of a card names its own action")
        return self

    @property
    def open(self) -> bool:
        return self.status in OPEN_STATUSES


def card_in(tools: Iterable[Any]) -> dict[str, Any] | None:
    """The last card among a conversation turn's tool executions."""
    found: dict[str, Any] | None = None
    for item in tools:
        host = getattr(item, "host", None)
        data = getattr(host, "data", None) if host is not None else None
        if isinstance(data, dict) and isinstance(data.get(CARD_KEY), dict):
            found = data[CARD_KEY]
    return found


def telegram_card(
    card: ActionCard, web_address: str = ""
) -> tuple[str, tuple[tuple[tuple[str, str], ...], ...]]:
    """The card as Telegram text and its inline buttons (one row).

    A card only Agent Web may decide shows no buttons and says where to go;
    a closed card shows its outcome instead of buttons."""
    lines = [card.title]
    for row in card.rows:
        lines.append(f"• {row.label}: {row.before or '(empty)'} → {row.after or '(empty)'}")
    if card.preview:
        lines.extend(("", card.preview))
    if card.reason:
        lines.extend(("", f"Why: {card.reason}"))
    lines.extend(f"⚠ {effect}" for effect in card.effects)
    buttons: tuple[tuple[tuple[str, str], ...], ...] = ()
    if not card.open:
        mark = "✅" if card.outcome_ok else "⛔" if card.outcome_ok is False else "•"
        lines.extend(("", f"{mark} {card.status_label or card.status}"
                      + (f": {card.outcome}" if card.outcome else "")))
    elif card.web_only:
        where = f": {web_address}" if web_address else "."
        lines.extend(("", "Open in Agent Web to apply" + where))
    else:
        buttons = (tuple((button.label, f"card:{card.card_id}:{button.action}")
                         for button in card.buttons),)
    return "\n".join(lines), buttons
