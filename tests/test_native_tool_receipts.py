"""Native requests share receipts across authenticated MCP entry points."""

import json

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
        assert data["ok"] and data["data"]["replayed"]
        assert data["data"]["handler_invoked"] is False
        assert recorder.calls == ["fixture"]
    finally:
        web.agent_mode.finish(run, "answered")
    assert _rpc(served, run.token, call).status == 401
