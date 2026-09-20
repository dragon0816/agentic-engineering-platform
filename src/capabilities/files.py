"""Adapted source read_file tool as a typed read-only capability.

Source lineage, preserved invariants and intentional differences are recorded in
docs/PHASE_2_MIGRATION.md; the pinned oracle lives in tests/fixtures.
"""

import asyncio
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from capabilities.contracts import CapabilitySpec
from common.base import Contract
from common.execution import RequestContext

TEXT_EXTENSIONS = frozenset(
    {
        ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
        ".toml", ".ini", ".cfg", ".env", ".html", ".css", ".xml",
        ".csv", ".log", ".sh", ".bat", ".ps1", ".sql", ".rs", ".go",
        ".java", ".c", ".cpp", ".h", ".rb", ".php",
    }
)  # fmt: skip
MAX_FILE_BYTES = 500_000
ENCODING_FALLBACKS: tuple[str, ...] = ("utf-8", "utf-8-sig", "big5", "gbk", "latin-1")

ReadOutcome = Literal[
    "read",
    "outside_root",
    "not_found",
    "not_a_file",
    "unsupported_type",
    "too_large",
    "access_denied",
]

READ_FILE_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "filesystem", "name": "read-file", "version": "1.0.0"},
        "name": "filesystem.read_file",
        "description": "Read a bounded local text file with the source tool's limits",
        "input_contract": "filesystem.read-file.input.v1",
        "output_contract": "filesystem.read-file.output.v1",
        "side_effect": "read",
        "policy": {
            "required_permissions": ["filesystem.read"],
            "policy_refs": ["filesystem-read-policy"],
        },
    }
)


class ReadFileInput(Contract):
    """The path is always explicit; the source's natural-language guessing is not migrated."""

    path: str = Field(min_length=1)
    max_lines: int = Field(default=100, ge=1, le=10_000)


class ReadFileOutput(Contract):
    outcome: ReadOutcome
    name: str | None = None
    size_bytes: int | None = None
    encoding: str | None = None
    total_lines: int | None = None
    content: str | None = None
    truncated: bool = False

    @model_validator(mode="after")
    def complete_reads_only(self) -> Self:
        data = (self.name, self.size_bytes, self.encoding, self.total_lines, self.content)
        if self.outcome == "read":
            if any(field is None for field in data):
                raise ValueError("successful reads must carry file metadata and content")
        elif any(field is not None for field in data) or self.truncated:
            raise ValueError("failed reads cannot carry file data")
        return self


class ReadFileHandler:
    """Preserves the source check order: existence, file kind, extension, size, encoding.

    The allowed root is trusted host configuration, like a LocalPolicy grant. Symlink
    resolution happens before the containment check, and containment is checked before
    existence so nothing about paths outside the root is revealed.
    """

    def __init__(self, allowed_root: Path) -> None:
        self.allowed_root = allowed_root.resolve()

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = ReadFileInput.model_validate(inputs)
        return await asyncio.to_thread(self._read, request)

    def _read(self, request: ReadFileInput) -> ReadFileOutput:
        try:
            path = Path(request.path).resolve()
            if not path.is_relative_to(self.allowed_root):
                return ReadFileOutput(outcome="outside_root")
            if not path.exists():
                return ReadFileOutput(outcome="not_found")
            if not path.is_file():
                return ReadFileOutput(outcome="not_a_file")
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                return ReadFileOutput(outcome="unsupported_type")
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                return ReadFileOutput(outcome="too_large")
            content, encoding = _decode(path)
        except PermissionError:
            return ReadFileOutput(outcome="access_denied")
        lines = content.splitlines()
        total = len(lines)
        truncated = total > request.max_lines
        if truncated:
            content = "\n".join(lines[: request.max_lines])
        return ReadFileOutput(
            outcome="read",
            name=path.name,
            size_bytes=size,
            encoding=encoding,
            total_lines=total,
            content=content,
            truncated=truncated,
        )


def _decode(path: Path) -> tuple[str, str]:
    for encoding in ENCODING_FALLBACKS[:-1]:
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError:
            continue
    # The terminal latin-1 fallback decodes any byte sequence.
    return path.read_text(encoding=ENCODING_FALLBACKS[-1]), ENCODING_FALLBACKS[-1]
