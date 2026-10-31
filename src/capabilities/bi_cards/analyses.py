"""Analyses of a BI knowledge base: read-only SQL and constrained Python (BI T3).

`docs/phases/BI_TEST_AND_TOOLS.md` §5; owner decision 2026-10-31 (SQL and
Python scripts, made in an AI conversation). An analysis answers an expert's
question with a table, drawn as a chart by the page:

- `run_sql`: one statement on a copy of the database, opened read-only, with an
  authorizer that allows reading only, a row cap and a time limit;
- `run_python`: a script in its own Python process (`-I`, empty environment,
  cwd its scratch folder) with a time limit and an output cap; an audit hook
  refuses network, child processes, native libraries and writes outside the
  scratch folder. It is a guard against mistakes and stray model output, not a
  boundary against a determined attacker: the script comes from the host's
  approved model and the person sees every script with its output.

Both see the copy with a view `card_values(card_id, entity_type, card, field,
value)` beside the BI tables. A saved analysis is the vault unit
`analysis:<slug>` = `{"title", "question", "kind", "code", "chart"}`,
committed and pushed like cards and rerun on the current data.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capabilities.bi_cards.store import BiStoreError

PREFIX = "analysis:"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
KINDS = ("sql", "python")
CHARTS = ("table", "bar", "line", "scatter")
MAX_ROWS = 2000
MAX_CODE = 20000
MAX_OUTPUT = 400_000
SQL_SECONDS = 10.0
PYTHON_SECONDS = 30.0
VIEW = """
CREATE VIEW IF NOT EXISTS card_values AS
SELECT c.id AS card_id, c.entity_type AS entity_type, c.name AS card, f.field AS field,
       CASE WHEN json_valid(f.value) THEN json_extract(f.value, '$') ELSE f.value END AS value
FROM cards c JOIN fields f ON f.card_id = c.id
"""
READ_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}

# The script's guard (an audit hook) and the helpers it is given. It runs as
# `python -I runner.py`; the script is `script.py` beside it.
RUNNER = r'''
import json, os, sqlite3, sys
SCRATCH = os.path.realpath(os.getcwd())
DB = os.path.join(SCRATCH, "bi.sqlite")
DENIED_IMPORTS = {"socket", "_socket", "ssl", "_ssl", "subprocess", "_posixsubprocess",
    "_winapi", "ctypes", "_ctypes", "multiprocessing", "_multiprocessing", "urllib.request",
    "http.client", "ftplib", "smtplib", "asyncio", "webbrowser"}
DENIED_EVENTS = ("socket.", "subprocess.", "os.system", "os.exec", "os.spawn", "os.posix_spawn",
    "os.fork", "os.kill", "ctypes.", "winreg.", "_winapi.", "os.startfile", "sys.addaudithook",
    "os.symlink", "os.link", "os.chmod", "shutil.rmtree")
WRITES = ("os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.truncate", "os.utime")
_ready = False

def _inside(path):
    try:
        real = os.path.realpath(os.fsdecode(path))
    except Exception:
        return False
    return real == SCRATCH or real.startswith(SCRATCH + os.sep)

def _guard(event, args):
    if not _ready:
        return
    if event == "import" and args and (args[0] in DENIED_IMPORTS or
                                       args[0].split(".")[0] in DENIED_IMPORTS):
        raise PermissionError("module not allowed in an analysis: " + args[0])
    if event.startswith(DENIED_EVENTS):
        raise PermissionError("not allowed in an analysis: " + event)
    if event == "open" and args:
        path, mode = args[0], args[1] if len(args) > 1 else "r"
        writing = isinstance(mode, str) and any(c in mode for c in "wax+")
        if isinstance(mode, int):
            writing = bool(mode & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND))
        if writing and isinstance(path, (str, bytes, os.PathLike)) and not _inside(path):
            raise PermissionError("writing outside the scratch folder is not allowed")
    if event in WRITES and args and not all(_inside(a) for a in args[:2] if a is not None):
        raise PermissionError("changing files outside the scratch folder is not allowed")

def query(sql, params=()):
    """Rows of a read-only query on the knowledge base copy, as dicts."""
    db = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
    try:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute(sql, params)]
    finally:
        db.close()

sys.addaudithook(_guard)
code = open(os.path.join(SCRATCH, "script.py"), encoding="utf-8").read()
_ready = True
space = {"__name__": "__analysis__", "query": query, "DB": DB}
exec(compile(code, "script.py", "exec"), space)
result = space.get("result")
print("\n" + "@@AEP_RESULT@@" + json.dumps(result, ensure_ascii=False, default=str))
'''


def _copy(db_path: Path, scratch: Path) -> Path:
    if not db_path.is_file():
        raise BiStoreError("dataset_empty", "這個知識庫還沒有資料")
    target = scratch / "bi.sqlite"
    shutil.copyfile(db_path, target)
    db = sqlite3.connect(target)
    try:
        db.executescript(VIEW)
    finally:
        db.close()
    return target


def _table(columns: list[str], rows: list[Any], truncated: bool) -> dict[str, Any]:
    return {"columns": columns, "rows": rows, "truncated": truncated}


def run_sql(db_path: Path, sql: str, *, seconds: float = SQL_SECONDS) -> dict[str, Any]:
    """One read-only statement on a copy; at most `MAX_ROWS` rows."""
    text = str(sql or "").strip().rstrip(";").strip()
    if not text:
        raise BiStoreError("analysis_invalid", "請寫 SQL")
    if len(text) > MAX_CODE:
        raise BiStoreError("analysis_invalid", f"SQL 最多 {MAX_CODE} 字")
    with tempfile.TemporaryDirectory(prefix="aep-bi-sql-") as scratch:
        copy = _copy(db_path, Path(scratch))
        db = sqlite3.connect(f"file:{copy.as_posix()}?mode=ro", uri=True)
        try:
            deadline = time.monotonic() + seconds
            db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
            db.set_authorizer(
                lambda action, *_: (
                    sqlite3.SQLITE_OK if action in READ_ACTIONS else sqlite3.SQLITE_DENY
                )
            )
            try:
                cursor = db.execute(text)
                rows = cursor.fetchmany(MAX_ROWS + 1)
            except sqlite3.Error as error:
                message = str(error)
                if "interrupted" in message:
                    message = f"超過 {seconds:.0f} 秒"
                raise BiStoreError("analysis_failed", f"SQL 沒有成功：{message}") from None
            columns = [d[0] for d in cursor.description or ()]
        finally:
            db.close()
    return _table(columns, [list(r) for r in rows[:MAX_ROWS]], len(rows) > MAX_ROWS)


def _shape(result: Any) -> dict[str, Any]:
    """`result` as `{"columns", "rows"}`: a dict of columns and rows, or a list of dicts."""
    if isinstance(result, dict) and isinstance(result.get("columns"), list):
        rows = [list(r) if isinstance(r, list | tuple) else [r] for r in result.get("rows") or []]
        columns = [str(c) for c in result["columns"]]
    elif isinstance(result, list) and all(isinstance(r, dict) for r in result):
        columns = list(dict.fromkeys(k for r in result for k in r))
        rows = [[r.get(c) for c in columns] for r in result]
    else:
        raise BiStoreError(
            "analysis_invalid",
            '腳本要把結果放在 result：{"columns": [...], "rows": [[...]]} 或一串 dict',
        )
    return _table(columns, rows[:MAX_ROWS], len(rows) > MAX_ROWS)


def run_python(db_path: Path, code: str, *, seconds: float = PYTHON_SECONDS) -> dict[str, Any]:
    """A script in its own guarded process; returns its table and printed output."""
    text = str(code or "")
    if not text.strip():
        raise BiStoreError("analysis_invalid", "請寫腳本")
    if len(text) > MAX_CODE:
        raise BiStoreError("analysis_invalid", f"腳本最多 {MAX_CODE} 字")
    with tempfile.TemporaryDirectory(prefix="aep-bi-py-") as scratch:
        folder = Path(scratch)
        _copy(db_path, folder)
        (folder / "script.py").write_text(text, encoding="utf-8")
        (folder / "runner.py").write_text(RUNNER, encoding="utf-8")
        try:
            done = subprocess.run(  # noqa: S603 (our interpreter, our runner, fixed arguments)
                [sys.executable, "-I", "runner.py"],
                cwd=folder,
                env={"SYSTEMROOT": _system_root(), "PYTHONIOENCODING": "utf-8"},
                capture_output=True,
                timeout=seconds,
                stdin=subprocess.DEVNULL,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise BiStoreError("analysis_failed", f"腳本超過 {seconds:.0f} 秒，已停止") from None
    out = done.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")[:MAX_OUTPUT]
    err = done.stderr.decode("utf-8", errors="replace")[-4000:]
    printed, _, marked = out.rpartition("\n@@AEP_RESULT@@")
    if done.returncode != 0 or not marked:
        last = err.strip().splitlines()[-1] if err.strip() else f"結束碼 {done.returncode}"
        raise BiStoreError("analysis_failed", f"腳本沒有成功：{last}")
    table = _shape(json.loads(marked))
    return {**table, "printed": printed[-4000:]}


def _system_root() -> str:
    return os.environ.get("SYSTEMROOT", "")


def run(db_path: Path, kind: str, code: str) -> dict[str, Any]:
    if kind == "sql":
        return run_sql(db_path, code)
    if kind == "python":
        return run_python(db_path, code)
    raise BiStoreError("analysis_invalid", "kind 必須是 sql 或 python")


# -- saved analyses (vault units) --------------------------------------------------------


def checked_chart(chart: Any, columns: list[str] | None = None) -> dict[str, Any]:
    if not isinstance(chart, dict) or chart.get("type", "table") not in CHARTS:
        raise BiStoreError("analysis_invalid", f"圖表 type 必須是 {'、'.join(CHARTS)}")
    shown = {"type": chart.get("type", "table")}
    for key in ("x", "y", "series"):
        value = chart.get(key)
        if value in (None, ""):
            continue
        if not isinstance(value, str) or (columns is not None and value not in columns):
            raise BiStoreError("analysis_invalid", f"圖表的 {key} 必須是結果裡的欄位名稱")
        shown[key] = value
    if shown["type"] != "table" and not ("x" in shown and "y" in shown):
        raise BiStoreError("analysis_invalid", "長條、折線與散佈圖要指定 x 與 y 欄位")
    return shown


def unit_problem(key: str, value: Any) -> str | None:
    if not NAME_RE.match(key[len(PREFIX) :]):
        return "analysis key must be analysis:<slug>"
    if not isinstance(value, dict):
        return "analysis must be an object"
    if value.get("kind") not in KINDS:
        return "analysis kind must be sql or python"
    if not isinstance(value.get("code"), str) or not value["code"].strip():
        return "analysis needs code"
    if not isinstance(value.get("title"), str) or not value["title"].strip():
        return "analysis needs a title"
    try:
        checked_chart(value.get("chart") or {"type": "table"})
    except BiStoreError as error:
        return error.message
    return None


def checked(given: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    title = str(given.get("title") or "").strip()
    if not title or len(title) > 200:
        raise BiStoreError("analysis_invalid", "請寫標題（最多 200 字）")
    slug = str(given.get("slug") or "").strip()
    if not NAME_RE.match(slug):
        raise BiStoreError("analysis_invalid", "代號只能用小寫英數字與 -")
    kind = str(given.get("kind") or "")
    if kind not in KINDS:
        raise BiStoreError("analysis_invalid", "kind 必須是 sql 或 python")
    code = str(given.get("code") or "")
    if not code.strip() or len(code) > MAX_CODE:
        raise BiStoreError("analysis_invalid", f"請寫 SQL 或腳本（最多 {MAX_CODE} 字）")
    value = {
        "title": title,
        "question": str(given.get("question") or "").strip()[:1000],
        "kind": kind,
        "code": code,
        "chart": checked_chart(given.get("chart") or {"type": "table"}),
    }
    return PREFIX + slug, value


def saved(units: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {"unit": key, "slug": key[len(PREFIX) :], **value}
        for key, value in sorted(units.items())
        if key.startswith(PREFIX) and isinstance(value, dict)
    ]


def describe(db_path: Path) -> str:
    """The data an analysis can use, in words for the model."""
    types = run_sql(db_path, "SELECT entity_type, count(*) FROM cards GROUP BY 1 ORDER BY 2 DESC")[
        "rows"
    ]
    fields = run_sql(
        db_path,
        "SELECT entity_type, field, count(*) FROM card_values GROUP BY 1, 2 ORDER BY 1, 3 DESC",
    )["rows"]
    lines = [
        "Tables: cards(id, entity_type, canonical_key, name, version, synthetic, created, "
        "updated), fields(card_id, field, value JSON text, kind, ref, by, at), history, "
        "proposals, evidence, imports, meta. Convenience view card_values(card_id, entity_type, "
        "card, field, value) with each field's value decoded (lists stay JSON text; use "
        "json_each to expand them).",
        "Card types (cards) and their fields (how many cards have each):",
    ]
    for entity, count in types:
        named = [f"{f} ({n})" for t, f, n in fields if t == entity][:40]
        lines.append(f"- {entity}: {count} cards; fields: {', '.join(named)}")
    return "\n".join(lines)


# -- on a vault ------------------------------------------------------------------------


def _db(workspace: Path, vault_id: str) -> Path:
    from capabilities.bi_cards import vault

    return vault.Vault(workspace, vault_id).db_path


def listing(workspace: Path, vault_id: str) -> dict[str, Any]:
    from capabilities.bi_cards import vault

    return {"analyses": saved(vault.Vault(workspace, vault_id).repo.working_units())}


def run_saved(workspace: Path, vault_id: str, slug: Any) -> dict[str, Any]:
    found = next((a for a in listing(workspace, vault_id)["analyses"] if a["slug"] == slug), None)
    if found is None:
        raise BiStoreError("analysis_unknown", "沒有這個分析")
    return {"analysis": found, "table": run(_db(workspace, vault_id), found["kind"], found["code"])}


def save(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Run it once (its chart must name columns of its result), then stage it."""
    from capabilities.bi_cards import vault

    key, value = checked(given)
    table = run(_db(workspace, vault_id), value["kind"], value["code"])
    checked_chart(value["chart"], table["columns"])
    target = vault._vault(workspace, vault_id)
    with target.lock, vault._repo_errors():
        target.repo.stage(key, value)
    return {"unit": key, "table": table, **listing(workspace, vault_id)}


def delete(workspace: Path, vault_id: str, unit: Any) -> dict[str, Any]:
    from capabilities.bi_cards import vault

    units = vault.Vault(workspace, vault_id).repo.working_units()
    if not isinstance(unit, str) or not unit.startswith(PREFIX) or unit not in units:
        raise BiStoreError("analysis_unknown", "沒有這個分析")
    target = vault._vault(workspace, vault_id)
    with target.lock, vault._repo_errors():
        target.repo.stage(unit, None)
    return listing(workspace, vault_id)
