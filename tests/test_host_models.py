"""Giving a company host a model, and what it refuses on the way.

The owner's team runs a LiteLLM gateway in front of the company's internal
LLM (2026-09-24). LiteLLM serves an OpenAI-shaped API, which is what
`models.openai_compatible` already speaks, so the work here is wiring and
the tests are about what the wiring will not do quietly.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_host_wiring import device, host_json, ready

from agent.routing import RequestRouter
from host_runtime.cli import main
from host_runtime.contracts import CompanyHostConfiguration, ModelBinding
from host_runtime.host import HostError, build_router, build_runtime, host_report
from models.wire import Transport

GATEWAY = "https://gateway.example.invalid/api"


def endpoint(**changes: Any) -> dict[str, Any]:
    """The company's own gateway, as a host would describe it: it runs inside
    the company, not on this machine, so it is not `local`."""
    return {
        "alias": "company",
        "provider": "openai_compatible",
        "model": "gpt-5.5",
        "base_url": GATEWAY,
        "credential": {"name": "llm_gateway_token"},
        "capabilities": {
            "reasoning": "high",
            "tool_calling": True,
            "structured_output": True,
            "streaming": True,
            "max_context_tokens": 128_000,
            **changes.pop("capabilities", {}),
        },
        **changes,
    }


def binding(**changes: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "catalog": {"endpoints": [endpoint()], "routes": [{"name": "default", "alias": "company"}]},
        "routing_alias": "company",
    }
    values.update(changes)
    return values


def configured(tmp_path: Path, **changes: Any) -> tuple[Any, Any]:
    return ready(
        tmp_path,
        config_changes={
            "models": binding(**changes),
            "credentials": [
                {"secret": "llm_gateway_token", "environment_variable": "AEP_LLM_TOKEN"}
            ],
        },
    )


def test_a_host_with_no_model_is_the_host_everyone_already_had(tmp_path: Path) -> None:
    """Not a degraded mode. A machine that guesses which of the team's
    workflows an ambiguous sentence meant, and runs it, is worse than one
    that asks."""
    config, _layout = ready(tmp_path)
    assert config.models is None
    with build_runtime(config) as runtime:
        assert isinstance(runtime.agent.gateway.router, RequestRouter)
        assert runtime.agent.gateway.router.model is None


def test_a_configured_gateway_reaches_the_router(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AEP_LLM_TOKEN", "a value nobody prints")
    config, layout = configured(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        router = runtime.agent.gateway.router
        assert isinstance(router, RequestRouter)
        assert router.model is not None, "the host was given a gateway and did not use it"
        assert router.model_alias == "company"
        assert router.local_only is False, "nothing asked for a model on this machine"


def test_naming_a_gateway_is_the_whole_decision(tmp_path: Path) -> None:
    """No second line to write. Somebody put that URL in the file and mapped
    a credential to go with it; asking again would add a line to every host
    and no information to any of them."""
    config = CompanyHostConfiguration.model_validate(
        {
            "device": device(),
            "workspace_root": str(Path(__file__).resolve().parents[1]),
            "models": binding(),
        }
    )
    assert config.models is not None
    assert config.models.require_local_model is False
    assert config.models.routing_alias == "company"


def _ollama(**changes: Any) -> dict[str, Any]:
    return {
        "catalog": {
            "endpoints": [
                {
                    "alias": "local",
                    "provider": "ollama",
                    "model": "qwen3:8b",
                    "base_url": "http://localhost:11434",
                    "capabilities": {"local": True, "max_context_tokens": 32_000},
                }
            ]
        },
        "routing_alias": "local",
        **changes,
    }


def test_a_machine_with_the_memory_to_run_one_can_insist_on_it(tmp_path: Path) -> None:
    """The path left open for a workstation powerful enough to load a model
    into its own memory, and for one that has to keep working with nothing
    reachable."""
    here = ModelBinding.model_validate(_ollama(require_local_model=True))
    assert here.require_local_model is True
    assert here.routing_alias == "local"


def test_insisting_on_a_local_model_and_naming_a_gateway_is_refused(tmp_path: Path) -> None:
    """Two things that cannot both be true, refused where they were written
    rather than at the first message, where it would read as the model
    declining to answer."""
    with pytest.raises(ValidationError, match="require_local_model is set"):
        ModelBinding.model_validate(binding(require_local_model=True))


def test_a_catalog_with_no_routing_alias_still_answers_needs_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Configuring models for capabilities to use, without letting one choose
    what to run, is a reasonable thing to want."""
    monkeypatch.setenv("AEP_LLM_TOKEN", "a value nobody prints")
    config, layout = configured(tmp_path, routing_alias=None)
    with build_runtime(config, layout=layout) as runtime:
        router = runtime.agent.gateway.router
        assert isinstance(router, RequestRouter)
        assert router.model is None


def test_a_routing_alias_that_names_nothing_is_refused_where_it_is_written() -> None:
    with pytest.raises(Exception, match="routing_alias names an endpoint"):
        ModelBinding.model_validate(binding(routing_alias="not-an-endpoint"))


def test_an_unmapped_secret_stops_the_host_rather_than_the_first_message(
    tmp_path: Path,
) -> None:
    """The same refusal the board token gets. A host assembled without its
    credential would fail at whatever somebody typed first, which names the
    wrong thing."""
    config, layout = ready(tmp_path, config_changes={"models": binding(), "credentials": []})
    with pytest.raises(HostError, match="credential_unmapped"):
        build_runtime(config, layout=layout)


def test_a_provider_this_build_cannot_speak_is_refused_at_assembly(tmp_path: Path) -> None:
    """Not at the first message. `unknown_alias` cannot happen here because
    the contract checked it, so this is the other one."""
    config, _layout = ready(tmp_path)
    changed = config.model_copy(
        update={
            "models": ModelBinding.model_validate(
                binding(
                    catalog={
                        "endpoints": [endpoint(provider="something_nobody_wrote", credential=None)]
                    }
                )
            )
        }
    )
    from agent.routing import CommandRouter
    from agent.skills import SkillRegistry

    with pytest.raises(HostError, match="models_invalid"):
        build_router(changed, CommandRouter(SkillRegistry()))


def test_the_doctor_says_what_this_machine_can_reason_with(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without contacting anything: a doctor that made a chargeable request
    to answer a question about configuration is a doctor nobody runs."""
    monkeypatch.delenv("AEP_LLM_TOKEN", raising=False)
    plain, layout = ready(tmp_path)
    checks = {check.name: check for check in host_report(plain, layout).checks}
    assert checks["models"].status == "pending"
    assert "does not reason" in checks["models"].detail

    config, layout = configured(tmp_path)
    checks = {check.name: check for check in host_report(config, layout).checks}
    assert checks["models"].status == "failed"
    assert "AEP_LLM_TOKEN, which is not set" in checks["models"].detail

    monkeypatch.setenv("AEP_LLM_TOKEN", "a value nobody prints")
    checks = {check.name: check for check in host_report(config, layout).checks}
    assert checks["models"].status == "passed"
    assert "routing through company" in checks["models"].detail
    assert "on this machine only" not in checks["models"].detail

    insisting = config.model_copy(
        update={"models": ModelBinding.model_validate(_ollama(require_local_model=True))}
    )
    checks = {check.name: check for check in host_report(insisting, layout).checks}
    assert "a model on this machine only" in checks["models"].detail


def test_the_doctor_never_prints_the_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AEP_LLM_TOKEN", "sk-a-real-looking-secret")
    config, layout = configured(tmp_path)
    where = str(host_json(tmp_path, config))
    main(["doctor", "--config", where])
    printed = capsys.readouterr().out
    assert "sk-a-real-looking-secret" not in printed
    assert "routing through company" in printed
    # And when it is missing, the variable is named so the reader can fix it.
    # The variable is a name, not a value; the value is never printed either
    # way, which is the point.
    monkeypatch.delenv("AEP_LLM_TOKEN")
    main(["doctor", "--config", where])
    missing = capsys.readouterr().out
    assert "AEP_LLM_TOKEN" in missing
    assert "sk-a-real-looking-secret" not in missing


def test_the_configuration_file_may_not_carry_the_key_itself(tmp_path: Path) -> None:
    """A gateway key pasted into host.json is the mistake this refuses. The
    endpoint names its secret; the value lives in an environment variable."""
    written = json.dumps(binding())
    assert "sk-" not in written
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ModelBinding.model_validate(
            binding(
                catalog={
                    "endpoints": [
                        endpoint(credential={"name": "x", "value": "sk-pasted-in-by-hand"})
                    ]
                }
            )
        )


class GatewayReply:
    """One answer, shaped the way a LiteLLM proxy shapes one."""

    def __init__(self, status: int, body: dict[str, Any]) -> None:
        self.status = status
        self._body = json.dumps(body).encode("utf-8")
        self.closed = False

    def chunks(self) -> Iterator[bytes]:
        yield self._body

    def close(self) -> None:
        self.closed = True


class FakeGateway:
    """A stand-in for the company's LiteLLM gateway. It records what was sent
    so the test can check what left the machine."""

    def __init__(self, chose: dict[str, Any] | None) -> None:
        self.chose = chose
        self.calls: list[dict[str, Any]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        self.calls.append({"url": url, "payload": json.loads(body), "headers": dict(headers)})
        return GatewayReply(
            200,
            {
                "id": "chatcmpl-1",
                "model": "gpt-5.5",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(self.chose)},
                    }
                ],
                # chatrs returns a non-standard field here; PHASE_5_MIGRATION
                # records that an adapter must tolerate it rather than fail.
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 20,
                    "latency_checkpoint": "something nobody asked for",
                },
            },
        )


def routed(tmp_path: Path, gateway: FakeGateway, message: str) -> Any:
    """Assemble a real host with the fake gateway behind it and ask it
    something no installed command matches."""
    import asyncio

    from common.execution import TraceIdentifiers
    from common.local_agent import LocalAgentRequest
    from host_runtime.agent import LocalAgent

    config, layout = configured(tmp_path)
    from host_runtime.host import build_gateway, load_authorization, load_membership
    from host_runtime.state import SqliteLocalState

    membership = load_membership(config, layout)
    built = build_gateway(
        config,
        layout,
        load_authorization(config, layout),
        model_transport=gateway,
    )
    state = SqliteLocalState(layout.state, bridge_id=config.device.bridge_id)
    try:
        agent = LocalAgent(membership, built, state)
        return asyncio.run(
            agent.handle(
                LocalAgentRequest(
                    ingress="local",
                    actor="engineer",
                    bridge_id=config.device.bridge_id,
                    namespace="engineering",
                    message=message,
                    trace=TraceIdentifiers(trace_id="t-1", request_id="r-1", span_id="s-1"),
                )
            )
        )
    finally:
        state.close()


def test_a_sentence_no_command_matches_is_routed_by_the_gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point of the wiring. Before it, this answered `needs_input`
    with `no_known_route` whatever was typed."""
    monkeypatch.setenv("AEP_LLM_TOKEN", "a value nobody prints")
    gateway = FakeGateway(
        {
            "kind": "workflow",
            "target": {
                "namespace": "engineering",
                "name": "read-local-file",
                "version": "1.0.0",
            },
            "arguments": {},
        }
    )
    outcome = routed(tmp_path, gateway, "please show me what is in my notes")
    assert gateway.calls, "the gateway was never asked"
    assert outcome.decision is not None
    assert outcome.decision.kind == "workflow"
    assert outcome.decision.target.name == "read-local-file"
    assert "Model selected" in outcome.decision.reason


def test_the_request_goes_to_the_configured_gateway_and_carries_its_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whose key, and to where, is what an owner asking "does our data leave"
    needs to be able to check."""
    monkeypatch.setenv("AEP_LLM_TOKEN", "sk-the-company-key")
    gateway = FakeGateway(None)
    routed(tmp_path, gateway, "anything at all")
    sent = gateway.calls[0]
    assert sent["url"].startswith(GATEWAY)
    assert sent["headers"]["Authorization"] == "Bearer sk-the-company-key"
    assert sent["payload"]["model"] == "gpt-5.5"


def test_a_gateway_that_chooses_nothing_leaves_the_agent_asking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model that will not choose is not a licence to guess."""
    monkeypatch.setenv("AEP_LLM_TOKEN", "a value nobody prints")
    outcome = routed(tmp_path, FakeGateway(None), "something meaningless")
    assert outcome.decision is not None
    assert outcome.decision.kind == "needs_input"


def test_a_gateway_naming_something_not_installed_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model proposes; the host disposes. A name it invented must not
    become a run."""
    monkeypatch.setenv("AEP_LLM_TOKEN", "a value nobody prints")
    gateway = FakeGateway(
        {
            "kind": "workflow",
            "target": {"namespace": "engineering", "name": "invented", "version": "9.9.9"},
            "arguments": {},
        }
    )
    outcome = routed(tmp_path, gateway, "run the thing")
    assert outcome.decision is not None
    assert outcome.decision.kind == "needs_input"
    assert outcome.decision.reason == "uninstalled_model_target"


def test_a_command_that_matches_never_reaches_the_gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deterministic routing still wins. A machine that asked a model what
    `files.read` meant would be slower, dearer and less certain."""
    monkeypatch.setenv("AEP_LLM_TOKEN", "a value nobody prints")
    gateway = FakeGateway(None)
    config, layout = configured(tmp_path)
    outcome = routed(tmp_path, gateway, f"files.read {layout.workspace_root / 'notes.txt'}")
    assert gateway.calls == [], "the gateway was asked about a command that matched"
    assert outcome.decision is not None and outcome.decision.kind == "workflow"


def test_the_host_never_opens_a_socket_while_being_assembled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Building a host reads files. A build that contacted the gateway would
    make `doctor` and every test depend on the company network."""

    from agent.routing import CommandRouter
    from agent.skills import SkillRegistry

    class Forbidden:
        """A transport that fails the test if anything sends through it."""

        def send(
            self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
        ) -> GatewayReply:
            raise AssertionError("assembling a host contacted the gateway")

    monkeypatch.setenv("AEP_LLM_TOKEN", "a value nobody prints")
    config, _layout = configured(tmp_path)
    transport: Transport = Forbidden()
    router = build_router(config, CommandRouter(SkillRegistry()), transport=transport)
    assert router.model is not None, "the client was built"
