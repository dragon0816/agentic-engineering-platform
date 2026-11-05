"""The skill AI's budget per turn, and a new rule saved only when applied
(acceptance F16, 2026-11-06).

With the real model one message ran 25 minutes and 9 draft trials, then ended
with 「模型沒有回應（turn_time_limit）」 and no suggestion, while 「和 AI 新增
規則」 had already saved the person's sentence as revision 1. Here a scripted
model that never stops: the trials are capped, a time budget stops further
trials, the best draft so far comes back as the suggestion with what was
tried, a turn with nothing to show says in Chinese what to do, and a new rule
exists only once the person applies a draft. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_extract import MEETING_ANSWER, NOTE, Scripted
from test_bi_vault import _call, _ok
from test_business_cards_conversation import Conversation
from test_host_wiring import ready

from capabilities.bi_cards.ai_runs import AiRuntime
from capabilities.bi_cards.staging import Staging
from host_runtime import bi_bench, bi_skill_agent, skill_packs
from host_runtime.assets import shipped
from host_runtime.bi_cards_api import route
from host_runtime.host import build_runtime
from models.contracts import ModelRequest, ModelResponse, ModelToolCall


class Forever(Conversation):
    """A model that never calls bi_skill__suggest: each reply is `step(n)`."""

    def __init__(self, step: Any) -> None:
        super().__init__()
        self.step = step

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        name, args = self.step(len(self.requests))
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            text="",
            tool_calls=(
                ModelToolCall(call_id=f"c{len(self.requests)}", name=name, arguments=args),
            ),
        )


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _vault(tmp_path: Path) -> tuple[Any, Any, Path, dict[str, Any], str, AiRuntime]:
    config, layout = ready(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    ws = layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(
        _call(
            ws,
            "POST",
            "/api/bi/vaults",
            {
                "path": str(shared),
                "title": "Market",
                "purpose": "虛構",
                "schema": "bi.schema/v1.1",
                "author": "alice",
            },
        )
    )
    source = _ok(
        _call(
            ws,
            "POST",
            "/api/bi/sources",
            {
                "dataset": made["vault"]["dataset"],
                "name": "meeting.md",
                "text": NOTE,
                "classification": "UNCLASSIFIED",
            },
        )
    )["source"]["id"]
    ai = AiRuntime(
        model=lambda: (Scripted(MEETING_ANSWER), "test-model"),
        background=lambda _t, work: work(),
        approved=lambda: ("UNCLASSIFIED", "INTERNAL"),
    )
    return config, layout, ws, made["vault"], source, ai


def _turn(
    config: Any,
    layout: Any,
    ws: Path,
    dataset: str,
    session_id: str,
    ai: AiRuntime,
    model: Any,
    message: str,
    clock: Clock | None = None,
) -> dict[str, Any]:
    with build_runtime(config, layout=layout) as runtime:
        gateway = runtime.agent.gateway
        gateway.router.model = model
        bench = bi_bench.BenchRuntime(
            ask_for=lambda _v, _a: lambda q, s: {},
            extract_for=lambda _v, _a: lambda c: [],
            background=lambda _t, work: work(),
            skill_asker_for=lambda d, s, a: bi_skill_agent.harness_asker(
                gateway, ws, d, s, ai, a, "engineering", **({"clock": clock} if clock else {})
            ),
        )
        status, answer = route(
            ws,
            "alice",
            "POST",
            f"/api/bi/sessions/{session_id}/turns",
            {},
            {"dataset": dataset, "message": message},
            None,
            ai,
            bench,
        )
    assert status == 200, answer
    turn: dict[str, Any] = answer["session"]["turns"][-1]
    return turn


def _trials(ws: Path, dataset: str) -> int:
    return len([r for r in Staging(ws, dataset).run_rows() if r["kind"] == "trial"])


def test_trials_are_capped_and_the_best_draft_comes_back(tmp_path: Path) -> None:
    config, layout, ws, vault, source, ai = _vault(tmp_path)
    dataset = vault["dataset"]
    session = _ok(
        _call(
            ws,
            "POST",
            "/api/bi/sessions",
            {"dataset": dataset, "kind": "skill", "target": "classify"},
        )
    )["session"]
    model = Forever(
        lambda n: ("bi_skill__try", {"source_id": source, "changes": {"body": f"草稿 {n}"}})
    )
    turn = _turn(config, layout, ws, dataset, session["id"], ai, model, "會議紀錄要建 Signal")
    assert _trials(ws, dataset) == bi_skill_agent.TRIALS
    assert turn["error"] is None, turn
    suggestion = turn["suggestion"]
    assert suggestion["changes"] == {"body": f"草稿 {bi_skill_agent.TRIALS}"}
    assert "最好的草稿" in suggestion["reply"]
    assert any(f"試跑 {bi_skill_agent.TRIALS} 次" in item for item in suggestion["limits"])
    # Calls after the cap were refused with a reason the model can act on.
    told = "\n".join(m.text for m in model.requests[-1].messages if m.role == "tool")
    assert "bi_skill__suggest" in told
    assert turn["sent"]["budget"] == {
        "trials": bi_skill_agent.TRIALS,
        "minutes": bi_skill_agent.BUDGET_SECONDS // 60,
        "trials_used": bi_skill_agent.TRIALS,
    }


def test_the_time_budget_stops_trials_before_the_cap(tmp_path: Path) -> None:
    config, layout, ws, vault, source, ai = _vault(tmp_path)
    dataset = vault["dataset"]
    session = _ok(
        _call(
            ws,
            "POST",
            "/api/bi/sessions",
            {"dataset": dataset, "kind": "skill", "target": "classify"},
        )
    )["session"]
    clock = Clock()

    def step(n: int) -> tuple[str, dict[str, Any]]:
        clock.now += bi_skill_agent.BUDGET_SECONDS * 0.6  # each trial takes most of the budget
        return "bi_skill__try", {"source_id": source, "changes": {"body": f"草稿 {n}"}}

    turn = _turn(
        config, layout, ws, dataset, session["id"], ai, Forever(step), "會議紀錄要建 Signal", clock
    )
    assert _trials(ws, dataset) == 1
    assert turn["error"] is None, turn
    assert turn["suggestion"]["changes"] == {"body": "草稿 1"}
    assert any("時間" in item for item in turn["suggestion"]["limits"])


def test_a_turn_with_nothing_to_show_says_in_chinese_what_to_do(tmp_path: Path) -> None:
    config, layout, ws, vault, _source, ai = _vault(tmp_path)
    dataset = vault["dataset"]
    session = _ok(
        _call(
            ws,
            "POST",
            "/api/bi/sessions",
            {"dataset": dataset, "kind": "skill", "target": "classify"},
        )
    )["session"]
    model = Forever(lambda n: ("bi_skill__sources", {}))
    turn = _turn(config, layout, ws, dataset, session["id"], ai, model, "看一下來源")
    assert turn["suggestion"] is None
    message = turn["error"]["message"]
    assert "_limit" not in message and "（" not in message, message
    assert "再送一次" in message


def test_a_new_rule_is_saved_only_when_the_person_applies_a_draft(tmp_path: Path) -> None:
    config, layout, ws, vault, source, ai = _vault(tmp_path)
    dataset = vault["dataset"]
    folders = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault['id']}/skills"))["folders"]
    folder = next(f for f in folders if f != "sources")
    session = _ok(
        _call(
            ws,
            "POST",
            "/api/bi/sessions",
            {
                "dataset": dataset,
                "kind": "skill",
                "target": "power-vendors",
                "new": {"role": "extract", "applies_to": [folder]},
            },
        )
    )["session"]

    def names() -> set[str]:
        listed = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault['id']}/skills"))
        return {s["name"] for s in listed["skills"]}

    assert "power-vendors" not in names()
    # A turn that ends with nothing leaves no rule.
    failed = _turn(
        config,
        layout,
        ws,
        dataset,
        session["id"],
        ai,
        Forever(lambda n: ("bi_skill__sources", {})),
        "虛構電源廠是 Account",
    )
    assert failed["suggestion"] is None and "power-vendors" not in names()
    model = Conversation()
    model.then(
        {
            "tools": [
                (
                    "bi_skill__try",
                    {"source_id": source, "changes": {"body": "虛構電源廠一律是 Account。"}},
                )
            ]
        },
        {
            "tools": [
                (
                    "bi_skill__suggest",
                    {"reply": "新規則。", "changes": {"body": "虛構電源廠一律是 Account。"}},
                )
            ]
        },
        {"text": "建議如上。"},
    )
    turn = _turn(config, layout, ws, dataset, session["id"], ai, model, "虛構電源廠是 Account")
    assert turn["error"] is None, turn
    assert turn["suggestion"]["changes"] == {"body": "虛構電源廠一律是 Account。"}
    assert "power-vendors" not in names()
    shown = _ok(_call(ws, "GET", f"/api/bi/sessions/{session['id']}", dataset=dataset))
    index = len(shown["session"]["turns"]) - 1
    applied = _ok(
        _call(
            ws,
            "POST",
            f"/api/bi/sessions/{session['id']}/apply",
            {"dataset": dataset, "turn": index},
        )
    )
    assert applied["skill"]["revision"] == 1
    listed = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault['id']}/skills"))
    saved = next(s for s in listed["skills"] if s["name"] == "power-vendors")
    assert saved["body"].strip() == "虛構電源廠一律是 Account。"
    assert saved["applies_to"] == [folder]


def test_a_new_rule_cannot_take_an_existing_name(tmp_path: Path) -> None:
    _config, _layout, ws, vault, _source, _ai = _vault(tmp_path)
    status, answer = _call(
        ws,
        "POST",
        "/api/bi/sessions",
        {
            "dataset": vault["dataset"],
            "kind": "skill",
            "target": "classify",
            "new": {"role": "extract", "applies_to": []},
        },
    )
    assert status == 400 and answer["code"] == "skill_exists", answer
