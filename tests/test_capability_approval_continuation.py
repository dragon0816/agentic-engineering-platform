"""An approved ordinary capability resumes an unfinished authoring task once.

Owner 2026-11-11 (docs/phases/CAPABILITY_APPROVAL_CONTINUATION_PROPOSAL.md):
an ordinary approval used to end the model turn for good, so a person had to
type "continue" after every button. Knowledge and other conversations without
a planned authoring task keep their exact behavior.
"""

from pathlib import Path
from typing import Any

from test_authoring_repair import Capturing
from test_chat_authoring import Echo, Out, spec
from test_conversation_turn_groups import _chat_config, _ChatGateway

from capabilities.runtime import CapabilityExecutionFailed, CapabilityGrant, LocalPolicy
from capabilities.web.handlers import WebHostBinding
from common.assets import AssetIdentity, ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from host_runtime.authoring_task import AuthoringQuestion, Requirement
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb
from workflow.dispatch import BridgeExecutor

READ = AssetIdentity(namespace="lab", name="read-it", version="1.0.0")


class _Setup:
    def __init__(self, tmp_path: Path) -> None:
        config, layout = _chat_config(tmp_path)
        config = config.model_copy(update={"web": WebHostBinding(allowed_origins=("*",))})
        self._built = build_runtime(config, layout=layout, model_transport=_ChatGateway())
        self.runtime = self._built.__enter__()
        self.calls: list[str] = []

        async def fixture(context: RequestContext, inputs: Contract) -> Contract:
            value = Echo.model_validate(inputs).value
            self.calls.append(value)
            if value == "bad":
                raise CapabilityExecutionFailed("fixture_failure", Out(echoed="failed"))
            return Out(echoed=value)

        self.runtime.agent.gateway.bridge.installed.register(
            spec("read-it", "read"),
            fixture,
            Echo,
            Out,
            ExecutionDependencies(central_required=False),
        )
        self.web = AgentWeb(self.runtime)
        self.session = self.web.create_conversation()["conversation"]["session_id"]
        chat = self.runtime.chat_authoring
        assert chat is not None
        self.chat = chat
        # The person's approved call runs as the person (owner mode), as live.
        grant = CapabilityGrant(
            actor=self.runtime.actor,
            asset=READ,
            permissions=("lab.read-it",),
            policy_refs=("lab-policy",),
            approval_ref="device-owner",
        )
        bridge = BridgeExecutor(
            self.runtime.agent.gateway.bridge.installed, LocalPolicy((grant,), owner_mode=True)
        )
        chat._bridge = lambda: bridge

    def close(self) -> None:
        self._built.__exit__(None, None, None)

    def plan(self) -> None:
        self.chat.tasks.plan(
            self.runtime.actor,
            self.session,
            "Read fixture and build a reusable Workflow",
            [
                Requirement(
                    requirement_id="read",
                    description="Read fixture",
                    check_ids=("read",),
                    assertions=(
                        {
                            "path": ["steps", 0, "capability", "name"],
                            "operator": "equals",
                            "expected": "read-it",
                        },
                    ),
                )
            ],
        )

    def model(self, *answers: Any) -> Capturing:
        model = Capturing(*answers)
        self.runtime.agent.gateway.router.model = model
        return model

    def request(self, value: str = "good") -> str:
        pending = self.chat.request_capability(
            self.runtime.actor, self.session, READ, {"value": value}
        )
        return pending.approval_id

    def messages(self) -> list[Any]:
        record = self.runtime.state.conversation(self.session, self.runtime.actor)
        assert record is not None
        return list(record.messages)


def test_approved_capability_continues_the_authoring_task_once(tmp_path: Path) -> None:
    setup = _Setup(tmp_path)
    try:
        setup.plan()
        # A text-only end on an unfinished task is re-asked once and then held
        # by the existing completion check; this continuation must not change it.
        model = setup.model({"text": "我先看一下結果。"}, {"text": "下一步需要你核准。"})
        approval = setup.request()
        result = setup.web.decide_approval(approval, "approve")
        assert result["ok"] is True and setup.calls == ["good"]
        assert result["continuation"]["status"] == "needs_input"
        assert len(model.requests) == 2
        sent = model.requests[0].messages[-1].text
        assert "[Host continuation after the owner's approval]" in sent
        messages = setup.messages()
        assert messages[-1].role == "assistant"
        assert messages[-1].text.startswith("下一步需要你核准。")
        assert messages[-2].text.startswith("【已核准並執行】lab/read-it@1.0.0")
        assert len(messages) == 3
        # The same button pressed again neither runs nor continues anything.
        again = setup.web.decide_approval(approval, "approve")
        assert again == {"ok": False, "code": "approval_already_decided"}
        assert setup.calls == ["good"] and len(model.requests) == 2
        assert len(setup.messages()) == 3
        # The continuation is visible as Agent Web activity while it runs.
        kinds = [task["kind"] for task in setup.web.task_list()["tasks"]]
        assert "authoring_continuation" in kinds
    finally:
        setup.close()


def test_failed_capability_also_continues_once(tmp_path: Path) -> None:
    setup = _Setup(tmp_path)
    try:
        setup.plan()
        model = setup.model({"text": "動作失敗。"}, {"text": "我會換一個目標再請你核准。"})
        result = setup.web.decide_approval(setup.request("bad"), "approve")
        assert result["ok"] is True and result["approval"]["status"] == "failed"
        assert "continuation" in result and len(model.requests) == 2
        assert "[Host continuation after the owner's approval]" in (
            model.requests[0].messages[-1].text
        )
    finally:
        setup.close()


def test_rejection_does_not_continue(tmp_path: Path) -> None:
    setup = _Setup(tmp_path)
    try:
        setup.plan()
        model = setup.model()
        result = setup.web.decide_approval(setup.request(), "reject")
        assert result["ok"] is True and "continuation" not in result
        assert model.requests == [] and setup.calls == []
    finally:
        setup.close()


def test_knowledge_or_plain_conversation_keeps_its_behavior(tmp_path: Path) -> None:
    """No planned authoring task (e.g. a Knowledge question) means no new turn."""
    setup = _Setup(tmp_path)
    try:
        setup.chat.tasks.observe(
            setup.runtime.actor,
            setup.session,
            "CMX500 支援哪些 5G NR 頻段？",
            (),
            event_id="web-input-knowledge",
            reopen=False,
        )
        model = setup.model()
        before = len(setup.messages())
        result = setup.web.decide_approval(setup.request(), "approve")
        assert result["ok"] is True and "continuation" not in result
        assert model.requests == [] and setup.calls == ["good"]
        assert len(setup.messages()) == before + 2  # only the decision and its result
    finally:
        setup.close()


def test_open_business_question_waits_for_the_person(tmp_path: Path) -> None:
    setup = _Setup(tmp_path)
    try:
        setup.plan()
        task = setup.chat.tasks.load(setup.runtime.actor, setup.session)
        assert task is not None
        setup.chat.tasks.save(
            setup.runtime.actor,
            setup.session,
            task.model_copy(
                update={
                    "question": AuthoringQuestion(
                        reason="business_decision", question="沒有匯率的幣別要怎麼處理？"
                    )
                }
            ),
        )
        model = setup.model()
        result = setup.web.decide_approval(setup.request(), "approve")
        assert result["ok"] is True and "continuation" not in result
        assert model.requests == []
    finally:
        setup.close()


def test_active_turn_is_not_interrupted(tmp_path: Path) -> None:
    setup = _Setup(tmp_path)
    try:
        setup.plan()
        model = setup.model()
        with setup.web._turn_lock(setup.session):
            result = setup.web.decide_approval(setup.request(), "approve")
        assert result["ok"] is True and setup.calls == ["good"]
        assert "continuation" not in result and model.requests == []
    finally:
        setup.close()


def test_non_gateway_conversation_does_not_continue(tmp_path: Path) -> None:
    setup = _Setup(tmp_path)
    try:
        setup.plan()
        record = setup.runtime.state.conversation(setup.session, setup.runtime.actor)
        assert record is not None
        setup.runtime.state.save_conversation(record.model_copy(update={"backend": "codex"}))
        model = setup.model()
        result = setup.web.decide_approval(setup.request(), "approve")
        assert result["ok"] is True and "continuation" not in result
        assert model.requests == []
    finally:
        setup.close()
