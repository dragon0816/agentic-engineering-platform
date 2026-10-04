"""Agent Web's schedule routes, without HTTP.

`host_runtime.web` applies its usual guards first -- loopback address,
loopback `Host` header and the per-run Bearer token -- and these routes add a
refusal of any request carrying a non-loopback `Origin`. The browser never
supplies the owner, approver, policy reference or approval time: those come
from the running Host. Approving a run and resolving a claim are explicit
actions on one exact occurrence; nothing here executes a target except
through `ScheduleControl.approve`, which re-checks every grant.
"""

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ValidationError

from host_runtime.schedule_control import (
    ScheduleControl,
    ScheduleControlError,
    ScheduleCreateRequest,
    ScheduleGrantRequest,
    ScheduleResolveRequest,
    ScheduleRunDecisionRequest,
    ScheduleSelectRequest,
)

GET_PATHS = ("/api/schedules", "/api/schedules/history")
POST_PATHS = (
    "/api/schedules/create",
    "/api/schedules/pause",
    "/api/schedules/resume",
    "/api/schedules/grant",
    "/api/schedules/revoke",
    "/api/schedules/approve",
    "/api/schedules/deny",
    "/api/schedules/resolve",
)

_STATUS = {
    "unknown": 404,
    "owner_mismatch": 403,
    "not_admitted": 403,
    "definition_owner_mismatch": 403,
    "unavailable": 503,
    "commit_unknown": 503,
}


def is_schedule_path(path: str) -> bool:
    return path in GET_PATHS or path in POST_PATHS


def origin_allowed(origin: str | None) -> bool:
    """No Origin (a same-origin GET or a non-browser client) or a loopback one."""
    if origin is None:
        return True
    host = urlparse(origin).hostname
    return host in ("127.0.0.1", "localhost", "::1")


def _run(item: BaseModel) -> dict[str, Any]:
    return item.model_dump(mode="json")


def handle(
    control: ScheduleControl,
    method: str,
    path: str,
    query: dict[str, list[str]],
    body: object,
    *,
    loop_status: dict[str, Any] | None,
) -> tuple[int, dict[str, Any]]:
    try:
        if method == "GET" and path == "/api/schedules":
            return 200, {
                "ok": True,
                **control.overview(),
                "targets": control.targets(),
                "resident_loop": loop_status or {"running": False},
            }
        if method == "GET" and path == "/api/schedules/history":
            schedule_id = (query.get("schedule_id") or [""])[0]
            selected = ScheduleSelectRequest(schedule_id=schedule_id)
            return 200, {
                "ok": True,
                "schedule_id": selected.schedule_id,
                "runs": [_run(run) for run in control.history(selected.schedule_id)],
                "decisions": control.decisions(selected.schedule_id),
            }
        if method != "POST" or path not in POST_PATHS:
            return 404, {"error": "no such page"}
        if path == "/api/schedules/create":
            created = control.create_from_request(ScheduleCreateRequest.model_validate(body))
            return 201, {"ok": True, "schedule": _run(created)}
        if path in ("/api/schedules/pause", "/api/schedules/resume"):
            selected = ScheduleSelectRequest.model_validate(body)
            record = control.set_active(
                selected.schedule_id, active=path.endswith("/resume")
            )
            return 200, {"ok": True, "schedule": _run(record)}
        if path == "/api/schedules/grant":
            granted = ScheduleGrantRequest.model_validate(body)
            grant = control.grant(
                granted.schedule_id,
                max_side_effect=granted.max_side_effect,
                expires_at=granted.expires_at,
            )
            return 200, {"ok": True, "grant": _run(grant)}
        if path == "/api/schedules/revoke":
            selected = ScheduleSelectRequest.model_validate(body)
            return 200, {"ok": True, "grant": _run(control.revoke(selected.schedule_id))}
        if path in ("/api/schedules/approve", "/api/schedules/deny"):
            decision = ScheduleRunDecisionRequest.model_validate(body)
            if path.endswith("/approve"):
                run = control.approve(decision.idempotency_key, note=decision.note)
            else:
                run = control.deny(decision.idempotency_key, note=decision.note)
            return 200, {"ok": True, "run": _run(run)}
        resolution = ScheduleResolveRequest.model_validate(body)
        if not resolution.confirm:
            return 400, {"ok": False, "code": "confirmation_required"}
        run = control.resolve(
            resolution.idempotency_key, outcome=resolution.outcome, note=resolution.note
        )
        return 200, {"ok": True, "run": _run(run)}
    except ScheduleControlError as error:
        return _STATUS.get(error.code, 409), {"ok": False, "code": error.code}
    except (ValidationError, ValueError, TypeError):
        return 400, {"ok": False, "code": "invalid_request"}
