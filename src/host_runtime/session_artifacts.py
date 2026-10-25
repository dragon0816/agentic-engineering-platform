"""What a session produced, kept for that session (owner, Telegram, 2026-10-25).

The SDE weekly report ran in a chat at 15:15 and made its chart; at 16:57 the
owner asked to have the chart posted and the agent said it had no file and
asked for a path. The run's result had been one short line in a twelve-message
window and the chart was never named anywhere the model could see.

This module keeps, per session and actor, the Workflow runs of that session
(name, run id, status, a one-line summary) and the files and drafts they or a
tool made (a short id, a kind and a file name). Two things read it:

- the Gateway puts a compact list of it into each turn's system prompt
  (`guidance`), so it survives any history window; it is capped instead
  (`MAX_SHOWN_RUNS`, `MAX_SHOWN_FILES`), which keeps the window for the
  conversation itself;
- `session__attach_file {artifact_id}` attaches one of those files to the
  reply. Only an id recorded for this session and this actor is accepted, and
  only a file that still lies in the workspace; any other id, a path, or
  another person's file is refused by code. The model never sees a path:
  the channel resolves the id again when it sends the file.

docs/DECISIONS.md 2026-10-25 "A session remembers what it produced";
docs/CONTRACTS.md "Session artifacts and session__attach_file".
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, JsonValue

from agent.gateway import HostTool, HostToolOutcome
from common.base import Contract, Text
from common.execution import Failure, RequestContext
from host_runtime.workspace import write_atomically
from models.contracts import ModelTool
from workflow.engine import WorkflowRunSnapshot

ATTACH_TOOL = "session__attach_file"
#: What a session keeps, newest last; older entries drop out first.
MAX_RUNS = 20
MAX_ARTIFACTS = 60
#: What each turn's system prompt lists of it.
MAX_SHOWN_RUNS = 8
MAX_SHOWN_FILES = 24
MAX_SUMMARY_CHARS = 160
_ID = re.compile(r"^f[0-9]{1,4}$")

ArtifactKind = Literal["image", "spreadsheet", "document", "mail draft", "file"]

#: Output fields whose value is a file a step made (not an input it read,
#: such as `workbook_path`, nor a safety copy, such as `backup_path`).
OUTPUT_PATH_KEYS = frozenset({"chart_path", "png_path", "html_path", "output_path"})
#: Output fields holding a list of `{path, ...}` entries a step made.
OUTPUT_LIST_KEYS = frozenset({"attach", "files"})

_IMAGE = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})
_SHEET = frozenset({".xlsx", ".xlsm", ".xls", ".csv"})
_DOCUMENT = frozenset({".docx", ".doc", ".pdf", ".pptx", ".md", ".html", ".htm", ".txt"})

_LOG = logging.getLogger(__name__)


def kind_of(path: str) -> ArtifactKind:
    suffix = Path(path).suffix.lower()
    if suffix in _IMAGE:
        return "image"
    if suffix in _SHEET:
        return "spreadsheet"
    if suffix in _DOCUMENT:
        return "document"
    return "file"


class SessionArtifact(Contract):
    """One file or draft this session produced. `path` is the Host's, never
    shown to the model; a mail draft has none (it lives in Outlook)."""

    artifact_id: str = Field(pattern=_ID.pattern)
    kind: ArtifactKind
    filename: Text
    path: str = ""
    run_id: str | None = None
    workflow: str | None = None
    created_at: datetime


class SessionRun(Contract):
    run_id: str
    workflow: Text
    status: Text
    summary: Text = ""
    artifact_ids: tuple[str, ...] = ()
    created_at: datetime


class SessionLedger(Contract):
    session_id: Text
    actor: Text
    next_id: int = Field(default=1, ge=1, strict=True)
    runs: tuple[SessionRun, ...] = ()
    artifacts: tuple[SessionArtifact, ...] = ()


class SessionArtifactError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _workflow_name(snapshot: WorkflowRunSnapshot) -> str:
    return snapshot.run.workflow.name


def run_summary(snapshot: WorkflowRunSnapshot) -> str:
    """One line: the last step's own summary or preview, else the step count."""
    run = snapshot.run
    if run.failure is not None:
        return f"{run.completed_steps} step(s), stopped: {run.failure.code}"
    for result in reversed(snapshot.step_results):
        data = result.data if isinstance(result.data, dict) else {}
        for key in ("summary", "preview", "message"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                line = next(part.strip() for part in value.splitlines() if part.strip())
                return line[:MAX_SUMMARY_CHARS]
    return f"{run.completed_steps} step(s)"


def _output_files(data: JsonValue, depth: int = 0) -> Iterable[str]:
    """Paths under the known output fields of a step's data, in order."""
    if depth > 4:
        return
    if isinstance(data, dict):
        for key, value in data.items():
            if key in OUTPUT_PATH_KEYS and isinstance(value, str) and value:
                yield value
            elif key in OUTPUT_LIST_KEYS and isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                        yield str(entry["path"])
            elif isinstance(value, dict | list):
                yield from _output_files(value, depth + 1)
    elif isinstance(data, list):
        for entry in data:
            yield from _output_files(entry, depth + 1)


def _mail_drafts(data: JsonValue) -> Iterable[str]:
    """The subject of a mail draft a step saved (an Outlook item, not a file)."""
    if (
        isinstance(data, dict)
        and isinstance(data.get("entry_id"), str)
        and data["entry_id"]
        and isinstance(data.get("subject"), str)
        and not data.get("skipped")
    ):
        yield str(data["subject"])


class SessionArtifacts:
    """The ledger of each (session, actor), one JSON file each under
    `<workspace>/session-artifacts/`; ids and names only, never content."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.root = self.workspace_root / "session-artifacts"
        self._lock = threading.Lock()

    # -- storage ---------------------------------------------------------------

    def _file(self, session_id: str, actor: str) -> Path:
        digest = hashlib.sha256(f"{session_id}\0{actor}".encode()).hexdigest()[:32]
        return self.root / f"{digest}.json"

    def ledger(self, session_id: str, actor: str) -> SessionLedger:
        path = self._file(session_id, actor)
        try:
            found = SessionLedger.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return SessionLedger(session_id=session_id, actor=actor)
        if found.session_id != session_id or found.actor != actor:
            return SessionLedger(session_id=session_id, actor=actor)
        return found

    def _save(self, ledger: SessionLedger) -> None:
        kept = ledger.model_copy(
            update={"runs": ledger.runs[-MAX_RUNS:], "artifacts": ledger.artifacts[-MAX_ARTIFACTS:]}
        )
        write_atomically(
            self._file(ledger.session_id, ledger.actor),
            kept.model_dump_json(indent=2).encode("utf-8"),
        )

    def clear(self, session_id: str, actor: str) -> None:
        """A fresh conversation (Telegram /new) starts with nothing produced."""
        with self._lock:
            try:
                self._file(session_id, actor).unlink()
            except OSError:
                pass

    # -- recording -------------------------------------------------------------

    def _inside(self, path: str) -> Path | None:
        try:
            target = Path(path).resolve()
        except (OSError, ValueError):
            return None
        if not target.is_relative_to(self.workspace_root) or not target.is_file():
            return None
        return target

    def _add(
        self,
        ledger: SessionLedger,
        kind: ArtifactKind,
        filename: str,
        path: str,
        run_id: str | None,
        workflow: str | None,
        now: datetime,
    ) -> tuple[SessionLedger, str]:
        for existing in ledger.artifacts:
            if path and existing.path == path and existing.run_id == run_id:
                return ledger, existing.artifact_id
        artifact = SessionArtifact(
            artifact_id=f"f{ledger.next_id}",
            kind=kind,
            filename=filename[:200] or "file",
            path=path,
            run_id=run_id,
            workflow=workflow,
            created_at=now,
        )
        return (
            ledger.model_copy(
                update={"next_id": ledger.next_id + 1, "artifacts": (*ledger.artifacts, artifact)}
            ),
            artifact.artifact_id,
        )

    def record_run(
        self, session_id: str | None, actor: str, snapshot: WorkflowRunSnapshot | None
    ) -> SessionRun | None:
        """Keep one finished run and what it made; None when there is no
        session or no run. Files outside the workspace are not kept."""
        if not session_id or snapshot is None:
            return None
        now = datetime.now(UTC)
        name = _workflow_name(snapshot)
        with self._lock:
            ledger = self.ledger(session_id, actor)
            for known in ledger.runs:
                if known.run_id == snapshot.run.run_id:
                    return known
            ids: list[str] = []
            for result in snapshot.step_results:
                for raw in _output_files(result.data):
                    target = self._inside(raw)
                    if target is None:
                        continue
                    ledger, artifact_id = self._add(
                        ledger,
                        kind_of(str(target)),
                        target.name,
                        str(target),
                        snapshot.run.run_id,
                        name,
                        now,
                    )
                    if artifact_id not in ids:
                        ids.append(artifact_id)
                for subject in _mail_drafts(result.data):
                    ledger, artifact_id = self._add(
                        ledger, "mail draft", subject, "", snapshot.run.run_id, name, now
                    )
                    ids.append(artifact_id)
            run = SessionRun(
                run_id=snapshot.run.run_id,
                workflow=name,
                status=snapshot.run.status,
                summary=run_summary(snapshot),
                artifact_ids=tuple(ids),
                created_at=now,
            )
            self._save(ledger.model_copy(update={"runs": (*ledger.runs, run)}))
        _LOG.info("session artifacts: recorded a run with %d output(s)", len(ids))
        return run

    def record_files(
        self, session_id: str | None, actor: str, files: Sequence[Mapping[str, Any]]
    ) -> list[str]:
        """Files a tool made for an answer in this session (an org chart)."""
        if not session_id or not files:
            return []
        now = datetime.now(UTC)
        ids: list[str] = []
        with self._lock:
            ledger = self.ledger(session_id, actor)
            for entry in files:
                target = self._inside(str(entry.get("path") or ""))
                if target is None:
                    continue
                ledger, artifact_id = self._add(
                    ledger,
                    kind_of(str(target)),
                    str(entry.get("filename") or target.name),
                    str(target),
                    None,
                    None,
                    now,
                )
                ids.append(artifact_id)
            if ids:
                self._save(ledger)
        return ids

    def record_turn(self, session_id: str | None, actor: str, result: Any) -> None:
        """What a model turn made: Workflows it ran and files a host tool
        produced (not the files it re-attached, which are already here)."""
        if not session_id or result is None:
            return
        for item in getattr(result, "tools", ()):
            if item.workflow is not None:
                self.record_run(session_id, actor, item.workflow)
            host = item.host
            if host is None or host.status != "succeeded" or item.name == ATTACH_TOOL:
                continue
            data = host.data if isinstance(host.data, dict) else {}
            attach = data.get("attach")
            if isinstance(attach, list):
                self.record_files(
                    session_id, actor, [entry for entry in attach if isinstance(entry, dict)]
                )

    # -- reading ---------------------------------------------------------------

    def run_images(self, session_id: str | None, actor: str, run_id: str) -> list[SessionArtifact]:
        """The pictures one recorded run made, to show at the end of the run."""
        if not session_id:
            return []
        ledger = self.ledger(session_id, actor)
        return [
            item
            for item in ledger.artifacts
            if item.run_id == run_id and item.kind == "image" and self._inside(item.path)
        ]

    def resolve(self, session_id: str | None, actor: str, artifact_id: object) -> SessionArtifact:
        """The file an id names in this session for this actor, or why not."""
        if not session_id:
            raise SessionArtifactError("attach_no_session")
        if not isinstance(artifact_id, str) or not _ID.match(artifact_id.strip()):
            raise SessionArtifactError("artifact_id_invalid")
        wanted = artifact_id.strip()
        found = next(
            (
                item
                for item in self.ledger(session_id, actor).artifacts
                if item.artifact_id == wanted
            ),
            None,
        )
        if found is None:
            raise SessionArtifactError("artifact_unknown")
        if not found.path:
            raise SessionArtifactError("artifact_not_a_file")
        if self._inside(found.path) is None:
            raise SessionArtifactError("artifact_missing")
        return found

    def attached(self, session_id: str | None, actor: str, result: Any) -> list[dict[str, str]]:
        """The files `session__attach_file` attached in this turn, resolved
        again here (the model's data carries ids only), each once."""
        files: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in getattr(result, "tools", ()) if result is not None else ():
            host = item.host
            if item.name != ATTACH_TOOL or host is None or host.status != "succeeded":
                continue
            data = host.data if isinstance(host.data, dict) else {}
            try:
                found = self.resolve(session_id, actor, data.get("artifact_id"))
            except SessionArtifactError:
                continue
            if found.path in seen:
                continue
            seen.add(found.path)
            files.append(
                {
                    "filename": found.filename,
                    "kind": "image" if found.kind == "image" else _web_kind(found.path),
                    "path": found.path,
                }
            )
        return files

    def guidance(self, context: RequestContext) -> str:
        """The pinned list for a turn's system prompt; empty without one."""
        if not context.session_id:
            return ""
        ledger = self.ledger(context.session_id, context.actor)
        if not ledger.runs and not ledger.artifacts:
            return ""
        by_id = {item.artifact_id: item for item in ledger.artifacts}
        lines = [
            "What this session already produced (kept for the whole session, newest last; "
            "names only, no contents). When the person asks to see, post, send or attach one "
            f"of these again, call {ATTACH_TOOL} with its id; never ask the person for a path "
            "or file you made. A mail draft is in Outlook and cannot be attached."
        ]
        shown = 0
        for run in ledger.runs[-MAX_SHOWN_RUNS:]:
            lines.append(
                f"- Workflow {run.workflow} run {run.run_id}: {run.status}"
                + (f" — {run.summary}" if run.summary else "")
            )
            for artifact_id in run.artifact_ids:
                item = by_id.get(artifact_id)
                if item is None or shown >= MAX_SHOWN_FILES:
                    continue
                lines.append(f"  - {item.artifact_id} {item.kind}: {item.filename}")
                shown += 1
        loose = [item for item in ledger.artifacts if item.run_id is None]
        for item in loose[-max(0, MAX_SHOWN_FILES - shown) :] if shown < MAX_SHOWN_FILES else ():
            lines.append(f"- {item.artifact_id} {item.kind} (made by a tool): {item.filename}")
        return "\n".join(lines)

    # -- the model's tool ------------------------------------------------------

    def tools(self) -> Sequence[HostTool]:
        return (HostTool(tool=ATTACH_MODEL_TOOL, handler=self._attach),)

    async def _attach(
        self, context: RequestContext, arguments: dict[str, JsonValue]
    ) -> HostToolOutcome:
        try:
            found = self.resolve(context.session_id, context.actor, arguments.get("artifact_id"))
        except SessionArtifactError as error:
            _LOG.info("session attach refused: %s", error.code)
            return HostToolOutcome(
                status="failed",
                failure=Failure(code=error.code, message=_REFUSALS[error.code]),
            )
        _LOG.info("session attach: 1 file")
        return HostToolOutcome(
            status="succeeded",
            data={
                "artifact_id": found.artifact_id,
                "kind": found.kind,
                "filename": found.filename,
                "note": "Attached to your reply; the person will see it under your answer.",
            },
        )


def _web_kind(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in (".html", ".htm"):
        return "html"
    if suffix in (".md", ".markdown"):
        return "md"
    if suffix == ".csv":
        return "csv"
    return "text" if suffix == ".txt" else "file"


_REFUSALS = {
    "attach_no_session": "Attaching needs a conversation; this request has none.",
    "artifact_id_invalid": "Give the short id listed for this session (like f1), not a path.",
    "artifact_unknown": "No file with that id was produced in this session.",
    "artifact_not_a_file": "That is a mail draft in Outlook; it cannot be attached.",
    "artifact_missing": "That file is no longer in the workspace.",
}

ATTACH_MODEL_TOOL = ModelTool(
    name=ATTACH_TOOL,
    description=(
        "Attach a file this session already produced (a Workflow run's chart, report or "
        "document, or a file a tool made here) to your reply, by the short id listed under "
        "'What this session already produced'. Images are shown as pictures, other files as "
        "documents. Only ids from that list work; paths are refused."
    ),
    input_contract=f"host.{ATTACH_TOOL}.v1",
    input_schema={
        "type": "object",
        "properties": {
            "artifact_id": {
                "type": "string",
                "description": "The short id from this session's list, for example f1.",
            }
        },
        "required": ["artifact_id"],
        "additionalProperties": False,
    },
)


def run_entry(store: SessionArtifacts, session_id: str | None, actor: str, run: SessionRun) -> str:
    """The compact history entry for a run: name, id, status, one line, and
    what it made by short id, kind and file name (no paths, no contents)."""
    lines = [f"【執行結果】{run.workflow} · run {run.run_id} · {run.status}"]
    if run.summary:
        lines.append(f"摘要：{run.summary}")
    by_id = (
        {item.artifact_id: item for item in store.ledger(session_id, actor).artifacts}
        if session_id
        else {}
    )
    made = [by_id[item] for item in run.artifact_ids if item in by_id]
    if made:
        lines.append("產出：")
        lines.extend(f"- {item.artifact_id} {item.kind}: {item.filename}" for item in made)
        lines.append(f"（要再看或貼出這些產出：{ATTACH_TOOL} 加上編號。）")
    return "\n".join(lines)
