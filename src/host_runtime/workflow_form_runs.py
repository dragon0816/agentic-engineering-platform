"""Durable state of an exact chat Workflow offer; execution stays in AgentWeb."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from host_runtime.contracts import WorkflowLaunchRequest


def update_form(web: Any, session: str, message_id: str, run: dict[str, Any]) -> None:
    """Caller holds the session record lock."""
    web.runtime.state.set_workflow_form_run(session, web.runtime.actor, message_id, run)


def launch(web: Any, item: WorkflowLaunchRequest) -> dict[str, Any]:
    """Claim a form before executing; a second click returns the saved outcome.

    Older clients without a message id bind to the newest matching offer.
    A retry must name the exact failed attempt the person saw.
    """
    if item.session_id is None:
        return dict(web._execute_workflow_launch(item))
    session = item.session_id
    if item.form_message_id is None:
        record = web.runtime.state.conversation(session, web.runtime.actor)
        if (
            record is not None
            and record.source != "telegram"
            and not any(
                m.workflow_form
                and m.workflow_form.get("workflow") == item.workflow.model_dump(mode="json")
                for m in record.messages
            )
        ):
            return dict(web._execute_workflow_launch(item))
    with web._record_lock(session):
        record = web.runtime.state.conversation(session, web.runtime.actor)
        if record is None or record.source == "telegram":
            raise ValueError("conversation unavailable")
        message = next(
            (
                m
                for m in reversed(record.messages)
                if m.workflow_form
                and (item.form_message_id is None or m.message_id == item.form_message_id)
                and m.workflow_form.get("workflow") == item.workflow.model_dump(mode="json")
            ),
            None,
        )
        if message is None:
            raise ValueError("Workflow form unavailable")
        form = message.workflow_form or {}
        previous = form.get("run")
        if previous is None:
            legacy = project(json.loads(record.model_dump_json()), web._workflow_form_owner)
            shown = next(m for m in legacy["messages"] if m["message_id"] == message.message_id)
            previous = (shown.get("workflow_form") or {}).get("run")
        if isinstance(previous, dict):
            interrupted = (
                previous.get("status") == "running"
                and previous.get("owner") != web._workflow_form_owner
            )
            retryable = previous.get("status") == "failed" or interrupted
            if not (
                retryable
                and item.retry_of == previous.get("key")
                and item.idempotency_key != previous.get("key")
            ):
                return {
                    "ok": previous.get("status") == "succeeded",
                    "replayed": True,
                    "answer": previous.get("answer")
                    or (
                        "The Workflow was interrupted. "
                        "Review its completed effects before retrying."
                        if interrupted
                        else "The Workflow is running."
                    ),
                    "status": "interrupted" if interrupted else previous.get("status"),
                }
        run = {
            "status": "running",
            "key": item.idempotency_key,
            "owner": web._workflow_form_owner,
            "started": datetime.now(UTC).isoformat(),
            "arguments": item.arguments,
        }
        update_form(web, session, message.message_id, run)
    try:
        result = web._execute_workflow_launch(item)
    except Exception:
        with web._record_lock(session):
            update_form(
                web,
                session,
                message.message_id,
                {
                    **run,
                    "status": "failed",
                    "answer": (
                        "The Workflow stopped unexpectedly. "
                        "Review its completed effects before retrying."
                    ),
                },
            )
        raise
    with web._record_lock(session):
        update_form(
            web,
            session,
            message.message_id,
            {
                **run,
                "status": "succeeded" if result["ok"] else "failed",
                "answer": result["answer"],
            },
        )
    return dict(result)


def _legacy_values(text: str, prefix: str) -> tuple[dict[str, Any], list[str]] | None:
    """Decode only the complete JSON-valued pairs the old recorder generated.

    Upload paths were deliberately hidden as (file), so never invent one.
    Truncated/unparseable records supply no automatic parameter recovery.
    """
    if len(text) >= 1500:  # Old recorder stored asked[:1500], even at a valid JSON boundary.
        return None
    rest = text[len(prefix) :]
    if not rest:
        return {}, []
    if not rest.startswith(": "):
        return None
    rest = rest[2:]
    values: dict[str, Any] = {}
    unavailable: list[str] = []
    decoder = json.JSONDecoder()
    while rest:
        name, equals, tail = rest.partition("=")
        if not equals or not name or any(c in name for c in " ,\n\r\t") or name in values:
            return None
        if tail.startswith("(file)"):
            unavailable.append(name)
            rest = tail[6:]
        else:
            try:
                values[name], end = decoder.raw_decode(tail)
            except ValueError:
                return None
            rest = tail[end:]
        if rest:
            if not rest.startswith(", ") or not rest[2:]:
                return None
            rest = rest[2:]
    return values, unavailable


def _legacy_runs(record: dict[str, Any]) -> None:
    """Recognize only the exact pair written by the old inline-form endpoint.

    Names with multiple exact identities are ambiguous and are left unchanged.
    No transcript text or persisted source record is rewritten.
    """
    identities: dict[str, set[str]] = {}
    pending: dict[str, dict[str, Any]] = {}
    for message in record.get("messages", []):
        form = message.get("workflow_form") or {}
        identity = form.get("workflow") or {}
        name = identity.get("name")
        if isinstance(name, str):
            identities.setdefault(name, set()).add(json.dumps(identity, sort_keys=True))
    messages = record.get("messages", [])
    for index, message in enumerate(messages):
        form = message.get("workflow_form") or {}
        name = (form.get("workflow") or {}).get("name")
        if isinstance(name, str) and len(identities.get(name, ())) == 1:
            pending[name] = form
        if message.get("role") != "user" or index + 1 >= len(messages):
            continue
        result = messages[index + 1]
        if result.get("role") != "assistant" or result.get("status") not in ("answered", "failed"):
            continue
        for name, offered in pending.items():
            prefix = "▶ Run " + name + " from the form"
            text = message.get("text", "")
            if text != prefix and not text.startswith(prefix + ": "):
                continue
            if "run" not in offered or str((offered.get("run") or {}).get("key", "")).startswith(
                "legacy-"
            ):
                offered["run"] = {
                    "status": "failed" if result["status"] == "failed" else "succeeded",
                    "key": "legacy-" + message["message_id"],
                    "answer": result["text"],
                }
                restored = _legacy_values(text, prefix)
                if restored is None:
                    offered["run"]["arguments_unavailable"] = True
                else:
                    offered["run"]["arguments"] = restored[0]
                    if restored[1]:
                        offered["run"]["unavailable_uploads"] = restored[1]


def project(record: dict[str, Any], owner: str) -> dict[str, Any]:
    """A prior process cannot still be running this form; never restart it."""
    _legacy_runs(record)
    for message in record.get("messages", []):
        form = message.get("workflow_form") or {}
        run = form.get("run")
        if isinstance(run, dict):
            if run.get("status") == "running" and run.get("owner") != owner:
                run["status"] = "interrupted"
                run["answer"] = (
                    "The Workflow was interrupted. Review its completed effects before retrying."
                )
            run.pop("owner", None)
    return record
