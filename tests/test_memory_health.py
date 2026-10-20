"""The memory health check (accumulated memory M5, docs/phases/ACCUMULATED_MEMORY.md §7–§8).

The check reads one actor's memory database and writes only its findings:
stale contacts by the space's freshness rule (a fake clock), people who look
like one person, contradictory preferences (a fake internal model, asked
once per scope with at least two preferences, never when the check is off),
unused preferences, orphan spaces and sync states that stopped moving. Every
fix is the person's press: merge (undoable), 仍在職 / 已離職, stop a
preference. Real stores in a temporary workspace, no network.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import capabilities.business_cards.store as store_module
from capabilities.business_cards.contracts import PersonRef
from capabilities.business_cards.space import CONTACTS_ORG, MERGE_RULES
from capabilities.business_cards.store import CardStore
from memory.health import (
    MAX_RULES_PER_SCOPE,
    MAX_SCOPES,
    HealthFindings,
    HealthSettings,
    cutoff,
    load_settings,
    months_before,
    run_check,
    save_settings,
)
from memory.preferences import Preference, Preferences

NOW = datetime(2026, 10, 21, 3, 0, tzinfo=UTC)
COMPANY = "範例科技股份有限公司"
SCOPE = "skill:engineering/business-cards"


def _store(root: Path, actor: str = "alice") -> CardStore:
    return CardStore.for_actor(root, actor)


def _add(store: CardStore, name: str, when: date, **values: str) -> str:
    fields = {"name": name, "company": COMPANY, "title": "經理", **values}
    return store.add(
        fields, source="card", source_date=when, source_ref="", uncertain=(), actor="seed"
    ).person_id


def _state(manager: str) -> str:
    return "host" if manager == "host/memory" else "on"


def _check(store: CardStore, **changes: Any) -> Any:
    prefs = Preferences(store.memory)
    given: dict[str, Any] = {
        "preferences": prefs.listed(),
        "last_used": {},
        "entities": {CONTACTS_ORG: store},
        "manager_state": _state,
        "ask": None,
        "now": NOW,
    }
    given.update(changes)
    return run_check(store.memory, **given)


def _open(store: CardStore, kind: str | None = None) -> list[dict[str, Any]]:
    found = HealthFindings(store.memory).listed()
    return [item for item in found if kind is None or item["kind"] == kind]


# -- freshness: rules as data, a fake clock ---------------------------------------


def test_freshness_is_merge_rule_data() -> None:
    entity, sync = MERGE_RULES.freshness
    assert (entity.kind, entity.after, entity.entity) == ("entities", "P12M", "person")
    assert entity.question == "{name} 是否仍在職？" and entity.status == ("active",)
    assert (sync.kind, sync.after) == ("sync_state", "P30D")
    assert months_before(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert cutoff("P12M", date(2026, 10, 21)) == date(2025, 10, 21)
    assert cutoff("P30D", date(2026, 10, 21)) == date(2026, 9, 21)


def test_a_contact_not_seen_for_12_months_becomes_a_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    old = _add(store, "王小明", date(2025, 9, 1), email="wang@example.com")
    _add(store, "李新人", date(2026, 1, 10), email="lee@example.com")
    gone = _add(store, "陳離職", date(2024, 1, 1), email="chen@example.com")
    store.set_status(PersonRef(person_id=gone), "left", actor="seed", reason="", effective=None)

    report = _check(store)
    (stale,) = _open(store, "stale")
    assert report.found["stale"] == 1
    assert stale["subject"]["person_id"] == old
    assert stale["subject"]["question"] == "王小明 是否仍在職？"
    assert stale["subject"]["last_seen"] == "2025-09-01"
    # A year earlier on the clock nothing is stale yet.
    other = _store(tmp_path, "bob")
    _add(other, "王小明", date(2025, 9, 1), email="wang@example.com")
    assert not _check(other, now=datetime(2026, 6, 1, tzinfo=UTC)).found.get("stale")

    # The person's setting overrides the rule's period: 24 months.
    save_settings(store.memory, {"freshness_months": 24})
    report = _check(store)
    assert "stale" not in report.found and report.gone == 1 and _open(store, "stale") == []
    save_settings(store.memory, {"freshness_months": 0})
    assert _check(store).opened == 1 and len(_open(store, "stale")) == 1

    # 仍在職: the person's word is a new observation; fresh again.
    monkeypatch.setattr(store_module, "_clock", lambda: NOW)
    store.confirm_active(PersonRef(person_id=old), actor="alice via web", reason="test")
    assert _check(store).found.get("stale") is None
    assert _open(store, "stale") == []
    history = store.history(PersonRef(person_id=old), limit=5).history
    assert history[0].kind == "still_active" and history[0].actor == "alice via web"
    assert store.view(old).status == "active"


# -- duplicates and the merge -----------------------------------------------------


def test_duplicates_are_offered_and_merged_only_by_the_press(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = _add(store, "王小明", date(2026, 9, 1), email="hm@a.example", department="射頻部")
    second = _add(
        store,
        "王小明",
        date(2026, 9, 2),
        email="hm@b.example",
        department="業務部",
        mobile="0912-000-111",
    )
    boss = _add(store, "張主管", date(2026, 9, 1), email="boss@a.example")
    store.set_line(
        PersonRef(person_id=second),
        PersonRef(person_id=boss),
        evidence_kind="user",
        evidence_ref="said so",
        confidence=1.0,
        inferred=False,
        actor="seed",
    )
    third = _add(store, "林同信", date(2026, 9, 1), email="lin@a.example")
    store.edit(PersonRef(person_id=third), {"email": "hm@a.example"}, actor="seed", reason="")
    assert len(store.list_people(company="", source="", status="any", limit=50)[0]) == 4

    _check(store)
    pairs = {item["subject"]["reason"]: item for item in _open(store, "duplicate")}
    assert set(pairs) == {"same_name_company", "same_email"}
    named = pairs["same_name_company"]["subject"]["people"]
    assert {p["person_id"] for p in named} == {first, second}
    assert {p["person_id"] for p in pairs["same_email"]["subject"]["people"]} == {first, third}
    # Found, never merged by the check.
    assert len(store.list_people(company="", source="", status="any", limit=50)[0]) == 4

    change = store.merge_people(first, second, actor="alice via web", reason="test")
    kept = store.view(first)
    assert kept.mobile == "0912-000-111" and kept.manager == "張主管"
    with pytest.raises(store_module.CardStoreError):
        store.view(second)
    report = _check(store)
    assert report.found.get("duplicate") == 1  # the same-email pair is still there
    assert [i["subject"]["reason"] for i in _open(store, "duplicate")] == ["same_email"]

    reverted, _ = store.undo(change, actor="alice via web")
    assert {item.kind for item in reverted} >= {"merged_away", "field"}
    assert store.view(second).mobile == "0912-000-111" and store.view(second).manager == "張主管"
    assert store.view(first).mobile == "" and store.view(first).manager == ""
    _check(store)
    # The undone merge's pair is found again, as the same finding.
    assert {i["subject"]["reason"] for i in _open(store, "duplicate")} == {
        "same_name_company",
        "same_email",
    }


# -- contradictions: a fake internal model, bounded --------------------------------


class _Asker:
    def __init__(self, answer: Any = None, fail: bool = False) -> None:
        self.calls: list[tuple[str, list[str]]] = []
        self.answer = answer
        self.fail = fail

    def __call__(self, scope: str, rules: list[Preference]) -> list[tuple[str, str, str]]:
        self.calls.append((scope, [item.text for item in rules]))
        if self.fail:
            raise RuntimeError("model_http_error")
        if self.answer is not None:
            return list(self.answer(rules))
        return [(rules[0].preference_id, rules[1].preference_id, "一個要英文，一個要中文")]


def test_contradictions_are_asked_once_per_scope_with_two_or_more(tmp_path: Path) -> None:
    store = _store(tmp_path)
    prefs = Preferences(store.memory)
    a, _ = prefs.save(SCOPE, "回覆一律用英文", actor="alice via web", scope_label="名片／組織圖")
    b, _ = prefs.save(SCOPE, "信件內容請寫中文", actor="alice via web", scope_label="名片／組織圖")
    prefs.save("skill:engineering/weekly", "週報用條列", actor="alice via web")
    asker = _Asker()
    report = _check(store, ask=asker)
    assert [scope for scope, _ in asker.calls] == [SCOPE]  # the one-preference scope is not asked
    assert report.model == "used" and report.model_calls == 1
    (found,) = _open(store, "contradiction")
    ids = {found["subject"]["a"]["preference_id"], found["subject"]["b"]["preference_id"]}
    assert ids == {a.preference_id, b.preference_id}
    assert found["subject"]["why"] == "一個要英文，一個要中文"

    # Without the internal model the question is skipped and the finding stays.
    report = _check(store, ask=None)
    assert report.model == "unavailable" and "contradiction" in report.skipped
    assert len(_open(store, "contradiction")) == 1
    # A failed question leaves it too.
    assert _check(store, ask=_Asker(fail=True)).model == "failed"
    assert len(_open(store, "contradiction")) == 1
    # The model says none: it goes.
    assert _check(store, ask=_Asker(answer=lambda rules: [])).gone == 1


def test_a_pair_the_deterministic_check_finds_is_not_reported_again(tmp_path: Path) -> None:
    store = _store(tmp_path)
    prefs = Preferences(store.memory)
    prefs.save(SCOPE, "執行時不需要問是否包含在職人員", actor="alice via web")
    prefs.save(SCOPE, "執行時要問是否包含在職人員", actor="alice via web", keep_conflicts=True)
    asker = _Asker()
    _check(store, ask=asker)
    assert len(asker.calls) == 1 and _open(store, "contradiction") == []


def test_no_model_call_when_off_or_fewer_than_two(tmp_path: Path) -> None:
    store = _store(tmp_path)
    prefs = Preferences(store.memory)
    prefs.save(SCOPE, "回覆一律用英文", actor="alice via web")
    asker = _Asker()
    report = _check(store, ask=asker)
    assert asker.calls == [] and report.model == "not_needed"
    prefs.save(SCOPE, "信件內容請寫中文", actor="alice via web")
    save_settings(store.memory, {"enabled": False})
    report = _check(store, ask=asker)
    assert asker.calls == [] and report.model == "off" and not report.enabled
    assert _open(store) == []


def test_the_question_is_bounded(tmp_path: Path) -> None:
    store = _store(tmp_path)
    prefs = Preferences(store.memory)
    for number in range(MAX_SCOPES + 2):
        for rule in ("規則甲", "規則乙"):
            prefs.save(f"skill:engineering/s{number}", f"{rule}{number}", actor="a via web")
    for number in range(20):
        prefs.save("skill:engineering/big", f"大量規則{number:02d}" + "x" * number, actor="a")
    asker = _Asker(answer=lambda rules: [])
    _check(store, ask=asker)
    assert len(asker.calls) == MAX_SCOPES
    assert max(len(rules) for _, rules in asker.calls) <= MAX_RULES_PER_SCOPE


# -- unused preferences, orphans, stale sync ---------------------------------------


def test_unused_preferences_by_last_use_and_a_kept_one_is_asked_again_later(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    prefs = Preferences(store.memory)
    used, _ = prefs.save(SCOPE, "回覆一律用英文", actor="a via web")
    idle, _ = prefs.save("skill:engineering/weekly", "週報用條列", actor="a via web")
    later = datetime.now(UTC) + timedelta(days=100)
    recent = (later - timedelta(days=3)).isoformat(timespec="seconds")
    _check(store, now=later, last_used={used.preference_id: recent})
    (found,) = _open(store, "unused")
    assert found["subject"]["preference_id"] == idle.preference_id
    # Recorded uses count too (Telegram answers, M5).
    prefs.mark_used([idle.preference_id], at=recent)
    assert prefs.last_used()[idle.preference_id] == recent
    assert _check(store, now=later, last_used=prefs.last_used()).found.get("unused", 0) == 1
    # 保留: dismissed, not asked again until another `unused_days` pass.
    kept_at = later + timedelta(days=200)
    _check(store, now=kept_at, last_used={})
    for item in _open(store, "unused"):
        HealthFindings(store.memory).close(
            item["finding_id"], "dismissed", action="keep", actor="a", at=kept_at.isoformat()
        )
    _check(store, now=kept_at + timedelta(days=30), last_used={})
    assert _open(store, "unused") == []
    unknown = _check(store, now=kept_at + timedelta(days=30), last_used=None)
    assert "unused" in unknown.skipped
    _check(store, now=kept_at + timedelta(days=91), last_used={})
    assert len(_open(store, "unused")) == 2


def test_orphan_spaces_and_stale_sync_states(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.memory.owned(CONTACTS_ORG).advance_sync(
        "mail:Inbox",
        "wnc.com.tw",
        last_message_date="2026-10-19T08:00:00+00:00",
        message_ids=["m-1"],
        extractor_version="sig-3",
        actor="alice via web",
    )
    soon = datetime.now(UTC) + timedelta(days=5)
    assert "stale_sync" not in _check(store, now=soon).found
    late = datetime.now(UTC) + timedelta(days=40)
    report = _check(
        store,
        now=late,
        manager_state=lambda m: "missing" if m == "engineering/business-cards" else "host",
    )
    assert report.found["orphan"] == 1 and report.found["stale_sync"] == 1
    (orphan,) = _open(store, "orphan")
    assert orphan["space"] == CONTACTS_ORG and orphan["subject"]["manager"] == (
        "engineering/business-cards"
    )
    (stale,) = _open(store, "stale_sync")
    assert stale["subject"]["key"] == "wnc.com.tw" and stale["subject"]["source"] == "mail:Inbox"


# -- the check never changes the memory ---------------------------------------------


def _snapshot(path: Path) -> dict[str, list[Any]]:
    with closing(sqlite3.connect(path)) as con:
        tables = [
            row[0]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            if row[0] not in ("health_findings", "meta", "sqlite_sequence")
        ]
        return {name: sorted(map(repr, con.execute(f"SELECT * FROM {name}"))) for name in tables}


def test_no_data_changes_without_a_press(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, "王小明", date(2025, 1, 1), email="hm@a.example", department="射頻部")
    _add(store, "王小明", date(2025, 1, 2), email="hm@b.example", department="業務部")
    prefs = Preferences(store.memory)
    prefs.save(SCOPE, "回覆一律用英文", actor="a via web")
    prefs.save(SCOPE, "信件內容請寫中文", actor="a via web")
    before = _snapshot(store.memory.path)
    report = _check(
        store,
        ask=_Asker(),
        now=datetime.now(UTC) + timedelta(days=400),
        manager_state=lambda m: "missing",
    )
    assert set(report.found) >= {"stale", "duplicate", "contradiction", "unused", "orphan"}
    assert _snapshot(store.memory.path) == before


def test_settings_round_trip_and_keep_keys_they_do_not_know(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert load_settings(store.memory) == HealthSettings()
    store.memory.set_meta("health_settings", json.dumps({"later_key": "kept"}))
    saved = save_settings(store.memory, {"enabled": False, "unused_days": 30})
    assert saved == HealthSettings(enabled=False, freshness_months=0, unused_days=30)
    raw = json.loads(store.memory.get_meta("health_settings") or "{}")
    assert raw["later_key"] == "kept"
    for wrong in ({"unused_days": 0}, {"freshness_months": 200}, {"enabled": "yes"}, {"x": 1}):
        with pytest.raises(Exception, match="health_settings_invalid"):
            save_settings(store.memory, wrong)
    assert load_settings(store.memory) == saved


def test_each_actor_has_their_own_findings(tmp_path: Path) -> None:
    alice, bob = _store(tmp_path, "alice"), _store(tmp_path, "bob")
    _add(alice, "王小明", date(2024, 1, 1), email="hm@a.example")
    _check(alice)
    _check(bob)
    assert len(_open(alice, "stale")) == 1 and _open(bob) == []
    assert alice.memory.path != bob.memory.path
    finding = _open(alice, "stale")[0]["finding_id"]
    assert HealthFindings(bob.memory).get(finding) is None
