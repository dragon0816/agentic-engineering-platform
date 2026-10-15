"""Settings model picker: list what the saved Gateway serves, never a secret."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from test_host_models import GATEWAY, binding, endpoint
from test_host_wiring import ready

from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb
from host_runtime.web_page import PAGE


class _Reply:
    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self.headers: Mapping[str, str] = {}
        self._body = json.dumps(payload).encode()

    def chunks(self) -> Iterator[bytes]:
        yield self._body

    def close(self) -> None:
        pass


class _Lister:
    def __init__(self, status: int, payload: Any) -> None:
        self.reply = _Reply(status, payload)
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def request(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout_s: float,
    ) -> _Reply:
        self.calls.append((method, url, dict(headers)))
        return self.reply


def _web(tmp_path: Path, **endpoint_changes: Any) -> Any:
    config, layout = ready(
        tmp_path,
        config_changes={
            "models": binding(
                catalog={
                    "endpoints": [endpoint(**endpoint_changes)],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            ),
            "credentials": [
                {"secret": "llm_gateway_token", "environment_variable": "AEP_LLM_TOKEN"}
            ],
        },
    )
    return build_runtime(config, layout=layout)


def test_lists_openai_compatible_models_with_the_environment_credential(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    with _web(tmp_path) as runtime:
        web = AgentWeb(runtime)
        variable = runtime.config.credential_environment()["llm_gateway_token"]
        monkeypatch.setenv(variable, "sk-test-value")
        lister = _Lister(200, {"data": [{"id": "gpt-5.5"}, {"id": "claude-opus"}, {"x": 1}]})
        web.model_listing_transport = lister
        listed = web.available_models()
        assert listed == {"ok": True, "models": ["claude-opus", "gpt-5.5"], "current": "gpt-5.5"}
        method, url, headers = lister.calls[0]
        assert (method, url) == ("GET", GATEWAY.rstrip("/") + "/models")
        assert headers["Authorization"] == "Bearer sk-test-value"
        assert "sk-test-value" not in json.dumps(listed)


def test_missing_credential_or_gateway_error_is_a_code_not_a_crash(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    with _web(tmp_path) as runtime:
        web = AgentWeb(runtime)
        variable = runtime.config.credential_environment()["llm_gateway_token"]
        monkeypatch.delenv(variable, raising=False)
        web.model_listing_transport = _Lister(200, {"data": []})
        assert web.available_models()["code"] == "credential_unavailable"
        monkeypatch.setenv(variable, "sk-test-value")
        web.model_listing_transport = _Lister(401, {"error": "denied"})
        assert web.available_models() == {"ok": False, "code": "gateway_http_401", "models": []}


def test_ollama_lists_its_tags_without_a_credential(tmp_path: Path) -> None:
    with _web(
        tmp_path,
        provider="ollama",
        credential=None,
        base_url="http://127.0.0.1:11434/v1",
    ) as runtime:
        web = AgentWeb(runtime)
        lister = _Lister(200, {"models": [{"name": "qwen3:8b"}, {"name": "llama3.1"}]})
        web.model_listing_transport = lister
        assert web.available_models()["models"] == ["llama3.1", "qwen3:8b"]
        assert lister.calls[0][1] == "http://127.0.0.1:11434/api/tags"
        assert "Authorization" not in lister.calls[0][2]


def test_settings_page_offers_the_gateway_model_picker() -> None:
    for expected in (
        'id="model-choices"',
        'id="model-choices-load"',
        'call("/api/settings/models")',
        'el("model-name").value = chosen',
    ):
        assert expected in PAGE, expected
