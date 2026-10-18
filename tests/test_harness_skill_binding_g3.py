"""G3: a domain adapter picks its Skill by the asset it binds (owner 2026-10-18).

A Skill may declare the assets it binds (a Knowledge vault, a Workflow, a
Strategy Config) with an explicit priority. The binding decides, never the
installation order; only when no Skill binds the asset does the adapter fall
back to the first eligible Skill, as before. The field is optional: a manifest
without it keeps its bytes and digest.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from agent.skills import SkillAssetBinding, SkillManifest, SkillRegistry, bound_skill
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from common.assets import AssetIdentity
from host_runtime.knowledge_harness import KnowledgeHarness, harness_skill

SALES = AssetIdentity(namespace="company", name="sales-vault", version="1.0.0")
LAB = AssetIdentity(namespace="company", name="lab-vault", version="2.0.0")


def skill(
    name: str, bindings: list[dict[str, Any]] | None = None, *, alias: str | None = None
) -> SkillManifest:
    payload: dict[str, Any] = {
        "metadata": {
            "identity": {"namespace": "engineering", "name": name, "version": "1.0.0"},
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "organization",
            "lifecycle": "published",
        },
        "alias": alias or name.replace("-", "_"),
        "instructions": "Answer from the vault with citations.",
        "commands": [
            {
                "name": "ask",
                "kind": "capability",
                "target": KNOWLEDGE_QUERY_SPEC.identity.model_dump(),
            }
        ],
        "harness_guidance": {"domains": ["knowledge"]},
    }
    if bindings is not None:
        payload["asset_bindings"] = bindings
    return SkillManifest.model_validate(payload)


def registry(*manifests: SkillManifest) -> SkillRegistry:
    skills = SkillRegistry()
    for manifest in manifests:
        skills.register(manifest)
    return skills


def binds(asset: AssetIdentity, priority: int = 0, **extra: Any) -> dict[str, Any]:
    return {
        "kind": "knowledge",
        "namespace": asset.namespace,
        "name": asset.name,
        "priority": priority,
        **extra,
    }


def test_a_manifest_without_bindings_keeps_its_bytes_and_digest() -> None:
    plain = skill("general")
    dumped = plain.model_dump_json()
    assert "asset_bindings" not in dumped
    assert SkillManifest.model_validate_json(dumped).asset_bindings == ()
    again = SkillManifest.model_validate_json(dumped).model_dump_json()
    assert hashlib.sha256(again.encode()).digest() == hashlib.sha256(dumped.encode()).digest()


def test_bindings_are_validated() -> None:
    with pytest.raises(ValueError):
        skill("dup", [binds(SALES), binds(SALES)])
    with pytest.raises(ValueError):
        SkillAssetBinding.model_validate({"kind": "vault", "namespace": "a", "name": "b"})
    with pytest.raises(ValueError):
        SkillAssetBinding.model_validate(
            {"kind": "knowledge", "namespace": "a", "name": "b", "priority": -1}
        )


@pytest.mark.parametrize("order", ["general first", "sales first"])
def test_the_skill_bound_to_the_vault_wins_whatever_the_installation_order(order: str) -> None:
    general, sales = skill("general"), skill("sales-skill", [binds(SALES)])
    skills = registry(general, sales) if order == "general first" else registry(sales, general)
    assert harness_skill(skills, SALES) == sales.metadata.identity


def test_several_bound_skills_are_ranked_by_explicit_priority() -> None:
    low, high = skill("sales-a", [binds(SALES, 1)]), skill("sales-b", [binds(SALES, 5)])
    assert harness_skill(registry(low, high), SALES) == high.metadata.identity
    assert harness_skill(registry(high, low), SALES) == high.metadata.identity
    # Equal priority: decided by identity, never by installation order.
    a, b = skill("sales-a", [binds(SALES)]), skill("sales-b", [binds(SALES)])
    assert harness_skill(registry(b, a), SALES) == harness_skill(registry(a, b), SALES)


def test_a_binding_may_name_one_exact_version() -> None:
    pinned = skill("lab-v1", [binds(LAB, version="1.0.0")])
    general = skill("general")
    assert harness_skill(registry(general, pinned), LAB) == general.metadata.identity
    exact = skill("lab-v2", [binds(LAB, version="2.0.0")])
    assert harness_skill(registry(general, exact), LAB) == exact.metadata.identity


def test_with_no_binding_the_first_eligible_skill_stays_the_choice() -> None:
    first, second = skill("first"), skill("second")
    assert harness_skill(registry(first, second), SALES) == first.metadata.identity
    assert harness_skill(registry(first, second)) == first.metadata.identity
    # A Skill bound to another vault does not change this vault's fallback.
    other = skill("lab-only", [binds(LAB)])
    assert harness_skill(registry(other, first), SALES) == other.metadata.identity


def test_an_ineligible_skill_is_never_chosen_by_its_binding() -> None:
    draft = skill("sales-draft", [binds(SALES, 9)]).model_copy(deep=True)
    draft = SkillManifest.model_validate(
        {
            **draft.model_dump(mode="json"),
            "metadata": {**draft.model_dump(mode="json")["metadata"], "lifecycle": "draft"},
        }
    )
    general = skill("general")
    assert harness_skill(registry(draft, general), SALES) == general.metadata.identity


def test_bound_skill_is_generic_over_asset_kinds() -> None:
    workflow = AssetIdentity(namespace="engineering", name="weekly-report", version="1.0.0")
    report = skill(
        "report-skill", [{"kind": "workflow", "namespace": "engineering", "name": "weekly-report"}]
    )
    found = bound_skill((skill("general"), report), "workflow", workflow)
    assert found is not None and found.metadata.identity == report.metadata.identity
    assert bound_skill((report,), "knowledge", workflow) is None


class _Runtime:
    def __init__(self, skills: SkillRegistry) -> None:
        router = type("R", (), {"commands": type("C", (), {"skills": skills})()})()
        self.agent = type("A", (), {"gateway": type("G", (), {"router": router})()})()


def test_the_tool_route_asks_with_the_skill_bound_to_its_vault(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    general, sales = skill("general"), skill("sales-skill", [binds(SALES)])
    harness = KnowledgeHarness(_Runtime(registry(general, sales)), "engineering")
    asked: list[Any] = []

    def fake_ask(item: Any, *, catalog: Any = None, supplementary: Any = ()) -> dict[str, Any]:
        asked.append(item)
        return {"ok": True}

    monkeypatch.setattr(harness, "ask", fake_ask)
    harness.for_tool("sales pipeline?", SALES)
    harness.for_tool("lab question?", LAB)
    assert asked[0].skill == sales.metadata.identity
    assert asked[1].skill == general.metadata.identity
