"""Migration adapter: an existing vault's Raw is adopted by content hash
without a byte changing, its sources pages gain typed provenance with a
backup, drift is reported, and the generated half can be snapshotted and
restored."""

from datetime import date
from pathlib import Path

import pytest
from test_raw import make_vault

from knowledge.lint import scan
from knowledge.migrate import (
    AdoptedRaw,
    AdoptionReport,
    DriftedRaw,
    SkippedRaw,
    UnresolvedPage,
    adopt,
    legacy_raw,
    restore,
    snapshot,
    snapshots,
    source_for_legacy,
)
from knowledge.planning import source_text
from knowledge.query import retrieve
from knowledge.raw import DropIntake, PlainTextExtractor, RawIndex, load_document
from knowledge.vault import Vault, VaultError

TODAY = date(2026, 9, 21)


def legacy_vault(vault: Vault) -> None:
    root = vault.root
    (root / "raw" / "Study").mkdir(parents=True)
    (root / "raw" / "Study" / "openhands.md").write_text(
        "# OpenHands\n\nAn agent framework with a runtime sandbox.\n", encoding="utf-8"
    )
    (root / "raw" / "Study" / "moved.md").write_bytes(b"moved elsewhere later\r\n")
    (root / "raw" / "Study" / "big5.md").write_bytes("舊筆記\n".encode("cp950"))
    (root / "raw" / "Study" / "empty.md").write_bytes(b"\n\n")
    (root / "wiki" / "sources").mkdir(parents=True)
    (root / "wiki" / "entities").mkdir(parents=True)
    (root / "wiki" / "sources" / "OpenHands SDK.md").write_bytes(
        b"---\r\ntitle: OpenHands SDK\r\ntype: source\r\n"
        b"source_path: raw/Study/openhands.md\r\n---\r\nSummary of the framework.\r\n"
    )
    (root / "wiki" / "sources" / "Stale.md").write_text(
        "---\ntitle: Stale\ntype: source\nsource_path: raw/Old/gone.md\n---\nbody\n",
        encoding="utf-8",
    )
    (root / "wiki" / "sources" / "Unclosed.md").write_text(
        "---\ntitle: Unclosed\nsource_path: raw/Study/moved.md\nno closing fence\n",
        encoding="utf-8",
    )
    (root / "wiki" / "entities" / "OpenHands.md").write_text(
        "---\ntitle: OpenHands\ntype: entity\n---\nSee [[OpenHands SDK]].\n", encoding="utf-8"
    )
    (root / "index.md").write_text("# Index\n\n## Sources\n- [[OpenHands SDK]]\n", encoding="utf-8")


def raw_bytes(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in (root / "raw").rglob("*") if p.is_file()}


def test_legacy_raw_is_adopted_by_content_without_a_byte_changing(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    legacy_vault(vault)
    before = raw_bytes(tmp_path)
    assert legacy_raw(vault) == (
        "raw/Study/big5.md",
        "raw/Study/empty.md",
        "raw/Study/moved.md",
        "raw/Study/openhands.md",
    )
    assert RawIndex.scan(vault).entries == []
    assert scan(vault).pending_sources == ()  # unknown to the index, so not pending yet

    preview = adopt(vault, today=TODAY, stamp="a1")
    assert preview.mode == "dry_run" and preview.snapshot is None
    assert [a.raw_ref for a in preview.raw_adopted] == [
        "raw/Study/moved.md",
        "raw/Study/openhands.md",
    ]
    assert preview.raw_skipped == (
        SkippedRaw(raw_ref="raw/Study/big5.md", reason="undecodable"),
        SkippedRaw(raw_ref="raw/Study/empty.md", reason="empty"),
    )
    assert [m.page for m in preview.pages_migrated] == ["wiki/sources/OpenHands SDK.md"]
    assert preview.pages_unresolved == (
        UnresolvedPage(page="wiki/sources/Stale.md", source_path="raw/Old/gone.md"),
    )
    assert preview.pages_skipped == ("wiki/sources/Unclosed.md",)
    assert preview.written == ("wiki/sources/OpenHands SDK.md", ".ingest-adopted.json")
    assert not (tmp_path / ".ingest-adopted.json").exists() and snapshots(vault) == ()
    assert "source_id" not in vault.read("wiki/sources/OpenHands SDK.md")
    assert raw_bytes(tmp_path) == before

    report = adopt(vault, mode="apply", today=TODAY, stamp="a1")
    assert report.snapshot == "a1-before-adopt" and snapshots(vault) == ("a1-before-adopt",)
    assert report.raw_adopted == preview.raw_adopted and report.written == preview.written
    expected = source_for_legacy(
        "raw/Study/openhands.md", before[tmp_path / "raw" / "Study" / "openhands.md"]
    )
    assert report.raw_adopted[1] == AdoptedRaw(raw_ref="raw/Study/openhands.md", source=expected)
    page = (tmp_path / "wiki" / "sources" / "OpenHands SDK.md").read_bytes()
    assert (
        f"source_path: raw/Study/openhands.md\r\nsource_id: {expected.source_id}\r\n"
        f"source_sha256: {expected.sha256}\r\n---\r\n"
    ).encode() in page
    assert b"\n" not in page.replace(b"\r\n", b"")  # the page keeps its line endings
    assert (tmp_path / ".ingest-backup" / "a1" / "wiki" / "sources" / "OpenHands SDK.md").exists()
    assert raw_bytes(tmp_path) == before

    # Adopted Raw is now a source for the index, the lint, planning and query.
    index = RawIndex.scan(vault)
    assert {e.raw_ref for e in index.entries} == {"raw/Study/moved.md", "raw/Study/openhands.md"}
    assert all(e.adopted and e.created == TODAY for e in index.entries)
    assert RawIndex.scan(vault, ledger=False).entries == []
    lint = scan(vault)
    assert lint.pending_sources == ("raw/Study/moved.md",)
    assert lint.unknown_source_id == ()
    assert [b.page for b in lint.broken_source_path] == ["wiki/sources/Stale.md"]
    hit = retrieve(vault, "runtime sandbox", k=1)[0]
    assert hit.citation.kind == "raw" and hit.citation.source == expected
    assert hit.citation.section == 2 and hit.citation.page is None
    document = load_document(vault, index.entries[1])
    assert document.extractor == "adopted.v1" and len(document.sections) == 2
    assert source_text(document).startswith("# OpenHands")
    assert load_document(vault, index.entries[0]).sections[0].text == "moved elsewhere later"

    # Adopting again changes nothing and snapshots nothing.
    again = adopt(vault, mode="apply", today=TODAY, stamp="a2")
    assert again.raw_adopted == () and again.pages_migrated == () and again.written == ()
    assert again.snapshot is None and snapshots(vault) == ("a1-before-adopt",)
    assert again.pages_unresolved == preview.pages_unresolved

    # A legacy file that changed since is drift: out of the index, reported,
    # and adopted again only by name.
    (tmp_path / "raw" / "Study" / "moved.md").write_text("edited by hand\n", encoding="utf-8")
    third = adopt(vault, today=TODAY, stamp="a3")
    (drift,) = third.raw_drifted
    assert isinstance(drift, DriftedRaw) and drift.raw_ref == "raw/Study/moved.md"
    assert drift.recorded_sha256 != drift.current_sha256
    assert third.raw_adopted == () and third.written == ()
    assert {e.raw_ref for e in RawIndex.scan(vault).entries} == {"raw/Study/openhands.md"}
    fourth = adopt(vault, mode="apply", today=TODAY, stamp="a4", readopt=["raw/Study/moved.md"])
    assert [r.raw_ref for r in fourth.raw_readopted] == ["raw/Study/moved.md"]
    assert fourth.raw_drifted == () and fourth.written == (".ingest-adopted.json",)
    assert fourth.snapshot == "a4-before-adopt"
    assert {e.raw_ref for e in RawIndex.scan(vault).entries} == {
        "raw/Study/moved.md",
        "raw/Study/openhands.md",
    }
    assert AdoptionReport.model_validate_json(fourth.model_dump_json()) == fourth
    with pytest.raises(ValueError, match="precedes an apply"):
        AdoptionReport(mode="dry_run", snapshot="x")


def test_ingested_and_adopted_raw_coexist(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    legacy_vault(vault)
    intake = DropIntake(vault, [PlainTextExtractor()])
    (tmp_path / "drop" / "new.txt").write_bytes(b"new source")
    intake.intake("drop/new.txt", mode="apply", today=TODAY)
    (tmp_path / "wiki" / "sources" / "New.md").write_text(
        "---\ntitle: New\nsource_path: raw/new.md\n---\nAbout the new source.\n", encoding="utf-8"
    )
    report = adopt(vault, mode="apply", today=TODAY, stamp="a1")
    assert [m.page for m in report.pages_migrated] == [
        "wiki/sources/New.md",
        "wiki/sources/OpenHands SDK.md",
    ]
    assert report.pages_migrated[0].source.original_ref == "drop/new.txt"
    index = RawIndex.scan(vault)
    assert {e.raw_ref: e.adopted for e in index.entries} == {
        "raw/new.md": False,
        "raw/Study/moved.md": True,
        "raw/Study/openhands.md": True,
    }
    assert index.by_content(source_for_legacy("x", b"new source").sha256) is not None
    assert scan(vault).pending_sources == ("raw/Study/moved.md",)
    # A corrupt ledger is a first run for the index, never a failure.
    (tmp_path / ".ingest-adopted.json").write_text("{not json", encoding="utf-8")
    assert [e.raw_ref for e in RawIndex.scan(vault).entries] == ["raw/new.md"]
    (tmp_path / ".ingest-adopted.json").write_text(
        '{"raw/Study/openhands.md": {"sha256": 5}, "raw/Study/moved.md": "x"}', encoding="utf-8"
    )
    assert [e.raw_ref for e in RawIndex.scan(vault).entries] == ["raw/new.md"]


def test_snapshots_cover_the_generated_half_and_restore_is_undoable(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    legacy_vault(vault)
    vault.ledger_write({"raw/Study/openhands.md": {"sha256": "0" * 64}})
    name = snapshot(vault, stamp="s1", label="clean")
    assert name == "s1-clean" and snapshots(vault) == ("s1-clean",)
    kept_dir = tmp_path / ".ingest-snapshot" / "s1-clean"
    assert (kept_dir / "wiki" / "entities" / "OpenHands.md").exists()
    assert (kept_dir / ".ingest-adopted.json").exists() and (kept_dir / "index.md").exists()
    assert not (kept_dir / "raw").exists() and not (kept_dir / "drop").exists()
    with pytest.raises(VaultError, match="write_failed"):
        snapshot(vault, stamp="s1", label="clean")
    with pytest.raises(ValueError, match="single path component"):
        snapshot(vault, stamp="../x")

    (tmp_path / "wiki" / "entities" / "OpenHands.md").write_text("ruined\n", encoding="utf-8")
    (tmp_path / "wiki" / "entities" / "Extra.md").write_text("extra\n", encoding="utf-8")
    (tmp_path / "index.md").write_text("ruined index\n", encoding="utf-8")
    (tmp_path / ".ingest-adopted.json").unlink()
    (tmp_path / "raw" / "Study" / "openhands.md").write_text("raw stays\n", encoding="utf-8")
    kept = restore(vault, "s1-clean", stamp="s2")
    assert kept == "s2-before-restore" and snapshots(vault) == ("s1-clean", "s2-before-restore")
    assert vault.read("wiki/entities/OpenHands.md").endswith("See [[OpenHands SDK]].\n")
    assert not (tmp_path / "wiki" / "entities" / "Extra.md").exists()
    assert vault.read("index.md").startswith("# Index")
    assert vault.ledger_read() == {"raw/Study/openhands.md": {"sha256": "0" * 64}}
    assert vault.read("raw/Study/openhands.md") == "raw stays\n"  # never part of a snapshot
    assert (
        tmp_path / ".ingest-snapshot" / "s2-before-restore" / "wiki" / "entities" / "Extra.md"
    ).exists()
    assert not (
        tmp_path / ".ingest-snapshot" / "s2-before-restore" / ".ingest-adopted.json"
    ).exists()
    with pytest.raises(VaultError, match="missing_original"):
        restore(vault, "nope", stamp="s3")
    with pytest.raises(ValueError, match="single path component"):
        restore(vault, "../../etc", stamp="s3")
