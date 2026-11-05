"""Benchmarks kept in a BI vault: question sets and extraction cases (BI T1).

`docs/phases/BI_TEST_AND_TOOLS.md` §3.1. Two unit kinds, committed and pushed
like cards and skills, never rows of `bi.sqlite`:

- `check:question:<set>/<slug>` = `{"question", "must", "must_not", "home"?}`, graded
  as a wiki question (`knowledge.questions`): case-insensitive terms; a question
  with no terms is listed as ungraded. `home` is the working domain it belongs to
  (`docs/phases/BI_PAGE_SIMPLE.md` §9); without it, the whole vault's.
- `check:extract:<slug>` = `{"note", "folder", "expected"}`: a short source text,
  the vault folder that picks its extract skill, and what extraction must find
  (`aep.bi.benchmark.expected/v1`, `benchmark.py`).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capabilities.bi_cards import benchmark, homes, vault_skills
from capabilities.bi_cards.store import BiStoreError

PREFIX = "check:"
QUESTION_PREFIX = "check:question:"
EXTRACT_PREFIX = "check:extract:"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
MAX_QUESTION = 1000
MAX_TERMS = 20
MAX_TERM = 200
MAX_NOTE = 20000
DEFAULT_SET = "main"


def _terms(value: Any) -> list[str] | None:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        value = [part for part in re.split(r"[,，、\n]", value)]
    if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
        return None
    terms = [t.strip() for t in value if t.strip()]
    if len(terms) > MAX_TERMS or any(len(t) > MAX_TERM for t in terms):
        return None
    return list(dict.fromkeys(terms))


def unit_problem(key: str, value: Any) -> str | None:
    """Why `value` cannot be the check unit `key`; None when it can."""
    if not isinstance(value, dict):
        return "check must be an object"
    if key.startswith(QUESTION_PREFIX):
        group, _, slug = key[len(QUESTION_PREFIX) :].partition("/")
        if not NAME_RE.match(group) or not NAME_RE.match(slug):
            return "question key must be check:question:<set>/<slug>"
        question = value.get("question")
        if not isinstance(question, str) or not question.strip():
            return "question needs text"
        if _terms(value.get("must")) is None or _terms(value.get("must_not")) is None:
            return "must and must_not must be lists of short terms"
        if "home" in value and homes.home_problem(value["home"]):
            return "home must be <application> or library/<entry>"
        return None
    if key.startswith(EXTRACT_PREFIX):
        if not NAME_RE.match(key[len(EXTRACT_PREFIX) :]):
            return "case key must be check:extract:<slug>"
        note = value.get("note")
        if not isinstance(note, str) or not note.strip():
            return "case needs a note"
        expected = value.get("expected")
        if not isinstance(expected, dict):
            return "case needs expected"
        problems = benchmark.check_expected(expected, note)
        return "；".join(problems) or None
    return "unknown check"


def label(key: str, units: Mapping[str, Any]) -> str:
    value = units.get(key)
    if key.startswith(QUESTION_PREFIX):
        text = value.get("question") if isinstance(value, dict) else None
        return f"測試題「{text or key[len(QUESTION_PREFIX) :]}」"
    return f"擷取測試「{key[len(EXTRACT_PREFIX) :]}」"


def _slug(text: str) -> str:
    return "q-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]  # noqa: S324 (a name)


def questions(units: Mapping[str, Any]) -> list[dict[str, Any]]:
    found = []
    for key, value in sorted(units.items()):
        if key.startswith(QUESTION_PREFIX) and isinstance(value, dict):
            group, _, slug = key[len(QUESTION_PREFIX) :].partition("/")
            found.append(
                {
                    "unit": key,
                    "set": group,
                    "slug": slug,
                    "question": value.get("question"),
                    "must": list(value.get("must") or []),
                    "must_not": list(value.get("must_not") or []),
                    "home": value.get("home") or None,
                }
            )
    return found


def case_home(case: Mapping[str, Any]) -> str | None:
    return homes.home_of(str(case.get("folder") or ""))


def in_scope(home: str | None, own: str | None) -> bool:
    """Whether a check of the home `own` is the working domain `home`'s. Each domain has its
    own; no working domain is the overview, which has them all. A check of no home is waiting
    to be given one and belongs to no domain (`docs/phases/BI_PAGE_SIMPLE.md` §11)."""
    return not home or own == home


def cases(units: Mapping[str, Any]) -> list[dict[str, Any]]:
    found = []
    for key, value in sorted(units.items()):
        if key.startswith(EXTRACT_PREFIX) and isinstance(value, dict):
            found.append(
                {
                    "unit": key,
                    "slug": key[len(EXTRACT_PREFIX) :],
                    "note": value.get("note"),
                    "folder": value.get("folder"),
                    "expected": value.get("expected"),
                }
            )
    return found


def checked_question(given: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    question = str(given.get("question") or "").strip()
    if not question:
        raise BiStoreError("question_invalid", "請寫題目")
    if len(question) > MAX_QUESTION:
        raise BiStoreError("question_invalid", f"題目最多 {MAX_QUESTION} 字")
    must, must_not = _terms(given.get("must")), _terms(given.get("must_not"))
    if must is None or must_not is None:
        raise BiStoreError(
            "question_invalid",
            f"「必須提到」與「不可以說」各最多 {MAX_TERMS} 個詞，每個最多 {MAX_TERM} 字",
        )
    group = str(given.get("set") or DEFAULT_SET).strip()
    slug = str(given.get("slug") or _slug(question)).strip()
    if not NAME_RE.match(group) or not NAME_RE.match(slug):
        raise BiStoreError("question_invalid", "題組與代號只能用小寫英數字與 -")
    home = given.get("home") or None
    if home is not None and homes.home_problem(home):
        raise BiStoreError("question_invalid", "領域必須是應用資料夾或 library 的項目")
    # Absent, not null, on a question of no home: its unit stays what it was.
    return f"{QUESTION_PREFIX}{group}/{slug}", {
        "question": question,
        "must": must,
        "must_not": must_not,
        **({"home": home} if home else {}),
    }


def checked_case(given: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    note = str(given.get("note") or "")
    if not note.strip():
        raise BiStoreError("case_invalid", "請貼上測試用的原文")
    if len(note) > MAX_NOTE:
        raise BiStoreError("case_invalid", f"原文最多 {MAX_NOTE} 字")
    slug = str(given.get("slug") or "").strip()
    if not NAME_RE.match(slug):
        raise BiStoreError("case_invalid", "代號只能用小寫英數字與 -")
    expected = given.get("expected")
    if not isinstance(expected, dict):
        raise BiStoreError("case_invalid", "expected 必須是 JSON 物件")
    expected = {**expected, "note": f"{slug}.md"}
    problems = benchmark.check_expected(expected, note)
    if problems:
        raise BiStoreError("case_invalid", "；".join(problems))
    folder = given.get("folder") or None
    if folder is not None:
        folder = vault_skills.checked_folder(folder)
    return f"{EXTRACT_PREFIX}{slug}", {"note": note, "folder": folder, "expected": expected}


# -- on a vault -------------------------------------------------------------------------


def listing(workspace: Path, vault_id: str) -> dict[str, Any]:
    from capabilities.bi_cards import vault

    units = vault.Vault(workspace, vault_id).repo.working_units()
    return {"questions": questions(units), "cases": cases(units)}


def _stage(workspace: Path, vault_id: str, key: str, value: Any) -> dict[str, Any]:
    from capabilities.bi_cards import vault

    target = vault._vault(workspace, vault_id)
    with target.lock, vault._repo_errors():
        target.repo.stage(key, value)
    return listing(workspace, vault_id)


def save_question(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    key, value = checked_question(given)
    return {"unit": key, **_stage(workspace, vault_id, key, value)}


def save_case(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    key, value = checked_case(given)
    return {"unit": key, **_stage(workspace, vault_id, key, value)}


def delete(workspace: Path, vault_id: str, unit: Any) -> dict[str, Any]:
    if not isinstance(unit, str) or not unit.startswith((QUESTION_PREFIX, EXTRACT_PREFIX)):
        raise BiStoreError("check_unknown", "沒有這個測試")
    from capabilities.bi_cards import vault

    units = vault.Vault(workspace, vault_id).repo.working_units()
    if unit not in units:
        raise BiStoreError("check_unknown", "沒有這個測試")
    return _stage(workspace, vault_id, unit, None)
