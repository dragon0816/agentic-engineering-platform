"""Native adapters inherit IT tool settings and consume the common MCP inventory."""

from pathlib import Path

import pytest
from test_conversation_backends import Runner, history, installed, public_context

from host_runtime.conversation_backends import (
    SPECS,
    AgentLaunch,
    ConversationBackendName,
    LocalConversationBackends,
)


@pytest.mark.parametrize("backend", ["claude_code", "codex"])
def test_native_launch_keeps_it_configuration_and_uses_aep_mcp(
    tmp_path: Path, backend: ConversationBackendName
) -> None:
    runner = Runner('{"result":"fixture done"}')
    backends = LocalConversationBackends(tmp_path, which=installed, runner=runner)
    launch = AgentLaunch(
        folder=tmp_path,
        servers={"aep": ("http://127.0.0.1:1234/mcp/authoring", "fixture-token-not-a-secret")},
        on_permission=lambda _params: True,
    )
    result = backends.complete(
        backend,
        history(),
        persona_guidance="",
        outbound=public_context(history(), ""),
        agent=launch,
    )
    assert result.status == "answered" and result.text == "fixture done"
    argv, options = runner.calls[0]
    denied_flags = {
        "--restricted",
        "--safe-mode",
        "--tools",
        "--strict-mcp-config",
        "--permission-mode",
        "--settings",
        "--setting-sources",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
    }
    assert denied_flags.isdisjoint(argv)
    assert not any("bypass" in value or "skip-permissions" in value for value in argv)
    assert options["cwd"] == tmp_path
    if backend == "claude_code":
        assert "--mcp-config" in argv
    else:
        assert any("mcp_servers" in value for value in argv)
        assert "fixture-token-not-a-secret" not in str(argv)


def test_cli_specs_do_not_hide_builtin_or_it_installed_tools() -> None:
    for spec in SPECS:
        assert not any(
            arg.startswith(("--deny-tool", "--available-tools=")) for arg in spec.arguments
        )
        assert "--disable-builtin-mcps" not in spec.arguments
        assert "--ignore-user-config" not in spec.arguments
