"""Task result summaries (任務結果摘要; owner 2026-10-25).

「每次跑完任務是不是應該要compose，把重要的結果結論記下來」, kept 「存硬碟，保留 30 天」.

When a task completes in a session (a Workflow run, or a model turn that used
several tools), the Host composes a short structured summary: what was done,
its status, up to five key results taken from the run's outputs, the
artifacts by the ids `session__attach_file` uses, follow-ups (「郵件草稿已存在
Outlook，尚未寄出」), when, and the session. It is

- shown at the end of the reply as a 「結果摘要」 block (3–5 lines);
- listed in each later turn's system prompt with the session's ledger
  (`SessionArtifacts.guidance`), so 「剛剛的圖」 or 「這週算了幾項」 can be
  answered after any number of messages and after a restart;
- kept on disk per actor for `retention_days` (default 30, Settings on the
  memory page) in `<workspace>/session-artifacts/task-summaries.sqlite`, and
  deleted by the nightly job without a model;
- saved as a note only when the person presses 「存成筆記」.

Key results are extracted deterministically from the step results. Only when
that finds fewer than two and the run has a text preview, one bounded model
call (`condenser`, set by the Host on the approved client and the session's
model) may condense the preview; without a model nothing is called.

docs/DECISIONS.md 2026-10-25 "Task result summaries, kept 30 days";
docs/CONTRACTS.md "Task result summaries".
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import Field, JsonValue

from common.base import Contract
from host_runtime.workspace import write_atomically

SUMMARIES_FILE = "task-summaries.sqlite"
SETTINGS_FILE = "task-summaries-settings.json"
DEFAULT_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 365
MAX_KEY_RESULTS = 5
MAX_FACT_CHARS = 80
#: How many of a session's summaries each turn's system prompt carries.
MAX_SHOWN_SUMMARIES = 5
#: How much of a run's preview a condensing model call is given.
MAX_CONDENSE_INPUT_CHARS = 3_000
CONDENSE_MAX_OUTPUT_TOKENS = 200
#: Step-data fields that are never a key result (files, ids, bodies, inputs).
_SKIP_KEYS = frozenset(
    {
        "preview",
        "summary",
        "message",
        "entry_id",
        "folder",
        "subject",
        "to",
        "cc",
        "trace",
        "excluded",
        "skipped",
        "activity_required",
    }
)
STATUS_WORDS = {
    "succeeded": "成功",
    "answered": "已回覆",
    "failed": "失敗",
    "needs_input": "還需要輸入",
    "unavailable": "無法執行",
}

_LOG = logging.getLogger(__name__)

#: (preview text) -> up to five short facts; set by the Host, None calls nothing.
Condenser = Callable[[str], list[str]]


class TaskSummarySettings(Contract):
    retention_days: int = Field(
        default=DEFAULT_RETENTION_DAYS, ge=1, le=MAX_RETENTION_DAYS, strict=True
    )


class SummaryArtifact(Contract):
    id: str
    kind: str
    name: str


class TaskSummary(Contract):
    summary_id: str
    session_id: str
    actor: str
    at: datetime
    task: str
    status: str
    key_results: tuple[str, ...] = ()
    artifacts: tuple[SummaryArtifact, ...] = ()
    follow_ups: tuple[str, ...] = ()
    run_id: str | None = None

    def block(self) -> str:
        """The 「結果摘要」 shown under the reply: 3–5 lines."""
        lines = ["結果摘要", f"- 任務：{self.task}（{STATUS_WORDS.get(self.status, self.status)}）"]
        if self.key_results:
            lines.append("- 重點：" + "；".join(self.key_results))
        if self.artifacts:
            lines.append(
                "- 產出："
                + "；".join(
                    f"{item.id} {item.name}（{_kind_word(item.kind)}）" for item in self.artifacts
                )
            )
        if self.follow_ups:
            lines.append("- 後續：" + "；".join(self.follow_ups))
        return "\n".join(lines)

    def line(self) -> str:
        """One compact line for a turn's system prompt."""
        parts = [f"{self.at.astimezone(UTC):%Y-%m-%d %H:%M}Z {self.task} ({self.status})"]
        if self.key_results:
            parts.append("results: " + "; ".join(self.key_results))
        if self.artifacts:
            parts.append("artifacts: " + ", ".join(f"{a.id} {a.name}" for a in self.artifacts))
        if self.follow_ups:
            parts.append("follow-ups: " + "; ".join(self.follow_ups))
        return " — ".join(parts)

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = json.loads(self.model_dump_json())
        data["block"] = self.block()
        return data


def _kind_word(kind: str) -> str:
    return {
        "image": "圖",
        "spreadsheet": "試算表",
        "document": "文件",
        "mail draft": "郵件草稿",
    }.get(kind, "檔案")


def _short(value: str) -> str:
    text = " ".join(value.split())
    return text if len(text) <= MAX_FACT_CHARS else text[: MAX_FACT_CHARS - 1] + "…"


def facts(datas: Iterable[JsonValue]) -> list[str]:
    """Short facts from step or tool data, newest step first: numbers, and
    short words that are not files, ids or bodies. At most five."""
    found: list[str] = []
    for data in datas:
        if not isinstance(data, dict):
            continue
        for key, value in data.items():
            if len(found) >= MAX_KEY_RESULTS:
                return found
            if key in _SKIP_KEYS or key.endswith(("_path", "_id", "_paths")):
                continue
            if isinstance(value, bool) or value is None:
                continue
            if isinstance(value, int | float):
                fact = f"{key} {value}"
            elif isinstance(value, str) and 0 < len(value) <= 40 and "\n" not in value:
                if "/" in value or "\\" in value:
                    continue
                fact = f"{key} {value}"
            else:
                continue
            if fact not in found:
                found.append(_short(fact))
    return found


def task_label(name: str, arguments: Mapping[str, Any] | None, labels: Mapping[str, str]) -> str:
    """「sde-weekly-report（Report week 2026_43W，執行方式 正式執行）」: the
    Workflow and up to three of the values it ran with, shown by label."""
    shown: list[str] = []
    for key, value in (arguments or {}).items():
        if len(shown) >= 3:
            break
        word = labels.get(f"{key}={value}") or (
            value if isinstance(value, str | int | float) and not isinstance(value, bool) else None
        )
        if word is None or (isinstance(word, str) and ("/" in word or "\\" in word)):
            continue
        shown.append(f"{labels.get(key, key)} {_short(str(word))}")
    return f"{name}（{'，'.join(shown)}）" if shown else name


def run_follow_ups(status: str, failure: str | None, datas: Sequence[JsonValue]) -> list[str]:
    ups: list[str] = []
    for data in datas:
        if not isinstance(data, dict):
            continue
        if isinstance(data.get("entry_id"), str) and data["entry_id"] and not data.get("skipped"):
            ups.append("郵件草稿已存在 Outlook，尚未寄出")
        elif data.get("skipped") is True:
            ups.append("這次沒有寫入或起草郵件")
    if failure:
        ups.append(f"沒有完成（{failure}）；可以說「再跑一次」")
    return list(dict.fromkeys(ups))[:3]


class TaskSummaries:
    """Every actor's summaries in one small SQLite file under the
    workspace's `session-artifacts/`; each read filters by actor."""

    def __init__(self, root: Path, *, clock: Callable[[], datetime] | None = None) -> None:
        self.root = root
        self.path = root / SUMMARIES_FILE
        self.clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()

    # -- storage ---------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        self.root.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=10)
        con.execute(
            "CREATE TABLE IF NOT EXISTS task_summaries ("
            "summary_id TEXT PRIMARY KEY, actor TEXT NOT NULL, session_id TEXT NOT NULL, "
            "at TEXT NOT NULL, body TEXT NOT NULL)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS task_summaries_by_session "
            "ON task_summaries (actor, session_id, at)"
        )
        return con

    def settings(self) -> TaskSummarySettings:
        try:
            return TaskSummarySettings.model_validate_json(
                (self.root / SETTINGS_FILE).read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return TaskSummarySettings()

    def save_settings(self, retention_days: object) -> TaskSummarySettings:
        checked = TaskSummarySettings.model_validate({"retention_days": retention_days})
        write_atomically(
            self.root / SETTINGS_FILE, checked.model_dump_json(indent=2).encode("utf-8")
        )
        return checked

    def _since(self) -> str:
        return (self.clock() - timedelta(days=self.settings().retention_days)).isoformat()

    def add(self, summary: TaskSummary) -> TaskSummary:
        with self._lock, closing(self._connect()) as con, con:
            con.execute(
                "INSERT OR REPLACE INTO task_summaries VALUES (?, ?, ?, ?, ?)",
                (
                    summary.summary_id,
                    summary.actor,
                    summary.session_id,
                    summary.at.astimezone(UTC).isoformat(),
                    summary.model_dump_json(),
                ),
            )
        return summary

    def _rows(self, sql: str, args: Sequence[object]) -> list[TaskSummary]:
        if not self.path.is_file():
            return []
        with self._lock, closing(self._connect()) as con:
            rows = con.execute(sql, args).fetchall()
        found = []
        for (body,) in rows:
            try:
                found.append(TaskSummary.model_validate_json(body))
            except ValueError:
                continue
        return found

    def for_session(
        self, session_id: str, actor: str, limit: int = MAX_SHOWN_SUMMARIES
    ) -> list[TaskSummary]:
        """The session's newest summaries within retention, oldest first."""
        found = self._rows(
            "SELECT body FROM task_summaries WHERE actor = ? AND session_id = ? AND at >= ? "
            "ORDER BY at DESC LIMIT ?",
            (actor, session_id, self._since(), limit),
        )
        return list(reversed(found))

    def recent(self, actor: str, limit: int = 50) -> list[TaskSummary]:
        return self._rows(
            "SELECT body FROM task_summaries WHERE actor = ? AND at >= ? ORDER BY at DESC LIMIT ?",
            (actor, self._since(), limit),
        )

    def get(self, actor: str, summary_id: str) -> TaskSummary | None:
        found = self._rows(
            "SELECT body FROM task_summaries WHERE actor = ? AND summary_id = ? AND at >= ?",
            (actor, summary_id, self._since()),
        )
        return found[0] if found else None

    def delete(self, actor: str, summary_id: str) -> bool:
        if not self.path.is_file():
            return False
        with self._lock, closing(self._connect()) as con, con:
            cursor = con.execute(
                "DELETE FROM task_summaries WHERE actor = ? AND summary_id = ?",
                (actor, summary_id),
            )
        return cursor.rowcount > 0

    def purge(self, now: datetime | None = None) -> int:
        """Delete every summary older than the retention, and the session
        ledgers last written before it. No model is involved."""
        moment = now or self.clock()
        cutoff = moment - timedelta(days=self.settings().retention_days)
        removed = 0
        if self.path.is_file():
            with self._lock, closing(self._connect()) as con, con:
                removed = con.execute(
                    "DELETE FROM task_summaries WHERE at < ?", (cutoff.isoformat(),)
                ).rowcount
        for ledger in self.root.glob("*.json"):
            if ledger.name == SETTINGS_FILE:
                continue
            try:
                if datetime.fromtimestamp(ledger.stat().st_mtime, UTC) < cutoff:
                    ledger.unlink()
            except OSError:
                continue
        _LOG.info("task summaries: purged %d", removed)
        return removed

    # -- composing -------------------------------------------------------------

    def new(
        self,
        session_id: str,
        actor: str,
        *,
        task: str,
        status: str,
        key_results: Sequence[str],
        artifacts: Sequence[SummaryArtifact],
        follow_ups: Sequence[str],
        run_id: str | None = None,
    ) -> TaskSummary:
        return self.add(
            TaskSummary(
                summary_id=f"ts-{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                actor=actor,
                at=self.clock(),
                task=_short(task) if len(task) > 120 else task,
                status=status,
                key_results=tuple(_short(item) for item in key_results[:MAX_KEY_RESULTS]),
                artifacts=tuple(artifacts),
                follow_ups=tuple(follow_ups[:3]),
                run_id=run_id,
            )
        )


def condensed(condenser: Condenser | None, preview: str) -> list[str]:
    """The bounded model call's facts, or nothing (no model, a fault)."""
    if condenser is None or not preview.strip():
        return []
    try:
        found = condenser(preview[:MAX_CONDENSE_INPUT_CHARS])
    except Exception:  # noqa: BLE001 - the deterministic fields stand alone
        return []
    return [_short(item) for item in found if isinstance(item, str) and item.strip()][
        :MAX_KEY_RESULTS
    ]


CONDENSE_PROMPT = (
    "Extract at most five key results (numbers, totals, counts, decisions) from this task "
    "output. Answer with a JSON array of short strings in the output's language, nothing else."
)


def parse_condensed(text: str) -> list[str]:
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        found = json.loads(text[start : end + 1])
    except ValueError:
        return []
    return [str(item) for item in found if isinstance(item, str | int | float)][:MAX_KEY_RESULTS]
