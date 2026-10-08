"""`coding/run-python@1.0.0`: run one Python script for a conversation task.

The Agent writes a program for a task the person asked for in words, the host
runs it under the restricted runner, and the result (exit code, output, the
files in `output/`) goes back to the model so it can repair and run again.
Owner approval 2026-10-06 (coding_v1 G1), on the condition that Knowledge
asking and task/Workflow execution are not affected.

Bounds: the workspace must lie under a folder listed in the host's
`coding.workspace_roots`; the script can write only to the workspace's
`output/` and its own run folder (low integrity labels only those two);
`input/` and everything else stay read-only to it; no credential reaches it;
direct outbound network is blocked by the runner's firewall rule; memory cap
and timeout as for every coding run. Unlike `coding/change`, the script may
start a few child processes (`coding.run_python_max_processes`, default 4) so
it can run a command-line tool; they inherit the low-integrity token and die
with the run (owner decision 2026-10-06, lab gap L3). Each script is kept under
`.aep-run/` in the workspace as evidence.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from pathlib import Path

from pydantic import Field, JsonValue

from capabilities.coding_change.contracts import CodingHostBinding
from capabilities.coding_change.workspaces import containing_root
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract, Text
from common.execution import RequestContext
from harness.network_block import outbound_rule_present
from harness.restricted_runner import RestrictedRunner, RunnerError, RunnerLimits, label_low

RUN_SPEC = CapabilitySpec.model_validate({
    "identity": {"namespace": "coding", "name": "run-python", "version": "1.0.0"},
    "name": "coding.run_python",
    "description": (
        "Run one Python script in an allowed task workspace under restricted execution; "
        "it may write only to the workspace's output folder"
    ),
    "input_contract": "coding.run-python.input.v1",
    "output_contract": "coding.run-python.output.v1",
    "side_effect": "execute",
    "policy": {
        "risk": "medium",
        "approval_required": True,
        "required_permissions": ["coding.run-python"],
        "policy_refs": ["coding-restricted-execution-policy"],
    },
})
MAX_OUTPUT_CHARS = 12_000
MAX_FILES_LISTED = 200


class RunPythonRequest(Contract):
    workspace: Text
    script: Text = Field(max_length=200_000)


class RunPythonStepInput(Contract):
    request: RunPythonRequest
    # A Workflow's run values for the script (G4): written as JSON beside the
    # script, its path in AEP_WORKFLOW_PARAMS, so a saved script is rerun
    # with new values without changing its code.
    arguments: dict[str, JsonValue] | None = None


class OutputFile(Contract):
    path: str
    bytes: int


class RunPythonResult(Contract):
    exit_code: int | None
    timed_out: bool
    output: str
    files: tuple[OutputFile, ...]
    script_path: str


class RunPythonHandler:
    def __init__(
        self, binding: CodingHostBinding, *,
        rule_present: Callable[[Path], bool] = outbound_rule_present,
        extra_env: Mapping[str, str] | None = None,
    ) -> None:
        self.binding = binding
        self.rule_present = rule_present
        self.extra_env = dict(extra_env or {})

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step_input = RunPythonStepInput.model_validate(inputs)
        return await asyncio.to_thread(self.run, step_input.request, step_input.arguments)

    def _workspace(self, raw: str) -> Path:
        path = Path(raw.strip())
        if not path.is_absolute():
            raise CapabilityRefused("coding_workspace_not_absolute")
        resolved = containing_root(raw, self.binding.workspace_roots)
        if resolved is None:
            raise CapabilityRefused("coding_workspace_not_allowed")
        if not resolved.is_dir():
            raise CapabilityRefused("coding_workspace_missing")
        return resolved

    def run(
        self, request: RunPythonRequest, arguments: dict[str, JsonValue] | None = None
    ) -> RunPythonResult:
        workspace = self._workspace(request.workspace)
        python = Path(self.binding.runner_python)
        try:
            runner = RestrictedRunner(python, RunnerLimits(
                timeout_seconds=self.binding.timeout_seconds, memory_mb=self.binding.memory_mb,
                max_processes=self.binding.run_python_max_processes))
        except RunnerError as error:
            raise CapabilityRefused(error.code) from None
        if self.binding.require_network_block and not self.rule_present(python):
            raise CapabilityRefused("coding_network_block_missing")
        output = workspace / "output"
        output.mkdir(exist_ok=True)
        runs = workspace / ".aep-run"
        runs.mkdir(exist_ok=True)
        step = runs / f"run-{len(list(runs.glob('run-*'))) + 1:03d}"
        step.mkdir()
        script = step / "script.py"
        script.write_text(request.script, encoding="utf-8")
        env = dict(self.extra_env)
        if arguments is not None:
            params = step / "params.json"
            params.write_text(json.dumps(arguments, ensure_ascii=False, indent=1), encoding="utf-8")
            env["AEP_WORKFLOW_PARAMS"] = str(params)
        label_low(output)
        result = runner.run([str(script)], cwd=workspace, run_dir=step, extra_env=env)
        files = sorted(
            (OutputFile(path=item.relative_to(workspace).as_posix(), bytes=item.stat().st_size)
             for item in output.rglob("*") if item.is_file()),
            key=lambda item: item.path,
        )[:MAX_FILES_LISTED]
        return RunPythonResult(
            exit_code=result.exit_code, timed_out=result.timed_out,
            output=result.output[-MAX_OUTPUT_CHARS:], files=tuple(files),
            script_path=script.relative_to(workspace).as_posix(),
        )
