"""Settings → Agents and agent-owned conversations (owner consent 2026-11-20,
docs/DECISIONS.md "Sidebar sections and agents bound to Telegram bots").

The page keeps persistent sub-agents (AgentProfile fields V1 allows), binds each to a
Telegram bot by the *name* of the environment variable holding its token (a pasted
token is refused and nothing is written), lists the BI collection bots as 「BI 收集→領域」,
and writes `agents.json`, `telegram.json` and `host.json` atomically, keeping every
other field. Saved bots apply without a restart, but only once no Telegram turn or
flow is running (AGENTS rule 19). A conversation a sub-agent owns offers only its
Skills' tools; the sidebar's Agents list shows its conversations and the delegation
records of its profile.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr
from test_host_wiring import host_json, ready
from test_telegram_settings import TOKEN, Store, _update

from common.execution import TraceIdentifiers
from common.local_agent import LocalAgentRequest
from host_runtime import agents_settings
from host_runtime import web as web_module
from host_runtime.agents_settings import (
    AgentForm,
    AgentSettingsError,
    CollectionBotForm,
    agents_view,
    checked_token,
    checked_variable,
    default_variable,
    save_agent,
    save_collection_bot,
)
from host_runtime.conversations import ConversationMessage, ConversationRecord
from host_runtime.host import HostRuntime, build_runtime
from host_runtime.persistent_agents import AgentStore, PersistentAgent
from host_runtime.telegram_settings import TelegramSettingsError
from host_runtime.web import AgentWeb

#: A second bot's token (the conversation bot holds TOKEN).
AGENT_TOKEN = "987654321:BBz" + "y" * 33


@pytest.fixture
def web(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[AgentWeb]:
    monkeypatch.setattr(web_module, "BOT_RELOAD_POLL_S", 0.02)
    monkeypatch.setenv("AEP_TELEGRAM_BOT_TOKEN", TOKEN)
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        page = AgentWeb(runtime, config_path=path)
        page.user_environment = Store()
        page.started = 0  # type: ignore[attr-defined]

        def started() -> None:  # no network in tests
            page.started += 1  # type: ignore[attr-defined]

        monkeypatch.setattr(page, "start_telegram", started)
        yield page


def _telegram_on(page: AgentWeb) -> None:
    assert page.update_telegram_settings(_update())["ok"] is True


def _wait(page: AgentWeb, state: str) -> None:
    deadline = time.monotonic() + 10
    while page._bots_reload != state and time.monotonic() < deadline:
        time.sleep(0.02)
    assert page._bots_reload == state


def _agent(**changes: Any) -> dict[str, Any]:
    return {
        "name": "Sales",
        "purpose": "Answer shipment questions.",
        "skills": [],
        "bot": {
            "variable": "AEP_TG_SALES",
            "senders": [{"sender_id": 42, "actor": ""}],
            "enabled": True,
        },
        **changes,
    }


def test_a_pasted_token_is_refused_and_a_name_is_kept() -> None:
    for pasted in (TOKEN, f"bot{TOKEN}", f" {TOKEN} ", "123:abc"):
        with pytest.raises(AgentSettingsError, match="bot_token_value_refused"):
            checked_variable(pasted)
    with pytest.raises(AgentSettingsError, match="bot_variable_invalid"):
        checked_variable("not a name")
    assert checked_variable("  AEP_TG_SALES ") == "AEP_TG_SALES"


def test_agents_are_created_edited_bound_and_deleted_on_the_page(web: AgentWeb) -> None:
    _telegram_on(web)
    runtime = web.runtime
    assert runtime.telegram is not None
    view = web.agent_settings_action("/api/settings/agents", _agent())
    assert view["ok"] is True, view
    (agent,) = view["agents"]
    assert agent["name"] == "Sales" and agent["model_policy"] == "session"
    bot = agent["bot"]
    assert bot["variable"] == "AEP_TG_SALES" and bot["token_present"] is False
    assert bot["senders"] == [{"sender_id": 42, "actor": runtime.actor}]
    # host.json maps the bot's secret to the variable; telegram.json holds the bot.
    assert runtime.config.credential_environment()[f"telegram_agent_{agent['id']}"] == (
        "AEP_TG_SALES"
    )
    saved = json.loads(runtime.layout.telegram.read_text(encoding="utf-8"))
    assert saved["agent_bots"][0]["agent"] == agent["id"]
    assert saved["senders"] == [{"sender_id": 42, "actor": "engineer"}]  # kept
    # Applied without a restart: the conversation bot now polls the agent bot too.
    _wait(web, "applied")
    assert [b.owner_agent for b in runtime.telegram.agent_bots] == [agent["id"]]
    assert web.started >= 1  # type: ignore[attr-defined]

    # Edit: off, renamed; the record is the same agent.
    edited = web.agent_settings_action(
        "/api/settings/agents",
        _agent(id=agent["id"], name="Sales desk", bot={**_agent()["bot"], "enabled": False}),
    )
    assert [a["name"] for a in edited["agents"]] == ["Sales desk"]
    assert edited["agents"][0]["bot"]["enabled"] is False
    _wait(web, "applied")
    assert runtime.telegram.agent_bots == []

    deleted = web.agent_settings_action("/api/settings/agents/delete", {"id": agent["id"]})
    assert deleted["agents"] == []
    assert "agent_bots" not in json.loads(runtime.layout.telegram.read_text(encoding="utf-8"))
    assert web.agent_settings_action("/api/settings/agents/delete", {"id": agent["id"]}) == {
        "ok": False,
        "code": "agent_unknown",
    }


def test_main_senders_carry_the_username_they_last_wrote_with(web: AgentWeb) -> None:
    """The page turns a typed @username into the numeric id (owner report
    2026-11-21); unknown usernames stay empty."""
    _telegram_on(web)
    assert web.runtime.telegram is not None
    assert web.agent_settings()["main"]["bot"]["senders"] == [
        {"sender_id": 42, "actor": "engineer", "username": ""}
    ]
    web.runtime.telegram.sender_usernames[42] = "leo_oel_0816"
    assert web.agent_settings()["main"]["bot"]["senders"][0]["username"] == "leo_oel_0816"


def test_skills_are_offered_with_a_name_and_a_one_line_description(tmp_path: Path) -> None:
    from host_runtime.agents_settings import skill_choices

    folder = tmp_path / "skills"
    folder.mkdir()
    (folder / "company-agent__knowledge-query__1.12.0.json").write_text(
        json.dumps(
            {
                "alias": "knowledge-query",
                "instructions": "Answer from the company Knowledge with citations. Then stop.",
            }
        ),
        encoding="utf-8",
    )
    (folder / "engineering__bi-knowledge__1.0.0.json").write_text(
        json.dumps(
            [{"alias": "bi", "selector_hint": "BI 資料查詢：" + "很長" * 60, "instructions": "x"}]
        ),
        encoding="utf-8",
    )
    (folder / "broken__thing__1.0.0.json").write_text("{", encoding="utf-8")
    choices = skill_choices(folder)
    assert [c["key"] for c in choices] == [
        "engineering/bi-knowledge@1.0.0",
        "company-agent/knowledge-query@1.12.0",
        "broken/thing@1.0.0",
    ]
    bi, query, broken = choices
    assert bi["name"] == "bi" and bi["description"].startswith("BI 資料查詢：")
    assert len(bi["description"]) == agents_settings.SKILL_DESCRIPTION_CHARS
    assert bi["description"].endswith("…")
    assert broken == {"key": "broken/thing@1.0.0", "name": "thing", "description": ""}
    assert query["description"] == "Answer from the company Knowledge with citations."


def test_a_pasted_token_writes_nothing(web: AgentWeb) -> None:
    _telegram_on(web)
    layout = web.runtime.layout
    assert web.config_path is not None
    files = [web.config_path, layout.telegram, layout.workspace_root / "agents.json"]
    before = [p.read_bytes() if p.exists() else None for p in files]
    refused = web.agent_settings_action(
        "/api/settings/agents", _agent(bot={"variable": TOKEN, "senders": []})
    )
    assert refused == {"ok": False, "code": "bot_token_value_refused"}
    assert [p.read_bytes() if p.exists() else None for p in files] == before
    for written in files:
        if written.exists():
            assert TOKEN.split(":")[1] not in written.read_text(encoding="utf-8")


def test_a_bot_needs_the_conversation_bot_configured_first(web: AgentWeb) -> None:
    refused = web.agent_settings_action("/api/settings/agents", _agent())
    assert refused == {"ok": False, "code": "telegram_not_configured"}
    plain = web.agent_settings_action("/api/settings/agents", _agent(bot=None))
    assert plain["ok"] is True and plain["agents"][0]["bot"] is None
    assert plain["reload"] == "not_running"


def test_writes_are_atomic_and_keep_every_other_field(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    raw_host = json.loads(path.read_text(encoding="utf-8"))
    layout.telegram.write_text(
        json.dumps(
            {
                "credential": {"name": "telegram_bot"},
                "bridge_id": config.device.bridge_id,
                "namespace": "engineering",
                "senders": [{"sender_id": 7, "actor": "engineer"}],
                "poll_timeout_seconds": 10,
            }
        ),
        encoding="utf-8",
    )
    (layout.workspace_root / "agents.json").write_text(
        json.dumps({"note": "kept", "agents": [{"id": "ops", "name": "Ops", "colour": "red"}]}),
        encoding="utf-8",
    )
    agent, updated = save_agent(
        path,
        layout,
        AgentForm.model_validate(_agent(id="ops", name="Ops desk")),
        default_actor="engineer",
    )
    assert agent.name == "Ops desk" and updated is not None
    stored = json.loads((layout.workspace_root / "agents.json").read_text(encoding="utf-8"))
    assert stored["note"] == "kept" and stored["agents"][0]["colour"] == "red"
    assert stored["agents"][0]["name"] == "Ops desk"
    host = json.loads(path.read_text(encoding="utf-8"))
    assert {k: v for k, v in host.items() if k != "credentials"} == {
        k: v for k, v in raw_host.items() if k != "credentials"
    }
    telegram = json.loads(layout.telegram.read_text(encoding="utf-8"))
    assert telegram["poll_timeout_seconds"] == 10
    assert telegram["senders"] == [{"sender_id": 7, "actor": "engineer"}]
    # Nothing half-written is left beside them.
    assert not list(tmp_path.rglob("*.part"))


def test_collection_bots_are_listed_and_edited_here(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    layout.telegram.write_text(
        json.dumps(
            {
                "credential": {"name": "telegram_bot"},
                "bridge_id": config.device.bridge_id,
                "namespace": "engineering",
                "collection_bots": [
                    {
                        "name": "bi_aidc",
                        "credential": {"name": "telegram_bi_aidc"},
                        "feature": "bi-knowledge",
                        "target": "aidc",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    form: dict[str, Any] = {
        "name": "bi_aidc",
        "target": "aidc",
        "bot": {"variable": "AEP_TG_BI_AIDC", "senders": [{"sender_id": 5, "actor": ""}]},
    }
    updated = save_collection_bot(
        path, layout, CollectionBotForm.model_validate(form), default_actor="engineer"
    )
    # The existing bot keeps its secret name; only its variable is mapped.
    assert updated.credential_environment()["telegram_bi_aidc"] == "AEP_TG_BI_AIDC"
    added = save_collection_bot(
        path,
        layout,
        CollectionBotForm.model_validate(
            {**form, "name": "bi_rf", "target": "RF", "bot": {**form["bot"], "enabled": False}}
        ),
        default_actor="engineer",
    )
    view = agents_view(added, layout)
    bots = {bot["name"]: bot for bot in view["collection_bots"]}
    assert bots["bi_aidc"]["purpose"] == "BI 收集→aidc"
    assert bots["bi_rf"]["purpose"] == "BI 收集→RF" and bots["bi_rf"]["enabled"] is False
    assert bots["bi_aidc"]["senders"] == [{"sender_id": 5, "actor": "engineer"}]
    assert TOKEN not in json.dumps(view)
    with pytest.raises(AgentSettingsError, match="bot_token_value_refused"):
        save_collection_bot(
            path,
            layout,
            CollectionBotForm.model_validate({**form, "bot": {"variable": TOKEN}}),
            default_actor="engineer",
        )


def test_a_reload_waits_while_a_telegram_turn_runs(web: AgentWeb) -> None:
    _telegram_on(web)
    ingress = web.runtime.telegram
    assert ingress is not None
    ingress._busy[(1, 1)] = datetime.now(UTC)
    before = web.started  # type: ignore[attr-defined]
    view = web.agent_settings_action("/api/settings/agents", _agent())
    assert view["reload"] == "waiting"
    time.sleep(0.2)
    assert web._bots_reload == "waiting" and web.started == before  # type: ignore[attr-defined]
    assert ingress.agent_bots == []
    del ingress._busy[(1, 1)]
    _wait(web, "applied")
    assert len(ingress.agent_bots) == 1


def _request(runtime: HostRuntime, session: str) -> LocalAgentRequest:
    return LocalAgentRequest(
        ingress="local",
        actor=runtime.actor,
        bridge_id=runtime.config.device.bridge_id,
        namespace="engineering",
        message="hi",
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        session_id=session,
    )


def test_a_conversation_an_agent_owns_offers_only_its_skills(web: AgentWeb) -> None:
    runtime = web.runtime
    assert web.create_conversation("nobody") == {"ok": False, "code": "agent_unknown"}
    AgentStore(runtime.layout.workspace_root).save(
        PersistentAgent(id="sales", name="Sales", purpose="Shipments.", skills=())
    )
    created = web.create_conversation("sales")["conversation"]
    assert created["agent"] == "sales"
    options = web._converse_options(_request(runtime, created["session_id"]))
    assert options["allowed_tools"] == frozenset()
    assert 'You are "Sales"' in options["persona_guidance"]
    main = web.create_conversation()["conversation"]
    assert "allowed_tools" not in web._converse_options(_request(runtime, main["session_id"]))
    listed = {item["session_id"]: item["agent"] for item in web.conversations()["conversations"]}
    assert listed[created["session_id"]] == "sales" and listed[main["session_id"]] is None


def test_the_agents_list_shows_each_agents_conversations_and_delegations(web: AgentWeb) -> None:
    runtime = web.runtime
    AgentStore(runtime.layout.workspace_root).save(
        PersistentAgent(
            id="sales", name="Sales", profile="engineering/sales-profile@1.0.0", skills=()
        )
    )
    owned = web.create_conversation("sales")["conversation"]
    now = datetime.now(UTC)
    runtime.state.create_conversation(
        ConversationRecord(
            session_id="conversation-parent",
            actor=runtime.actor,
            title="Parent turn",
            created_at=now,
            updated_at=now,
            messages=(
                ConversationMessage(
                    message_id="m1", role="user", text="ask", created_at=now, status="submitted"
                ),
                ConversationMessage(
                    message_id="m2",
                    role="assistant",
                    text="done",
                    created_at=now,
                    status="answered",
                    delegations=(
                        {
                            "profile": "engineering/sales-profile@1.0.0",
                            "status": "succeeded",
                            "summary": "Three shipments found.",
                        },
                    ),
                ),
            ),
        )
    )
    overview = web.agents_overview()
    main, sales = overview["agents"]
    assert main["main"] is True and main["id"] == "main"
    assert sales["id"] == "sales" and sales["bot"] is None
    kinds = [(e["kind"], e["session_id"]) for e in sales["conversations"]]
    assert ("conversation", owned["session_id"]) in kinds
    assert ("delegation", "conversation-parent") in kinds
    (delegation,) = [e for e in sales["conversations"] if e["kind"] == "delegation"]
    assert delegation["summary"] == "Three shipments found."


# -- A token pasted in the bot's token field (owner decision 2026-11-20) -------


def _written(page: AgentWeb) -> list[Path]:
    assert page.config_path is not None
    return [
        path
        for path in (page.config_path, *page.runtime.layout.workspace_root.rglob("*"))
        if path.is_file()
    ]


def _nowhere(page: AgentWeb, token: str, *views: object) -> None:
    """The token is in no written file and no response; the secret half included."""
    secret = token.split(":")[1].encode("utf-8")
    for path in _written(page):
        assert secret not in path.read_bytes(), path
    for view in views:
        assert secret.decode() not in json.dumps(view, ensure_ascii=False, default=str)


def test_a_pasted_token_must_have_the_bot_token_shape() -> None:
    assert checked_token(None) == ""
    assert checked_token(SecretStr("  ")) == ""
    assert checked_token(SecretStr(f" {AGENT_TOKEN} ")) == AGENT_TOKEN
    assert checked_token(SecretStr(f"bot{AGENT_TOKEN}")) == AGENT_TOKEN
    for bad in ("123:abc", "987654321:" + "y" * 34, "abc:" + "y" * 40, AGENT_TOKEN + " x"):
        with pytest.raises(AgentSettingsError, match="^bot_token_invalid$"):
            checked_token(SecretStr(bad))
    assert default_variable("", "agent-1a2b3c") == "AEP_TG_AGENT_1A2B3C"
    assert default_variable("BI_", "bi.sales-2") == "AEP_TG_BI_BI_SALES_2"


def test_a_pasted_token_goes_only_to_the_user_environment_and_applies_at_once(
    web: AgentWeb, monkeypatch: pytest.MonkeyPatch
) -> None:
    _telegram_on(web)
    monkeypatch.setenv("AEP_TG_SALES", "unset")  # recorded, so teardown removes it
    monkeypatch.delenv("AEP_TG_SALES")
    store = web.user_environment
    assert isinstance(store, Store)
    view = web.agent_settings_action(
        "/api/settings/agents",
        _agent(id="sales", bot={"variable": "", "token": AGENT_TOKEN, "senders": []}),
    )
    assert view["ok"] is True, view
    bot = view["agents"][0]["bot"]
    # The empty name became the default; the page learns only that a token is there.
    assert bot["variable"] == "AEP_TG_SALES" and bot["token_present"] is True
    assert store.saved["AEP_TG_SALES"] == AGENT_TOKEN
    assert os.environ["AEP_TG_SALES"] == AGENT_TOKEN
    assert web.runtime.config.credential_environment()["telegram_agent_sales"] == "AEP_TG_SALES"
    _nowhere(web, AGENT_TOKEN, view, web.agent_settings())
    # The reload resolves the bot's token from the running process at once.
    _wait(web, "applied")
    telegram = web.runtime.telegram
    assert telegram is not None
    (own,) = telegram.agent_bots
    assert own._resolver.resolve(own.config.credential) == AGENT_TOKEN

    # Empty token field: unchanged; a new token overwrites the same variable.
    store.saved.clear()
    kept = web.agent_settings_action("/api/settings/agents", _agent(id="sales"))
    assert kept["ok"] is True and store.saved == {}
    newer = AGENT_TOKEN.replace("y", "z")
    replaced = web.agent_settings_action(
        "/api/settings/agents",
        _agent(id="sales", bot={"variable": "AEP_TG_SALES", "token": newer, "senders": []}),
    )
    assert replaced["ok"] is True and store.saved == {"AEP_TG_SALES": newer}
    assert os.environ["AEP_TG_SALES"] == newer
    _nowhere(web, newer, replaced)

    # Deleting the agent leaves its variable alone.
    web.agent_settings_action("/api/settings/agents/delete", {"id": "sales"})
    assert os.environ["AEP_TG_SALES"] == newer


def test_a_collection_bot_takes_a_pasted_token_too(
    web: AgentWeb, monkeypatch: pytest.MonkeyPatch
) -> None:
    _telegram_on(web)
    monkeypatch.setenv("AEP_TG_BI_BI_RF", "unset")  # recorded, so teardown removes it
    monkeypatch.delenv("AEP_TG_BI_BI_RF")
    view = web.agent_settings_action(
        "/api/settings/collection-bots",
        {"name": "bi_rf", "target": "RF", "bot": {"token": f"bot{AGENT_TOKEN}"}},
    )
    assert view["ok"] is True, view
    (bot,) = view["collection_bots"]
    assert bot["variable"] == "AEP_TG_BI_BI_RF" and bot["token_present"] is True
    assert os.environ["AEP_TG_BI_BI_RF"] == AGENT_TOKEN
    _nowhere(web, AGENT_TOKEN, view)


def test_a_bad_token_or_a_taken_variable_writes_nothing(
    web: AgentWeb, monkeypatch: pytest.MonkeyPatch
) -> None:
    _telegram_on(web)
    monkeypatch.setenv("AEP_TG_SALES", "unset")  # recorded, so teardown removes it
    monkeypatch.delenv("AEP_TG_SALES")
    monkeypatch.setenv("AEP_SOME_PATH", "C:/tools")
    store = web.user_environment
    assert isinstance(store, Store)
    store.saved.clear()
    layout = web.runtime.layout
    assert web.config_path is not None
    files = [web.config_path, layout.telegram, layout.workspace_root / "agents.json"]
    before = [p.read_bytes() if p.exists() else None for p in files]
    cases = {
        # Not a token: the code alone, never what was typed.
        "bot_token_invalid": {"variable": "AEP_TG_SALES", "token": "12345:short"},
        # The conversation bot's variable holds another token.
        "bot_variable_in_use": {"variable": "AEP_TELEGRAM_BOT_TOKEN", "token": AGENT_TOKEN},
        # A variable that holds something other than a bot token is not overwritten.
        "bot_variable_in_use ": {"variable": "AEP_SOME_PATH", "token": AGENT_TOKEN},
    }
    for code, bot in cases.items():
        refused = web.agent_settings_action("/api/settings/agents", _agent(bot=bot))
        assert refused == {"ok": False, "code": code.strip()}
    assert store.saved == {} and os.environ["AEP_TELEGRAM_BOT_TOKEN"] == TOKEN
    assert os.environ["AEP_SOME_PATH"] == "C:/tools" and "AEP_TG_SALES" not in os.environ
    assert [p.read_bytes() if p.exists() else None for p in files] == before
    # The same token again on a shared variable is not a retarget.
    same = web.agent_settings_action(
        "/api/settings/agents",
        _agent(bot={"variable": "AEP_TELEGRAM_BOT_TOKEN", "token": TOKEN}),
    )
    assert same["ok"] is True


def test_a_host_that_cannot_store_a_token_says_so_and_writes_nothing(
    web: AgentWeb, monkeypatch: pytest.MonkeyPatch
) -> None:
    _telegram_on(web)
    monkeypatch.setenv("AEP_TG_SALES", "unset")  # recorded, so teardown removes it
    monkeypatch.delenv("AEP_TG_SALES")

    def unsupported(name: str, value: str) -> None:
        raise TelegramSettingsError("token_store_unavailable")

    web.user_environment = unsupported
    layout = web.runtime.layout
    assert web.config_path is not None
    files = [web.config_path, layout.telegram, layout.workspace_root / "agents.json"]
    before = [p.read_bytes() if p.exists() else None for p in files]
    refused = web.agent_settings_action(
        "/api/settings/agents", _agent(bot={"variable": "AEP_TG_SALES", "token": AGENT_TOKEN})
    )
    assert refused == {"ok": False, "code": "bot_token_store_unsupported"}
    assert "AEP_TG_SALES" not in os.environ
    assert [p.read_bytes() if p.exists() else None for p in files] == before


def test_the_default_store_refuses_off_windows_without_touching_a_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("AEP_TG_SALES", "unset")  # recorded, so teardown removes it
    monkeypatch.delenv("AEP_TG_SALES")
    with pytest.raises(AgentSettingsError, match="^bot_token_store_unsupported$"):
        agents_settings._store_token(None, "AEP_TG_SALES", AGENT_TOKEN)
    assert "AEP_TG_SALES" not in os.environ


def test_the_windows_store_writes_hkcu_and_broadcasts_without_a_command_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """winreg and user32 are fakes: the real registry is never written in tests."""
    import subprocess
    import types

    calls: list[tuple[Any, ...]] = []

    class Key:
        def __enter__(self) -> Key:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    def open_key(root: object, path: str, reserved: int, access: int) -> Key:
        calls.append(("open", root, path))
        return Key()

    def set_value(key: object, name: str, reserved: int, kind: int, value: str) -> None:
        calls.append(("set", name, kind, value))

    def broadcast(*args: object) -> int:
        calls.append(("broadcast", args[0], args[1], args[3]))
        return 1

    winreg = types.SimpleNamespace(
        HKEY_CURRENT_USER="HKCU", KEY_SET_VALUE=2, REG_SZ=1, OpenKey=open_key, SetValueEx=set_value
    )
    ctypes = types.SimpleNamespace(
        windll=types.SimpleNamespace(user32=types.SimpleNamespace(SendMessageTimeoutW=broadcast)),
        c_ulong=lambda: 0,
        byref=lambda value: value,
    )
    spawned: list[object] = []

    def no_process(*args: object, **kwargs: object) -> None:
        spawned.append(args)
        raise AssertionError("a process was started")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winreg", winreg)
    monkeypatch.setitem(sys.modules, "ctypes", ctypes)
    monkeypatch.setattr(subprocess, "Popen", no_process)
    monkeypatch.setenv("AEP_TG_SALES", "unset")  # recorded, so teardown removes it
    monkeypatch.delenv("AEP_TG_SALES")
    agents_settings._store_token(None, "AEP_TG_SALES", AGENT_TOKEN)
    assert calls == [
        ("open", "HKCU", "Environment"),
        ("set", "AEP_TG_SALES", 1, AGENT_TOKEN),
        ("broadcast", 0xFFFF, 0x001A, "Environment"),
    ]
    assert spawned == []  # no setx: the token is on no process command line
    assert os.environ["AEP_TG_SALES"] == AGENT_TOKEN
