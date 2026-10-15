"""The Agent Web Knowledge tab's routes (K1.4, owner 2026-10-11)."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch
from test_host_wiring import membership_record, workspace
from test_knowledge_pipeline_host import _grants
from test_knowledge_sandbox import _base, _snapshot

from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE


@pytest.fixture
def served_pipeline(tmp_path: Path) -> Iterator[tuple[AgentWebServer, Path]]:
    vault = _base(tmp_path)
    config, _ = workspace(
        tmp_path,
        membership=membership_record(),
        grants=_grants(),
        config_changes={"knowledge_pipeline": {"vaults": [{"name": "k-test", "root": str(vault)}]}},
    )
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server, vault
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _step(server: AgentWebServer, step: str, arguments: dict[str, Any]) -> dict[str, Any]:
    reply = fetch(
        base(server) + "/api/knowledge/pipeline/call",
        token=server.token,
        body={"step": step, "arguments": arguments},
    )
    assert reply.status == 200
    loaded: dict[str, Any] = json.loads(reply.body)
    return loaded


def test_the_tab_lists_bases_and_runs_steps_in_a_sandbox(
    served_pipeline: tuple[AgentWebServer, Path],
) -> None:
    server, vault = served_pipeline
    before = _snapshot(vault)
    info = json.loads(fetch(base(server) + "/api/knowledge/pipeline", token=server.token).body)
    assert info == {
        "enabled": True,
        "bases": ["k-test"],
        "vaults": [{"name": "k-test", "project": False, "asset": None}],
    }
    made = _step(server, "sandbox-create", {"base": "k-test", "label": "web trial"})
    assert made["ok"], made
    sandbox = made["data"]["sandbox_id"]
    assert _step(
        server, "drop-add", {"sandbox_id": sandbox, "name": "a.txt", "data_base64": "aGVsbG8K"}
    )["ok"]
    converted = _step(server, "convert", {"sandbox_id": sandbox, "mode": "apply"})
    assert converted["data"]["items"][0]["status"] == "written"
    linted = _step(server, "lint", {"sandbox_id": sandbox})
    assert linted["ok"] and linted["data"]["pages"] >= 1
    assert _snapshot(vault) == before


def test_only_pipeline_steps_can_be_called_and_the_token_is_required(
    served_pipeline: tuple[AgentWebServer, Path],
) -> None:
    server, _ = served_pipeline
    assert _step(server, "read-file", {})["code"] == "unknown_pipeline_step"
    refused = _step(server, "lint", {"sandbox_id": "../escape"})
    assert refused == {"ok": False, "code": "invalid_sandbox_id"}
    assert (
        fetch(
            base(server) + "/api/knowledge/pipeline/call",
            body={"step": "sandbox-list", "arguments": {}},
        ).status
        == 401
    )
    assert fetch(base(server) + "/api/knowledge/pipeline").status == 401


def test_the_page_has_the_knowledge_tab() -> None:
    assert 'id="nav-knowledge"' in PAGE and 'id="panel-knowledge"' in PAGE
    assert "/api/knowledge/pipeline/call" in PAGE


def test_publish_is_a_person_route_that_needs_the_host_file(
    served_pipeline: tuple[AgentWebServer, Path],
) -> None:
    server, _ = served_pipeline
    url = base(server) + "/api/knowledge/pipeline/publish"
    body = {"base": "k-test", "candidate_root": "x"}
    assert fetch(url, body=body).status == 401
    reply = fetch(url, token=server.token, body=body)
    # This server was started without host.json, so it has nothing to switch.
    assert json.loads(reply.body) == {"ok": False, "code": "publish_unavailable"}
    assert _step(server, "publish", {})["code"] == "unknown_pipeline_step"
    assert "/api/knowledge/pipeline/publish" in PAGE and 'id="kp-merge"' in PAGE


def test_push_and_refresh_routes_need_the_token_and_a_sandbox(
    served_pipeline: tuple[AgentWebServer, Path],
) -> None:
    server, _ = served_pipeline
    body = {"sandbox_id": "sb-missing-000000", "sets": [], "resolutions": {}}
    assert fetch(base(server) + "/api/knowledge/push/start", body=body).status == 401
    reply = json.loads(
        fetch(base(server) + "/api/knowledge/push/start", token=server.token, body=body).body
    )
    assert reply == {"ok": False, "code": "unknown_sandbox"}
    status = json.loads(
        fetch(
            base(server) + "/api/knowledge/push?sandbox_id=sb-missing-000000", token=server.token
        ).body
    )
    assert status == {"ok": False, "code": "unknown_sandbox"}
    refresh = json.loads(
        fetch(
            base(server) + "/api/knowledge/refresh", token=server.token, body={"base": "k-test"}
        ).body
    )
    assert refresh == {"ok": False, "code": "refresh_unavailable"}
    assert 'id="kp-push"' in PAGE and "/api/knowledge/push/start" in PAGE


def test_re_ingest_runs_in_the_background_and_reports_each_document(
    served_pipeline: tuple[AgentWebServer, Path],
) -> None:
    server, vault = served_pipeline
    before = _snapshot(vault)
    url = base(server) + "/api/knowledge/reingest"
    made = _step(server, "sandbox-create", {"base": "k-test", "label": "re"})
    sandbox = made["data"]["sandbox_id"]
    assert _step(
        server, "drop-add", {"sandbox_id": sandbox, "name": "a.txt", "data_base64": "aGVsbG8K"}
    )["ok"]
    raw_ref = _step(server, "convert", {"sandbox_id": sandbox, "mode": "apply"})["data"]["items"][
        0
    ]["raw_ref"]
    body = {"sandbox_id": sandbox, "raw_refs": [raw_ref]}
    assert fetch(url + "/start", body=body).status == 401
    refused = json.loads(
        fetch(
            url + "/start",
            token=server.token,
            body={"sandbox_id": sandbox, "raw_refs": ["wiki/x.md"]},
        ).body
    )
    assert refused == {"ok": False, "code": "no_raw_documents"}
    assert json.loads(
        fetch(url + "/stop", token=server.token, body={"sandbox_id": sandbox}).body
    ) == {"ok": False, "code": "reingest_not_running"}
    assert json.loads(fetch(url + "/start", token=server.token, body=body).body)["ok"]
    deadline = time.monotonic() + 30
    while True:
        run = json.loads(fetch(f"{url}?sandbox_id={sandbox}", token=server.token).body)["run"]
        if run["status"] == "finished" or time.monotonic() > deadline:
            break
        time.sleep(0.2)
    # This Host has no model, so planning fails; the run still records it.
    assert run["status"] == "finished" and run["remaining"] == []
    assert [(i["raw_ref"], i["status"]) for i in run["items"]] == [(raw_ref, "failed")]
    assert _snapshot(vault) == before


def test_the_skill_assistant_route_only_edits_rule_files(
    served_pipeline: tuple[AgentWebServer, Path],
) -> None:
    server, _ = served_pipeline
    url = base(server) + "/api/knowledge/skill-assist"
    sandbox = _step(server, "sandbox-create", {"base": "k-test", "label": "assist"})
    body: dict[str, Any] = {
        "sandbox_id": sandbox["data"]["sandbox_id"],
        "path": "wiki/x.md",
        "current": "",
        "turns": [{"role": "user", "text": "hi"}],
    }
    assert fetch(url, body=body).status == 401

    def finished(reply: dict[str, Any]) -> dict[str, Any]:
        # The reply runs in the background; the page polls its state.
        assert reply["ok"] and reply["job_id"]
        for _ in range(50):
            status = json.loads(fetch(url + "?job=" + reply["job_id"], token=server.token).body)
            if status["state"] in ("done", "failed"):
                assert status["history"][0] == "collecting"
                return dict(status["result"])
            time.sleep(0.1)
        raise AssertionError("the assistant never finished")

    refused = finished(json.loads(fetch(url, token=server.token, body=body).body))
    assert refused == {"ok": False, "code": "not_a_rule_file"}
    body["path"] = "skills/ingest-market/SKILL.md"
    # This test host has no Knowledge asking model installed.
    reply = finished(json.loads(fetch(url, token=server.token, body=body).body))
    assert reply == {"ok": False, "code": "skill_assist_unavailable"}
    unknown = json.loads(fetch(url + "?job=nope", token=server.token).body)
    assert unknown == {"ok": False, "code": "unknown_job"}


def test_the_experience_review_routes_keep_settings_and_report(
    served_pipeline: tuple[AgentWebServer, Path],
) -> None:
    server, _ = served_pipeline
    assert fetch(base(server) + "/api/experience").status == 401
    info = json.loads(fetch(base(server) + "/api/experience", token=server.token).body)
    assert info["settings"] == {"retention_days": 30, "nightly": True}
    assert info["open"] == 0 and info["review"] is None
    saved = json.loads(
        fetch(
            base(server) + "/api/experience/settings",
            token=server.token,
            body={"retention_days": 14, "nightly": False},
        ).body
    )
    assert saved["settings"] == {"retention_days": 14, "nightly": False}
    bad = json.loads(
        fetch(
            base(server) + "/api/experience/settings",
            token=server.token,
            body={"retention_days": 0},
        ).body
    )
    assert bad == {"ok": False, "code": "experience_settings_invalid"}
    # Harvesting reads this host's own records (the conversation limit is the
    # state's maximum of 100).
    assert server.web.experience_harvest() == 0
    # Without a Knowledge asking model the review cannot run and says so.
    assert server.web.experience_review() == {"ok": False, "code": "experience_review_unavailable"}


def test_a_project_vault_is_offered_first(tmp_path: Path) -> None:
    # Live 2026-10-14: the start form defaulted to a test vault listed first, and a new
    # sandbox pulled one file instead of the project's 46.
    test_vault = _base(tmp_path / "t")
    project = _base(tmp_path / "p")
    config, _ = workspace(
        tmp_path,
        membership=membership_record(),
        grants=_grants(),
        config_changes={
            "knowledge_pipeline": {
                "vaults": [
                    {"name": "k-test", "root": str(test_vault)},
                    {"name": "rs-project", "root": str(project), "knowledge_asset": "rs-knowledge"},
                ]
            }
        },
    )
    with build_runtime(config) as runtime:
        info = AgentWeb(runtime).knowledge_pipeline()
    assert info["bases"] == ["rs-project", "k-test"]
    assert info["vaults"][0] == {"name": "rs-project", "project": True, "asset": "rs-knowledge"}
