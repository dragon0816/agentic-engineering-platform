"""The general chat changes a saved analysis, with the owner's approval (BI P1).

`docs/phases/BI_CHAT_EMBED_AND_PANEL_EDIT.md`: `propose_change` kind
`bi_analysis_edit` takes only what changes; the card shows each field before and
after and the whole code; only Apply in Agent Web stages it; a script the chat
wrote runs only after Apply; published, the edit reaches Atlas through the
feed's digest. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_ai_proposed_changes import _card, _propose
from test_bi_chat_charts import DATASET, _host
from test_host_wiring import host_json

from capabilities.bi_cards import analyses, board, feed, vault
from common.change_proposal import KINDS, PROPOSE_GUIDANCE, TELEGRAM_KINDS
from host_runtime import bi_chat_save
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb
from scripts import bi_feed_fixtures as fixtures

SLUG = "accounts-by-region"
BY_DOMAIN = (
    "SELECT value AS domain, count(*) AS accounts FROM card_values "
    "WHERE entity_type = 'Account' AND field = 'domain' GROUP BY 1 ORDER BY 1"
)
SCRIPT = 'result = {"columns": ["n"], "rows": [[len(query("SELECT id FROM cards"))]]}'


@pytest.fixture
def web(tmp_path: Path) -> Any:
    config, layout = _host(tmp_path)
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        agent_web = AgentWeb(runtime, config_path=path)
        agent_web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        yield agent_web


def _workspace(web: AgentWeb) -> Path:
    return Path(web.runtime.layout.workspace_root)


def _working(web: AgentWeb) -> dict[str, Any]:
    return dict(vault.Vault(_workspace(web), fixtures.VAULT_ID).repo.working_units())


def _edit(**changes: Any) -> dict[str, Any]:
    return {"vault": DATASET, "slug": SLUG, **changes}


def _rows(card: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {row["label"]: row for row in card["rows"]}


def test_changes_list_only_the_fields_that_differ() -> None:
    before = {"title": "A", "question": "", "kind": "sql", "code": "SELECT 1",
              "chart": {"type": "table"}, "params": {}}  # fmt: skip
    assert analyses.changes(before, {**before, "question": None, "requires": {}}) == []
    assert analyses.changes(before, {**before, "title": "B", "unit": "x"}) == [
        {"field": "title", "before": "A", "after": "B"}
    ]


def test_the_kind_is_offered_and_never_applied_from_telegram() -> None:
    assert "bi_analysis_edit" in KINDS and "bi_analysis_edit" not in TELEGRAM_KINDS
    assert "change a saved analysis" in PROPOSE_GUIDANCE


def test_an_edit_shows_before_and_after_and_only_apply_stages_it(web: AgentWeb) -> None:
    before = _working(web)
    unit = before[f"analysis:{SLUG}"]
    chart = {"type": "line", "x": "domain", "y": "accounts"}
    values = _edit(title="各領域的客戶數", sql=BY_DOMAIN, chart=chart, params={})
    card = _card(_propose(web, "bi_analysis_edit", values, "by domain instead"))
    assert card["status"] == "pending" and card["web_only"] is True
    rows = _rows(card)
    assert rows["Title"]["before"] == unit["title"] and rows["Title"]["after"] == "各領域的客戶數"
    assert rows["SQL"]["before"] == unit["code"] and rows["SQL"]["after"] == BY_DOMAIN
    assert rows["Chart"]["after"] == '{"type": "line", "x": "domain", "y": "accounts"}'
    assert '"bar"' in rows["Chart"]["before"]
    assert "domain" in rows["Parameters"]["before"] and rows["Parameters"]["after"] == ""
    result = rows["Result on the working copy"]
    assert result["before"] == "5 rows: TW, 3; DE, 1; EU, 1"
    assert result["after"] == '5 rows: ["AIDC"], 3; ["robotics","AIDC"], 1; ["robotics"], 5'
    assert card["preview"].startswith("--- now\n+++ after")
    assert f"+{BY_DOMAIN}" in card["preview"]
    assert _working(web) == before  # nothing staged by the proposal

    refused = web.decide_card(card["card_id"], "apply", "telegram")
    assert refused["code"] == "web_only" and _working(web) == before

    applied = web.decide_card(card["card_id"], "apply")
    assert applied["ok"] is True and "commit, push and publish" in applied["message"]
    edited = _working(web)[f"analysis:{SLUG}"]
    assert edited["code"] == BY_DOMAIN and edited["chart"] == chart
    assert edited["title"] == "各領域的客戶數" and "params" not in edited


def test_what_is_not_given_stays(web: AgentWeb) -> None:
    unit = _working(web)[f"analysis:{SLUG}"]
    card = _card(_propose(web, "bi_analysis_edit", _edit(title="新標題")))
    labels = [row["label"] for row in card["rows"]]
    assert labels == ["Knowledge base", "Title", "Result on the working copy"]
    assert card["preview"] == ""
    assert web.decide_card(card["card_id"], "apply")["ok"] is True
    assert _working(web)[f"analysis:{SLUG}"] == {**unit, "title": "新標題"}


def test_long_code_is_clipped_in_its_cell_and_whole_in_the_preview(web: AgentWeb) -> None:
    long_sql = (
        "SELECT json_extract(value, '$') AS domain, count(*) AS accounts FROM card_values "
        + "WHERE 1 = 1 "
        + "AND entity_type = 'Account' " * 30
        + "AND field = 'domain' GROUP BY 1"
    )
    assert len(long_sql) > bi_chat_save.CELL
    chart = {"type": "bar", "x": "domain", "y": "accounts"}
    values = _edit(sql=long_sql, chart=chart, params={})
    card = _card(_propose(web, "bi_analysis_edit", values))
    cell = _rows(card)["SQL"]["after"]
    assert len(cell) == bi_chat_save.CELL and cell.endswith("…")
    assert f"+{long_sql}" in card["preview"]


def test_a_new_long_analysis_shows_its_whole_sql_too(web: AgentWeb) -> None:
    long_sql = "SELECT entity_type AS t FROM cards WHERE 1 = 1 " + "AND 2 = 2 " * 60
    values = {"vault": DATASET, "slug": "a-new-one", "title": "新的", "chart": {"type": "table"},
              "sql": long_sql}  # fmt: skip
    card = _card(_propose(web, "bi_analysis", values))
    assert _rows(card)["SQL"]["after"].endswith("…") and card["preview"] == long_sql


def test_a_script_from_the_chat_runs_only_after_apply(
    web: AgentWeb, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[str] = []
    real = analyses.run_python

    def counted(path: Path, code: str, *args: Any, **kwargs: Any) -> Any:
        ran.append(code)
        return real(path, code, *args, **kwargs)

    monkeypatch.setattr(analyses, "run_python", counted)
    values = _edit(script=SCRIPT, chart={"type": "table"}, params={})
    card = _card(_propose(web, "bi_analysis_edit", values))
    assert ran == []  # not run for the card
    rows = _rows(card)
    assert rows["Script"]["after"] == SCRIPT and rows["Kind"]["after"] == "python"
    assert rows["Result on the working copy"]["after"] == bi_chat_save.NOT_RUN

    assert web.decide_card(card["card_id"], "apply")["ok"] is True
    assert ran == [SCRIPT]
    edited = _working(web)[f"analysis:{SLUG}"]
    assert edited["kind"] == "python" and edited["code"] == SCRIPT


def test_a_script_that_fails_on_apply_stages_nothing(web: AgentWeb) -> None:
    before = _working(web)
    values = _edit(script="raise ValueError('boom')", chart={"type": "table"}, params={})
    card = _card(_propose(web, "bi_analysis_edit", values))
    outcome = web.decide_card(card["card_id"], "apply")
    assert outcome.get("ok") is not True
    assert _working(web) == before


def test_a_saved_script_whose_code_stays_is_run_for_the_card(web: AgentWeb) -> None:
    card = _card(
        _propose(web, "bi_analysis_edit", {"vault": DATASET, "slug": "tech-updates", "title": "新"})
    )
    assert _rows(card)["Result on the working copy"]["after"] != bi_chat_save.NOT_RUN


@pytest.mark.parametrize(
    ("changes", "says"),
    [
        ({"vault": "vault-nowhere"}, "No such knowledge base"),
        ({"slug": "no-such-analysis", "title": "x"}, "no analysis"),
        ({}, "changes nothing"),
        ({"title": "各地區的客戶數"}, "changes nothing"),
        ({"sql": "SELECT 1", "script": "result = []"}, "either sql or script"),
        ({"sql": "DELETE FROM cards", "params": {}}, "not authorized"),
        ({"chart": {"type": "bar", "x": "nowhere", "y": "accounts"}}, "欄位"),
        ({"sql": "SELECT 1 AS one"}, "欄位"),  # the saved chart names columns it no longer has
        ({"grants": ["x"]}, "permission"),
        ({"code": "SELECT 1"}, ""),  # a key named for a secret
    ],
)
def test_bad_edits_are_refused_with_a_reason(
    web: AgentWeb, changes: dict[str, Any], says: str
) -> None:
    before = _working(web)
    outcome = _propose(web, "bi_analysis_edit", _edit(**changes))
    assert outcome.status == "failed" and outcome.failure.code == "proposal_refused"
    assert says in outcome.failure.message
    assert _working(web) == before


def test_a_create_on_a_saved_slug_points_at_the_edit_kind(web: AgentWeb) -> None:
    values = {"vault": DATASET, "slug": SLUG, "title": "x", "sql": "SELECT 1 AS a",
              "chart": {"type": "table"}}  # fmt: skip
    outcome = _propose(web, "bi_analysis", values)
    assert outcome.status == "failed" and "bi_analysis_edit" in outcome.failure.message


def test_a_save_meanwhile_makes_the_edit_stale(web: AgentWeb) -> None:
    card = _card(_propose(web, "bi_analysis_edit", _edit(title="新標題")))
    unit = _working(web)[f"analysis:{SLUG}"]
    analyses.save(_workspace(web), fixtures.VAULT_ID, {**unit, "slug": SLUG, "title": "別人改的"})
    stale = web.decide_card(card["card_id"], "apply")
    assert stale["code"] == "proposal_stale"
    assert _working(web)[f"analysis:{SLUG}"]["title"] == "別人改的"


def test_the_chat_reads_one_analysiss_definition_not_alls(web: AgentWeb) -> None:
    workspace = _workspace(web)
    (one,) = board.published_sections(workspace, fixtures.VAULT_ID, SLUG, {})
    unit = _working(web)[f"analysis:{SLUG}"]
    assert one["definition"]["code"] == unit["code"] and one["definition"]["kind"] == "sql"
    assert one["definition"]["params"] == unit["params"]
    every = board.published_sections(workspace, fixtures.VAULT_ID, "all", {})
    assert all("definition" not in section for section in every)


def test_a_published_edit_changes_only_that_analysiss_feed_digest(web: AgentWeb) -> None:
    """P4: what the feed gives Atlas moves only when the edit is published."""
    workspace = _workspace(web)

    def digests() -> dict[str, str]:
        listed = feed.listing(workspace, fixtures.VAULT_ID)
        return {a["slug"]: a["digest"] for a in listed["analyses"]}

    before = digests()
    chart = {"type": "line", "x": "region", "y": "accounts"}
    card = _card(_propose(web, "bi_analysis_edit", _edit(chart=chart)))
    assert web.decide_card(card["card_id"], "apply")["ok"] is True
    assert digests() == before  # staged only: the feed reads the published version

    vault.commit(workspace, fixtures.VAULT_ID, {"purpose": "改成折線圖"})
    pushed = vault.push(workspace, fixtures.VAULT_ID)
    assert pushed.get("ok", True) is not False, pushed
    assert digests() == before  # pushed, not yet published
    vault.tag(workspace, fixtures.VAULT_ID, {"name": "v2", "purpose": "改圖"})
    vault.publish(workspace, fixtures.VAULT_ID, {"tag": "v2", "confirm": True})

    after = digests()
    changed = {slug for slug in before if before[slug] != after.get(slug)}
    assert changed == {SLUG}
    published = feed.listing(workspace, fixtures.VAULT_ID)
    shown = next(a for a in published["analyses"] if a["slug"] == SLUG)
    assert shown["chart"] == chart
