"""Which BI domains a link can go to, how a person names one, and the AI's suggestion.

A domain is a home (an application or library entry) of a BI vault this PC uses,
keyed `<vault id>:<home>`, shown by its label; a collection bot is bound to one.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aep_bi.cards import vault
from aep_bi.cards.store import BiStoreError


@dataclass(frozen=True)
class Domain:
    key: str
    vault_id: str
    dataset: str
    home: str
    label: str
    vault_title: str = ""
    purpose: str = ""
    types: tuple[str, ...] = field(default=())

    @property
    def short(self) -> str:
        return self.home.rpartition("/")[2]


def key_of(vault_id: str, home: str) -> str:
    return f"{vault_id}:{home}"


def listed(workspace: Path) -> list[Domain]:
    """Every domain of every reachable vault on this PC, in the page's order. Two
    vaults with the same domain label are told apart by the vault's title."""
    found: list[Domain] = []
    for described in vault.listing(workspace):
        vault_id = str(described["id"])
        try:
            profiles = vault.profiles(workspace, vault_id)
        except BiStoreError:
            continue
        types = {
            str(item.get("home")): tuple(sorted((item.get("types") or {}).keys()))
            for item in profiles.get("profiles", [])
        }
        for item in profiles.get("homes", []):
            home = str(item["home"])
            found.append(
                Domain(
                    key=key_of(vault_id, home),
                    vault_id=vault_id,
                    dataset=str(described["dataset"]),
                    home=home,
                    label=str(item.get("label") or home),
                    vault_title=str(described.get("title") or vault_id),
                    purpose=str(described.get("purpose") or ""),
                    types=types.get(home, ()),
                )
            )
    labels = [d.label.casefold() for d in found]
    return [
        replace(d, label=f"{d.vault_title}／{d.label}")
        if labels.count(d.label.casefold()) > 1
        else d
        for d in found
    ]


def _same(text: str) -> str:
    return re.sub(r"[\s_\-／/]+", "", text).casefold()


def resolve(domains: Sequence[Domain], name: str) -> list[Domain]:
    """The domains `name` means: its label, its folder name or its key; a `vault/label`
    form picks one of two vaults' namesakes."""
    wanted = _same(name.lstrip("#"))
    if not wanted:
        return []
    exact = [d for d in domains if wanted in (_same(d.key), _same(d.label))]
    if exact:
        return exact
    return [
        d
        for d in domains
        if wanted in (_same(d.short), _same(d.home), _same(f"{d.vault_id}{d.short}"))
    ]


def by_key(domains: Sequence[Domain], key: str) -> Domain | None:
    return next((d for d in domains if d.key == key), None)


def labels(domains: Sequence[Domain], keys: Sequence[str]) -> str:
    named = [d.label for key in keys if (d := by_key(domains, key)) is not None]
    return "、".join(named) or "（無）"


# -- times -------------------------------------------------------------------------------------


def parse_clock(text: Any) -> str | None:
    """`HH:MM` (24-hour) or None; anything else is refused by the caller."""
    if not isinstance(text, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", text.strip()):
        return None
    return text.strip()


def next_at(clock: str, after: datetime) -> datetime:
    """The next local `HH:MM` after `after` (aware, this PC's time zone)."""
    local = after.astimezone()
    hour, minute = (int(part) for part in clock.split(":"))
    candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate


def last_at(clock: str, before: datetime) -> datetime:
    """The latest local `HH:MM` at or before `before`."""
    local = before.astimezone()
    hour, minute = (int(part) for part in clock.split(":"))
    candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate > local:
        candidate -= timedelta(days=1)
    return candidate


def when(clock: str | None, now: datetime) -> str:
    """「今天 07:30」 / 「明天 07:30」 for a domain's next collect time."""
    if clock is None:
        return "尚未設定處理時間"
    at = next_at(clock, now)
    day = (at.date() - now.astimezone().date()).days
    return ("今天 " if day == 0 else "明天 " if day == 1 else at.strftime("%m-%d ")) + clock


def as_map(domains: Sequence[Domain]) -> Mapping[str, Domain]:
    return {d.key: d for d in domains}
