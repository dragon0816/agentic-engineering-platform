"""A legacy Knowledge tree becomes a queryable copy without changing its source."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path

import pytest

from knowledge.query import retrieve
from knowledge.stage import main, stage_legacy_query_vault
from knowledge.vault import Vault


def source_vault(root: Path) -> Path:
    (root / "raw").mkdir(parents=True)
    (root / "wiki" / "sources").mkdir(parents=True)
    (root / "drop").mkdir()
    (root / "raw" / "guide.md").write_text("# Device guide\n\nAster option supports fast links.\n")
    (root / "wiki" / "sources" / "Guide.md").write_text(
        "---\nsource_path: raw/guide.md\n---\n\nAster is documented.\n"
    )
    (root / "drop" / "original.pdf").write_bytes(b"not a real PDF")
    (root / "index.md").write_text("# Index\n")
    (root / "log.md").write_text("# Log\n")
    (root / ".brain-state.json").write_text("private legacy state")
    return root


def test_query_stage_adopts_raw_and_keeps_original_untouched(tmp_path: Path) -> None:
    source = source_vault(tmp_path / "source")
    before = {
        path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*")
        if path.is_file()
    }
    destination = tmp_path / "query-copy"
    report = stage_legacy_query_vault(
        source, destination, today=date(2026, 10, 3), stamp="fixture-20261003"
    )
    after = {
        path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert report.raw_files == 1 and report.wiki_pages == 1
    assert report.adopted_raw == 1 and report.migrated_pages == 1
    assert report.unresolved_pages == 0
    assert not report.originals_copied
    assert not (destination / "drop" / "original.pdf").exists()
    assert not (destination / ".brain-state.json").exists()
    assert (destination / "decisions.md").is_file()
    assert (destination / ".ingest-adopted.json").is_file()
    assert "source_id:" in (destination / "wiki" / "sources" / "Guide.md").read_text()
    passages = retrieve(Vault(destination), "Aster option")
    assert any(passage.citation.kind == "raw" for passage in passages)


def test_query_stage_refuses_an_existing_target_without_changing_it(tmp_path: Path) -> None:
    source = source_vault(tmp_path / "source")
    destination = tmp_path / "existing"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(ValueError, match="already exists"):
        stage_legacy_query_vault(
            source, destination, today=date(2026, 10, 3), stamp="fixture-20261003"
        )
    assert marker.read_text() == "keep"


def test_query_stage_cli_reports_corpus_and_omitted_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = source_vault(tmp_path / "source")
    target = tmp_path / "query-copy"
    assert (
        main(
            [
                "--source",
                str(source),
                "--target",
                str(target),
                "--stamp",
                "fixture-20261003",
                "--today",
                "2026-10-03",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["vault_root"] == str(target)
    assert report["raw_files"] == 1
    assert report["wiki_pages"] == 1
    assert report["originals_copied"] is False
    assert (target / "drop").is_dir()
    assert list((target / "drop").iterdir()) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows long-path regression")
def test_query_stage_copies_a_long_legacy_wiki_name(tmp_path: Path) -> None:
    source = source_vault(tmp_path / "source")
    relative = Path("wiki") / "sources" / ("x" * 190 + ".md")
    long_source = Path("\\\\?\\" + str(source / relative))
    long_source.write_text("---\nsource_path: raw/guide.md\n---\n\nAster option.\n")
    target = tmp_path / "query-copy"
    report = stage_legacy_query_vault(
        source, target, today=date(2026, 10, 3), stamp="long-path-20261003"
    )
    assert len(str(target / relative)) > 260
    assert report.wiki_pages == 2 and report.migrated_pages == 2
    long_copy = Path("\\\\?\\" + str(target / relative))
    assert "source_id:" in long_copy.read_text()
