"""Each bot's Telegram identity in Settings → Agents and the sidebar (owner 2026-11-20).
`getMe` is faked; the token never appears in a response."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from test_agents_settings import AGENT_TOKEN, _agent, _telegram_on, web  # noqa: F401
from test_telegram_settings import TOKEN

from host_runtime import bot_identity
from host_runtime.bot_identity import BotIdentities
from host_runtime.web import AgentWeb


class _Reply:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def chunks(self) -> Iterator[bytes]:
        yield self._body

    def close(self) -> None:
        return None


class FakeTelegram:
    """getMe answers by token: known bots get a name, others 401."""

    def __init__(self, bots: Mapping[str, tuple[str, str]]) -> None:
        self.bots = dict(bots)
        self.calls = 0

    def send(self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float) -> _Reply:
        self.calls += 1
        assert url.endswith("/getMe") and timeout_s <= 5
        token = url.split("/bot", 1)[1].rsplit("/", 1)[0]
        if token not in self.bots:
            return _Reply(401, b'{"ok":false,"error_code":401}')
        username, name = self.bots[token]
        result = {"id": 1, "is_bot": True, "first_name": name, "username": username}
        return _Reply(200, json.dumps({"ok": True, "result": result}).encode())


def test_identities_are_cached_by_fingerprint_and_failures_are_codes() -> None:
    fake = FakeTelegram({TOKEN: ("aep_main_bot", "AEP Main")})
    identities = BotIdentities(fake)
    first = identities.identities([TOKEN, "1:bad", ""])
    assert first == [
        {"username": "aep_main_bot", "title": "AEP Main", "problem": None},
        {"username": None, "title": None, "problem": "token_invalid"},
        {"username": None, "title": None, "problem": "token_missing"},
    ]
    identities.identities([TOKEN])
    assert fake.calls == 2  # cached
    assert all(TOKEN not in key for key in identities._cache)
    identities.clear()
    identities.identities([TOKEN])
    assert fake.calls == 3

    class Down:
        def send(self, *args: object) -> _Reply:
            raise TimeoutError("timed out")

    assert BotIdentities(Down()).identities([TOKEN])[0]["problem"] == "network_unreachable"


def test_settings_and_sidebar_show_each_bots_username_never_its_token(
    web: AgentWeb,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeTelegram(
        {TOKEN: ("aep_main_bot", "AEP Main"), AGENT_TOKEN: ("aep_sales_bot", "Sales")}
    )
    monkeypatch.setattr(bot_identity, "TRANSPORT_FACTORY", lambda: fake)
    monkeypatch.setenv("AEP_TG_SALES", "unset")  # recorded, so teardown removes it
    monkeypatch.delenv("AEP_TG_SALES")
    monkeypatch.setenv("AEP_TG_OPS", "unset")  # recorded, so teardown removes it
    monkeypatch.delenv("AEP_TG_OPS")
    _telegram_on(web)
    web.agent_settings_action(
        "/api/settings/agents",
        _agent(id="sales", bot={"variable": "", "token": AGENT_TOKEN, "senders": []}),
    )
    view = web.agent_settings_action(
        "/api/settings/agents",
        _agent(id="ops", name="Ops", bot={"variable": "AEP_TG_OPS", "senders": []}),
    )
    assert view["main"]["bot"]["username"] == "aep_main_bot"
    bots = {agent["id"]: agent["bot"] for agent in view["agents"]}
    assert bots["sales"]["username"] == "aep_sales_bot" and bots["sales"]["title"] == "Sales"
    # A bot whose variable is empty says so.
    assert bots["ops"]["username"] is None and bots["ops"]["problem"] == "token_missing"
    sidebar = web.agents_overview()
    badges = {agent["id"]: agent["bot"] for agent in sidebar["agents"]}
    assert badges["main"]["username"] == "aep_main_bot"
    assert badges["sales"]["username"] == "aep_sales_bot"
    for response in (view, sidebar):
        text = json.dumps(response, ensure_ascii=False, default=str)
        assert TOKEN.split(":")[1] not in text and AGENT_TOKEN.split(":")[1] not in text


def test_the_page_shows_username_first_and_a_bind_button(tmp_path: Path) -> None:
    from host_runtime.web_page import PAGE

    assert 'name = bot.username ? "@" + bot.username' in PAGE
    assert 'bind.append(text("綁定"))' in PAGE
    assert 'empty.append(text("還沒有子代理。")' in PAGE
    assert 'mark.className = "tg-mark"' in PAGE
