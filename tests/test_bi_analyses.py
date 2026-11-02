"""Analyses of a BI vault: SQL and guarded Python, saved and made by AI (BI T3).

`docs/phases/BI_TEST_AND_TOOLS.md` §5. SQL runs read-only on a copy; a script
runs in its own process and is refused network, child processes, native
libraries and writes outside its folder, and is stopped at its time limit. A
saved analysis is a vault unit committed, pushed and rerun by the other PC.
The analysis AI runs on the Agent harness: it queries, proposes, is told what
is wrong and fixes it; saving stays the person's. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _commit, _import, _ok, _push, _refused, _row, _sync, _two_pcs
from test_business_cards_conversation import Conversation
from test_host_wiring import ready

from capabilities.bi_cards import analyses, vault
from capabilities.bi_cards.store import BiStoreError
from host_runtime import bi_analysis_agent, bi_bench, skill_packs
from host_runtime.assets import shipped
from host_runtime.bi_cards_api import route
from host_runtime.host import build_runtime

BY_BODY = (
    "SELECT value AS body, count(*) AS n FROM card_values "
    "WHERE field = 'standard_body' GROUP BY value ORDER BY n DESC"
)
SCRIPT = """
rows = query("SELECT value FROM card_values WHERE field = 'standard_body'")
counts = {}
for row in rows:
    counts[row["value"]] = counts.get(row["value"], 0) + 1
result = {"columns": ["body", "n"], "rows": sorted(counts.items())}
print("counted", len(rows))
"""


def _vault_with_cards(tmp_path: Path) -> tuple[Any, str, str, Path, Path]:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"), _row("EtherCAT", standard_body="ETG"),
            _row("PROFINET", standard_body="IEEE"))  # fmt: skip
    return drive, vault_id, dataset, a, b


def test_sql_reads_only_and_a_script_is_guarded(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _vault_with_cards(tmp_path)
    db = vault.Vault(a, vault_id).db_path
    table = analyses.run_sql(db, BY_BODY)
    assert table["columns"] == ["body", "n"] and table["rows"][0] == ["IEEE", 2]
    for statement in ("DELETE FROM cards", "ATTACH DATABASE 'x.db' AS x",
                      "SELECT 1; DROP TABLE cards"):  # fmt: skip
        with pytest.raises(BiStoreError):
            analyses.run_sql(db, statement)
    done = analyses.run_python(db, SCRIPT)
    assert done["rows"] == [["ETG", 1], ["IEEE", 2]] and "counted 3" in done["printed"]
    outside = tmp_path / "outside.txt"
    refused = {
        "import socket": "socket",
        "import subprocess": "subprocess",
        "import os\nos.system('echo x')": "os.system",
        f"open(r'{outside}', 'w').write('x')": "outside",
        f"import os\nos.remove(r'{db}')": "outside",
        "import ctypes": "ctypes",
    }
    for code, word in refused.items():
        with pytest.raises(BiStoreError, match=word):
            analyses.run_python(db, code, seconds=20)
    with pytest.raises(BiStoreError, match="秒"):
        analyses.run_python(db, "while True:\n    pass", seconds=3)
    assert db.is_file() and not outside.exists()
    with pytest.raises(BiStoreError, match="result"):
        analyses.run_python(db, "x = 1", seconds=20)


def test_a_saved_analysis_is_committed_pushed_and_rerun_by_the_other_pc(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _vault_with_cards(tmp_path)
    given = {"title": "各標準組織的技術數", "slug": "by-body", "kind": "sql", "code": BY_BODY,
             "chart": {"type": "bar", "x": "body", "y": "n"}}  # fmt: skip
    wrong = {**given, "chart": {"type": "bar", "x": "body", "y": "count"}}
    _refused(_call(a, "POST", f"/api/bi/vaults/{vault_id}/analyses", {"save": wrong}),
             400, "analysis_invalid")  # fmt: skip
    saved = _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/analyses", {"save": given}))
    assert saved["unit"] == "analysis:by-body" and saved["table"]["rows"][0] == ["IEEE", 2]
    pending = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    assert "分析「各標準組織的技術數」" in {c["label"] for c in pending["uncommitted"]}
    _commit(a, vault_id, "加上分析")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    (listed,) = _ok(_call(b, "GET", f"/api/bi/vaults/{vault_id}/analyses"))["analyses"]
    assert listed["chart"] == {"type": "bar", "x": "body", "y": "n"}
    rerun = _ok(_call(b, "POST", f"/api/bi/vaults/{vault_id}/analyses", {"run": "by-body"}))
    assert rerun["table"]["rows"][0] == ["IEEE", 2]
    _refused(_call(b, "POST", f"/api/bi/vaults/{vault_id}/analyses", {"run": "nope"}),
             404, "analysis_unknown")  # fmt: skip
    gone = _ok(_call(b, "POST", f"/api/bi/vaults/{vault_id}/analyses",
                     {"delete": "analysis:by-body"}))  # fmt: skip
    assert gone["analyses"] == []


def test_the_analysis_ai_queries_proposes_and_fixes_on_the_harness(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    skill_packs.install_bundle(layout, None, shipped=shipped())
    ws = layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(_call(ws, "POST", "/api/bi/vaults", {
        "path": str(shared), "title": "Market", "purpose": "虛構", "schema": "bi.schema/v1.1",
        "author": "alice", "default_pack": False}))  # fmt: skip
    vault_id, dataset = made["vault"]["id"], made["vault"]["dataset"]
    _import(ws, dataset, _row("TSN", standard_body="IEEE"), _row("PROFINET", standard_body="IEEE"))
    opened = {"dataset": dataset, "kind": "analysis", "target": "new"}
    session = _ok(_call(ws, "POST", "/api/bi/sessions", opened))["session"]
    proposal = {"title": "各標準組織的技術數", "slug": "by-body", "kind": "sql", "code": BY_BODY}
    with build_runtime(config, layout=layout) as runtime:
        gateway = runtime.agent.gateway
        agent = Conversation()
        gateway.router.model = agent
        agent.then(
            {"tools": [("bi_analysis__sql", {"sql": BY_BODY})]},
            {
                "tools": [
                    (
                        "bi_analysis__propose",
                        {**proposal, "chart": {"type": "bar", "x": "body", "y": "count"}},
                    )
                ]
            },  # fmt: skip
            {
                "tools": [
                    (
                        "bi_analysis__propose",
                        {**proposal, "chart": {"type": "bar", "x": "body", "y": "n"}},
                    )
                ]
            },  # fmt: skip
            {"text": "IEEE 制定的技術最多（2 項）。"},
        )
        bench = bi_bench.BenchRuntime(
            ask_for=lambda _v, _a: lambda q, s: {},
            extract_for=lambda _v, _a: lambda c: [],
            background=lambda _t, work: work(),
            analysis_asker_for=lambda d, a: bi_analysis_agent.harness_asker(
                gateway, ws, d, a, "engineering"
            ),
        )
        body = {"dataset": dataset, "message": "哪個標準組織的技術最多？畫長條圖"}
        status, answer = route(ws, "alice", "POST", f"/api/bi/sessions/{session['id']}/turns",
                               {}, body, None, None, bench)  # fmt: skip
        assert status == 200, answer
    turn = answer["session"]["turns"][-1]
    assert turn["error"] is None, turn
    suggestion = turn["suggestion"]
    assert suggestion["reply"] == "IEEE 制定的技術最多（2 項）。"
    assert suggestion["analysis"]["chart"] == {"type": "bar", "x": "body", "y": "n"}
    assert suggestion["preview"]["rows"] == [["IEEE", 2]]
    assert turn["attempts"] == 2
    assert [t["name"] for t in turn["sent"]["tools"]] == [
        "bi_analysis__sql", "bi_analysis__propose", "bi_analysis__propose"
    ]  # fmt: skip
    assert {t.name for t in agent.requests[0].tools} == {
        "bi_analysis__sql", "bi_analysis__python", "bi_analysis__propose",
        "bi_analysis__propose_dashboard", "bi_analysis__read",
    }  # fmt: skip
    told = "\n".join(m.text for m in agent.requests[2].messages if m.role == "tool")
    assert "y" in told and "欄位" in told
    # Nothing is saved until the person saves it.
    assert _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/analyses"))["analyses"] == []
    applied = route(ws, "alice", "POST", f"/api/bi/sessions/{session['id']}/apply",
                    {}, {"dataset": dataset, "turn": 1})  # fmt: skip
    assert applied[0] == 200 and applied[1]["unit"] == "analysis:by-body", applied
    # Without the Agent Web harness there is no analysis AI.
    status, refused = route(ws, "alice", "POST", f"/api/bi/sessions/{session['id']}/turns",
                            {}, body)  # fmt: skip
    assert (status, refused["code"]) == (400, "harness_unavailable")


def test_a_scripts_non_ascii_result_and_output_survive(tmp_path: Path) -> None:
    # `python -I` ignores PYTHONIOENCODING: the runner must write UTF-8 itself.
    drive, vault_id, dataset, a, b = _vault_with_cards(tmp_path)
    db = vault.Vault(a, vault_id).db_path
    done = analyses.run_python(
        db, 'print("標準組織")\nresult = {"columns": ["組織"], "rows": [["電機"]]}'
    )
    assert done["columns"] == ["組織"] and done["rows"] == [["電機"]]
    assert "標準組織" in done["printed"]
