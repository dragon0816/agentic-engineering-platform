"""`coding/run-python@1.0.0`: execute Python in the actual IT-managed environment.

An absolute workspace organizes input/, output/ and retained .aep-run/ scripts.
No AEP folder ACL, restricted token or firewall-rule admission is added. OS and
service permissions, real timeouts/exit codes and redacted bounded output apply.
Only new or content-changed output artifacts count as this invocation's result;
JSON must be a complete bounded object before it can feed another Workflow step."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from time import monotonic

from pydantic import Field, JsonValue, TypeAdapter

from capabilities.coding_change.contracts import CodingHostBinding
from capabilities.coding_change.workspaces import create_workspace
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityExecutionFailed, CapabilityRefused
from common.base import Contract, Text
from common.execution import RequestContext
from harness.environment_runner import EnvironmentRunner
from harness.network_block import outbound_rule_present
from harness.restricted_runner import RunnerError, RunnerLimits

RUN_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "coding", "name": "run-python", "version": "1.0.0"},
        "name": "coding.run_python",
        "description": (
            "Run Python under the actual OS account in an absolute task folder. "
            "No AEP folder/firewall admission; retain script/parameters and output artifacts."
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
    }
)
MAX_OUTPUT_CHARS = 12_000
MAX_FILES_LISTED = 200
# Both scans are bounded independently; unknown freshness is never a success.
MAX_SCAN_FILES = 2_000
MAX_SCAN_ENTRIES = 10_000
MAX_SCAN_BYTES = 1024**3
MAX_SCAN_SECONDS = 10.0
SCAN_CHUNK_BYTES = 1024**2


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
    # The workspace did not exist and this run created it under its root.
    workspace_created: bool = False
    # Only an exact, complete bounded JSON object on stdout is composable.
    data: dict[str, JsonValue] | None = None


class RunPythonHandler:
    def __init__(
        self,
        binding: CodingHostBinding | None,
        *,
        rule_present: Callable[[Path], bool] = outbound_rule_present,
        extra_env: Mapping[str, str] | None = None,
    ) -> None:
        self.binding = binding
        self.rule_present = rule_present
        self.extra_env = dict(extra_env or {})

    @property
    def python(self) -> Path:
        return Path(self.binding.runner_python if self.binding else sys.executable)

    @property
    def timeout_seconds(self) -> int:
        return self.binding.timeout_seconds if self.binding else 120

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step_input = RunPythonStepInput.model_validate(inputs)
        result = await self._run_async(step_input.request, step_input.arguments)
        if result.timed_out:
            raise CapabilityExecutionFailed("coding_program_timeout", result)
        if result.exit_code != 0:
            raise CapabilityExecutionFailed("coding_program_failed", result)
        return result

    def _workspace(self, raw: str) -> Path:
        """The resolved workspace, checked but not created: it lies under a
        root, names no `..`, and is a folder or nothing yet."""
        path = Path(raw.strip())
        if not path.is_absolute():
            raise CapabilityRefused("coding_workspace_not_absolute")
        resolved = path.resolve()
        if resolved.exists() and not resolved.is_dir():
            raise CapabilityRefused("coding_workspace_not_a_folder")
        return resolved

    def run(
        self, request: RunPythonRequest, arguments: dict[str, JsonValue] | None = None
    ) -> RunPythonResult:
        return asyncio.run(self._run_async(request, arguments))

    async def _run_async(
        self, request: RunPythonRequest, arguments: dict[str, JsonValue] | None = None
    ) -> RunPythonResult:
        workspace = self._workspace(request.workspace)
        python = self.python
        try:
            runner = EnvironmentRunner(
                python,
                RunnerLimits(
                    timeout_seconds=self.timeout_seconds,
                ),
            )
        except RunnerError as error:
            raise CapabilityRefused(error.code) from None
        # Created only once every check passed, so a refused run leaves nothing.
        created = not workspace.is_dir()
        if created:
            create_workspace(workspace)
        output = workspace / "output"
        output.mkdir(exist_ok=True)
        before = _output_fingerprints(output)
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
        try:
            result = await runner.run_async(
                [str(script)], cwd=workspace, run_dir=step, extra_env=env
            )
        except RunnerError as error:
            raise CapabilityRefused(error.code) from None
        diagnostics = RunPythonResult(
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            output=result.output[-MAX_OUTPUT_CHARS:],
            files=(),
            script_path=script.relative_to(workspace).as_posix(),
            workspace_created=created,
            data=_structured_output(result.output),
        )
        try:
            after = _output_fingerprints(output)
        except CapabilityRefused as failure:
            raise CapabilityExecutionFailed(failure.code, diagnostics) from None
        files = sorted(
            (
                OutputFile(path=item.relative_to(workspace).as_posix(), bytes=item.stat().st_size)
                for item, digest in after.items()
                if before.get(item) != digest
            ),
            key=lambda item: item.path,
        )[:MAX_FILES_LISTED]
        return diagnostics.model_copy(update={"files": tuple(files)})


def _structured_output(output: str) -> dict[str, JsonValue] | None:
    if len(output) > MAX_OUTPUT_CHARS:
        return None
    try:
        data = TypeAdapter(dict[str, JsonValue]).validate_json(output, strict=True)
        # Pydantic's JSON reader accepts NaN/Infinity; exported data must be
        # ordinary transport-safe JSON, including deeply nested numeric values.
        json.dumps(data, allow_nan=False)
        return data
    except (ValueError, RecursionError):
        return None


def _output_fingerprints(output: Path) -> dict[Path, bytes]:
    """Bounded content evidence, independent of timestamps and file lengths.

    Count directories too so an empty historical tree cannot evade the bound.
    Stream checks also catch growing files without trusting their initial size.
    """
    deadline = monotonic() + MAX_SCAN_SECONDS
    fingerprints: dict[Path, bytes] = {}
    pending = [output]
    entries = total_bytes = 0

    def check_deadline() -> None:
        if monotonic() >= deadline:
            raise CapabilityRefused("coding_output_scan_limit")

    while pending:
        check_deadline()
        with os.scandir(pending.pop()) as directory:
            for entry in directory:
                check_deadline()
                entries += 1
                if entries > MAX_SCAN_ENTRIES:
                    raise CapabilityRefused("coding_output_scan_limit")
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file():
                    if len(fingerprints) >= MAX_SCAN_FILES:
                        raise CapabilityRefused("coding_output_scan_limit")
                    if total_bytes + entry.stat().st_size > MAX_SCAN_BYTES:
                        raise CapabilityRefused("coding_output_scan_limit")
                    digest = hashlib.sha256()
                    with open(entry.path, "rb") as stream:
                        while chunk := stream.read(SCAN_CHUNK_BYTES):
                            check_deadline()
                            total_bytes += len(chunk)
                            if total_bytes > MAX_SCAN_BYTES:
                                raise CapabilityRefused("coding_output_scan_limit")
                            digest.update(chunk)
                    check_deadline()
                    fingerprints[Path(entry.path)] = digest.digest()
    return fingerprints
