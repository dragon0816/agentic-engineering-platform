"""Guarded read-only ad-hoc SQL in the general chat (BI C1b, owner 2026-11-01).

`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` C1b: `bi__query` `sql`
runs one read-only statement through the analyses' own guard
(`analyses.run_sql`) on the data the chat reads (a vault's published version),
within the analyses' time limit and a 200-row cap, and the result is charted
like a saved analysis. Nothing is saved. All data is fictional.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from test_bi_chat_charts import DATASET, _call, _data, _host
from test_bi_query_analyses import _joined
from test_bi_vault_published import CONTEXT

from capabilities.bi_cards import analyses
from capabilities.bi_cards.capability import CHAT_SQL_ROWS, QueryHandler, QueryRequest
from capabilities.bi_cards.store import BiStore
from capabilities.runtime import CapabilityRefused
from host_runtime.bi_cards_tools import bi_cards_tools
from host_runtime.host import build_runtime
from scripts import bi_feed_fixtures as fixtures

BY_REGION = (
    "SELECT value AS region, count(*) AS accounts FROM card_values "
    "WHERE entity_type = 'Account' AND field = 'region' GROUP BY value ORDER BY value"
)
NUMBERS = "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < {}) "


def _sql(ws: Path, sql: str, **given: Any) -> dict[str, Any]:
    request = QueryRequest(dataset=DATASET, sql=sql, **given)
    return dict(asyncio.run(QueryHandler(ws)(CONTEXT, request)).model_dump())


def _refused(ws: Path, sql: str, **given: Any) -> str:
    with pytest.raises(CapabilityRefused) as refused:
        _sql(ws, sql, **given)
    return str(refused.value.code)


def test_a_query_is_answered_and_charted_like_an_analysis(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    found = _sql(ws, BY_REGION)
    (section,) = found["analysis"]
    assert section["id"] == "query" and section["sql"] == BY_REGION
    assert section["columns"] == ["region", "accounts"] and section["truncated"] is False
    assert section["chart"] == {"type": "bar", "x": "region", "y": "accounts"}  # the default
    assert "發佈版本 v1" in found["scope_note"]
    line = {"type": "line", "x": "region", "y": "accounts"}
    assert _sql(ws, BY_REGION, chart=line)["analysis"][0]["chart"] == line
    wrong = {"type": "line", "x": "nowhere", "y": "accounts"}
    assert _sql(ws, BY_REGION, chart=wrong)["analysis"][0]["chart"]["type"] == "bar"


def test_writes_attach_pragma_and_several_statements_are_refused(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    for sql in (
        "DELETE FROM cards",
        "UPDATE cards SET name = 'x'",
        "INSERT INTO cards (id) VALUES ('x')",
        "DROP TABLE cards",
        "CREATE TABLE stolen AS SELECT * FROM cards",
        f"ATTACH DATABASE '{(tmp_path / 'other.db').as_posix()}' AS other",
        "PRAGMA journal_mode = DELETE",
        "PRAGMA writable_schema = ON",
    ):
        assert _refused(ws, sql) == "sql_not_allowed", sql
    assert not (tmp_path / "other.db").exists()
    assert _refused(ws, "SELECT 1; DELETE FROM cards") == "sql_one_statement"
    assert _refused(ws, "SELECT nothing FROM nowhere") == "sql_failed"
    assert _refused(ws, BY_REGION, analysis="accounts-by-region") == "invalid_input"
    # The published data is intact afterwards.
    assert len(_sql(ws, BY_REGION)["analysis"][0]["rows"]) == 5


def test_a_long_query_hits_the_time_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _joined(tmp_path)
    assert analyses.SQL_SECONDS == 10.0  # the analyses' limit is the chat's
    monkeypatch.setattr(analyses, "SQL_SECONDS", 0.5)
    endless = "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) SELECT max(i) FROM n"
    assert _refused(ws, endless) == "timeout"


def test_at_most_200_rows_are_returned_and_a_cut_result_says_so(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    assert CHAT_SQL_ROWS == 200
    (cut,) = _sql(ws, NUMBERS.format(500) + "SELECT i FROM n")["analysis"]
    assert len(cut["rows"]) == 200 and cut["truncated"] is True
    (whole,) = _sql(ws, NUMBERS.format(200) + "SELECT i FROM n")["analysis"]
    assert len(whole["rows"]) == 200 and whole["truncated"] is False


def test_unpublished_work_is_never_read(tmp_path: Path) -> None:
    """The fixture pushed Maple Grippers after v1; this PC adds another card to
    its working copy; the chat's SQL sees neither."""
    ws = _joined(tmp_path)
    fixtures._import(
        BiStore(ws, DATASET),
        "Account",
        [{"name": "Rowan Local", "domain": ["robotics"], "region": "KR"}],
    )
    names = "SELECT card FROM card_values WHERE entity_type = 'Account' AND field = 'name'"
    (section,) = _sql(ws, names)["analysis"]
    found = {row[0] for row in section["rows"]}
    assert len(found) == len(fixtures.ACCOUNTS)
    assert not any("Maple" in str(n) or "Rowan" in str(n) for n in found)


def test_the_chat_tool_runs_sql_through_the_bridge_and_attaches_the_chart(
    tmp_path: Path,
) -> None:
    config, layout = _host(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        (tool, _atlas) = bi_cards_tools(runtime.agent.gateway)
        properties = (tool.tool.input_schema or {}).get("properties")
        assert isinstance(properties, dict) and {"sql", "chart"} <= set(properties)
        answer = _call(tool, {"dataset": DATASET, "sql": BY_REGION})
        refused = _call(tool, {"dataset": DATASET, "sql": "DELETE FROM cards"})
    (attached,) = _data(answer)["attach"]
    assert Path(attached["path"]).name.startswith("bi-query-")
    assert "查詢結果" in Path(attached["path"]).read_text("utf-8")
    assert refused.status == "failed" and refused.failure is not None
    assert refused.failure.code == "sql_not_allowed"
    assert "只能讀取" in refused.failure.message
