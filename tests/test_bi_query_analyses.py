"""`bi__query` `analysis` names a saved analysis of the published version (BI P4).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.3: in a vault the chat asks for one
of its saved analyses (or `all`) with parameters and reads the published
version, never this PC's unpushed work; the coded names keep working until P5.
All data is fictional.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault_published import CONTEXT

from capabilities.bi_cards import vault
from capabilities.bi_cards.capability import QueryHandler, QueryRequest
from capabilities.runtime import CapabilityRefused
from scripts import bi_feed_fixtures as fixtures

DATASET = vault.dataset_name(fixtures.VAULT_ID)


def _joined(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    copy = tmp_path / "shared" / "vault"
    shutil.copytree(fixtures.VAULT_DIR, copy)
    fixtures.join(workspace, copy)
    return workspace


def _ask(ws: Path, **given: Any) -> dict[str, Any]:
    request = QueryRequest(dataset=DATASET, **given)
    return dict(asyncio.run(QueryHandler(ws)(CONTEXT, request)).model_dump())


def test_a_saved_analysis_is_answered_from_the_published_version(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    found = _ask(ws, analysis="accounts-by-region", params={"domain": "AIDC"})
    (section,) = found["analysis"]
    assert section["id"] == "accounts-by-region" and section["params"] == {"domain": "AIDC"}
    assert [r[1] for r in section["rows"]] == [2, 2]
    assert "發佈版本 v1" in found["scope_note"]
    robotics = _ask(ws, analysis="accounts-by-region", domain="robotics")["analysis"][0]
    assert "EU" not in {r[0] for r in robotics["rows"]}  # pushed after v1: not read
    aidc = _ask(ws, analysis="accounts-by-region", params={"domain": "aidc"})["analysis"][0]
    assert aidc["params"] == {"domain": "AIDC"}  # the enum value matched without case
    every = _ask(ws, analysis="all", domain="wireless")["analysis"]
    assert [s["id"] for s in every] == fixtures.LAYOUT["order"]
    nodes = every[0]
    assert nodes["columns"] == ["node", "solutions"] and nodes["flags"]


def test_an_unpublished_or_unknown_analysis_is_refused(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    for name in ("draft-only", "nothing-here"):
        with pytest.raises(CapabilityRefused) as refused:
            _ask(ws, analysis=name)
        assert refused.value.code == "analysis_unknown", name
    with pytest.raises(CapabilityRefused) as refused:
        _ask(ws, analysis="accounts-by-region", params={"domain": "space"})
    assert refused.value.code == "param_invalid"
    with pytest.raises(CapabilityRefused) as refused:
        _ask(ws, analysis="Not A Name")
    assert refused.value.code == "invalid_input"


def test_the_coded_names_still_answer_until_they_are_removed(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    (section,) = _ask(ws, analysis="funnel", domain="robotics")["analysis"]
    assert section["id"] == "17"  # the coded funnel: the fixture vault has no `funnel` analysis
