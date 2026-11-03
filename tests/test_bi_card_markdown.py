"""What a publish writes to the shared folder: read-only card pages and a snapshot
(`docs/phases/BI_CARD_MODEL.md` §6). Temp folders only; fictional data."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from test_bi_vault import _call, _commit, _Drive, _ok, _push, _row, _sync, _two_pcs

from capabilities.bi_cards import card_markdown, vault, vault_sources
from capabilities.bi_cards.store import BiStore


def _publish(ws: Path, vault_id: str, tag: str) -> dict[str, Any]:
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": tag, "purpose": tag}))
    return _ok(
        _call(ws, "POST", f"/api/bi/vaults/{vault_id}/publish", {"tag": tag, "confirm": True})
    )


def _shared(tmp_path: Path) -> tuple[_Drive, str, str, Path, Path, Path]:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    BiStore(a, dataset).apply(
        [_row("TSN", standard_body="IEEE"), _row("EtherCAT", standard_body="ETG")],
        filename="t.csv",
        entity_type="Technology",
        actor="x via web",
    )
    _push(a, vault_id)
    return drive, vault_id, dataset, a, b, drive.parent("a") / vault_id


def _card_id(ws: Path, dataset: str, key: str) -> str:
    card = BiStore(ws, dataset).find("Technology", key)
    assert card is not None
    return str(card["id"])


def _page(folder: Path, card_id: str) -> str:
    return (folder / "cards" / f"{card_id}.md").read_text(encoding="utf-8")


def test_a_publish_writes_every_card_page_and_the_manifest(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _, folder = _shared(tmp_path)
    answer = _publish(a, vault_id, "v1")
    assert answer["cards"]["behind"] is False and answer["cards"]["written"] == 2
    tsn = _card_id(a, dataset, "TSN")
    page = _page(folder, tsn)
    assert page.startswith(f"---\nid: {tsn}\n") and "generated: true" in page
    assert "# TSN" in page and "IEEE" in page and "請勿編輯" in page
    manifest = json.loads((folder / "cards" / "_manifest.json").read_text(encoding="utf-8"))
    assert manifest["tag"] == "v1" and manifest["commit"] == answer["published"]["commit"]
    assert manifest["by"] == "alice" and set(manifest["hashes"]) == {
        tsn,
        _card_id(a, dataset, "EtherCAT"),
    }
    assert manifest["hashes"][tsn] == hashlib.sha256(page.encode("utf-8")).hexdigest()


def test_only_changed_pages_are_written_and_a_removed_card_goes(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _, folder = _shared(tmp_path)
    _publish(a, vault_id, "v1")
    tsn, ether = _card_id(a, dataset, "TSN"), _card_id(a, dataset, "EtherCAT")
    untouched = (folder / "cards" / f"{ether}.md").stat().st_mtime_ns
    store = BiStore(a, dataset)
    card = store.card(tsn)
    assert card is not None
    store.set_field(tsn, "standard_body", "IETF", base_version=card["version"], actor="a via web")
    _commit(a, vault_id, "改")
    _push(a, vault_id)
    answer = _publish(a, vault_id, "v2")
    assert answer["cards"]["written"] == 1 and answer["cards"]["removed"] == 0
    assert "IETF" in _page(folder, tsn)
    assert (folder / "cards" / f"{ether}.md").stat().st_mtime_ns == untouched
    # A page nobody needs any more is deleted; a page that went missing comes back.
    (folder / "cards" / f"{tsn}.md").unlink()
    stray = folder / "cards" / "_manifest.json"
    record = json.loads(stray.read_text(encoding="utf-8"))
    record["hashes"]["gonecard"] = "x"
    stray.write_text(json.dumps(record), encoding="utf-8")
    (folder / "cards" / "gonecard.md").write_text("old", encoding="utf-8")
    again = vault.Vault(a, vault_id).write_cards()
    assert again["removed"] == 1 and again["written"] == 1
    assert not (folder / "cards" / "gonecard.md").exists()
    assert (folder / "cards" / f"{tsn}.md").is_file()


def test_a_repeat_with_nothing_changed_writes_nothing(tmp_path: Path) -> None:
    _, vault_id, _, a, _, folder = _shared(tmp_path)
    _publish(a, vault_id, "v1")
    manifest = (folder / "cards" / "_manifest.json").read_bytes()
    again = vault.Vault(a, vault_id).write_cards()
    assert (again["written"], again["removed"], again["unchanged"]) == (0, 0, 2)
    assert (folder / "cards" / "_manifest.json").read_bytes() == manifest


def test_the_pages_are_the_same_from_either_pc(tmp_path: Path) -> None:
    """Pure: the same version gives the same bytes, so a second publisher writes nothing."""
    drive, vault_id, dataset, a, b, folder = _shared(tmp_path)
    _publish(a, vault_id, "v1")
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    answer = vault.Vault(b, vault_id).write_cards()
    assert answer["written"] == 0 and answer["unchanged"] == 2
    other = drive.parent("b") / vault_id
    tsn = _card_id(a, dataset, "TSN")
    assert _page(other, tsn) == _page(folder, tsn)


def test_a_slower_publisher_cannot_put_an_older_view_back(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b, folder = _shared(tmp_path)
    _publish(a, vault_id, "v1")
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    store = BiStore(a, dataset)
    tsn = _card_id(a, dataset, "TSN")
    card = store.card(tsn)
    assert card is not None
    store.set_field(tsn, "standard_body", "IETF", base_version=card["version"], actor="a via web")
    _commit(a, vault_id, "改")
    _push(a, vault_id)
    _publish(a, vault_id, "v2")
    # b writes again, having seen only v1: its folder keeps the v1 it knows, and once
    # v2 arrives it renders v2, whichever order the publishes were made in.
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert vault.Vault(b, vault_id).write_cards()["behind"] is False
    assert "IETF" in _page(drive.parent("b") / vault_id, tsn)


def test_a_failed_view_does_not_undo_the_publish(tmp_path: Path, monkeypatch: Any) -> None:
    _, vault_id, _, a, _, _ = _shared(tmp_path)

    def broken(*_: Any, **__: Any) -> dict[str, str]:
        raise OSError("disk")

    monkeypatch.setattr(card_markdown, "render_all", broken)
    answer = _publish(a, vault_id, "v1")
    assert answer["cards"]["behind"] is True and answer["published"]["tag"] == "v1"
    assert vault.status(a, vault_id)["reads"]["tag"] == "v1"
    assert vault.status(a, vault_id)["cards_view_behind"] is True
    monkeypatch.undo()
    assert vault.Vault(a, vault_id).write_cards()["written"] == 2
    assert vault.status(a, vault_id)["cards_view_behind"] is False


def test_the_snapshot_is_written_once_with_its_hash_in_the_record(tmp_path: Path) -> None:
    _, vault_id, _, a, _, folder = _shared(tmp_path)
    record = _publish(a, vault_id, "v1")["published"]
    snapshot = folder / "published" / "v1.sqlite"
    first = snapshot.read_bytes()
    assert record["snapshot"] == {
        "path": "published/v1.sqlite",
        "sha256": hashlib.sha256(first).hexdigest(),
    }
    with sqlite3.connect(snapshot) as db:
        assert db.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 2
    assert not [p for p in (folder / "published").iterdir() if p.name != "v1.sqlite"]
    # A second publish of the tag keeps the first.
    again = _ok(
        _call(a, "POST", f"/api/bi/vaults/{vault_id}/publish", {"tag": "v1", "confirm": True})
    )
    assert snapshot.read_bytes() == first
    assert again["published"]["snapshot"] == record["snapshot"]


def test_a_withdrawn_sources_excerpt_leaves_the_pages_at_once(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _, folder = _shared(tmp_path)
    body = {"dataset": dataset, "name": "fict.md", "text": "機密段落 SECRET-EXCERPT"}
    source = _ok(_call(a, "POST", "/api/bi/sources", body))["source"]["id"]
    _commit(a, vault_id, "來源")
    tsn = _card_id(a, dataset, "TSN")
    with sqlite3.connect(BiStore(a, dataset).path) as db:
        before = db.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    assert before == 2
    _push(a, vault_id)
    # The page's rendering is pure: given the withdrawn id, the excerpt is blank.
    item = {
        "field": "standard_body",
        "source_id": source,
        "source_name": "fict.md",
        "locator": "{}",
        "excerpt": "SECRET-EXCERPT",
    }
    card = dict(BiStore(a, dataset).card(tsn) or {})
    reg = vault.Vault(a, vault_id)._registry()
    shown = card_markdown.render_card(
        card, reg, fields={}, states={}, evidence=[item], relations=[], aliases=[], names={}
    )
    assert "SECRET-EXCERPT" in shown
    hidden = card_markdown.render_card(
        card,
        reg,
        fields={},
        states={},
        evidence=[item],
        relations=[],
        aliases=[],
        names={},
        withdrawn={source},
    )
    assert "SECRET-EXCERPT" not in hidden and "fict.md" in hidden
    _publish(a, vault_id, "v1")
    _ok(
        _call(
            a,
            "POST",
            f"/api/bi/vaults/{vault_id}/withdraw-source",
            {"source_id": source, "confirm": True, "reason": "不該放"},
        )
    )
    assert vault_sources.withdrawn_shas(vault.Vault(a, vault_id).repo)
    assert "SECRET-EXCERPT" not in _page(folder, tsn)


def test_a_page_shows_states_relations_aliases_and_the_sample_mark(tmp_path: Path) -> None:
    _, vault_id, _, a, _, _ = _shared(tmp_path)
    reg = vault.Vault(a, vault_id)._registry()
    card = {
        "id": "c1",
        "entity_type": "Technology",
        "canonical_key": "TSN",
        "name": "TSN",
        "synthetic": 1,
        "created": "2026-01-01",
        "updated": "2026-01-02",
    }
    page = card_markdown.render_card(
        card,
        reg,
        fields={"summary": "摘要文字", "standard_body": "IEEE"},
        states={"maturity": {"state": "not_applicable", "reason": "不適用這類"}},
        evidence=[],
        relations=[
            {
                "from_card_id": "c1",
                "to_card_id": "c2",
                "relation_type": "has_supplier",
                "status": "unreviewed",
            },
            {
                "from_card_id": "c3",
                "to_card_id": "c1",
                "relation_type": "uses",
                "status": "confirmed",
            },
            {
                "from_card_id": "c1",
                "to_card_id": "c4",
                "relation_type": "wrong",
                "status": "rejected",
            },
        ],
        aliases=["舊名"],
        names={"c2": "甲公司", "c3": "乙產品", "c4": "丙"},
    )
    assert 'aliases:\n  - "舊名"' in page and "sample: true" in page and "樣本資料" in page
    assert "## 摘要\n\n摘要文字" in page
    assert "（不適用：不適用這類）" in page
    assert "- has_supplier：[[c2|甲公司]]" in page
    assert "- ← uses：[[c3|乙產品]]（confirmed）" in page
    assert "丙" not in page
    assert "建立" in page and "2026-01-02" in page
