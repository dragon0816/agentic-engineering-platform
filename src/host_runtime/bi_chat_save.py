"""Save a chat chart as a vault analysis (BI C3), for `propose_change`.

`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` C3. The chat model
proposes `propose_change` kind `bi_analysis`; `host_runtime.change_proposals`
keeps the card, the fingerprint and the owner's Apply, and asks this module
what is current (`now`), what the card shows (`plan`) and what Apply does
(`apply`). The plan runs the SQL on the vault's working data and checks the
chart; Apply stages `analysis:<slug>` with `analyses.save`. Commit, push and
publish stay the person's. SQL only: a saved SQL analysis may be copied, a
script never comes from the chat.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from capabilities.bi_cards import analyses, board, vault
from capabilities.bi_cards.store import VAULT_PREFIX, BiStoreError

#: The values the model may give, by alias.
FIELDS = {
    "vault": "vault",
    "dataset": "vault",
    "slug": "slug",
    "title": "title",
    "question": "question",
    "chart": "chart",
    "sql": "sql",
    "from_analysis": "from_analysis",
}


class Refused(Exception):
    """Why the proposal cannot be made; said to the model."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class Planned:
    title: str
    values: dict[str, Any]
    rows: list[tuple[str, str]]
    effects: list[str] = field(default_factory=list)


def vault_id_of(given: Any) -> str:
    """A vault's id from `vault-<id>` or the id itself."""
    text = str(given or "").strip()
    return text[len(VAULT_PREFIX) :] if text.startswith(VAULT_PREFIX) else text


def now(workspace: Path, values: Mapping[str, Any]) -> dict[str, Any]:
    """Whether the vault is on this PC and what its working copy holds under
    the slug (a save meanwhile makes the card stale)."""
    vault_id = vault_id_of(values.get("vault") or values.get("dataset"))
    slug = str(values.get("slug") or "")
    if not vault_id or vault.registry_entry(workspace, vault_id) is None:
        return {"vault": None}
    try:
        units = vault.Vault(workspace, vault_id).repo.working_units()
    except Exception:  # noqa: BLE001 - an unreadable vault cannot be changed
        return {"vault": vault_id, "readable": False}
    return {"vault": vault_id, "readable": True, "unit": units.get(analyses.PREFIX + slug)}


def plan(workspace: Path, given: Mapping[str, Any], snapshot: Mapping[str, Any]) -> Planned:
    vault_id = snapshot.get("vault")
    if vault_id is None:
        raise Refused(
            "No such knowledge base (vault) on this PC; use a vault-<id> dataset that "
            "bi__query lists."
        )
    if not snapshot.get("readable"):
        raise Refused("That knowledge base cannot be read now; nothing can change.")
    slug = str(given.get("slug") or "")
    if snapshot.get("unit") is not None:
        raise Refused(
            f"The knowledge base already has an analysis {slug!r}; choose a new slug, or "
            "change that analysis with the analysis AI on the Knowledge page."
        )
    sql, source = given.get("sql"), given.get("from_analysis")
    if bool(sql) == bool(source):
        raise Refused("Give either sql or from_analysis {vault, slug}, one of them.")
    analysis: dict[str, Any] = {
        "slug": slug,
        "title": given.get("title"),
        "question": given.get("question") or "",
        "chart": given.get("chart") or {"type": "table"},
        "kind": "sql",
    }
    if source:
        if not isinstance(source, Mapping):
            raise Refused("from_analysis is {vault, slug}.")
        found = board.published_analysis(
            workspace, vault_id_of(source.get("vault")), str(source.get("slug") or "")
        )
        if found is None:
            raise Refused("That knowledge base's published version has no such analysis.")
        if found.get("kind") != "sql":
            raise Refused(
                "Only a SQL analysis is saved from the chat; copy a script analysis with an "
                "analysis pack on the Knowledge page."
            )
        analysis["code"] = found["code"]
        for key in ("params", "requires"):
            if found.get(key):
                analysis[key] = found[key]
    else:
        analysis["code"] = str(sql)
    try:
        _key, value = analyses.checked(analysis)
        defaults = analyses.default_params(
            value, analyses._registry(workspace, vault_id), date.today().isoformat()
        )
        table = analyses.run_sql(analyses._db(workspace, vault_id), value["code"], params=defaults)
        chart = analyses.checked_chart(value["chart"], table["columns"])
    except BiStoreError as error:
        raise Refused(error.message) from None
    first = "; ".join(
        ", ".join("" if v is None else str(v) for v in row) for row in table["rows"][:3]
    )
    return Planned(
        title=f"Save the chart as the analysis “{value['title']}”",
        values={"vault": vault_id, "slug": slug, "analysis": {**value, "slug": slug}},
        rows=[
            ("Knowledge base", str(vault_id)),
            ("Analysis", f"{value['title']} ({slug})"),
            ("Chart", json.dumps(chart, ensure_ascii=False)),
            ("SQL", value["code"]),
            (
                "Result on the working copy",
                f"{len(table['rows'])} rows" + (f": {first}" if first else ""),
            ),
        ],
        effects=[
            "Only staged in this PC's working copy of the knowledge base; commit, push and "
            "publish on the Knowledge page make it visible to others and to Atlas."
        ],
    )


def apply(workspace: Path, values: Mapping[str, Any]) -> tuple[bool, str]:
    given = values.get("analysis")
    if not isinstance(given, dict):
        return False, "The proposal holds no analysis."
    try:
        saved = analyses.save(workspace, str(values["vault"]), given)
    except BiStoreError as error:
        return False, error.message
    return True, (
        f"Staged {saved['unit']} in {values['vault']}; commit, push and publish it on the "
        "Knowledge page."
    )
