import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from common.assets import SecretRef
from development.telegram_control import (
    MechanismGuidance,
    MechanismProblem,
    TelegramControlConfig,
    TelegramControlPlane,
    ValidationControlEvent,
    config_from_environment,
)
from models.credentials import StaticCredentials

TOKEN = "123456789:abcdefghijklmnopqrstuvwxyzABCDE12345"
REPOSITORY = "dragon0816/agentic-engineering-platform"


class Reply:
    def __init__(self, status: int, body: object) -> None:
        self.status = status
        self.body = json.dumps(body).encode("utf-8")

    def chunks(self) -> Iterator[bytes]:
        yield self.body

    def close(self) -> None:
        pass


class Transport:
    def __init__(self, *replies: Reply) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, dict[str, Any], Mapping[str, str]]] = []

    def send(
        self,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout_s: float,
    ) -> Reply:
        del timeout_s
        self.calls.append((url, json.loads(body), headers))
        return self.replies.pop(0)


class GitHub:
    def __init__(self) -> None:
        self.queued = (132,)
        self.snapshots = {
            132: {
                "number": 132,
                "title": "Company agent integration failure",
                "state": "OPEN",
                "url": f"https://github.com/{REPOSITORY}/issues/132",
                "labels": [
                    {"name": "codex-local-running"},
                    {"name": "hermes-validation-failed"},
                ],
            }
        }

    def queued_issues(self) -> tuple[int, ...]:
        return self.queued

    def issue_summary(self, issue: int) -> dict[str, Any]:
        return self.snapshots[issue]


def config() -> TelegramControlConfig:
    return TelegramControlConfig(
        repository=REPOSITORY,
        credential=SecretRef(name="local_codex_telegram"),
        owner_user_id=1001,
        validation_bot_id=2002,
        control_chat_id=-1003003,
    )


def update(
    update_id: int,
    *,
    sender: int,
    is_bot: bool,
    text: str,
    chat: int = -1003003,
) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "message": {
            "chat": {"id": chat},
            "from": {"id": sender, "is_bot": is_bot},
            "text": text,
        },
    }


def ok_updates(*items: dict[str, Any]) -> Reply:
    return Reply(200, {"ok": True, "result": list(items)})


def ok_sent() -> Reply:
    return Reply(200, {"ok": True, "result": {"message_id": 1}})


def plane(tmp_path: Path, transport: Transport) -> TelegramControlPlane:
    return TelegramControlPlane(
        config(),
        StaticCredentials({"local_codex_telegram": TOKEN}),
        GitHub(),
        state_path=tmp_path / "telegram-state.json",
        transport=transport,
    )


def event(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "aep-agent-coordination/v1",
        "producer": "validation-agent",
        "event_id": "hermes-132-validation-failed-001",
        "event": "validation_failed",
        "repository": REPOSITORY,
        "issue": 132,
        "request_id": "deployment-company-agent-36591676672",
        "target_sha": "a" * 40,
        "hop": 0,
    }
    value.update(changes)
    return value


def test_environment_config_is_optional_all_or_nothing_and_never_contains_token() -> None:
    assert config_from_environment(REPOSITORY, {}) is None

    environment = {
        "TELEGRAM_BOT_TOKEN": TOKEN,
        "TELEGRAM_OWNER_USER_ID": "1001",
        "TELEGRAM_HERMES_BOT_ID": "2002",
        "TELEGRAM_CONTROL_CHAT_ID": "-1003003",
    }
    configured = config_from_environment(REPOSITORY, environment)

    assert configured is not None
    assert configured.owner_user_id == 1001
    assert TOKEN not in json.dumps(configured.model_dump(mode="json"))
    with pytest.raises(ValueError, match="all four"):
        config_from_environment(REPOSITORY, {"TELEGRAM_BOT_TOKEN": TOKEN})


def test_config_keeps_owner_hermes_and_chat_identities_distinct() -> None:
    with pytest.raises(ValidationError, match="different identities"):
        TelegramControlConfig.model_validate(
            config().model_dump(mode="python") | {"validation_bot_id": 1001}
        )


def test_owner_status_reads_github_without_mutating_it(tmp_path: Path) -> None:
    transport = Transport(
        ok_updates(update(7, sender=1001, is_bot=False, text="/status #132")),
        ok_sent(),
    )

    result = plane(tmp_path, transport).poll_once()

    assert result.processed == 1
    assert result.failure is None
    assert len(transport.calls) == 2
    reply = transport.calls[1][1]["text"]
    assert "Issue #132" in reply
    assert "codex-local-running" in reply
    assert "Company agent integration failure" in reply
    assert (
        json.loads((tmp_path / "telegram-state.json").read_text(encoding="utf-8"))["next_offset"]
        == 8
    )


def test_untrusted_sender_wrong_chat_and_arbitrary_owner_text_do_nothing_dangerous(
    tmp_path: Path,
) -> None:
    transport = Transport(
        ok_updates(
            update(1, sender=9999, is_bot=False, text="/status"),
            update(2, sender=1001, is_bot=False, text="/status", chat=-1009999),
            update(3, sender=1001, is_bot=False, text="merge main"),
        ),
        ok_sent(),
    )

    result = plane(tmp_path, transport).poll_once()

    assert result.processed == 1
    assert len(transport.calls) == 2
    assert "Only /status" in transport.calls[1][1]["text"]


def test_hermes_event_is_strict_verified_against_github_and_acknowledged_once(
    tmp_path: Path,
) -> None:
    payload = json.dumps(event(), separators=(",", ":"))
    transport = Transport(
        ok_updates(update(10, sender=2002, is_bot=True, text=payload)),
        ok_sent(),
    )
    first = plane(tmp_path, transport)

    result = first.poll_once()

    assert result.processed == 1
    ack = json.loads(transport.calls[1][1]["text"])
    assert ack == {
        "schema": "aep-agent-coordination-ack/v1",
        "producer": "coding-agent",
        "event_id": "hermes-132-validation-failed-001",
        "repository": REPOSITORY,
        "issue": 132,
        "request_id": "deployment-company-agent-36591676672",
        "outcome": "observed",
        "github_state": "OPEN",
        "github_labels": ["codex-local-running", "hermes-validation-failed"],
        "next_action": "github_state_observed",
        "hop": 1,
    }

    duplicate_transport = Transport(ok_updates(update(11, sender=2002, is_bot=True, text=payload)))
    duplicate = plane(tmp_path, duplicate_transport).poll_once()
    assert duplicate.processed == 0
    assert len(duplicate_transport.calls) == 1


def test_hermes_payload_rejects_extra_fields_wrong_identity_and_reply_loops(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError):
        ValidationControlEvent.model_validate(event(command="gh pr merge"))
    with pytest.raises(ValidationError):
        ValidationControlEvent.model_validate(event(hop=1))

    transport = Transport(
        ok_updates(
            update(20, sender=2002, is_bot=False, text=json.dumps(event())),
            update(
                21,
                sender=2002,
                is_bot=True,
                text=json.dumps(event(repository="someone/else")),
            ),
        )
    )

    result = plane(tmp_path, transport).poll_once()

    assert result.processed == 0
    assert len(transport.calls) == 1


def test_mechanism_problem_needs_no_issue_and_is_persisted_with_a_bounded_next_action(
    tmp_path: Path,
) -> None:
    mechanism = {
        "code": "VALIDATION_POLLER_BLOCKED",
        "summary": "The validation poller stopped before functional tests.",
        "expected": "Consume the trusted payload once and run the fixed profile.",
        "observed": "The poller reports setup unavailable and stays paused.",
        "evidence_refs": ["hermes://runs/deployment-company-agent-001/result.json"],
        "requested_response": "diagnosis",
    }
    payload = event(
        event_id="mechanism-company-agent-001",
        event="mechanism_blocked",
        issue=None,
        mechanism=mechanism,
    )
    transport = Transport(
        ok_updates(update(30, sender=2002, is_bot=True, text=json.dumps(payload))),
        ok_sent(),
    )

    result = plane(tmp_path, transport).poll_once()

    assert result.processed == 1
    ack = json.loads(transport.calls[1][1]["text"])
    assert ack["schema"] == "aep-agent-coordination-ack/v1"
    assert ack["issue"] is None
    assert ack["next_action"] == "coding_agent_review_required"
    state = json.loads((tmp_path / "telegram-state.json").read_text(encoding="utf-8"))
    assert state["mechanism_events"][0]["problem"]["code"] == "VALIDATION_POLLER_BLOCKED"

    with pytest.raises(ValidationError, match="mechanism details"):
        ValidationControlEvent.model_validate(event(event="mechanism_blocked", issue=None))
    with pytest.raises(ValidationError, match="only mechanism events"):
        ValidationControlEvent.model_validate(event(mechanism=mechanism))
    with pytest.raises(ValidationError):
        MechanismProblem.model_validate(mechanism | {"command": "restart everything"})


def test_known_model_routing_blocker_emits_one_closed_guidance_after_ack(
    tmp_path: Path,
) -> None:
    payload = event(
        event_id="mechanism-blocked-139-model-routing",
        event="mechanism_blocked",
        issue=None,
        request_id="validate-e2e-02-43d4b9a-20260930",
        target_sha="b" * 40,
        mechanism={
            "code": "MODEL_ROUTING_NOT_CONFIGURED",
            "summary": "The fixed validation profile could not start.",
            "expected": "The profile-owned loopback model is available.",
            "observed": "The host has no models configuration.",
            "evidence_refs": ["github://example/issues/139#issuecomment-1"],
            "requested_response": "diagnosis",
        },
    )
    transport = Transport(
        ok_updates(update(40, sender=2002, is_bot=True, text=json.dumps(payload))),
        ok_sent(),
        ok_sent(),
    )

    result = plane(tmp_path, transport).poll_once()

    assert result.failure is None
    assert result.processed == 2
    ack = json.loads(transport.calls[1][1]["text"])
    guidance = json.loads(transport.calls[2][1]["text"])
    assert ack["next_action"] == "coding_agent_review_required"
    assert guidance == {
        "schema": "aep-agent-coordination-guidance/v1",
        "producer": "coding-agent",
        "event_id": "mechanism-blocked-139-model-routing",
        "repository": REPOSITORY,
        "issue": None,
        "request_id": "validate-e2e-02-43d4b9a-20260930",
        "target_sha": "b" * 40,
        "mechanism_code": "MODEL_ROUTING_NOT_CONFIGURED",
        "action": "provision_profile_model_routing",
        "next_action": "retry_same_validation_request",
        "hop": 1,
    }
    assert MechanismGuidance.model_validate(guidance).action == ("provision_profile_model_routing")
    state = json.loads((tmp_path / "telegram-state.json").read_text(encoding="utf-8"))
    assert state["guidance_event_ids"] == ["mechanism-blocked-139-model-routing"]

    duplicate = Transport(
        ok_updates(update(41, sender=2002, is_bot=True, text=json.dumps(payload)))
    )
    duplicate_result = plane(tmp_path, duplicate).poll_once()
    assert duplicate_result.processed == 0
    assert len(duplicate.calls) == 1


def test_existing_model_routing_blocker_gets_guidance_after_worker_upgrade(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "telegram-state.json"
    state_path.write_text(
        json.dumps(
            {
                "next_offset": 50,
                "event_ids": ["mechanism-blocked-139-existing"],
                "mechanism_events": [
                    {
                        "event_id": "mechanism-blocked-139-existing",
                        "request_id": "validate-e2e-02-43d4b9a-20260930",
                        "target_sha": "c" * 40,
                        "issue": None,
                        "problem": {
                            "code": "MODEL_ROUTING_NOT_CONFIGURED",
                            "summary": "The profile did not start.",
                            "expected": "A profile-owned loopback model binding.",
                            "observed": "No models configuration was present.",
                            "evidence_refs": [],
                            "requested_response": "diagnosis",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    transport = Transport(ok_updates(), ok_sent())

    result = plane(tmp_path, transport).poll_once()

    assert result.failure is None
    assert result.processed == 1
    guidance = json.loads(transport.calls[1][1]["text"])
    assert guidance["schema"] == "aep-agent-coordination-guidance/v1"
    assert guidance["event_id"] == "mechanism-blocked-139-existing"
    assert guidance["next_action"] == "retry_same_validation_request"


def test_mechanism_guidance_contract_rejects_arbitrary_actions() -> None:
    with pytest.raises(ValidationError):
        MechanismGuidance.model_validate(
            {
                "schema": "aep-agent-coordination-guidance/v1",
                "producer": "coding-agent",
                "event_id": "mechanism-blocked-139-model-routing",
                "repository": REPOSITORY,
                "issue": None,
                "request_id": "validate-e2e-02-43d4b9a-20260930",
                "target_sha": "d" * 40,
                "mechanism_code": "MODEL_ROUTING_NOT_CONFIGURED",
                "action": "run_shell_command",
                "next_action": "retry_same_validation_request",
                "hop": 1,
            }
        )


def test_resolved_model_routing_event_does_not_emit_retry_guidance(tmp_path: Path) -> None:
    payload = event(
        event_id="mechanism-resolved-139-model-routing",
        event="mechanism_resolved",
        issue=None,
        mechanism={
            "code": "MODEL_ROUTING_NOT_CONFIGURED",
            "summary": "The profile-owned model binding is now installed.",
            "expected": "The same request can resume.",
            "observed": "Preflight found the fixed loopback route.",
            "evidence_refs": [],
            "requested_response": "resume_decision",
        },
    )
    transport = Transport(
        ok_updates(update(60, sender=2002, is_bot=True, text=json.dumps(payload))),
        ok_sent(),
    )

    result = plane(tmp_path, transport).poll_once()

    assert result.processed == 1
    assert len(transport.calls) == 2
    assert json.loads(transport.calls[1][1]["text"])["next_action"] == "resume_validation"


def test_worker_notification_is_fixed_best_effort_json(tmp_path: Path) -> None:
    transport = Transport(ok_sent())
    control = plane(tmp_path, transport)

    assert control.notify_worker_state(
        issue=132,
        request_id="codex-local-132-d6e5edb4a9385e4a",
        state="completed",
        detail="https://github.com/dragon0816/agentic-engineering-platform/pull/999",
    )

    message = json.loads(transport.calls[0][1]["text"])
    assert message["schema"] == "aep-telegram-worker-event/v1"
    assert message["state"] == "completed"
    assert message["hop"] == 0
    assert "command" not in message
