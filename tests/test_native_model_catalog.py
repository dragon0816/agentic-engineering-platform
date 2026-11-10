"""Native metadata discovery must never submit an inference turn."""

import io
import json
from pathlib import Path
from typing import IO, Any

import pytest

from host_runtime.native_model_catalog import discover


class RecordedInput(io.StringIO):
    recorded = ""

    def close(self) -> None:
        if not self.closed:
            self.recorded = super().getvalue()
        super().close()

    def getvalue(self) -> str:
        return self.recorded if self.closed else super().getvalue()


class Process:
    stdin: IO[str] | None
    stdout: IO[str] | None

    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.stdin = RecordedInput()
        self.stdout = io.StringIO("".join(json.dumps(x) + "\n" for x in messages))
        self.killed = False

    def poll(self) -> int | None:
        return None

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        return 0


def test_codex_catalog_pagination_and_no_inference(tmp_path: Path) -> None:
    process = Process(
        [
            {"id": 1, "result": {}},
            {
                "id": 2,
                "result": {"data": [{"id": "m1", "model": "actual-1"}], "nextCursor": "next"},
            },
            {"id": 3, "result": {"data": [{"model": "actual-2"}], "nextCursor": None}},
        ]
    )
    argv: list[str] = []

    def launch(args: list[str], *_: Any) -> Process:
        argv.extend(args)
        return process

    result = discover("codex", "fixed-cli", tmp_path, {}, launcher=launch)
    assert result["models"] == ["actual-1", "actual-2"]
    assert isinstance(process.stdin, io.StringIO)
    requests = [json.loads(line) for line in process.stdin.getvalue().splitlines()]
    assert [x["method"] for x in requests] == [
        "initialize",
        "initialized",
        "model/list",
        "model/list",
    ]
    assert requests[2]["params"]["includeHidden"] is False
    assert process.killed
    assert "app-server" in argv


def test_claude_initialize_catalog_only(tmp_path: Path) -> None:
    process = Process(
        [
            {
                "type": "control_response",
                "response": {
                    "subtype": "success",
                    "request_id": "catalog",
                    "response": {
                        "models": [{"value": "sonnet", "displayName": "Sonnet"}],
                        "account": {"token": "DO-NOT-RETURN"},
                    },
                },
            }
        ]
    )
    argv: list[str] = []

    def launch(args: list[str], *_: Any) -> Process:
        argv.extend(args)
        return process

    result = discover("claude_code", "fixed-cli", tmp_path, {}, launcher=launch)
    assert result == {"ok": True, "models": ["sonnet"]}
    assert "DO-NOT-RETURN" not in str(result)
    assert isinstance(process.stdin, io.StringIO)
    request = json.loads(process.stdin.getvalue())
    assert request["request"]["subtype"] == "initialize"
    assert "user" not in request
    assert "--strict-mcp-config" in argv and "--tools" in argv
    assert process.killed


@pytest.mark.parametrize("output", ["not-json\n", "x" * 300_000], ids=["malformed", "oversized"])
def test_malformed_and_oversized_metadata_fail_closed(tmp_path: Path, output: str) -> None:
    process = Process([])
    process.stdout = io.StringIO(output)
    result = discover("codex", "fixed", tmp_path, {}, launcher=lambda *_: process)
    assert not result["ok"]
    assert result["models"] == []
    assert process.killed


def test_metadata_deadline_and_cleanup_without_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = Process([])
    # A live CLI with no metadata leaves the bounded request waiting.
    import threading

    monkeypatch.setattr(
        "host_runtime.native_model_catalog.MetadataChannel._read",
        lambda _: threading.Event().wait(0.2),
    )
    result = discover(
        "claude_code", "fixed", tmp_path, {}, launcher=lambda *_: process, timeout=0.01
    )
    assert result == {"ok": False, "code": "model_catalog_timeout", "models": []}
    assert process.killed
    assert isinstance(process.stdin, io.StringIO)
    assert json.loads(process.stdin.getvalue())["request"]["subtype"] == "initialize"
