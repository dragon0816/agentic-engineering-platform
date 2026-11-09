"""Document upload -> model wire -> real draft/preview/install boundaries.

The model is scripted; this is a deterministic integration proof, not a claim
that an authenticated SAP session or model-generated business logic was tested.
"""

from __future__ import annotations

import base64
import io
import json
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from test_agent_web import base, fetch
from test_host_models import GatewayReply, binding, endpoint
from test_host_wiring import ready
from test_office import make_docx, make_pdf

from host_runtime.chat_authoring import digest
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer


class AuthoringGateway:
    def __init__(self) -> None:
        self.workbook = ""
        self.saw_documents = False
        self.trial_candidate_id = ""

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        payload = json.loads(body)
        tools = [message for message in payload["messages"] if message["role"] == "tool"]
        if not tools:
            content = payload["messages"][-1]["content"]
            text = "\n".join(part.get("text", "") for part in content)
            assert "Open Sales Order" in text and "First paragraph" in text
            assert "Sales Name / Owner" in text and "Sub-Dept." in text
            assert sum(part["type"] == "image_url" for part in content) == 2
            self.saw_documents = True
            name = "authoring__plan_workflow"
            arguments: dict[str, Any] = {
                "requirements": [
                    {
                        "requirement_id": "read_mapping",
                        "description": "Read the attached sales mapping",
                        "check_ids": ["mapping_rows"],
                        "assertions": [
                            {
                                "path": ["steps", 0, "capability", "name"],
                                "operator": "equals",
                                "expected": "read-sheet",
                            }
                        ],
                    }
                ]
            }
        else:
            observed = json.loads(tools[-1]["content"])
            assert observed["host"]["status"] == "succeeded"
            if observed["name"] == "authoring__run_workflow":
                assert observed["host"]["data"]["status"] == "succeeded"
                assert observed["host"]["data"]["verified"] is True
                message: dict[str, Any] = {
                    "role": "assistant",
                    "content": "Workflow draft created and verified.",
                }
                return GatewayReply(200, {"choices": [{"index": 0, "message": message}]})
            if observed["name"] == "authoring__draft_workflow":
                self.trial_candidate_id = observed["host"]["data"]["candidate_id"]
                name = "authoring__run_workflow"
                arguments = {"candidate_id": self.trial_candidate_id, "arguments": {}}
                return self._call(name, arguments)
            assert observed["name"] == "authoring__plan_workflow"
            workflow = {
                "name": "read-sales-mapping",
                "description": "Read the attached sales mapping as a reusable Workflow.",
                "steps": [
                    {
                        "capability": "excel/read-sheet@1.0.0",
                        "inputs": {
                            "workbook": {"source": "fixed", "value": self.workbook},
                            "sheet": {"source": "fixed", "value": "Sheet"},
                        },
                    }
                ],
                "checks": [{"check_id": "mapping_rows", "step_index": 0, "kind": "data_nonempty"}],
            }
            name = "authoring__draft_workflow"
            arguments = {"title": "Sales mapping", "workflow": workflow}
        return self._call(name, arguments)

    def _call(self, name: str, arguments: dict[str, Any]) -> GatewayReply:
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": name,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments),
                    },
                }
            ],
        }
        return GatewayReply(200, {"choices": [{"index": 0, "message": message}]})


def test_documents_cross_http_and_model_wire_then_create_preview_and_install(
    tmp_path: Path,
) -> None:
    config, layout = ready(
        tmp_path,
        config_changes={
            "models": binding(
                catalog={
                    "endpoints": [endpoint(credential=None, capabilities={"vision": True})],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            ),
            "web": {"allowed_origins": ["https://example.invalid"]},
        },
    )
    model = AuthoringGateway()
    book = Workbook()
    assert book.active is not None
    book.active.append(["Sales Name / Owner", "Sub-Dept."])
    book.active.append(["Example Owner", "SAS"])
    buffer = io.BytesIO()
    book.save(buffer)
    with build_runtime(config, model_transport=model) as runtime:
        web = AgentWeb(runtime)
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            session = fetch(base(server) + "/api/conversations", token=server.token, body={}).json()
            session_id = session["conversation"]["session_id"]
            ids = []
            for name, data in [
                ("sop.pdf", make_pdf(["Open Sales Order"], image=True)),
                ("sop.docx", make_docx()),
                ("mapping.xlsx", buffer.getvalue()),
            ]:
                reply = fetch(
                    base(server) + "/api/attachments",
                    token=server.token,
                    body={
                        "session_id": session_id,
                        "filename": name,
                        "data": base64.b64encode(data).decode(),
                    },
                ).json()
                assert reply["ok"]
                file_id = reply["attachment"]["file_id"]
                ids.append(file_id)
                if name.endswith(".xlsx"):
                    model.workbook = web.attachments.get(session_id, file_id).path
            turn = fetch(
                base(server) + "/api/conversations/turn",
                token=server.token,
                body={
                    "session_id": session_id,
                    "message": "依附件建立 Workflow",
                    "attachments": ids,
                },
            ).json()
            assert turn["ok"] and model.saw_documents
            chat = runtime.chat_authoring
            assert chat is not None
            (candidate,) = chat.candidates(runtime.actor)
            assert candidate.session_id == session_id
            assert candidate.candidate_id == model.trial_candidate_id
            assert candidate.authoring_task is not None
            assert candidate.authoring_task.last_status == "succeeded"
            assert candidate.authoring_task.verified_digest == digest(candidate.draft)
            preview = chat.preview(runtime.actor, candidate.candidate_id, {})
            assert isinstance(preview["preview"], dict)
            assert preview["preview"]["status"] == "previewed"
            # Approval is supplied explicitly by the test actor, never by the model.
            installed = chat.install_now(runtime.actor, candidate.candidate_id)
            assert installed.status == "approved"
            run = chat.execute(runtime.actor, candidate, {}, "test-explicit-read-approval")
            assert run["status"] == "succeeded"
            raw = candidate.draft.model_dump(mode="json")
            assert raw["steps"][0]["inputs"]["workbook"]["value"] == model.workbook
            assert list(layout.workflows.glob("*.json"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
