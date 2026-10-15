"""Pull chosen drop folders of the project vault into a sandbox (collaboration C1)."""

from pathlib import Path

import pytest
from test_knowledge_sandbox import _base, _snapshot

from knowledge.pipeline import KnowledgePipeline, PipelineError
from knowledge.raw import source_for
from knowledge.sandbox import Sandboxes


def _project(tmp_path: Path) -> tuple[KnowledgePipeline, Path]:
    base = _base(tmp_path)
    for rel, data in {
        "drop/Market/AI/deck.txt": "AI market deck\n",
        "drop/Market/5G.txt": "5G market\n",
        "drop/Productions/cmx.txt": "CMX500 spec\n",
    }.items():
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text(data, encoding="utf-8")
    pipeline = KnowledgePipeline(Sandboxes(tmp_path / "workspace"), {"rs-k": base})
    return pipeline, base


def test_a_sandbox_copies_no_drop_and_pulls_only_chosen_folders(tmp_path: Path) -> None:
    pipeline, base = _project(tmp_path)
    before = _snapshot(base)
    folders = {f.path: f.files for f in pipeline.drop_folders("rs-k").folders}
    assert folders == {"Market": 2, "Market/AI": 1, "Productions": 1}
    sandbox = pipeline.create_sandbox("rs-k", "market ai", "leo.chi").sandbox_id
    root = pipeline.sandboxes.open(sandbox)[1].root
    assert not any((root / "drop").rglob("*.txt"))  # the project's drop is not copied
    pulled = pipeline.pull(sandbox, ("Market/AI",))
    assert pulled.copied == ("Market/AI/deck.txt",) and pulled.folders == ("Market/AI",)
    assert (root / "drop/Market/AI/deck.txt").is_file()
    assert not (root / "drop/Productions").exists()
    again = pipeline.pull(sandbox, ("Market",))
    assert again.copied == ("Market/5G.txt",)
    assert again.already_in_sandbox == ("Market/AI/deck.txt",)
    assert pipeline.sandboxes.open(sandbox)[0].pulled == ("Market/AI", "Market")
    assert _snapshot(base) == before


def test_an_original_already_ingested_is_not_pulled(tmp_path: Path) -> None:
    pipeline, base = _project(tmp_path)
    data = (base / "drop/Productions/cmx.txt").read_bytes()
    source = source_for(data, "drop/Productions/cmx.txt")
    (base / "raw/Productions").mkdir(parents=True)
    (base / "raw/Productions/cmx.md").write_text(
        f"---\nsource_id: {source.source_id}\nsource_sha256: {source.sha256}\n"
        f"original_ref: {source.original_ref}\nraw_ref: raw/Productions/cmx.md\n"
        "extractor: text\ncreated: 2026-10-11\n---\nCMX500 spec\n",
        encoding="utf-8",
    )
    sandbox = pipeline.create_sandbox("rs-k", "prod", "leo.chi").sandbox_id
    pulled = pipeline.pull(sandbox, ("Productions",))
    assert pulled.copied == () and pulled.already_ingested == ("Productions/cmx.txt",)
    # Its Raw is already in the sandbox: a rule change ingests that again.
    assert pulled.already_raw == ("raw/Productions/cmx.md",)


def test_pull_stays_inside_the_project_drop(tmp_path: Path) -> None:
    pipeline, _ = _project(tmp_path)
    sandbox = pipeline.create_sandbox("rs-k", "x", "a").sandbox_id
    for bad in ("../wiki", "Market/../../wiki", ""):
        with pytest.raises(PipelineError, match="outside_drop"):
            pipeline.pull(sandbox, (bad,))
    with pytest.raises(PipelineError):  # an absolute path is read inside drop/, never outside
        pipeline.pull(sandbox, ("/etc",))
    with pytest.raises(PipelineError, match="unknown_drop_folder"):
        pipeline.pull(sandbox, ("Nope",))


def test_an_original_known_to_legacy_raw_by_its_hash_prefix_is_not_pulled(tmp_path: Path) -> None:
    import hashlib

    pipeline, base = _project(tmp_path)
    prefix = hashlib.sha256((base / "drop/Market/5G.txt").read_bytes()).hexdigest()[:16]
    (base / "raw/Market").mkdir(parents=True)
    (base / "raw/Market/5G.md").write_text(
        f"---\ntitle: 5G\ntype: raw\nsource_sha: {prefix}\n---\n5G market\n", encoding="utf-8"
    )
    sandbox = pipeline.create_sandbox("rs-k", "legacy", "leo.chi").sandbox_id
    pulled = pipeline.pull(sandbox, ("Market",))
    assert pulled.already_ingested == ("Market/5G.txt",)
    assert pulled.already_raw == ("raw/Market/5G.md",)
    assert pulled.copied == ("Market/AI/deck.txt",)
