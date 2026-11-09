"""File input checks run locally before dispatch, without authorizing file access."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_workflow_parameter_declaration import _manifest

from common.workflow_parameters import (
    WorkflowParameterError,
    validate_run_parameters,
    validate_static_settings,
)


def _file(**extra: Any) -> dict[str, Any]:
    return {"name": "lookup", "label": "Lookup", "kind": "file", **extra}


def test_input_contract_is_additive_and_only_applies_to_files() -> None:
    legacy = _manifest([_file()])
    assert "file_mode" not in legacy.parameters[0].model_dump(mode="json")
    declared = _manifest([_file(file_mode="input")])
    assert declared.parameters[0].model_dump(mode="json")["file_mode"] == "input"
    with pytest.raises(ValidationError, match="only file"):
        _manifest([_file(kind="text", file_mode="input")])


@pytest.mark.parametrize("file_mode", [None, "input", "output"])
def test_a_directory_never_satisfies_a_file_parameter(
    tmp_path: Path, file_mode: str | None
) -> None:
    manifest = _manifest([_file(file_mode=file_mode)])
    with pytest.raises(WorkflowParameterError, match="lookup .*file.*directory"):
        validate_run_parameters(manifest, {"lookup": str(tmp_path)})


def test_missing_declared_input_is_refused_but_output_destinations_remain_valid(
    tmp_path: Path,
) -> None:
    missing = str(tmp_path / "new.xlsx")
    with pytest.raises(WorkflowParameterError, match="lookup .*existing file"):
        validate_run_parameters(_manifest([_file(file_mode="input")]), {"lookup": missing})
    for mode in (None, "output"):
        assert validate_run_parameters(_manifest([_file(file_mode=mode)]), {"lookup": missing}) == {
            "lookup": missing
        }


def test_file_accept_and_multiple_values_are_checked(tmp_path: Path) -> None:
    workbook = tmp_path / "Owners.XLSX"
    workbook.write_bytes(b"fixture")
    other = tmp_path / "owners.txt"
    other.write_text("fixture", encoding="utf-8")
    manifest = _manifest([_file(file_mode="input", multiple=True, accept=["xlsx"])])
    assert validate_run_parameters(manifest, {"lookup": [str(workbook)]}) == {
        "lookup": [str(workbook)]
    }
    with pytest.raises(WorkflowParameterError, match="lookup .*accepted file type"):
        validate_run_parameters(manifest, {"lookup": [str(workbook), str(other)]})
    with pytest.raises(WorkflowParameterError, match="lookup .*existing file"):
        validate_run_parameters(manifest, {"lookup": [str(workbook), str(tmp_path / "gone.xlsx")]})


def test_required_defaults_are_applied_and_revalidated_at_run_time(tmp_path: Path) -> None:
    workbook = tmp_path / "owners.xlsx"
    workbook.write_bytes(b"fixture")
    manifest = _manifest([_file(file_mode="input", required=True, default=str(workbook))])
    assert validate_run_parameters(manifest, {}) == {"lookup": str(workbook)}
    workbook.unlink()
    with pytest.raises(WorkflowParameterError, match="lookup .*existing file"):
        validate_run_parameters(manifest, {})
    with pytest.raises(WorkflowParameterError, match="lookup is required"):
        validate_run_parameters(_manifest([_file(file_mode="input", required=True)]), {})
    assert validate_run_parameters(_manifest([_file(file_mode="input")]), {}) == {}


def test_static_input_defaults_receive_the_same_validation(tmp_path: Path) -> None:
    manifest = _manifest([_file(scope="static", file_mode="input", default=str(tmp_path))])
    with pytest.raises(WorkflowParameterError, match="lookup .*file.*directory"):
        validate_static_settings(manifest, {}, complete=True)
    with pytest.raises(WorkflowParameterError, match="lookup .*file.*directory"):
        validate_static_settings(manifest, {"lookup": str(tmp_path)}, complete=False)


def test_submitted_paths_are_not_unescaped_or_rewritten(tmp_path: Path) -> None:
    workbook = tmp_path / "owners.xlsx"
    workbook.write_bytes(b"fixture")
    submitted = str(workbook).replace("\\", "\\\\") if os.name == "nt" else str(workbook)
    manifest = _manifest([_file(file_mode="input")])
    assert validate_run_parameters(manifest, {"lookup": submitted}) == {"lookup": submitted}


@pytest.mark.parametrize(
    ("submitted_kind", "problem"),
    [
        ("folder", "file.*directory"),
        ("missing", "existing file"),
        ("unsupported", "accepted file type"),
    ],
)
def test_form_submission_is_rejected_before_any_workflow_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, submitted_kind: str, problem: str
) -> None:
    from test_chat_workflow_forms import _plain
    from test_conversation_turn_groups import _chat_config, _ChatGateway

    from host_runtime.contracts import WorkflowLaunchRequest
    from host_runtime.host import build_runtime
    from host_runtime.web import AgentWeb

    config, layout = _chat_config(tmp_path)
    manifest = _plain(
        "sales-order-report",
        [_file(name="owner_mapping_excel", required=True, file_mode="input", accept=[".xlsx"])],
    )
    supplied = tmp_path
    if submitted_kind == "missing":
        supplied = tmp_path / "missing.xlsx"
    elif submitted_kind == "unsupported":
        supplied = tmp_path / "owners.txt"
        supplied.write_text("fixture", encoding="utf-8")
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        (runtime.layout.workflows / "sales-order-report.json").write_text(
            manifest.model_dump_json(), encoding="utf-8"
        )
        calls: list[Any] = []

        async def unexpected_dispatch(*args: Any, **kwargs: Any) -> Any:
            calls.append((args, kwargs))
            raise AssertionError("invalid file reached execution")

        monkeypatch.setattr(type(runtime.agent), "execute_workflow", unexpected_dispatch)
        with pytest.raises(WorkflowParameterError, match="owner_mapping_excel .*" + problem):
            AgentWeb(runtime).launch_workflow(
                WorkflowLaunchRequest(
                    workflow=manifest.metadata.identity,
                    arguments={"owner_mapping_excel": str(supplied)},
                    idempotency_key="invalid-folder",
                )
            )
        assert calls == []
