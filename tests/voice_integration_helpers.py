"""Contract-derived, offline fixtures shared by the voice channel tests."""

from __future__ import annotations

import base64
import hashlib
import importlib
import io
import json
import threading
import wave
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from test_agent_web import base, fetch

from agent.skills import SkillManifest
from capabilities.coding_change.contracts import CodingChangeResult, CodingChangeStepInput
from capabilities.coding_change.manifest import CHANGE_SPEC, coding_skill
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from common.workflow_run_form import FORM_TOOL
from host_runtime.chat_authoring import ChatAuthoring
from host_runtime.web import AgentWeb, AgentWebServer
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent, ModelToolCall
from voice.contracts import VoiceConfig
from voice.stt import FakeSttProvider, Pcm16k, Segment, SttError, SttResult
from voice.transcript import TranscriptStore
from workflow.dispatch import BridgeExecutor

FIXTURES = Path(__file__).parent / "fixtures" / "voice"
MAX_BYTES = 10 * 1024 * 1024


def fixture(name: str) -> tuple[bytes, Pcm16k, str]:
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["fixtures"] if item["name"] == name)
    data = (FIXTURES / entry["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    with wave.open(io.BytesIO(data)) as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 16000)
        pcm = Pcm16k(audio.readframes(audio.getnframes()))
    return data, pcm, entry.get("text", "")


def wav(seconds: float) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * int(seconds * 16000))
    return buffer.getvalue()


def provider(name: str, answer: str | SttError | None = None) -> FakeSttProvider:
    _, pcm, text = fixture(name)
    result = (
        answer
        if isinstance(answer, SttError)
        else SttResult(
            segments=(Segment(0, pcm.duration_seconds, text if answer is None else answer),),
            language="zh",
            duration_seconds=pcm.duration_seconds,
            elapsed_seconds=0.01,
            engine="fake",
            model="fixture",
            model_revision="a" * 64,
        )
    )
    return FakeSttProvider({pcm.sha256: result})


def service(root: Path, fake: FakeSttProvider) -> Any:
    # V2 is intentionally optional at collection time; absence is a test failure,
    # never an import error that hides the tests for the already committed APIs.
    module = importlib.import_module("voice.service")
    config = VoiceConfig(
        enabled=True, model_path=str(root / "offline-model"), model_sha256="a" * 64
    )
    return module.VoiceService(config, fake, TranscriptStore(root))


def payload(session: str, data: bytes, **changes: Any) -> dict[str, Any]:
    return {
        "session_id": session,
        "mime_type": "audio/wav",
        "duration_ms": 1000,
        "data": base64.b64encode(data).decode("ascii"),
        **changes,
    }


def assert_no_audio(root: Path, *recordings: bytes) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            content = path.read_bytes()
            assert path.suffix.lower() not in {".wav", ".ogg", ".webm", ".mp3", ".m4a", ".pcm"}
            for recording in recordings:
                if recording:
                    assert recording not in content, f"Audio persisted in {path}"


@contextmanager
def serve(runtime: Any, voice: Any = None) -> Iterator[AgentWebServer]:
    kwargs = {} if voice is None else {"voice": voice}
    server = AgentWebServer(AgentWeb(runtime), **kwargs)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def post(server: AgentWebServer, path: str, body: dict[str, Any]) -> Any:
    return fetch(base(server) + path, token=server.token, body=body)


def conversation(server: AgentWebServer) -> str:
    response = post(server, "/api/conversations", {})
    assert response.status == 201
    return str(response.json()["conversation"]["session_id"])


class TextModel:
    """A deterministic model; routing/Workflow policy remain real."""

    def __init__(self, workflow: str | None = None, values: dict[str, Any] | None = None) -> None:
        self.workflow = workflow
        self.values = values or {}
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        calls = (
            ()
            if self.workflow is None
            else (
                ModelToolCall(
                    call_id="voice-form",
                    name=FORM_TOOL,
                    arguments={"workflow": self.workflow, "values": self.values},
                ),
            )
        )
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            text="CMX500 的 Wi-Fi 8 選項請參考產品手冊 [1]。",
            tool_calls=calls,
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise AssertionError("The deterministic test model does not stream")


def user_messages(model: TextModel) -> list[str]:
    return [
        message.text
        for request in model.requests
        for message in request.messages
        if message.role == "user"
    ]


CODING_ARGUMENTS: dict[str, Any] = {
    "request": {
        "repository": "fixture",
        "requirement": "Use UTF-8 for CSV",
        "file": "parser.py",
        "tests": ["tests/test_parser.py"],
    }
}


class CodingModel(TextModel):
    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if request.messages[-1].role == "tool":
            return ModelResponse(
                trace=request.trace, model_alias=request.model_alias, text="程式修改等待你的核准。"
            )
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            tool_calls=(
                ModelToolCall(
                    call_id="coding-write", name="coding__change", arguments=CODING_ARGUMENTS
                ),
            ),
        )


def coding_approvals(agent: Any, root: Path) -> tuple[ChatAuthoring, list[dict[str, Any]]]:
    """Use the real coding spec and owner policy with an inert execution spy."""
    writes: list[dict[str, Any]] = []

    async def write(context: RequestContext, inputs: Contract) -> Contract:
        writes.append(inputs.model_dump())
        raise AssertionError("Coding must wait for approval")

    installed = InstalledCapabilities()
    installed.register(
        CHANGE_SPEC,
        write,
        CodingChangeStepInput,
        CodingChangeResult,
        ExecutionDependencies(central_required=False),
    )
    grant = CapabilityGrant(
        actor="engineer",
        asset=CHANGE_SPEC.identity,
        permissions=("coding.change",),
        policy_refs=("coding-restricted-execution-policy",),
        approval_ref="device-owner",
    )
    bridge = BridgeExecutor(installed, LocalPolicy((grant,), owner_mode=True))
    chat = ChatAuthoring(
        root / "chat",
        bridge=lambda: bridge,
        namespace="engineering",
        workflows_dir=root / "workflows",
        grants_file=root / "grants.json",
    )
    raw = coding_skill().model_dump(mode="json")
    raw["commands"] = [
        {
            "name": "change",
            "kind": "capability",
            "target": CHANGE_SPEC.identity.model_dump(mode="json"),
        }
    ]
    raw["rules"] = []
    raw["default_command"] = None
    agent.gateway.router.commands.skills.register(SkillManifest.model_validate(raw))
    agent.gateway.bridge = bridge
    agent.gateway.capability_approval = chat.capability_approval_tool_data
    return chat, writes
