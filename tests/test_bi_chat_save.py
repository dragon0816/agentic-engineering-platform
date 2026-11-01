"""Save a chat chart as a vault analysis, with the owner's approval (BI C3).

`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` C3: the chat model
proposes through `propose_change` kind `bi_analysis`; the card shows the
analysis and its result on the vault's working copy; only Apply in Agent Web
stages `analysis:<slug>` (Telegram cannot); commit, push and publish stay the
person's. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_ai_proposed_changes import _card, _propose
from test_bi_chat_charts import DATASET, _host
from test_bi_chat_sql import BY_REGION
from test_host_wiring import host_json

from capabilities.bi_cards import analyses, vault
from common.change_proposal import KINDS, PROPOSE_GUIDANCE, TELEGRAM_KINDS
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb
from scripts import bi_feed_fixtures as fixtures

CHART = {"type": "bar", "x": "region", "y": "accounts"}


@pytest.fixture
def web(tmp_path: Path) -> Any:
    config, layout = _host(tmp_path)
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        agent_web = AgentWeb(runtime, config_path=path)
        agent_web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        yield agent_web


def _values(**changes: Any) -> dict[str, Any]:
    return {
        "vault": DATASET,
        "slug": "accounts-all-regions",
        "title": "全部地區的客戶數",
        "question": "客戶分布在哪些地區？",
        "chart": CHART,
        "sql": BY_REGION,
        **changes,
    }


def _working(web: AgentWeb) -> dict[str, Any]:
    workspace = web.runtime.layout.workspace_root
    return dict(vault.Vault(workspace, fixtures.VAULT_ID).repo.working_units())


def test_the_kind_is_offered_and_never_applied_from_telegram() -> None:
    assert "bi_analysis" in KINDS and "bi_analysis" not in TELEGRAM_KINDS
    assert "BI chart" in PROPOSE_GUIDANCE


def test_a_proposal_changes_nothing_and_apply_stages_the_analysis(web: AgentWeb) -> None:
    before = _working(web)
    card = _card(_propose(web, "bi_analysis", _values(), "keep this chart"))
    assert card["status"] == "pending" and card["web_only"] is True
    rows = {row["label"]: row["after"] for row in card["rows"]}
    assert rows["Knowledge base"] == fixtures.VAULT_ID
    assert (
        rows["SQL"] == BY_REGION
        and rows["Chart"] == '{"type": "bar", "x": "region", "y": "accounts"}'
    )
    assert rows["Result on the working copy"].startswith(
        "6 rows: CN, 1; DE, 1; EU, 1"
    )  # EU: pushed, not published
    assert _working(web) == before  # nothing staged by the proposal

    refused = web.decide_card(card["card_id"], "apply", "telegram")
    assert refused["code"] == "web_only" and _working(web) == before

    applied = web.decide_card(card["card_id"], "apply")
    assert applied["ok"] is True and "commit, push and publish" in applied["message"]
    unit = _working(web)["analysis:accounts-all-regions"]
    assert unit["kind"] == "sql" and unit["code"] == BY_REGION and unit["chart"] == CHART
    # Only staged: the published version the chat and Atlas read is unchanged.
    workspace = web.runtime.layout.workspace_root
    published = {
        a["slug"]
        for a in analyses.saved(
            vault.Vault(workspace, fixtures.VAULT_ID).repo.state_at(
                vault.Vault(workspace, fixtures.VAULT_ID).reads()["commit"]
            )
        )
    }
    assert "accounts-all-regions" not in published


def test_a_saved_sql_analysis_shown_in_the_chat_is_copied(web: AgentWeb) -> None:
    values = _values(slug="regions-copy", sql=None)
    del values["sql"]
    values["from_analysis"] = {"vault": DATASET, "slug": "accounts-by-region"}
    card = _card(_propose(web, "bi_analysis", values))
    assert web.decide_card(card["card_id"], "apply")["ok"] is True
    copied = _working(web)["analysis:regions-copy"]
    original = _working(web)["analysis:accounts-by-region"]
    assert copied["code"] == original["code"] and copied["params"] == original["params"]


@pytest.mark.parametrize(
    ("changes", "says"),
    [
        ({"vault": "vault-nowhere"}, "No such knowledge base"),
        ({"slug": "accounts-by-region"}, "already has an analysis"),
        ({"slug": "Not A Slug"}, ""),
        ({"sql": "DELETE FROM cards"}, "not authorized"),
        ({"chart": {"type": "bar", "x": "nowhere", "y": "accounts"}}, "欄位"),
        ({"from_analysis": {"vault": DATASET, "slug": "accounts-by-region"}}, "either sql"),
        ({"from_analysis": {"vault": DATASET, "slug": "tech-updates"}, "sql": ""}, "SQL analysis"),
        ({"from_analysis": {"vault": DATASET, "slug": "draft-only"}, "sql": ""}, "no such"),
        ({"grants": ["x"]}, "permission"),
    ],
)
def test_bad_proposals_are_refused_with_a_reason(
    web: AgentWeb, changes: dict[str, Any], says: str
) -> None:
    before = _working(web)
    outcome = _propose(web, "bi_analysis", _values(**changes))
    assert outcome.status == "failed" and outcome.failure.code == "proposal_refused"
    assert says in outcome.failure.message
    assert _working(web) == before


def test_a_save_meanwhile_makes_the_card_stale(web: AgentWeb) -> None:
    card = _card(_propose(web, "bi_analysis", _values()))
    workspace = web.runtime.layout.workspace_root
    analyses.save(workspace, fixtures.VAULT_ID, {**_values(), "kind": "sql", "code": BY_REGION})
    stale = web.decide_card(card["card_id"], "apply")
    assert stale["code"] == "proposal_stale"
