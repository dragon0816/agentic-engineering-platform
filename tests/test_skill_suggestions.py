"""Suggested Skills from experience, S1: detection and the nightly report only.

`docs/phases/SKILL_SUGGESTIONS.md` and its owner decisions of 2026-10-16. Every
model here is a fake; nothing reaches a gateway or the network.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from common.execution import Failure, TraceIdentifiers
from host_runtime import cli
from host_runtime.conversations import ConversationMessage, ConversationRecord
from host_runtime.experience import ExperienceSettings, ExperienceStore, save_settings
from host_runtime.experience_review import ReviewReport, latest_review, run_review
from host_runtime.skill_suggestions import (
    Catalog,
    Known,
    Scorer,
    SuggestionStore,
    from_reuse,
    load_catalog,
    parse_groups,
    qualifies,
    run_suggestions,
    suggest_for_runtime,
    terms,
)
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

# Today at 04:00 UTC: the CLI dry run uses the real clock and the 30-day window.
NOW = datetime.now(UTC).replace(hour=4, minute=0, second=0, microsecond=0)
# 04:00 UTC is the same calendar day in every time zone from UTC-12 to UTC+14,
# so "one day" and "two days" below do not depend on the machine's zone.
TRACE = TraceIdentifiers(trace_id="t", request_id="r", span_id="s")
ME = "leo.chi"
WEEKLY_TOOLS = "- files__read: succeeded\n- excel__read: succeeded\n- mail__draft: succeeded"


def _at(day: int, hour: int = 0) -> datetime:
    return NOW - timedelta(days=day) + timedelta(minutes=hour)


def _ask(mid: str, text: str, when: datetime, reply_to: str | None = None) -> ConversationMessage:
    return ConversationMessage(
        message_id=mid,
        role="user",
        text=text,
        created_at=when,
        status="submitted",
        reply_to=reply_to,
    )


def _answer(
    mid: str, when: datetime, tools: str | None = None, form: dict[str, Any] | None = None
) -> ConversationMessage:
    return ConversationMessage(
        message_id=mid,
        role="assistant",
        text="done",
        created_at=when,
        status="answered",
        trace=TRACE,
        tool_summary=tools,
        workflow_form=form,
    )


def _session(
    sid: str,
    text: str,
    day: int,
    *,
    actor: str = ME,
    tools: str | None = None,
    form: dict[str, Any] | None = None,
) -> ConversationRecord:
    when = _at(day)
    return ConversationRecord(
        session_id=sid,
        actor=actor,
        title="t",
        created_at=when,
        updated_at=when + timedelta(minutes=1),
        messages=(
            _ask(f"{sid}-u", text, when),
            _answer(f"{sid}-a", when + timedelta(minutes=1), tools, form),
        ),
    )


def _weekly(day: int, sid: str, week: int, actor: str = ME) -> ConversationRecord:
    return _session(
        sid, f"幫我整理 2026_W{week} 的週報 Excel 並寄給主管", day, actor=actor, tools=WEEKLY_TOOLS
    )


class _Grouper:
    """A fake company model: `reply(prompt)` builds its structured answer."""

    def __init__(self, reply: Callable[[str], Any] | None = None, fail: bool = False) -> None:
        self.reply = reply or (lambda prompt: {"groups": []})
        self.fail = fail
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.fail:
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                failure=Failure(code="model_http_error", message="503"),
            )
        reply = self.reply(request.messages[1].text)
        if isinstance(reply, str):
            return ModelResponse(trace=request.trace, model_alias=request.model_alias, text=reply)
        return ModelResponse(
            trace=request.trace, model_alias=request.model_alias, structured_output=reply
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError

    @property
    def prompt(self) -> str:
        return self.requests[-1].messages[1].text


def _keys(prompt: str, *needles: str) -> list[str]:
    """The R/G ids whose prompt line (or a G's example lines) holds a needle."""
    found: list[str] = []
    current = ""
    for line in prompt.splitlines():
        head = re.match(r"^([RG]\d+) ", line)
        if head:
            current = head.group(1)
        if current and any(n in line for n in needles) and current not in found:
            found.append(current)
    return found


def _all_r(prompt: str) -> list[str]:
    return re.findall(r"^(R\d+) ", prompt, flags=re.MULTILINE)


def _group_by(*tasks: tuple[str, tuple[str, ...]]) -> Callable[[str], Any]:
    """Group the prompt's items holding any of the needles, one group a task."""

    def reply(prompt: str) -> Any:
        return {"groups": [{"ids": _keys(prompt, *needles), "task": t} for t, needles in tasks]}

    return reply


def _run(
    tmp_path: Path,
    records: list[ConversationRecord],
    model: _Grouper,
    *,
    actor: str = ME,
    catalog: Catalog | None = None,
    settings: ExperienceSettings | None = None,
    now: datetime = NOW,
    dry_run: bool = False,
) -> Any:
    if not dry_run:
        tmp_path.mkdir(parents=True, exist_ok=True)
    return run_suggestions(
        records,
        actor=actor,
        model=model,
        alias="company-model",
        store=SuggestionStore(tmp_path, read_only=dry_run),
        catalog=catalog or Catalog(),
        settings=settings or ExperienceSettings(),
        now=now,
        dry_run=dry_run,
    )


# -- requests and the deterministic score ------------------------------------------


def test_a_request_is_an_opening_message_and_short_follow_ups_are_skipped() -> None:
    when = _at(2)
    record = ConversationRecord(
        session_id="s1",
        actor=ME,
        title="t",
        created_at=when,
        updated_at=when + timedelta(minutes=9),
        messages=(
            _ask("u1", "整理本週週報 Excel", when),
            _answer(
                "a1",
                when + timedelta(minutes=1),
                WEEKLY_TOOLS + "\n- files__read: succeeded",
                {"workflow": {"namespace": "engineering", "name": "weekly", "version": "1.0.0"}},
            ),
            _ask("u2", "ok", when + timedelta(minutes=2)),
            _answer("a2", when + timedelta(minutes=3)),
            _ask("u3", "謝謝！", when + timedelta(minutes=4)),
            _answer("a3", when + timedelta(minutes=5)),
            _ask("u4", "把第二段改短一點", when + timedelta(minutes=6), reply_to="a1"),
            _answer("a4", when + timedelta(minutes=7)),
            _ask("u5", "Also list the open bugs from Jira", when + timedelta(minutes=8)),
        ),
    )
    harvest = from_reuse([record], ME, retention_days=30, now=NOW)
    assert [r.message_id for r in harvest.requests] == ["u1", "u5"]
    first, second = harvest.requests
    assert first.tools == ("files__read", "excel__read", "mail__draft")  # ordered, unique
    assert first.workflows == ("engineering/weekly",) and first.status == "answered"
    assert second.status == "unanswered" and second.tools == ()


def test_requests_outside_the_retention_window_are_not_harvested() -> None:
    harvest = from_reuse(
        [_weekly(40, "old", 1), _weekly(3, "new", 2)], ME, retention_days=30, now=NOW
    )
    assert [r.session_id for r in harvest.requests] == ["new"]


def test_chinese_english_and_mixed_requests_compare_without_numbers_or_dates() -> None:
    assert "2026_w30" not in terms("2026_W30 週報") and "2026" not in terms("2026-10-16 週報")
    assert {"週報", "週", "報"} <= terms("整理週報")
    records = [
        _session("zh1", "幫我整理第 30 週的週報", 5),
        _session("zh2", "整理第 31 週週報", 4),
        _session("en1", "Summarize the weekly test report for week 30", 5),
        _session("en2", "summarize weekly test report, week 31", 4),
        _session("mx1", "整理 weekly report Excel 給主管", 3),
        _session("mx2", "weekly report Excel 整理一下", 2),
        _session("other", "ZNA67 的 option 有哪些？", 1),
    ]
    found = {r.session_id: r for r in from_reuse(records, ME, retention_days=30, now=NOW).requests}
    scorer = Scorer(list(found.values()))
    assert scorer.text(found["zh1"], found["zh2"]) > 0.3
    assert scorer.text(found["en1"], found["en2"]) > 0.5
    assert scorer.text(found["mx1"], found["mx2"]) > 0.25
    assert scorer.text(found["zh1"], found["other"]) < 0.1
    assert scorer.text(found["en1"], found["other"]) == 0.0


def test_the_same_tool_shape_scores_even_across_languages() -> None:
    records = [
        _session("a", "整理週報", 3, tools=WEEKLY_TOOLS),
        _session("b", "weekly report please", 2, tools=WEEKLY_TOOLS),
    ]
    a, b = from_reuse(records, ME, retention_days=30, now=NOW).requests
    scorer = Scorer([a, b])
    assert scorer.tools(a, b) == 1.0 and scorer.score(a, b) >= 0.4


# -- the pre-filter and the model's grouping ----------------------------------------


def test_the_pre_filter_drops_one_offs_and_never_joins_requests_by_itself(
    tmp_path: Path,
) -> None:
    records = [
        _weekly(5, "s1", 30),
        _weekly(4, "s2", 31),
        _weekly(3, "s3", 32),
        _session("s4", "今天新竹天氣如何？", 3),
    ]
    model = _Grouper()  # groups nothing
    result = _run(tmp_path, records, model)
    assert len(model.requests) == 1
    assert "天氣" not in model.prompt and len(_all_r(model.prompt)) == 3
    counts = result.counts
    assert (counts.harvested, counts.new_requests, counts.one_offs, counts.sent_requests) == (
        4,
        4,
        1,
        3,
    )
    # Three near-identical requests, but the model joined none: no group.
    assert result.suggestions == () and counts.qualified == 0


def test_the_models_groups_qualify_with_evidence_words_and_tool_shape(tmp_path: Path) -> None:
    records = [_weekly(5, "s1", 30), _weekly(4, "s2", 31), _weekly(3, "s3", 32)]
    model = _Grouper(_group_by(("整理週報並寄給主管", ("週報",))))
    result = _run(tmp_path, records, model)
    request = model.requests[0]
    assert request.model_alias == "company-model" and request.output_contract == (
        "skill_suggestion_groups"
    )
    assert request.requirements.structured_output
    (item,) = result.suggestions
    assert item.status == "qualified" and item.task == "整理週報並寄給主管"
    assert (item.requests, item.sessions, item.days) == (3, 3, 3)
    assert "週報" in item.matched_words and "excel" in item.matched_words
    assert item.tool_shape == ("files__read", "excel__read", "mail__draft")
    assert [e.session_id for e in item.evidence] == ["s1", "s2", "s3"]
    assert (
        item.evidence[0].message_id == "s1-u"
        and item.evidence[0].date == _at(5).astimezone().date().isoformat()
    )
    assert "週報" in item.evidence[0].excerpt


def test_the_model_may_join_requests_the_score_would_not(tmp_path: Path) -> None:
    # Chinese and English wording of one task: the words differ, the tools match,
    # so the pre-filter sends them and the model's grouping decides.
    records = [
        _session("zh", "整理週報寄給主管", 5, tools=WEEKLY_TOOLS),
        _session("en", "send my boss the weekly summary", 4, tools=WEEKLY_TOOLS),
        _session("mx", "weekly 報告 寄出", 3, tools=WEEKLY_TOOLS),
    ]
    model = _Grouper(lambda prompt: {"groups": [{"ids": _all_r(prompt), "task": "週報"}]})
    result = _run(tmp_path, records, model)
    assert [i.status for i in result.suggestions] == ["qualified"]


# -- thresholds ---------------------------------------------------------------------


def test_three_requests_in_three_sessions_over_two_days_qualify() -> None:
    def requests(*pairs: tuple[str, int]) -> list[Any]:
        records = [_weekly(day, sid, n) for n, (sid, day) in enumerate(pairs)]
        return from_reuse(records, ME, retention_days=30, now=NOW).requests

    assert qualifies(requests(("a", 3), ("b", 3), ("c", 2)))  # two days
    assert not qualifies(requests(("a", 3), ("b", 3), ("c", 3)))  # one day
    assert not qualifies(requests(("a", 3), ("b", 2)))  # two requests


def test_requests_inside_one_session_never_qualify(tmp_path: Path) -> None:
    first, second, third = _at(5), _at(4), _at(3)
    one_session = ConversationRecord(
        session_id="long",
        actor=ME,
        title="t",
        created_at=first,
        updated_at=third + timedelta(minutes=1),
        messages=(
            _ask("u1", "整理 2026_W30 週報 Excel", first),
            _answer("a1", first + timedelta(minutes=1), WEEKLY_TOOLS),
            _ask("u2", "整理 2026_W31 週報 Excel", second),
            _answer("a2", second + timedelta(minutes=1), WEEKLY_TOOLS),
            _ask("u3", "整理 2026_W32 週報 Excel", third),
            _answer("a3", third + timedelta(minutes=1), WEEKLY_TOOLS),
        ),
    )
    # A fourth request elsewhere gives the pre-filter a partner in another session.
    records = [one_session, _weekly(2, "other", 33)]
    model = _Grouper(lambda prompt: {"groups": [{"ids": _all_r(prompt), "task": "週報"}]})
    result = _run(tmp_path, records, model)
    (item,) = result.suggestions
    assert item.status == "considered" and (item.requests, item.sessions) == (4, 2)
    assert "below the threshold" in item.reason


def test_three_sessions_on_one_day_do_not_qualify(tmp_path: Path) -> None:
    records = [
        _session(sid, f"整理 W{n} 週報 Excel", 3, tools=WEEKLY_TOOLS)
        for n, sid in enumerate(("a", "b", "c"))
    ]
    model = _Grouper(lambda prompt: {"groups": [{"ids": _all_r(prompt), "task": "週報"}]})
    (item,) = _run(tmp_path, records, model).suggestions
    assert item.status == "considered" and item.days == 1


# -- caps and only new requests ---------------------------------------------------

TASKS = (
    ("weekly", "整理週報 Excel 寄主管", "- excel__read: succeeded"),
    ("jira", "list open Jira bugs for project lab", "- jira__search: succeeded"),
    ("dut", "check the DUT firmware version on bench", "- dut__status: succeeded"),
    ("license", "盤點儀器 license 到期日", "- inventory__read: succeeded"),
)


def _four_tasks() -> list[ConversationRecord]:
    return [
        _session(f"{key}{n}", f"{text} {n}", day, tools=tools)
        for key, text, tools in TASKS
        for n, day in enumerate((5, 4, 3))
    ]


def _by_task(prompt: str) -> Any:
    return {
        "groups": [
            {"ids": _keys(prompt, text.split()[0]), "task": f"task {key}"} for key, text, _ in TASKS
        ]
    }


def test_at_most_three_new_suggestions_a_night_and_the_rest_wait(tmp_path: Path) -> None:
    model = _Grouper(_by_task)
    first = _run(tmp_path, _four_tasks(), model)
    statuses = sorted(i.status for i in first.suggestions)
    assert statuses == ["deferred", "qualified", "qualified", "qualified"]
    waiting = next(i for i in first.suggestions if i.status == "deferred")
    # Next night: nothing new, so no model call, and the waiting group is reported.
    second = _run(tmp_path, _four_tasks(), model, now=NOW + timedelta(days=1))
    assert len(model.requests) == 1 and not second.counts.model_called
    assert [(i.group_id, i.status) for i in second.suggestions] == [(waiting.group_id, "qualified")]


def test_the_requests_per_pass_are_capped_and_the_rest_go_next_night(tmp_path: Path) -> None:
    records = [_weekly(1 + n % 5, f"s{n:02d}", n) for n in range(14)]
    model = _Grouper()
    settings = ExperienceSettings(suggestion_max_requests=10)
    first = _run(tmp_path, records, model, settings=settings)
    assert len(_all_r(model.prompt)) == 10
    assert (first.counts.sent_requests, first.counts.left_for_next) == (10, 4)
    sent_first = set(re.findall(r"W(\d+) ", model.prompt))
    _run(tmp_path, records, model, settings=settings)
    assert len(_all_r(model.prompt)) == 4
    new_lines = [line for line in model.prompt.splitlines() if re.match(r"^R\d+ ", line)]
    assert not sent_first & {re.search(r"W(\d+) ", line).group(1) for line in new_lines}  # type: ignore[union-attr]
    assert len(re.findall(r"^(G\d+) ", model.prompt, flags=re.MULTILINE)) <= 5  # half the cap


def test_only_new_requests_are_sent_the_next_night_with_the_groups_they_resemble(
    tmp_path: Path,
) -> None:
    model = _Grouper(_group_by(("週報", ("週報",))))
    records = [_weekly(5, "s1", 30), _weekly(4, "s2", 31)]
    first = _run(tmp_path, records, model)
    assert [i.status for i in first.suggestions] == ["considered"]
    _run(tmp_path, records, model)
    assert len(model.requests) == 1  # nothing new, no call
    records.append(_weekly(3, "s3", 32))
    third = _run(tmp_path, records, model)
    assert len(model.requests) == 2
    assert _all_r(model.prompt) == ["R1"] and "W32" in model.prompt
    assert re.findall(r"^(G\d+) ", model.prompt, flags=re.MULTILINE) == ["G1"]
    (item,) = third.suggestions
    assert item.status == "qualified" and item.requests == 3


# -- the model's output is checked ------------------------------------------------


def test_unknown_ids_duplicates_and_counts_in_the_reply_are_ignored() -> None:
    known = {"R1", "R2", "R3", "G1"}
    reply = {
        "groups": [
            {"ids": ["R1", "R99", "R1", "G7", "R2"], "task": "週報 password=hunter2", "count": 50},
            {"ids": ["R2", "R3"], "task": "R2 again"},  # R2 already used: one id left
            {"ids": "R3"},
            "garbage",
            {"ids": ["G1", "R3"], "task": "x" * 400},
        ],
        "total": 999,
    }
    groups = parse_groups(reply, known)
    assert [ids for ids, _ in groups] == [["R1", "R2"], ["G1", "R3"]]
    assert "hunter2" not in groups[0][1] and len(groups[1][1]) == 120
    with pytest.raises(ValueError):
        parse_groups(["R1", "R2"], known)
    with pytest.raises(ValueError):
        parse_groups({"clusters": []}, known)


@pytest.mark.parametrize(
    "model",
    [
        _Grouper(lambda prompt: "this is not JSON"),
        _Grouper(lambda prompt: {"no": "groups"}),
        _Grouper(fail=True),
    ],
    ids=["text", "shape", "failure"],
)
def test_a_malformed_reply_changes_nothing_and_is_retried(tmp_path: Path, model: _Grouper) -> None:
    records = [_weekly(5, "s1", 30), _weekly(4, "s2", 31), _weekly(3, "s3", 32)]
    result = _run(tmp_path, records, model)
    assert result.counts.error and result.suggestions == ()
    good = _Grouper(_group_by(("週報", ("週報",))))
    again = _run(tmp_path, records, good)
    assert len(_all_r(good.prompt)) == 3 and again.counts.qualified == 1


def test_a_reply_in_text_is_read_as_json(tmp_path: Path) -> None:
    records = [_weekly(5, "s1", 30), _weekly(4, "s2", 31), _weekly(3, "s3", 32)]
    model = _Grouper(
        lambda prompt: json.dumps({"groups": [{"ids": _all_r(prompt), "task": "週報"}]})
    )
    assert _run(tmp_path, records, model).counts.qualified == 1


# -- per-actor isolation ----------------------------------------------------------


def test_another_actors_identical_requests_never_join(tmp_path: Path) -> None:
    mine = [_weekly(5, "m1", 30), _weekly(4, "m2", 31)]
    theirs = [_weekly(5, "t1", 30, actor="amy"), _weekly(3, "t2", 32, actor="amy")]
    model = _Grouper(lambda prompt: {"groups": [{"ids": _all_r(prompt), "task": "週報"}]})
    result = _run(tmp_path, mine + theirs, model)
    assert len(_all_r(model.prompt)) == 2 and result.counts.harvested == 2
    (item,) = result.suggestions
    assert item.status == "considered" and {e.session_id for e in item.evidence} == {"m1", "m2"}
    # Amy's own pass sees only her requests and none of my groups.
    amy = _run(tmp_path, mine + theirs, model, actor="amy")
    assert re.findall(r"^(G\d+) ", model.prompt, flags=re.MULTILINE) == []
    assert {e.session_id for i in amy.suggestions for e in i.evidence} == {"t1", "t2"}


def test_the_host_reads_only_the_actors_conversations(tmp_path: Path) -> None:
    asked: list[str] = []

    def conversations(actor: str, *, limit: int) -> tuple[ConversationRecord, ...]:
        asked.append(actor)
        return ()

    runtime = _runtime(tmp_path, conversations)
    suggest_for_runtime(runtime, _Grouper(), "m", actor="amy", now=NOW)
    assert asked == ["amy"]


# -- dedupe -----------------------------------------------------------------------


def _three_weekly(**extra: Any) -> list[ConversationRecord]:
    return [
        _session(sid, f"整理 W{n} 週報 Excel", day, **extra)
        for n, (sid, day) in enumerate((("s1", 5), ("s2", 4), ("s3", 3)))
    ]


def _all_one_group(task: str) -> _Grouper:
    return _Grouper(lambda prompt: {"groups": [{"ids": _all_r(prompt), "task": task}]})


def test_an_installed_workflow_run_by_name_in_the_evidence_drops_the_group(
    tmp_path: Path,
) -> None:
    catalog = Catalog(
        workflows=[
            Known(
                "engineering/weekly-report",
                frozenset({"weekly"}),
                ("weekly_report", "weekly_run_report"),
            )
        ]
    )
    records = _three_weekly(tools="- weekly__run_report: succeeded")
    (item,) = _run(tmp_path, records, _all_one_group("整理週報"), catalog=catalog).suggestions
    assert item.status == "dropped"
    assert item.reason == "installed Workflow engineering/weekly-report was run in the evidence"
    form = {"workflow": {"namespace": "engineering", "name": "weekly-report", "version": "1.0.0"}}
    records = _three_weekly(form=form)
    (item,) = _run(tmp_path / "f", records, _all_one_group("整理週報"), catalog=catalog).suggestions
    assert item.status == "dropped" and "engineering/weekly-report" in item.reason


def test_an_installed_skill_a_pending_candidate_and_an_earlier_suggestion_drop_it(
    tmp_path: Path,
) -> None:
    skill = Catalog(skills=[Known("engineering/weekly", frozenset(terms("每週整理週報 Excel")))])
    (item,) = _run(
        tmp_path / "a", _three_weekly(), _all_one_group("整理週報"), catalog=skill
    ).suggestions
    assert (item.status, item.reason) == (
        "dropped",
        "installed Skill engineering/weekly covers this task",
    )
    draft = Catalog(candidates=[Known("skill candidate sc-1", frozenset(terms("整理週報草稿")))])
    (item,) = _run(
        tmp_path / "b", _three_weekly(), _all_one_group("整理週報"), catalog=draft
    ).suggestions
    assert (item.status, item.reason) == ("dropped", "a draft already exists: skill candidate sc-1")
    # Reported once; a later group for the same task is not reported again.
    first = _run(tmp_path / "c", _three_weekly(), _all_one_group("整理週報"))
    assert [i.status for i in first.suggestions] == ["qualified"]
    later = [
        _session(sid, f"週報整理 第{n}週 Excel", day)
        for n, (sid, day) in enumerate((("t1", 2), ("t2", 1), ("t3", 0)))
    ]
    model = _Grouper(
        lambda prompt: {"groups": [{"ids": _keys(prompt, "第"), "task": "整理週報 Excel"}]}
    )
    (item,) = _run(tmp_path / "c", _three_weekly() + later, model).suggestions
    assert item.status == "dropped"
    assert item.reason == f"already reported as {first.suggestions[0].group_id}"


def test_the_catalog_reads_installed_assets_and_only_the_actors_pending_candidates(
    tmp_path: Path,
) -> None:
    workflows, skills, chat = tmp_path / "workflows", tmp_path / "skills", tmp_path / "chat"
    for folder in (workflows, skills, chat / "skill-candidates"):
        folder.mkdir(parents=True)
    (workflows / "weekly.json").write_text(json.dumps(_workflow()), encoding="utf-8")
    skill = _skill_manifest("weekly-helper", "weekly")
    (skills / "engineering__weekly-helper__1.0.0.json").write_text(
        json.dumps(skill), encoding="utf-8"
    )
    for actor, ident in ((ME, "sc-mine"), ("amy", "sc-amy")):
        (chat / "skill-candidates" / f"{ident}.json").write_text(
            json.dumps(
                {
                    "candidate_id": ident,
                    "actor": actor,
                    "source": "conversation",
                    "title": "Jira 每日清單",
                    "created_at": NOW.isoformat(),
                    "updated_at": NOW.isoformat(),
                    "draft": _skill_manifest("jira-list", "jira_list", owner=actor),
                }
            ),
            encoding="utf-8",
        )
    catalog = load_catalog(workflows_dir=workflows, skills_dir=skills, chat_root=chat, actor=ME)
    (workflow,) = catalog.workflows
    assert workflow.label == "engineering/weekly-report"
    assert workflow.names == ("weekly_report", "weekly_run")
    assert [k.label for k in catalog.skills] == ["engineering/weekly-helper"]
    assert [k.label for k in catalog.candidates] == ["skill candidate sc-mine"]


# -- settings, secrets and the report ---------------------------------------------


def test_suggestions_off_means_no_harvest_and_no_model_call(tmp_path: Path) -> None:
    model = _Grouper()
    records = [_weekly(5, "s1", 30), _weekly(4, "s2", 31)]
    result = _run(tmp_path, records, model, settings=ExperienceSettings(suggestions=False))
    assert model.requests == [] and not result.counts.enabled and result.counts.harvested == 0
    asked: list[str] = []

    def conversations(actor: str, *, limit: int) -> tuple[ConversationRecord, ...]:
        asked.append(actor)
        return ()

    save_settings(tmp_path, ExperienceSettings(suggestions=False))
    suggest_for_runtime(_runtime(tmp_path, conversations), model, "m", now=NOW)
    assert asked == [] and model.requests == []


def test_settings_files_without_the_new_fields_keep_working(tmp_path: Path) -> None:
    (tmp_path / "experience-settings.json").write_text(
        '{"retention_days": 14, "nightly": false}', encoding="utf-8"
    )
    from host_runtime.experience import load_settings

    loaded = load_settings(tmp_path)
    assert loaded.suggestions and loaded.suggestion_max_requests == 120
    with pytest.raises(ValueError):
        ExperienceSettings(suggestion_max_requests=5)


def test_requests_with_secret_shaped_text_are_dropped(tmp_path: Path) -> None:
    records = [_weekly(5, "s1", 30), _weekly(4, "s2", 31), _weekly(3, "s3", 32)]
    # Saved text is redacted on save; one that slipped through is still refused.
    when = _at(2)
    leaked = ConversationRecord.model_construct(
        session_id="leak",
        actor=ME,
        title="t",
        created_at=when,
        updated_at=when,
        messages=(
            ConversationMessage.model_construct(
                message_id="leak-u",
                role="user",
                text="整理 W33 週報 Excel api_key=sk-live-0123456789",
                created_at=when,
                status="submitted",
                reply_to=None,
            ),
        ),
    )
    redacted = _session("red", "整理 W34 週報 Excel password=abc", 1)
    assert "[redacted]" in redacted.messages[0].text
    model = _all_one_group("週報")
    result = _run(tmp_path, [*records, leaked, redacted], model)
    assert "sk-live" not in model.prompt and "[redacted]" not in model.prompt
    assert result.counts.secret_dropped == 2
    assert "sk-live" not in result.model_dump_json()


def test_the_report_has_suggestions_beside_findings(tmp_path: Path) -> None:
    records = [_weekly(5, "s1", 30), _weekly(4, "s2", 31), _weekly(3, "s3", 32)]
    records += [_session("j1", "list open Jira bugs", 5), _session("j2", "list open Jira bugs", 4)]
    model = _Grouper(_group_by(("整理週報", ("週報",)), ("Jira 清單", ("Jira",))))
    passed = _run(tmp_path, records, model)

    class _NoCases:
        def generate(self, request: ModelRequest) -> ModelResponse:
            raise AssertionError("no failure cases, no review call")

        def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
            raise NotImplementedError

    report = run_review(
        ExperienceStore(tmp_path),
        _NoCases(),
        "company-model",
        lambda domain: "",
        workspace=tmp_path,
        suggestions=passed,
    )
    (saved,) = (tmp_path / "experience-reviews").glob("review-*.json")
    data = json.loads(saved.read_text(encoding="utf-8"))
    assert data["findings"] == [] and [s["status"] for s in data["suggestions"]] == [
        "qualified",
        "considered",
    ]
    item = data["suggestions"][0]
    assert set(item) == {
        "group_id",
        "task",
        "status",
        "reason",
        "requests",
        "sessions",
        "days",
        "matched_words",
        "tool_shape",
        "evidence",
    }
    assert set(item["evidence"][0]) == {"session_id", "message_id", "date", "excerpt"}
    assert data["suggestion_counts"]["actor"] == ME and data["suggestion_counts"]["qualified"] == 1
    # The counts carry no request text.
    assert "週報" not in json.dumps(data["suggestion_counts"], ensure_ascii=False)
    shown = latest_review(tmp_path)
    assert shown is not None and "## Suggested Skills" in shown["markdown"]
    assert "qualified: 整理週報" in report.markdown()
    assert (
        ReviewReport.model_validate(
            {k: v for k, v in data.items() if k not in ("suggestions", "suggestion_counts")}
        ).suggestions
        == ()
    )


# -- the CLI dry run ----------------------------------------------------------------


def _workflow() -> dict[str, Any]:
    return {
        "metadata": {
            "identity": {"namespace": "engineering", "name": "weekly-report", "version": "1.0.0"},
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "private",
            "lifecycle": "published",
        },
        "kind": "workflow",
        "description": "Weekly report from the Excel sheet",
        "execution": {"mode": "local"},
        "dependencies": {"central_required": False},
        "input_contract": "engineering.weekly-report.input.v1",
        "output_contract": "engineering.weekly-report.output.v1",
        "steps": [
            {
                "capability": {"namespace": "filesystem", "name": "read-file", "version": "1.0.0"},
                "inputs": {"path": {"source": "run", "path": ["args"]}},
            }
        ],
    }


def _skill_manifest(name: str, alias: str, owner: str = ME) -> dict[str, Any]:
    return {
        "metadata": {
            "identity": {"namespace": "engineering", "name": name, "version": "1.0.0"},
            "owner": {"type": "user", "id": owner},
            "visibility": "private",
            "lifecycle": "published",
        },
        "alias": alias,
        "instructions": "整理週報 and mail it",
        "selector_hint": "weekly report",
        "commands": [
            {
                "name": "run",
                "kind": "workflow",
                "target": {"namespace": "engineering", "name": "weekly-report", "version": "1.0.0"},
            }
        ],
    }


def _runtime(tmp_path: Path, conversations: Callable[..., Any]) -> Any:
    return SimpleNamespace(
        actor=ME,
        layout=SimpleNamespace(
            workspace_root=tmp_path, workflows=tmp_path / "workflows", skills=tmp_path / "skills"
        ),
        state=SimpleNamespace(conversations=conversations),
    )


def _tree(root: Path) -> dict[str, float]:
    return {str(p.relative_to(root)): p.stat().st_mtime for p in root.rglob("*")}


def test_the_cli_dry_run_uses_the_nightly_code_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = (_weekly(5, "s1", 30), _weekly(4, "s2", 31), _weekly(3, "s3", 32))
    runtime = _runtime(tmp_path, lambda actor, limit: tuple(r for r in records if r.actor == actor))
    model = _all_one_group("整理週報")
    before = _tree(tmp_path)
    code = cli._experience_suggest(
        runtime, None, True, False, resolve=lambda runtime: (model, "company-model")
    )
    assert code == 0 and _tree(tmp_path) == before == {}
    out = capsys.readouterr().out
    assert "## Suggested Skills" in out and "qualified: 整理週報" in out
    # Run it again: still the same answer, because nothing was stored.
    cli._experience_suggest(runtime, ME, True, True, resolve=lambda runtime: (model, "m"))
    shown = json.loads(capsys.readouterr().out)
    assert shown["counts"]["dry_run"] and shown["suggestions"][0]["status"] == "qualified"
    assert _tree(tmp_path) == {}
    # An existing store is read, never changed, by a dry run.
    suggest_for_runtime(runtime, model, "m", now=NOW)
    before = _tree(tmp_path)
    store_bytes = (tmp_path / "experience.sqlite").read_bytes()
    cli._experience_suggest(runtime, None, True, True, resolve=lambda runtime: (model, "m"))
    assert json.loads(capsys.readouterr().out)["suggestions"] == []  # already reported
    assert _tree(tmp_path) == before
    assert (tmp_path / "experience.sqlite").read_bytes() == store_bytes
    # Without --dry-run the CLI refuses; without a model it says so.
    assert cli._experience_suggest(runtime, None, False, False) == 2
    assert cli._experience_suggest(runtime, None, True, False, resolve=lambda r: None) == 1


def test_the_cli_parses_the_experience_suggest_command() -> None:
    args = cli._parser().parse_args(
        ["experience", "suggest", "--config", "host.json", "--dry-run", "--actor", "amy"]
    )
    assert (args.command, args.experience_action, args.dry_run, args.actor) == (
        "experience",
        "suggest",
        True,
        "amy",
    )


# -- the nightly job ------------------------------------------------------------------


def test_the_nightly_job_runs_the_same_pass_and_a_fault_never_stops_the_review(
    tmp_path: Path,
) -> None:
    from host_runtime.web import AgentWeb

    records: tuple[ConversationRecord, ...] = (
        _weekly(5, "s1", 30),
        _weekly(4, "s2", 31),
        _weekly(3, "s3", 32),
    )
    runtime = _runtime(tmp_path, lambda actor, limit: tuple(r for r in records if r.actor == actor))
    web = SimpleNamespace(runtime=runtime)
    # New requests past the pre-filter make the night due, with no model call.
    assert AgentWeb._suggestions_due(web)  # type: ignore[arg-type]
    model = _all_one_group("整理週報")
    passed = AgentWeb._suggestion_pass(web, model, "m")  # type: ignore[arg-type]
    assert passed.counts.qualified == 1 and not passed.counts.dry_run
    assert not AgentWeb._suggestions_due(web)  # type: ignore[arg-type]
    save_settings(tmp_path, ExperienceSettings(suggestions=False))
    records += (_weekly(2, "s4", 33),)
    assert not AgentWeb._suggestions_due(web)  # type: ignore[arg-type]

    def broken(actor: str, *, limit: int) -> tuple[ConversationRecord, ...]:
        raise OSError("state locked")

    save_settings(tmp_path, ExperienceSettings())
    failed = AgentWeb._suggestion_pass(
        SimpleNamespace(runtime=_runtime(tmp_path, broken)),  # type: ignore[arg-type]
        model,
        "m",
    )
    assert failed.counts.error == "OSError" and failed.suggestions == ()
