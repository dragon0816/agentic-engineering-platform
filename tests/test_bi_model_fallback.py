"""BI on a host with a model and no wiki Knowledge asset (owner 2026-11-03).

The real Agent Web routes and the real model chain, with a stub Gateway behind
it: nothing is installed for Knowledge, and every BI feature that uses the model
works, always behind the host's data approval. All data is fictional.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import fetch
from test_bi_extract import MEETING_ANSWER, NOTE
from test_host_models import GatewayReply, binding, endpoint
from test_host_wiring import ready

from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from capabilities.workflow_author.handlers import DRAFT_SPEC
from host_runtime import bi_cards_api, skill_packs
from host_runtime.assets import shipped
from host_runtime.host import HostRuntime, build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from models.approved import ApprovedModelClient


class StubGateway:
    """An OpenAI-compatible Gateway: card candidates for a request that offers
    no tools, plain words for the Agent; `failing` many errors first."""

    def __init__(self, failing: int = 0) -> None:
        self.bodies: list[dict[str, Any]] = []
        self.failing = failing

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        payload = json.loads(body)
        self.bodies.append(payload)
        if self.failing > 0:
            self.failing -= 1
            return GatewayReply(500, {"error": {"message": "the gateway is starting"}})
        words = "好的，我看過了。" if payload.get("tools") else json.dumps(MEETING_ANSWER)
        return GatewayReply(
            200,
            {
                "choices": [{"index": 0, "message": {"role": "assistant", "content": words}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    def offered_tools(self) -> set[str]:
        return {
            tool["function"]["name"] for body in self.bodies for tool in body.get("tools") or ()
        }


@dataclass
class Host:
    runtime: HostRuntime
    web: AgentWeb
    server: AgentWebServer
    gateway: StubGateway

    def call(self, path: str, body: Any = None) -> tuple[int, dict[str, Any]]:
        reply = fetch(
            f"http://127.0.0.1:{self.server.server_address[1]}{path}",
            token=self.server.token,
            body=body,
        )
        return reply.status, reply.json()

    def ok(self, path: str, body: Any = None) -> dict[str, Any]:
        status, answer = self.call(path, body)
        assert status == 200, answer
        return answer

    def wait(self, run_id: str, dataset: str = "demo") -> dict[str, Any]:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            run = self.ok(f"/api/bi/runs/{run_id}?dataset={dataset}")["run"]
            if run["status"] != "extracting":
                return dict(run)
            time.sleep(0.05)
        raise AssertionError("the run did not finish")


APPROVED = ("UNCLASSIFIED", "INTERNAL")


@pytest.fixture
def make_host(tmp_path: Path) -> Iterator[Any]:
    opened: list[tuple[Any, AgentWebServer, threading.Thread]] = []

    def make(
        approved: tuple[str, ...] | None = APPROVED, failing: int = 0, with_model: bool = True
    ) -> Host:
        stub = endpoint(credential=None)
        changes: dict[str, Any] = {}
        if with_model:
            models = binding(
                catalog={
                    "endpoints": [stub],
                    "routes": [{"name": "default", "alias": "company"}],
                },
                **(
                    {}
                    if approved is None
                    else {
                        "data_approval": {
                            "backend_id": "gateway",
                            "endpoint_alias": "company",
                            "endpoint_base_url": stub["base_url"],
                            "approved_classes": list(approved),
                            "approval_ref": "host-admin/internal-gateway-fixture",
                            "internal_gateway": True,
                        }
                    }
                ),
            )
            if approved is None:
                del models["data_approval"]
            changes["config_changes"] = {"models": models}
        config, layout = ready(tmp_path, **changes)
        assert not config.knowledge
        skill_packs.install_bundle(layout, None, shipped=shipped())
        gateway = StubGateway(failing)
        context = build_runtime(config, layout=layout, model_transport=gateway)
        runtime = context.__enter__()
        assert runtime.agent.gateway.bridge.installed.get(KNOWLEDGE_QUERY_SPEC.identity) is None
        web = AgentWeb(runtime)
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        opened.append((context, server, thread))
        return Host(runtime, web, server, gateway)

    yield make
    for context, server, thread in opened:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        context.__exit__(None, None, None)


def demo(host: Host, **source: Any) -> str:
    host.ok("/api/bi/datasets", {"name": "demo", "schema": "bi.schema/v1.1"})
    body = {"dataset": "demo", "name": "meeting.md", "text": NOTE, **source}
    return str(host.ok("/api/bi/sources", body)["source"]["id"])


def test_the_page_gate_says_a_model_is_available(make_host: Any) -> None:
    host = make_host()
    host.ok("/api/bi/datasets", {"name": "demo", "schema": "bi.schema/v1.1"})
    assert host.ok("/api/bi/ai?dataset=demo") == {
        "available": True,
        "model": "company",
        "message": "",
    }


def test_the_client_is_the_approved_one_and_never_a_raw_client(make_host: Any) -> None:
    host = make_host()
    ai = bi_cards_api.web_ai_runtime(host.web)
    chosen = ai.model()
    assert chosen is not None
    assert isinstance(chosen[0], ApprovedModelClient) and chosen[1] == "company"
    # A client without the approval wrapper is not used: neither the drafting client
    # (extraction's first choice, 2026-11-06) nor the conversation's.
    gateway = host.runtime.agent.gateway
    drafting = gateway.bridge.installed.get(DRAFT_SPEC.identity)
    if drafting is not None:
        drafting.handler.model = host.gateway
    gateway.router.model = host.gateway
    assert ai.model() is None


def test_a_host_with_no_model_stays_unavailable(make_host: Any) -> None:
    host = make_host(with_model=False)
    demo(host)
    state = host.ok("/api/bi/ai?dataset=demo")
    assert state["available"] is False and "Knowledge" not in state["message"]


def test_ai_ingest_runs(make_host: Any) -> None:
    host = make_host()
    source = demo(host)
    body = {"dataset": "demo", "kind": "ingest", "source_id": source}
    run = host.ok("/api/bi/runs", body)["run"]
    finished = host.wait(run["id"])
    assert finished["status"] == "review" and finished["model"] == "company"
    assert host.gateway.bodies


def test_a_failed_chunk_is_retried(make_host: Any) -> None:
    host = make_host(failing=10)
    source = demo(host)
    body = {"dataset": "demo", "kind": "ingest", "source_id": source}
    run = host.ok("/api/bi/runs", body)["run"]
    assert host.wait(run["id"])["status"] in ("partial", "failed")
    host.gateway.failing = 0
    host.ok(f"/api/bi/runs/{run['id']}/retry", {"dataset": "demo"})
    assert host.wait(run["id"])["status"] == "review"


def test_session_b_takes_a_turn(make_host: Any) -> None:
    host = make_host()
    source = demo(host)
    made = host.ok(
        "/api/bi/methods", {"dataset": "demo", "method": {"name": "會議紀錄", "mode": "llm"}}
    )
    opened = {"dataset": "demo", "kind": "method", "target": made["method"]["id"]}
    session = host.ok("/api/bi/sessions", opened)["session"]
    asked = len(host.gateway.bodies)
    turn = {"dataset": "demo", "message": "會議紀錄要建 Signal", "source_ids": [source]}
    status, answer = host.call(f"/api/bi/sessions/{session['id']}/turns", turn)
    assert status == 200, answer
    assert len(host.gateway.bodies) > asked


def test_session_a_and_the_skill_assistant_reach_the_agent(make_host: Any, tmp_path: Path) -> None:
    host = make_host()
    shared = tmp_path / "shared"
    shared.mkdir()
    made = host.ok(
        "/api/bi/vaults",
        {
            "path": str(shared),
            "title": "Market",
            "purpose": "虛構",
            "schema": "bi.schema/v1.1",
            "author": "alice",
        },
    )
    dataset = made["vault"]["dataset"]
    assert host.ok(f"/api/bi/ai?dataset={dataset}")["available"] is True

    opened = {"dataset": dataset, "kind": "skill", "target": "classify"}
    skill = host.ok("/api/bi/sessions", opened)["session"]
    status, answer = host.call(
        f"/api/bi/sessions/{skill['id']}/turns", {"dataset": dataset, "message": "建 Signal"}
    )
    assert status == 200, answer
    assert "bi_skill__try" in host.gateway.offered_tools()

    draft = host.ok("/api/bi/schema-drafts", {"dataset": dataset, "base": "bi.schema/v1.1"})
    opened = {"dataset": dataset, "kind": "schema", "target": draft["draft"]["id"]}
    schema = host.ok("/api/bi/sessions", opened)["session"]
    status, answer = host.call(
        f"/api/bi/sessions/{schema['id']}/turns", {"dataset": dataset, "message": "加一個欄位"}
    )
    assert status == 200, answer
    assert any(name.startswith("bi_schema__") for name in host.gateway.offered_tools())


def test_a_bench_extraction_case_is_read(make_host: Any, tmp_path: Path) -> None:
    host = make_host()
    shared = tmp_path / "shared-bench"
    shared.mkdir()
    made = host.ok(
        "/api/bi/vaults",
        {
            "path": str(shared),
            "title": "Bench",
            "purpose": "虛構",
            "schema": "bi.schema/v1.1",
            "author": "alice",
        },
    )
    bench = bi_cards_api.web_bench_runtime(host.web)
    extract = bench.extract_for(made["vault"]["id"], "alice")
    found = extract({"slug": "case-1", "note": NOTE, "expected": {}})
    assert found, "the trial found candidates"


@pytest.mark.parametrize("approved", [("UNCLASSIFIED",), None])
def test_a_source_of_an_unapproved_class_is_still_refused(
    make_host: Any, approved: tuple[str, ...] | None
) -> None:
    host = make_host(approved=approved)
    source = demo(host)  # INTERNAL by default
    body = {"dataset": "demo", "kind": "ingest", "source_id": source}
    status, answer = host.call("/api/bi/runs", body)
    assert (status, answer["code"]) == (400, "classification_not_approved")
    assert host.gateway.bodies == []


@pytest.mark.parametrize("level", ["CONFIDENTIAL", "RESTRICTED"])
def test_higher_classes_are_refused_with_internal_approved(make_host: Any, level: str) -> None:
    host = make_host()
    source = demo(host, classification=level)
    body = {"dataset": "demo", "kind": "ingest", "source_id": source}
    status, answer = host.call("/api/bi/runs", body)
    assert (status, answer["code"]) == (400, "classification_not_approved")
    assert host.gateway.bodies == []


def _vault(host: Host, tmp_path: Path) -> dict[str, Any]:
    shared = tmp_path / "shared-sources"
    shared.mkdir()
    return dict(
        host.ok(
            "/api/bi/vaults",
            {
                "path": str(shared),
                "title": "Sources",
                "purpose": "虛構",
                "schema": "bi.schema/v1.1",
                "author": "alice",
            },
        )["vault"]
    )


def test_a_vault_source_goes_through_the_fallback_and_a_withdrawn_one_is_not_sent(
    make_host: Any, tmp_path: Path
) -> None:
    host = make_host(failing=10)
    vault = _vault(host, tmp_path)
    dataset = vault["dataset"]
    secret = {"dataset": dataset, "name": "secret.md", "text": NOTE + "\n機密。\n"}
    source = host.ok("/api/bi/sources", {**secret, "classification": "RESTRICTED"})["source"]
    status, answer = host.call(
        "/api/bi/runs", {"dataset": dataset, "kind": "trial", "source_id": source["id"]}
    )
    assert (status, answer["code"]) == (400, "classification_not_approved")
    assert host.gateway.bodies == []

    plain = {"dataset": dataset, "name": "meeting.md", "text": NOTE}
    source = host.ok("/api/bi/sources", plain)["source"]
    body = {"dataset": dataset, "kind": "trial", "source_id": source["id"]}
    run = host.ok("/api/bi/runs", body)["run"]
    assert host.wait(run["id"], dataset)["status"] in ("partial", "failed")

    host.ok(f"/api/bi/vaults/{vault['id']}/commit", {"purpose": "加入來源"})
    host.ok(f"/api/bi/vaults/{vault['id']}/push", {})
    withdrawn = {"source_id": source["id"], "confirm": True}
    host.ok(f"/api/bi/vaults/{vault['id']}/withdraw-source", withdrawn)
    host.gateway.failing = 0
    asked = len(host.gateway.bodies)
    status, answer = host.call(f"/api/bi/runs/{run['id']}/retry", {"dataset": dataset})
    assert status != 200 and answer["code"] == "run_closed"
    assert len(host.gateway.bodies) == asked


def test_the_card_page_importer_asks_no_model(make_host: Any, tmp_path: Path) -> None:
    host = make_host()
    dataset = _vault(host, tmp_path)["dataset"]
    page = {"path": "tsn.md", "text": "---\ntype: Technology\nname: TSN\n---\n\n正文。\n"}
    preview = host.ok("/api/bi/import/pages/preview", {"dataset": dataset, "pages": [page]})
    host.ok("/api/bi/import/pages/apply", {"preview_id": preview["preview_id"]})
    assert host.gateway.bodies == []
    assert host.ok(f"/api/bi/ai?dataset={dataset}")["available"] is True
