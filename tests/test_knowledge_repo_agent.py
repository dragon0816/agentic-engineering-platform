"""The Agent reads a wiki repository's published version (knowledge repositories R4a).

A `host.json` Knowledge binding names a repository once (`repo`); the catalog
keeps that identity and serves the published version, rebuilt and picked up at
the next question; publishing never changes the binding. Two PCs as in
`tests/test_knowledge_repos_api.py`. All data is fictional.
"""

from __future__ import annotations

import shutil
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import ValidationError
from test_knowledge_repos_api import PAGE, _call, _deliver, _edit, _ok, _push, _two_pcs

from common.assets import AssetIdentity, AssetMetadata, BusinessApproval, Owner
from host_runtime.contracts import KnowledgeHostBinding
from host_runtime.host import build_knowledge_catalog
from knowledge import wiki_repos
from knowledge.evolution import KnowledgeCatalog, KnowledgeManifest

ASSET = AssetIdentity(namespace="engineering", name="tester-knowledge", version="1.0.3")


def _template(purpose: str = "虛構測試儀器的知識") -> KnowledgeManifest:
    """The governed manifest the binding keeps; its digests are recomputed."""
    return KnowledgeManifest(
        metadata=AssetMetadata(
            identity=ASSET,
            owner=Owner(type="user", id="tester"),
            visibility="private",
            lifecycle="published",
            business_approval=BusinessApproval(status="approved", reviewer="tester", evidence="t"),
            validation_refs=("test",),
        ),
        domain="engineering",
        vault_ref="C:/placeholder" if Path("C:/").exists() else "/placeholder",
        raw_sha256="0" * 64,
        decisions_sha256="0" * 64,
        content_sha256="0" * 64,
        purpose=purpose,
    )


def _page(catalog: KnowledgeCatalog) -> str:
    found = catalog.get(ASSET)
    assert found is not None
    return found[1].read_bytes(PAGE).decode("utf-8")


def test_a_live_entry_follows_the_published_version(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    catalog = KnowledgeCatalog()
    catalog.register_live(_template(), partial(wiki_repos.agent_source, a, repo_id))
    # Before the first question the template stands in (the tool's words).
    (listed,) = catalog.manifests()
    assert listed.purpose == "虛構測試儀器的知識" and listed.content_sha256 == "0" * 64
    assert "K1 base" in _page(catalog)  # never published: the pushed head
    first = catalog.manifests()[0]
    assert first.content_sha256 != "0" * 64 and Path(first.vault_ref).name == "vault"
    _edit(a, repo_id, "Nothing yet.", "Shipping in Q3.", "出貨時程")
    assert "Shipping in Q3." not in _page(catalog)  # committed, not pushed
    _push(a, repo_id)
    _ok(_call(a, "POST", f"/{repo_id}/tag", {"name": "v1", "purpose": "第一版"}))
    _ok(_call(a, "POST", f"/{repo_id}/publish", {"tag": "v1", "confirm": True}))
    assert "Shipping in Q3." in _page(catalog)
    published = catalog.manifests()[0].content_sha256
    _edit(a, repo_id, "Intro.", "Intro, revised.", "改開頭")
    _push(a, repo_id)
    assert "Intro, revised." not in _page(catalog)  # v1 stays what the Agent reads
    assert catalog.manifests()[0].content_sha256 == published
    # The shared folder goes away (OneDrive offline): the last version is kept.
    shutil.move(str(drive_a / repo_id), str(tmp_path / "away"))
    assert "Shipping in Q3." in _page(catalog)
    # The other PC's Agent reads the same version once the files arrive.
    shutil.move(str(tmp_path / "away"), str(drive_a / repo_id))
    _deliver(drive_a / repo_id, drive_b / repo_id)
    other = KnowledgeCatalog()
    other.register_live(_template(), partial(wiki_repos.agent_source, b, repo_id))
    text = _page(other)
    assert "Shipping in Q3." in text and "Intro, revised." not in text


def test_the_host_binds_an_identity_to_a_repository_once(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    manifests = tmp_path / "assets" / "knowledge"
    manifests.mkdir(parents=True)
    (manifests / "tester-knowledge.json").write_text(_template().model_dump_json(), "utf-8")
    config = SimpleNamespace(knowledge=[KnowledgeHostBinding(asset=ASSET, repo=repo_id)])
    layout = SimpleNamespace(
        knowledge=manifests, workspace_root=a, knowledge_vaults=tmp_path / "vaults"
    )
    catalog = build_knowledge_catalog(cast(Any, config), cast(Any, layout))
    assert "K1 base" in _page(catalog)


def test_a_binding_names_exactly_one_source() -> None:
    with pytest.raises(ValidationError):
        KnowledgeHostBinding(asset=ASSET)
    with pytest.raises(ValidationError):
        KnowledgeHostBinding(asset=ASSET, repo="tester-wiki", vault_root=str(Path.cwd()))
    assert KnowledgeHostBinding(asset=ASSET, repo="tester-wiki").vault_root is None
