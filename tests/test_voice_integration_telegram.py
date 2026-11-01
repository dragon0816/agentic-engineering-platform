"""Offline Bot API voice integration; production api_base remains HTTPS-only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_chat_workflow_forms import _plain
from test_telegram_attachments import FileTransport
from test_telegram_ingress import (
    OWNER,
    STRANGER,
    TOKEN,
    CountingCredentials,
    config,
    ingress,
    poll,
    update,
)
from test_telegram_workflow_flow import _install, _tap
from voice_integration_helpers import (
    FIXTURES,
    MAX_BYTES,
    TextModel,
    assert_no_audio,
    fixture,
    provider,
    service,
    user_messages,
    wav,
)

from capabilities.coding_change.manifest import CHANGE_SPEC, coding_workflow
from channels.telegram import TelegramIngress
from host_runtime.workflow_form_tool import workflow_form_tools
from voice.contracts import REPLIES, ErrorCode
from voice.stt import SttError
from voice.transcript import TranscriptStore


def voice_update(
    number: int = 1,
    *,
    sender: int = OWNER,
    kind: str = "voice",
    duration: int = 2,
    size: int | None = None,
    mime: str = "audio/wav",
    caption: str | None = None,
) -> dict[str, Any]:
    message = update(number, sender, "")["message"]
    message.pop("text")
    message[kind] = {
        "file_id": "speech",
        "file_unique_id": "fixture-speech",
        "duration": duration,
        "mime_type": mime,
        "file_size": size,
    }
    if size is None:
        message[kind].pop("file_size")
    if caption is not None:
        message["caption"] = caption
    return {"update_id": number, "message": message}


def enabled(
    tmp_path: Path, transport: FileTransport, name: str = "zh_ask", error: SttError | None = None
) -> tuple[TelegramIngress, Any, Any, Any]:
    _, agent, runner = ingress(tmp_path, transport)
    fake = provider(name, error)
    injected: dict[str, Any] = {"voice": service(tmp_path / "workspace", fake)}
    item = TelegramIngress(
        config(),
        agent,
        CountingCredentials({"telegram_bot": TOKEN}),
        transport=transport,
        **injected,
    )
    return item, agent, runner, fake


def said(transport: FileTransport) -> list[str]:
    return [
        payload["text"]
        for url, payload in transport.calls
        if url.endswith(("/sendMessage", "/editMessageText")) and "text" in payload
    ]


def test_api_base_remains_https_only() -> None:
    """VOICE_INPUT §4.5: fake download transport never relaxes production validation."""
    with pytest.raises(ValidationError):
        config(api_base="http://127.0.0.1:12345")
    assert config().api_base == "https://api.telegram.org"


@pytest.mark.parametrize("kind", ["voice", "audio"])
def test_disabled_voice_keeps_the_existing_reply_and_never_downloads(
    tmp_path: Path, kind: str
) -> None:
    """VOICE_INPUT §3.3, §4.3: default disabled is the existing text-only refusal."""
    transport = FileTransport([[voice_update(kind=kind)]], {"speech": fixture("zh_ask")[0]})
    item, _, runner = ingress(tmp_path, transport)
    result = poll(item).deliveries[0]
    assert result.disposition == "unsupported_content"
    assert result.reply == "Only text messages are accepted here."
    assert transport.file_requests() == [] and transport.downloads == []
    assert runner.bridge.events == ()


def test_untrusted_sender_is_refused_before_getfile_or_download(tmp_path: Path) -> None:
    """VOICE_INPUT §3.3, §4.3: sender authorization precedes every file operation."""
    transport = FileTransport([[voice_update(sender=STRANGER)]], {"speech": fixture("zh_ask")[0]})
    item, _, runner, fake = enabled(tmp_path, transport)
    result = poll(item).deliveries[0]
    assert result.disposition == "unmapped_sender" and result.reply is None
    assert transport.file_requests() == [] and transport.downloads == []
    assert said(transport) == [] and fake.calls == [] and runner.bridge.events == ()


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"duration": 181}, "audio_too_long"),
        ({"size": MAX_BYTES + 1}, "audio_too_large"),
        ({"mime": "video/mp4"}, "audio_unsupported_format"),
    ],
)
def test_declared_limits_refuse_before_download(
    tmp_path: Path, changes: dict[str, Any], code: ErrorCode
) -> None:
    """VOICE_INPUT §3.3, §3.6: 180 s / 10 MiB / format checked before getFile."""
    transport = FileTransport([[voice_update(**changes)]], {"speech": fixture("zh_ask")[0]})
    item, _, runner, fake = enabled(tmp_path, transport)
    delivery = poll(item).deliveries[0]
    assert REPLIES[code] in (delivery.reply or "")
    assert transport.file_requests() == [] and transport.downloads == []
    assert fake.calls == [] and runner.bridge.events == ()
    records = TranscriptStore(tmp_path / "workspace").list("engineer", f"telegram-chat-{OWNER}")
    assert len(records) == 1 and records[0].error_code == code


def test_video_note_is_still_refused_without_download(tmp_path: Path) -> None:
    """VOICE_INPUT §1.2, §3.3: enabling voice never enables video notes."""
    transport = FileTransport([[voice_update(kind="video_note")]], {})
    item, _, runner, fake = enabled(tmp_path, transport)
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "unsupported_content"
    assert delivery.reply == "Only text messages are accepted here."
    assert transport.file_requests() == [] and transport.downloads == []
    assert fake.calls == [] and runner.bridge.events == ()


@pytest.mark.parametrize(
    "name,kind",
    [("zh_ask", "voice"), ("zh_ask", "audio"), ("zh_workflow", "voice"), ("zh_coding", "voice")],
)
def test_audio_reaches_the_same_three_text_paths_and_shows_transcript_first(
    tmp_path: Path,
    name: str,
    kind: str,
) -> None:
    """VOICE_INPUT §2.3, §3.3, §4.3: decode -> transcript -> unchanged model/form path."""
    data, pcm, expected = fixture(name)
    transport = FileTransport([[voice_update(kind=kind, size=len(data))]], {"speech": data})
    item, agent, runner, fake = enabled(tmp_path, transport, name)
    model = TextModel(
        None if name == "zh_ask" else ("coding-change" if name == "zh_coding" else "weekly-report")
    )
    agent.gateway.router.model = model
    engine = agent.gateway.engine
    engine.workflows.register(coding_workflow() if name == "zh_coding" else _plain("weekly-report"))
    agent.gateway.host_tools = lambda: workflow_form_tools(engine)
    spoken = poll(item).deliveries[0]
    assert spoken.replied and spoken.reply is not None
    assert transport.file_requests() == ["speech"] and len(transport.downloads) == 1
    assert transport.downloads[0].startswith("https://api.telegram.org/file/bot")
    assert [call.sha256 for call in fake.calls] == [pcm.sha256]
    messages = said(transport)
    transcript_index = next(
        i for i, text in enumerate(messages) if f"🎤 你說：「{expected}」" in text
    )
    answer_index = next(i for i, text in enumerate(messages) if text == spoken.reply)
    assert transcript_index < answer_index
    assert expected in user_messages(model)
    assert runner.bridge.events == ()
    records = TranscriptStore(tmp_path / "workspace").list("engineer", f"telegram-chat-{OWNER}")
    assert len(records) == 1 and records[0].text == expected and records[0].channel == "telegram"
    assert records[0].used_as is not None
    assert TOKEN not in records[0].model_dump_json()

    # A separate text session provides the baseline, with the same real router
    # and deterministic model. The voice turn must not inject hidden prompts.
    typed_root = tmp_path / "typed"
    typed_transport = FileTransport([[update(1, OWNER, expected)]], {})
    typed_item, typed_agent, typed_runner = ingress(typed_root, typed_transport)
    typed_model = TextModel(model.workflow)
    typed_agent.gateway.router.model = typed_model
    typed_engine = typed_agent.gateway.engine
    typed_engine.workflows.register(
        coding_workflow() if name == "zh_coding" else _plain("weekly-report")
    )
    typed_agent.gateway.host_tools = lambda: workflow_form_tools(typed_engine)
    typed = poll(typed_item).deliveries[0]
    assert spoken.reply == typed.reply and spoken.buttons == typed.buttons
    assert user_messages(model) == user_messages(typed_model)
    assert typed_runner.bridge.events == ()
    if name != "zh_ask":
        assert item._flows and typed_item._flows
    if name == "zh_coding":
        assert CHANGE_SPEC.side_effect == "write" and CHANGE_SPEC.policy.approval_required is True
    assert_no_audio(tmp_path / "workspace", data, pcm.samples)


@pytest.mark.parametrize("code", ["stt_unavailable", "stt_busy", "stt_timeout", "stt_failed"])
def test_stt_errors_show_a_safe_reply_and_do_not_reach_agent(
    tmp_path: Path, code: ErrorCode
) -> None:
    """VOICE_INPUT §3.6, §4.2: failed STT records the failure and never calls Agent."""
    data = fixture("zh_ask")[0]
    transport = FileTransport([[voice_update()]], {"speech": data})
    item, agent, runner, _ = enabled(tmp_path, transport, error=SttError(code))
    model = TextModel()
    agent.gateway.router.model = model
    assert REPLIES[code] in (poll(item).deliveries[0].reply or "")
    assert model.requests == [] and runner.bridge.events == ()
    records = TranscriptStore(tmp_path / "workspace").list("engineer", f"telegram-chat-{OWNER}")
    assert len(records) == 1 and records[0].error_code == code and records[0].text is None
    assert_no_audio(tmp_path / "workspace", data)


def test_download_failure_never_transcribes_or_calls_agent(tmp_path: Path) -> None:
    """VOICE_INPUT §3.3, §3.6: Bot API download failure uses the attachment refusal."""
    data = fixture("zh_ask")[0]
    transport = FileTransport([[voice_update()]], {"speech": data}, download_status=404)
    item, agent, runner, fake = enabled(tmp_path, transport)
    model = TextModel()
    agent.gateway.router.model = model
    delivery = poll(item).deliveries[0]
    assert delivery.reply and "🎤 你說" not in delivery.reply
    assert fake.calls == [] and model.requests == [] and runner.bridge.events == ()
    records = TranscriptStore(tmp_path / "workspace").list("engineer", f"telegram-chat-{OWNER}")
    assert len(records) == 1 and records[0].error_code == "download_failed"
    assert_no_audio(tmp_path / "workspace", data)


@pytest.mark.parametrize(
    "case,code",
    [
        ("duration", "audio_too_long"),
        ("bytes", "audio_too_large"),
        ("decode", "audio_decode_failed"),
        ("silence", "transcript_empty"),
    ],
)
def test_downloaded_audio_is_rechecked_before_acting(
    tmp_path: Path, case: str, code: ErrorCode
) -> None:
    """VOICE_INPUT §3.3, §3.6: actual bytes and decoded length override Telegram metadata."""
    data = fixture("zh_ask")[0]
    if case == "duration":
        data = wav(180.001)
    elif case == "bytes":
        data += b"\0" * (MAX_BYTES + 1 - len(data))
    elif case == "decode":
        data = (FIXTURES / "not_audio.ogg").read_bytes()
    elif case == "silence":
        data = fixture("silence_2s")[0]
    transport = FileTransport([[voice_update(size=1, duration=1)]], {"speech": data})
    item, agent, runner, _ = enabled(
        tmp_path, transport, "silence_2s" if case == "silence" else "zh_ask"
    )
    model = TextModel()
    agent.gateway.router.model = model
    assert REPLIES[code] in (poll(item).deliveries[0].reply or "")
    assert model.requests == [] and runner.bridge.events == ()
    assert_no_audio(tmp_path / "workspace", data)


@pytest.mark.parametrize("name", ["zh_confirm", "zh_cancel"])
def test_spoken_confirm_keeps_card_open_but_cancel_closes_it(tmp_path: Path, name: str) -> None:
    """VOICE_INPUT §2.4, §4.3: spoken 好 cannot run; spoken 取消 cancels the open card."""
    data = fixture(name)[0]
    transport = FileTransport(
        [[update(1, OWNER, "run release-validation-form package=quick")]], {"speech": data}
    )
    item, agent, runner, _ = enabled(tmp_path, transport, name)
    _install(agent, [{"name": "package", "label": "Mode", "kind": "text", "required": True}])
    waiting = poll(item).deliveries[0]
    assert waiting.buttons == ((("確認執行", "run:yes"), ("修改", "run:edit")),)
    assert runner.bridge.events == ()
    transport.batches.append([voice_update(2)])
    spoken = poll(item).deliveries[0]
    assert runner.bridge.events == ()
    if name == "zh_confirm":
        assert REPLIES["voice_not_confirmation"] in (spoken.reply or "")
        assert item._flows
        transport.batches.append([_tap(3, OWNER, "run:yes", transport)])
        ran = poll(item).deliveries[0]
        assert ran.outcome is not None and ran.outcome.workflow is not None
    else:
        assert spoken.reply == "Cancelled." and not item._flows
    assert_no_audio(tmp_path / "workspace", data)


@pytest.mark.parametrize("voice_enabled", [False, True])
def test_plain_text_keeps_its_confirmation_semantics(tmp_path: Path, voice_enabled: bool) -> None:
    """VOICE_INPUT §2.4, §4.3: typed 好 still confirms, whether voice is on or off."""
    transport = FileTransport(
        [[update(1, OWNER, "run release-validation-form package=quick")], [update(2, OWNER, "好")]],
        {},
    )
    if voice_enabled:
        item, agent, runner, fake = enabled(tmp_path, transport)
    else:
        item, agent, runner = ingress(tmp_path, transport)
        fake = provider("zh_ask")
    _install(agent, [{"name": "package", "label": "Mode", "kind": "text", "required": True}])
    assert poll(item).deliveries[0].buttons
    assert runner.bridge.events == ()
    ran = poll(item).deliveries[0]
    assert ran.outcome is not None and ran.outcome.workflow is not None
    assert fake.calls == [] and transport.downloads == []


def test_coding_voice_preserves_the_real_pending_approval_and_never_writes(tmp_path: Path) -> None:
    """VOICE_INPUT §2.3, §4.3: a spoken coding request creates the typed coding ApprovalRequest."""
    from voice_integration_helpers import CODING_ARGUMENTS, CodingModel, coding_approvals

    data, _, text = fixture("zh_coding")
    transport = FileTransport([[voice_update()], [update(2, OWNER, text)]], {"speech": data})
    item, agent, _, _ = enabled(tmp_path, transport, "zh_coding")
    chat, writes = coding_approvals(agent, tmp_path / "workspace")
    item.approvals = chat
    agent.gateway.router.model = CodingModel()
    voice_result = poll(item).deliveries[0]
    first = chat.approvals("engineer")
    assert len(first) == 1 and first[0].status == "pending"
    assert first[0].workflow == "coding/change@1.0.0" and first[0].arguments == CODING_ARGUMENTS
    assert any(data.startswith("approve:") for row in voice_result.buttons for _, data in row)
    assert writes == []
    typed_result = poll(item).deliveries[0]
    approvals = chat.approvals("engineer")
    assert len(approvals) == 2 and all(record.status == "pending" for record in approvals)
    assert all(record.arguments == CODING_ARGUMENTS for record in approvals)
    assert voice_result.reply == typed_result.reply and writes == []
    assert_no_audio(tmp_path / "workspace", data)


def test_knowledge_voice_and_text_keep_the_same_grounded_answer_and_citations(
    tmp_path: Path,
) -> None:
    """VOICE_INPUT §2.3, §4.3: the existing knowledge tool keeps Raw citations on both paths."""
    from test_agent_web import knowledge_runtime
    from test_product_e2e_05 import V1

    from agent.gateway import KnowledgeVaultTool
    from agent.skills import SkillManifest
    from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
    from host_runtime.knowledge_harness import KnowledgeHarness
    from models.contracts import ModelRequest, ModelResponse, ModelToolCall

    class KnowledgeModel(TextModel):
        def generate(self, request: ModelRequest) -> ModelResponse:
            self.requests.append(request)
            assert "knowledge__widget-guide" in {tool.name for tool in request.tools}
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                tool_calls=(
                    ModelToolCall(
                        call_id="knowledge",
                        name="knowledge__widget-guide",
                        arguments={"question": "What firmware does Safe mode require?"},
                    ),
                ),
            )

    data, _, text = fixture("zh_ask")
    with knowledge_runtime(tmp_path, harness_skill=True) as runtime:
        transport = FileTransport([[voice_update()]], {"speech": data})
        model = KnowledgeModel()
        runtime.agent.gateway._knowledge_vaults = lambda: [
            KnowledgeVaultTool(asset=V1, purpose="Widget operating instructions")
        ]
        runtime.agent.gateway._knowledge_capability = KNOWLEDGE_QUERY_SPEC.identity
        runtime.agent.gateway.router.commands.skills.register(
            SkillManifest.model_validate(
                {
                    "metadata": {
                        "identity": {
                            "namespace": "engineering",
                            "name": "voice-knowledge",
                            "version": "1.0.0",
                        },
                        "owner": {"type": "team", "id": "engineering"},
                        "visibility": "private",
                        "lifecycle": "validated",
                    },
                    "alias": "knowledge",
                    "instructions": "Answer from Raw with citations.",
                    "commands": [
                        {
                            "name": "ask",
                            "kind": "capability",
                            "target": KNOWLEDGE_QUERY_SPEC.identity.model_dump(),
                        }
                    ],
                }
            )
        )
        harness = KnowledgeHarness(runtime, "engineering")
        evidence: list[dict[str, Any]] = []

        def grounded(*args: Any, **kwargs: Any) -> dict[str, Any]:
            result = harness.for_tool(*args, **kwargs)
            evidence.append(result)
            return result

        def raw_citations(value: Any) -> list[str]:
            if isinstance(value, dict):
                own = (
                    [value["raw_ref"]]
                    if value.get("kind") == "raw" and value.get("raw_ref")
                    else []
                )
                return own + [ref for child in value.values() for ref in raw_citations(child)]
            if isinstance(value, list):
                return [ref for child in value for ref in raw_citations(child)]
            return []

        runtime.agent.gateway.knowledge_harness = grounded
        runtime.agent.gateway.router.model = model
        # The STT response is scripted to ask the existing fixture vault's
        # question; ASR accuracy belongs to the opt-in real-engine tests.
        text = "What firmware does Safe mode require?"
        injected: dict[str, Any] = {
            "voice": service(runtime.layout.workspace_root, provider("zh_ask", text))
        }
        item = TelegramIngress(
            config(bridge_id=runtime.config.device.bridge_id),
            runtime.agent,
            CountingCredentials({"telegram_bot": TOKEN}),
            transport=transport,
            **injected,
        )
        spoken = poll(item).deliveries[0]
        assert text in user_messages(model)
        assert spoken.reply and "Safe mode requires firmware 2.0 [1]." in spoken.reply
        # Use a different private chat so the baseline has no voice history.
        transport.batches.append([update(2, OWNER, text, chat=777)])
        typed = poll(item).deliveries[0]
        assert typed.reply == spoken.reply
        assert len(evidence) == 2
        assert raw_citations(evidence[0]) and raw_citations(evidence[0]) == raw_citations(
            evidence[1]
        )
        assert_no_audio(runtime.layout.workspace_root, data)
