"""Accumulated memory M2: the Memory Service's generic sync state
(docs/phases/ACCUMULATED_MEMORY.md §3.3).

A space that declares the `sync_state` kind keeps, per `(source, key)`, how
far a source was processed: only forward, reset with history (restorable),
per actor. Synthetic data only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from capabilities.business_cards.manifest import CARDS_SKILL
from capabilities.business_cards.space import CONTACTS_ORG, DECLARATION, MERGE_RULES
from common.assets import AssetIdentity
from common.memory import MAX_SYNC_IDS, MemorySpaceDeclaration, MergeRules, SyncState
from memory.registry import MemoryRegistry
from memory.service import MemoryAccessError, MemoryService, MemoryServiceError, MemorySpace

MAIL_SKILL = AssetIdentity(namespace="engineering", name="mail-writer", version="1.0.0")
READINESS = AssetIdentity(namespace="engineering", name="readiness", version="1.0.0")
READINESS_RULES = MergeRules(rules_id="projects.readiness.merge.v1", trust={"user": "user_stated"})
SOURCE, KEY = "mail:Inbox", "wnc.com.tw"


def _registry() -> MemoryRegistry:
    found = MemoryRegistry()
    found.provide_rules(MERGE_RULES)
    found.provide_rules(READINESS_RULES)
    found.declare(CARDS_SKILL, [DECLARATION])
    found.declare(MAIL_SKILL, [MemorySpaceDeclaration(space=CONTACTS_ORG, role="reader")])
    # A space whose manager declares no sync state.
    found.declare(
        READINESS,
        [
            MemorySpaceDeclaration(
                space="projects/readiness",
                role="manager",
                kinds=("facts",),
                sensitivity="INTERNAL",
                retention="until_deleted",
                schema_ref="projects.readiness.item.v1",
                merge_rules=READINESS_RULES.rules_id,
            )
        ],
    )
    return found


def _cards(tmp_path: Path, actor: str = "alice") -> tuple[MemoryService, MemorySpace]:
    service = MemoryService.for_actor(tmp_path, actor, _registry())
    return service, service.space(CONTACTS_ORG, asset=CARDS_SKILL)


def _advance(
    space: MemorySpace, day: str, ids: list[str], version: str = "signature.1"
) -> SyncState:
    return space.advance_sync(
        SOURCE,
        KEY,
        last_message_date=day,
        message_ids=ids,
        extractor_version=version,
        actor="alice via web",
    )


def test_the_state_only_moves_forward(tmp_path: Path) -> None:
    _, space = _cards(tmp_path)
    assert space.sync_state(SOURCE, KEY) is None
    first = _advance(space, "2026-10-19T08:00:00+00:00", ["m1", "m2"])
    assert first.last_message_ids == ("m1", "m2")
    assert first.updated_by == "alice via web"
    with pytest.raises(MemoryServiceError) as backwards:
        _advance(space, "2026-10-18T08:00:00+00:00", ["m0"])
    assert backwards.value.code == "sync_state_backwards"
    # The same moment again: the ids join (newest first), nothing is lost.
    again = _advance(space, "2026-10-19T08:00:00+00:00", ["m3"])
    assert again.last_message_ids == ("m3", "m1", "m2")
    later = _advance(space, "2026-10-20T01:00:00+08:00", ["m4"])
    assert later.last_message_date == "2026-10-19T17:00:00+00:00"
    stored = space.sync_state(SOURCE, KEY)
    assert stored == later
    # The id set is bounded.
    many = _advance(space, "2026-10-21T00:00:00+00:00", [f"n{i}" for i in range(MAX_SYNC_IDS + 50)])
    assert len(many.last_message_ids) == MAX_SYNC_IDS
    assert many.last_message_ids[0] == "n0"
    with pytest.raises(MemoryServiceError) as bad:
        _advance(space, "yesterday", [])
    assert bad.value.code == "sync_date_invalid"


def test_an_extractor_change_needs_a_reset_first_and_a_reset_is_audited_and_restorable(
    tmp_path: Path,
) -> None:
    _, space = _cards(tmp_path)
    _advance(space, "2026-10-19T08:00:00+00:00", ["m1"])
    with pytest.raises(MemoryServiceError) as changed:
        _advance(space, "2026-10-20T08:00:00+00:00", ["m2"], version="signature.2")
    assert changed.value.code == "sync_extractor_changed"
    before = space.reset_sync(SOURCE, KEY, actor="alice via web", reason="manual")
    assert before is not None and before.last_message_ids == ("m1",)
    assert space.sync_state(SOURCE, KEY) is None
    history = space.sync_history(SOURCE, KEY)
    assert [entry.action for entry in history] == ["reset", "advance"]
    assert history[0].old == before and history[0].new is None
    assert history[0].reason == "manual" and history[0].actor == "alice via web"
    # The reset can be undone: the state before it comes back.
    restored = space.restore_sync(history[0].history_id, actor="alice via web")
    assert restored is not None and restored.last_message_ids == ("m1",)
    now = space.sync_state(SOURCE, KEY)
    assert now is not None and now.last_message_date == before.last_message_date
    assert space.sync_history(SOURCE, KEY)[0].action == "restore"
    with pytest.raises(MemoryServiceError) as unknown:
        space.restore_sync(9999, actor="a")
    assert unknown.value.code == "sync_history_unknown"
    # After a reset, the new extractor may start.
    space.reset_sync(SOURCE, KEY, actor="a", reason="extractor")
    fresh = _advance(space, "2026-10-20T08:00:00+00:00", ["m2"], version="signature.2")
    assert fresh.extractor_version == "signature.2"
    assert [s.key for s in space.sync_states()] == [KEY]


def test_each_actor_has_its_own_sync_state(tmp_path: Path) -> None:
    _, alice = _cards(tmp_path, "alice")
    _, bob = _cards(tmp_path, "bob")
    _advance(alice, "2026-10-19T08:00:00+00:00", ["m1"])
    assert bob.sync_state(SOURCE, KEY) is None
    assert bob.sync_history() == []


def test_sync_state_needs_the_declared_kind_and_a_contributor_to_write(tmp_path: Path) -> None:
    service, cards = _cards(tmp_path)
    _advance(cards, "2026-10-19T08:00:00+00:00", ["m1"])
    reader = service.space(CONTACTS_ORG, asset=MAIL_SKILL)
    assert reader.sync_state(SOURCE, KEY) is not None
    with pytest.raises(MemoryAccessError) as refused:
        reader.advance_sync(
            SOURCE,
            KEY,
            last_message_date="2026-10-20T00:00:00+00:00",
            message_ids=[],
            extractor_version="signature.1",
            actor="a",
        )
    assert refused.value.code == "memory_write_not_declared"
    with pytest.raises(MemoryAccessError):
        reader.reset_sync(SOURCE, KEY, actor="a", reason="x")
    # A space that does not declare `sync_state` has none.
    readiness = service.space("projects/readiness", asset=READINESS)
    with pytest.raises(MemoryAccessError) as undeclared:
        readiness.sync_state(SOURCE, KEY)
    assert undeclared.value.code == "memory_kind_not_declared"
    with pytest.raises(MemoryAccessError):
        readiness.advance_sync(
            SOURCE,
            KEY,
            last_message_date="2026-10-20T00:00:00+00:00",
            message_ids=[],
            extractor_version="v",
            actor="a",
        )
