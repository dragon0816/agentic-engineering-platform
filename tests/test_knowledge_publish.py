"""Publish a merged Knowledge candidate as a new version (K3.4, owner 2026-10-11)."""

import json
from pathlib import Path

import pytest
from test_host_wiring import workspace
from test_knowledge_sandbox import _base, _snapshot
from test_product_e2e_05 import manifest

from common.assets import AssetIdentity
from host_runtime.contracts import CompanyHostConfiguration, HostLayout
from host_runtime.knowledge_publish import PublishError, publish_candidate
from knowledge.evolution import KnowledgeCatalog, KnowledgeManifest
from knowledge.pipeline import KnowledgePipeline
from knowledge.sandbox import Sandboxes
from knowledge.vault import Vault

V1 = AssetIdentity(namespace="engineering", name="rs-knowledge", version="1.0.2")


def _host(tmp_path: Path) -> tuple[Path, KnowledgePipeline, Path]:
    base = _base(tmp_path)
    sandbox_root = tmp_path / "sb"
    config, layout = workspace(
        tmp_path,
        config_changes={
            "knowledge_pipeline": {
                "vaults": [{"name": "rs-k", "root": str(base)}],
                "sandbox_root": str(sandbox_root),
            },
            "knowledge": [{"asset": V1.model_dump(mode="json"), "vault_root": str(base)}],
        },
    )
    layout.knowledge.mkdir(parents=True, exist_ok=True)
    published = manifest(Vault(base)).model_copy(deep=True)
    data = json.loads(published.model_dump_json())
    data["metadata"]["identity"] = V1.model_dump(mode="json")
    (layout.knowledge / "engineering__rs-knowledge__1.0.2.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    path = tmp_path / "host.json"
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    pipeline = KnowledgePipeline(
        Sandboxes(layout.workspace_root, root=sandbox_root), {"rs-k": base}
    )
    return path, pipeline, base


def test_publishing_a_candidate_switches_the_binding_and_keeps_the_old_version(
    tmp_path: Path,
) -> None:
    path, pipeline, base = _host(tmp_path)
    before = _snapshot(base)
    sandbox = pipeline.create_sandbox("rs-k", "vna", "leo.chi").sandbox_id
    root = pipeline.sandboxes.open(sandbox)[1].root
    (root / "wiki/concepts/VNA.md").write_text("---\ntitle: VNA\n---\nVNA\n", encoding="utf-8")
    candidate = pipeline.merge(sandbox, mode="apply").candidate_root
    assert candidate
    config = CompanyHostConfiguration.model_validate_json(path.read_text(encoding="utf-8"))
    layout = HostLayout.under(config.workspace_root)
    result = publish_candidate(path, layout, "rs-k", candidate, "leo.chi")
    assert result.version == "1.1.0" and Path(result.backup).is_file()
    target = Path(result.vault_root)
    assert target.name == "base-v1.1.0" and (target / "wiki/concepts/VNA.md").is_file()
    assert not Path(candidate).exists() and _snapshot(base) == before
    updated = CompanyHostConfiguration.model_validate_json(path.read_text(encoding="utf-8"))
    assert updated.knowledge[0].asset.version == "1.1.0"
    assert Path(updated.knowledge[0].vault_root) == target
    assert updated.knowledge_pipeline is not None
    assert Path(updated.knowledge_pipeline.vaults[0].root) == target
    # The new manifest loads into the query catalog exactly as a published version.
    new = KnowledgeManifest.model_validate_json(
        (layout.knowledge / "engineering__rs-knowledge__1.1.0.json").read_text(encoding="utf-8")
    )
    KnowledgeCatalog().register(new, Vault(target))
    assert (layout.knowledge / "engineering__rs-knowledge__1.0.2.json").is_file()


def test_only_a_candidate_of_that_base_can_be_published(tmp_path: Path) -> None:
    path, pipeline, base = _host(tmp_path)
    config = CompanyHostConfiguration.model_validate_json(path.read_text(encoding="utf-8"))
    layout = HostLayout.under(config.workspace_root)
    with pytest.raises(PublishError, match="not_a_candidate"):
        publish_candidate(path, layout, "rs-k", str(base), "leo.chi")
    with pytest.raises(PublishError, match="unknown_base_vault"):
        publish_candidate(path, layout, "other", str(base), "leo.chi")


def test_refresh_stages_the_project_vault_as_the_agents_next_version(tmp_path: Path) -> None:
    from host_runtime.knowledge_publish import refresh_from_project

    path, _, base = _host(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["knowledge_pipeline"]["vaults"][0]["knowledge_asset"] = "rs-knowledge"
    path.write_text(json.dumps(data), encoding="utf-8")
    (base / "drop/big.pdf").write_bytes(b"%PDF original")  # originals are not staged
    before = _snapshot(base)
    config = CompanyHostConfiguration.model_validate_json(path.read_text(encoding="utf-8"))
    layout = HostLayout.under(config.workspace_root)
    result = refresh_from_project(path, layout, "rs-k", "leo.chi")
    target = Path(result.vault_root)
    assert result.version == "1.1.0" and target.name == "base-v1.1.0"
    assert (target / "wiki/concepts/EVM.md").is_file() and not (target / "drop").exists()
    assert _snapshot(base) == before  # the shared project folder is only read
    updated = CompanyHostConfiguration.model_validate_json(path.read_text(encoding="utf-8"))
    assert updated.knowledge[0].asset.version == "1.1.0"
    assert updated.knowledge_pipeline is not None
    assert Path(updated.knowledge_pipeline.vaults[0].root) == base  # still the project vault
    new = KnowledgeManifest.model_validate_json(
        (layout.knowledge / "engineering__rs-knowledge__1.1.0.json").read_text(encoding="utf-8")
    )
    KnowledgeCatalog().register(new, Vault(target))
    assert refresh_from_project(path, layout, "rs-k", "leo.chi").version == "1.2.0"
