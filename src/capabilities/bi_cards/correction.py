"""A correction note (更正單): how a person changes one value on a card.

Design: `docs/phases/BI_CARD_MODEL.md` §5.2. A note is a small Markdown source with
frontmatter, read by the same reader as a card page and with no model, so it works
with no gateway. It goes source → preview → confirm → commit: `preview` writes
nothing, and `apply` keeps the note as a source and writes the value as `human`,
with the note's line as its evidence. Direct edits of a card are gone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from capabilities.bi_cards import vault, vault_skills
from capabilities.bi_cards.catalog import for_store
from capabilities.bi_cards.page_import import MAX_EXCERPT, Page, parse_page
from capabilities.bi_cards.schema import FieldDef, Registry
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore, BiStoreError, now
from knowledge.repo import repository as repo_engine

METHOD_REF = "correction-note"
#: For a card in no home yet. Shaped like any library entry (design §4).
NO_HOME_FOLDER = "library/corrections/sources"
#: Refusals of what the note says, as opposed to the card it names.
BAD_NOTE = frozenset(
    {
        "note_invalid",
        "type_unknown",
        "field_unknown",
        "field_derived",
        "base_version_missing",
        "reason_required",
        "value_invalid",
    }
)


@dataclass(frozen=True)
class Note:
    card_id: str
    field: str
    value: Any
    reason: str
    author: str
    page: Page


def _line(key: str, value: Any) -> str:
    """One frontmatter line: JSON, so any text stays on it and reads back the same.
    `splitlines` also breaks where JSON does not escape, so these are escaped here."""
    text = json.dumps(value, ensure_ascii=False)
    for char in ("\x85", " ", " "):
        text = text.replace(char, f"\\u{ord(char):04x}")
    return f"{key}: {text}"


def render(card: Any, field: str, value: Any, reason: str, author: str, at: str) -> str:
    """The note `read` reads back."""
    return "\n".join(
        [
            "---",
            _line("card", card["id"]),
            _line("field", field),
            _line("value", value),
            _line("reason", reason),
            _line("author", author),
            _line("at", at),
            "---",
            "",
            f"# 更正單：{card['entity_type']}「{card['name']}」的 {field}",
            "",
            *reason.splitlines(),
            "",
        ]
    )


def _given(page: Page, key: str) -> Any:
    """What `key` says, with the JSON form `render` writes read exactly; a note
    written by hand reads as a card page does."""
    written = page.raw.get(key, "").partition(":")[2].strip()
    if written.startswith(('"', "[")):
        try:
            return json.loads(written)
        except ValueError:
            pass
    return page.values.get(key)


def read(text: Any) -> Note:
    """Read a note. Text with no such frontmatter is an ordinary source, not a note."""
    page = parse_page("note.md", text if isinstance(text, str) else "")
    if page.problems:
        raise BiStoreError("note_invalid", page.problems[0]["message"])
    card_id, field = _given(page, "card"), _given(page, "field")
    if not isinstance(card_id, str) or not card_id or not isinstance(field, str) or not field:
        raise BiStoreError("note_invalid", "更正單的 frontmatter 要有 card 和 field")
    if "value" not in page.raw:
        raise BiStoreError("note_invalid", "更正單要寫 value")
    return Note(
        card_id=card_id,
        field=field,
        value=_given(page, "value"),
        reason=str(_given(page, "reason") or "").strip(),
        author=str(_given(page, "author") or "").strip(),
        page=page,
    )


def _list_value(reg: Registry, item: FieldDef, raw: list[Any]) -> list[str] | None:
    """A list's items, stripped; a domain item in its canonical spelling (as an
    import stores it), so the same domains in other case or an alias compare equal.
    An item the schema does not know is kept as typed."""
    values: list[str] = []
    for given in raw:
        text = str(given).strip()
        if not text:
            continue
        if item.name == "domain":
            known, _ = reg.normalize(item, text)
            if isinstance(known, list) and len(known) == 1:
                text = str(known[0])
        if text not in values or item.name != "domain":
            values.append(text)
    return values or None


def checked_field(reg: Registry, entity_type: str, name: str) -> FieldDef:
    """A field a person may change on a card of this type."""
    try:
        entity = reg.type(entity_type)
    except KeyError:
        raise BiStoreError("type_unknown", f"schema 沒有類型 {entity_type}") from None
    item = entity.get(name)
    if item is None:
        raise BiStoreError("field_unknown", f"{entity.name} 沒有欄位 {name}")
    if item.klass == "derived":
        raise BiStoreError("field_derived", f"{item.label} 是推導欄位，不能直接修改")
    return item


def checked_value(reg: Registry, item: FieldDef, raw: Any) -> Any:
    """`raw` normalised like an import cell; empty clears the field."""
    if raw is None or raw == "" or raw == []:
        return None
    if isinstance(raw, list):
        if not item.is_list:
            raise BiStoreError("value_invalid", f"{item.label} 不是清單欄位")
        if not item.enum:
            return _list_value(reg, item, raw)
        # A list with allowed values (BI vault V9) takes only those values.
        value, problems = reg.normalize(item, "；".join(str(x) for x in raw))
        if problems:
            raise BiStoreError("value_invalid", problems[0][1])
        return value
    value, problems = reg.normalize(item, str(raw))
    if value is None:
        message = problems[0][1] if problems else f"{item.label} 的值無法採用"
        raise BiStoreError("value_invalid", message)
    return value


def _checked(store: BiStore, note: Note, base: Any) -> tuple[Any, FieldDef, Any, int]:
    """The card, the field, the value and the base version, or why this note cannot
    be taken."""
    card = store.card(note.card_id)
    if card is None:
        raise BiStoreError("card_unknown", "找不到這張卡片")
    reg = for_store(store)
    item = checked_field(reg, card["entity_type"], note.field)
    if not isinstance(base, int):
        raise BiStoreError("base_version_missing", "需要 base_version")
    if not note.reason:
        raise BiStoreError("reason_required", "更正單必須寫理由")
    return card, item, checked_value(reg, item, note.value), base


def _current(store: BiStore, card_id: str, field: str) -> Any:
    stored = store.fields(card_id).get(field)
    return None if stored is None else stored["value"]


def note_folder(store: BiStore, card_id: str) -> str:
    """The `sources/` of the card's first home, or the shared one for a card with none."""
    home = store.first_home(card_id)
    if home is None:
        return NO_HOME_FOLDER
    return f"{home}/sources" if home.startswith("library/") else f"applications/{home}/sources"


def preview(store: BiStore, given: dict[str, Any], *, actor: str) -> dict[str, Any]:
    """What this note would change; writes nothing. It comes as the form's parts, or
    as the text of a note someone wrote."""
    store.refuse_write()
    text = given.get("text")
    if not isinstance(text, str):
        named = store.card(str(given.get("card") or ""))
        if named is None:
            raise BiStoreError("card_unknown", "找不到這張卡片")
        text = render(
            named,
            str(given.get("field") or ""),
            given.get("value"),
            str(given.get("reason") or "").strip(),
            str(given.get("author") or "").strip() or actor,
            now(),
        )
    note = read(text)
    card, item, value, base = _checked(store, note, given.get("base_version"))
    store.refuse_moved(card["id"], note.field, base)
    current = _current(store, card["id"], note.field)
    return {
        "card": card["id"],
        "name": card["name"],
        "field": note.field,
        "label": item.label,
        "current": current,
        "value": value,
        "reason": note.reason,
        "author": note.author,
        "unchanged": current == value,
        "base_version": base,
        "folder": note_folder(store, card["id"]),
        "text": text,
    }


def apply(store: BiStore, given: dict[str, Any], *, actor: str) -> dict[str, Any]:
    """The person confirmed the note: keep it as a source and write its value, in one
    commit with the note's reason as its purpose."""
    store.refuse_write()
    text = given.get("text")
    note = read(text)
    card, _, value, base = _checked(store, note, given.get("base_version"))
    store.refuse_moved(card["id"], note.field, base)
    if _current(store, card["id"], note.field) == value:
        # The value it already has (owner 2026-10-24): no source, no version, no history.
        return {"version": base, "unchanged": True}
    staging = Staging(store.workspace, store.dataset)
    stamp = now().replace(":", "").replace("-", "")
    source = staging.add_source(
        f"correction-{card['id']}-{note.field}-{stamp}.md",
        text=text,
        folder=_stored_folder(store, card["id"]),
        media_type="text/markdown",
        actor=actor,
    )
    run_id = staging.create_run(
        kind="ingest",
        method_ref=METHOD_REF,
        schema_ref=for_store(store).ref,
        model=None,
        source_ids=[source["id"]],
        actor=actor,
    )
    evidence = {
        "source_id": source["id"],
        "source_name": source["name"],
        "locator": {"line": note.page.lines.get("value"), "key": "value"},
        "excerpt": note.page.raw.get("value", "")[:MAX_EXCERPT],
        "basis": "human",
    }
    purpose = f"更正 {card['entity_type']}「{card['name']}」的 {note.field}：{note.reason}"
    with vault.purpose(purpose[: repo_engine.MAX_PURPOSE]):
        version, import_id = store.correct(
            card["id"],
            note.field,
            value,
            base_version=base,
            actor=actor,
            reason=note.reason,
            ref=source["name"],
            run_id=run_id,
            evidence=evidence,
        )
    staging.set_status(
        run_id,
        "committed",
        commit_result={"import_id": import_id, "created": 0, "updated": 1},
    )
    return {"version": version, "source": source["id"], "import_id": import_id}


def _stored_folder(store: BiStore, card_id: str) -> str | None:
    """Where the note goes in a vault. The default `sources/` until this PC's engine
    takes the folder layout (design §4)."""
    try:
        return vault_skills.checked_folder(note_folder(store, card_id))
    except BiStoreError:
        return None
