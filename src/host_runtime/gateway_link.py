"""What Agent Web and Telegram know about the built-in LLM gateway
(docs/phases/LLM_GATEWAY.md): the Settings card's facts, and a plain answer
when a model turn failed because the gateway is down, still starting, or
rejecting the token.

A turn that fails on a model endpoint behind 127.0.0.1 used to say only
"The configured model could not answer this turn"; after a reboot the
gateway can take minutes to serve (2026-10-16), so the person needs to know
whether to wait, start it, or renew the token.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlparse

from common.execution import Failure
from host_runtime.contracts import CompanyHostConfiguration
from llm_gateway import control
from llm_gateway import state as gateway_state
from llm_gateway.config import GatewayPaths, default_home

#: Failures of a model call that the gateway's state can explain.
GATEWAY_FAILURE_CODES = frozenset(
    {"model_unreachable", "model_timeout", "model_error", "model_http_error", "model_unavailable"}
)
WHERE = "Settings > LLM gateway"


def default_paths() -> GatewayPaths:
    return GatewayPaths(default_home())


def model_base_url(config: CompanyHostConfiguration) -> str | None:
    binding = config.models
    if binding is None or binding.routing_alias is None:
        return None
    endpoint = binding.catalog.endpoint(binding.routing_alias)
    return None if endpoint is None else str(endpoint.base_url)


def gateway_port(config: CompanyHostConfiguration) -> int | None:
    """The loopback port the routing model is reached on, if it is one."""
    base = model_base_url(config)
    if base is None:
        return None
    parsed = urlparse(base)
    if parsed.hostname not in ("127.0.0.1", "localhost"):
        return None
    return parsed.port or 80


def explain_model_failure(
    config: CompanyHostConfiguration,
    failure: Failure | None,
    *,
    paths: GatewayPaths | None = None,
    probe: Callable[[int], bool] = control.health,
    alive: Callable[[int], bool] = control.process_alive,
    now: Callable[[], float] = time.time,
) -> str | None:
    """A plain explanation, or None when the gateway does not explain it."""
    if failure is None or failure.code not in GATEWAY_FAILURE_CODES:
        return None
    port = gateway_port(config)
    if port is None:
        return None
    if not probe(port):
        facts = gateway_state.read((paths or default_paths()).state)
        pid = facts.get("pid")
        started = facts.get("started_at")
        if isinstance(pid, int) and facts.get("port") in (None, port) and alive(pid):
            waited = ""
            if isinstance(started, str):
                try:
                    since = now() - datetime.fromisoformat(started).astimezone(UTC).timestamp()
                except ValueError:
                    since = -1
                if since >= 0:
                    waited = f" (started {int(since)} s ago)"
            return (
                f"The LLM gateway is still starting{waited}; a first start after a reboot "
                f"can take a few minutes. Ask again in a moment — {WHERE} shows when it "
                "is ready."
            )
        return (
            f"The LLM gateway is not running (127.0.0.1:{port}), so no model can answer. "
            f"Start it in {WHERE}, or run `aep-host gateway start`."
        )
    if failure.code == "model_http_error" and failure.message.startswith("401"):
        return (
            "The LLM gateway rejected the request (401): the company token has probably "
            f"expired, or the local key does not match. Renew the token in {WHERE} "
            "(needs the company domain sign-in), then restart the gateway."
        )
    if failure.code == "model_http_error" and failure.message.startswith("405"):
        return (
            "The LLM gateway answered 405: a model in its configuration uses openai/ "
            f"instead of hosted_vllm/ (the Responses API). See {WHERE}."
        )
    return None


def gateway_card(
    config: CompanyHostConfiguration,
    *,
    paths: GatewayPaths | None = None,
    probe: Callable[[int], bool] = control.health,
    alive: Callable[[int], bool] = control.process_alive,
    autostart_query: Callable[[], dict[str, object]] | None = None,
) -> dict[str, object]:
    """The card's facts: the gateway's status (never a token or key value),
    and whether the Natural-language model goes through it."""
    chosen = paths or default_paths()
    current = control.status(chosen, probe=probe, alive=alive, autostart_query=autostart_query)
    port = gateway_port(config)
    return {
        "ok": True,
        **current.to_json(),
        "model_base_url": model_base_url(config),
        "model_uses_gateway": port is not None and port == current.port,
        "installed": chosen.settings.is_file(),
    }
