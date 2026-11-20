"""The data-processing tool AI of a working domain (owner 2026-11-19: 「是不是要提供AI
session讓使用者協助幫忙改程式，並且引導使用者要提供什麼資訊」).

A session of kind `tool` (target `tool:<home>`) is kept in the vault dataset's
`staging.sqlite` like the other sessions. Each turn is one model call with structured
output and no tools (`sessions.ask`): the model sees the working domain, the card types
it uses, the domain's sources by name, the code in the page's editor, the sample sources
the person ticked for a trial (as data) and the last trial's outcome. Until it knows the
input, the wanted output and the edge cases it asks for them in `needs` and writes no
code. A code proposal is checked (it compiles, it writes to OUTPUT, it fits a tool) and
problems go back to the model.

Nothing runs or is saved from here: 「放進編輯區」 only marks the turn and hands the code to
the page's editor; trying it (`tool_runs.try_code`) and saving a version stay the
person's presses, and the sandbox of `tool_runs` is the same for every run.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from aep_bi.cards import catalog, homes, sessions, vault, vault_sources, vault_tools
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import VAULT_PREFIX, BiStore, BiStoreError, now

TARGET_PREFIX = "tool:"
CONTRACT = "aep.bi.tool_suggestion.v1"
FORMAT = "aep.bi.tool_suggestion/v1"
MAX_TRIAL_TEXT = 3000
MAX_SOURCES_LISTED = 40

SYSTEM = """You help a BI knowledge maintainer write a small Python data-processing tool.
A tool turns one raw source file of a working domain into CSV or Markdown files that become
new sources; they then go through the usual preview and review, so the tool never writes
knowledge cards itself.

How a tool runs: the global INPUT is the path of the one source file to read, and OUTPUT is
the folder to write into. It may write only .csv or .md files into OUTPUT (at most 20, none
empty). It runs in an isolated Python process without network, child processes, native
libraries or writes outside OUTPUT; csv, re, json, datetime, decimal, zipfile, xml.etree and
openpyxl (when installed) are available. Print a short summary at the end.

Guide the person. Before you write code you need: (1) what the input looks like (a sample
source ticked for the trial, or a description of its layout), (2) the output wanted (CSV
columns or Markdown sections, one file or several), and (3) edge cases (empty cells, merged
headers, units, dates, several sheets). While any of these is unknown, ask for it in
"needs" in plain Traditional Chinese and leave "code" null. When you know enough, give the
whole program in "code" (not a fragment); when the person's editor already has code, change
that code and keep what works. After a trial, read its outcome and fix what failed.

Answer with one JSON object only:
{"reply": "what you say to the person, in Traditional Chinese",
 "needs": ["what the person should still provide"],
 "code": "the whole Python program" or null,
 "notes": ["short notes on assumptions or limits"]}"""


#: Said when the editor's code is not a tool yet, e.g. a command-line script from a package.
REWRITE_HINT = """The code in the editor does not follow the tool contract yet; it is probably a
command-line script imported from a package (argparse, sys.argv, sibling modules, YAML, writing
cards itself). Rewrite it into one self-contained program that reads the global INPUT and writes
CSV or Markdown files into OUTPUT: keep its parsing logic, drop the command line, sibling-module
imports and anything that writes cards, and use only what the sandbox has. Ask in "needs" only
for what the script itself does not tell you."""


def _vault_id(dataset: str) -> str:
    if not dataset.startswith(VAULT_PREFIX):
        raise BiStoreError("not_a_vault", "資料處理程式只在共用知識庫（vault）裡")
    return dataset[len(VAULT_PREFIX) :]


def create_session(workspace: Path, dataset: str, target: str, actor: str) -> dict[str, Any]:
    _vault_id(dataset)
    if homes.home_problem(target):
        raise BiStoreError("home_invalid", "先選一個工作領域，AI 才知道程式給哪個領域用")
    return sessions.create(
        Staging(workspace, dataset), kind="tool", target_ref=TARGET_PREFIX + target, actor=actor
    )


def check_code(code: str) -> list[str]:
    """Why `code` cannot be a tool; empty when it can."""
    if len(code) > vault_tools.MAX_TEXT:
        return [f"`code` is longer than {vault_tools.MAX_TEXT} characters"]
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return [f"`code` does not compile: line {error.lineno}: {error.msg}"]
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    return [
        f"`code` must use the global {name}" for name in ("INPUT", "OUTPUT") if name not in names
    ]


def check_answer(answer: dict[str, Any]) -> list[str]:
    if not isinstance(answer.get("reply"), str) or not answer["reply"].strip():
        return ["`reply` must be a non-empty text"]
    code = answer.get("code")
    if code in (None, ""):
        return []
    if not isinstance(code, str):
        return ["`code` must be a text or null"]
    return check_code(code)


def _context(workspace: Path, dataset: str, home: str, code: str, samples: str, trial: Any) -> str:
    target = vault._vault(workspace, _vault_id(dataset))
    units = target.repo.working_units()
    reg = catalog.for_store(BiStore(workspace, dataset))
    folder = homes.sources_dir(home)
    staging = Staging(workspace, dataset)
    listed = [
        s["name"]
        for s in staging.sources()
        if homes.home_of(str(vault_sources.folder_of(units, s["sha256"]) or "")) == home
    ][:MAX_SOURCES_LISTED]
    used = vault.profile_types_of(target, folder, units)
    types = [
        f"- {entity.name}: {entity.label} (fields: "
        + ", ".join(f.name for f in entity.fields[:30])
        + ")"
        for entity in reg.types.values()
        if not used or entity.name in used
    ]
    tools = [
        t["name"]
        for t in vault_tools.current_tools(units)
        if str(t["name"]).rpartition("/")[0] == home
    ]
    parts = [
        f"Working domain: {home} (its sources are in {folder})",
        "Card types this domain's cards use:\n" + "\n".join(types),
        "This domain's sources: " + ("、".join(listed) or "(none yet)"),
        "This domain's saved tools: " + ("、".join(tools) or "(none)"),
        sessions.fenced("The code in the person's editor now:", code or "(empty)"),
    ]
    if code.strip() and check_code(code):
        # A command-line script imported from a package (「需改寫」, owner 2026-11-19).
        parts.append(REWRITE_HINT)
    if samples:
        parts.append(samples)
    if isinstance(trial, dict) and trial:
        text = json.dumps(trial, ensure_ascii=False)[:MAX_TRIAL_TEXT]
        parts.append(sessions.fenced("The last trial of the editor's code:", text))
    return "\n\n".join(parts)


def session_turn(
    workspace: Path,
    dataset: str,
    ai: Any,
    session_id: str,
    *,
    message: Any,
    code: Any,
    source_ids: Any,
    trial: Any,
    actor: str,
) -> dict[str, Any]:
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    session = sessions.load(staging, session_id, "tool")
    text = sessions.check_message(message)
    model, alias = sessions.model_or_refuse(ai)
    home = session["target_ref"][len(TARGET_PREFIX) :]
    editor = str(code or "")[: vault_tools.MAX_TEXT]
    samples, sent = sessions.excerpts(staging, source_ids)
    context = _context(workspace, dataset, home, editor, samples, trial)
    turns = [*session["turns"], {"role": "user", "text": text}]
    asked = sessions.ask(
        model,
        alias,
        system=SYSTEM,
        context=context,
        turns=turns,
        contract=CONTRACT,
        check=check_answer,
    )
    suggestion = None
    if asked.answer is not None and asked.failure is None and not check_answer(asked.answer):
        given = asked.answer.get("code")
        suggestion = {
            "format": FORMAT,
            "reply": asked.answer["reply"].strip(),
            "needs": sessions.strings(asked.answer.get("needs")),
            "code": given if isinstance(given, str) and given.strip() else None,
            "notes": sessions.strings(asked.answer.get("notes")),
            "result": {"home": home},
        }
    record = {
        "model": alias,
        "home": home,
        "sources": sent,
        "code_chars": len(editor),
        "trial": bool(trial),
    }
    return sessions.record(
        staging,
        session,
        message=text,
        actor=actor,
        alias=alias,
        asked=asked,
        sent=record,
        suggestion=suggestion,
    )


def apply_suggestion(
    workspace: Path, dataset: str, session_id: str, turn: Any, actor: str
) -> dict[str, Any]:
    """「放進編輯區」: the turn's code for the page's editor. Nothing is saved or run."""
    staging = Staging(workspace, dataset)
    staging.store.refuse_write()
    session = sessions.load(staging, session_id, "tool")
    found, index = sessions.assistant_turn(staging, session, turn)
    code = found["suggestion"].get("code")
    if not code:
        raise BiStoreError("turn_unknown", "這一輪沒有程式碼可以放進編輯區")
    sessions.mark_applied(staging, session, index, {"at": now(), "by": actor})
    return {"session": session, "code": code}
