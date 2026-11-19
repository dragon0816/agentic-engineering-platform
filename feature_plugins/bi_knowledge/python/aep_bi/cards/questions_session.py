"""Benchmark questions from an AI conversation (`docs/phases/BI_BUILD_FLOW.md` §7).

A session of kind `questions` (target `questions:<set>`) is kept in the vault
dataset's `staging.sqlite` like the other sessions. Each turn runs on the Agent
harness (`aep_bi.host.bi_questions_agent`): the Agent reads the cards and the
saved analyses and proposes questions with their `must` and `must_not` terms.
Code checks a proposal and sends problems back: a question is graded, is not a
repeat, and every `must` term is found in the working cards or the saved analyses'
results (a term nothing supports would be a question nothing can pass).
「加入測試題」 stages the ticked questions as `check:question:<set>/<slug>` units;
they reach others only by commit and push.
"""

from __future__ import annotations

import copy
import json
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from datetime import date
from pathlib import Path
from typing import Any

from aep_bi.cards import analyses, board, homes, sessions, vault_checks
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import VAULT_PREFIX, BiStore, BiStoreError, now

TARGET_PREFIX = "questions:"
MAX_QUESTIONS = 20
#: The default pack's 31 Python analyses take about 2 s each, one process each.
RUN_WORKERS = 4
#: (context, turns so far, check of a proposal) -> (what came back, model alias,
#: tool calls made); supplied by Agent Web.
Asker = Callable[
    [str, list[dict[str, Any]], Callable[[dict[str, Any]], list[str]]],
    tuple[sessions.Asked, str, list[dict[str, Any]]],
]


def _vault_id(dataset: str) -> str:
    if not dataset.startswith(VAULT_PREFIX):
        raise BiStoreError("not_a_vault", "測試題只在共用知識庫（vault）裡")
    return dataset[len(VAULT_PREFIX) :]


def create_session(workspace: Path, dataset: str, target: str, actor: str) -> dict[str, Any]:
    _vault_id(dataset)
    group = target or vault_checks.DEFAULT_SET
    if not vault_checks.NAME_RE.match(group):
        raise BiStoreError("question_invalid", "題組只能用小寫英數字與 -")
    return sessions.create(
        Staging(workspace, dataset), kind="questions", target_ref=TARGET_PREFIX + group, actor=actor
    )


#: The last results per vault and working domain with what they were read from: a turn reads
#: them for the model and again for the check of its proposal.
_LAST_RESULTS: dict[tuple[str, str, str], tuple[Any, list[dict[str, Any]]]] = {}
#: The working domain and the session of the turn under way, for the Agent's tools, which run
#: in the turn's context (`asyncio.to_thread` copies it).
_HOME: ContextVar[str | None] = ContextVar("bi_questions_home", default=None)
_SESSION: ContextVar[str | None] = ContextVar("bi_questions_session", default=None)
#: What each turn under way is doing, for the page to show beside 送出 (AGENTS.md 23).
_PROGRESS: dict[str, dict[str, Any]] = {}
_PROGRESS_LOCK = threading.Lock()


def _report(**state: Any) -> None:
    session_id = _SESSION.get()
    if session_id is None:
        return
    with _PROGRESS_LOCK:
        if session_id in _PROGRESS:
            _PROGRESS[session_id].update(state)


def progress(session_id: str) -> dict[str, Any] | None:
    """What the turn of `session_id` is doing now: `step` (`ai` or `check`), the analyses
    checked of how many, and seconds since it started; None when no turn is under way."""
    with _PROGRESS_LOCK:
        found = _PROGRESS.get(session_id)
        if found is None:
            return None
        return {**found, "seconds": round(time.monotonic() - found["since"], 1)}


def saved_results(workspace: Path, vault_id: str, home: str | None = None) -> list[dict[str, Any]]:
    """The saved analyses with their results on the working data; one that cannot
    run reports why and is left out of what supports a term. In a working domain, only its
    Dashboard's analyses, run as its Dashboard runs them (its domain and folder): the rest
    say nothing of its questions (owner 2026-11-19). Results come from the Dashboard's cache
    when it drew them, and are run again only when the analyses or the data changed."""
    home = home if home is not None else _HOME.get()
    listed = analyses.listing(workspace, vault_id, home)
    saved = listed["analyses"]
    if home:
        saved = [a for a in saved if a["slug"] in listed["order"]]
    db = analyses._db(workspace, vault_id)
    data = db.stat()
    stamp = (data.st_mtime_ns, data.st_size, json.dumps(saved, sort_keys=True, default=str))
    place = (str(workspace), vault_id, home or "")
    known = _LAST_RESULTS.get(place)
    if known is not None and known[0] == stamp:
        return copy.deepcopy(known[1])
    registry = analyses._registry(workspace, vault_id)
    domain = (analyses.home_domain(registry, home) or home.rpartition("/")[2]) if home else None
    today = date.today().isoformat()
    total, done = len(saved), [0]
    lock = threading.Lock()
    _report(step="check", done=0, total=total)

    def one(item: dict[str, Any]) -> dict[str, Any]:
        entry = {key: item.get(key) for key in ("slug", "title", "question")}
        try:
            declared = item.get("params") or {}
            given = {"domain": domain} if domain and "domain" in declared else {}
            values = analyses.resolve_params(
                declared, given, registry, today=today, domains=listed["domains"]
            )
            values = analyses.folder_filter(item, values, home, registry)
            entry["table"] = board._run(db, item, values)
        except BiStoreError as error:
            entry["error"] = error.message
        with lock:
            done[0] += 1
            _report(done=done[0], name=item.get("title"))
        return entry

    with ThreadPoolExecutor(max_workers=RUN_WORKERS) as pool:
        found = list(pool.map(one, saved))
    _report(step="ai")
    _LAST_RESULTS[place] = (stamp, copy.deepcopy(found))
    return found


def _corpus(workspace: Path, dataset: str, home: str | None = None) -> str:
    """What a `must` term may come from: the working cards and analysis results (in a
    working domain, its Dashboard's)."""
    store = BiStore(workspace, dataset)
    fields = store.all_fields() if store.exists else {}
    pieces: list[Any] = []
    for card in store.card_rows() if store.exists else []:
        pieces.append(card["name"])
        pieces.extend(item["value"] for item in fields.get(card["id"], {}).values())
    pieces.extend(
        entry.get("table", {}).get("rows")
        for entry in saved_results(workspace, _vault_id(dataset), home)
    )
    return json.dumps(pieces, ensure_ascii=False, default=str).casefold()


def check_proposal(
    answer: dict[str, Any], group: str, existing: set[str], corpus: Callable[[], str]
) -> list[str]:
    """Why this proposal cannot be shown; empty when it can."""
    if not isinstance(answer.get("reply"), str) or not answer["reply"].strip():
        return ["`reply` must be a non-empty text"]
    given = answer.get("questions") or []
    if not isinstance(given, list) or not all(isinstance(q, dict) for q in given):
        return ["`questions` must be a list of {question, must, must_not}"]
    if len(given) > MAX_QUESTIONS:
        return [f"at most {MAX_QUESTIONS} questions in one proposal"]
    problems: list[str] = []
    seen = set(existing)
    text = corpus() if given else ""
    for number, item in enumerate(given):
        at = f"questions[{number}]"
        try:
            unit, value = vault_checks.checked_question({**item, "set": group})
        except BiStoreError as error:
            problems.append(f"{at}: {error.message}")
            continue
        if not value["must"] and not value["must_not"]:
            problems.append(
                f"{at}: give at least one must or must_not term, or it cannot be graded"
            )
        if unit in seen:
            problems.append(f"{at}: this question is already in the set")
        seen.add(unit)
        problems.extend(
            f"{at}: the must term {term!r} is in no card and no saved analysis's result"
            for term in value["must"]
            if term.casefold() not in text
        )
    return problems


def session_turn(
    workspace: Path,
    dataset: str,
    session_id: str,
    *,
    message: Any,
    actor: str,
    asker: Asker | None,
    home: Any = None,
) -> dict[str, Any]:
    vault_id = _vault_id(dataset)
    home = str(home) if home else None
    if home is not None and homes.home_problem(home):
        raise BiStoreError("home_invalid", "領域必須是應用資料夾或 library 的項目")
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    session = sessions.load(staging, session_id, "questions")
    text = sessions.check_message(message)
    if asker is None:
        raise BiStoreError(
            "harness_unavailable", "AI 出題要在 Agent Web 裡用（需要 Agent 的 harness）"
        )
    group = session["target_ref"][len(TARGET_PREFIX) :]
    listed = vault_checks.listing(workspace, vault_id)["questions"]
    existing = {q["unit"] for q in listed}
    known: list[str] = []

    def corpus() -> str:
        if not known:
            known.append(_corpus(workspace, dataset, home))
        return known[0]

    def check(answer: dict[str, Any]) -> list[str]:
        return check_proposal(answer, group, existing, corpus)

    context = (
        f"{analyses.describe(analyses._db(workspace, vault_id))}\n\n"
        f"The question set: {group}\n"
        "Questions it already has (do not repeat them):\n"
        + sessions.fenced(
            "Saved questions:",
            json.dumps(
                [{k: q[k] for k in ("question", "must", "must_not")} for q in listed],
                ensure_ascii=False,
            ),
        )
    )
    turns = [*session["turns"], {"role": "user", "text": text}]
    with _PROGRESS_LOCK:
        _PROGRESS[session_id] = {"step": "ai", "since": time.monotonic(), "done": 0, "total": 0}
    home_set, session_set = _HOME.set(home), _SESSION.set(session_id)
    try:
        asked, alias, tools = asker(context, turns, check)
    finally:
        _HOME.reset(home_set)
        _SESSION.reset(session_set)
        with _PROGRESS_LOCK:
            _PROGRESS.pop(session_id, None)
    suggestion = None
    if asked.answer is not None and asked.failure is None and not check(asked.answer):
        chosen = []
        for item in asked.answer.get("questions") or []:
            unit, value = vault_checks.checked_question({**item, "set": group})
            chosen.append({"unit": unit, **value})
        suggestion = {
            "format": "aep.bi.questions_suggestion/v1",
            "reply": asked.answer["reply"].strip(),
            "questions": chosen,
            "reasons": sessions.strings(asked.answer.get("reasons")),
            "result": {"diff": [{"key": q["unit"]} for q in chosen]},
        }
    sent = {"model": alias, "harness": True, "tools": tools, "question_set": group}
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


def apply_suggestion(
    workspace: Path,
    dataset: str,
    session_id: str,
    turn: Any,
    picks: Any,
    actor: str,
    home: Any = None,
) -> dict[str, Any]:
    """「加入測試題」: stage the questions the person ticked (by index), of the working
    domain `home` if any; nothing else changes, and they reach others only by commit and push."""
    vault_id = _vault_id(dataset)
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    session = sessions.load(staging, session_id, "questions")
    found, index = sessions.assistant_turn(staging, session, turn)
    proposed = found["suggestion"].get("questions") or []
    if not isinstance(picks, list) or not all(
        isinstance(p, int) and not isinstance(p, bool) and 0 <= p < len(proposed) for p in picks
    ):
        raise BiStoreError("picks_invalid", "picks 必須是這一輪題目的編號清單")
    if not picks:
        raise BiStoreError("picks_empty", "請至少勾選一題")
    group = session["target_ref"][len(TARGET_PREFIX) :]
    # One write of the working copy for all of them (one per question took a second or
    # more on a real vault), and marked applied only once they are staged.
    saved = vault_checks.save_questions(
        workspace,
        vault_id,
        [
            {
                "question": proposed[pick]["question"],
                "must": proposed[pick]["must"],
                "must_not": proposed[pick]["must_not"],
                "set": group,
                "slug": proposed[pick]["unit"].rpartition("/")[2],
                "home": home,
            }
            for pick in dict.fromkeys(picks)
        ],
    )
    units = saved.pop("units")
    listed = saved
    sessions.mark_applied(staging, session, index, {"units": units, "at": now(), "by": actor})
    return {"session": session, "units": units, **listed}
