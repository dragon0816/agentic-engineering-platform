"""Historical preflight decisions remain readable and never manufacture trial proof.

The legacy request builder below is intentionally explicit; normal tools execute
directly and are exercised separately in test_it_tool_boundaries.
"""

from __future__ import annotations

import asyncio
import copy
import json
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_authoring_repair import Capturing
from test_browser_session import SITE, FakeBrowser
from test_conversation_turn_groups import _chat_config, _ChatGateway

from capabilities.browser_session.handlers import SPEC, BrowserRequest, BrowserSessionHandler
from common.execution import RequestContext
from host_runtime.authoring_browser_preflight import (
    PREFLIGHT_SOURCE,
    PREFLIGHT_TOOL,
    claim_continuation,
    repair_scope_for,
)
from host_runtime.authoring_browser_preflight import (
    _legacy_preflight_tool as preflight_tool,
)
from host_runtime.authoring_browser_preflight_budget import (
    _path,
    budget,
    charge,
    ensure_budget,
)
from host_runtime.authoring_browser_preflight_contracts import (
    BrowserPreflightRequest,
    BrowserRepairScope,
)
from host_runtime.authoring_task import Requirement
from host_runtime.chat_authoring import ChatAuthoring, ChatAuthoringError, digest
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb
from integrations.browser import BrowserError
from workflow.dispatch import BridgeExecutor


class RepairBrowser(FakeBrowser):
    def navigate(self, url: str) -> None:
        super().navigate(url)
        if url.endswith("/bad"):
            raise BrowserError("navigation_failed")
        if url.endswith("/redirect"):
            self.url = "https://outside.example/"


@contextmanager
def failed_browser_trial(
    tmp_path: Path, *, direct: bool = False
) -> Iterator[tuple[Any, Any, str, RepairBrowser]]:
    from capabilities.web.handlers import WebHostBinding

    config, layout = _chat_config(tmp_path)
    config = config.model_copy(update={"web": WebHostBinding(allowed_origins=("*",))})
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        browser = RepairBrowser()
        binding = runtime.agent.gateway.bridge.installed.get(SPEC.identity)
        assert binding is not None and isinstance(binding.handler, BrowserSessionHandler)
        binding.handler._factory = lambda: browser
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        chat = runtime.chat_authoring
        assert chat is not None
        chat.tasks.plan(
            runtime.actor,
            session,
            "Build a browser report",
            [Requirement(requirement_id="browse", description="Read the authorized site")],
        )
        item, problems = chat.draft(
            runtime.actor,
            session,
            "Browser report",
            {
                "name": "preflight-fixture",
                "description": "Read the authorized site",
                "parameters": [],
                "steps": [
                    {
                        "capability": "browser/operate@1.0.0",
                        "inputs": {
                            "actions": {
                                "source": "fixed",
                                "value": [{"do": "open", "url": SITE + "/bad"}],
                            }
                        },
                    }
                ],
            },
        )
        assert item is not None and not problems
        if direct:
            done = chat.execute(runtime.actor, item, {}, "direct-fixture")
            assert done["status"] == "failed"
        else:
            request = chat.request(runtime.actor, session, "run", item.candidate_id)
            decided = chat.decide(request.approval_id, runtime.actor, True)
            assert isinstance(decided.result, dict) and decided.result["status"] == "failed"
        scope = repair_scope_for(chat, current(chat, runtime.actor, session))
        assert scope is not None
        ensure_budget(chat, scope, runtime.agent.gateway.limits())
        yield runtime, web, session, browser


def current(chat: ChatAuthoring, actor: str, session: str) -> Any:
    return next(item for item in chat.candidates(actor) if item.session_id == session)


def context(chat: ChatAuthoring, actor: str, session: str) -> RequestContext:
    item = current(chat, actor, session)
    return chat._context(actor, chat.namespace, session, "preflight").model_copy(
        update={"message": f"[Host authoring continuation: test] Candidate {item.candidate_id};"}
    )


def ask(runtime: Any, session: str, url: str = SITE + "/good") -> Any:
    chat = runtime.chat_authoring
    ctx = context(chat, runtime.actor, session)
    item = current(chat, runtime.actor, session)
    scope = repair_scope_for(chat, item)
    assert scope is not None
    tool = preflight_tool(chat, ctx, scope)

    async def request() -> Any:
        return await tool.handler(
            ctx,
            {
                "candidate_id": item.candidate_id,
                "base_digest": digest(item.draft),
                "actions": [{"do": "open", "url": url}],
            },
        )

    return asyncio.run(request())


@pytest.mark.parametrize("actions", [[], [{"do": "reload"}] * 9])
def test_action_batch_is_closed_and_bounded(actions: list[Any]) -> None:
    with pytest.raises(ValidationError):
        BrowserPreflightRequest.model_validate(
            {"candidate_id": "wf-test", "base_digest": "a" * 64, "actions": actions}
        )


def test_pending_request_has_no_effect_legacy_shape_refuses_and_approval_is_once(
    tmp_path: Path,
) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, browser):
        chat = runtime.chat_authoring
        before = list(browser.visited)
        task_before = chat.tasks.load(runtime.actor, session).model_dump_json()
        asked = ask(runtime, session)
        assert asked.status == "awaiting_approval" and browser.visited == before
        assert isinstance(asked.data, dict)
        approval = chat.approval(asked.data["approval_id"], runtime.actor)
        assert approval.source == PREFLIGHT_SOURCE and approval.kind == "capability"
        with pytest.raises(ValidationError):
            BrowserRequest.model_validate(approval.arguments)
        duplicate = ask(runtime, session)
        assert duplicate.data["approval_id"] == approval.approval_id
        result = chat.decide(approval.approval_id, runtime.actor, True)
        assert result.result["failure"] is None
        assert result.status == "approved" and result.result["status"] == "succeeded", result.result
        assert result.result["preflight_only"] is True
        assert browser.visited == before + [SITE + "/good"]
        assert chat.tasks.load(runtime.actor, session).model_dump_json() == task_before
        assert chat.readiness(current(chat, runtime.actor, session))["verified"] is False
        with pytest.raises(ChatAuthoringError, match="approval_already_decided"):
            chat.decide(approval.approval_id, runtime.actor, True)
        replay = ask(runtime, session)
        assert replay.status == "succeeded" and replay.data["replayed"] is True
        assert browser.visited == before + [SITE + "/good"]


def test_new_origin_is_refused_before_approval_and_request_budget_is_two(tmp_path: Path) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, browser):
        before = list(browser.visited)
        bad = ask(runtime, session, "https://outside.example/")
        assert bad.status == "failed" and bad.failure.code == "preflight_origin_refused"
        first = ask(runtime, session)
        second = ask(runtime, session, SITE + "/other")
        third = ask(runtime, session, SITE + "/third")
        assert first.status == second.status == "awaiting_approval"
        assert third.status == "failed" and third.failure.code == "preflight_limit"
        assert browser.visited == before


def test_stale_candidate_is_not_executed_after_owner_approval(tmp_path: Path) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, browser):
        chat = runtime.chat_authoring
        asked = ask(runtime, session)
        item = current(chat, runtime.actor, session)
        chat._save_candidate(
            item.model_copy(
                update={
                    "draft": item.draft.model_copy(
                        update={"description": "Changed after the request"}
                    )
                }
            ),
            expected_digest=digest(item.draft),
        )
        before = list(browser.visited)
        result = chat.decide(asked.data["approval_id"], runtime.actor, True)
        assert result.status == "failed" and result.result["failure"] == "preflight_stale"
        assert browser.visited == before


def test_eligible_repair_executes_probe_without_cards_or_false_trial_verification(
    tmp_path: Path,
) -> None:
    with failed_browser_trial(tmp_path) as (runtime, web, session, browser):
        chat = runtime.chat_authoring
        item = current(chat, runtime.actor, session)
        model = Capturing(
            {
                "tools": [
                    (
                        PREFLIGHT_TOOL,
                        {
                            "candidate_id": item.candidate_id,
                            "base_digest": digest(item.draft),
                            "actions": [{"do": "open", "url": SITE + "/good"}],
                        },
                    )
                ]
            },
            {"text": "Waiting for browser validation approval."},
        )
        runtime.agent.gateway.router.model = model
        result = web._resume_failed_authoring(session)
        assert result is not None
        assert all(PREFLIGHT_TOOL in {t.name for t in r.tools} for r in model.requests)
        assert all("browser__operate" not in {t.name for t in r.tools} for r in model.requests)
        assert not any(a.source == PREFLIGHT_SOURCE for a in chat.approvals(runtime.actor))
        after = chat.tasks.load(runtime.actor, session)
        assert after.repair_attempts == 1
        assert after.verified_digest is None
        assert browser.visited.count(SITE + "/good") == 1
        runtime.agent.gateway.router.model = Capturing({"text": "A workflow is a procedure."})
        web.conversation_turn({"session_id": session, "message": "What is a workflow?"})
        assert all(
            PREFLIGHT_TOOL not in {t.name for t in r.tools}
            for r in runtime.agent.gateway.router.model.requests
        )


@pytest.mark.parametrize(
    "action",
    [
        {"do": "download", "target": {"css": "#export"}, "save_as": "out"},
        {
            "do": "read_table",
            "table": "#rows",
            "save_as": "rows",
            "pagination": {
                "next": {"css": "#next"},
                "current": {"css": "#current"},
                "total": {"css": "#total"},
                "max_pages": 2,
            },
        },
    ],
)
def test_preflight_does_not_become_an_export_job(action: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        BrowserPreflightRequest.model_validate(
            {
                "candidate_id": "wf-test",
                "base_digest": "a" * 64,
                "actions": [action],
            }
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("actor", "someone-else"),
        ("session_id", "another-conversation"),
    ],
)
def test_bound_tool_rejects_other_request_context(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, browser):
        chat = runtime.chat_authoring
        ctx = context(chat, runtime.actor, session)
        item = current(chat, runtime.actor, session)
        scope = repair_scope_for(chat, item)
        assert scope is not None
        tool = preflight_tool(chat, ctx, scope)
        args = {
            "candidate_id": item.candidate_id,
            "base_digest": digest(item.draft),
            "actions": [{"do": "open", "url": SITE + "/good"}],
        }

        async def invoke() -> Any:
            return await tool.handler(ctx.model_copy(update={field: value}), args)

        before = list(browser.visited)
        result = asyncio.run(invoke())
        assert result.failure.code == "preflight_scope_required"
        assert browser.visited == before
        assert not [a for a in chat.approvals(runtime.actor) if a.source == PREFLIGHT_SOURCE]


def test_approval_is_model_origin_with_one_trial_grant_and_no_global_grant_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, _browser):
        chat = runtime.chat_authoring
        original = runtime.agent.gateway.bridge.policy
        before = copy.deepcopy(original.__dict__)
        asked = ask(runtime, session)
        captured: list[Any] = []
        execute = BridgeExecutor.execute

        async def observe(bridge: BridgeExecutor, invocation: Any) -> Any:
            captured.append((invocation.origin, bridge.policy, invocation.target))
            return await execute(bridge, invocation)

        monkeypatch.setattr(BridgeExecutor, "execute", observe)
        result = chat.decide(asked.data["approval_id"], runtime.actor, True)
        assert result.result["status"] == "succeeded"
        assert len(captured) == 1 and captured[0][0] == "model"
        assert captured[0][1] is not original and captured[0][2] == SPEC.identity
        assert original.__dict__ == before
        assert chat.external_view(result).get("data") is None
        assert "preflight_only" not in chat.external_view(result)


def test_legacy_preflight_does_not_need_synthetic_tool_grants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, browser):
        chat = runtime.chat_authoring
        asked = ask(runtime, session)
        before = list(browser.visited)
        monkeypatch.setattr(chat, "grants", lambda *_args: ())
        result = chat.decide(asked.data["approval_id"], runtime.actor, True)
        assert result.result["failure"] is None
        assert result.result["handler_invoked"] is True and browser.visited != before
        assert claim_continuation(chat, runtime.actor, session, result.approval_id) is not None


def test_redirect_scope_stops_before_other_actions_and_does_not_leak_to_normal_calls(
    tmp_path: Path,
) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, browser):
        chat = runtime.chat_authoring
        asked = ask(runtime, session, SITE + "/redirect")
        result = chat.decide(asked.data["approval_id"], runtime.actor, True)
        assert result.result["failure"] == "web_origin_not_allowed"
        assert result.result["handler_invoked"] is True
        binding = chat.installed.get(SPEC.identity)
        assert binding is not None and isinstance(binding.handler, BrowserSessionHandler)
        normal = binding.handler.run(
            BrowserRequest.model_validate(
                {
                    "actions": [{"do": "open", "url": "https://outside.example/normal"}],
                }
            )
        )
        assert normal.url == "https://outside.example/normal"
        assert browser.url == normal.url


def test_rejection_and_tampering_never_reach_browser(tmp_path: Path) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, browser):
        chat = runtime.chat_authoring
        first = ask(runtime, session)
        before = list(browser.visited)
        rejected = chat.decide(first.data["approval_id"], runtime.actor, False)
        assert rejected.status == "rejected" and browser.visited == before
        second = ask(runtime, session, SITE + "/other")
        saved = chat.approval(second.data["approval_id"], runtime.actor)
        args = copy.deepcopy(saved.arguments)
        args["authoring_browser_preflight"]["browser"]["actions"][0]["url"] = SITE + "/tampered"
        chat._save_approval(saved.model_copy(update={"arguments": args}))
        changed = chat.decide(saved.approval_id, runtime.actor, True)
        assert changed.status == "failed" and changed.result["failure"] == "preflight_stale"
        assert browser.visited == before


def test_parallel_duplicate_decisions_dispatch_once(tmp_path: Path) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, browser):
        chat = runtime.chat_authoring
        asked = ask(runtime, session)
        barrier = threading.Barrier(2)

        def decide() -> str:
            barrier.wait(timeout=10)
            try:
                return str(chat.decide(asked.data["approval_id"], runtime.actor, True).status)
            except ChatAuthoringError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = pool.submit(decide), pool.submit(decide)
            outcomes = [a.result(timeout=20), b.result(timeout=20)]
        # Candidate admission is deliberately nonblocking across processes.
        assert outcomes.count("approved") == 1
        assert all(
            o in {"approved", "approval_already_decided", "authoring_candidate_busy"}
            for o in outcomes
        )
        assert browser.visited.count(SITE + "/good") == 1


def test_completed_trial_budget_is_not_renewed_by_preflight(tmp_path: Path) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, _browser):
        chat = runtime.chat_authoring
        item = current(chat, runtime.actor, session)
        task = chat.tasks.load(runtime.actor, session).model_copy(update={"repair_attempts": 3})
        chat.tasks.save(runtime.actor, session, task)
        item = chat._save_candidate(item.model_copy(update={"authoring_task": task}))
        assert repair_scope_for(chat, item) is None


def test_changed_trial_refuses_pending_preflight(tmp_path: Path) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, browser):
        chat = runtime.chat_authoring
        asked = ask(runtime, session)
        before = list(browser.visited)
        task = chat.tasks.load(runtime.actor, session)
        chat.tasks.save(runtime.actor, session, task.model_copy(update={"last_run_id": "run-new"}))
        result = chat.decide(asked.data["approval_id"], runtime.actor, True)
        assert result.result["failure"] == "preflight_stale" and browser.visited == before


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "file://host",
        "https://user:password@example.test",
        "https://example.test/path",
        "https://example.test?parameter=value",
        "https://example.test#part",
        "https://EXAMPLE.test",
    ],
)
def test_scope_requires_literal_origin_authority(origin: str) -> None:
    with pytest.raises(ValidationError):
        BrowserRepairScope(
            actor="owner",
            session_id="session",
            candidate_id="wf-test",
            trial_run_id="run-test",
            trial_digest="a" * 64,
            trial_arguments_digest="b" * 64,
            repair_attempt=1,
            step_index=0,
            capability=SPEC.identity,
            origins=(origin,),
        )


def test_interrupted_dispatch_is_not_reexecuted_or_resumed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, browser):
        chat = runtime.chat_authoring
        asked = ask(runtime, session)
        before = list(browser.visited)

        async def interrupted(_bridge: Any, _invocation: Any) -> Any:
            browser.visited.append(SITE + "/possibly-executed")
            raise RuntimeError("fixture interruption after a possible effect")

        monkeypatch.setattr(BridgeExecutor, "execute", interrupted)
        with pytest.raises(RuntimeError):
            chat.decide(asked.data["approval_id"], runtime.actor, True)
        saved = chat.approval(asked.data["approval_id"], runtime.actor)
        assert saved.status == "approved" and saved.result["status"] == "unavailable"
        assert saved.result["failure"] == "preflight_execution_unknown"
        assert claim_continuation(chat, runtime.actor, session, saved.approval_id) is None
        with pytest.raises(ChatAuthoringError, match="approval_already_decided"):
            chat.decide(saved.approval_id, runtime.actor, True)
        assert ask(runtime, session).status == "failed"
        assert browser.visited == before + [SITE + "/possibly-executed"]


def test_reject_cannot_overwrite_an_already_claimed_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, browser):
        chat = runtime.chat_authoring
        asked = ask(runtime, session)
        entered, release = threading.Event(), threading.Event()
        navigate = browser.navigate

        def blocked(url: str) -> None:
            entered.set()
            assert release.wait(timeout=10)
            navigate(url)

        monkeypatch.setattr(browser, "navigate", blocked)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(chat.decide, asked.data["approval_id"], runtime.actor, True)
            try:
                assert entered.wait(timeout=10)
                with pytest.raises(ChatAuthoringError, match="approval_already_decided"):
                    chat.decide(asked.data["approval_id"], runtime.actor, False)
            finally:
                release.set()
            result = pending.result(timeout=20)
        assert result.status == "approved" and result.result["status"] == "succeeded"
        assert browser.visited.count(SITE + "/good") == 1


def test_historical_approval_continuation_reuses_consumed_model_and_tool_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from host_runtime import authoring_browser_preflight

    # Reconstruct an old-version pending record, then exercise its continuation.
    monkeypatch.setattr(authoring_browser_preflight, "preflight_tool", preflight_tool)
    with failed_browser_trial(tmp_path) as (runtime, web, session, browser):
        chat = runtime.chat_authoring
        item = current(chat, runtime.actor, session)
        model = Capturing(
            {
                "tools": [
                    (
                        PREFLIGHT_TOOL,
                        {
                            "candidate_id": item.candidate_id,
                            "base_digest": digest(item.draft),
                            "actions": [{"do": "open", "url": SITE + "/good"}],
                        },
                    )
                ]
            },
            {"text": "Waiting for browser validation approval."},
        )
        runtime.agent.gateway.router.model = model
        web._resume_failed_authoring(session)
        pending = next(a for a in chat.approvals(runtime.actor) if a.source == PREFLIGHT_SOURCE)
        scope = repair_scope_for(chat, item)
        assert scope is not None
        before = budget(chat, scope)
        assert before.model_calls == len(model.requests) and before.tool_calls == 1
        resumed = Capturing({"text": "Preflight checked. A full trial is still required."})
        runtime.agent.gateway.router.model = resumed
        result = web.decide_approval(pending.approval_id, "approve")
        assert result["ok"] and resumed.requests
        after = budget(chat, scope)
        assert after.deadline_at == before.deadline_at
        assert after.model_calls == before.model_calls + len(resumed.requests)
        assert after.tool_calls == before.tool_calls
        assert browser.visited.count(SITE + "/good") == 1


@pytest.mark.parametrize("damage", ["expired", "corrupt", "missing"])
def test_unavailable_or_expired_budget_refuses_pending_execution(
    tmp_path: Path,
    damage: str,
) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, browser):
        chat = runtime.chat_authoring
        asked = ask(runtime, session)
        scope = repair_scope_for(chat, current(chat, runtime.actor, session))
        assert scope is not None
        path = _path(chat, scope)
        if damage == "missing":
            path.unlink()
        elif damage == "corrupt":
            path.write_text("{}", encoding="utf-8")
        else:
            path.write_text(
                budget(chat, scope)
                .model_copy(update={"deadline_at": time.time() - 1})
                .model_dump_json(),
                encoding="utf-8",
            )
        before = list(browser.visited)
        result = chat.decide(asked.data["approval_id"], runtime.actor, True)
        expected = (
            "preflight_budget_expired" if damage == "expired" else "preflight_budget_unavailable"
        )
        assert result.result["failure"] == expected and browser.visited == before
        assert claim_continuation(chat, runtime.actor, session, result.approval_id) is None


def test_budget_limits_survive_reinitialization_and_process_failure(tmp_path: Path) -> None:
    with failed_browser_trial(tmp_path) as (runtime, _web, session, _browser):
        chat = runtime.chat_authoring
        scope = repair_scope_for(chat, current(chat, runtime.actor, session))
        assert scope is not None
        before = budget(chat, scope)
        for _ in range(before.model_limit):
            assert charge(chat, scope, "model") is None
        assert charge(chat, scope, "model") == "preflight_budget_exhausted"
        for _ in range(before.tool_limit):
            assert charge(chat, scope, "tool") is None
        assert charge(chat, scope, "tool") == "preflight_budget_exhausted"
        ensure_budget(chat, scope, runtime.agent.gateway.limits())
        assert budget(chat, scope).deadline_at == before.deadline_at
        assert charge(chat, scope, "model") == "preflight_budget_exhausted"
        assert charge(chat, scope, "tool") == "preflight_budget_exhausted"


def test_owner_can_review_exact_preflight_actions_before_approval(tmp_path: Path) -> None:
    from host_runtime.web import AgentWebServer
    from integrations.browser import Browser

    with failed_browser_trial(tmp_path) as (runtime, web, session, fake):
        asked = ask(runtime, session, SITE + "/review-me")
        listed = web.approvals(session_id=session)
        card = next(a for a in listed["approvals"] if a["approval_id"] == asked.data["approval_id"])
        assert card["browser_preflight"]["actions"][0]["url"] == SITE + "/review-me"
        before = list(fake.visited)
        served = AgentWebServer(web)
        thread = threading.Thread(target=served.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "review-browser", timeout_s=60)
        try:
            browser.start()
            browser.navigate(served.address)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                shown = browser._evaluate(
                    "document.querySelector('.browser-preflight-details pre')?.textContent || ''"
                )
                if shown:
                    break
                time.sleep(0.2)
            assert isinstance(shown, str) and json.loads(shown) == card["browser_preflight"]
            assert (
                browser._evaluate(
                    "Array.from(document.querySelectorAll('button'))"
                    ".some(b => b.textContent === '允許這次驗證')"
                )
                is True
            )
            assert (
                runtime.chat_authoring.approval(asked.data["approval_id"], runtime.actor).status
                == "pending"
            )
            assert fake.visited == before
        finally:
            browser.close()
            served.shutdown()
            served.server_close()
            thread.join(timeout=10)
