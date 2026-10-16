"""Suggested Skills S2: Reviews cards, Ignore / Snooze, sensitivity and settings.

`docs/phases/SKILL_SUGGESTIONS.md` sections 7.1, 8, 11 and 13 (row S2), with
the owner decisions of 2026-10-16: Normal is 3 requests in 3 sessions over 2
days with at most 3 new cards a night; each member sees only their own
suggestions; the model groups. Every model here is a fake; nothing reaches a
gateway or the network.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture
from test_skill_suggestions import (
    ME,
    NOW,
    TASKS,
    _by_task,
    _four_tasks,
    _Grouper,
    _run,
    _session,
    _weekly,
)

from host_runtime import experience_proposals
from host_runtime.conversations import ConversationRecord
from host_runtime.experience import (
    ExperienceSettings,
    ExperienceStore,
    load_settings,
    save_settings,
)
from host_runtime.experience_proposals import (
    ProposalError,
    ProposalStore,
    ReviewProposal,
    make_cards,
)
from host_runtime.experience_review import run_review
from host_runtime.skill_suggestions import (
    SENSITIVITY,
    SuggestionPass,
    SuggestionStore,
    qualifies,
    sensitivity_rows,
    suggest_for_runtime,
    thresholds_for,
)
from host_runtime.web import AgentWeb

AMY = "amy.lin"
SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "skill-suggestion-ui"


def _all_items(task: str) -> _Grouper:
    """A model that puts every R and G item of the prompt in one group."""

    def reply(prompt: str) -> Any:
        ids = re.findall(r"^([RG]\d+) ", prompt, flags=re.MULTILINE)
        return {"groups": [{"ids": ids, "task": task}]}

    return _Grouper(reply)


def _night(
    workspace: Path,
    records: list[ConversationRecord],
    model: _Grouper,
    *,
    actor: str = ME,
    now: datetime = NOW,
    settings: ExperienceSettings | None = None,
) -> SuggestionPass:
    """One nightly pass for one actor, then its cards, as the host does."""
    found = _run(workspace, records, model, actor=actor, now=now, settings=settings)
    return make_cards(ProposalStore(workspace, owner=ME), found)


def _cards(workspace: Path, actor: str = ME) -> list[ReviewProposal]:
    return [
        p for p in ProposalStore(workspace, owner=ME).all(actor) if p.kind == "skill_suggestion"
    ]


def _tree(root: Path) -> dict[str, float]:
    if not root.is_dir():
        return {}
    return {str(p.relative_to(root)): p.stat().st_mtime for p in root.rglob("*")}


# -- cards from the nightly pass ------------------------------------------------------


def test_a_qualified_group_becomes_one_card_with_its_evidence(tmp_path: Path) -> None:
    records = [_weekly(5, "s1", 30), _weekly(4, "s2", 31), _weekly(3, "s3", 32)]
    passed = _night(tmp_path, records, _all_items("整理週報並寄給主管"))
    (item,) = passed.suggestions
    assert item.status == "qualified" and item.card == f"suggest-{item.group_id}"
    assert item.card_note == "card created" and passed.counts.cards_created == 1
    (card,) = _cards(tmp_path)
    assert card.actor == ME and card.status == "proposed" and card.kind == "skill_suggestion"
    shown = card.suggestion
    assert shown is not None and shown.task == "整理週報並寄給主管"
    assert (shown.requests, shown.sessions, shown.days) == (3, 3, 3)
    assert "週報" in shown.matched_words and shown.tool_shape[0] == "files__read"
    assert [(e.session_id, e.message_id) for e in shown.evidence] == [
        ("s1", "s1-u"),
        ("s2", "s2-u"),
        ("s3", "s3-u"),
    ]
    # The card keeps ids and dates, never request text: Agent Web cuts the
    # excerpts from the conversations when it lists the card.
    assert all(e.date and e.excerpt == "" for e in shown.evidence)
    stored = sqlite3.connect(tmp_path / "experience.sqlite").execute("SELECT record FROM proposals")
    assert "2026_W3" not in "".join(row[0] for row in stored)  # the request text


def test_a_second_night_adds_no_duplicate_and_new_evidence_updates_the_open_card(
    tmp_path: Path,
) -> None:
    model = _all_items("整理週報")
    records = [_weekly(5, "s1", 30), _weekly(4, "s2", 31), _weekly(3, "s3", 32)]
    _night(tmp_path, records, model)
    again = _night(tmp_path, records, model, now=NOW + timedelta(days=1))
    assert again.suggestions == () and len(_cards(tmp_path)) == 1
    records += [_weekly(2, "s4", 33), _weekly(1, "s5", 34)]
    grown = _night(tmp_path, records, model)
    (item,) = grown.suggestions
    assert item.status == "updated" and item.card_note == "card updated: seen 2 more times"
    (card,) = _cards(tmp_path)
    assert card.suggestion is not None and card.suggestion.seen_more == 2
    assert card.suggestion.requests == 5 and len(card.suggestion.evidence) == 5
    assert grown.counts.cards_updated == 1 and grown.counts.cards_created == 0


def test_at_most_three_new_cards_a_night_and_the_fourth_comes_the_next(tmp_path: Path) -> None:
    model = _Grouper(_by_task)
    first = _night(tmp_path, _four_tasks(), model)
    assert len(_cards(tmp_path)) == 3 and first.counts.cards_created == 3
    assert [i.card for i in first.suggestions if i.status == "deferred"] == [None]
    _night(tmp_path, _four_tasks(), model, now=NOW + timedelta(days=1))
    assert len(_cards(tmp_path)) == len(TASKS) == 4


def test_a_dry_run_or_suggestions_off_make_no_card(tmp_path: Path) -> None:
    records = [_weekly(5, "s1", 30), _weekly(4, "s2", 31), _weekly(3, "s3", 32)]
    model = _all_items("整理週報")
    tmp_path.mkdir(exist_ok=True)
    ProposalStore(tmp_path)
    dry = make_cards(ProposalStore(tmp_path), _run(tmp_path, records, model, dry_run=True))
    assert dry.suggestions[0].card is None and _cards(tmp_path) == []
    off = _night(tmp_path, records, model, settings=ExperienceSettings(suggestions=False))
    assert not off.counts.enabled and _cards(tmp_path) == []


def test_the_report_marks_which_groups_became_cards(tmp_path: Path) -> None:
    records = [_weekly(5, "s1", 30), _weekly(4, "s2", 31), _weekly(3, "s3", 32)]
    records += [_session("j1", "list open Jira bugs", 5), _session("j2", "list open Jira bugs", 4)]
    model = _Grouper(
        lambda prompt: {
            "groups": [
                {"ids": [k for k in re.findall(r"^(R\d+) .*週報", prompt, re.M)], "task": "週報"},
                {"ids": [k for k in re.findall(r"^(R\d+) .*Jira", prompt, re.M)], "task": "Jira"},
            ]
        }
    )
    passed = _night(tmp_path, records, model)

    class _NoCases:
        def generate(self, request: Any) -> Any:
            raise AssertionError("no failure cases, no review call")

        def stream(self, request: Any) -> Iterator[Any]:
            raise NotImplementedError

    run_review(
        ExperienceStore(tmp_path),
        _NoCases(),
        "m",
        lambda domain: "",
        workspace=tmp_path,
        suggestions=passed,
    )
    (saved,) = (tmp_path / "experience-reviews").glob("review-*.json")
    data = json.loads(saved.read_text(encoding="utf-8"))
    by_status = {s["status"]: s for s in data["suggestions"]}
    assert by_status["qualified"]["card"].startswith("suggest-sg-")
    assert by_status["qualified"]["card_note"] == "card created"
    assert by_status["considered"]["card"] is None
    assert data["suggestion_counts"]["cards_created"] == 1
    markdown = saved.with_suffix(".md").read_text(encoding="utf-8")
    assert "- Card: suggest-sg-" in markdown and "(card created)" in markdown
    assert "Reviews cards: 1 new, 0 updated" in markdown
    # The counts carry no request text.
    assert "週報" not in json.dumps(data["suggestion_counts"], ensure_ascii=False)


# -- actors -----------------------------------------------------------------------------


def test_each_actor_lists_and_decides_only_their_own_cards(tmp_path: Path) -> None:
    mine = [_weekly(5, "s1", 30), _weekly(4, "s2", 31), _weekly(3, "s3", 32)]
    hers = [_weekly(5, "a1", 30, AMY), _weekly(4, "a2", 31, AMY), _weekly(3, "a3", 32, AMY)]
    _night(tmp_path, mine + hers, _all_items("整理週報"))
    _night(tmp_path, mine + hers, _all_items("Amy 的週報"), actor=AMY)
    store = ProposalStore(tmp_path, owner=ME)
    (my_card,) = _cards(tmp_path, ME)
    (her_card,) = _cards(tmp_path, AMY)
    assert my_card.actor == ME and her_card.actor == AMY
    assert {e.session_id for e in my_card.suggestion.evidence} == {"s1", "s2", "s3"}  # type: ignore[union-attr]
    # Another person's card is answered exactly like a missing one, by id too.
    for action in ("snooze", "reject", "reopen", "accept"):
        with pytest.raises(ProposalError) as raised:
            store.decide(her_card.proposal_id, action, ME)
        assert raised.value.code == "unknown_proposal"
    with pytest.raises(ProposalError):
        store.get(her_card.proposal_id, ME)
    assert store.get(her_card.proposal_id, AMY).status == "proposed"


def test_rows_from_before_s2_are_migrated_and_stay_the_owners(tmp_path: Path) -> None:
    """An S1-era store: no actor column, a failure-review proposal row."""
    with sqlite3.connect(tmp_path / "experience.sqlite") as conn:
        conn.execute(
            "CREATE TABLE proposals (proposal_id TEXT PRIMARY KEY,"
            " created_at TEXT NOT NULL, record TEXT NOT NULL)"
        )
        old = {
            "proposal_id": "review-1-1",
            "review_id": "review-1",
            "created_at": "2026-10-10T02:00:00+00:00",
            "group": "knowledge|x|-",
            "kind": "rule_edit",
            "text": "add a rule",
        }
        conn.execute(
            "INSERT INTO proposals VALUES (?, ?, ?)",
            ("review-1-1", old["created_at"], json.dumps(old)),
        )
    store = ProposalStore(tmp_path, owner=ME)
    columns = {
        row[1]
        for row in sqlite3.connect(tmp_path / "experience.sqlite").execute(
            "PRAGMA table_info(proposals)"
        )
    }
    assert "actor" in columns
    ProposalStore(tmp_path, owner=ME)  # a second open migrates nothing twice
    (record,) = store.all(ME)
    assert record.actor is None and record.text == "add a rule"
    assert store.all(AMY) == []  # the device owner's, not anybody's
    assert ProposalStore(tmp_path).all(AMY) == [record]  # no owner given: as before S2
    # The failure review's Reject still needs a reason.
    with pytest.raises(ProposalError) as raised:
        store.decide("review-1-1", "reject", ME)
    assert raised.value.code == "reason_required"


# -- Ignore, Snooze and the way back ----------------------------------------------------


def _one_card(workspace: Path) -> tuple[ReviewProposal, list[ConversationRecord], _Grouper]:
    records = [_weekly(9, "s1", 30), _weekly(8, "s2", 31), _weekly(7, "s3", 32)]
    model = _all_items("整理週報")
    _night(workspace, records, model, now=NOW - timedelta(days=6))
    (card,) = _cards(workspace)
    return card, records, model


def _ignore(workspace: Path, card: ReviewProposal, **body: Any) -> ReviewProposal:
    """What the Agent Web route does: the decision, then the group. The
    group is marked at the simulated time of the decision (the card was made
    six days before NOW), so the later test requests come after it."""
    decided = ProposalStore(workspace, owner=ME).decide(
        card.proposal_id, "reject", ME, body.get("reason"), body.get("reason_code")
    )
    assert decided.suggestion is not None and decided.decided_at is not None
    at = (NOW - timedelta(days=6) + timedelta(hours=1)).isoformat(timespec="seconds")
    SuggestionStore(workspace).set_ignored(ME, decided.suggestion.group_id, True, at=at)
    return decided


def test_ignore_needs_no_reason_and_keeps_a_quick_pick_and_a_comment(tmp_path: Path) -> None:
    card, _, _ = _one_card(tmp_path)
    bare = _ignore(tmp_path, card)
    assert bare.status == "rejected" and bare.reason is None and bare.reason_code is None
    store = ProposalStore(tmp_path, owner=ME)
    store.decide(card.proposal_id, "reopen", ME)
    picked = _ignore(tmp_path, card, reason_code="one_off", reason=" only for that audit ")
    assert (picked.reason_code, picked.reason) == ("one_off", "only for that audit")
    store.decide(card.proposal_id, "reopen", ME)
    with pytest.raises(ProposalError) as raised:
        store.decide(card.proposal_id, "reject", ME, reason_code="because")
    assert raised.value.code == "unknown_reason_code"
    # A suggestion has no draft in S2: it can never be accepted or done.
    for action in ("accept", "done"):
        with pytest.raises(ProposalError) as raised:
            store.decide(card.proposal_id, action, ME)
        assert raised.value.code == "suggestion_has_no_draft_yet"


def test_an_ignored_group_returns_only_after_enough_new_requests(tmp_path: Path) -> None:
    card, records, model = _one_card(tmp_path)
    _ignore(tmp_path, card, reason_code="wrong_grouping")
    group_id = card.suggestion.group_id  # type: ignore[union-attr]
    assert SuggestionStore(tmp_path).load(ME).groups[group_id].status == "ignored"
    # Two new requests after the rejection: not enough (Normal needs 3 in 3
    # sessions over 2 days); the report says why, and no card appears.
    records += [_weekly(3, "s4", 33), _weekly(2, "s5", 34)]
    later = _night(tmp_path, records, model)
    (item,) = later.suggestions
    assert item.status == "considered" and item.group_id == group_id
    assert "ignored on" in item.reason and "2 new requests" in item.reason
    assert [c.status for c in _cards(tmp_path)] == ["rejected"]
    # The third new request: proposed again as a new card; the old stays rejected.
    records.append(_weekly(1, "s6", 35))
    back = _night(tmp_path, records, model)
    (item,) = back.suggestions
    assert item.status == "qualified" and item.reason == "proposed again: 3 new requests"
    assert item.card == f"suggest-{group_id}-2"
    assert item.card_note == "card created again after it was ignored"
    statuses = {c.proposal_id: c.status for c in _cards(tmp_path)}
    assert statuses == {card.proposal_id: "rejected", f"suggest-{group_id}-2": "proposed"}
    assert SuggestionStore(tmp_path).load(ME).groups[group_id].status == "reported"


def test_reopening_an_ignored_card_stops_the_group_from_coming_back_twice(
    tmp_path: Path,
) -> None:
    card, _, _ = _one_card(tmp_path)
    decided = _ignore(tmp_path, card)
    assert decided.suggestion is not None
    ProposalStore(tmp_path, owner=ME).decide(card.proposal_id, "reopen", ME)
    SuggestionStore(tmp_path).set_ignored(
        ME,
        decided.suggestion.group_id,
        False,
        at="2026-10-16T00:00:00+00:00",
    )
    group = SuggestionStore(tmp_path).load(ME).groups[decided.suggestion.group_id]
    assert group.status == "reported" and group.ignored_request_ids == ()
    # Another actor cannot touch the group.
    assert not SuggestionStore(tmp_path).set_ignored(AMY, group.group_id, True, at="x")


def test_snooze_hides_the_card_for_seven_days_then_it_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    card, _, _ = _one_card(tmp_path)
    store = ProposalStore(tmp_path, owner=ME)
    snoozed = store.decide(card.proposal_id, "snooze", ME)
    assert snoozed.status == "snoozed" and snoozed.snooze_until is not None
    assert [c.status for c in _cards(tmp_path)] == ["snoozed"]
    later = datetime.now(UTC) + timedelta(days=6, hours=23)
    monkeypatch.setattr(experience_proposals, "_now", lambda: later)
    assert [c.status for c in _cards(tmp_path)] == ["snoozed"]
    after = datetime.now(UTC) + timedelta(days=7, minutes=1)
    monkeypatch.setattr(experience_proposals, "_now", lambda: after)
    assert [c.status for c in _cards(tmp_path)] == ["proposed"]


# -- sensitivity and settings -----------------------------------------------------------


def test_sensitivity_rows_follow_the_design_table() -> None:
    assert {k: (t.requests, t.sessions, t.days, t.per_night) for k, t in SENSITIVITY.items()} == {
        "low": (4, 3, 3, 1),
        "normal": (3, 3, 2, 3),
        "high": (2, 2, 1, 5),
    }
    assert thresholds_for("unknown") == SENSITIVITY["normal"]
    words = {row["key"]: row["describe"] for row in sensitivity_rows()}
    assert words["normal"] == "3 times in 3 conversations over at least 2 days, up to 3 a night"
    assert words["high"] == "2 times in 2 conversations, up to 5 a night"
    assert words["low"] == "4 times in 3 conversations over at least 3 days, up to 1 a night"


def test_sensitivity_changes_what_qualifies_and_how_many_cards_a_night(tmp_path: Path) -> None:
    two = [_weekly(5, "s1", 30), _weekly(4, "s2", 31)]
    model = _all_items("整理週報")
    normal = _night(tmp_path / "n", two, model)
    assert [i.status for i in normal.suggestions] == ["considered"]
    assert "needs 3 in 3 sessions over 2 days" in normal.suggestions[0].reason
    high = _night(
        tmp_path / "h",
        two,
        model,
        settings=ExperienceSettings(suggestion_sensitivity="high"),
    )
    assert [i.status for i in high.suggestions] == ["qualified"]
    assert high.counts.sensitivity == "high" and len(_cards(tmp_path / "h")) == 1
    assert _cards(tmp_path / "h")[0].suggestion.sensitivity == "high"  # type: ignore[union-attr]
    # Two requests inside one session never qualify, even on High.
    one_session = [two[0].model_copy(update={"session_id": "s2"}), two[1]]
    assert not qualifies([r for r in _requests(one_session)], SENSITIVITY["high"])
    three = [_weekly(5, "s1", 30), _weekly(4, "s2", 31), _weekly(3, "s3", 32)]
    low = _night(
        tmp_path / "l", three, model, settings=ExperienceSettings(suggestion_sensitivity="low")
    )
    assert [i.status for i in low.suggestions] == ["considered"]
    assert "needs 4 in 3 sessions over 3 days" in low.suggestions[0].reason
    # Low: one card a night.
    low_four = _night(
        tmp_path / "l4",
        [
            _session(f"{key}{n}", f"{text} {n}", day, tools=tools)
            for key, text, tools in TASKS
            for n, day in enumerate((6, 5, 4, 3))
        ],
        _Grouper(_by_task),
        settings=ExperienceSettings(suggestion_sensitivity="low"),
    )
    assert sorted(i.status for i in low_four.suggestions) == [
        "deferred",
        "deferred",
        "deferred",
        "qualified",
    ]


def _requests(records: list[ConversationRecord]) -> list[Any]:
    from host_runtime.skill_suggestions import from_reuse

    return from_reuse(records, ME, retention_days=30, now=NOW).requests


def test_settings_round_trip_and_keep_the_fields_a_form_did_not_send(tmp_path: Path) -> None:
    from host_runtime.experience import SETTINGS_FILE

    save_settings(tmp_path, ExperienceSettings(retention_days=14, nightly=False))
    web = _bare_web(tmp_path)
    shown = AgentWeb.update_experience_settings(
        web,
        {"suggestions": False, "suggestion_sensitivity": "low", "suggestion_max_requests": 50},
    )
    assert shown["ok"] and shown["settings"]["suggestion_sensitivity"] == "low"
    assert [row["key"] for row in shown["sensitivities"]] == ["low", "normal", "high"]
    saved = json.loads((tmp_path / SETTINGS_FILE).read_text(encoding="utf-8"))
    assert saved == {
        "retention_days": 14,
        "nightly": False,
        "suggestions": False,
        "suggestion_max_requests": 50,
        "suggestion_sensitivity": "low",
    }
    # The two older fields alone (an older page) keep the suggestion fields.
    AgentWeb.update_experience_settings(web, {"retention_days": 20, "nightly": True})
    loaded = load_settings(tmp_path)
    assert (loaded.retention_days, loaded.suggestion_sensitivity, loaded.suggestions) == (
        20,
        "low",
        False,
    )
    bad = AgentWeb.update_experience_settings(web, {"suggestion_sensitivity": "max"})
    assert bad == {"ok": False, "code": "experience_settings_invalid"}
    # An S1-era file (no sensitivity) reads as Normal.
    (tmp_path / SETTINGS_FILE).write_text('{"retention_days": 30}', encoding="utf-8")
    assert load_settings(tmp_path).suggestion_sensitivity == "normal"


def test_a_changed_sensitivity_applies_to_the_next_pass_without_a_restart(tmp_path: Path) -> None:
    records = [_weekly(5, "s1", 30), _weekly(4, "s2", 31)]

    def conversations(actor: str, limit: int) -> tuple[ConversationRecord, ...]:
        return tuple(r for r in records if r.actor == actor)

    from types import SimpleNamespace

    runtime = SimpleNamespace(
        actor=ME,
        layout=SimpleNamespace(
            workspace_root=tmp_path, workflows=tmp_path / "workflows", skills=tmp_path / "skills"
        ),
        state=SimpleNamespace(conversations=conversations),
    )
    model = _all_items("整理週報")
    first = suggest_for_runtime(runtime, model, "m", now=NOW)
    assert [i.status for i in first.suggestions] == ["considered"]
    save_settings(tmp_path, ExperienceSettings(suggestion_sensitivity="high"))
    second = suggest_for_runtime(runtime, model, "m", now=NOW)
    assert [i.status for i in second.suggestions] == ["qualified"]


# -- Agent Web --------------------------------------------------------------------------


def _bare_web(workspace: Path) -> Any:
    from types import SimpleNamespace

    runtime = SimpleNamespace(actor=ME, layout=SimpleNamespace(workspace_root=workspace))
    web = SimpleNamespace(runtime=runtime)
    web._experience_store = lambda: AgentWeb._experience_store(web)  # type: ignore[arg-type]
    web.experience = lambda: AgentWeb.experience(web)  # type: ignore[arg-type]
    return web


def _seed(web: AgentWeb) -> tuple[str, str]:
    """A card for this Agent Web's person and one for another member, each
    from their own conversations saved in the Host state."""
    workspace = web.runtime.layout.workspace_root
    me = web.runtime.actor
    mine = [_weekly(5, "s1", 30, me), _weekly(4, "s2", 31, me), _weekly(3, "s3", 32, me)]
    hers = [_weekly(5, "a1", 30, AMY), _weekly(4, "a2", 31, AMY), _weekly(3, "a3", 32, AMY)]
    for record in mine + hers:
        web.runtime.state.create_conversation(record)
    now = datetime.now(UTC)
    for actor, records, task in ((me, mine, "整理週報並寄給主管"), (AMY, hers, "Amy 的週報")):
        found = _run(workspace, records, _all_items(task), actor=actor, now=now)
        make_cards(ProposalStore(workspace, owner=me), found)
    (my_card,) = _cards(workspace, me)
    store = ProposalStore(workspace, owner=me)
    (her_card,) = [p for p in store.all(AMY) if p.actor == AMY]
    return my_card.proposal_id, her_card.proposal_id


def _post(server: Any, path: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_address[1]}{path}",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {server.token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as reply:
        loaded: dict[str, Any] = json.loads(reply.read())
    return loaded


def _get(server: Any, path: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_address[1]}{path}",
        headers={"Authorization": f"Bearer {server.token}"},
    )
    with urllib.request.urlopen(request, timeout=30) as reply:
        loaded: dict[str, Any] = json.loads(reply.read())
    return loaded


def test_agent_web_lists_and_decides_only_its_persons_suggestions(served: Any) -> None:  # noqa: F811
    web, server, _recorder, _ = served
    skills, workflows = web.runtime.layout.skills, web.runtime.layout.workflows
    before = (
        _tree(skills) if skills.is_dir() else {},
        _tree(workflows) if workflows.is_dir() else {},
    )
    mine, hers = _seed(web)
    listed = _get(server, "/api/reviews")
    ids = [p["proposal_id"] for p in listed["proposals"]]
    assert mine in ids and hers not in ids
    assert listed["counts"]["proposed"] == 1
    (shown,) = [p for p in listed["proposals"] if p["proposal_id"] == mine]
    evidence = shown["suggestion"]["evidence"]
    assert [e["session_id"] for e in evidence] == ["s1", "s2", "s3"]
    assert all("週報" in e["excerpt"] and not e["gone"] for e in evidence)
    # A deleted conversation drops out of the evidence (its text is not kept).
    assert web.runtime.state.delete_conversation("s3", web.runtime.actor)
    relisted = _get(server, "/api/reviews")
    (shown,) = [p for p in relisted["proposals"] if p["proposal_id"] == mine]
    assert [(e["session_id"], e["gone"], e["excerpt"]) for e in shown["suggestion"]["evidence"]][
        -1
    ] == ("s3", True, "")
    assert "Amy" not in json.dumps(listed, ensure_ascii=False)
    # Another member's card cannot be decided by id through the route.
    for action in ("snooze", "reject", "reopen"):
        refused = _post(server, "/api/reviews/decide", {"proposal_id": hers, "action": action})
        assert refused == {"ok": False, "code": "unknown_proposal"}
    store = ProposalStore(web.runtime.layout.workspace_root)
    assert store.get(hers).status == "proposed"
    # Ignore with a quick pick and no text, through the route.
    ignored = _post(
        server,
        "/api/reviews/decide",
        {"proposal_id": mine, "action": "reject", "reason": None, "reason_code": "not_useful"},
    )
    assert ignored["ok"]
    (card,) = [p for p in ignored["proposals"] if p["proposal_id"] == mine]
    assert (card["status"], card["reason_code"], card["reason"]) == ("rejected", "not_useful", None)
    group = (
        SuggestionStore(web.runtime.layout.workspace_root)
        .load(web.runtime.actor)
        .groups[card["suggestion"]["group_id"]]
    )
    assert group.status == "ignored" and len(group.ignored_request_ids) == 3
    assert _post(server, "/api/reviews/decide", {"proposal_id": mine, "action": "accept"}) == {
        "ok": False,
        "code": "suggestion_has_no_draft_yet",
    }
    # The model has no tool for any of it.
    host_tools = web.runtime.agent.gateway.host_tools
    names = [item.tool.name for item in (host_tools() if host_tools else ())]
    assert names and not [
        n for n in names if re.search(r"(^|_)(reviews?|suggest\w*|proposal_decide)(_|$)", n)
    ]
    # Nothing was drafted or installed.
    after = (
        _tree(skills) if skills.is_dir() else {},
        _tree(workflows) if workflows.is_dir() else {},
    )
    assert after == before
    chat = web.runtime.layout.workspace_root / "authoring" / "chat"
    assert not list(chat.rglob("*.json")) if chat.is_dir() else True


# -- the card in a real browser ---------------------------------------------------------


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_suggestion_card_renders_and_opens_the_conversation_in_a_real_browser(
    served: Any,  # noqa: F811
    tmp_path: Path,
) -> None:
    from integrations.browser import Browser

    web, server, _recorder, _ = served
    mine, hers = _seed(web)
    # The card has seen new requests since it was made.
    store = ProposalStore(web.runtime.layout.workspace_root)
    record = store.get(mine)
    assert record.suggestion is not None
    store.save(
        record.model_copy(
            update={"suggestion": record.suggestion.model_copy(update={"seen_more": 2})}
        )
    )
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)

    def wait(expression: str, seconds: float = 30) -> object:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = browser._evaluate(expression)
            if value:
                return value
            time.sleep(0.2)
        raise AssertionError(expression)

    def measure(selector: str) -> list[int]:
        size: list[int] = json.loads(
            str(
                browser._evaluate(
                    "JSON.stringify((() => { const r = document.querySelector("
                    + json.dumps(selector)
                    + ").getBoundingClientRect();"
                    " return [Math.round(r.width), Math.round(r.height)]; })())"
                )
            )
        )
        return size

    def no_side_scroll() -> None:
        assert not browser._evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )

    card = f'.sg-card[data-proposal-id="{mine}"]'
    try:
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        browser._evaluate('document.getElementById("nav-reviews").click()')
        wait(f"!!document.querySelector({json.dumps(card)})")
        assert not browser._evaluate(
            f"document.querySelector({json.dumps(f'[data-proposal-id={hers!r}]')})"
        )
        width, height = measure(card)
        assert width >= 280 and height >= 200, (width, height)
        shown = str(browser._evaluate(f"document.querySelector({json.dumps(card)}).innerText"))
        for words in (
            "SUGGESTED SKILL",
            "整理週報並寄給主管",
            "3 requests · 3 conversations · 3 days",
            "seen 2 more times since",
            "matched words:",
            "same tools: files__read → excel__read → mail__draft",
            "No draft yet",
        ):
            assert words in shown, (words, shown)
        assert "Create draft" not in shown
        assert (
            browser._evaluate(
                f"document.querySelectorAll({json.dumps(card + ' .sg-evidence button')}).length"
            )
            == 3
        )
        counts = str(browser._evaluate('document.getElementById("rv-counts").textContent'))
        assert counts.startswith("1 to decide"), counts
        for selector in (
            card + ' button[data-action="ignore"]',
            card + ' button[data-action="snooze"]',
            card + " .sg-evidence button",
        ):
            w, h = measure(selector)
            assert w >= 44 and h >= 44, (selector, w, h)
        no_side_scroll()
        browser._evaluate(
            f"document.querySelector({json.dumps(card)}).scrollIntoView({{block: 'start'}})"
        )
        browser.screenshot(shots / "suggestion-card-light.png")
        # Dark mode: the card follows the page's colours.
        light = browser._evaluate(
            f"getComputedStyle(document.querySelector({json.dumps(card)})).backgroundColor"
        )
        browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "dark"}],
        )
        dark = browser._evaluate(
            f"getComputedStyle(document.querySelector({json.dumps(card)})).backgroundColor"
        )
        assert light != dark, (light, dark)
        why_bg = browser._evaluate(
            f"getComputedStyle(document.querySelector({json.dumps(card + ' .sg-why')}))"
            ".backgroundColor"
        )
        assert why_bg != "rgb(234, 242, 251)", why_bg  # not the light tint in dark mode
        no_side_scroll()
        browser.screenshot(shots / "suggestion-card-dark.png")
        # Ignore opens the optional reasons; buttons stay 44 px.
        browser._evaluate(
            f"document.querySelector({json.dumps(card + ' button[data-action=ignore]')}).click()"
        )
        wait(f"!!document.querySelector({json.dumps(card + ' .sg-ignore')})")
        for selector in (
            card + " .sg-picks button",
            card + ' button[data-action="confirm-ignore"]',
        ):
            w, h = measure(selector)
            assert w >= 44 and h >= 44, (selector, w, h)
        browser._evaluate(
            f"document.querySelector({json.dumps(card + ' .sg-ignore')})"
            ".scrollIntoView({block: 'start'})"
        )
        browser.screenshot(shots / "suggestion-card-ignore.png")
        # Settings: the sensitivity choice is visible in plain words.
        browser._evaluate('document.getElementById("xp-card").open = true')
        wait('document.querySelectorAll("#xp-sensitivity input").length === 3')
        settings = str(browser._evaluate('document.getElementById("xp-suggest").innerText'))
        assert "Suggest Skills from my repeated work" in settings
        assert "Normal: 3 times in 3 conversations over at least 2 days, up to 3 a night" in (
            settings
        )
        assert browser._evaluate(
            'document.querySelector("#xp-sensitivity input[value=normal]").checked'
        )
        w, h = measure("#xp-sensitivity label")
        assert h >= 44, (w, h)
        browser._evaluate('document.getElementById("xp-suggest").scrollIntoView({block: "start"})')
        no_side_scroll()
        browser.screenshot(shots / "suggestion-settings-dark.png")
        browser._evaluate('document.querySelector("#xp-sensitivity input[value=high]").click()')
        browser._evaluate('document.getElementById("xp-save").click()')
        deadline = time.monotonic() + 15
        while load_settings(web.runtime.layout.workspace_root).suggestion_sensitivity != "high":
            assert time.monotonic() < deadline, "the sensitivity was not saved"
            time.sleep(0.2)
        # An evidence entry opens that conversation at the request.
        browser._evaluate(
            f"document.querySelectorAll({json.dumps(card + ' .sg-evidence button')})[1].click()"
        )
        wait('!!document.querySelector(".turn.sg-target")')
        assert browser._evaluate('document.querySelector(".turn.sg-target").dataset.askedId') == (
            "s2-u"
        )
        assert browser._evaluate("activeConversation") == "s2"
        browser.screenshot(shots / "suggestion-opened-conversation.png")
        # Narrow screen: no horizontal scroll on the card.
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=390,
            height=844,
            deviceScaleFactor=1,
            mobile=True,
        )
        browser._evaluate('document.getElementById("nav-reviews").click()')
        wait(f"!!document.querySelector({json.dumps(card)})")
        no_side_scroll()
        browser._evaluate(
            f"document.querySelector({json.dumps(card)}).scrollIntoView({{block: 'start'}})"
        )
        browser.screenshot(shots / "suggestion-card-narrow.png")
    finally:
        browser.close()
        browser.discard_profile()
