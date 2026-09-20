import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import JsonValue, ValidationError
from test_routing import FakeModel
from test_source_file_tools import source_tools

from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.files import READ_FILE_SPEC, ReadFileHandler, ReadFileInput, ReadFileOutput
from capabilities.runtime import (
    CapabilityGrant,
    CapabilityInvocation,
    InstalledCapabilities,
    LocalPolicy,
)
from common.assets import ExecutionDependencies
from common.evaluation import EvaluationCase
from common.execution import CapabilityResult, RequestContext, TraceIdentifiers
from workflow.dispatch import BridgeExecutor

ROOT = Path(__file__).resolve().parents[1]


class CountingHandler(ReadFileHandler):
    def __init__(self, allowed_root: Path) -> None:
        super().__init__(allowed_root)
        self.calls = 0

    async def __call__(self, context: RequestContext, inputs: Any) -> Any:
        self.calls += 1
        return await super().__call__(context, inputs)


def grant() -> CapabilityGrant:
    return CapabilityGrant.model_validate(
        {
            "actor": "engineer",
            "asset": READ_FILE_SPEC.identity,
            "permissions": ["filesystem.read"],
            "policy_refs": ["filesystem-read-policy"],
            "approval_ref": "filesystem-read-approval",
        }
    )


def bridge(handler: ReadFileHandler, *, granted: bool = True) -> BridgeExecutor:
    installed = InstalledCapabilities()
    installed.register(
        READ_FILE_SPEC,
        handler,
        ReadFileInput,
        ReadFileOutput,
        ExecutionDependencies(central_required=False),
    )
    return BridgeExecutor(installed, LocalPolicy((grant(),) if granted else ()))


def dispatch(executor: BridgeExecutor, **arguments: JsonValue) -> CapabilityResult:
    invocation = CapabilityInvocation(
        context=RequestContext(
            trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
            actor="engineer",
            namespace="filesystem",
            channel="test",
            message="read a file",
        ),
        target=READ_FILE_SPEC.identity,
        arguments=arguments,
    )
    return asyncio.run(executor.execute(invocation))


def test_read_dispatch_through_bridge_policy(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("alpha\nbeta\ngamma", encoding="utf-8")
    result = dispatch(bridge(ReadFileHandler(tmp_path)), path=str(target))
    assert result.status == "succeeded"
    output = ReadFileOutput.model_validate(result.data)
    assert output.outcome == "read"
    assert output.content == "alpha\nbeta\ngamma"
    assert output.encoding == "utf-8"
    assert output.name == "notes.txt"
    assert output.total_lines == 3
    assert output.truncated is False


def test_default_deny_never_touches_the_filesystem(tmp_path: Path) -> None:
    handler = CountingHandler(tmp_path)
    result = dispatch(bridge(handler, granted=False), path=str(tmp_path / "notes.txt"))
    assert result.failure is not None and result.failure.code == "permission_denied"
    assert handler.calls == 0


def test_reads_are_confined_to_the_allowed_root(tmp_path: Path) -> None:
    """Path confinement is an intentional difference; the source read any host path."""
    root = tmp_path / "inbox"
    root.mkdir()
    secret = tmp_path / "secrets.env"
    secret.write_text("token=synthetic", encoding="utf-8")
    executor = bridge(ReadFileHandler(root))
    for escape in (str(secret), str(root / ".." / "secrets.env")):
        output = ReadFileOutput.model_validate(dispatch(executor, path=escape).data)
        assert output.outcome == "outside_root"
        assert output.content is None


def test_outcomes_match_source_results(tmp_path: Path) -> None:
    binary = tmp_path / "firmware.bin"
    binary.write_bytes(b"\x00" * 600_000)
    big = tmp_path / "big.txt"
    big.write_bytes(b"a" * 500_001)
    scenarios = [
        (str(tmp_path / "absent.txt"), "not_found", "檔案不存在"),
        (str(tmp_path), "not_a_file", "這不是一個檔案"),
        (str(binary), "unsupported_type", "無法讀取二進位檔案"),
        (str(big), "too_large", "檔案太大"),
    ]
    executor = bridge(ReadFileHandler(tmp_path))
    oracle = source_tools()
    for path, outcome, source_marker in scenarios:
        assert source_marker in oracle.read_file(path=path)
        result = dispatch(executor, path=path)
        assert result.status == "succeeded"
        assert ReadFileOutput.model_validate(result.data).outcome == outcome


def test_encoding_fallback_order_is_preserved(tmp_path: Path) -> None:
    chinese = tmp_path / "big5.txt"
    chinese.write_bytes("中文".encode("big5"))
    arbitrary = tmp_path / "bytes.txt"
    arbitrary.write_bytes(b"\xff\xfe\x00\x01")
    executor = bridge(ReadFileHandler(tmp_path))
    decoded = ReadFileOutput.model_validate(dispatch(executor, path=str(chinese)).data)
    assert decoded.encoding == "big5"
    assert decoded.content == "中文"
    fallback = ReadFileOutput.model_validate(dispatch(executor, path=str(arbitrary)).data)
    assert fallback.encoding == "latin-1"


def test_bom_survives_like_the_source(tmp_path: Path) -> None:
    """utf-8 precedes utf-8-sig in the source, so a BOM stays in the content; pinned."""
    target = tmp_path / "bom.txt"
    target.write_bytes("\ufeffdata".encode("utf-8"))
    output = ReadFileOutput.model_validate(
        dispatch(bridge(ReadFileHandler(tmp_path)), path=str(target)).data
    )
    assert output.encoding == "utf-8"
    assert output.content is not None and output.content.startswith("\ufeff")


def test_truncation_matches_source(tmp_path: Path) -> None:
    lines = [f"line-{n}" for n in range(1, 151)]
    target = tmp_path / "long.log"
    target.write_text("\n".join(lines), encoding="utf-8")
    output = ReadFileOutput.model_validate(
        dispatch(bridge(ReadFileHandler(tmp_path)), path=str(target), max_lines=100).data
    )
    assert output.outcome == "read"
    assert output.truncated is True
    assert output.total_lines == 150
    assert output.content == "\n".join(lines[:100])


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"path": ""},
        {"path": "notes.txt", "max_lines": 0},
        {"path": "notes.txt", "max_lines": 10_001},
        {"task": "read C:/notes.txt"},
    ],
)
def test_explicit_validated_path_replaces_source_guessing(
    tmp_path: Path, arguments: dict[str, JsonValue]
) -> None:
    """No path is ever guessed from natural language; invalid input fails before the handler."""
    handler = CountingHandler(tmp_path)
    result = dispatch(bridge(handler), **arguments)
    assert result.failure is not None and result.failure.code == "invalid_input"
    assert handler.calls == 0


def test_output_contract_rejects_inconsistent_results() -> None:
    with pytest.raises(ValidationError):
        ReadFileOutput(outcome="not_found", content="data")
    with pytest.raises(ValidationError):
        ReadFileOutput(outcome="read", content="data")


def test_read_file_evaluation_case_routes_without_model() -> None:
    registry = SkillRegistry()
    for data in json.loads((ROOT / "skills/file-read.json").read_text(encoding="utf-8")):
        registry.register(SkillManifest.model_validate(data))
    cases = json.loads(
        (ROOT / "evaluation/cases/phase2-read-file.json").read_text(encoding="utf-8")
    )
    assert cases
    for payload in cases:
        case = EvaluationCase.model_validate(payload)
        model = FakeModel()
        result = RequestRouter(CommandRouter(registry), model=model).route(case.request)
        assert result.decision == case.expected_route
        assert result.origin == "deterministic"
        assert model.calls == []
