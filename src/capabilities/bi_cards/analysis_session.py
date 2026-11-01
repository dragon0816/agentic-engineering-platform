"""Analyses made in an AI conversation (BI T3).

`docs/phases/BI_TEST_AND_TOOLS.md` §5. A session of kind `analysis` (target
`analysis:new`, or `analysis:<slug>` to change a saved one) is kept in the
vault dataset's `staging.sqlite` like the other sessions. Each turn runs on the
Agent harness (`host_runtime.bi_analysis_agent`): the Agent queries the data
with read-only SQL or a guarded Python script and proposes an analysis, which
is run and checked before the person sees it. 「存成分析」 stages it as the
vault unit `analysis:<slug>`; it reaches others only by commit and push.

A turn may instead propose a dashboard (BI K1,
`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md`): several new analyses and
the Dashboard's order. 「套用」 stages them all and the new `meta:dashboard` in
one step; the vault's analyses not in the order are hidden, never deleted.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from capabilities.bi_cards import analyses, sessions
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import VAULT_PREFIX, BiStoreError, now

TARGET_PREFIX = "analysis:"
NEW = "new"
#: (context, turns so far, check of a proposal) -> (what came back, model
#: alias, tool calls made); supplied by Agent Web.
Asker = Callable[
    [str, list[dict[str, Any]], Callable[[dict[str, Any]], list[str]]],
    tuple[sessions.Asked, str, list[dict[str, Any]]],
]


def _vault_id(dataset: str) -> str:
    if not dataset.startswith(VAULT_PREFIX):
        raise BiStoreError("not_a_vault", "分析只在共用知識庫（vault）裡")
    return dataset[len(VAULT_PREFIX) :]


def _saved(workspace: Path, vault_id: str, slug: str) -> dict[str, Any] | None:
    found = analyses.listing(workspace, vault_id)["analyses"]
    return next((a for a in found if a["slug"] == slug), None)


def create_session(workspace: Path, dataset: str, target: str, actor: str) -> dict[str, Any]:
    vault_id = _vault_id(dataset)
    slug = target or NEW
    if slug != NEW and _saved(workspace, vault_id, slug) is None:
        raise BiStoreError("analysis_unknown", "沒有這個分析")
    return sessions.create(
        Staging(workspace, dataset), kind="analysis", target_ref=TARGET_PREFIX + slug, actor=actor
    )


def order_problem(order: Any, proposed: list[str], saved: list[str]) -> str | None:
    """A dashboard's order: distinct slugs, each proposed or already saved."""
    if not isinstance(order, list) or not order:
        return "order 必須是分析代號的清單（由上到下）"
    if not all(isinstance(s, str) and analyses.NAME_RE.match(s) for s in order):
        return "order 必須是分析代號的清單（由上到下）"
    if len(set(order)) != len(order):
        return "order 裡的分析代號重複了"
    if len(set(proposed)) != len(proposed):
        return "提出的分析代號重複了"
    unknown = [s for s in order if s not in proposed and s not in saved]
    if unknown:
        return "order 裡有知識庫沒有、也沒有提出的分析：" + "、".join(unknown)
    return None


def _dashboard_problems(dashboard: Any) -> list[str]:
    if not isinstance(dashboard, dict) or not isinstance(dashboard.get("analyses"), list):
        return ["`dashboard` must hold analyses and an order"]
    previews = dashboard.get("previews") or {}
    for proposed in dashboard["analyses"]:
        try:
            _, value = analyses.checked(proposed)
            columns = (previews.get(proposed.get("slug")) or {}).get("columns")
            analyses.checked_chart(value["chart"], columns)
        except (BiStoreError, AttributeError) as error:
            message = getattr(error, "message", "每個分析都要是 {title, slug, kind, code, chart}")
            return [
                f"分析「{proposed.get('slug') if isinstance(proposed, dict) else '?'}」：{message}"
            ]
    order = dashboard.get("order")
    if not isinstance(order, list) or not order:
        return ["order 必須是分析代號的清單（由上到下）"]
    return []


def check(answer: dict[str, Any]) -> list[str]:
    """A proposal must be a valid analysis whose chart names its result's columns."""
    if not isinstance(answer.get("reply"), str) or not answer["reply"].strip():
        return ["`reply` must be a non-empty text"]
    if answer.get("dashboard") is not None:
        return _dashboard_problems(answer["dashboard"])
    proposed = answer.get("analysis")
    if proposed is None:
        return []
    try:
        _, value = analyses.checked(proposed)
        columns = (answer.get("preview") or {}).get("columns")
        analyses.checked_chart(value["chart"], columns)
    except BiStoreError as error:
        return [error.message]
    return []


def session_turn(
    workspace: Path,
    dataset: str,
    session_id: str,
    *,
    message: Any,
    actor: str,
    asker: Asker | None,
) -> dict[str, Any]:
    vault_id = _vault_id(dataset)
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    session = sessions.load(staging, session_id, "analysis")
    text = sessions.check_message(message)
    if asker is None:
        raise BiStoreError(
            "harness_unavailable", "AI 分析要在 Agent Web 裡用（需要 Agent 的 harness）"
        )
    slug = session["target_ref"][len(TARGET_PREFIX) :]
    current = _saved(workspace, vault_id, slug) if slug != NEW else None
    db_path = analyses._db(workspace, vault_id)
    context = analyses.describe(db_path) + (
        "\n\nThe analysis to change (its slug stays):\n"
        + sessions.fenced(
            "Saved analysis:",
            json.dumps({k: v for k, v in current.items() if k != "unit"}, ensure_ascii=False),
        )
        if current
        else ""
    )
    turns = [*session["turns"], {"role": "user", "text": text}]
    asked, alias, tools = asker(context, turns, check)
    suggestion = None
    usable = asked.answer is not None and asked.failure is None and not check(asked.answer)
    if usable and asked.answer is not None and asked.answer.get("dashboard") is not None:
        suggestion = _dashboard_suggestion(asked.answer)
    elif usable and asked.answer is not None:
        proposed = asked.answer.get("analysis")
        suggestion = {
            "format": "aep.bi.analysis_suggestion/v1",
            "reply": asked.answer["reply"].strip(),
            "analysis": None
            if proposed is None
            else dict(analyses.checked(proposed)[1]) | {"slug": proposed["slug"]},
            "preview": asked.answer.get("preview"),
            "result": {"diff": [] if proposed is None else [{"key": "analysis"}]},
        }
    sent = {"model": alias, "harness": True, "tools": tools, "analysis": slug}
    return sessions.record(
        staging,
        session,
        message=text,
        actor=actor,
        alias=alias,
        asked=asked,
        sent=sent,
        suggestion=suggestion,
    )


def _dashboard_suggestion(answer: dict[str, Any]) -> dict[str, Any]:
    dashboard = answer["dashboard"]
    proposed = [
        dict(analyses.checked(item)[1]) | {"slug": item["slug"]} for item in dashboard["analyses"]
    ]
    return {
        "format": "aep.bi.analysis_suggestion/v1",
        "reply": answer["reply"].strip(),
        "analysis": None,
        "dashboard": {"analyses": proposed, "order": list(dashboard["order"])},
        "previews": dashboard.get("previews") or {},
        "result": {
            "diff": [{"key": analyses.PREFIX + a["slug"]} for a in proposed]
            + [{"key": analyses.DASHBOARD_UNIT}]
        },
    }


def _apply_dashboard(
    workspace: Path, vault_id: str, dashboard: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    """Stage every proposed analysis, then `meta:dashboard`: the order, and
    the vault's other analyses hidden. Checked before anything is staged."""
    proposed = list(dashboard.get("analyses") or [])
    order = list(dashboard.get("order") or [])
    saved = [a["slug"] for a in analyses.listing(workspace, vault_id)["analyses"]]
    fresh = [str(a.get("slug")) for a in proposed]
    problem = order_problem(order, fresh, saved)
    if problem:
        raise BiStoreError("dashboard_invalid", problem)
    taken = [s for s in fresh if s in saved]
    if taken:
        raise BiStoreError(
            "analysis_exists", "知識庫裡已經有這些分析，請請 AI 換一個代號：" + "、".join(taken)
        )
    units = [analyses.save(workspace, vault_id, item)["unit"] for item in proposed]
    every = [*saved, *fresh]
    hidden = [s for s in every if s not in order]
    listed = analyses.set_dashboard(workspace, vault_id, {"order": order, "hidden": hidden})
    return [*units, analyses.DASHBOARD_UNIT], listed


def apply_suggestion(
    workspace: Path, dataset: str, session_id: str, turn: Any, actor: str
) -> dict[str, Any]:
    """「存成分析」: stage the proposed analysis (run again on the data now);
    for a dashboard, 「套用」 stages its analyses and the order in one step."""
    vault_id = _vault_id(dataset)
    staging = Staging(workspace, dataset)
    session = sessions.load(staging, session_id, "analysis")
    found, index = sessions.assistant_turn(staging, session, turn)
    dashboard = found["suggestion"].get("dashboard")
    if dashboard is not None:
        units, listed = _apply_dashboard(workspace, vault_id, dashboard)
        sessions.mark_applied(staging, session, index, {"units": units, "at": now(), "by": actor})
        return {"session": session, "units": units, **listed}
    proposed = found["suggestion"].get("analysis")
    if proposed is None:
        raise BiStoreError("turn_unknown", "這一輪沒有可以存的分析")
    saved = analyses.save(workspace, vault_id, proposed)
    sessions.mark_applied(
        staging, session, index, {"unit": saved["unit"], "at": now(), "by": actor}
    )
    return {"session": session, **saved}
