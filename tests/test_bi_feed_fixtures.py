"""The BI analysis feed on its fixture vault: golden answers and parameters.

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.1, §5, §6.1. The golden files
(`tests/fixtures/bi_feed/golden/`) are the contract Atlas vendors: they must be
exactly what the feed answers on the fixture vault, and both must be what
`scripts/bi_feed_fixtures.py` rebuilds. A feed request never runs a script; it
shows only the published version. All data is fictional.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from capabilities.bi_cards import analyses, feed, vault
from capabilities.bi_cards.store import BiStoreError
from scripts import bi_feed_fixtures as fixtures


@pytest.fixture(autouse=True)
def _empty_queue() -> Any:
    feed.drain()
    yield
    feed.drain()


def _joined(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    copy = tmp_path / "shared" / "vault"
    import shutil

    shutil.copytree(fixtures.VAULT_DIR, copy)
    workspace.mkdir()
    fixtures.join(workspace, copy)
    return workspace


def _golden(name: str) -> Any:
    return json.loads((fixtures.GOLDEN_DIR / name).read_text(encoding="utf-8"))


def test_the_golden_files_are_the_feeds_answers_on_the_fixture_vault(tmp_path: Path) -> None:
    manifest = _golden("requests.json")
    found = fixtures.answers(_joined(tmp_path))
    assert [r["file"] for r, _, _ in found] == [m["file"] for m in manifest["requests"]]
    for (request, status, body), listed in zip(found, manifest["requests"], strict=True):
        assert status == listed["status"], request["file"]
        assert body == _golden(request["file"]), request["file"]
    statuses = {m["file"]: m["status"] for m in manifest["requests"]}
    assert statuses["error-result_not_ready.json"] == 409
    assert statuses["error-origin_refused.json"] == 403
    assert {statuses[f"error-{c}.json"] for c in ("param_invalid", "param_unknown")} == {400}


def test_the_fixture_and_golden_files_rebuild_byte_for_byte() -> None:
    assert fixtures.main(["--check"]) == 0


def test_the_rebuild_check_ignores_empty_folders_git_cannot_keep(tmp_path: Path) -> None:
    left, right = tmp_path / "committed", tmp_path / "rebuilt"
    for side in (left, right):
        side.mkdir()
        (side / "repo.json").write_text("{}", encoding="utf-8")
    (right / "sources" / "nested").mkdir(parents=True)  # a fresh checkout never has these
    assert fixtures._differences(left, right) == []
    (right / "sources" / "nested" / "card.md").write_text("x", encoding="utf-8")
    assert fixtures._differences(left, right) == ["sources"]


def test_only_the_published_version_is_served(tmp_path: Path) -> None:
    workspace = _joined(tmp_path)
    head = vault.Vault(workspace, fixtures.VAULT_ID).repo.head()
    listed = feed.listing(workspace, fixtures.VAULT_ID)
    assert listed["version"]["tag"] == "v1" and listed["version"]["commit"] != head
    assert "draft-only" not in {a["slug"] for a in listed["analyses"]}
    working = analyses.listing(workspace, fixtures.VAULT_ID)["analyses"]
    assert "draft-only" in {a["slug"] for a in working}  # the pushed head has it
    rows = feed.result(workspace, fixtures.VAULT_ID, "accounts-by-region", {})["rows"]
    assert "EU" not in {r[0] for r in rows}  # the card pushed after v1


def test_a_feed_request_never_runs_a_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _joined(tmp_path)
    monkeypatch.setattr(feed, "on_queued", None)  # no worker: this test drains the queue itself
    ran: list[str] = []
    real = analyses.run

    def counting(db: Path, kind: str, code: str, params: Any = None) -> dict[str, Any]:
        ran.append(kind)
        return real(db, kind, code, params)

    analyses.run = counting  # type: ignore[assignment]
    try:
        for _ in range(2):
            status, body = feed.answer(
                workspace, "GET", f"{feed.PREFIX}vaults/{fixtures.VAULT_ID}/analyses/"
                "tech-updates/result", "domain=AIDC", None,
            )  # fmt: skip
            assert (status, body["code"]) == (409, "result_not_ready")
        assert ran == [] and feed.queued() == 1  # queued once, not run
        status, body = feed.answer(
            workspace, "GET", f"{feed.PREFIX}vaults/{fixtures.VAULT_ID}/analyses/"
            "node-coverage/result", "", "http://localhost:5173",
        )  # fmt: skip
        assert status == 200 and ran == ["sql"]  # SQL is computed on request
        assert feed.drain() == 1 and ran == ["sql", "python"]
        done = feed.result(workspace, fixtures.VAULT_ID, "tech-updates", {"domain": "AIDC"})
        assert done["rows"] == [["2026-09", 1], ["2026-10", 1]] and len(ran) == 2  # cached
    finally:
        analyses.run = real


def test_a_failed_analysis_is_cached_as_a_failure(tmp_path: Path) -> None:
    workspace = _joined(tmp_path)
    target = vault.Vault(workspace, fixtures.VAULT_ID)
    request = feed._Request(workspace, fixtures.VAULT_ID, "accounts-by-region", {})
    request.item = {**request.item, "code": "SELECT nope FROM nowhere"}
    record = request.compute()
    assert record["error"]["code"] == "result_failed"
    with pytest.raises(feed.FeedError) as refused:
        feed.result(workspace, fixtures.VAULT_ID, "accounts-by-region", {})
    assert (refused.value.status, refused.value.code) == (409, "result_failed")
    assert request.path.is_relative_to(target.local / feed.RESULTS_DIR)


# -- parameters and requirements (design §4.1) ------------------------------------------


def test_parameters_are_checked_and_resolved() -> None:
    domain = {"type": "enum", "values": ["robotics", "AIDC"]}
    params = {
        "domain": domain,
        "include_sample": {"type": "bool", "default": True},
        "today": {"type": "date", "default": "today"},
        "word": {"type": "text"},
    }
    assert analyses.params_problem(params) is None
    resolved = analyses.resolve_params(params, {}, None, today="2026-11-01")
    assert resolved == {
        "domain": "robotics",
        "include_sample": True,
        "today": "2026-11-01",
        "word": "",
    }
    given = {"domain": "AIDC", "include_sample": "false", "today": "2026-01-31", "word": "x"}
    assert analyses.resolve_params(params, given, None, today="2026-11-01") == {
        "domain": "AIDC",
        "include_sample": False,
        "today": "2026-01-31",
        "word": "x",
    }
    for wrong in ({"domain": "space"}, {"include_sample": "maybe"}, {"today": "31.1.2026"},
                  {"word": "x" * 201}, {"other": "1"}):  # fmt: skip
        with pytest.raises(BiStoreError) as refused:
            analyses.resolve_params(params, wrong, None, today="2026-11-01")
        assert refused.value.code == "param_invalid"
    for bad in (
        {"Domain": domain},
        {"domain": {"type": "list"}},
        {"domain": {"type": "enum"}},
        {"domain": {**domain, "default": "space"}},
        {"domain": {"type": "enum", "values_from": "account domain"}},
        {"flag": {"type": "bool", "default": "yes"}},
        {"day": {"type": "date", "default": "tomorrow"}},
        {"word": {"type": "text", "extra": 1}},
    ):
        assert analyses.params_problem(bad) is not None, bad
    assert analyses.requires_problem({"types": ["Account"], "fields": ["Account.region"]}) is None
    assert analyses.requires_problem({"fields": ["region"]}) is not None
    assert analyses.requires_problem({"types": "Account"}) is not None


def test_enum_values_and_requirements_come_from_the_schema(tmp_path: Path) -> None:
    workspace = _joined(tmp_path)
    registry = vault.Vault(workspace, fixtures.VAULT_ID)._registry()
    from_domain = {"type": "enum", "values_from": "Account.domain"}
    assert analyses.enum_values(from_domain, registry) == list(registry.domains)
    segment = analyses.enum_values({"type": "enum", "values_from": "Account.segment"}, registry)
    assert "robotics-amr" in segment
    assert analyses.enum_values({"type": "enum", "values_from": "Nope.x"}, registry) == []
    assert analyses.requires_met({"types": ["Account"], "fields": ["Node.layer"]}, registry)
    assert not analyses.requires_met({"fields": ["Account.tech_areas"]}, registry)
    assert not analyses.requires_met({"types": ["Robot"]}, registry)
    assert analyses.requires_met(None, None) and not analyses.requires_met({"types": ["A"]}, None)


def test_sql_and_scripts_receive_the_parameters(tmp_path: Path) -> None:
    workspace = _joined(tmp_path)
    db = vault.Vault(workspace, fixtures.VAULT_ID).db_path
    sql = "SELECT count(*) AS n FROM card_values WHERE entity_type = :t AND field = 'name'"
    assert analyses.run_sql(db, sql, params={"t": "Node"})["rows"] == [[8]]
    script = 'result = [{"t": PARAMS["t"], "n": len(query("SELECT 1 FROM cards"))}]'
    assert analyses.run_python(db, script, params={"t": "Node"})["rows"] == [["Node", 35]]
    with pytest.raises(BiStoreError, match="SQL"):
        analyses.run_sql(db, sql)  # :t not given


def test_a_saved_analysis_keeps_params_and_runs_with_its_defaults(tmp_path: Path) -> None:
    workspace = _joined(tmp_path)
    given = {**fixtures.ANALYSES[0], "slug": "accounts-again"}
    saved = analyses.save(workspace, fixtures.VAULT_ID, given)
    assert saved["table"]["rows"][0] == ["TW", 3]
    found = analyses.run_saved(workspace, fixtures.VAULT_ID, "accounts-again", {"domain": "AIDC"})
    assert found["params"] == {"domain": "AIDC"} and found["table"]["rows"] == [
        ["TW", 2],
        ["US", 2],
    ]
    wrong = {**given, "params": {"domain": {"type": "enum"}}}
    with pytest.raises(BiStoreError, match="enum"):
        analyses.save(workspace, fixtures.VAULT_ID, wrong)
    plain = {"title": "t", "slug": "plain", "kind": "sql", "code": "SELECT 1 AS one"}
    key, value = analyses.checked(plain)
    assert "params" not in value and "requires" not in value  # the old value, the old digest


def test_the_dashboard_order_leaves_hidden_ones_out() -> None:
    units = {feed.DASHBOARD_UNIT: json.dumps({"order": ["c", "x", "a"], "hidden": ["b"]})}
    assert feed.order(units, ["a", "b", "c", "d"]) == ["c", "a", "d"]
    assert feed.order({feed.DASHBOARD_UNIT: "not json"}, ["b", "a"]) == ["a", "b"]
    assert feed.order({}, []) == []
