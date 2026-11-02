"""`aep_bi_query`: external agents read BI cards, off until the owner turns it on.

`docs/phases/BI_VAULT_ASKING.md` §5. Through the real `/mcp` route and the Bridge, on a
vault made, pushed and published on another PC. All data is fictional.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import test_bi_vault as bi
from test_agent_web import base, fetch
from test_host_wiring import host_json
from test_vault_asking_e2e import _bi_host, _bi_join, _bi_published

from host_runtime import assistant_bridge
from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE

NOTE_WORDS = "讓外部 coding agent 讀取 BI 知識卡片"


@contextmanager
def _served(config: Any, layout: Any, root: Path) -> Iterator[AgentWebServer]:
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime, config_path=host_json(root, config))
        web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


@contextmanager
def _joined(tmp_path: Path, **host: Any) -> Iterator[tuple[AgentWebServer, str, str, Any]]:
    folder, vault_id, dataset, publisher = _bi_published(tmp_path)
    config, layout = _bi_host(tmp_path, **host)
    _bi_join(layout.workspace_root, folder)
    with _served(config, layout, tmp_path) as server:
        yield server, vault_id, dataset, publisher


def _rpc(server: AgentWebServer, method: str, params: Any = None) -> dict[str, Any]:
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    reply = fetch(base(server) + "/mcp", token=server.web.assistant_token, body=body)
    assert reply.status == 200, reply.body
    return dict(reply.json()["result"])


def _call(server: AgentWebServer, **arguments: Any) -> dict[str, Any]:
    result = _rpc(server, "tools/call", {"name": "aep_bi_query", "arguments": arguments})
    return dict(result["structuredContent"])


def _names(server: AgentWebServer) -> set[str]:
    return {tool["name"] for tool in _rpc(server, "tools/list")["tools"]}


def _switch(server: AgentWebServer, enabled: bool) -> dict[str, Any]:
    reply = fetch(
        base(server) + "/api/coding-agents/bi-query",
        token=server.token,
        body={"enabled": enabled},
    )
    assert reply.status == 200, reply.body
    return dict(reply.json())


def _search(dataset: str) -> dict[str, Any]:
    return {"dataset": dataset, "entity_type": "Technology", "text": "TSN"}


def test_it_is_off_by_default_hidden_and_refused(tmp_path: Path) -> None:
    with _joined(tmp_path) as (server, _, dataset, _):
        assert "aep_bi_query" not in _names(server)
        answer = _call(server, **_search(dataset))
        assert answer["ok"] is False and answer["code"] == "bi_query_off"
        assert "FACT" not in json.dumps(answer)
        assert fetch(base(server) + "/api/coding-agents", token=server.token).json()[
            "bi_query"
        ] == {"enabled": False}


def test_the_stdio_list_still_names_it_and_says_it_may_be_off() -> None:
    # The known limit: stdio lists from the constant, without reaching Agent Web.
    reply = assistant_bridge.Bridge(None, "test").handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )
    assert reply is not None
    found = {tool["name"]: tool for tool in reply["result"]["tools"]}
    description = found["aep_bi_query"]["description"]
    assert "off until the owner" in description and "bi_query_off" in description


def test_turned_on_it_answers_from_the_published_version_with_the_source_line(
    tmp_path: Path,
) -> None:
    with _joined(tmp_path) as (server, vault_id, dataset, publisher):
        saved = _switch(server, True)
        assert saved["bi_query"] == {"enabled": True}
        # Saved, and live with no restart.
        path = server.web.config_path
        assert path is not None
        config = CompanyHostConfiguration.model_validate_json(path.read_text(encoding="utf-8-sig"))
        assert config.assistant_bi_query is True
        assert "aep_bi_query" in _names(server)
        answer = _call(server, **_search(dataset))
        assert answer["ok"] is True, answer
        assert "FACT-PUBLISHED" in json.dumps(answer["cards"], ensure_ascii=False)
        assert answer["source"] == f"資料來源：知識庫 {dataset} 發佈版本 v1"
        assert answer["reads"]["tag"] == "v1"
        # A push after the tag is not read; the source line does not move.
        bi._ok(bi._edit(publisher, dataset, "TSN", "standard_body", "FACT-PUSHED", "alice"))
        bi._commit(publisher, vault_id, "發佈後")
        bi._push(publisher, vault_id)
        later = json.dumps(_call(server, **_search(dataset)), ensure_ascii=False)
        assert "FACT-PUBLISHED" in later and "FACT-PUSHED" not in later
        # Turned off, it stops at once.
        assert _switch(server, False)["bi_query"] == {"enabled": False}
        assert _call(server, **_search(dataset))["code"] == "bi_query_off"


def test_a_saved_analysis_and_a_built_in_query_are_answered(tmp_path: Path) -> None:
    with _joined(tmp_path) as (server, _, dataset, _):
        _switch(server, True)
        quality = _call(server, dataset=dataset, analysis="quality")
        assert quality["ok"] is True, quality
        assert quality["analysis"]
        assert _call(server, dataset=dataset, analysis="no-such")["code"] == "analysis_unknown"


@pytest.mark.parametrize("sql", ["SELECT 1", ""])
def test_sql_is_refused_even_when_on(tmp_path: Path, sql: str) -> None:
    with _joined(tmp_path) as (server, _, dataset, _):
        _switch(server, True)
        answer = _call(server, dataset=dataset, sql=sql)
    assert answer["ok"] is False and answer["code"] == "sql_not_allowed"


def test_only_vaults_are_read_and_a_missing_one_names_those_there_are(tmp_path: Path) -> None:
    with _joined(tmp_path) as (server, _, dataset, _):
        _switch(server, True)
        missing = _call(server)
        assert missing["code"] == "dataset_missing"
        assert [item["dataset"] for item in missing["vaults"]] == [dataset]
        assert _call(server, dataset="demo")["code"] == "not_a_vault"
        assert _call(server, dataset="vault-no-such")["code"] == "not_a_vault"


def test_without_the_grant_or_the_skill_it_answers_nothing(tmp_path: Path) -> None:
    with _joined(tmp_path / "no-grant", granted=False) as (server, _, dataset, _):
        _switch(server, True)
        denied = _call(server, **_search(dataset))
    assert denied["ok"] is False and "FACT" not in json.dumps(denied)
    assert denied["code"] == "permission_denied"
    with _joined(tmp_path / "skill-off", skill_on=False) as (server, _, dataset, _):
        _switch(server, True)
        off = _call(server, **_search(dataset))
    assert off["code"] == "bi_unavailable"


def test_the_switch_needs_the_agent_web_token_and_a_writable_host_json(tmp_path: Path) -> None:
    with _joined(tmp_path) as (server, _, _, _):
        url = base(server) + "/api/coding-agents/bi-query"
        assert fetch(url, body={"enabled": True}).status == 401
        # The token external agents hold cannot turn it on.
        own = fetch(url, token=server.web.assistant_token, body={"enabled": True})
        assert own.status == 401
        assert fetch(url, token=server.token, body={"enabled": "yes"}).status == 409
        assert server.web.runtime.config.assistant_bi_query is False
        server.web.config_path = None
        assert fetch(url, token=server.token, body={"enabled": True}).status == 409


def test_the_chat_cannot_turn_it_on(tmp_path: Path) -> None:
    from common.change_proposal import KINDS

    assert not {"assistant", "bi_query", "assistant_bi_query"} & set(KINDS)
    assert NOTE_WORDS in PAGE


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_settings_card_shows_the_switch_and_turns_it_on(tmp_path: Path) -> None:
    import time

    from integrations.browser import Browser, BrowserError

    with _joined(tmp_path) as (server, _, _, _):
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()

        def wait(expression: str) -> Any:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    value = browser._evaluate(expression)
                except BrowserError:
                    value = None
                if value:
                    return value
                time.sleep(0.1)
            raise AssertionError(expression)

        try:
            browser.navigate(server.address)
            wait('!!document.getElementById("nav-settings")')
            browser._evaluate("loadCodingAgents()")
            wait('document.getElementById("coding-agents").textContent.includes("aep_bi_query")')
            assert browser._evaluate('document.getElementById("bi-query-on").checked') is False
            browser._evaluate('document.getElementById("bi-query-on").click()')
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and not server.web.runtime.config.assistant_bi_query:
                time.sleep(0.1)
            assert server.web.runtime.config.assistant_bi_query is True
        finally:
            browser.close()
