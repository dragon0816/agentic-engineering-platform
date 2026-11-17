"""Native requests share receipts across authenticated MCP entry points."""

import json

import pytest
from test_agent_web import served as served
from test_assistant_tools import _rpc
from test_chat_authoring import Echo, Out, Recorder, spec

from common.assets import ExecutionDependencies
from host_runtime.web import AgentWebServer


def test_native_assistant_and_authoring_share_receipts_and_token_lifetime(
    served: AgentWebServer,
) -> None:
    web = served.web
    recorder = Recorder()
    web.runtime.agent.gateway.bridge.installed.register(
        spec("native-fixture", "write"),
        recorder,
        Echo,
        Out,
        ExecutionDependencies(central_required=False),
    )
    session = "native-fixture-session"
    run = web.agent_mode.begin(session, "claude_code")
    call = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "aep_tools_invoke",
            "arguments": {
                "target": "lab/native-fixture@1.0.0",
                "arguments": {"value": "fixture"},
            },
        },
    }
    try:
        first = web.authoring_mcp(call, (session, "claude-code"))
        assert first and first["result"]["structuredContent"]["ok"]
        second = _rpc(served, run.token, call)
        assert second.status == 200
        data = json.loads(second.body)["result"]["structuredContent"]
        assert data["ok"] and data["replayed"]
        assert data["handler_invoked"] is False
        assert recorder.calls == ["fixture"]
    finally:
        web.agent_mode.finish(run, "answered")
    assert _rpc(served, run.token, call).status == 401


@pytest.mark.parametrize("entrypoint", ["assistant", "agent_mode", "unscoped"])
def test_public_native_generic_execution_returns_status_without_new_raw_data(
    served: AgentWebServer,
    entrypoint: str,
) -> None:
    from common.base import Contract
    from common.execution import RequestContext

    private = "CONFIDENTIAL-NATIVE-FIXTURE-ONLY"
    calls = []

    async def read(context: RequestContext, inputs: Contract) -> Contract:
        calls.append(1)
        return Out(echoed=private)

    web = served.web
    web.runtime.agent.gateway.bridge.installed.register(
        spec("native-read-fixture", "read"),
        read,
        Echo,
        Out,
        ExecutionDependencies(central_required=False),
    )
    run = web.agent_mode.begin("public-native-fixture", "codex")
    call = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "aep_tools_invoke",
            "arguments": {
                "target": "lab/native-read-fixture@1.0.0",
                "arguments": {"value": "public lookup"},
            },
        },
    }
    try:
        if entrypoint == "agent_mode":
            body = web.agent_mode.call(
                run,
                "aep_tools_invoke",
                {
                    "target": "lab/native-read-fixture@1.0.0",
                    "arguments": {"value": "public lookup"},
                },
            )
        elif entrypoint == "unscoped":
            response = web.assistant_mcp(call)
            assert response is not None
            body = response["result"]["structuredContent"]
        else:
            answer = _rpc(served, run.token, call)
            assert answer.status == 200
            body = json.loads(answer.body)["result"]["structuredContent"]
        assert private not in json.dumps(body)
        assert body["ok"] and body["handler_invoked"] is True
        assert body["data_route"]["result_data_withheld"] is True
        assert body["data_route"]["backend"] == ("unknown" if entrypoint == "unscoped" else "codex")
        assert calls == [1]
    finally:
        web.agent_mode.finish(run, "answered")
