"""Save a chat chart as a vault analysis (BI C3), for `propose_change`.

`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` C3. The chat model
proposes `propose_change` kind `bi_analysis`; `host_runtime.change_proposals`
keeps the card, the fingerprint and the owner's Apply, and asks this module
what is current (`now`), what the card shows (`plan`) and what Apply does
(`apply`). The plan runs the SQL on the vault's working data and checks the
chart; Apply stages `analysis:<slug>` with `analyses.save`. Commit, push and
publish stay the person's. SQL only: a saved SQL analysis may be copied, a
script never comes from the chat.

Kind `bi_analysis_edit` (BI P1, `docs/phases/BI_CHAT_EMBED_AND_PANEL_EDIT.md`)
changes a saved analysis: only the fields given change, the card shows each one
before and after, and a script the chat wrote runs only after Apply.
"""

from __future__ import annotations

import difflib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from aep_bi.cards import analyses, board, vault
from aep_bi.cards.store import VAULT_PREFIX, BiStoreError

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
#: What an edit may change, by alias; the rest of the analysis stays.
EDIT_FIELDS = {
    "vault": "vault",
    "dataset": "vault",
    "slug": "slug",
    "title": "title",
    "question": "question",
    "chart": "chart",
    "sql": "sql",
    "script": "script",
    "params": "params",
    "requires": "requires",
}
#: A card's cell and its preview (`common.action_cards`).
CELL = 400
PREVIEW = 20_000
#: The card's words for an analysis's fields; `code` says SQL or Script.
LABELS = {
    "title": "Title",
    "question": "Question",
    "kind": "Kind",
    "chart": "Chart",
    "params": "Parameters",
    "requires": "Requires",
}
NOT_RUN = "Not run yet: the script runs when you press Apply"
STAGED_ONLY = (
    "Only staged in this PC's working copy of the knowledge base; commit, push and "
    "publish on the Knowledge page make it visible to others and to Atlas."
)


class Refused(Exception):
    """Why the proposal cannot be made; said to the model."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class Planned:
    title: str
    values: dict[str, Any]
    #: (label, now, after), each cell clipped to the card's.
    rows: list[tuple[str, str, str]]
    effects: list[str] = field(default_factory=list)
    #: The whole code, which a cell may have clipped.
    preview: str = ""


def _clip(text: str, limit: int = CELL) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _brief(table: Mapping[str, Any]) -> str:
    first = "; ".join(
        ", ".join("" if v is None else str(v) for v in row) for row in table["rows"][:3]
    )
    return f"{len(table['rows'])} rows" + (f": {first}" if first else "")


def _code_diff(before: str, after: str) -> str:
    lines = difflib.unified_diff(
        before.splitlines(), after.splitlines(), "now", "after", lineterm=""
    )
    return _clip("\n".join(lines), PREVIEW)


def _readable_vault(snapshot: Mapping[str, Any]) -> str:
    vault_id = snapshot.get("vault")
    if vault_id is None:
        raise Refused(
            "No such knowledge base (vault) on this PC; use a vault-<id> dataset that "
            "bi__query lists."
        )
    if not snapshot.get("readable"):
        raise Refused("That knowledge base cannot be read now; nothing can change.")
    return str(vault_id)


def _ran(workspace: Path, vault_id: str, value: Mapping[str, Any]) -> dict[str, Any]:
    """One version's result with its default parameters."""
    defaults = analyses.default_params(
        value, analyses._registry(workspace, vault_id), date.today().isoformat()
    )
    table: dict[str, Any] = analyses.run(
        analyses._db(workspace, vault_id), str(value["kind"]), str(value["code"]), defaults
    )
    return table


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
    vault_id = _readable_vault(snapshot)
    slug = str(given.get("slug") or "")
    if snapshot.get("unit") is not None:
        raise Refused(
            f"The knowledge base already has an analysis {slug!r}; choose a new slug, or "
            "change it with kind bi_analysis_edit."
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
    return Planned(
        title=f"Save the chart as the analysis “{value['title']}”",
        values={"vault": vault_id, "slug": slug, "analysis": {**value, "slug": slug}},
        rows=[
            ("Knowledge base", "", str(vault_id)),
            ("Analysis", "", _clip(f"{value['title']} ({slug})")),
            ("Chart", "", _clip(_cell(chart))),
            ("SQL", "", _clip(value["code"])),
            ("Result on the working copy", "", _clip(_brief(table))),
        ],
        effects=[STAGED_ONLY],
        preview=_clip(value["code"], PREVIEW) if len(value["code"]) > CELL else "",
    )


def plan_edit(workspace: Path, given: Mapping[str, Any], snapshot: Mapping[str, Any]) -> Planned:
    vault_id = _readable_vault(snapshot)
    slug = str(given.get("slug") or "")
    unit = snapshot.get("unit")
    if not isinstance(unit, Mapping):
        raise Refused(
            f"The knowledge base has no analysis {slug!r} to change; a new one is kind bi_analysis."
        )
    sql, script = given.get("sql"), given.get("script")
    if sql and script:
        raise Refused("Give either sql or script, not both.")
    edited: dict[str, Any] = {**unit, "slug": slug}
    for key in ("title", "question", "params", "requires"):
        if given.get(key) is not None:
            edited[key] = given[key]
    # Only what changes, also inside the chart: `{"type": "line"}` keeps its x and y.
    # A table has no axes, so it inherits none.
    chart = given.get("chart")
    if isinstance(chart, Mapping):
        merged = {**(unit.get("chart") or {}), **chart}
        edited["chart"] = dict(chart) if merged.get("type") == "table" else merged
    elif chart is not None:
        edited["chart"] = chart
    if sql:
        edited |= {"kind": "sql", "code": str(sql)}
    elif script:
        edited |= {"kind": "python", "code": str(script)}
    try:
        _key, value = analyses.checked(edited)
    except BiStoreError as error:
        raise Refused(error.message) from None
    changed = analyses.changes(unit, value)
    if not changed:
        raise Refused(f"That changes nothing in {slug!r}; give the values that should change.")
    try:
        was = _brief(_ran(workspace, vault_id, unit))
    except BiStoreError as error:
        was = f"Does not run now: {error.message}"
    new_script = value["kind"] == "python" and (unit.get("kind"), unit.get("code")) != (
        value["kind"],
        value["code"],
    )
    if new_script:
        # A script from the chat runs only after the owner's press.
        try:
            analyses.default_params(
                value, analyses._registry(workspace, vault_id), date.today().isoformat()
            )
        except BiStoreError as error:
            raise Refused(error.message) from None
        will = NOT_RUN
    else:
        try:
            table = _ran(workspace, vault_id, value)
            analyses.checked_chart(value["chart"], table["columns"])
        except BiStoreError as error:
            raise Refused(error.message) from None
        will = _brief(table)
    code_label = "Script" if value["kind"] == "python" else "SQL"
    rows = [
        (
            code_label if item["field"] == "code" else LABELS[item["field"]],
            _clip(_cell(item["before"])),
            _clip(_cell(item["after"])),
        )
        for item in changed
    ]
    return Planned(
        title=f"Change the analysis “{value['title']}” ({slug})",
        values={"vault": vault_id, "slug": slug, "analysis": {**value, "slug": slug}},
        rows=[
            ("Knowledge base", str(vault_id), str(vault_id)),
            *rows,
            ("Result on the working copy", _clip(was), _clip(will)),
        ],
        effects=[STAGED_ONLY],
        preview=(
            _code_diff(str(unit.get("code") or ""), value["code"])
            if any(item["field"] == "code" for item in changed)
            else ""
        ),
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
