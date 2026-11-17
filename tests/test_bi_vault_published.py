"""Knowledge repositories R5, BI side (`docs/phases/KNOWLEDGE_REPO.md` §7, §9).

The Agent reads a vault's published version only, the pushed head while it
was never published, and never a PC's unpushed work; `REPO.md` and the
schema's readable `.md` are written by the PC that pushes or publishes; the
page gets units in words. Two PCs as in `test_bi_vault.py`. All data is
fictional.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from test_bi_vault import (
    _call,
    _card,
    _commit,
    _edit,
    _import,
    _ok,
    _push,
    _row,
    _status,
    _sync,
    _two_pcs,
)

from aep_bi.cards import vault
from aep_bi.cards.capability import QueryHandler, QueryRequest
from common.execution import RequestContext, TraceIdentifiers

CONTEXT = RequestContext(
    trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
    actor="tester",
    namespace="engineering",
    message="bi",
    channel="local",
    session_id="s-1",
)


def _ask(ws: Path, dataset: str) -> dict[str, Any]:
    request = QueryRequest(dataset=dataset, entity_type="Technology", text="TSN")
    return dict(asyncio.run(QueryHandler(ws)(CONTEXT, request)).model_dump())


def _value(answer: dict[str, Any]) -> Any:
    (card,) = answer["cards"]
    return card["fields"]["standard_body"]["value"]


def test_the_agent_reads_the_pushed_head_until_a_version_is_published(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"))
    assert _ask(a, dataset)["cards"] == ()  # the import is a local commit, not pushed yet
    _push(a, vault_id)
    answer = _ask(a, dataset)
    assert _value(answer) == "IEEE" and "還沒有發佈過" in answer["scope_note"]
    # This PC's uncommitted edit is on the page, never in the Agent's answer.
    _ok(_edit(a, dataset, "TSN", "standard_body", "draft", "alice"))
    assert _card(a, dataset, "TSN")["fields"]["standard_body"]["value"] == "draft"
    assert _value(_ask(a, dataset)) == "IEEE"
    assert _status(a, vault_id)["reads"] == {"tag": None, "commit": _status(a, vault_id)["head"]}


def test_the_agent_answers_from_the_published_tag_while_the_head_moves_on(
    tmp_path: Path,
) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"))
    _push(a, vault_id)
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": "v1", "purpose": "第一版"}))
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/publish", {"tag": "v1", "confirm": True}))
    _ok(_edit(a, dataset, "TSN", "standard_body", "IEEE 802.1", "alice"))
    _commit(a, vault_id, "標準組織寫得更精確")
    _push(a, vault_id)
    answer = _ask(a, dataset)
    assert _value(answer) == "IEEE" and "發佈版本 v1" in answer["scope_note"]
    # The other PC reads the same published version once the records arrive.
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _value(_ask(b, dataset)) == "IEEE"
    assert _status(b, vault_id)["reads"]["tag"] == "v1"
    # Publishing a newer tag moves what the Agent reads.
    _ok(_call(b, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": "v2", "purpose": "第二版"}))
    _ok(_call(b, "POST", f"/api/bi/vaults/{vault_id}/publish", {"tag": "v2", "confirm": True}))
    assert _value(_ask(b, dataset)) == "IEEE 802.1"


def test_repo_md_and_the_schema_document_are_written(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    folder = drive.parent("a") / vault_id
    readable = folder / "schemas" / "bi.schema__v1.1@5.0.0.md"
    assert readable.read_text(encoding="utf-8").startswith("# ")
    _import(a, dataset, _row("TSN", standard_body="IEEE"), filename="tech.csv")
    _push(a, vault_id)
    text = (folder / "REPO.md").read_text(encoding="utf-8")
    assert "匯入 tech.csv" in text and "bi.schema__v1.1@5.0.0.md" in text
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": "v1", "purpose": "第一版"}))
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/publish", {"tag": "v1", "confirm": True}))
    assert "v1" in (folder / "REPO.md").read_text(encoding="utf-8")


def test_pending_changes_and_push_conflicts_name_the_card_and_field(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"))
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    _ok(_edit(a, dataset, "TSN", "standard_body", "IEEE 802.1", "alice"))
    pending = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    assert [c["label"] for c in pending["uncommitted"]] == ["Technology「TSN」 的 standard_body"]
    _commit(a, vault_id, "a 的修改")
    _push(a, vault_id)
    _ok(_edit(b, dataset, "TSN", "standard_body", "IETF", "bob"))
    _commit(b, vault_id, "b 的修改")
    drive.deliver("a", "b", vault_id)
    (conflict,) = _push(b, vault_id)["conflicts"]
    assert conflict["label"] == "Technology「TSN」 的 standard_body"
    assert vault.unit_label({}, "schema") == "schema 版本"
