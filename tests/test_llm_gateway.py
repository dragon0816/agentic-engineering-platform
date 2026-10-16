"""AEP's built-in LLM gateway (docs/phases/LLM_GATEWAY.md), without LiteLLM.

CI installs only `.[dev,office]`, so everything here runs on fakes: a fake
streaming module for the patch, temporary gateway homes, a fake HTTP server
for `test`, fake runners for Task Scheduler and the Kerberos script. The
tests that need the real LiteLLM skip cleanly where it is not installed.
No test touches the live gateway, port 4000, Task Scheduler or the registry.
"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import os
import socket
import subprocess
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from llm_gateway import (
    DEFAULT_PORT,
    LOOPBACK,
    cli,
    control,
    launcher,
    patch,
    secrets_file,
    token_refresh,
)
from llm_gateway import state as gateway_state
from llm_gateway.config import (
    DEFAULT_MODELS,
    GatewayConfigError,
    GatewayModel,
    GatewayPaths,
    GatewaySettings,
    default_home,
    find_secret_values,
    find_secrets,
    init_home,
    load_settings,
    render_config,
    validate_config_text,
    write_atomically,
)

LOCAL_KEY = "local-test-key-not-a-secret"


def fake_jwt(expires_in_days: float) -> str:
    def part(data: Mapping[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    expiry = int(time.time() + expires_in_days * 86400)
    return part({"alg": "none"}) + "." + part({"exp": expiry, "sub": "test"}) + ".signature"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind((LOOPBACK, 0))
        return int(probe.getsockname()[1])


def home_with(
    tmp_path: Path, *, port: int = DEFAULT_PORT, token: str | None = None, key: str = LOCAL_KEY
) -> GatewayPaths:
    paths = GatewayPaths(tmp_path / "gateway")
    write_atomically(paths.settings, json.dumps(GatewaySettings(port=port).to_json()))
    init_home(paths)
    lines = []
    if token is not None:
        lines.append(f"CHATRS_TOKEN={token}")
    if key:
        lines.append(f"LITELLM_MASTER_KEY={key}")
    paths.secrets.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths


# --- the streaming patch ---------------------------------------------------------


class Chunk:
    def __init__(self, choices: list[str]) -> None:
        self.choices = choices


def fake_streaming_module(with_anext: bool = True) -> ModuleType:
    module = ModuleType("fake_streaming_iterator")

    class Splitter:
        def __init__(self, chunks: Sequence[Chunk]) -> None:
            self.chunks = list(chunks)

        def __iter__(self) -> Splitter:
            return self

        def __next__(self) -> Chunk:
            if not self.chunks:
                raise StopIteration
            return self.chunks.pop(0)

    if with_anext:

        async def anext_(self: Splitter) -> Chunk:
            if not self.chunks:
                raise StopAsyncIteration
            return self.chunks.pop(0)

        Splitter.__anext__ = anext_  # type: ignore[attr-defined]
    module._CombinedChunkSplitter = Splitter  # type: ignore[attr-defined]
    return module


def chunks() -> list[Chunk]:
    return [Chunk([]), Chunk(["a"]), Chunk([]), Chunk(["b"]), Chunk([])]


def test_the_patch_drops_chunks_without_choices_on_both_paths() -> None:
    splitter: Any = patch.apply(fake_streaming_module())
    assert [chunk.choices for chunk in splitter(chunks())] == [["a"], ["b"]]

    async def collect() -> list[list[str]]:
        instance = splitter(chunks())
        seen = []
        while True:
            try:
                seen.append((await instance.__anext__()).choices)
            except StopAsyncIteration:
                return seen

    assert asyncio.run(collect()) == [["a"], ["b"]]


def test_applying_the_patch_twice_does_not_wrap_it_twice() -> None:
    module = fake_streaming_module()
    first: Any = patch.apply(module)
    patched_next = first.__next__
    second: Any = patch.apply(module)
    assert second.__next__ is patched_next


def test_the_patch_fails_loudly_when_litellm_internals_moved() -> None:
    empty = ModuleType("moved")
    with pytest.raises(patch.GatewayPatchError, match="_CombinedChunkSplitter is gone"):
        patch.apply(empty)
    with pytest.raises(patch.GatewayPatchError, match="__anext__"):
        patch.apply(fake_streaming_module(with_anext=False))


def test_without_litellm_the_patch_says_so_instead_of_an_import_error() -> None:
    if importlib.util.find_spec("litellm") is not None:
        pytest.skip("LiteLLM is installed here")
    with pytest.raises(patch.GatewayPatchError, match="streaming adapter is gone"):
        patch.apply()


def test_the_patch_applies_to_the_installed_litellm() -> None:
    pytest.importorskip("litellm")
    splitter = patch.apply()
    assert splitter._aep_empty_choices_patch is True


# --- configuration ---------------------------------------------------------------


def test_the_rendered_configuration_holds_references_not_secrets() -> None:
    text = render_config(GatewaySettings())
    assert validate_config_text(text) == []
    assert find_secrets(text) == []
    assert "api_key: os.environ/CHATRS_TOKEN" in text
    assert "master_key: os.environ/LITELLM_MASTER_KEY" in text
    assert "model: openai/" not in text
    for model in DEFAULT_MODELS:
        assert f"model_name: {model.name}" in text
        assert f"model: hosted_vllm/{model.upstream}" in text
    assert "api_base: https://chatrs.cloud.rsint.net/api" in text


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ("api_key: os.environ/CHATRS_TOKEN", "api_key: " + fake_jwt(5)),
        ("master_key: os.environ/LITELLM_MASTER_KEY", "master_key: sk-abcdef1234567890"),
    ],
)
def test_a_configuration_with_a_credential_value_is_refused(change: str, problem: str) -> None:
    text = render_config(GatewaySettings()).replace(change, problem, 1)
    assert any("credential" in item for item in validate_config_text(text))


def test_a_configuration_using_openai_prefix_is_refused() -> None:
    text = render_config(GatewaySettings()).replace("model: hosted_vllm/", "model: openai/", 1)
    assert any("hosted_vllm" in item for item in validate_config_text(text))


@pytest.mark.parametrize(
    "changes",
    [
        {"port": 80},
        {"upstream": "http://chatrs.example/api"},
        {"models": (GatewayModel("a", "a"), GatewayModel("a", "b")), "default_model": "a"},
        {"default_model": "not-listed"},
        {"models": (GatewayModel("bad name", "x"),), "default_model": "bad name"},
    ],
)
def test_settings_refuse_what_the_gateway_cannot_run(changes: dict[str, Any]) -> None:
    with pytest.raises(GatewayConfigError):
        GatewaySettings(**changes)


def test_settings_round_trip_and_a_loopback_test_upstream_is_allowed() -> None:
    settings = GatewaySettings(port=4123, upstream="http://127.0.0.1:9999/api")
    assert GatewaySettings.from_json(settings.to_json()) == settings


def test_init_keeps_the_persons_files_and_force_renders_again(tmp_path: Path) -> None:
    paths = GatewayPaths(tmp_path / "gw")
    written = init_home(paths)
    assert written == [paths.settings, paths.config]
    paths.config.write_text(paths.config.read_text() + "# mine\n", encoding="utf-8")
    custom = GatewaySettings(port=4555).to_json()
    paths.settings.write_text(json.dumps(custom), encoding="utf-8")
    assert init_home(paths) == []
    assert paths.config.read_text().endswith("# mine\n")
    assert init_home(paths, force=True) == [paths.config]
    assert "# mine" not in paths.config.read_text()
    assert load_settings(paths).port == 4555


def test_the_home_is_in_the_users_profile_unless_named() -> None:
    assert default_home({"AEP_GATEWAY_HOME": "D:/gw"}) == Path("D:/gw")
    home = default_home({"LOCALAPPDATA": "C:/Users/x/AppData/Local"})
    assert "gateway" in home.parts


# --- the token file --------------------------------------------------------------


def test_setting_a_value_keeps_other_lines_and_a_backup(tmp_path: Path) -> None:
    path = tmp_path / "gateway.env"
    path.write_text("# comment\nOTHER=1\nCHATRS_TOKEN=old\n", encoding="utf-8")
    secrets_file.set_value(path, "CHATRS_TOKEN", "new")
    assert secrets_file.read(path) == {"OTHER": "1", "CHATRS_TOKEN": "new"}
    assert "# comment" in path.read_text()
    assert "CHATRS_TOKEN=old" in (tmp_path / "gateway.env.bak").read_text()
    with pytest.raises(ValueError):
        secrets_file.set_value(path, "CHATRS_TOKEN", "two\nlines")


def test_token_info_reports_expiry_never_the_value() -> None:
    token = fake_jwt(3)
    info = secrets_file.token_info(token)
    shown = json.dumps(info.to_json())
    assert info.readable and not info.expired()
    assert token not in shown and "signature" not in shown
    assert secrets_file.token_info(fake_jwt(-1)).expired()
    assert secrets_file.token_info("not-a-jwt").to_json()["readable"] is False
    assert secrets_file.token_info(None).present is False


def test_the_local_key_is_generated_once_and_never_changed(tmp_path: Path) -> None:
    path = tmp_path / "gateway.env"
    key, made = secrets_file.ensure_master_key(path, {})
    assert made and key.startswith(secrets_file.MASTER_KEY_PREFIX)
    again, made_again = secrets_file.ensure_master_key(path, {})
    assert (again, made_again) == (key, False)
    # The environment's key is what AEP's credential mapping reads; it wins.
    assert secrets_file.ensure_master_key(path, {"LITELLM_MASTER_KEY": "from-env"}) == (
        "from-env",
        False,
    )


def test_loading_the_token_file_reports_what_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "gateway.env"
    path.write_text(f"LITELLM_MASTER_KEY={LOCAL_KEY}\n", encoding="utf-8")
    environ: dict[str, str] = {}
    assert secrets_file.load_into(environ, path) == ["CHATRS_TOKEN"]
    token = fake_jwt(5)
    secrets_file.set_value(path, "CHATRS_TOKEN", token)
    environ = {}
    assert secrets_file.load_into(environ, path) == []
    assert environ == {"CHATRS_TOKEN": token, "LITELLM_MASTER_KEY": LOCAL_KEY}


# --- the launcher ----------------------------------------------------------------


def prepare(paths: GatewayPaths, environ: dict[str, str]) -> tuple[Any, list[str]]:
    said: list[str] = []
    return launcher.prepare(paths, None, environ, said.append), said


def test_the_launcher_starts_on_loopback_offline_with_the_tokens_in_its_own_process(
    tmp_path: Path,
) -> None:
    paths = home_with(tmp_path, port=free_port(), token=fake_jwt(10))
    environ: dict[str, str] = {"LITELLM_LOCAL_MODEL_COST_MAP": "False"}
    prepared, said = prepare(paths, environ)
    assert not isinstance(prepared, int), said
    port, arguments = prepared
    assert arguments[arguments.index("--host") + 1] == LOOPBACK
    assert arguments[arguments.index("--port") + 1] == str(port)
    assert environ["LITELLM_MASTER_KEY"] == LOCAL_KEY
    # Offline by default; a value the person set is kept.
    assert environ["LITELLM_LOCAL_ANTHROPIC_BETA_HEADERS"] == "True"
    assert environ["LITELLM_LOCAL_MODEL_COST_MAP"] == "False"
    assert set(launcher.OFFLINE_ENVIRONMENT) <= set(environ)


@pytest.mark.parametrize(
    ("token", "expected"),
    [(None, "missing CHATRS_TOKEN"), (fake_jwt(-2), "expired")],
)
def test_the_launcher_will_not_start_without_a_valid_token(
    tmp_path: Path, token: str | None, expected: str
) -> None:
    paths = home_with(tmp_path, port=free_port(), token=token)
    prepared, said = prepare(paths, {})
    assert prepared == launcher.EXIT_NOT_READY
    assert expected in said[0]


def test_the_launcher_will_not_start_with_a_secret_in_the_configuration(tmp_path: Path) -> None:
    paths = home_with(tmp_path, port=free_port(), token=fake_jwt(10))
    text = paths.config.read_text().replace("os.environ/CHATRS_TOKEN", fake_jwt(10), 1)
    paths.config.write_text(text, encoding="utf-8")
    prepared, said = prepare(paths, {})
    assert prepared == launcher.EXIT_NOT_READY and "credential" in said[0]


def test_the_launcher_exits_quietly_when_the_port_is_already_served(tmp_path: Path) -> None:
    with socket.socket() as listener:
        listener.bind((LOOPBACK, 0))
        listener.listen()
        paths = home_with(tmp_path, port=listener.getsockname()[1], token=fake_jwt(10))
        prepared, said = prepare(paths, {})
    assert prepared == launcher.EXIT_ALREADY_SERVED
    assert "already served" in said[0]


def test_the_launcher_without_litellm_stops_before_starting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = home_with(tmp_path, port=free_port(), token=fake_jwt(10))
    monkeypatch.setattr(launcher, "litellm_version", lambda: None)
    monkeypatch.setattr(os, "environ", {})
    assert launcher.main(["--home", str(paths.home)]) == launcher.EXIT_NOT_READY


def test_the_launcher_refuses_to_run_when_the_patch_no_longer_applies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = home_with(tmp_path, port=free_port(), token=fake_jwt(10))
    monkeypatch.setattr(launcher, "litellm_version", lambda: "9.9.9")
    monkeypatch.setattr(os, "environ", {})

    def moved(module: ModuleType | None = None) -> type[Any]:
        raise patch.GatewayPatchError("moved")

    monkeypatch.setattr(patch, "apply", moved)
    assert launcher.main(["--home", str(paths.home)]) == launcher.EXIT_PATCH


# --- status, start, stop ---------------------------------------------------------


def test_status_tells_serving_starting_and_stopped_apart(tmp_path: Path) -> None:
    paths = home_with(tmp_path, token=fake_jwt(10))
    gateway_state.update(paths.state, pid=4242)
    serving = control.status(paths, {}, probe=lambda port: True, alive=lambda pid: True)
    starting = control.status(paths, {}, probe=lambda port: False, alive=lambda pid: True)
    stopped = control.status(paths, {}, probe=lambda port: False, alive=lambda pid: False)
    external = control.status(paths, {}, probe=lambda port: True, alive=lambda pid: False)
    assert (serving.state, serving.ours) == ("serving", True)
    assert (starting.state, starting.pid) == ("starting", 4242)
    assert (stopped.state, stopped.pid) == ("stopped", None)
    assert (external.state, external.ours) == ("serving", False)
    shown = json.dumps(serving.to_json())
    assert LOCAL_KEY not in shown and "signature" not in shown
    assert serving.to_json()["address"] == f"http://127.0.0.1:{DEFAULT_PORT}/v1"
    assert serving.key_present and serving.to_json()["config_ok"]


def test_start_spawns_the_launcher_and_remembers_its_process(tmp_path: Path) -> None:
    paths = home_with(tmp_path, token=fake_jwt(10))
    spawned: list[Sequence[str]] = []

    def spawner(command: Sequence[str], log: Path, environ: Mapping[str, str]) -> int:
        spawned.append(command)
        assert log == paths.log
        return 777

    result = control.start(
        paths, {}, probe=lambda port: False, alive=lambda pid: pid == 777, spawner=spawner
    )
    assert spawned and spawned[0][1:4] == ["-m", "llm_gateway.launcher", "--home"]
    assert result.state == "starting" and result.pid == 777
    # A second start while it is starting does not spawn another.
    control.start(paths, {}, probe=lambda port: False, alive=lambda pid: True, spawner=spawner)
    assert len(spawned) == 1


def test_start_refuses_a_broken_configuration(tmp_path: Path) -> None:
    paths = home_with(tmp_path, token=fake_jwt(10))
    paths.config.write_text("model_list:\n", encoding="utf-8")
    with pytest.raises(control.GatewayControlError):
        control.start(paths, {}, probe=lambda port: False, alive=lambda pid: False)


def test_stop_leaves_a_gateway_aep_did_not_start(tmp_path: Path) -> None:
    paths = home_with(tmp_path, token=fake_jwt(10))
    killed: list[int] = []
    with pytest.raises(control.GatewayControlError, match="did not start"):
        control.stop(paths, probe=lambda port: True, alive=lambda pid: False, killer=killed.append)
    gateway_state.update(paths.state, pid=99)
    control.stop(paths, probe=lambda port: False, alive=lambda pid: pid == 99, killer=killed.append)
    assert killed == [99]
    assert "pid" not in gateway_state.read(paths.state)


# --- test against a fake gateway -------------------------------------------------


class FakeGateway(BaseHTTPRequestHandler):
    answer_status = 200

    def log_message(self, *args: object) -> None:
        return

    def _reply(self, status: int, body: object) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.headers.get("Authorization") != f"Bearer {LOCAL_KEY}":
            self._reply(401, {"error": {"message": "Authentication Error"}})
            return
        self._reply(200, {"data": [{"id": "gpt-5.5"}, {"id": "gpt-5.4"}]})

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.answer_status != 200:
            self._reply(self.answer_status, {"error": {"message": "upstream said no"}})
            return
        self._reply(
            200, {"choices": [{"message": {"role": "assistant", "content": "OK " + body["model"]}}]}
        )


@pytest.fixture
def fake_gateway() -> Iterator[tuple[int, type[FakeGateway]]]:
    handler = type("Handler", (FakeGateway,), {"answer_status": 200})
    server = ThreadingHTTPServer((LOOPBACK, 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield int(server.server_address[1]), handler
    finally:
        server.shutdown()
        server.server_close()


def test_test_lists_models_and_asks_each_one(
    tmp_path: Path, fake_gateway: tuple[int, type[FakeGateway]]
) -> None:
    port, _handler = fake_gateway
    paths = home_with(tmp_path, port=port, token=fake_jwt(10))
    results = control.test(paths, {}, models=["gpt-5.5", "gpt-5.4"])
    assert [(r.model, r.ok) for r in results] == [
        ("(models)", True),
        ("gpt-5.5", True),
        ("gpt-5.4", True),
    ]
    assert results[1].detail == "OK gpt-5.5"
    recorded = json.dumps(gateway_state.read(paths.state))
    assert '"ok": true' in recorded and LOCAL_KEY not in recorded
    assert control.health(port) is False  # the fake has no liveness route


def test_test_names_a_wrong_key_and_an_upstream_error(
    tmp_path: Path, fake_gateway: tuple[int, type[FakeGateway]]
) -> None:
    port, handler = fake_gateway
    paths = home_with(tmp_path, port=port, token=fake_jwt(10), key="wrong")
    assert control.test(paths, {})[0].code == "unauthorized"
    paths = home_with(tmp_path, port=port, token=fake_jwt(10))
    handler.answer_status = 405
    checked = control.test(paths, {})
    assert checked[-1].code == "responses_api" and not checked[-1].ok


def test_test_says_not_running_when_nothing_listens(tmp_path: Path) -> None:
    paths = home_with(tmp_path, port=free_port(), token=fake_jwt(10))
    assert control.test(paths, {})[0].code == "not_running"


# --- autostart -------------------------------------------------------------------


class FakeRunKey(control.RunKey):
    def __init__(self) -> None:
        self.value: str | None = None

    def get(self) -> str | None:
        return self.value

    def set(self, command: str) -> None:
        self.value = command

    def delete(self) -> None:
        self.value = None


def runner_returning(code: int, calls: list[Sequence[str]]) -> control.CommandRunner:
    def run(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(arguments))
        return subprocess.CompletedProcess(list(arguments), code, "", "")

    return run


def test_autostart_registers_a_current_user_logon_task(tmp_path: Path) -> None:
    paths = home_with(tmp_path, token=fake_jwt(10))
    calls: list[Sequence[str]] = []
    keys = FakeRunKey()
    outcome = control.set_autostart(
        paths, True, {}, runner=runner_returning(0, calls), run_key=keys
    )
    assert outcome == {"on": True, "task": True, "run_key": False}
    script = calls[0][-1]
    assert "-AtLogOn -User $user" in script and "-RunLevel Limited" in script
    assert "Highest" not in script and control.TASK_NAME in script
    assert "llm_gateway.launcher" in script and "--refresh-if-due" in script


def test_autostart_falls_back_to_the_users_run_key_and_off_removes_both(tmp_path: Path) -> None:
    paths = home_with(tmp_path, token=fake_jwt(10))
    calls: list[Sequence[str]] = []
    keys = FakeRunKey()
    outcome = control.set_autostart(
        paths, True, {}, runner=runner_returning(1, calls), run_key=keys
    )
    assert outcome["run_key"] is True and keys.value and "llm_gateway.launcher" in keys.value
    control.set_autostart(paths, False, {}, runner=runner_returning(0, calls), run_key=keys)
    assert keys.value is None
    assert calls[-1][:3] == ["schtasks", "/Delete", "/TN"]


# --- token refresh ---------------------------------------------------------------


def script_runner(code: int, stdout: str = "") -> token_refresh.Runner:
    def run(arguments: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
        assert arguments[0] == "powershell.exe" and "-EncodedCommand" in arguments
        return subprocess.CompletedProcess(list(arguments), code, stdout, "")

    return run


def test_refresh_is_skipped_while_the_token_is_far_from_expiry(tmp_path: Path) -> None:
    paths = home_with(tmp_path, token=fake_jwt(20))
    result = token_refresh.refresh(paths, GatewaySettings(), runner=script_runner(99))
    assert (result.ok, result.code) == (True, "not_due")


def test_refresh_writes_a_new_valid_token_with_a_backup(tmp_path: Path) -> None:
    old, new = fake_jwt(2), fake_jwt(28)
    paths = home_with(tmp_path, token=old)
    result = token_refresh.refresh(
        paths, GatewaySettings(), runner=script_runner(0, f"AEP-TOKEN:{new}\n"), platform="win32"
    )
    assert (result.ok, result.code) == (True, "renewed")
    assert secrets_file.read(paths.secrets)["CHATRS_TOKEN"] == new
    assert secrets_file.read(paths.secrets)["LITELLM_MASTER_KEY"] == LOCAL_KEY
    assert old in (paths.home / "gateway.env.bak").read_text()
    recorded = gateway_state.read(paths.state)
    assert "last_refresh_at" in recorded and new not in json.dumps(recorded)
    assert new not in json.dumps(result.to_json())


@pytest.mark.parametrize(
    ("code", "stdout", "expected"),
    [
        (token_refresh.EXIT_NO_TICKET, "", "no_kerberos_ticket"),
        (token_refresh.EXIT_REJECTED, "", "kerberos_rejected"),
        (0, "AEP-TOKEN:garbage\n", "unreadable_token"),
        (0, f"AEP-TOKEN:{fake_jwt(-1)}\n", "expired_token"),
    ],
)
def test_refresh_failures_are_named_and_never_write(
    tmp_path: Path, code: int, stdout: str, expected: str
) -> None:
    old = fake_jwt(1)
    paths = home_with(tmp_path, token=old)
    result = token_refresh.refresh(
        paths, GatewaySettings(), runner=script_runner(code, stdout), platform="win32"
    )
    assert (result.ok, result.code) == (False, expected)
    assert secrets_file.read(paths.secrets)["CHATRS_TOKEN"] == old
    assert gateway_state.read(paths.state)["last_refresh_error"] == expected


def test_refresh_outside_windows_says_so(tmp_path: Path) -> None:
    paths = home_with(tmp_path, token=None)
    result = token_refresh.refresh(paths, GatewaySettings(), platform="linux")
    assert result.code == "not_windows"


def test_the_refresh_script_signs_in_to_the_upstreams_site() -> None:
    command = token_refresh.script_command("https://chatrs.example.net")
    decoded = base64.b64decode(command[-1]).decode("utf-16-le")
    assert "-Base 'https://chatrs.example.net'" in decoded
    assert "UseDefaultCredentials = $true" in decoded
    assert "AllowAutoRedirect = $false" in decoded
    assert token_refresh.service_of(GatewaySettings()) == "https://chatrs.cloud.rsint.net"


# --- the command line ------------------------------------------------------------


def test_cli_init_status_and_test_print_no_values(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    fake_gateway: tuple[int, type[FakeGateway]],
) -> None:
    port, _handler = fake_gateway
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    monkeypatch.delenv("CHATRS_TOKEN", raising=False)
    home = tmp_path / "gw"
    assert cli.main(["--home", str(home), "init"]) == 0
    key = secrets_file.read(home / "gateway.env")["LITELLM_MASTER_KEY"]
    settings = json.loads((home / "gateway.json").read_text())
    settings["port"] = port
    (home / "gateway.json").write_text(json.dumps(settings), encoding="utf-8")
    secrets_file.set_value(home / "gateway.env", "LITELLM_MASTER_KEY", LOCAL_KEY)
    secrets_file.set_value(home / "gateway.env", "CHATRS_TOKEN", fake_jwt(9))
    monkeypatch.setattr(control, "autostart_query", lambda: {"on": False})
    assert cli.main(["--home", str(home), "status", "--json"]) == 0
    assert cli.main(["--home", str(home), "status"]) == 0
    assert cli.main(["--home", str(home), "test"]) == 0
    output = capsys.readouterr().out
    assert key not in output and LOCAL_KEY not in output and "signature" not in output
    assert '"state": "stopped"' in output
    assert "token: expires" in output and "ok   gpt-5.5" in output


# --- what ships ------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[1]


def test_the_dependency_lock_pins_the_verified_litellm_without_its_enterprise_package() -> None:
    from llm_gateway import PINNED_LITELLM_VERSION

    lines = [
        line.strip()
        for line in (REPO / "deploy/windows-preview/gateway/requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert f"litellm=={PINNED_LITELLM_VERSION}" in lines
    assert all("==" in line for line in lines), "every dependency is pinned exactly"
    assert not [line for line in lines if line.lower().startswith("litellm-enterprise")]
    assert not [line for line in lines if "[" in line], "no extras: litellm[proxy] pulls it in"


def test_nothing_the_gateway_ships_holds_a_credential() -> None:
    shipped = sorted((REPO / "src/llm_gateway").glob("*.py"))
    shipped += sorted((REPO / "deploy/windows-preview/gateway").glob("*"))
    shipped.append(REPO / "docs/phases/LLM_GATEWAY.md")
    for path in shipped:
        assert find_secret_values(path.read_text(encoding="utf-8")) == [], path
