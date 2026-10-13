"""Review proposals a person decides on, and where accepted ones go (E3-E5, 2026-10-13)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from test_agent_web import base, fetch
from test_knowledge_pipeline_web import _step, served_pipeline  # noqa: F401 - fixture
from test_knowledge_scope import _project

from host_runtime.experience_proposals import ProposalError, ProposalStore
from host_runtime.experience_review import REVIEWS_DIR, Finding, Proposal, ReviewReport
from host_runtime.review_routes import draft_question, question_folder, resolve_rule
from host_runtime.web import AgentWebServer
from host_runtime.web_page import PAGE


def _report(workspace: Path, *findings: Finding) -> None:
    report = ReviewReport(review_id="review-20261013T000000-abcd",
                          started_at="2026-10-13T00:00:00+00:00",
                          finished_at="2026-10-13T00:01:00+00:00", findings=findings)
    (workspace / REVIEWS_DIR).mkdir(parents=True, exist_ok=True)
    (workspace / REVIEWS_DIR / f"{report.review_id}.json").write_text(
        report.model_dump_json(), encoding="utf-8")


def _finding(kind: str, target: str, text: str = "Every claim carries a date.") -> Finding:
    return Finding(group=f"knowledge|{kind}|-", case_ids=("case-1",), cases=1,
                   cause="rule_missing", diagnosis="Answers lacked dates (case 1).",
                   proposal=Proposal.model_validate({"kind": kind, "target": target,
                                                     "text": text}),
                   confidence="high", confirm="a dated answer")


def test_findings_become_proposals_a_person_decides(tmp_path: Path) -> None:
    _report(tmp_path, _finding("rule_edit", "skills/ask-knowledge/SKILL.md"),
            Finding(group="x", case_ids=(), cases=0, error="RuntimeError: 503"),
            _finding("issue", "workflow handler"))
    store = ProposalStore(tmp_path)
    assert store.sync() == 2 and store.sync() == 0  # an errored group is not a proposal
    first, issue = sorted(store.all(), key=lambda p: p.proposal_id)
    assert first.kind == "rule_edit" and first.status == "proposed"
    with pytest.raises(ProposalError, match="reason_required"):
        store.decide(first.proposal_id, "reject", "leo.chi", "  ")
    rejected = store.decide(first.proposal_id, "reject", "leo.chi", "dates are already required")
    assert (rejected.status, rejected.reason) == ("rejected", "dates are already required")
    with pytest.raises(ProposalError, match="proposal_not_"):
        store.decide(first.proposal_id, "snooze", "leo.chi")
    assert store.decide(first.proposal_id, "reopen", "leo.chi").status == "proposed"
    snoozed = store.decide(issue.proposal_id, "snooze", "leo.chi")
    assert snoozed.status == "snoozed" and snoozed.snooze_until is not None
    store.save(snoozed.model_copy(update={"snooze_until": "2026-01-01T00:00:00+00:00"}))
    assert store.get(issue.proposal_id).status == "proposed"  # the snooze ran out


def test_targets_resolve_to_vault_rules_and_question_folders(tmp_path: Path) -> None:
    pipeline, root = _project(tmp_path)
    found = resolve_rule("ingest-vna rules in skills/ingest-vna/SKILL.md", {"rs-k": root})
    assert found is not None and (found.base, found.path, found.scope) == (
        "rs-k", "skills/ingest-vna/SKILL.md", "Productions/VNA")
    legacy = resolve_rule("the ask-knowledge answer rules", {"rs-k": root})
    assert legacy is not None and legacy.scope == "Knowledge"  # by the ask-<folder> name
    assert resolve_rule("platform Skill company-agent/knowledge-query", {"rs-k": root}) is None
    assert question_folder("checks/questions/market", root) == "Market"
    _report(tmp_path, _finding("test_question", "market", "Which VNA covers 67 GHz?"))
    store = ProposalStore(tmp_path)
    store.sync()
    draft = draft_question(store.all()[0])
    assert "# Which VNA covers 67 GHz?" in draft and "（請專家填寫）" in draft


def test_a_question_written_in_a_sandbox_is_merged_and_scoped(tmp_path: Path) -> None:
    pipeline, _ = _project(tmp_path)
    market = pipeline.create_sandbox("rs-k", "m", "leo", scope="Market").sandbox_id
    text = "# A question\n\n必須提到:\n  - FSW\n"
    pipeline.write_rule(market, "checks/questions/market/q.md", text)
    pipeline.write_rule(market, "checks/questions/market_production/q.md", text)
    for outside in ("checks/questions/productions/q.md", "checks/questions/q.md"):
        with pytest.raises(Exception, match="rule_outside_scope"):
            pipeline.write_rule(market, outside, text)
    changes = {c.path for c in pipeline.merge(market).changes}
    assert {"checks/questions/market/q.md", "checks/questions/market_production/q.md"} <= changes


def test_accepting_a_rule_edit_opens_a_review_sandbox(
    served_pipeline: tuple[AgentWebServer, Path],  # noqa: F811 - fixture
) -> None:
    server, vault = served_pipeline
    (vault / "skills/ingest-notes").mkdir(parents=True)
    (vault / "skills/ingest-notes/SKILL.md").write_text(
        "---\nname: ingest-notes\nmode: procedure\napplies_to: raw/notes\n---\n\n# rules\n",
        encoding="utf-8")
    workspace = server.web.runtime.layout.workspace_root
    _report(workspace, _finding("rule_edit", "skills/ingest-notes/SKILL.md"),
            _finding("knowledge_gap", "notes", "No source covers the 2026 price list."))
    url = base(server) + "/api/reviews"
    assert fetch(url).status == 401
    listed = json.loads(fetch(url, token=server.token).body)
    rule = next(p for p in listed["proposals"] if p["kind"] == "rule_edit")
    gap = next(p for p in listed["proposals"] if p["kind"] == "knowledge_gap")
    decided = json.loads(fetch(url + "/decide", token=server.token, body={
        "proposal_id": gap["proposal_id"], "action": "accept"}).body)
    assert next(p for p in decided["proposals"] if p["kind"] == "knowledge_gap")["route"] == "gap"
    assert json.loads(fetch(url + "/decide", token=server.token, body={
        "proposal_id": rule["proposal_id"], "action": "accept"}).body)["ok"]
    deadline = time.monotonic() + 60
    while True:
        listed = json.loads(fetch(url, token=server.token).body)
        routed = next(p for p in listed["proposals"] if p["kind"] == "rule_edit")
        if (routed["route"] or "").startswith("sandbox:") or time.monotonic() > deadline:
            break
        time.sleep(0.3)
    sandbox = routed["route"][len("sandbox:"):]
    assert routed["outcome"] == "in the sandbox, not pushed yet"
    shown = json.loads(fetch(base(server) + "/api/knowledge/review-proposal?sandbox_id="
                             + sandbox, token=server.token).body)
    assert shown["proposal"]["path"] == "skills/ingest-notes/SKILL.md"
    assert shown["proposal"]["text"] == "Every claim carries a date."
    assert listed["counts"]["accepted"] == 2
    tasks = json.loads(fetch(base(server) + "/api/tasks", token=server.token).body)["tasks"]
    assert tasks[0]["kind"] == "review" and tasks[0]["status"] == "succeeded"


def test_the_reviews_tab_and_the_knowledge_banner_are_on_the_page() -> None:
    for hook in ('id="nav-reviews"', 'id="panel-reviews"', "/api/reviews/decide",
                 'id="kp-review"', "/api/knowledge/review-proposal", 'id="rv-gaps"'):
        assert hook in PAGE
    # The review settings moved off the Knowledge tab onto the Reviews tab.
    assert PAGE.index('id="xp-card"') > PAGE.index('id="panel-reviews"')
