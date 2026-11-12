"""Application tool scopes do not replace IT/OS/service execution permissions."""

import asyncio
from pathlib import Path

from test_agent_mail import FakeMailbox, _message
from test_agent_mode import _mode
from test_gateway import request

from capabilities.files import ReadFileHandler, ReadFileInput, ReadFileOutput
from capabilities.mail_read.handlers import MailSearchRequest
from integrations.outlook_mail import MAX_BODY_CHARS, MailScope, read, search


def test_old_folder_sender_and_date_limits_do_not_hide_it_accessible_mail() -> None:
    old = _message(1, folder="Sent Items", sender="excluded@example.test", days=500)
    reader = FakeMailbox([old])
    scope = MailScope(
        folders=("Inbox",),
        max_days=1,
        excluded_folders=("Sent Items",),
        excluded_senders=(old.sender,),
    )
    assert read(reader, scope, old.message_id).body == old.body
    found = search(reader, scope, folder="Sent Items", days=600, query="Status")
    assert [item.message_id for item in found] == [old.message_id]
    assert MailSearchRequest(days=600).days == 600
    assert search(reader, scope, folder="Sent Items", days=10) == []  # requested filter applies


def test_truncated_mail_is_explicit_and_can_be_read_in_continuation_chunks() -> None:
    text = "x" * (MAX_BODY_CHARS + 17)
    reader = FakeMailbox([_message(1, body=text)])
    first = read(reader, MailScope(), "m1")
    assert first.body_truncated and first.next_body_offset == MAX_BODY_CHARS
    rest = read(reader, MailScope(), "m1", body_offset=first.next_body_offset)
    assert not rest.body_truncated and rest.next_body_offset is None
    assert first.body + rest.body == text


def test_agent_mode_requires_no_tool_switch_or_application_permission_card(tmp_path: Path) -> None:
    mode, tasks = _mode(tmp_path)
    assert all(mode.enabled(backend) for backend in ("claude_code", "codex", "copilot"))
    run = mode.begin("session", "claude_code")
    try:
        result = mode.claude_permission(
            run, {"tool_name": "Bash", "input": {"command": "fixture-command"}}
        )
        assert result["behavior"] == "allow"
        assert mode.acp_permission(
            run, {"toolCall": {"kind": "execute", "title": "fixture-command"}}
        )
        assert mode.open_cards("session") == []
        assert not run.cards
    finally:
        mode.finish(run, "answered")


def test_generic_file_reader_has_no_application_folder_allowlist(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("IT accessible fixture", encoding="utf-8")
    handler = ReadFileHandler(workspace, restrict_root=False)
    result = asyncio.run(handler(request("read fixture"), ReadFileInput(path=str(outside))))
    assert isinstance(result, ReadFileOutput)
    assert result.outcome == "read" and result.content == "IT accessible fixture"


def test_declared_agent_execution_choices_are_not_hidden_by_confirm_metadata() -> None:
    from test_workflow_parameter_declaration import _manifest

    from common.workflow_forms import agent_tool_schema

    manifest = _manifest([{"name": "send", "label": "Send", "kind": "boolean", "confirm": True}])
    assert "send" in agent_tool_schema(manifest)["properties"]


def test_browser_repair_probe_executes_without_approval_and_never_verifies(tmp_path: Path) -> None:
    from test_authoring_browser_preflight import context, current, failed_browser_trial
    from test_browser_session import SITE

    from agent.turn_effects import turn_scope
    from host_runtime.authoring_browser_preflight import preflight_tool, repair_scope_for
    from host_runtime.chat_authoring import digest

    with failed_browser_trial(tmp_path, direct=True) as (runtime, _web, session, browser):
        chat = runtime.chat_authoring
        candidate = current(chat, runtime.actor, session)
        scope = repair_scope_for(chat, candidate)
        assert scope is not None
        ctx = context(chat, runtime.actor, session)
        tool = preflight_tool(chat, ctx, scope)
        args = {
            "candidate_id": candidate.candidate_id,
            "base_digest": digest(candidate.draft),
            "actions": [{"do": "open", "url": SITE + "/good"}],
        }
        before = list(browser.visited)
        with turn_scope():
            from agent.gateway import HostToolOutcome

            async def invoke() -> tuple[HostToolOutcome, HostToolOutcome]:
                return await tool.handler(ctx, args), await tool.handler(ctx, args)

            done, repeated = asyncio.run(invoke())
        assert done.status == repeated.status == "succeeded"
        assert isinstance(done.data, dict) and done.data["verified"] is False
        assert isinstance(repeated.data, dict) and repeated.data["replayed"] is True
        assert browser.visited == before + [SITE + "/good"]
        assert chat.approvals(runtime.actor, session_id=session, pending_only=True) == []
        assert chat.readiness(current(chat, runtime.actor, session))["verified"] is False


def test_desktop_export_has_no_application_folder_allowlist(tmp_path: Path) -> None:
    from test_desktop_session import Fakes, handler, request

    target = tmp_path / "outside" / "fixture.csv"
    fakes = Fakes()
    handler(tmp_path, fakes).run(request(actions=[{"do": "save_as", "path": str(target)}]))
    assert fakes.requests[-1]["actions"][0]["path"] == str(target.resolve())


def test_direct_trial_inputs_are_reused_without_a_historical_approval_record(
    tmp_path: Path,
) -> None:
    from test_authoring_browser_preflight import context, current, failed_browser_trial

    with failed_browser_trial(tmp_path, direct=True) as (runtime, _web, session, _browser):
        chat = runtime.chat_authoring
        candidate = current(chat, runtime.actor, session)
        ctx = context(chat, runtime.actor, session)
        assert chat.approvals(runtime.actor) == []
        assert chat._continue_authoring_trial(ctx, candidate, {}) == {}
