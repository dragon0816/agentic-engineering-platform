"""Giving what a vault already has to its domains: a dry run, then one step.

`docs/phases/BI_PAGE_SIMPLE.md` §12. `plan` writes nothing and says, for each question and
analysis, which domain it could belong to and why, in plain basis a person can check.
`apply` stages an approved list: a question gets its `home`, an analysis goes on each chosen
home's Dashboard. Nothing is committed: that stays the person's.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capabilities.bi_cards import analyses, homes, vault_checks, vault_skills
from capabilities.bi_cards.store import BiStoreError

_PREFIX_RE = re.compile(r"^\s*([^：:]{1,30})[：:]")


def _same(text: Any) -> str:
    return re.sub(r"[\s_-]+", "", str(text)).casefold()


def _names(units: Mapping[str, Any]) -> dict[str, str]:
    """What a home is called, to its home: its short name and its label."""
    found: dict[str, str] = {}
    for item in vault_skills.home_list(units):
        found[_same(item["home"].rpartition("/")[2])] = item["home"]
        found[_same(item["label"])] = item["home"]
    return found


def _named_in(text: str, names: Mapping[str, str]) -> list[str]:
    """The homes `text` names as whole words; a short name inside a longer word is not one."""
    hits = []
    for name, home in names.items():
        pattern = rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])"
        if re.search(pattern, str(text).casefold()) and home not in hits:
            hits.append(home)
    return hits


def _question(item: Mapping[str, Any], names: Mapping[str, str]) -> dict[str, Any]:
    text = str(item["question"] or "")
    row = {
        "unit": item["unit"],
        "question": text,
        "home": item["home"],
        "suggested": None,
        "basis": "題目裡看不出領域",
    }
    if item["home"]:
        return {**row, "suggested": item["home"], "basis": "已經指定了領域"}
    matched = _PREFIX_RE.match(text)
    if matched and _same(matched.group(1)) in names:
        return {
            **row,
            "suggested": names[_same(matched.group(1))],
            "basis": f"題目開頭寫著「{matched.group(1).strip()}」",
        }
    hits = _named_in(text, names)
    if len(hits) == 1:
        return {**row, "suggested": hits[0], "basis": "題目裡提到這個領域"}
    if hits:
        return {**row, "basis": "題目提到幾個領域：" + "、".join(hits)}
    return row


def _analysis(
    item: Mapping[str, Any], names: Mapping[str, str], domains: list[str], order: list[str]
) -> dict[str, Any]:
    row = {
        "slug": item["slug"],
        "title": item.get("title"),
        "on_vault_dashboard": item["slug"] in order,
        "filters_domain": analyses.uses_domain(item),
    }
    if row["filters_domain"]:
        return {
            **row,
            "suggested": domains,
            "kind": "shared",
            "basis": "查詢用 domain 參數篩選，各領域看到自己的數字",
        }
    hits = _named_in(f"{item.get('title') or ''} {item.get('question') or ''}", names)
    if len(hits) == 1:
        return {
            **row,
            "suggested": hits,
            "kind": "one_domain",
            "basis": "標題或問題提到這個領域，但查詢沒有篩選領域，請確認",
        }
    return {
        **row,
        "suggested": [],
        "kind": "whole_vault",
        "basis": "查詢沒有篩選領域，看的是全庫資料，留在全庫 Dashboard",
    }


def plan(workspace: Path, vault_id: str) -> dict[str, Any]:
    """The dry run. Writes nothing."""
    from capabilities.bi_cards import vault

    target = vault.Vault(workspace, vault_id)
    units = target.repo.working_units()
    names = _names(units)
    reg = target._schema_of(units)
    known = reg.domains if reg is not None else ()
    domains = [
        item["home"]
        for item in vault_skills.home_list(units)
        if homes.domain_of_folder(known, homes.sources_dir(item["home"]))
    ]
    order = analyses.order(units, [str(a["slug"]) for a in analyses.saved(units)])
    return {
        "homes": [item["home"] for item in vault_skills.home_list(units)],
        "questions": [_question(q, names) for q in vault_checks.questions(units)],
        "analyses": [_analysis(a, names, domains, order) for a in analyses.saved(units)],
    }


def apply(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Stage an approved list: `{"questions": {unit: home}, "analyses": {slug: [home]}}`.
    Everything is checked before anything is staged."""
    from capabilities.bi_cards import vault

    target = vault.Vault(workspace, vault_id)
    units = target.repo.working_units()
    known = {item["home"] for item in vault_skills.home_list(units)}
    questions = given.get("questions") or {}
    panels = given.get("analyses") or {}
    if not isinstance(questions, dict) or not isinstance(panels, dict):
        raise BiStoreError("assign_invalid", "questions 與 analyses 必須是對照表")
    saved = {str(a["slug"]) for a in analyses.saved(units)}
    for unit, home in questions.items():
        if not str(unit).startswith(vault_checks.QUESTION_PREFIX) or unit not in units:
            raise BiStoreError("assign_invalid", f"沒有這個測試題：{unit}")
        if home not in known:
            raise BiStoreError("assign_invalid", f"沒有這個領域：{home}")
    for slug, chosen in panels.items():
        if slug not in saved:
            raise BiStoreError("assign_invalid", f"沒有這個分析：{slug}")
        if not isinstance(chosen, list) or any(home not in known for home in chosen):
            raise BiStoreError("assign_invalid", f"分析 {slug} 的領域不對")
    changes: dict[str, Any] = {
        unit: {**units[unit], "home": home} for unit, home in questions.items()
    }
    for home in sorted({h for chosen in panels.values() for h in chosen}):
        layout = analyses.dashboard_layout(units, home)
        added = [slug for slug, chosen in panels.items() if home in chosen]
        changes[analyses.dashboard_unit(home)] = json.dumps(
            {
                "order": [*layout["order"], *[s for s in added if s not in layout["order"]]],
                "hidden": [s for s in layout["hidden"] if s not in added],
            },
            ensure_ascii=False,
        )
    with target.lock, vault._repo_errors():
        target.repo.stage_many(changes)
    return {"questions": len(questions), "dashboards": len(changes) - len(questions)}
