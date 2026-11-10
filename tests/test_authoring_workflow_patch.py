"""Surgical candidate edits preserve previously tested, unmentioned content."""

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from test_chat_authoring import Echo, Out, context, spec, studio, workflow

from agent.gateway import HostToolOutcome
from capabilities.runtime import CapabilityExecutionFailed
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from host_runtime.attachments import AttachmentStore
from host_runtime.chat_authoring import ChatAuthoring, ChatAuthoringError, digest
from host_runtime.external_authoring import ExternalAuthoring
from host_runtime.mcp_server import dispatch
from host_runtime.workflow_patch import PatchOperation


def _request(item: Any, value: str = "repaired") -> dict[str, Any]:
    return {
        "candidate_id": item.candidate_id,
        "base_digest": digest(item.draft),
        "operations": [
            {
                "op": "replace",
                "path": ["steps", 0, "inputs", "value"],
                "value": {"source": "fixed", "value": value},
            }
        ],
    }


def test_copy_reference_schema_identifies_host_id_instead_of_filename_or_path() -> None:
    description = PatchOperation.model_json_schema()["properties"]["attachment_id"]["description"]
    assert "Host-issued att-" in description
    assert "never use a filename or filesystem path" in description


def _draft(chat: ChatAuthoring) -> Any:
    item, problems = chat.draft("owner", "session-1", "Report", workflow("read-it"))
    assert item is not None and not problems
    return item


def test_automatic_repair_cannot_replace_unexecuted_downstream_code(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    raw = workflow("read-it")
    raw["steps"].append(
        {
            "capability": "lab/read-it@1.0.0",
            "inputs": {
                "value": {
                    "source": "fixed",
                    "value": "tested report code\r\nprint('unchanged')\r\n",
                }
            },
        }
    )
    item, problems = chat.draft("owner", "session-1", "Report", raw)
    assert item is not None and not problems
    before = item.model_dump(mode="json")
    raw["steps"][1]["inputs"]["value"]["value"] = "broken downstream replacement"
    tool = next(t for t in chat.tools() if t.tool.name == "authoring__draft_workflow")
    repair = context().model_copy(
        update={
            "message": (
                f"[Host authoring continuation: trial failed] Candidate {item.candidate_id}; "
                "failure web_target_missing. Repair the actual failed Browser step."
            )
        }
    )

    async def invoke() -> HostToolOutcome:
        return await tool.handler(repair, {"candidate_id": item.candidate_id, "workflow": raw})

    result = asyncio.run(invoke())
    assert result.status == "failed"
    assert result.failure is not None and result.failure.code == "authoring_patch_required"
    assert chat.candidate(item.candidate_id, "owner").model_dump(mode="json") == before


def test_patch_preserves_canonical_identity_defaults_and_unmentioned_strings(
    tmp_path: Path,
) -> None:
    chat, _ = studio(tmp_path)
    raw = workflow("read-it")
    raw["parameters"][0]["default"] = "2026-06"
    script = "# tested code\r\nprint('quote: \\\"')\r\n"
    raw["steps"].append(
        {
            "capability": "lab/read-it@1.0.0",
            "inputs": {"value": {"source": "fixed", "value": script}},
        }
    )
    item, problems = chat.draft("owner", "session-1", "Report", raw)
    assert item is not None and not problems
    expected = item.draft.model_dump(mode="json")
    chat.tasks.observe("owner", "session-1", "For this QA run use month=2026-09")
    expected["steps"][0]["inputs"]["value"] = {"source": "fixed", "value": "repair"}
    request: dict[str, Any] = {
        "candidate_id": item.candidate_id,
        "base_digest": digest(item.draft),
        "operations": [
            {
                "op": "replace",
                "path": ["steps", 0, "inputs", "value"],
                "value": {"source": "fixed", "value": "repair"},
            }
        ],
    }
    changed, problems = chat.patch(context(), request)
    assert changed is not None and not problems
    assert changed.draft.model_dump(mode="json") == expected
    assert changed.revision == item.revision + 1


@pytest.mark.parametrize(
    "path",
    [
        ["steps", True, "inputs", "value"],
        ["steps", -1, "inputs", "value"],
        ["steps", 0, "inputs", ".."],
        ["steps", 99, "inputs", "value"],
        ["steps"],
        ["metadata", "identity", "version"],
        ["steps", 0, "capability"],
    ],
)
def test_invalid_patch_cannot_mutate_candidate_or_task(tmp_path: Path, path: list[Any]) -> None:
    chat, _ = studio(tmp_path)
    item = _draft(chat)
    before = item.model_dump(mode="json")
    request = _request(item)
    request["operations"][0]["path"] = path
    with pytest.raises(ChatAuthoringError):
        chat.patch(context(), request)
    assert chat.candidate(item.candidate_id, "owner").model_dump(mode="json") == before
    assert chat.tasks.load("owner", "session-1") is None


def test_patch_copy_uses_owned_session_reference_without_retyping(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    chat.attachments = AttachmentStore(tmp_path)
    item = _draft(chat)
    source = "exact source\r\nprint('\\\\quoted')\r\n"
    attachment = chat.attachments.add(
        "session-1", "prior.json", json.dumps({"script": source}).encode()
    )
    request = _request(item)
    request["operations"] = [
        {
            "op": "copy_reference",
            "attachment_id": attachment.file_id,
            "source_path": ["script"],
            "path": ["steps", 0, "inputs", "value", "path"],
        }
    ]
    # Existing destination is a run binding path tuple, and the wrong type must fail validation.
    changed, problems = chat.patch(context(), request)
    assert changed is None and problems
    request["operations"][0]["path"] = ["steps", 0, "inputs", "value"]
    source_attachment = chat.attachments.add(
        "session-1",
        "source.json",
        json.dumps({"binding": {"source": "fixed", "value": source}}).encode(),
    )
    request["operations"][0].update(
        attachment_id=source_attachment.file_id, source_path=["binding"]
    )
    changed, problems = chat.patch(context(), request)
    assert changed is not None and not problems
    assert changed.draft.model_dump(mode="json")["steps"][0]["inputs"]["value"]["value"] == source


@pytest.mark.parametrize("which", ["actor", "session", "digest", "installed", "foreign_reference"])
def test_patch_scope_and_stale_refusals_preserve_state(tmp_path: Path, which: str) -> None:
    chat, _ = studio(tmp_path)
    chat.attachments = AttachmentStore(tmp_path)
    item = _draft(chat)
    request = _request(item)
    ctx = context()
    if which == "actor":
        ctx = ctx.model_copy(update={"actor": "stranger"})
    elif which == "session":
        ctx = ctx.model_copy(update={"session_id": "another"})
    elif which == "digest":
        request["base_digest"] = "0" * 64
    elif which == "installed":
        item = chat._save_candidate(item.model_copy(update={"status": "installed"}))
    else:
        attachment = chat.attachments.add("another", "foreign.json", b'{"value":"secret"}')
        request["operations"] = [
            {
                "op": "copy_reference",
                "attachment_id": attachment.file_id,
                "source_path": ["value"],
                "path": ["steps", 0, "inputs", "value"],
            }
        ]
    with pytest.raises(ChatAuthoringError):
        chat.patch(ctx, request)
    assert chat.candidate(item.candidate_id, "owner").model_dump(mode="json") == item.model_dump(
        mode="json"
    )


def test_actual_failed_step_scope_protects_downstream_and_invalidates_proof(tmp_path: Path) -> None:
    from test_authoring_trial_diagnostics import _plan

    chat, _ = studio(tmp_path)
    _plan(chat, capability="fail-it")

    async def fail(context: RequestContext, inputs: Contract) -> Contract:
        raise CapabilityExecutionFailed(
            "web_target_missing", Out(echoed="failure"), where="actions[0]"
        )

    chat.installed.register(
        spec("fail-it", "read"), fail, Echo, Out, ExecutionDependencies(central_required=False)
    )
    raw = workflow("fail-it")
    raw["steps"].append(
        {
            "capability": "lab/read-it@1.0.0",
            "inputs": {"value": {"source": "fixed", "value": "tested downstream"}},
        }
    )
    raw["checks"] = [{"check_id": "rows", "step_index": 0, "kind": "data_nonempty"}]
    item, problems = chat.draft("owner", "session-1", "Report", raw)
    assert item is not None and not problems
    result = chat.execute("owner", item, {"month": "2026-06"}, "test-scope")
    assert result["status"] == "failed"
    current = chat.candidate(item.candidate_id, "owner")
    repair = context().model_copy(
        update={
            "message": f"[Host authoring continuation: failure] Candidate {item.candidate_id}; "
            "failure web_target_missing"
        }
    )
    request = _request(current)
    request["operations"][0]["path"][1] = 1
    with pytest.raises(ChatAuthoringError, match="authoring_patch_path_refused"):
        chat.patch(repair, request)
    request["operations"][0]["path"][1] = 0
    changed, problems = chat.patch(repair, request)
    assert changed is not None and not problems
    assert changed.draft.steps[1] == item.draft.steps[1]
    assert changed.authoring_task is not None
    assert changed.authoring_task.verified_digest is None
    assert changed.authoring_task.active_trial_token is None


@pytest.mark.parametrize("writer", ["patch", "draft"])
def test_concurrent_writer_cannot_overwrite_accepted_patch(tmp_path: Path, writer: str) -> None:
    chat, _ = studio(tmp_path)
    from test_authoring_trial_diagnostics import _plan

    _plan(chat)
    item = _draft(chat)
    task_before = chat.tasks.load("owner", "session-1")
    admitted = threading.Event()
    release = threading.Event()
    original = chat.prepare_workspaces

    def paused(manifest: Any) -> None:
        admitted.set()
        assert release.wait(10)
        original(manifest)

    chat.prepare_workspaces = paused  # type: ignore[method-assign]
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(chat.patch, context(), _request(item, "first"))
        assert admitted.wait(10)
        try:
            with pytest.raises(ChatAuthoringError, match="authoring_candidate_busy"):
                if writer == "patch":
                    chat.patch(context(), _request(item, "second"))
                else:
                    chat.draft(
                        "owner", "session-1", "overwrite", workflow("read-it"), item.candidate_id
                    )
            assert chat.tasks.load("owner", "session-1") == task_before
        finally:
            release.set()
        changed, problems = first.result(timeout=10)
    assert changed is not None and not problems
    assert chat.candidate(item.candidate_id, "owner").draft == changed.draft
    with pytest.raises(ChatAuthoringError, match="authoring_digest_stale"):
        chat.patch(context(), _request(item))


def test_mcp_and_native_patch_share_exact_canonical_behavior(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    item = _draft(chat)
    facade = ExternalAuthoring(chat, "owner", "codex", session_id="session-1")
    result = dispatch(facade, "aep_patch_workflow", _request(item, "external"))
    assert result["ok"] is True
    current = chat.candidate(item.candidate_id, "owner")
    tool = next(t for t in chat.tools() if t.tool.name == "authoring__patch_workflow")

    async def invoke() -> HostToolOutcome:
        return await tool.handler(context(), _request(current, "native"))

    outcome = asyncio.run(invoke())
    assert outcome.status == "succeeded"
    final = chat.candidate(item.candidate_id, "owner")
    assert final.draft.metadata == item.draft.metadata
    assert final.revision == item.revision + 2
    assert isinstance(outcome.data, dict) and outcome.data["digest"] == digest(final.draft)
    assert (
        dispatch(facade, "aep_patch_workflow", _request(item))["code"] == "authoring_digest_stale"
    )


def test_install_admission_excludes_patch_before_publication(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    item = _draft(chat)
    admitted, release = threading.Event(), threading.Event()
    original = chat.prepare_workspaces

    def pause(manifest: Any) -> None:
        admitted.set()
        assert release.wait(10)
        original(manifest)

    chat.prepare_workspaces = pause  # type: ignore[method-assign]
    with ThreadPoolExecutor(max_workers=1) as pool:
        installing = pool.submit(chat.install, item, "owner", "explicit-test-approval")
        assert admitted.wait(10)
        try:
            with pytest.raises(ChatAuthoringError, match="authoring_candidate_busy"):
                chat.patch(context(), _request(item))
        finally:
            release.set()
        result = installing.result(timeout=10)
    current = chat.candidate(item.candidate_id, "owner")
    assert current.status == "installed" and current.installed_digest == digest(item.draft)
    assert current.draft == item.draft and result["digest"] == digest(item.draft)
    assert len(list(chat.workflows_dir.glob("*.json"))) == 1


def test_stale_install_cannot_publish_after_patch(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    item = _draft(chat)
    changed, problems = chat.patch(context(), _request(item))
    assert changed is not None and not problems
    with pytest.raises(ChatAuthoringError, match="authoring_digest_stale"):
        chat.install(item, "owner", "stale-test-approval")
    assert not list(chat.workflows_dir.glob("*.json"))
    assert not chat.grants_file.exists()
    assert chat.candidate(item.candidate_id, "owner").draft == changed.draft


def test_noop_patch_cannot_have_old_trial_proof_restored_by_metadata_writer(tmp_path: Path) -> None:
    from test_authoring_trial_diagnostics import _candidate

    chat, _ = studio(tmp_path)
    item = _candidate(chat)
    assert (
        chat.execute("owner", item, {"month": "2026-06"}, "verified-before-noop")["verified"]
        is True
    )
    verified = chat.candidate(item.candidate_id, "owner")
    request = _request(verified)
    request["operations"][0]["value"] = verified.draft.model_dump(mode="json")["steps"][0][
        "inputs"
    ]["value"]
    changed, problems = chat.patch(context(), request)
    assert changed is not None and not problems and digest(changed.draft) == digest(verified.draft)
    with pytest.raises(ChatAuthoringError, match="authoring_digest_stale"):
        chat._save_candidate(verified)
    current = chat.candidate(item.candidate_id, "owner")
    assert current.authoring_task is not None and current.authoring_task.verified_digest is None


def test_automatic_patch_without_actual_diagnostic_scope_refuses(tmp_path: Path) -> None:
    chat, _ = studio(tmp_path)
    item = _draft(chat)
    repair = context().model_copy(
        update={
            "message": f"[Host authoring continuation: failure] Candidate {item.candidate_id}; "
            "failure"
        }
    )
    with pytest.raises(ChatAuthoringError, match="authoring_repair_scope_unavailable"):
        chat.patch(repair, _request(item))
    assert chat.candidate(item.candidate_id, "owner") == item


def test_actual_typed_browser_failure_allows_only_browser_inputs(tmp_path: Path) -> None:
    from test_authoring_collection_completeness import _raw
    from test_authoring_trial_diagnostics import _plan

    from capabilities.browser_session.handlers import SPEC, BrowserRequest, BrowserResult

    chat, _ = studio(tmp_path)
    _plan(chat, capability="operate")

    async def fail(context: RequestContext, inputs: Contract) -> Contract:
        BrowserRequest.model_validate(inputs)
        raise CapabilityExecutionFailed(
            "web_target_missing",
            BrowserResult(
                failed_action_index=0,
                failed_action_kind="read_table",
                failed_target_field="pagination.next",
            ),
            where="pagination.next",
        )

    chat.installed.register(
        SPEC, fail, BrowserRequest, BrowserResult, ExecutionDependencies(central_required=False)
    )
    raw = _raw()
    raw["steps"].append(
        {
            "capability": "lab/read-it@1.0.0",
            "inputs": {"value": {"source": "fixed", "value": "tested report\r\n"}},
        }
    )
    item, problems = chat.draft("owner", "session-1", "Browser report", raw)
    assert item is not None and not problems
    assert chat.execute("owner", item, {}, "typed-browser-scope")["status"] == "failed"
    current = chat.candidate(item.candidate_id, "owner")
    repair = context().model_copy(
        update={
            "message": f"[Host authoring continuation: failure] Candidate {item.candidate_id}; "
            "failure"
        }
    )
    actions = current.draft.model_dump(mode="json")["steps"][0]["inputs"]["actions"]["value"]
    actions[0]["table"] = "#repaired-table"
    request = {
        "candidate_id": current.candidate_id,
        "base_digest": digest(current.draft),
        "operations": [
            {"op": "replace", "path": ["steps", 0, "inputs", "actions", "value"], "value": actions}
        ],
    }
    changed, problems = chat.patch(repair, request)
    assert changed is not None and not problems
    assert changed.draft.steps[1] == item.draft.steps[1]
    assert changed.authoring_task is not None and changed.authoring_task.verified_digest is None


@pytest.mark.parametrize("kind", ["missing", "outside_store"])
def test_reference_metadata_cannot_authorize_missing_or_arbitrary_file(
    tmp_path: Path, kind: str
) -> None:
    chat, _ = studio(tmp_path)
    chat.attachments = AttachmentStore(tmp_path)
    item = _draft(chat)
    attachment = chat.attachments.add(
        "session-1", "source.json", b'{"binding":{"source":"fixed","value":"source"}}'
    )
    path = Path(attachment.path)
    if kind == "missing":
        path.unlink()
    else:
        outside = tmp_path / "outside.json"
        outside.write_text('{"binding":{"source":"fixed","value":"outside"}}', encoding="utf-8")
        metadata = path.parent / "attachment.json"
        metadata.write_text(
            attachment.model_copy(update={"path": str(outside)}).model_dump_json(), encoding="utf-8"
        )
    request = _request(item)
    request["operations"] = [
        {
            "op": "copy_reference",
            "attachment_id": attachment.file_id,
            "source_path": ["binding"],
            "path": ["steps", 0, "inputs", "value"],
        }
    ]
    with pytest.raises(ChatAuthoringError):
        chat.patch(context(), request)
    assert chat.candidate(item.candidate_id, "owner") == item


@pytest.mark.parametrize(
    "source", [b"not-json", b'{"script":1}' * 100000], ids=["invalid", "oversized"]
)
def test_invalid_or_oversized_reference_never_changes_candidate(
    tmp_path: Path, source: bytes
) -> None:
    chat, _ = studio(tmp_path)
    chat.attachments = AttachmentStore(tmp_path)
    item = _draft(chat)
    attachment = chat.attachments.add("session-1", "bad.json", source)
    request = _request(item)
    request["operations"] = [
        {
            "op": "copy_reference",
            "attachment_id": attachment.file_id,
            "source_path": ["script"],
            "path": ["steps", 0, "inputs", "value"],
        }
    ]
    with pytest.raises(ChatAuthoringError):
        chat.patch(context(), request)
    assert chat.candidate(item.candidate_id, "owner") == item
