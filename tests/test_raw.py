"""Drop → Raw: content identity, write-once Raw, and a Markdown form that
round-trips its provenance and section relationships."""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from knowledge.contracts import KnowledgeSource
from knowledge.raw import (
    DropIntake,
    ExtractionError,
    IntakeOutcome,
    MarkdownExtractor,
    PlainTextExtractor,
    RawDocument,
    RawSection,
    StagedAssets,
    assets_dir_for,
    parse,
    raw_index,
    render,
    source_for,
)
from knowledge.vault import Vault, VaultError

TODAY = date(2026, 9, 21)


def make_vault(root: Path) -> Vault:
    for name in ("drop", "raw", "wiki"):
        (root / name).mkdir()
    (root / "index.md").write_text("# Index\n", encoding="utf-8")
    (root / "log.md").write_text("# Log\n", encoding="utf-8")
    return Vault(root)


def intake_for(vault: Vault) -> DropIntake:
    return DropIntake(vault, [PlainTextExtractor(), MarkdownExtractor()])


def drop(vault: Vault, rel: str, data: bytes) -> str:
    path = vault.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return rel


def document(**changes: Any) -> RawDocument:
    source = source_for(b"hello", "drop/notes/hello.txt").model_copy(
        update={"raw_ref": "raw/notes/hello.md"}
    )
    data: dict[str, Any] = {
        "source": source,
        "extractor": "plain-text.v1",
        "created": TODAY,
        "sections": (RawSection(text="hello"),),
    }
    data.update(changes)
    return RawDocument.model_validate(data)


def test_identity_follows_content_not_path() -> None:
    one = source_for(b"same bytes", "drop/a.txt")
    two = source_for(b"same bytes", "drop/deep/b.txt")
    assert one.sha256 == two.sha256 and one.source_id == two.source_id
    assert one.original_ref == "drop/a.txt" and two.original_ref == "drop/deep/b.txt"
    assert source_for(b"other", "drop/a.txt").source_id != one.source_id
    assert source_for(b"x", "\\drop\\a.txt").original_ref == "drop/a.txt"


def test_section_and_document_contracts_refuse_the_wrong_shape() -> None:
    assert RawSection(text="\n\nbody\n").text == "body"
    with pytest.raises(ValidationError, match="exactly an image section"):
        RawSection(kind="image")
    with pytest.raises(ValidationError, match="exactly an image section"):
        RawSection(text="x", image_ref="raw/a/assets/p.png")
    with pytest.raises(ValidationError, match="carries text"):
        RawSection(kind="table", text="  ")
    with pytest.raises(ValidationError, match="lives under raw/"):
        RawSection(kind="image", image_ref="drop/p.png")
    with pytest.raises(ValidationError, match="no whitespace"):
        RawSection(kind="image", image_ref="raw/a/assets/fig 1.png")
    assert RawSection(kind="image", image_ref="raw\\a\\p.png").image_ref == "raw/a/p.png"
    with pytest.raises(ValidationError, match="supersede itself"):
        document(supersedes=document().source.source_id)
    with pytest.raises(ValidationError, match="raw_ref under raw/"):
        document(source=source_for(b"hello", "drop/hello.txt"))
    with pytest.raises(ValidationError, match="no page or slide"):
        document(source=document().source.model_copy(update={"page": 2}))
    with pytest.raises(ValidationError):
        document(sections=())


def test_raw_markdown_round_trips_every_relationship() -> None:
    doc = document(
        extractor="office.v1",
        sections=(
            RawSection(text="Intro paragraph.\n\nSecond paragraph.", page=1),
            RawSection(kind="table", text="| a | b |\n|---|---|\n| 1 | 2 |", page=2),
            RawSection(kind="image", image_ref="raw/notes/assets/fig1.png", page=2),
            RawSection(
                kind="image",
                text="A chart of throughput by channel.",
                image_ref="raw/notes/assets/fig2.png",
                slide=7,
            ),
            RawSection(text="Closing remarks with a `---` inside a sentence.", slide=8),
        ),
    )
    text = render(doc)
    assert text.startswith(
        "---\nsource_id: src-2cf24dba5fb0a30e\n"
        "source_sha256: 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824\n"
        "original_ref: drop/notes/hello.txt\nraw_ref: raw/notes/hello.md\n"
        "extractor: office.v1\ncreated: 2026-09-21\n---\n"
    )
    assert "<!-- raw-section 3 kind=image page=2 image=raw/notes/assets/fig1.png -->" in text
    assert "<!-- raw-section 4 kind=image slide=7 image=raw/notes/assets/fig2.png -->" in text
    assert parse(text) == doc
    assert render(parse(text)) == text


def test_parse_refuses_what_is_not_a_raw_document() -> None:
    good = render(document())
    for bad, why in (
        ("# just markdown\n", "well-formed frontmatter"),
        ("---\nsource_id: x\n", "well-formed frontmatter"),
        ("---\nnot a field\n---\n", "well-formed frontmatter"),
        ("---\nsource_id: src-1\n---\n", "missing"),
        (good.replace("raw-section 1", "raw-section 2"), "numbered in order"),
        (good.replace("---\n\n<!--", "---\nstray text\n<!--"), "before the first section"),
    ):
        with pytest.raises(ValueError, match=why):
            parse(bad)


def test_extractors_decode_and_strip_only_what_they_must() -> None:
    sink = StagedAssets("raw/x/assets")
    plain = PlainTextExtractor()
    assert plain.extract(b"  hello\n\n", sink) == (RawSection(text="  hello"),)
    assert plain.extract(b"   \n", sink) == ()
    with pytest.raises(ExtractionError) as raised:
        plain.extract(b"\xff\xfe", sink)
    assert raised.value.code == "undecodable"
    markdown = MarkdownExtractor()
    assert markdown.extract(b"---\ntitle: T\n---\n# Heading\n\nbody\n", sink) == (
        RawSection(text="# Heading\n\nbody"),
    )
    assert markdown.extract(b"---\nno end\nbody\n", sink) == (RawSection(text="---\nno end\nbody"),)
    assert markdown.extract(b"---\ntitle: T\n---\n\n", sink) == ()
    assert sink.items == {}
    # Assets are named by content under the document's own directory.
    ref = sink.put(b"\x89PNG...", "PNG")
    assert (
        ref.startswith("raw/x/assets/")
        and ref.endswith(".png")
        and sink.put(b"\x89PNG...", ".png") == ref
    )
    assert assets_dir_for("raw/notes/hello--abcd1234.md") == "raw/notes/hello--abcd1234/assets"


def test_intake_writes_once_and_reports_exactly_what_it_would(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    intake = intake_for(vault)
    drop(vault, "drop/notes/hello.txt", b"hello world\n")
    preview = intake.intake("drop/notes/hello.txt", today=TODAY)
    assert preview.mode == "dry_run" and preview.status == "written"
    assert preview.raw_ref == "raw/notes/hello.md" and preview.written == ("raw/notes/hello.md",)
    assert not (tmp_path / "raw" / "notes").exists()

    outcome = intake.intake("drop/notes/hello.txt", mode="apply", today=TODAY)
    assert outcome.model_dump(exclude={"mode"}) == preview.model_dump(exclude={"mode"})
    stored = parse(vault.read("raw/notes/hello.md"))
    assert stored.source == outcome.source and stored.sections == (RawSection(text="hello world"),)
    assert stored.extractor == "plain-text.v1" and stored.created == TODAY
    assert (tmp_path / "drop" / "notes" / "hello.txt").read_bytes() == b"hello world\n"

    # The same content again, from anywhere, is the same source and nothing is written.
    drop(vault, "drop/copies/hello-again.txt", b"hello world\n")
    again = intake.intake("drop/copies/hello-again.txt", mode="apply", today=TODAY)
    assert again.status == "duplicate" and again.written == ()
    assert again.raw_ref == "raw/notes/hello.md" and again.source == outcome.source
    assert vault.raw_files() == ("raw/notes/hello.md",)


def test_a_changed_original_is_drift_and_the_old_raw_stays(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    intake = intake_for(vault)
    drop(vault, "drop/report.md", b"# v1\n")
    first = intake.intake("drop/report.md", mode="apply", today=TODAY)
    drop(vault, "drop/report.md", b"# v2\n")
    second = intake.intake("drop/report.md", mode="apply", today=TODAY)
    assert second.status == "drifted" and second.supersedes == first.source
    assert second.source is not None and second.source.sha256 != first.source.sha256  # type: ignore[union-attr]
    assert second.raw_ref == f"raw/report--{second.source.sha256[:8]}.md"
    assert parse(vault.read("raw/report.md")).sections == (RawSection(text="# v1"),)
    assert parse(vault.read(second.raw_ref)).sections == (RawSection(text="# v2"),)
    assert {e.raw_ref for e in raw_index(vault)} == {"raw/report.md", second.raw_ref}
    # Dropping v1 again anywhere is a duplicate of the first raw, not new drift.
    drop(vault, "drop/old/report.md", b"# v1\n")
    assert intake.intake("drop/old/report.md", today=TODAY).status == "duplicate"


def test_intake_refuses_or_reports_what_it_cannot_take(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    intake = intake_for(vault)
    drop(vault, "drop/slides.pptx", b"PK\x03\x04")
    drop(vault, "drop/binary.txt", b"\xff\xfe\x00")
    drop(vault, "drop/blank.txt", b"\n\n")
    (tmp_path / "raw" / "note.txt").write_bytes(b"in raw")
    assert intake.intake("drop/slides.pptx", mode="apply").status == "unsupported"
    assert intake.intake("drop/binary.txt", mode="apply").status == "undecodable"
    assert intake.intake("drop/blank.txt", mode="apply").status == "empty"
    for rel, code in (
        ("raw/note.txt", "outside_drop"),
        ("drop/../raw/note.txt", "escapes_vault"),
        ("drop/nope.txt", "missing_original"),
        ("drop", "outside_drop"),
    ):
        with pytest.raises(VaultError) as raised:
            intake.intake(rel, mode="apply")
        assert raised.value.code == code, rel
    assert vault.raw_files() == ()


def test_raw_is_written_once_and_only_by_the_intake_path(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    vault.write_raw("raw/a.md", "x")
    with pytest.raises(VaultError, match="raw_exists"):
        vault.write_raw("raw/a.md", "y")
    assert vault.read("raw/a.md") == "x"
    for rel, code in (
        ("wiki/a.md", "outside_raw"),
        ("drop/a.md", "outside_raw"),
        ("raw/../escaped.md", "escapes_vault"),
    ):
        with pytest.raises(VaultError) as raised:
            vault.write_raw(rel, "x")
        assert raised.value.code == code
    with pytest.raises(VaultError, match="immutable_area"):
        vault.write("raw/b.md", "x", stamp="s")
    assert vault.raw_files() == ("raw/a.md",)


def test_the_index_skips_raw_files_without_provenance(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    (tmp_path / "raw" / "legacy.md").write_text("# an existing vault page\n", encoding="utf-8")
    (tmp_path / "raw" / "half.md").write_text("---\nsource_id: only\n---\n", encoding="utf-8")
    (tmp_path / "raw" / "bad.md").write_text(
        "---\nsource_id: x\nsource_sha256: nothex\noriginal_ref: drop/x\n---\n", encoding="utf-8"
    )
    (tmp_path / "raw" / "assets").mkdir()
    (tmp_path / "raw" / "assets" / "note.md").write_text(render(document()), encoding="utf-8")
    assert raw_index(vault) == ()
    intake_for(vault).intake(drop(vault, "drop/new.txt", b"fresh"), mode="apply", today=TODAY)
    (entry,) = raw_index(vault)
    assert entry.raw_ref == "raw/new.md" and entry.source.original_ref == "drop/new.txt"
    assert (tmp_path / "raw" / "legacy.md").read_text(
        encoding="utf-8"
    ) == "# an existing vault page\n"


def test_outcomes_are_honest_about_their_status() -> None:
    src = source_for(b"x", "drop/x.txt").model_copy(update={"raw_ref": "raw/x.md"})
    with pytest.raises(ValidationError, match="lists writes"):
        IntakeOutcome(
            mode="apply",
            status="written",
            original_ref="drop/x.txt",
            source=src,
            raw_ref="raw/x.md",
        )
    with pytest.raises(ValidationError, match="supersedes"):
        IntakeOutcome(
            mode="apply",
            status="drifted",
            original_ref="drop/x.txt",
            source=src,
            raw_ref="raw/x.md",
            written=("raw/x.md",),
        )
    with pytest.raises(ValidationError, match="raw_ref belongs"):
        IntakeOutcome(
            mode="apply", status="unsupported", original_ref="drop/x.txt", raw_ref="raw/x.md"
        )
    with pytest.raises(ValidationError, match="names its source"):
        IntakeOutcome(
            mode="apply", status="duplicate", original_ref="drop/x.txt", raw_ref="raw/x.md"
        )
    ok = IntakeOutcome(mode="dry_run", status="empty", original_ref="drop/x.txt")
    assert IntakeOutcome.model_validate_json(ok.model_dump_json()) == ok
    assert isinstance(src, KnowledgeSource)


def test_any_text_is_representable_and_line_endings_are_one(tmp_path: Path) -> None:
    tricky = (
        "see <!-- raw-section 1 kind=text --> in docs\n"
        "<!-- raw-section 1 kind=text -->\n"
        "\\<!-- raw-section 2 kind=text -->\n"
        "---\na: b\n---\nhorizontal rules too\r\nand CRLF\r\nand a \x0c form feed here"
    )
    doc = document(sections=(RawSection(text=tricky), RawSection(text="\r\nsecond\r\n", page=2)))
    assert doc.sections[0].text == tricky.replace("\r\n", "\n")
    assert doc.sections[1].text == "second"
    text = render(doc)
    assert "\n\\<!-- raw-section 1 kind=text -->\n\\\\<!-- raw-section 2" in text
    assert parse(text) == doc and render(parse(text)) == text
    # Through the vault and back, on any platform, byte for byte.
    vault = make_vault(tmp_path)
    vault.write_raw("raw/tricky.md", text)
    assert (tmp_path / "raw" / "tricky.md").read_bytes() == text.encode("utf-8")
    assert parse(vault.read("raw/tricky.md")) == doc
    # A CRLF original is stored with one line ending and no doubled blank lines.
    intake = intake_for(vault)
    drop(vault, "drop/win.txt", b"line one\r\nline two\r\n")
    intake.intake("drop/win.txt", mode="apply", today=TODAY)
    assert parse(vault.read("raw/win.md")).sections == (RawSection(text="line one\nline two"),)
    drop(vault, "drop/marker.txt", b"see <!-- raw-section note")
    assert intake.intake("drop/marker.txt", mode="apply", today=TODAY).status == "written"


def test_equivalent_drop_paths_are_one_identity(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    intake = intake_for(vault)
    drop(vault, "drop/d.txt", b"v1")
    first = intake.intake("drop/./d.txt", mode="apply", today=TODAY)
    assert first.original_ref == "drop/d.txt" and first.raw_ref == "raw/d.md"
    drop(vault, "drop/d.txt", b"v2")
    second = intake.intake("drop//d.txt", mode="apply", today=TODAY)
    assert second.status == "drifted" and second.supersedes == first.source
    assert first.source is not None and second.raw_ref is not None
    stored = parse(vault.read(second.raw_ref))
    assert stored.source.raw_ref == second.raw_ref
    assert stored.supersedes == first.source.source_id


def test_drift_chains_supersede_the_latest_not_an_arbitrary_version(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    intake = intake_for(vault)
    versions = []
    for body in (b"# v1", b"# v2", b"# v3", b"# v4"):
        drop(vault, "drop/r.md", body)
        versions.append(intake.intake("drop/r.md", mode="apply", today=TODAY))
    for earlier, later in zip(versions, versions[1:], strict=False):
        assert later.status == "drifted" and later.supersedes == earlier.source
    assert len(vault.raw_files()) == 4
    # A batch dry run sees its own would-be writes, exactly as an apply would.
    drop(vault, "drop/batch-a.md", b"same")
    drop(vault, "drop/batch-b.md", b"same")
    preview = intake.intake_all(["drop/batch-a.md", "drop/batch-b.md"], today=TODAY)
    assert [o.status for o in preview] == ["written", "duplicate"]
    assert [o.raw_ref for o in preview] == ["raw/batch-a.md", "raw/batch-a.md"]
    applied = intake.intake_all(["drop/batch-a.md", "drop/batch-b.md"], mode="apply", today=TODAY)
    assert [o.status for o in applied] == ["written", "duplicate"]


def test_legacy_raw_never_breaks_an_intake(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    (tmp_path / "raw" / "big5.md").write_bytes("# 舊筆記\n".encode("cp950"))
    good_head = render(document()).encode("utf-8")
    (tmp_path / "raw" / "mixed.md").write_bytes(good_head + "後面是 Big5 內文\n".encode("cp950"))
    entries = raw_index(vault)
    assert [e.raw_ref for e in entries] == ["raw/mixed.md"]
    outcome = intake_for(vault).intake(
        drop(vault, "drop/new.txt", b"fresh"), mode="apply", today=TODAY
    )
    assert outcome.status == "written"
    # A legacy file sitting where the hash-suffixed name would go is not overwritten.
    drop(vault, "drop/report.md", b"# v1")
    first = intake_for(vault).intake("drop/report.md", mode="apply", today=TODAY)
    drop(vault, "drop/report.md", b"# v2")
    clash = source_for(b"# v2", "drop/report.md").sha256[:8]
    (tmp_path / "raw" / f"report--{clash}.md").write_text("legacy\n", encoding="utf-8")
    preview = intake_for(vault).intake("drop/report.md", today=TODAY)
    applied = intake_for(vault).intake("drop/report.md", mode="apply", today=TODAY)
    assert preview.raw_ref == applied.raw_ref == f"raw/report--{clash}-2.md"
    assert applied.supersedes == first.source
    assert (tmp_path / "raw" / f"report--{clash}.md").read_text(encoding="utf-8") == "legacy\n"
