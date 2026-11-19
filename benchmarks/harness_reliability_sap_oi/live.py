"""SOP-driven native AEP run; every model exchange is saved without credentials."""

import argparse
import asyncio
import csv
import hashlib
import json
import os
import shutil
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.backend_contracts import ConversationLimits
from agent.gateway import Gateway
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillRegistry
from capabilities.browser_session.handlers import (
    SPEC as BROWSER_SPEC,
)
from capabilities.browser_session.handlers import (
    BrowserRequest,
    BrowserResult,
    BrowserSessionHandler,
)
from capabilities.coding_change.contracts import CodingHostBinding
from capabilities.coding_change.manifest import coding_skill, run_python_workflow
from capabilities.coding_change.run_python import (
    RUN_SPEC,
    RunPythonHandler,
    RunPythonResult,
    RunPythonStepInput,
)
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies
from common.execution import Failure, RequestContext, TraceIdentifiers
from host_runtime.bridge_tools import _tool, bridge_tools
from host_runtime.contracts import ModelBinding
from host_runtime.state import SqliteLocalState
from models.clients import ModelClients
from models.contracts import ModelMessage, ModelRequest, ModelResponse
from models.credentials import EnvironmentCredentials
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

from .acceptance import task_passed
from .adapter import SPEC as EXPORT_SPEC
from .adapter import ExportHandler, ExportInput, ExportResult
from .environment import disable_test_telegram
from .oracle import verify_workbook

HERE = Path(__file__).resolve().parent


class RecordedModel:
    def __init__(self, model: Any, evidence: Path) -> None:
        self.model = model
        self.evidence = evidence
        self.turns: list[tuple[ModelRequest, ModelResponse]] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        number = len(self.turns) + 1
        (self.evidence / f"model-{number:02d}-request.json").write_text(
            request.model_dump_json(indent=2), encoding="utf-8"
        )
        response: ModelResponse = self.model.generate(request)
        (self.evidence / f"model-{number:02d}-response.json").write_text(
            response.model_dump_json(indent=2), encoding="utf-8"
        )
        self.turns.append((request, response))
        print(
            f"model_turn={number} tools={len(response.tool_calls)} "
            f"failure={response.failure.code if response.failure else 'none'}",
            flush=True,
        )
        return response


async def run(args: argparse.Namespace) -> int:
    disable_test_telegram()
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / "input").mkdir()
    (workspace / "output").mkdir()
    evidence = workspace / "evidence"
    evidence.mkdir()
    sop = (HERE / "SOP.md").read_text(encoding="utf-8")
    shutil.copyfile(HERE / "SOP.md", workspace / "SOP.md")
    for name in (
        "build.mjs",
        "render.mjs",
        "workbook.py",
        "adapter.py",
        "pivot_package.py",
        "oracle.py",
        "live.py",
        "site.py",
        "environment.py",
        "acceptance.py",
    ):
        shutil.copyfile(HERE / name, evidence / name)
    if args.secret_file:
        os.environ["AEP_GATEWAY_59_KEY"] = args.secret_file.read_text(encoding="utf-8").strip()
    config = json.loads(args.model_config.read_text(encoding="utf-8"))
    endpoint = config["models"]["catalog"]["endpoints"][0]
    endpoint["capabilities"].update(tool_calling=True, max_context_tokens=65536)
    binding = ModelBinding.model_validate(config["models"])
    resolver = EnvironmentCredentials(
        {x["secret"]: x["environment_variable"] for x in config["credentials"]}
    )
    model = ModelClients(
        binding.catalog, resolver=resolver, options=binding.options, timeout_s=90
    ).for_alias(binding.routing_alias)
    if isinstance(model, Failure):
        raise RuntimeError(model.code)
    recorder = RecordedModel(model, evidence)
    browser = BrowserSessionHandler(
        (args.url,),
        workspace / "browser-profile",
        headless=True,
        timeout_s=20,
        workspace_roots=(str(workspace),),
    )
    python = RunPythonHandler(
        CodingHostBinding.model_validate(
            {
                "runner_python": str(Path(getattr(sys, "_base_executable", sys.executable))),
                "timeout_seconds": 45,
                "repositories": [
                    {"name": "synthetic", "path": str(workspace), "writable": ["*.py"]}
                ],
                "workspace_roots": [str(workspace)],
            }
        ),
        rule_present=lambda _: True,
        extra_env={},
    )
    exporter = ExportHandler(workspace, args.url)
    installed = InstalledCapabilities()
    for spec, handler, input_type, output_type in (
        (BROWSER_SPEC, browser, BrowserRequest, BrowserResult),
        (RUN_SPEC, python, RunPythonStepInput, RunPythonResult),
        (EXPORT_SPEC, exporter, ExportInput, ExportResult),
    ):
        installed.register(
            spec, handler, input_type, output_type, ExecutionDependencies(central_required=False)
        )
    grants = tuple(
        CapabilityGrant(
            actor="engineer",
            asset=spec.identity,
            permissions=spec.policy.required_permissions,
            policy_refs=spec.policy.policy_refs,
            approval_ref="synthetic-task-authorized",
        )
        for spec in (BROWSER_SPEC, RUN_SPEC, EXPORT_SPEC)
    )
    bridge = BridgeExecutor(installed, LocalPolicy(grants), timeout_seconds=120)
    skills = SkillRegistry()
    skills.register(coding_skill())
    export_guide = (
        "After browser download, use coding__run to write output/normalized.json (a JSON list). "
        "Each row has document,line,created_at,sales,customer,status,currency,amount (number),"
        "fx (number),month. Preserve identifiers as strings; date-time YYYY-MM-DD HH:MM:SS. "
        "Apply SOP exactly. Pass its absolute normalized_path here. This benchmark-only tool "
        "authors Excel with native PivotTable parts and mandatory independent acceptance. "
        "It returns structured failure if validation fails. It does not fetch or normalize source."
    )
    export_tool = _tool(
        bridge,
        "oi__export",
        export_guide,
        EXPORT_SPEC.identity,
        ExportInput.model_json_schema(),
    )
    tools = [*bridge_tools(bridge), replace(export_tool, side_effect="write")]
    workflows = InstalledWorkflows()
    workflows.register(run_python_workflow())
    gateway = Gateway(
        RequestRouter(
            CommandRouter(skills), recorder, model_alias=binding.routing_alias, local_only=False
        ),
        bridge,
        WorkflowEngine(workflows, bridge),
        workspace_roots=(str(workspace),),
        host_tools=lambda: tools,
    )
    prompt = (
        f"請實際完成以下受控任務，不是只提供建議。模擬 SAP 網址：{args.url}。"
        f"唯一任務工作目錄：{workspace}。所有步驟與輸出已授權，資料全為虛構。"
        "先用 browser__operate 觀察網頁，再依 SOP 操作篩選並以瀏覽器下載所有篩選資料。"
        "日期欄位已有 SOP 預設值，但仍需核對。用 coding__run 撰寫並執行 CSV 正規化程式，"
        "只用 Python 標準函式庫，將結果寫到 output/normalized.json。"
        "瀏覽器下載資料不得用程式 requests/fetch 取代。不要硬編造來源列。"
        "下載按鈕必須使用 do=download，不能先 do=click，以確保檔案只保存於任務目錄。"
        "最後呼叫 oi__export 製作 Excel 並查看其獨立驗收結果。失敗須修正，通過後才回報完成。"
        "不用建立或安裝可重用 Workflow。請以中文說明每個操作及最後結果。\n\n" + sop
    )
    (workspace / "task-request.md").write_text(prompt, encoding="utf-8")
    trace = TraceIdentifiers(
        trace_id="sap-oi-simulation", request_id=workspace.name, span_id="native-loop"
    )
    started = datetime.now(UTC)
    try:
        with SqliteLocalState(workspace / "state.sqlite", bridge_id="synthetic-141") as state:
            bridge.operations = state
            result = await gateway.converse(
                RequestContext(
                    trace=trace,
                    actor="engineer",
                    namespace="engineering",
                    channel="test",
                    message=prompt,
                ),
                (ModelMessage(role="user", text=prompt),),
                allowed_tools=frozenset({"browser__operate", "coding__run", "oi__export"}),
                max_turns=12,
                limits=ConversationLimits(time_limit_seconds=600),
            )
            (workspace / "conversation-result.json").write_text(
                result.model_dump_json(indent=2), encoding="utf-8"
            )
            (workspace / "final-answer.md").write_text(result.text, encoding="utf-8")
            operations = [row.model_dump(mode="json") for row in reversed(state.operations())]
            (evidence / "operations.json").write_text(
                json.dumps(operations, indent=2), encoding="utf-8"
            )
        report: dict[str, Any] = {
            "conversation_status": result.status,
            "model_turns": result.model_turns,
            "tool_calls": len(result.tools),
            "started_at": started.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
        }
        try:
            report.update(verify_workbook(workspace / "output/sales-oi-pivot.xlsx"))
            downloads = list((workspace / "output/downloads").iterdir())
            with downloads[0].open(encoding="utf-8-sig", newline="") as stream:
                report["browser_export_rows"] = len(list(csv.DictReader(stream)))
            report["artifact_passed"] = report["passed"]
            checks = sorted(evidence.glob("verification-*.json"))
            last_check = json.loads(checks[-1].read_text(encoding="utf-8")) if checks else {}
            report["exporter_passed"] = last_check.get("passed") is True
            report["passed"] = task_passed(
                result.status,
                report["artifact_passed"],
                report["exporter_passed"],
                report["browser_export_rows"],
            )
        except Exception as error:
            report.update(passed=False, verification_error=type(error).__name__ + ": " + str(error))
        (workspace / "validation.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    finally:
        if browser._browser is not None:
            browser._browser.screenshot(evidence / "sap-final-page.png")
        browser.close()
        lines = ["# AEP 過程對話（完整模型回應及工具回饋）", "", "## 原始任務", "", prompt]
        seen: set[str] = set()
        for i, (request, response) in enumerate(recorder.turns, 1):
            for message in request.messages:
                if message.role == "tool":
                    token = str(message.tool_call_id) + message.text
                    if token not in seen:
                        seen.add(token)
                        lines.extend(
                            [
                                "",
                                f"### 工具結果 {message.tool_call_id}",
                                "```json",
                                message.text,
                                "```",
                            ]
                        )
            lines.extend(["", f"## 模型回合 {i}", "", response.text])
            for call in response.tool_calls:
                lines.extend(
                    [
                        "",
                        f"### 工具呼叫 {call.name} ({call.call_id})",
                        "```json",
                        json.dumps(call.arguments, ensure_ascii=False, indent=2),
                        "```",
                    ]
                )
            if response.failure:
                lines.extend(["", "模型錯誤：" + response.failure.model_dump_json()])
        (workspace / "dialogue.md").write_text("\n".join(lines), encoding="utf-8")
        scripts = workspace / "output" / "scripts"
        scripts.mkdir(exist_ok=True)
        for index, script in enumerate(sorted(workspace.rglob("script.py")), 1):
            shutil.copyfile(script, scripts / f"generated-{index:02d}.py")
        manifest = {
            str(p.relative_to(workspace)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in workspace.rglob("*")
            if p.is_file()
            and "browser-profile" not in p.parts
            and p.name not in {"state.sqlite-shm", "state.sqlite-wal", "manifest.json"}
        }
        (workspace / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report["passed"] else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--secret-file", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8766")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
