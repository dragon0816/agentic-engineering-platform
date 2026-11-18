"""What the LLM Wiki maintenance does today, pinned before it moves behind the
feature mount points (docs/phases/FEATURE_PLUGIN_WIKI_PROPOSAL_DRAFT_20261118.md
§4 stage A). Synthetic local data only: a test vault in a temporary folder.

These describe current behaviour, not new requirements: the Knowledge pipeline's
21 capabilities in their order, its `/api/knowledge/*` maintenance routes'
representative answers and size limits, and the Knowledge page shell the
maintenance pane sits in.
"""

from __future__ import annotations

import hashlib
import http.client
import json
from pathlib import Path
from typing import Any

from test_agent_web import base, fetch
from test_knowledge_pipeline_web import served_pipeline  # noqa: F401 - fixture

from host_runtime.web import MAX_ATTACHMENT_REQUEST_BYTES, MAX_BODY_BYTES, AgentWebServer
from host_runtime.web_page import PAGE

#: The Knowledge pipeline's capabilities, in the order the Host registers them.
PIPELINE_CAPABILITIES = (
    "sandbox-create",
    "sandbox-list",
    "convert",
    "ingest-plan",
    "ingest-apply",
    "lint",
    "adopt",
    "index-enrich",
    "index-build",
    "merge",
    "drop-folders",
    "pull",
    "question-sets",
    "rule-files",
    "file-read",
    "rule-write",
    "plan-page",
    "skill-guide",
    "drop-add",
    "sandbox-contents",
    "sandbox-discard",
)
#: sha256 of the 21 specs (identity, policy, schemas), as JSON in registration order.
PIPELINE_SPECS_SHA256 = "b4e3330bf01268b00ac838443c24c7d28f6e64c415c96ef53e26acbb75d85738"


def _get(server: AgentWebServer, path: str) -> tuple[int, Any]:
    reply = fetch(base(server) + path, token=server.token)
    return reply.status, json.loads(reply.body)


def _post(server: AgentWebServer, path: str, body: Any) -> tuple[int, Any]:
    reply = fetch(base(server) + path, token=server.token, body=body)
    return reply.status, json.loads(reply.body)


def _claimed_length(server: AgentWebServer, path: str, length: int) -> int:
    """POST that claims `length` bytes and sends none: the size check comes first."""
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=30)
    try:
        connection.putrequest("POST", path)
        connection.putheader("Authorization", f"Bearer {server.token}")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(length))
        connection.endheaders()
        return connection.getresponse().status
    finally:
        connection.close()


def test_the_pipeline_registers_its_21_capabilities_in_order(
    served_pipeline: tuple[AgentWebServer, Path],  # noqa: F811 - fixture
) -> None:
    server, _ = served_pipeline
    installed = server.web.runtime.agent.gateway.bridge.installed
    keys = [binding.spec.identity for binding in installed._bindings.values()]
    pipeline = [key for key in keys if key.namespace == "knowledge-pipeline"]
    assert [key.name for key in pipeline] == list(PIPELINE_CAPABILITIES)
    assert {key.version for key in pipeline} == {"1.0.0"}
    # One block, at the same place among the other capabilities.
    first = keys.index(pipeline[0])
    assert keys[first : first + len(pipeline)] == pipeline
    assert first + len(pipeline) == len(keys)  # the last ones registered
    assert keys[first - 1].key == ("coding", "run-python", "1.0.0")
    specs = []
    for key in pipeline:
        held = installed.get(key)
        assert held is not None
        specs.append(held.spec.model_dump(mode="json"))
    for spec in specs:
        assert spec["policy"]["required_permissions"] == ["knowledge-pipeline.use"]
        assert spec["policy"]["policy_refs"] == ["knowledge-sandbox-policy"]
    digest = hashlib.sha256(json.dumps(specs, sort_keys=True).encode("utf-8")).hexdigest()
    assert digest == PIPELINE_SPECS_SHA256


def test_the_maintenance_routes_answer_as_before(
    served_pipeline: tuple[AgentWebServer, Path],  # noqa: F811 - fixture
) -> None:
    server, _ = served_pipeline
    unknown = "?sandbox_id=sb-none"
    assert _get(server, "/api/knowledge/push" + unknown) == (
        200,
        {"ok": False, "code": "unknown_sandbox"},
    )
    assert _get(server, "/api/knowledge/convert" + unknown) == (200, {"ok": True, "run": None})
    assert _get(server, "/api/knowledge/reingest" + unknown)[1]["ok"] is False
    assert _get(server, "/api/knowledge/benchmark" + unknown)[1]["ok"] is False
    assert _get(server, "/api/knowledge/review-proposal" + unknown)[1]["ok"] is False
    assert _get(server, "/api/knowledge/progress?key=pnone") == (
        200,
        {"ok": True, "progress": None},
    )
    assert _get(server, "/api/knowledge/skill-assist?job=none") == (
        200,
        {"ok": False, "code": "unknown_job"},
    )
    assert _get(server, "/api/knowledge/repos") == (200, {"repos": []})
    for path, body, code in (
        ("/api/knowledge/pipeline/call", [], "pipeline_request_invalid"),
        ("/api/knowledge/push/start", {}, "push_request_invalid"),
        ("/api/knowledge/reingest/start", {}, "reingest_request_invalid"),
        ("/api/knowledge/skill-assist", {}, "skill_assist_request_invalid"),
        ("/api/knowledge/refresh", [], "refresh_request_invalid"),
        ("/api/knowledge/benchmark/start", {}, "benchmark_request_invalid"),
        ("/api/knowledge/pipeline/publish", [], "publish_request_invalid"),
    ):
        assert _post(server, path, body) == (400, {"ok": False, "code": code}), path
    assert _post(server, "/api/knowledge/pipeline/call", {"step": "nope"}) == (
        200,
        {"ok": False, "code": "unknown_pipeline_step"},
    )
    assert _post(server, "/api/knowledge/convert/stop", {"sandbox_id": "sb-none"}) == (
        200,
        {"ok": False, "code": "convert_not_running"},
    )
    assert _post(server, "/api/knowledge/reingest/stop", {"sandbox_id": "sb-none"}) == (
        200,
        {"ok": False, "code": "reingest_not_running"},
    )
    assert _post(server, "/api/knowledge/convert/start", {"sandbox_id": "sb-none"}) == (
        200,
        {"ok": False, "code": "knowledge_pipeline_disabled"},
    )


def test_the_maintenance_routes_keep_their_size_limits(
    served_pipeline: tuple[AgentWebServer, Path],  # noqa: F811 - fixture
) -> None:
    server, _ = served_pipeline
    # An original travels in the step call, so it takes an attachment's size.
    call = "/api/knowledge/pipeline/call"
    assert _claimed_length(server, call, MAX_ATTACHMENT_REQUEST_BYTES + 1) == 413
    for path in ("/api/knowledge/convert/start", "/api/knowledge/repos/create"):
        assert _claimed_length(server, path, MAX_BODY_BYTES * 4 + 1) == 413, path


def test_the_knowledge_page_shell_and_the_maintenance_pane() -> None:
    for mount in (
        'id="kn-tabs"',
        'data-kn="pipeline"',
        'id="kn-pane-pipeline"',
        'id="kp-refresh"',
        'id="kn-note"',
        'id="kp-status"',
        'id="kp-askable"',
        'id="kp-stepper"',
        'id="kp-repos"',
        'id="kp-review"',
    ):
        assert PAGE.count(mount) == 1, mount
    # The pipeline pane comes before the BI pane, in the Knowledge panel.
    assert (
        PAGE.index('id="panel-knowledge"')
        < PAGE.index('id="kn-pane-pipeline"')
        < PAGE.index('id="kn-pane-bi"')
    )
    # The tab switch reads the pipeline and opens it when it has a base or a repository.
    script = PAGE.split("async function loadKnowledgeTab()", 1)[1].split("\n}\n", 1)[0]
    assert 'call("/api/knowledge/pipeline")' in script and "await loadKnowledge()" in script
    # Reviews opens a review sandbox on the Knowledge tab through the pipeline helpers.
    for name in ("async function pipeline(", "function kpOpen(", "async function kpRun("):
        assert PAGE.count(name) == 1, name
