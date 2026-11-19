"""Which BI domains a link can go to, how a person names one, and the AI's suggestion.

A domain is a home (an application or library entry) of a BI vault this PC uses,
keyed `<vault id>:<home>`, shown by its label. The suggestion compares a link's title
and summary with each domain's label, folder, the vault's purpose and the card types
of the domain's profile; without a model there is no suggestion (owner 2026-11-19).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aep_bi.cards import vault
from aep_bi.cards.store import BiStoreError
from common.execution import TraceIdentifiers
from models.contracts import ModelClient, ModelMessage, ModelRequest

#: A suggestion at least this sure is used for an item nobody tapped (owner 2026-11-19).
CONFIDENT = 0.7


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


# -- the AI's suggestion ---------------------------------------------------------------------


def _described(domains: Sequence[Domain]) -> str:
    return "\n".join(
        f"{index}. {d.label}（資料夾 {d.home}；知識庫：{d.vault_title} {d.purpose}".rstrip()
        + (f"；卡片類型：{'、'.join(d.types)}" if d.types else "")
        + "）"
        for index, d in enumerate(domains, start=1)
    )


def suggest(
    model: tuple[ModelClient, str] | None,
    domains: Sequence[Domain],
    title: str,
    summary: str,
) -> tuple[str | None, float]:
    """(domain key, confidence 0..1) for a link, or (None, 0) without a model, without
    domains or when the answer cannot be read. One short model call."""
    if model is None or not domains or not (title or summary).strip():
        return None, 0.0
    client, alias = model
    prompt = (
        "把一則分享的資訊歸到最適合的 BI 領域。只回 JSON："
        '{"domain": <編號或 0 表示都不適合>, "confidence": <0 到 1>}。\n\n'
        f"領域：\n{_described(domains)}\n\n"
        f"標題：{title[:300]}\n摘要：{summary[:800]}"
    )
    try:
        response = client.generate(
            ModelRequest(
                trace=TraceIdentifiers(
                    trace_id="bi-inbox-suggest", request_id="bi-inbox-suggest", span_id="suggest"
                ),
                model_alias=alias,
                messages=(ModelMessage(role="user", text=prompt),),
                max_output_tokens=60,
            )
        )
    except Exception:  # noqa: BLE001 - no suggestion is a fine answer
        return None, 0.0
    if response.failure is not None:
        return None, 0.0
    found = re.search(r"\{.*?\}", response.text or "", re.DOTALL)
    try:
        answer: Any = json.loads(found.group(0)) if found else None
        number = int(answer["domain"])
        confidence = max(0.0, min(1.0, float(answer.get("confidence", 0))))
    except (ValueError, TypeError, KeyError, AttributeError):
        return None, 0.0
    if not 1 <= number <= len(domains):
        return None, 0.0
    return domains[number - 1].key, confidence


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


def model_of(host: Any) -> Callable[[], tuple[ModelClient, str] | None]:
    """This host's model for BI (as AI runs use it); none without Agent Web."""
    if host is None:
        return lambda: None
    from aep_bi.host.bi_cards_api import web_ai_runtime

    ai = web_ai_runtime(host)
    return ai.model


def as_map(domains: Sequence[Domain]) -> Mapping[str, Domain]:
    return {d.key: d for d in domains}
