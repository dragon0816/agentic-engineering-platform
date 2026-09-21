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
    with pytest.raises(ValidationError, match="section marker"):
        RawSection(text="<!-- raw-section 9 kind=text -->")
    with pytest.raises(ValidationError, match="frontmatter block"):
        RawSection(text="---\na: b\n---\nbody")
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
        ("# just markdown\n", "starts with frontmatter"),
        ("---\nsource_id: x\n", "unterminated"),
        ("---\nnot a field\n---\n", "malformed frontmatter"),
        ("---\nsource_id: src-1\n---\n", "missing"),
        (good.replace("raw-section 1", "raw-section 2"), "numbered in order"),
        (good.replace("---\n\n<!--", "---\nstray text\n<!--"), "before the first section"),
    ):
        with pytest.raises(ValueError, match=why):
            parse(bad)


def test_extractors_decode_and_strip_only_what_they_must() -> None:
    plain = PlainTextExtractor()
    assert plain.extract(b"  hello\n\n") == (RawSection(text="  hello"),)
    assert plain.extract(b"   \n") == ()
    with pytest.raises(ExtractionError) as raised:
        plain.extract(b"\xff\xfe")
    assert raised.value.code == "undecodable"
    markdown = MarkdownExtractor()
    assert markdown.extract(b"---\ntitle: T\n---\n# Heading\n\nbody\n") == (
        RawSection(text="# Heading\n\nbody"),
    )
    assert markdown.extract(b"---\nno end\nbody\n") == (RawSection(text="---\nno end\nbody"),)
    assert markdown.extract(b"---\ntitle: T\n---\n\n") == ()


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
