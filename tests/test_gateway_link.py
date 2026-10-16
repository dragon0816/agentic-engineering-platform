"""Agent Web and Telegram with the built-in LLM gateway (docs/phases/LLM_GATEWAY.md).

The Settings card's answers and actions, `aep-host gateway`, and the plain
answer a failed model turn gets when the gateway is down, still starting or
rejecting the token. Everything runs on fakes: no test touches port 4000,
the owner's gateway, Task Scheduler or the registry.
"""

from __future__ import annotations

import json
import socket
import subprocess
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from test_host_models import binding, endpoint
from test_host_wiring import device, host_json, ready

from common.execution import Failure
from host_runtime.cli import main as host_main
from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.conversations import ConversationTurnRequest
from host_runtime.gateway_link import explain_model_failure, gateway_card, gateway_port
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE
from llm_gateway import control
from llm_gateway import state as gateway_state
from llm_gateway.config import GatewayPaths, GatewaySettings, init_home, save_settings

REPO = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def default_fragment_config() -> CompanyHostConfiguration:
    fragment = json.loads(
        (REPO / "deploy" / "windows-preview" / "gateway-default.json").read_text(encoding="utf-8")
    )
    return CompanyHostConfiguration.model_validate(
        {"device": device(), "workspace_root": str(REPO), **fragment}
    )


def gateway_home(tmp_path: Path, **changes: Any) -> GatewayPaths:
    paths = GatewayPaths(tmp_path / "gateway")
    save_settings(paths, GatewaySettings(**changes))
    init_home(paths)
    paths.secrets.write_text("LITELLM_MASTER_KEY=local-test-key\n", encoding="utf-8")
    return paths


# --- the explanation -------------------------------------------------------------


def test_the_shipped_model_goes_through_the_gateway_port() -> None:
    assert gateway_port(default_fragment_config()) == 4000


def test_a_failed_turn_says_the_gateway_is_not_running(tmp_path: Path) -> None:
    text = explain_model_failure(
        default_fragment_config(),
        Failure(code="model_unreachable", message="refused"),
        paths=GatewayPaths(tmp_path),
        probe=lambda port: False,
    )
    assert text is not None and "not running" in text and "Settings > LLM gateway" in text


def test_a_failed_turn_says_the_gateway_is_still_starting(tmp_path: Path) -> None:
    paths = GatewayPaths(tmp_path)
    gateway_state.update(paths.state, pid=321, port=4000, started_at="2026-10-16T01:00:00+00:00")
    started = datetime.fromisoformat("2026-10-16T01:00:00+00:00").timestamp()
    text = explain_model_failure(
        default_fragment_config(),
        Failure(code="model_timeout", message="slow"),
        paths=paths,
        probe=lambda port: False,
        alive=lambda pid: pid == 321,
        now=lambda: started + 42,
    )
    assert text is not None and "still starting (started 42 s ago)" in text


def test_a_401_says_the_token_has_probably_expired(tmp_path: Path) -> None:
    text = explain_model_failure(
        default_fragment_config(),
        Failure(code="model_http_error", message="401: Authentication Error"),
        paths=GatewayPaths(tmp_path),
        probe=lambda port: True,
    )
    assert text is not None and "401" in text and "Renew the token" in text


@pytest.mark.parametrize(
    "failure",
    [
        None,
        Failure(code="model_output_truncated", message="cut"),
        Failure(code="model_http_error", message="503: busy"),
    ],
)
def test_other_failures_keep_their_own_answer(tmp_path: Path, failure: Failure | None) -> None:
    assert (
        explain_model_failure(
            default_fragment_config(), failure, paths=GatewayPaths(tmp_path), probe=lambda p: True
        )
        is None
    )


def test_a_model_not_on_this_computer_is_not_explained_by_the_gateway(tmp_path: Path) -> None:
    config, _layout = ready(tmp_path, config_changes={"models": binding(), "credentials": []})
    assert gateway_port(config) is None
    assert (
        explain_model_failure(
            config, Failure(code="model_unreachable", message="x"), probe=lambda p: False
        )
        is None
    )


# --- a real conversation turn in Agent Web ----------------------------------------


def unreachable_model_config(tmp_path: Path, port: int) -> tuple[Any, Any]:
    return ready(
        tmp_path,
        config_changes={
            "models": binding(
                catalog={
                    "endpoints": [
                        endpoint(credential=None, base_url=f"http://127.0.0.1:{port}/v1")
                    ],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            )
        },
    )


def test_agent_web_answers_not_running_when_the_gateway_is_down(tmp_path: Path) -> None:
    port = free_port()
    config, layout = unreachable_model_config(tmp_path, port)
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime)
        web.gateway_paths = GatewayPaths(tmp_path / "gateway")
        web.gateway_probe = lambda candidate: False
        created = web.create_conversation()["conversation"]
        result = web.conversation_turn(
            ConversationTurnRequest(session_id=created["session_id"], message="hello there")
        )
    assert result["ok"] is False
    assert f"not running (127.0.0.1:{port})" in result["answer"]["answer"]
    assert result["conversation"]["messages"][-1]["text"] == result["answer"]["answer"]


def test_telegram_answers_not_running_when_the_gateway_is_down(tmp_path: Path) -> None:
    from test_telegram_ingress import OWNER, FakeTransport, ingress, poll, update

    from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

    class Down:
        def generate(self, item: ModelRequest) -> ModelResponse:
            return ModelResponse(
                trace=item.trace,
                model_alias=item.model_alias,
                failure=Failure(code="model_unreachable", message="refused", retryable=True),
            )

        def stream(self, item: ModelRequest) -> Iterator[ModelStreamEvent]:
            raise NotImplementedError

    transport = FakeTransport([[update(1, OWNER, "what can you do")]])
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.router.model = Down()
    item.explain_failure = lambda failure: (
        "The LLM gateway is not running." if failure.code == "model_unreachable" else None
    )
    delivery = poll(item).deliveries[0]
    assert delivery.reply == "The LLM gateway is not running."


# --- the Settings card ----------------------------------------------------------


@pytest.fixture
def web(tmp_path: Path) -> Iterator[AgentWeb]:
    config, layout = ready(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        agent_web = AgentWeb(runtime, config_path=host_json(tmp_path, config))
        agent_web.gateway_paths = gateway_home(tmp_path)
        agent_web.gateway_probe = lambda port: False
        agent_web.gateway_alive = lambda pid: False
        agent_web.gateway_autostart_query = lambda: {"on": False}
        yield agent_web


def test_the_card_shows_status_without_any_secret(web: AgentWeb) -> None:
    card = web.gateway_settings()
    assert card["state"] == "stopped" and card["port"] == 4000 and card["managed"] is True
    assert card["key_present"] is True and card["installed"] is True
    assert "local-test-key" not in json.dumps(card)
    assert card["model_uses_gateway"] is False  # this host has no model


def test_start_from_the_card_spawns_the_launcher_and_shows_starting(web: AgentWeb) -> None:
    spawned: list[Sequence[str]] = []

    def spawner(command: Sequence[str], log: Path, environ: Mapping[str, str]) -> int:
        spawned.append(command)
        return 4711

    web.gateway_spawner = spawner
    web.gateway_alive = lambda pid: pid == 4711
    done = web.gateway_action({"action": "start"})
    assert done["ok"] is True and done["state"] == "starting" and done["started_at"]
    assert "llm_gateway.launcher" in spawned[0]


def test_a_gateway_run_outside_aep_is_shown_and_tested_only(web: AgentWeb) -> None:
    settings = GatewaySettings(managed=False, secrets_file=str(web.gateway_paths.secrets))
    save_settings(web.gateway_paths, settings)
    web.gateway_probe = lambda port: True
    killed: list[int] = []
    web.gateway_killer = killed.append
    for action in ("start", "restart", "stop", "refresh"):
        done = web.gateway_action({"action": action, "on": True})
        if action == "start":
            # Already serving: nothing to start, nothing refused.
            assert done["ok"] is True and done["state"] == "serving"
        elif action == "refresh":
            assert done["refresh"]["code"] == "not_managed"
        else:
            assert done["ok"] is False and done["code"] == "not_managed", done
    autostart = web.gateway_action({"action": "autostart", "on": True})
    assert autostart["code"] == "not_managed" and killed == []
    assert web.gateway_settings()["managed"] is False


def test_autostart_from_the_card_uses_the_injected_scheduler(web: AgentWeb) -> None:
    calls: list[Sequence[str]] = []

    def runner(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(arguments))
        return subprocess.CompletedProcess(list(arguments), 0, "", "")

    web.gateway_command_runner = runner
    done = web.gateway_action({"action": "autostart", "on": True})
    assert done["autostart_result"]["task"] is True and "-AtLogOn" in calls[0][-1]
    off = web.gateway_action({"action": "autostart", "on": False})
    assert off["autostart_result"]["on"] is False


def test_an_unknown_action_is_refused(web: AgentWeb) -> None:
    assert web.gateway_action({"action": "format-c"})["code"] == "gateway_action_unknown"


def test_the_card_names_the_gateway_the_model_uses(tmp_path: Path) -> None:
    card = gateway_card(
        default_fragment_config(),
        paths=gateway_home(tmp_path),
        probe=lambda port: True,
        alive=lambda pid: False,
    )
    assert card["model_uses_gateway"] is True and card["state"] == "serving"
    assert card["ours"] is False


def test_the_page_has_the_gateway_card_and_links_the_model_card_to_it() -> None:
    for part in (
        'id="gateway-card"',
        'id="gateway-state"',
        'id="gateway-start"',
        'id="gateway-restart"',
        'id="gateway-refresh"',
        'id="gateway-test"',
        'id="gateway-autostart"',
        'id="model-gateway-link"',
        "/api/settings/gateway",
        'starting: "Starting…"',
        "Uses the built-in gateway at ",
    ):
        assert part in PAGE, part
    assert PAGE.index('id="gateway-card"') < PAGE.index('id="model-settings"')


def test_the_card_routes_answer_over_http(tmp_path: Path) -> None:
    import urllib.request

    config, layout = ready(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        agent_web = AgentWeb(runtime, config_path=host_json(tmp_path, config))
        agent_web.gateway_paths = gateway_home(tmp_path)
        agent_web.gateway_probe = lambda port: False
        agent_web.gateway_autostart_query = None
        server = AgentWebServer(agent_web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            headers = {"Authorization": f"Bearer {server.token}"}
            with urllib.request.urlopen(
                urllib.request.Request(base + "/api/settings/gateway", headers=headers)
            ) as reply:
                card = json.loads(reply.read())
            request = urllib.request.Request(
                base + "/api/settings/gateway",
                data=json.dumps({"action": "nothing"}).encode(),
                headers={**headers, "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request) as reply:
                refused = json.loads(reply.read())
        finally:
            server.shutdown()
            server.server_close()
    assert card["state"] == "stopped"
    assert refused == {"ok": False, "code": "gateway_action_unknown"}


# --- aep-host gateway ----------------------------------------------------------


def test_aep_host_gateway_init_and_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(control, "autostart_query", lambda: {"on": False})
    home = tmp_path / "gw"
    python = tmp_path / "gateway-venv" / "Scripts" / "python.exe"
    assert (
        host_main(
            ["gateway", "--home", str(home), "init", "--python", str(python), "--port", "4123"]
        )
        == 0
    )
    settings = json.loads((home / "gateway.json").read_text(encoding="utf-8"))
    assert settings["python"] == str(python) and settings["port"] == 4123
    assert host_main(["gateway", "--home", str(home), "status", "--json"]) == 0
    output = capsys.readouterr().out
    status = json.loads(output[output.index("{") :])
    assert status["port"] == 4123 and status["config_ok"] is True


def test_aep_host_gateway_init_for_a_gateway_run_elsewhere_writes_no_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    elsewhere = tmp_path / "owner" / ".env"
    elsewhere.parent.mkdir()
    elsewhere.write_text("CHATRS_TOKEN=\n", encoding="utf-8")
    before = elsewhere.read_bytes()
    home = tmp_path / "gw"
    assert (
        host_main(
            [
                "gateway",
                "--home",
                str(home),
                "init",
                "--unmanaged",
                "--secrets-file",
                str(elsewhere),
            ]
        )
        == 0
    )
    settings = json.loads((home / "gateway.json").read_text(encoding="utf-8"))
    assert settings["managed"] is False and settings["secrets_file"] == str(elsewhere)
    assert elsewhere.read_bytes() == before and not (home / "gateway.env").exists()
    assert host_main(["gateway", "--home", str(home), "stop"]) == 2
    assert host_main(["gateway", "--home", str(home), "autostart", "--on"]) == 2


def test_the_local_key_goes_to_the_user_environment_only_when_none_is_there() -> None:
    class Fake(control.UserEnvironment):
        def __init__(self, value: str | None) -> None:
            self.value = value

        def get(self, name: str) -> str | None:
            return self.value

        def set(self, name: str, value: str) -> None:
            self.value = value

    empty = Fake(None)
    assert control.export_master_key("sk-aep-new", {}, empty) and empty.value == "sk-aep-new"
    kept = Fake("sk-existing")
    assert not control.export_master_key("sk-aep-new", {}, kept) and kept.value == "sk-existing"
    assert not control.export_master_key("sk-aep-new", {"LITELLM_MASTER_KEY": "x"}, Fake(None))


# --- the card in a real browser ---------------------------------------------------


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_card_renders_starting_and_its_buttons_in_a_real_browser(tmp_path: Path) -> None:
    """Measured: the card is laid out, says "Starting…" while the process
    exists and the port does not answer, and its buttons are big enough to
    press; the Natural-language model card links to it."""
    from integrations.browser import Browser

    config = default_fragment_config()
    _config, layout = ready(tmp_path)
    config = config.model_copy(update={"workspace_root": str(layout.workspace_root)})
    with build_runtime(config, layout=layout) as runtime:
        agent_web = AgentWeb(runtime, config_path=host_json(tmp_path, config))
        paths = gateway_home(tmp_path)
        gateway_state.update(paths.state, pid=99, port=4000, started_at=gateway_state.now_text())
        agent_web.gateway_paths = paths
        agent_web.gateway_probe = lambda port: False
        agent_web.gateway_alive = lambda pid: pid == 99
        agent_web.gateway_autostart_query = lambda: {"on": True}
        server = AgentWebServer(agent_web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()

        def wait(expression: str, seconds: float = 40) -> object:
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

        try:
            browser.navigate(server.address)
            wait('!document.getElementById("send").disabled')
            browser._evaluate('document.getElementById("nav-settings").click()')
            wait('document.getElementById("gateway-state").textContent.includes("Starting")')
            state = str(browser._evaluate('document.getElementById("gateway-state").textContent'))
            assert "127.0.0.1:4000" in state and "started" in state
            width, height = measure("#gateway-card")
            assert width >= 280 and height >= 150, (width, height)
            start_w, start_h = measure("#gateway-start")
            assert start_w >= 88 and start_h >= 44, (start_w, start_h)
            assert browser._evaluate('document.getElementById("gateway-start").disabled') is True
            assert browser._evaluate('document.getElementById("gateway-autostart").checked') is True
            link = str(
                browser._evaluate('document.getElementById("model-gateway-link").textContent')
            )
            assert "Uses the built-in gateway at 127.0.0.1:4000" in link
            assert "local-test-key" not in str(browser._evaluate("document.body.innerText"))
            print(f"gateway card {width}x{height}, Start {start_w}x{start_h}")
        finally:
            browser.close()
            server.shutdown()
            server.server_close()
