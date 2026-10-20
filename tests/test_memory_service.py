"""Accumulated memory M1: memory space declarations, the Memory Service's
shared facilities and their access rules (docs/phases/ACCUMULATED_MEMORY.md).

Synthetic data only. Covers the manifest section (validation and unchanged
bytes without it), the registry (one manager per space), reader / contributor
enforcement, append-only observations, the merge rules as data with the
owner's `contacts/org` defaults, proposals, history and undo, external ids
and auto-merge, and per-actor isolation.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from agent.skills import SkillManifest
from capabilities.business_cards.manifest import CARDS_SKILL, business_cards_skill
from capabilities.business_cards.space import CONTACTS_ORG, DECLARATION, MERGE_RULES
from common.assets import AssetIdentity, WorkflowManifest
from common.memory import Decision, FieldMergeRule, MemorySpaceDeclaration, MergeRules
from host_runtime.asset_shelf import ShelfError, switch_off, switch_on
from host_runtime.assets import shipped
from host_runtime.contracts import HostLayout
from host_runtime.memory_spaces import conflicts, registry
from memory import merge
from memory.registry import MemoryRegistry, MemoryRegistryError
from memory.service import (
    MemoryAccessError,
    MemoryService,
    MemoryServiceError,
    SpaceTx,
    memory_path,
)

C4C_SKILL = AssetIdentity(namespace="sales", name="c4c-sync", version="1.0.0")
MAIL_SKILL = AssetIdentity(namespace="engineering", name="mail-writer", version="1.0.0")
STRANGER = AssetIdentity(namespace="engineering", name="stranger", version="1.0.0")


def _skill(name: str, memory: list[dict[str, Any]] | None = None) -> SkillManifest:
    payload: dict[str, Any] = {
        "metadata": {
            "identity": {"namespace": "engineering", "name": name, "version": "1.0.0"},
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "organization",
            "lifecycle": "published",
        },
        "alias": name.replace("-", "_"),
        "instructions": "Do the thing.",
    }
    if memory is not None:
        payload["memory_spaces"] = memory
    return SkillManifest.model_validate(payload)


def _registry() -> MemoryRegistry:
    found = MemoryRegistry()
    found.provide_rules(MERGE_RULES)
    found.declare(CARDS_SKILL, [DECLARATION])
    found.declare(C4C_SKILL, [MemorySpaceDeclaration(space=CONTACTS_ORG, role="contributor")])
    found.declare(MAIL_SKILL, [MemorySpaceDeclaration(space=CONTACTS_ORG, role="reader")])
    return found


def _service(tmp_path: Path, actor: str = "alice") -> MemoryService:
    return MemoryService.for_actor(tmp_path, actor, _registry())


# -- the manifest section ----------------------------------------------


def test_a_manifest_without_memory_spaces_keeps_its_bytes_and_digest() -> None:
    plain = _skill("general")
    dumped = plain.model_dump_json()
    assert "memory_spaces" not in dumped
    again = SkillManifest.model_validate_json(dumped).model_dump_json()
    assert hashlib.sha256(again.encode()).digest() == hashlib.sha256(dumped.encode()).digest()
    for manifest in shipped():
        data = manifest.model_dump(mode="json")
        if manifest.metadata.identity == CARDS_SKILL:
            assert data["memory_spaces"][0]["space"] == CONTACTS_ORG
        else:
            # Every other shipped manifest is byte for byte what it was.
            assert "memory_spaces" not in data
    workflow = next(item for item in shipped() if isinstance(item, WorkflowManifest))
    assert "memory_spaces" not in workflow.model_dump_json()


def test_the_business_cards_skill_manages_contacts_org() -> None:
    declared = business_cards_skill().memory_spaces
    assert declared == (DECLARATION,)
    assert DECLARATION.role == "manager"
    assert DECLARATION.kinds == ("entities", "sync_state")  # M2: mail sync state
    assert DECLARATION.sensitivity == "CONFIDENTIAL"
    assert DECLARATION.merge_rules == MERGE_RULES.rules_id
    round_trip = SkillManifest.model_validate_json(business_cards_skill().model_dump_json())
    assert round_trip.memory_spaces == declared


@pytest.mark.parametrize(
    "bad",
    [
        # a manager says what the space is
        {"space": "contacts/org", "role": "manager"},
        {
            "space": "contacts/org",
            "role": "manager",
            "kinds": ["entities"],
            "sensitivity": "INTERNAL",
            "retention": "until_deleted",
            "schema_ref": "contacts.org.person.v1",
        },
        # only the manager defines it
        {"space": "contacts/org", "role": "reader", "schema_ref": "contacts.org.person.v1"},
        {"space": "contacts/org", "role": "contributor", "sensitivity": "PUBLIC"},
        # names, kinds, sensitivity and retention are closed
        {"space": "Contacts/Org", "role": "reader"},
        {"space": "contacts", "role": "reader"},
        {"space": "contacts/org", "role": "owner"},
        {"space": "contacts/org", "role": "reader", "kinds": ["secrets"]},
        {"space": "contacts/org", "role": "reader", "kinds": ["facts", "facts"]},
        {
            "space": "contacts/org",
            "role": "manager",
            "kinds": ["entities"],
            "sensitivity": "SECRET",
            "retention": "until_deleted",
            "schema_ref": "contacts.org.person.v1",
            "merge_rules": "contacts.org.merge.v1",
        },
        {
            "space": "contacts/org",
            "role": "manager",
            "kinds": ["entities"],
            "sensitivity": "INTERNAL",
            "retention": "forever",
            "schema_ref": "contacts.org.person.v1",
            "merge_rules": "contacts.org.merge.v1",
        },
    ],
)
def test_declarations_are_validated(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        MemorySpaceDeclaration.model_validate(bad)
    with pytest.raises(ValidationError):
        _skill("bad", [bad])


def test_a_space_is_declared_once_per_manifest_and_workflows_may_declare_too() -> None:
    reader = {"space": "contacts/org", "role": "reader"}
    with pytest.raises(ValidationError):
        _skill("twice", [reader, {"space": "contacts/org", "role": "contributor"}])
    workflow = next(item for item in shipped() if isinstance(item, WorkflowManifest))
    data = workflow.model_dump(mode="json")
    with_memory = WorkflowManifest.model_validate({**data, "memory_spaces": [reader]})
    assert with_memory.memory_spaces[0].role == "reader"
    with pytest.raises(ValidationError):
        WorkflowManifest.model_validate({**data, "memory_spaces": [reader, reader]})


# -- the registry -------------------------------------------------------


def test_a_space_has_one_manager() -> None:
    found = _registry()
    with pytest.raises(MemoryRegistryError) as refused:
        found.declare(STRANGER, [DECLARATION])
    assert refused.value.code == "memory_space_has_a_manager"
    # Another version of the manager is not a conflict.
    found.declare(CARDS_SKILL.model_copy(update={"version": "2.0.0"}), [DECLARATION])
    assert found.role(CONTACTS_ORG, CARDS_SKILL) == "manager"
    assert found.role(CONTACTS_ORG, C4C_SKILL) == "contributor"
    assert found.role(CONTACTS_ORG, MAIL_SKILL) == "reader"
    assert found.role(CONTACTS_ORG, STRANGER) is None
    # From manifests, a conflicting later manager is left out.
    rival = _skill("rival", [DECLARATION.model_dump(mode="json")])
    built = MemoryRegistry.from_manifests([business_cards_skill(), rival], rules=[MERGE_RULES])
    assert built.role(CONTACTS_ORG, rival.metadata.identity) is None


def test_installing_a_second_manager_is_refused_on_this_host(tmp_path: Path) -> None:
    layout = HostLayout.under(tmp_path)
    layout.skills.mkdir(parents=True)
    rival = _skill("rival", [DECLARATION.model_dump(mode="json")])
    assert conflicts(layout, rival) == (CONTACTS_ORG,)
    assert conflicts(layout, _skill("reader", [{"space": CONTACTS_ORG, "role": "reader"}])) == ()
    assert conflicts(layout, business_cards_skill()) == ()
    # Switching on a switched-off rival is refused the same way.
    path = layout.skills / "engineering__rival__1.0.0.json"
    path.write_text(rival.model_dump_json(), encoding="utf-8")
    switch_off(layout, "skill", rival.metadata.identity)
    with pytest.raises(ShelfError) as refused:
        switch_on(layout, "skill", rival.metadata.identity)
    assert refused.value.code == "memory_space_has_a_manager"
    # The Host's registry keeps the shipped manager and leaves the rival out.
    host = registry(layout)
    assert host.role(CONTACTS_ORG, CARDS_SKILL) == "manager"
    assert host.role(CONTACTS_ORG, rival.metadata.identity) is None


# -- access rules -------------------------------------------------------


def test_reads_need_a_reader_and_writes_a_contributor_declaration(tmp_path: Path) -> None:
    service = _service(tmp_path)
    cards = service.space(CONTACTS_ORG, asset=CARDS_SKILL)
    c4c = service.space(CONTACTS_ORG, asset=C4C_SKILL)
    mail = service.space(CONTACTS_ORG, asset=MAIL_SKILL)
    observed = c4c.add_observation(
        "p-1",
        {"company": "範例科技"},
        source_kind="c4c",
        source_date="2026-10-01",
        recorded_by="alice via web",
    )
    assert [item.observation_id for item in mail.observations("p-1")] == [observed]
    assert mail.observations("p-1")[0].contributor == "sales/c4c-sync"
    with pytest.raises(MemoryAccessError) as refused:
        mail.add_observation(
            "p-1",
            {"title": "經理"},
            source_kind="card",
            source_date="2026-10-01",
            recorded_by="alice via web",
        )
    assert refused.value.code == "memory_write_not_declared"
    with pytest.raises(MemoryAccessError) as undeclared:
        service.space(CONTACTS_ORG, asset=STRANGER)
    assert undeclared.value.code == "memory_space_not_declared"
    # Only the manager reaches the space's own tables and writes provenance.
    with c4c.transaction() as tx, pytest.raises(MemoryAccessError) as manager_only:
        tx.table("people")
    assert manager_only.value.code == "memory_manager_only"
    with c4c.transaction() as tx, pytest.raises(MemoryAccessError):
        tx.set_provenance(
            "p-1",
            "company",
            source_kind="c4c",
            source_date="2026-10-01",
            observation_id=observed,
            set_by="x",
        )
    with cards.transaction() as tx:
        assert tx.table("people") == "contacts_org__people"
    # A source kind the space's rules do not know is refused.
    with pytest.raises(MemoryServiceError) as unknown:
        c4c.add_observation(
            "p-1", {"x": "y"}, source_kind="rumour", source_date="2026-10-01", recorded_by="a"
        )
    assert unknown.value.code == "memory_source_unknown"
    with pytest.raises(MemoryServiceError) as unregistered:
        MemoryService.for_actor(tmp_path, "bob", MemoryRegistry()).space(
            CONTACTS_ORG, asset=CARDS_SKILL
        )
    assert unregistered.value.code == "memory_space_not_declared"


def test_the_space_is_registered_with_its_rules_as_data(tmp_path: Path) -> None:
    service = _service(tmp_path)
    (summary,) = service.spaces()
    assert (summary.space, summary.manager) == (CONTACTS_ORG, "engineering/business-cards")
    assert summary.rules == MERGE_RULES and summary.declaration == DECLARATION
    with sqlite3.connect(service.path) as con:
        stored = json.loads(con.execute("SELECT rules_json FROM spaces").fetchone()[0])
    assert stored["fields"]["company"]["policy"] == "precedence"
    with pytest.raises(MemoryAccessError):
        service.register_space(DECLARATION, manager=STRANGER, rules=MERGE_RULES)


def test_observations_are_append_only(tmp_path: Path) -> None:
    service = _service(tmp_path)
    space = service.space(CONTACTS_ORG, asset=CARDS_SKILL)
    observed = space.add_observation(
        "p-1", {"title": "經理"}, source_kind="card", source_date="2026-01-10", recorded_by="a"
    )
    with sqlite3.connect(service.path) as con:
        for statement in (
            "UPDATE observations SET fields_json = '{}'",
            "UPDATE observations SET entity_id = 'p-2'",
            "DELETE FROM observations",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="append_only"):
                con.execute(statement)
    with space.transaction() as tx:
        assert tx.retract([observed], "c-1") == 1
        # Retracted once; its content stays.
        assert tx.retract([observed], "c-2") == 0
        assert tx.observations("p-1") == []
        (kept,) = tx.observations("p-1", include_retracted=True)
    assert kept.fields == {"title": "經理"} and kept.retracted_by == "c-1"
    with sqlite3.connect(service.path) as con, pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE observations SET retracted_by = ''")


# -- merge rules --------------------------------------------------------


def _decide(
    field: str, current: str, kind: str | None, date: str, offered: str, by: str, on: str
) -> Decision:
    return merge.decide(
        MERGE_RULES,
        field,
        current=current,
        current_kind=kind,
        current_date=date,
        offered=offered,
        offered_kind=by,
        offered_date=on,
    )


def test_the_company_name_follows_the_card_and_c4c_only_proposes() -> None:
    later_c4c = _decide(
        "company", "範例科技股份有限公司", "card", "2026-01-10", "範例科技", "c4c", "2026-09-01"
    )
    assert (later_c4c.action, later_c4c.reason) == ("propose", "lower_trust")
    older_card = _decide(
        "company", "範例科技", "c4c", "2026-09-01", "範例科技股份有限公司", "card", "2026-01-10"
    )
    assert older_card.action == "take"
    assert _decide("company", "", None, "", "範例科技", "c4c", "2026-09-01").action == "take"
    newer_card = _decide(
        "company", "A 公司", "card", "2026-01-10", "B 公司", "email_signature", "2026-02-01"
    )
    assert newer_card.action == "take"


def test_title_and_place_follow_the_newest_evidence_from_any_source() -> None:
    for field in ("title", "department", "division", "business_group"):
        newer = _decide(field, "經理", "card", "2026-01-10", "協理", "c4c", "2026-03-01")
        assert newer.action == "take", field
        older = _decide(field, "協理", "c4c", "2026-03-01", "經理", "card", "2026-01-10")
        assert (older.action, older.reason) == ("keep", "older_evidence"), field


def test_the_persons_value_wins_and_differing_evidence_becomes_a_proposal() -> None:
    newer = _decide("title", "資深經理", "user", "2026-02-01", "協理", "card", "2026-03-01")
    assert (newer.action, newer.reason) == ("propose", "user_set")
    stated = _decide("title", "資深經理", "card", "2026-02-01", "協理", "user", "2020-01-01")
    assert stated.action == "take"
    # Newest-only variant, as data: older evidence is then kept silently.
    rules = MERGE_RULES.model_copy(
        update={"default": FieldMergeRule(user_conflict="propose_if_newer"), "fields": {}}
    )
    older = merge.decide(
        rules,
        "title",
        current="資深經理",
        current_kind="user",
        current_date="2026-02-01",
        offered="協理",
        offered_kind="card",
        offered_date="2026-01-01",
    )
    assert (older.action, older.reason) == ("keep", "older_evidence")


def test_external_ids_only_match_and_uncertain_readings_never_replace() -> None:
    assert _decide("c4c_account", "", None, "", "A-1", "c4c", "2026-01-01").reason == "match_only"
    unsure = merge.decide(
        MERGE_RULES,
        "phone",
        current="02-1234",
        current_kind="card",
        current_date="2026-01-01",
        offered="02-9999",
        offered_kind="card",
        offered_date="2026-05-01",
        uncertain=True,
    )
    assert (unsure.action, unsure.reason) == ("keep", "uncertain")


def test_reporting_lines_are_solid_only_on_the_persons_word_or_evidence(tmp_path: Path) -> None:
    space = _service(tmp_path).space(CONTACTS_ORG, asset=MAIL_SKILL)
    with space.transaction() as tx:
        assert all(
            tx.solid("reporting_line", kind) for kind in ("user", "signature", "email_content")
        )
        assert not tx.solid("reporting_line", "title_inference")
        assert not tx.solid("reporting_line", "agent")


def test_current_values_resolve_from_observations_with_conflicts_left_to_the_person(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    cards = service.space(CONTACTS_ORG, asset=CARDS_SKILL)
    c4c = service.space(CONTACTS_ORG, asset=C4C_SKILL)
    cards.add_observation(
        "p-1",
        {"company": "範例科技股份有限公司", "title": "經理"},
        source_kind="card",
        source_date="2026-01-10",
        recorded_by="a",
    )
    c4c.add_observation(
        "p-1",
        {"company": "範例科技", "title": "協理", "c4c_account": "A-7"},
        source_kind="c4c",
        source_date="2026-05-01",
        recorded_by="a",
    )
    cards.add_observation(
        "p-1", {"title": "資深經理"}, source_kind="user", source_date="2026-06-01", recorded_by="a"
    )
    cards.add_observation(
        "p-1",
        {"title": "副總"},
        source_kind="email_signature",
        source_date="2026-08-01",
        recorded_by="a",
    )
    found = c4c.resolve("p-1")
    assert found.values["company"].value == "範例科技股份有限公司"
    assert found.values["title"].value == "資深經理"
    assert "c4c_account" not in found.values
    assert [(c.field, c.proposed, c.reason) for c in found.conflicts] == [
        ("company", "範例科技", "lower_trust"),
        ("title", "副總", "user_set"),
    ]


def test_another_source_joins_a_person_only_on_an_identical_email_or_a_mapped_id(
    tmp_path: Path,
) -> None:
    space = _service(tmp_path).space(CONTACTS_ORG, asset=C4C_SKILL)
    emails = {"hm.wang@example.com": "p-1"}

    def by_identity(system: str, value: str) -> str | None:
        return emails.get(value.casefold()) if system == "email" else None

    with space.transaction() as tx:
        same = tx.auto_merge(
            {"email": "HM.Wang@example.com"}, by_identity=lambda s, v: by_identity(s, v)
        )
        assert (same.entity_id, same.by) == ("p-1", "email")
        assert tx.map_external_id("p-2", "c4c_contact", "C-9", actor="alice via web")
        assert not tx.map_external_id("p-2", "c4c_contact", "C-9", actor="alice via web")
        with pytest.raises(MemoryServiceError) as taken:
            tx.map_external_id("p-3", "c4c_contact", "C-9", actor="alice via web")
        assert taken.value.code == "external_id_taken"
        mapped = tx.auto_merge({"c4c_contact": "C-9"}, by_identity=by_identity)
        assert (mapped.entity_id, mapped.by) == ("p-2", "external_id:c4c_contact")
        # A name at the same company is a possible match: asked, never merged.
        maybe = tx.auto_merge(
            {"email": "other@example.com", "c4c_contact": "C-1"},
            by_identity=by_identity,
            possible=lambda: ["p-1"],
        )
        assert (maybe.entity_id, maybe.ask, maybe.candidates) == (None, True, ("p-1",))
        new = tx.auto_merge({"email": "new@example.com"}, by_identity=by_identity)
        assert (new.entity_id, new.ask) == (None, False)
        assert tx.external_ids("p-2") == {"c4c_contact": ["C-9"]}


# -- history, proposals and undo -----------------------------------------


def test_history_proposals_and_undo_are_shared_facilities(tmp_path: Path) -> None:
    service = _service(tmp_path)
    space = service.space(CONTACTS_ORG, asset=CARDS_SKILL)
    with space.transaction() as tx:
        stated = tx.add_observation(
            "p-1",
            {"title": "資深經理"},
            source_kind="user",
            source_date="2026-06-01",
            recorded_by="alice via telegram",
            change_id="c-1",
        )
        tx.set_provenance(
            "p-1",
            "title",
            source_kind="user",
            source_date="2026-06-01",
            observation_id=stated,
            set_by="alice via telegram",
            reason="said so",
        )
        tx.record(
            "c-1",
            "alice via telegram",
            "p-1",
            "field",
            field_name="title",
            old="經理",
            new="資深經理",
        )
        assert tx.propose(
            "c-1",
            "alice via telegram",
            "p-1",
            "title",
            "資深經理",
            "協理",
            source_kind="card",
            observation_id=None,
        )
        # The same value is not proposed twice.
        assert not tx.propose(
            "c-1", "a", "p-1", "title", "資深經理", " 協理", source_kind="card", observation_id=None
        )
    with service.space(CONTACTS_ORG, asset=MAIL_SKILL).transaction() as reading:
        (provenance,) = reading.field_provenance("p-1").values()
    assert (provenance.origin, provenance.set_by, provenance.source_kind) == (
        "human",
        "alice via telegram",
        "user",
    )
    assert [row["kind"] for row in space.history("p-1")] == ["proposal", "field"]
    assert len(space.proposals("p-1")) == 1
    reverted_fields: list[str] = []

    def field_row(tx: SpaceTx, item: sqlite3.Row, extra: dict[str, Any], new: str) -> bool:
        reverted_fields.append(item["field"])
        return True

    reverted, new_change = space.undo(
        "c-1", actor="alice via telegram", handlers={"field": field_row}
    )
    assert [row["kind"] for row in reverted] == ["proposal", "field"]
    assert reverted_fields == ["title"] and new_change.startswith("c-")
    assert space.proposals("p-1") == []
    # The person's statement in the undone change is withdrawn.
    assert space.observations("p-1") == []
    with pytest.raises(MemoryServiceError) as again:
        space.undo("c-1", actor="a")
    assert again.value.code == "change_already_undone"
    with pytest.raises(MemoryServiceError) as unknown:
        space.undo("c-nope", actor="a")
    assert unknown.value.code == "change_unknown"
    # A reader cannot undo.
    with pytest.raises(MemoryAccessError):
        service.space(CONTACTS_ORG, asset=MAIL_SKILL).undo("c-1", actor="a")


def test_each_actor_has_a_separate_memory(tmp_path: Path) -> None:
    alice, bob = _service(tmp_path, "alice"), _service(tmp_path, "bob")
    assert alice.path != bob.path
    assert alice.path == memory_path(tmp_path, "alice")
    assert alice.path.parent.parent == tmp_path / "memory"
    alice.space(CONTACTS_ORG, asset=CARDS_SKILL).add_observation(
        "p-1", {"name": "王小明"}, source_kind="card", source_date="2026-01-10", recorded_by="alice"
    )
    assert bob.space(CONTACTS_ORG, asset=CARDS_SKILL).observations() == []
    assert len(alice.space(CONTACTS_ORG, asset=CARDS_SKILL).observations()) == 1


def test_merge_rules_are_checked_as_data() -> None:
    with pytest.raises(ValidationError):
        MergeRules.model_validate({"rules_id": "x.v1", "trust": {"card": "document"}})
    with pytest.raises(ValidationError):
        FieldMergeRule.model_validate({"precedence": ["document", "user_stated"]})
    data = MERGE_RULES.model_dump(mode="json")
    assert MergeRules.model_validate_json(json.dumps(data)) == MERGE_RULES
