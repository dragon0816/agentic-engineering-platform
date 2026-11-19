"""Writing a data-processing tool with the page (owner 2026-11-19: 「如果是python程式，應該要讓
使用者選檔案review…提供AI session讓使用者協助幫忙改程式，並且引導使用者要提供什麼資訊。與AI勾通好，
可以讓使用者選擇幾個檔案試跑測試」, and 「這應該也要根據上述的工作領域來自動調整」).

`tool-try` runs the editor's code on one source in the same sandbox as every run and keeps
nothing; the `tool` session asks for what it needs before it writes code, sees the working
domain's types and sources only, and its code is checked before it is shown. All fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_vault import _ok, _two_pcs

from aep_bi.cards import tool_session, vault
from aep_bi.cards.staging import Staging
from aep_bi.host.bi_cards_api import route

AIDC = "applications/aidc/sources"
WIRELESS = "applications/wireless/sources"
MARK = "TRIED-BY-THE-EDITOR"
TOOL = f"""import os
text = open(INPUT, encoding="utf-8").read()
with open(os.path.join(OUTPUT, "rows.csv"), "w", encoding="utf-8") as out:
    out.write("line" + chr(10) + "{MARK}" + chr(10))
print("1 row")
"""


def _post(ws: Path, path: str, body: Any, ai: Any = None) -> Any:
    return route(ws, "alice", "POST", path, {}, body, None, ai)


def _source(ws: Path, dataset: str, name: str, folder: str) -> str:
    body = {"dataset": dataset, "name": name, "text": f"# {name}\n\n虛構內容。\n", "folder": folder}
    return str(_ok(_post(ws, "/api/bi/sources", body))["source"]["id"])


def test_a_trial_runs_the_editors_code_and_keeps_nothing(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _source(a, dataset, "raw.md", AIDC)
    before = len(Staging(a, dataset).sources())
    units = dict(vault.Vault(a, vault_id).repo.working_units())
    tried = _ok(
        _post(a, f"/api/bi/vaults/{vault_id}/tool-try", {"code": TOOL, "source_id": source})
    )
    assert tried["source"] == {"id": source, "name": "raw.md"}
    assert [f["name"] for f in tried["files"]] == ["rows.csv"]
    assert MARK in tried["files"][0]["text"] and "1 row" in tried["printed"]
    assert len(Staging(a, dataset).sources()) == before, "a trial keeps no source"
    assert dict(vault.Vault(a, vault_id).repo.working_units()) == units, "nothing staged"
    # A failure says why, in place of a result.
    status, failed = _post(
        a,
        f"/api/bi/vaults/{vault_id}/tool-try",
        {"code": "raise ValueError('壞掉了')", "source_id": source},
    )
    assert (status, failed["code"]) == (400, "tool_failed") and "壞掉了" in failed["message"]
    # The sandbox is the same as every run's: no network.
    status, blocked = _post(
        a,
        f"/api/bi/vaults/{vault_id}/tool-try",
        {"code": "import socket\nsocket.create_connection(('example.com', 80))\n",
         "source_id": source},
    )  # fmt: skip
    assert (status, blocked["code"]) == (400, "tool_failed")
    status, empty = _post(
        a, f"/api/bi/vaults/{vault_id}/tool-try", {"code": " ", "source_id": source}
    )
    assert (status, empty["code"]) == (400, "tool_invalid")


def test_the_tool_ai_asks_first_then_writes_checked_code_for_the_working_domain(
    tmp_path: Path,
) -> None:
    _, _vault_id, dataset, a, _ = _two_pcs(tmp_path)
    sample = _source(a, dataset, "aidc-sheet.md", AIDC)
    _source(a, dataset, "wireless-note.md", WIRELESS)
    status, refused = _post(a, "/api/bi/sessions", {"dataset": dataset, "kind": "tool"})
    assert (status, refused["code"]) == (400, "home_invalid"), "a tool is for a domain"
    session = _ok(
        _post(a, "/api/bi/sessions", {"dataset": dataset, "kind": "tool", "target": "aidc"})
    )["session"]
    assert session["target_ref"] == "tool:aidc"
    ask = {
        "reply": "我需要知道輸出欄位。",
        "needs": ["要輸出哪些欄位", "空白列怎麼處理"],
        "code": None,
        "notes": [],
    }
    broken = {"reply": "這是程式。", "needs": [], "code": "def (:\n", "notes": []}
    good = {"reply": "這是程式。", "needs": [], "code": TOOL, "notes": ["假設第一行是標題"]}
    model = Scripted(ask, broken, good)
    ai = _runtime(model, Jobs())
    turns = f"/api/bi/sessions/{session['id']}/turns"
    first = _ok(
        _post(
            a,
            turns,
            {"dataset": dataset, "message": "幫我把表格轉成 CSV", "scope": "aidc",
             "code": "", "source_ids": [sample]},
            ai,
        )
    )["session"]  # fmt: skip
    asked = first["turns"][-1]["suggestion"]
    assert asked["code"] is None and asked["needs"] == ["要輸出哪些欄位", "空白列怎麼處理"]
    system = model.requests[0].messages[0].text
    assert "ask for it in" in system and "INPUT" in system and "OUTPUT" in system
    context = model.requests[0].messages[1].text
    assert "Working domain: aidc" in context and "aidc-sheet.md" in context
    assert "wireless-note.md" not in context, "only the working domain's sources"
    assert "Technology" in context, "the card types the domain uses"
    assert first["turns"][-1]["sent"]["sources"][0]["name"] == "aidc-sheet.md"
    second = _ok(
        _post(
            a,
            turns,
            {"dataset": dataset, "message": "欄位：line", "scope": "aidc", "code": "# old",
             "source_ids": [], "trial": {"results": [{"source": "aidc-sheet.md",
                                                      "error": "沒有寫出檔案"}]}},
            ai,
        )
    )["session"]  # fmt: skip
    turn = second["turns"][-1]
    assert turn["attempts"] == 2, "code that does not compile goes back to the model"
    assert turn["suggestion"]["code"] == TOOL and turn["sent"]["trial"] is True
    retried = model.requests[-1].messages
    assert any("does not compile" in m.text for m in retried)
    assert any("沒有寫出檔案" in m.text for m in retried), "the last trial is read"
    assert any("# old" in m.text for m in retried), "the editor's code is read"
    applied = _ok(
        _post(
            a,
            f"/api/bi/sessions/{session['id']}/apply",
            {"dataset": dataset, "turn": len(second["turns"]) - 1},
        )
    )
    assert applied["code"] == TOOL and applied["session"]["turns"][-1]["applied"]
    status, none = _post(
        a, f"/api/bi/sessions/{session['id']}/apply", {"dataset": dataset, "turn": 1}
    )
    assert (status, none["code"]) == (404, "turn_unknown")
    # Without a model nothing is asked or kept.
    status, unavailable = _post(
        a, turns, {"dataset": dataset, "message": "再試", "code": ""}, _runtime(None, Jobs())
    )
    assert (status, unavailable["code"]) == (400, "model_unavailable")


def test_code_checks() -> None:
    assert tool_session.check_code(TOOL) == []
    assert tool_session.check_code("print(1)") == [
        "`code` must use the global INPUT",
        "`code` must use the global OUTPUT",
    ]
    assert "does not compile" in tool_session.check_code("def (:")[0]
