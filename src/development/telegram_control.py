"""Bounded Telegram control channel for the trusted local Codex worker.

GitHub remains the durable queue and source of truth for implementation work.
Telegram provides owner status reads, best-effort worker notifications, and a
fixed coordination protocol between the current validation and coding agents.
No Telegram message can supply a command, change a label, start Codex, or merge
a PR. Mechanism problems are retained as bounded data for coding-agent review.
Known mechanism codes may receive one closed deterministic guidance message;
unknown codes remain review-only.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Protocol, Self, cast

from pydantic import Field, JsonValue, field_validator, model_validator

from common.assets import REDACTED, SECRET_PATTERN, SecretRef, reject_embedded_secrets
from common.base import Contract, Text
from common.execution import Failure
from models.credentials import CredentialMisconfigured, CredentialResolver, EnvironmentCredentials
from models.wire import (
    Transport,
    UrllibTransport,
    close_quietly,
    describe,
    status_failure,
    transport_failure,
)

TELEGRAM_CONTROL_CREDENTIAL = "local_codex_telegram"
TELEGRAM_ENVIRONMENT_NAMES = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OWNER_USER_ID",
    "TELEGRAM_HERMES_BOT_ID",
    "TELEGRAM_CONTROL_CHAT_ID",
)
MAX_MESSAGE_CHARS = 4000
MAX_EVENT_IDS = 200
MAX_UPDATES_PER_POLL = 25
STATUS_COMMAND = re.compile(r"^/status(?:@[A-Za-z0-9_]+)?(?:\s+#?([1-9][0-9]*))?\s*$")

WorkerState = Literal["running", "waiting_evidence", "failed", "completed"]
ValidationEventName = Literal[
    "evidence_posted",
    "validation_passed",
    "validation_failed",
    "blocked",
    "mechanism_blocked",
    "mechanism_update",
    "mechanism_resolved",
]
MechanismEventName = Literal["mechanism_blocked", "mechanism_update", "mechanism_resolved"]
MechanismGuidanceAction = Literal["provision_profile_model_routing"]
MechanismGuidanceNextAction = Literal["retry_same_validation_request"]


def _scrub(value: str) -> str:
    return SECRET_PATTERN.sub(REDACTED, value)


class GitHubStatusReader(Protocol):
    """The read-only GitHub surface allowed to Telegram."""

    def queued_issues(self) -> tuple[int, ...]: ...

    def issue_summary(self, issue: int) -> dict[str, Any]: ...


class TelegramControlConfig(Contract):
    """Non-secret identity binding for one local worker control bot."""

    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    credential: SecretRef
    owner_user_id: int = Field(gt=0, strict=True)
    validation_bot_id: int = Field(gt=0, strict=True)
    control_chat_id: int = Field(strict=True)
    poll_timeout_seconds: int = Field(default=0, ge=0, le=10, strict=True)
    api_base: Text = "https://api.telegram.org"

    @field_validator("control_chat_id")
    @classmethod
    def nonzero_chat(cls, value: int) -> int:
        if value == 0:
            raise ValueError("the Telegram control chat id cannot be zero")
        return value

    @field_validator("api_base")
    @classmethod
    def checked_api_base(cls, value: str) -> str:
        value = value.rstrip("/")
        if not value.startswith("https://") or "/bot" in value:
            raise ValueError("api_base is the HTTPS Bot API origin without a token")
        return value

    @model_validator(mode="after")
    def distinct_identities_without_secrets(self) -> Self:
        if self.owner_user_id == self.validation_bot_id:
            raise ValueError("owner and validation bot must be different identities")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class MechanismProblem(Contract):
    """Bounded mechanism evidence, never instructions for a subprocess."""

    code: str = Field(min_length=1, max_length=120, pattern=r"^[A-Z0-9_]+$")
    summary: str = Field(min_length=1, max_length=2_000)
    expected: str = Field(min_length=1, max_length=4_000)
    observed: str = Field(min_length=1, max_length=4_000)
    evidence_refs: tuple[str, ...] = Field(default=(), max_length=10)
    requested_response: Literal["diagnosis", "coordination", "resume_decision"]

    @field_validator("evidence_refs")
    @classmethod
    def bounded_references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() or len(item) > 2_000 for item in value):
            raise ValueError("mechanism evidence references must be 1..2000 characters")
        return value

    @model_validator(mode="after")
    def no_embedded_secret(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class ValidationControlEvent(Contract):
    """One non-authoritative notification sent by the validation bot."""

    schema_: Literal["aep-agent-coordination/v1"] = Field(alias="schema")
    producer: Literal["validation-agent"]
    event_id: str = Field(min_length=8, max_length=160, pattern=r"^[A-Za-z0-9._-]+$")
    event: ValidationEventName
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    issue: int | None = Field(default=None, gt=0, strict=True)
    request_id: str = Field(min_length=8, max_length=160, pattern=r"^[A-Za-z0-9._-]+$")
    target_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    mechanism: MechanismProblem | None = None
    hop: Literal[0]

    @model_validator(mode="after")
    def event_has_only_its_required_evidence(self) -> Self:
        mechanism_event = self.event.startswith("mechanism_")
        if mechanism_event and self.mechanism is None:
            raise ValueError("mechanism events require mechanism details")
        if not mechanism_event and self.mechanism is not None:
            raise ValueError("only mechanism events may include mechanism details")
        if not mechanism_event and self.issue is None:
            raise ValueError("validation result events require a GitHub Issue")
        return self


class MechanismGuidance(Contract):
    """One closed Coding Agent response for an allowlisted mechanism code."""

    schema_: Literal["aep-agent-coordination-guidance/v1"] = Field(alias="schema")
    producer: Literal["coding-agent"]
    event_id: str = Field(min_length=8, max_length=160, pattern=r"^[A-Za-z0-9._-]+$")
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    issue: int | None = Field(default=None, gt=0, strict=True)
    request_id: str = Field(min_length=8, max_length=160, pattern=r"^[A-Za-z0-9._-]+$")
    target_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    mechanism_code: Literal["MODEL_ROUTING_NOT_CONFIGURED"]
    action: MechanismGuidanceAction
    next_action: MechanismGuidanceNextAction
    hop: Literal[1]


class TelegramControlPollResult(Contract):
    processed: int = Field(default=0, ge=0, strict=True)
    failure: Failure | None = None
    next_offset: int | None = Field(default=None, ge=0, strict=True)


class _MechanismRecord(Contract):
    event_id: str
    event: MechanismEventName = "mechanism_blocked"
    request_id: str
    target_sha: str
    issue: int | None = None
    problem: MechanismProblem


class _State(Contract):
    next_offset: int | None = Field(default=None, ge=0, strict=True)
    event_ids: tuple[str, ...] = Field(default=(), max_length=MAX_EVENT_IDS)
    guidance_event_ids: tuple[str, ...] = Field(default=(), max_length=MAX_EVENT_IDS)
    mechanism_events: tuple[_MechanismRecord, ...] = Field(default=(), max_length=20)


class _Update:
    def __init__(
        self,
        update_id: int,
        chat_id: int,
        sender_id: int,
        is_bot: bool,
        text: str,
    ) -> None:
        self.update_id = update_id
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.is_bot = is_bot
        self.text = text


def _parse_update(raw: object) -> _Update | None:
    if not isinstance(raw, dict) or type(raw.get("update_id")) is not int:
        return None
    message = raw.get("message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat")
    sender = message.get("from")
    text = message.get("text")
    if not isinstance(chat, dict) or type(chat.get("id")) is not int:
        return None
    if not isinstance(sender, dict) or type(sender.get("id")) is not int:
        return None
    if type(sender.get("is_bot")) is not bool or not isinstance(text, str):
        return None
    return _Update(raw["update_id"], chat["id"], sender["id"], sender["is_bot"], text)


def config_from_environment(
    repository: str, environ: Mapping[str, str]
) -> TelegramControlConfig | None:
    """Build the non-secret binding only when all four settings are present.

    An entirely absent configuration disables Telegram.  A partial one is an
    operator error; the worker entry point records that Telegram is disabled
    and continues polling GitHub.
    """

    values = {name: str(environ.get(name, "")).strip() for name in TELEGRAM_ENVIRONMENT_NAMES}
    present = {name for name, value in values.items() if value}
    if not present:
        return None
    if present != set(TELEGRAM_ENVIRONMENT_NAMES):
        raise ValueError("Telegram control requires all four TELEGRAM_* settings")
    try:
        owner = int(values["TELEGRAM_OWNER_USER_ID"])
        validation = int(values["TELEGRAM_HERMES_BOT_ID"])
        chat = int(values["TELEGRAM_CONTROL_CHAT_ID"])
    except ValueError as error:
        raise ValueError("Telegram owner, validation bot and chat ids must be integers") from error
    return TelegramControlConfig(
        repository=repository,
        credential=SecretRef(name=TELEGRAM_CONTROL_CREDENTIAL),
        owner_user_id=owner,
        validation_bot_id=validation,
        control_chat_id=chat,
    )


def environment_resolver(environ: Mapping[str, str]) -> EnvironmentCredentials:
    return EnvironmentCredentials(
        {TELEGRAM_CONTROL_CREDENTIAL: "TELEGRAM_BOT_TOKEN"}, environ=environ
    )


class TelegramControlPlane:
    """Outbound-only Telegram observer for the local development worker."""

    def __init__(
        self,
        config: TelegramControlConfig,
        resolver: CredentialResolver,
        github: GitHubStatusReader,
        *,
        state_path: Path,
        transport: Transport | None = None,
    ) -> None:
        self.config = TelegramControlConfig.model_validate(config)
        self._resolver = resolver
        self._github = github
        self._state_path = state_path.resolve()
        self._transport = transport if transport is not None else UrllibTransport()

    def _load_state(self) -> _State:
        if not self._state_path.exists():
            return _State()
        return _State.model_validate_json(self._state_path.read_text(encoding="utf-8"))

    def _save_state(self, state: _State) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self._state_path)

    def _call(self, method: str, payload: Mapping[str, JsonValue]) -> tuple[int, bytes]:
        token = self._resolver.resolve(self.config.credential)
        reply = self._transport.send(
            f"{self.config.api_base}/bot{token}/{method}",
            json.dumps(dict(payload)).encode("utf-8"),
            {"Content-Type": "application/json"},
            float(self.config.poll_timeout_seconds + 10),
        )
        try:
            body = b"".join(reply.chunks())
        finally:
            close_quietly(reply)
        return reply.status, body

    def _send(self, text: str) -> bool:
        safe = _scrub(text)[:MAX_MESSAGE_CHARS]
        try:
            status, _ = self._call(
                "sendMessage", {"chat_id": self.config.control_chat_id, "text": safe}
            )
        except Exception:  # noqa: BLE001 - notifications are deliberately best effort
            return False
        return status == 200

    def notify_worker_state(
        self,
        *,
        issue: int,
        request_id: str,
        state: WorkerState,
        detail: str | None = None,
    ) -> bool:
        """Publish a bounded state event. It contains no executable action."""

        payload: dict[str, JsonValue] = {
            "schema": "aep-telegram-worker-event/v1",
            "producer": "local-codex-worker",
            "repository": self.config.repository,
            "issue": issue,
            "request_id": request_id[:160],
            "state": state,
            "hop": 0,
        }
        if detail:
            payload["detail"] = _scrub(detail)[:1000]
        return self._send(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    def _mechanism_guidance(self, record: _MechanismRecord) -> MechanismGuidance | None:
        if (
            record.event != "mechanism_blocked"
            or record.problem.code != "MODEL_ROUTING_NOT_CONFIGURED"
        ):
            return None
        return MechanismGuidance(
            schema="aep-agent-coordination-guidance/v1",
            producer="coding-agent",
            event_id=record.event_id,
            repository=self.config.repository,
            issue=record.issue,
            request_id=record.request_id,
            target_sha=record.target_sha,
            mechanism_code="MODEL_ROUTING_NOT_CONFIGURED",
            action="provision_profile_model_routing",
            next_action="retry_same_validation_request",
            hop=1,
        )

    def poll_once(self) -> TelegramControlPollResult:
        try:
            state = self._load_state()
        except Exception as error:  # noqa: BLE001 - state faults cannot stop GitHub polling
            return TelegramControlPollResult(
                failure=Failure(code="telegram_control_state_invalid", message=describe(error))
            )
        payload: dict[str, JsonValue] = {
            "timeout": self.config.poll_timeout_seconds,
            "limit": MAX_UPDATES_PER_POLL,
            "allowed_updates": ["message"],
        }
        if state.next_offset is not None:
            payload["offset"] = state.next_offset
        try:
            status, body = self._call("getUpdates", payload)
        except CredentialMisconfigured as error:
            return TelegramControlPollResult(
                failure=Failure(
                    code="telegram_control_credential_unavailable", message=describe(error)
                )
            )
        except Exception as error:  # noqa: BLE001 - transport failures are typed
            return TelegramControlPollResult(
                failure=transport_failure(error, prefix="telegram_control")
            )
        if status == 409:
            return TelegramControlPollResult(
                failure=Failure(
                    code="telegram_control_conflict",
                    message="another process is polling the Local Codex control bot",
                )
            )
        if status != 200:
            return TelegramControlPollResult(
                failure=status_failure(status, body, prefix="telegram_control")
            )
        try:
            response = json.loads(body)
        except ValueError:
            response = None
        if not isinstance(response, dict) or response.get("ok") is not True:
            return TelegramControlPollResult(
                failure=Failure(
                    code="telegram_control_bad_reply", message="Bot API reply was not ok"
                )
            )
        items = response.get("result")
        if not isinstance(items, list):
            return TelegramControlPollResult(
                failure=Failure(
                    code="telegram_control_bad_reply", message="Bot API reply had no result"
                )
            )

        highest = state.next_offset
        processed = 0
        event_ids = list(state.event_ids)
        guidance_event_ids = list(state.guidance_event_ids)
        mechanism_events = list(state.mechanism_events)
        for raw in items[:MAX_UPDATES_PER_POLL]:
            if isinstance(raw, dict) and type(raw.get("update_id")) is int:
                highest = max(highest or 0, raw["update_id"] + 1)
            item = _parse_update(raw)
            if item is None or item.chat_id != self.config.control_chat_id:
                continue
            if item.sender_id == self.config.owner_user_id and not item.is_bot:
                reply = self._owner_reply(item.text)
                if reply is not None:
                    self._send(reply)
                    processed += 1
                continue
            if item.sender_id != self.config.validation_bot_id or not item.is_bot:
                continue
            parsed = self._validation_event(item.text)
            if parsed is None or parsed.event_id in event_ids:
                continue
            snapshot: dict[str, Any] | None = None
            if parsed.issue is not None:
                try:
                    snapshot = self._github.issue_summary(parsed.issue)
                except Exception:  # noqa: BLE001 - no ack when GitHub cannot verify a reference
                    continue
            event_ids.append(parsed.event_id)
            event_ids = event_ids[-MAX_EVENT_IDS:]
            if parsed.mechanism is not None:
                mechanism_events.append(
                    _MechanismRecord(
                        event_id=parsed.event_id,
                        event=cast(MechanismEventName, parsed.event),
                        request_id=parsed.request_id,
                        target_sha=parsed.target_sha,
                        issue=parsed.issue,
                        problem=parsed.mechanism,
                    )
                )
                mechanism_events = mechanism_events[-20:]
            labels = (
                sorted(
                    str(value.get("name"))
                    for value in snapshot.get("labels", [])
                    if isinstance(value, dict) and value.get("name")
                )
                if snapshot is not None
                else []
            )
            next_action = {
                "mechanism_blocked": "coding_agent_review_required",
                "mechanism_update": "continue_coordination",
                "mechanism_resolved": "resume_validation",
            }.get(parsed.event, "github_state_observed")
            ack = {
                "schema": "aep-agent-coordination-ack/v1",
                "producer": "coding-agent",
                "event_id": parsed.event_id,
                "repository": self.config.repository,
                "issue": parsed.issue,
                "request_id": parsed.request_id,
                "outcome": "observed",
                "github_state": (
                    str(snapshot.get("state") or "UNKNOWN")
                    if snapshot is not None
                    else "NOT_APPLICABLE"
                ),
                "github_labels": labels,
                "next_action": next_action,
                "hop": 1,
            }
            self._send(json.dumps(ack, ensure_ascii=False, separators=(",", ":")))
            processed += 1

        for record in mechanism_events:
            if record.event_id in guidance_event_ids:
                continue
            guidance = self._mechanism_guidance(record)
            if guidance is None:
                continue
            sent = self._send(guidance.model_dump_json(by_alias=True))
            if not sent:
                continue
            guidance_event_ids.append(record.event_id)
            guidance_event_ids = guidance_event_ids[-MAX_EVENT_IDS:]
            processed += 1

        next_state = _State(
            next_offset=highest,
            event_ids=tuple(event_ids),
            guidance_event_ids=tuple(guidance_event_ids),
            mechanism_events=tuple(mechanism_events),
        )
        try:
            self._save_state(next_state)
        except Exception as error:  # noqa: BLE001 - caller sees typed state failure
            return TelegramControlPollResult(
                processed=processed,
                failure=Failure(
                    code="telegram_control_cursor_unconfirmed", message=describe(error)
                ),
                next_offset=state.next_offset,
            )
        return TelegramControlPollResult(processed=processed, next_offset=highest)

    def _owner_reply(self, text: str) -> str | None:
        match = STATUS_COMMAND.fullmatch(text.strip())
        if match is None:
            return "Only /status or /status <issue-number> is accepted by this control bot."
        issue_text = match.group(1)
        if issue_text is None:
            queued = self._github.queued_issues()
            listed = ", ".join(f"#{item}" for item in queued) if queued else "none"
            try:
                coordination_state = self._load_state()
                latest = (
                    coordination_state.mechanism_events[-1].problem.code
                    if coordination_state.mechanism_events
                    else "none"
                )
            except Exception:  # noqa: BLE001 - status remains useful without local coordination state
                latest = "unavailable"
            return (
                f"Coding worker is available. Queued GitHub Issues: {listed}. "
                f"Latest mechanism event: {latest}."
            )
        issue = int(issue_text)
        try:
            snapshot = self._github.issue_summary(issue)
        except Exception:  # noqa: BLE001 - do not expose GitHub/tool details to Telegram
            return f"Issue #{issue} could not be read from GitHub."
        labels = sorted(
            str(value.get("name"))
            for value in snapshot.get("labels", [])
            if isinstance(value, dict) and value.get("name")
        )
        label_text = ", ".join(labels) if labels else "none"
        title = _scrub(str(snapshot.get("title") or ""))[:500]
        issue_state = _scrub(str(snapshot.get("state") or "UNKNOWN"))[:30]
        return f"Issue #{issue} [{issue_state}] {title}\nLabels: {label_text}"

    def _validation_event(self, text: str) -> ValidationControlEvent | None:
        if len(text) > 4000:
            return None
        try:
            raw = json.loads(text)
            event = ValidationControlEvent.model_validate(raw)
        except (ValueError, TypeError):
            return None
        if event.repository != self.config.repository:
            return None
        return event
