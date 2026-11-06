"""Which card types a run with a skill produces, said where it is set (acceptance F17,
2026-11-06).

The skill form said 「只產生這些卡片類型（留空＝不限）」, but an empty list meant
`extract.DEFAULT_TYPES` (Signal, Technology, Application), so a good rule about
customers changed nothing until the types were typed in. One function decides the
types (the person's choice, the rule's, narrowed by the domain's profile, else the
profile's, else the defaults); the skills list says what each rule really produces,
and the skill AI must give card types for a rule about types a run would not make.
All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _ok

from capabilities.bi_cards import ai_runs, catalog, extract, sessions, skill_session

AIDC = "applications/aidc/sources"
PROFILE: dict[str, Any] = {"types": {"Technology": {"fields": {}}, "Account": {"fields": {}}}}


def _reg() -> Any:
    return catalog.resolve(Path("."), "bi.schema/v1.1@5.0.0")


@pytest.mark.parametrize(
    ("chosen", "rule", "profile", "expected"),
    [
        (["Account"], ["Signal"], None, (["Account"], "person")),
        ([], ["Account", "Signal"], None, (["Account", "Signal"], "skill")),
        ([], [], None, (list(extract.DEFAULT_TYPES), "default")),
        ([], [], ["Technology", "Account"], (["Technology", "Account"], "profile")),
        ([], ["Account", "Signal"], ["Technology", "Account"], (["Account"], "skill")),
        ([], ["Signal"], ["Technology", "Account"], (["Technology", "Account"], "profile")),
    ],
)
def test_one_function_decides_the_types_of_a_run(
    chosen: list[str], rule: list[str], profile: list[str] | None, expected: Any
) -> None:
    assert ai_runs.run_types(_reg(), chosen, rule, profile) == expected


def _vault(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    from test_host_wiring import ready

    from host_runtime import skill_packs
    from host_runtime.assets import shipped

    _config, layout = ready(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    ws = layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(_call(ws, "POST", "/api/bi/vaults", {
        "path": str(shared), "title": "Market", "purpose": "虛構", "schema": "bi.schema/v1.1",
        "author": "alice"}))  # fmt: skip
    return ws, made["vault"]


def _skill(ws: Path, vault_id: str, name: str, card_types: list[str]) -> None:
    body = {"name": name, "role": "extract", "applies_to": [AIDC], "card_types": card_types,
            "body": "虛構電源廠是 Account。"}  # fmt: skip
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/skills", body))


def _listed(ws: Path, vault_id: str) -> dict[str, Any]:
    return _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/skills"))


def test_the_skills_list_says_what_a_run_really_produces(tmp_path: Path) -> None:
    ws, vault = _vault(tmp_path)
    _skill(ws, vault["id"], "power-extract", [])
    found = next(s for s in _listed(ws, vault["id"])["skills"] if s["name"] == "power-extract")
    assert found["run_types"] == {"types": list(extract.DEFAULT_TYPES), "from": "default"}
    body = {"home": "aidc", "profile": PROFILE}
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault['id']}/profiles", body))
    listed = _listed(ws, vault["id"])
    found = next(s for s in listed["skills"] if s["name"] == "power-extract")
    assert found["run_types"] == {"types": ["Account", "Technology"], "from": "profile"}
    assert listed["profile_types"] == {"aidc": ["Account", "Technology"]}  # as stored


def _turn(ws: Path, vault: dict[str, Any], answers: list[dict[str, Any]]) -> Any:
    opened = {"dataset": vault["dataset"], "kind": "skill", "target": "power-extract"}
    session = _ok(_call(ws, "POST", "/api/bi/sessions", opened))["session"]
    seen: dict[str, Any] = {"problems": []}

    def asker(context: str, _turns: Any, check: Any, _base: Any) -> Any:
        seen["context"] = context
        for answer in answers:
            found = check(answer)
            seen["problems"].append(found)
            if not found:
                return sessions.Asked(answer=answer, attempts=len(seen["problems"])), "m", []
        return sessions.Asked(answer=None, attempts=len(answers), problems=found), "m", []

    turned = skill_session.session_turn(
        ws, vault["dataset"], None, session["id"], message="電源廠要建 Account",
        source_ids=[], run_ids=[], actor="alice", asker=asker,
    )  # fmt: skip
    return turned["turns"][-1], seen


def test_the_skill_ai_must_give_card_types_for_a_rule_about_other_types(tmp_path: Path) -> None:
    ws, vault = _vault(tmp_path)
    _skill(ws, vault["id"], "power-extract", [])
    body = "虛構電源廠是 Account；規格寫在 Technology。"
    turn, seen = _turn(ws, vault, [
        {"reply": "改好了。", "changes": {"body": body}},
        {"reply": "改好了。", "changes": {"body": body, "card_types": ["Account", "Technology"]}},
    ])  # fmt: skip
    assert "Signal, Technology, Application" in seen["context"]
    first = " ".join(seen["problems"][0])
    assert "Account" in first and "card_types" in first
    assert seen["problems"][1] == []
    assert turn["suggestion"]["changes"]["card_types"] == ["Account", "Technology"]


def test_a_type_the_profile_leaves_out_is_not_asked_for(tmp_path: Path) -> None:
    ws, vault = _vault(tmp_path)
    _skill(ws, vault["id"], "power-extract", [])
    only: dict[str, Any] = {"types": {"Technology": {"fields": {}}}}
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault['id']}/profiles",
              {"home": "aidc", "profile": only}))  # fmt: skip
    # card_types cannot add Account under this profile: no loop, the draft passes.
    turn, seen = _turn(ws, vault, [{"reply": "好。", "changes": {"body": "電源廠是 Account。"}}])
    assert seen["problems"] == [[]]
    assert turn["suggestion"] is not None
