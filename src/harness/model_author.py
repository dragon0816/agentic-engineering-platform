"""A `ChangeAuthor` backed by the configured model (the internal Gateway).

The model proposes; it decides nothing. Scope comes from the request: the
plan always names exactly the declared files and every declared command,
whatever the model says, so it cannot narrow validation or widen the files it
may write. Each answer is one JSON object.

A change is explored, not dictated (`docs/phases/CODING_AT_SCALE.md`): the
model reads what it needs through bounded read-only actions and answers with
search/replace edits that AEP applies, so neither a large file nor its
rewrite has to fit in one prompt or one answer. A whole-file `content` answer
is still accepted for the primary file. Read-only context (the golden tests)
is given by the host, not chosen by the model.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from difflib import unified_diff
from typing import Any

from pydantic import ValidationError

from common.execution import TraceIdentifiers
from harness.contracts import (
    CandidateChange,
    CodingHarnessRequest,
    CommandOutcome,
    HarnessPlan,
    PlannedChange,
)
from harness.edits import EditRefused, FileText, apply_edits, parse_edits
from harness.repo_reader import ReadRefused, RepoReader
from harness.workspace import WorkspaceRefused
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

OUTPUT_CONTRACT = "coding.change-author.v1"
MAX_CONTEXT_FILE_CHARS = 20_000
MAX_OUTLINE_CHARS = 6_000
MAX_DIFF_CHARS = 12_000
# About 50k tokens of conversation; the oldest action outputs go first.
MAX_TRANSCRIPT_CHARS = 200_000
ELIDED = "(output elided to save space; repeat the action if you still need it)"
SYSTEM = (
    "You are the change author inside a bounded coding harness. You may change only the "
    "files you are told you may write, and the harness validates them with tests you "
    "cannot change. Answer every turn with a single JSON object and nothing else. Never "
    "claim tests pass; the harness runs them.\n"
    "Actions, one per turn:\n"
    '{"action": "list", "path": "folder"} lists a folder of the repository;\n'
    '{"action": "outline", "path": "file.py"} shows its classes and functions with lines;\n'
    '{"action": "read", "path": "file", "start": 1, "end": 200} shows numbered lines '
    "(at most 400 per read);\n"
    '{"action": "search", "text": "exact text", "glob": "src/**/*.py"} finds lines;\n'
    '{"action": "edit", "edits": [{"path": "file", "old": "exact current text", "new": '
    '"replacement"}]} changes files: "old" must match the current text exactly once '
    "(copy it from a read, without the line numbers, with its indentation); an empty "
    '"old" creates a new file. A failed batch changes nothing;\n'
    '{"action": "done"} hands your changes to the tests.\n'
    "Read only what you need: large files are read in ranges. Keep edits small and exact."
)


class AuthorUnavailable(WorkspaceRefused):
    """The model gave no usable answer; the run stops with this code."""


class ModelChangeAuthor:
    def __init__(
        self,
        model: ModelClient,
        model_alias: str,
        trace: TraceIdentifiers,
        context: Mapping[str, str],
        *,
        local_only: bool = False,
        max_output_tokens: int = 8_000,
        reader: RepoReader | None = None,
        max_turns: int = 30,
    ) -> None:
        self.model = model
        self.model_alias = model_alias
        self.trace = trace
        self.context = dict(context)
        self.local_only = local_only
        self.max_output_tokens = max_output_tokens
        self.reader = reader
        self.max_turns = max_turns
        # The files' LF text before this run, as last handed to the tests, and now.
        self._original: dict[str, str | None] | None = None
        self._baseline: dict[str, str | None] = {}
        self._texts: dict[str, str | None] = {}
        self._styles: dict[str, FileText] = {}

    def plan(self, request: CodingHarnessRequest) -> HarnessPlan:
        answer = self._ask(
            [
                self._opening(
                    request,
                    'First, plan. Return {"summary": one sentence on what you '
                    'will change, "purpose": what the change achieves}.',
                )
            ],
            max_output_tokens=600,
        )
        summary = _text(answer, "summary")
        purpose = _text(answer, "purpose")
        return HarnessPlan(
            summary=summary,
            changes=tuple(
                PlannedChange(path=path, purpose=purpose) for path in request.allowed_paths
            ),
            validation_commands=request.allowed_commands,
        )

    def initial_change(
        self, request: CodingHarnessRequest, plan: HarnessPlan
    ) -> tuple[CandidateChange, ...]:
        return self._explore(
            request,
            f"Plan: {plan.summary}\nNow make the change: read what you need, edit, then "
            'answer {"action": "done"}.',
        )

    def repair(
        self,
        request: CodingHarnessRequest,
        plan: HarnessPlan,
        failure: CommandOutcome,
        attempt: int,
    ) -> tuple[CandidateChange, ...]:
        failures = "\n\n".join(
            f"[{item.case} {item.code}] {item.message}" for item in failure.failures
        )
        return self._explore(
            request,
            f"Plan: {plan.summary}\nYour changes so far (diff against the repository):\n"
            f"{self._diff()}\n\nThey failed `{failure.command}` (repair attempt {attempt}):\n"
            f"{failures}\n\nFix them: read what you need, edit, then answer "
            '{"action": "done"}.',
        )

    # -- the exploration loop ----------------------------------------------------

    def _explore(
        self, request: CodingHarnessRequest, instruction: str
    ) -> tuple[CandidateChange, ...]:
        self._load(request)
        transcript = [self._opening(request, instruction)]
        for _turn in range(self.max_turns):
            answer = self._ask(transcript)
            transcript.append(("assistant", json.dumps(answer, ensure_ascii=False)))
            if "action" not in answer and "content" in answer:
                self._texts[request.artifact_path] = _text(answer, "content")
                return self._candidates(request)
            action = answer.get("action")
            if action == "done":
                if self._changed():
                    return self._candidates(request)
                observation = "You have not changed any file yet; edit first, then answer done."
            else:
                observation = self._act(action, answer)
            transcript.append(("user", observation))
            _trim(transcript)
        if self._changed():
            return self._candidates(request)
        raise AuthorUnavailable("author_turns_exhausted")

    def _act(self, action: object, answer: Mapping[str, Any]) -> str:
        overlay = {path: text for path, text in self._texts.items() if text is not None}
        try:
            if action == "edit":
                touched = apply_edits(self._texts, parse_edits(answer.get("edits")))
                self._texts.update(touched)
                return "Applied. Changed: " + ", ".join(sorted(touched))
            if self.reader is None:
                return "Reading is not available in this run; edit with what you were given."
            path = str(answer.get("path") or "")
            if action == "list":
                return self.reader.listing(path or ".")
            if action == "outline":
                return self.reader.outline(path, overlay)
            if action == "read":
                start, end = _int(answer.get("start"), 1), _int(answer.get("end"), 200)
                return self.reader.read(path, start, end, overlay)
            if action == "search":
                return self.reader.search(
                    str(answer.get("text") or ""), str(answer.get("glob") or "**/*"), overlay
                )
        except (EditRefused, ReadRefused) as refused:
            return f"Refused: {refused}"
        return f"Unknown action {action!r}; use list, outline, read, search, edit or done."

    def _load(self, request: CodingHarnessRequest) -> None:
        """The writable files as they are now (the worktree holds the last tested version)."""
        for path in request.allowed_paths:
            if self.reader is None:
                if path not in self._texts:
                    known = self.context.get(path)
                    self._texts[path] = None if known is None else known.replace("\r\n", "\n")
                    self._styles[path] = FileText("")
                continue
            target = self.reader.root / path
            if not target.is_file():
                self._texts[path] = None
                self._styles[path] = FileText("")
                continue
            try:
                style = FileText.decode(path, target.read_bytes())
            except EditRefused as refused:
                raise AuthorUnavailable(_refusal_code(str(refused))) from None
            self._texts[path] = style.text
            self._styles[path] = style
        self._baseline = dict(self._texts)
        if self._original is None:
            self._original = dict(self._texts)

    def _changed(self) -> bool:
        return any(self._texts[path] != self._baseline.get(path) for path in self._texts)

    def _candidates(self, request: CodingHarnessRequest) -> tuple[CandidateChange, ...]:
        changes: list[CandidateChange] = []
        for path in request.allowed_paths:
            text = self._texts.get(path)
            if text is None or text == self._baseline.get(path):
                continue
            try:
                changes.append(CandidateChange(path=path, content=self._styles[path].encode(text)))
            except ValidationError:
                raise AuthorUnavailable("author_change_has_credential") from None
        if not changes:
            raise AuthorUnavailable("author_answer_incomplete")
        return tuple(changes)

    def _diff(self) -> str:
        original = self._original or {}
        parts: list[str] = []
        for path, text in self._texts.items():
            before = original.get(path) or ""
            parts.extend(
                unified_diff(
                    before.splitlines(keepends=True),
                    (text or "").splitlines(keepends=True),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                )
            )
        diff = "".join(parts)
        if len(diff) > MAX_DIFF_CHARS:
            return diff[:MAX_DIFF_CHARS] + "\n(diff truncated; read the files for the rest)"
        return diff or "(no changes)"

    # -- prompts -------------------------------------------------------------------

    def _opening(self, request: CodingHarnessRequest, instruction: str) -> tuple[str, str]:
        files = "\n\n".join(
            f"--- {path} ---\n{_capped(text, MAX_CONTEXT_FILE_CHARS)}"
            for path, text in self.context.items()
        )
        return (
            "user",
            f"Requirement:\n{request.requirement}\n\n"
            f"Files you may write:\n{self._writable(request)}\n\n"
            f"Read-only context (current files):\n{files or '(none)'}\n\n{instruction}",
        )

    def _writable(self, request: CodingHarnessRequest) -> str:
        lines: list[str] = []
        for path in request.allowed_paths:
            marker = " (primary)" if path == request.artifact_path else ""
            if self.reader is None:
                lines.append(f"- {path}{marker}")
                continue
            try:
                outline = self.reader.outline(path, None)
            except ReadRefused:
                lines.append(f"- {path}{marker}: does not exist yet")
                continue
            lines.append(f"- {path}{marker}\n{_capped(outline, MAX_OUTLINE_CHARS)}")
        return "\n".join(lines)

    def _ask(
        self, transcript: list[tuple[str, str]], *, max_output_tokens: int = 0
    ) -> dict[str, Any]:
        messages = (
            ModelMessage(role="system", text=SYSTEM),
            *(ModelMessage(role=role, text=text) for role, text in transcript),
        )
        reply = self.model.generate(
            ModelRequest(
                trace=self.trace,
                model_alias=self.model_alias,
                messages=messages,
                requirements=ModelRequirements(structured_output=True, local_only=self.local_only),
                output_contract=OUTPUT_CONTRACT,
                max_output_tokens=max_output_tokens or self.max_output_tokens,
            )
        )
        if reply.failure is not None:
            raise AuthorUnavailable("author_model_failed")
        answer: object = reply.structured_output
        if answer is None:
            answer = _salvage(reply.text)
        if not isinstance(answer, dict):
            raise AuthorUnavailable("author_answer_unparseable")
        return answer


def _trim(transcript: list[tuple[str, str]]) -> None:
    """Elide the oldest action outputs (never the opening) until it fits."""
    total = sum(len(text) for _role, text in transcript)
    for index in range(1, len(transcript)):
        if total <= MAX_TRANSCRIPT_CHARS:
            return
        role, text = transcript[index]
        if role == "user" and text != ELIDED:
            transcript[index] = (role, ELIDED)
            total -= len(text) - len(ELIDED)


def _capped(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n(cut at {limit} of {len(text)} characters; read the rest in ranges)"


def _refusal_code(message: str) -> str:
    return "author_file_not_utf8" if "UTF-8" in message else "author_file_mixed_newlines"


def _int(value: object, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _text(answer: Mapping[str, Any], field: str) -> str:
    value = answer.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AuthorUnavailable("author_answer_incomplete")
    return value


def _salvage(text: str) -> object:
    """A fenced or prefixed JSON object, which some models return anyway."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except ValueError:
        return None
