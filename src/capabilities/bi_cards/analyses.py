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

An analysis may declare `params` and `requires`
(`docs/phases/BI_ANALYSIS_DASHBOARD.md` §4.1): SQL receives the parameters as
named parameters (`:domain`), a script reads `PARAMS["domain"]`; `requires`
names the types and fields the schema must have for the analysis to be offered.
"""

from __future__ import annotations

import hashlib
import json
import numbers
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from capabilities.bi_cards import homes
from capabilities.bi_cards.store import BiStoreError

PREFIX = "analysis:"
_PRELUDE_DOMAIN = 'D = str(PARAMS.get("domain") or "robotics")'
_READS_DOMAIN = re.compile(":domain\\b|PARAMS(?:\\.get\\(|\\[)\\s*[\"']domain[\"']|\\bD\\b")
DASHBOARD_UNIT = "meta:dashboard"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
KINDS = ("sql", "python")
CHARTS = ("table", "bar", "line", "scatter")
PARAM_TYPES = ("enum", "bool", "date", "text")
PARAM_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
FIELD_REF_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\.[a-z][a-z0-9_]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_PARAMS = 10
MAX_TEXT_PARAM = 200
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

# The script's guard (an audit hook), shared with a home's tools (`tool_runs`), and the
# helpers it is given. It runs as `python -I runner.py`; the script is `script.py` beside it.
GUARD = r"""
import json, os, sys
# -I ignores PYTHONIOENCODING: without this, Windows writes the result in its
# ANSI code page and every non-ASCII text comes back garbled.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
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
"""

RUNNER = (
    GUARD
    + r'''
import sqlite3

def query(sql, params=()):
    """Rows of a read-only query on the knowledge base copy, as dicts."""
    db = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
    try:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute(sql, params)]
    finally:
        db.close()

PARAMS = json.load(open(os.path.join(SCRATCH, "params.json"), encoding="utf-8"))
sys.addaudithook(_guard)
code = open(os.path.join(SCRATCH, "script.py"), encoding="utf-8").read()
_ready = True
space = {"__name__": "__analysis__", "query": query, "DB": DB, "PARAMS": PARAMS}
exec(compile(code, "script.py", "exec"), space)
result = space.get("result")
print("\n" + "@@AEP_RESULT@@" + json.dumps(result, ensure_ascii=False, default=str))
'''
)


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


def run_sql(
    db_path: Path,
    sql: str,
    *,
    seconds: float = SQL_SECONDS,
    params: Mapping[str, Any] | None = None,
    max_rows: int = MAX_ROWS,
) -> dict[str, Any]:
    """One read-only statement on a copy; at most `max_rows` rows (marked
    `truncated` when cut). `params` are bound as named parameters (`:name`)."""
    text = str(sql or "").strip().rstrip(";").strip()
    if not text:
        raise BiStoreError("analysis_invalid", "請寫 SQL")
    if len(text) > MAX_CODE:
        raise BiStoreError("analysis_invalid", f"SQL 最多 {MAX_CODE} 字")
    with tempfile.TemporaryDirectory(prefix="aep-bi-sql-", ignore_cleanup_errors=True) as scratch:
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
                cursor = db.execute(text, dict(params or {}))
                rows = cursor.fetchmany(max_rows + 1)
            except sqlite3.Error as error:
                message = str(error)
                if "interrupted" in message:
                    message = f"超過 {seconds:.0f} 秒"
                raise BiStoreError("analysis_failed", f"SQL 沒有成功：{message}") from None
            columns = [d[0] for d in cursor.description or ()]
        finally:
            db.close()
    return _table(columns, [list(r) for r in rows[:max_rows]], len(rows) > max_rows)


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


def run_python(
    db_path: Path,
    code: str,
    *,
    seconds: float = PYTHON_SECONDS,
    params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """A script in its own guarded process; returns its table and printed
    output. The script reads `params` as `PARAMS`."""
    text = str(code or "")
    if not text.strip():
        raise BiStoreError("analysis_invalid", "請寫腳本")
    if len(text) > MAX_CODE:
        raise BiStoreError("analysis_invalid", f"腳本最多 {MAX_CODE} 字")
    with tempfile.TemporaryDirectory(prefix="aep-bi-py-", ignore_cleanup_errors=True) as scratch:
        folder = Path(scratch)
        _copy(db_path, folder)
        (folder / "script.py").write_text(text, encoding="utf-8")
        (folder / "params.json").write_text(
            json.dumps(dict(params or {}), ensure_ascii=False), encoding="utf-8"
        )
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


def run(
    db_path: Path, kind: str, code: str, params: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    if kind == "sql":
        return run_sql(db_path, code, params=params)
    if kind == "python":
        return run_python(db_path, code, params=params)
    raise BiStoreError("analysis_invalid", "kind 必須是 sql 或 python")


# -- parameters and requirements (design §4.1) -------------------------------------------


def _param_problem(name: Any, spec: Any) -> str | None:
    if not isinstance(name, str) or PARAM_NAME_RE.match(name) is None:
        return "parameter names use lowercase letters, digits and _"
    if not isinstance(spec, dict) or spec.get("type") not in PARAM_TYPES:
        return f"parameter {name}: type must be one of {', '.join(PARAM_TYPES)}"
    kind, default = spec["type"], spec.get("default")
    source = spec.get("values_from")
    if source is not None and (not isinstance(source, str) or not FIELD_REF_RE.match(source)):
        return f"parameter {name}: values_from must be <Type>.<field>"
    values = spec.get("values")
    if values is not None and (
        not isinstance(values, list) or not all(isinstance(v, str) for v in values)
    ):
        return f"parameter {name}: values must be a list of text"
    if kind == "enum":
        if not values and source is None:
            return f"parameter {name}: an enum needs values or values_from"
        if default is not None and not isinstance(default, str):
            return f"parameter {name}: the default must be text"
        if default is not None and values and default not in values:
            return f"parameter {name}: the default must be one of its values"
    elif kind == "bool":
        if default is not None and not isinstance(default, bool):
            return f"parameter {name}: the default must be true or false"
    elif kind == "date":
        if (
            default is not None
            and default != "today"
            and not (isinstance(default, str) and DATE_RE.match(default))
        ):
            return f"parameter {name}: the default must be YYYY-MM-DD or today"
    elif default is not None and (not isinstance(default, str) or len(default) > MAX_TEXT_PARAM):
        return f"parameter {name}: the default must be text of at most {MAX_TEXT_PARAM}"
    unknown = set(spec) - {"type", "default", "values_from", "values", "label"}
    if unknown:
        return f"parameter {name}: unknown keys {', '.join(sorted(unknown))}"
    return None


def params_problem(params: Any) -> str | None:
    if params is None:
        return None
    if not isinstance(params, dict) or len(params) > MAX_PARAMS:
        return f"params must be an object of at most {MAX_PARAMS} parameters"
    for name, spec in params.items():
        problem = _param_problem(name, spec)
        if problem:
            return problem
    return None


def requires_problem(requires: Any) -> str | None:
    if requires is None:
        return None
    if not isinstance(requires, dict) or set(requires) - {"types", "fields"}:
        return "requires must be {types: [...], fields: [<Type>.<field>, ...]}"
    types, fields = requires.get("types") or [], requires.get("fields") or []
    if not isinstance(types, list) or not all(isinstance(t, str) and t for t in types):
        return "requires.types must be a list of type names"
    if not isinstance(fields, list) or not all(
        isinstance(f, str) and FIELD_REF_RE.match(f) for f in fields
    ):
        return "requires.fields must be a list of <Type>.<field>"
    return None


def enum_values(spec: Mapping[str, Any], registry: Any | None) -> list[str]:
    """An enum parameter's values: its own `values`, else the schema field
    `values_from` names (its allowed values; a `domain` field without them
    takes the schema's domains)."""
    if spec.get("values"):
        return [str(v) for v in spec["values"]]
    source = str(spec.get("values_from") or "")
    if registry is None or "." not in source:
        return []
    type_name, _, field_name = source.partition(".")
    try:
        found = registry.type(type_name).get(field_name)
    except KeyError:
        return []
    if found is not None and found.enum:
        return list(found.enum)
    if found is not None and field_name == "domain":
        return list(registry.domains)
    return []


def requires_missing(requires: Mapping[str, Any] | None, registry: Any | None) -> list[str]:
    """The types and fields the analysis requires that the schema does not have."""
    if not requires:
        return []
    named = [str(t) for t in requires.get("types") or []]
    refs = [str(r) for r in requires.get("fields") or []]
    if registry is None:
        return [*named, *refs]
    missing = [t for t in named if t not in registry.types]
    for ref in refs:
        type_name, _, field_name = ref.partition(".")
        entity = registry.types.get(type_name)
        if entity is None or entity.get(field_name) is None:
            missing.append(ref)
    return missing


def requires_met(requires: Mapping[str, Any] | None, registry: Any | None) -> bool:
    """Whether the schema has every type and field the analysis requires."""
    if not requires:
        return True
    return registry is not None and not requires_missing(requires, registry)


def described_params(params: Mapping[str, Any] | None, registry: Any | None) -> dict[str, Any]:
    """The declared parameters with each enum's values resolved (for a page or the feed)."""
    shown = {}
    for name, spec in sorted((params or {}).items()):
        item = dict(spec)
        if spec.get("type") == "enum":
            item["values"] = enum_values(spec, registry)
            if item.get("default") is None and item["values"]:
                item["default"] = item["values"][0]
        shown[name] = item
    return shown


def resolve_params(
    params: Mapping[str, Any] | None,
    given: Mapping[str, Any],
    registry: Any | None,
    *,
    today: str,
) -> dict[str, Any]:
    """Every declared parameter's value: the given one (checked; text from a
    query string is converted) or its default. Unknown names are refused."""
    declared = described_params(params, registry)
    unknown = sorted(set(given) - set(declared))
    if unknown:
        raise BiStoreError("param_invalid", f"沒有這個參數：{', '.join(unknown)}")
    values: dict[str, Any] = {}
    for name, spec in declared.items():
        kind, value = spec["type"], given.get(name, spec.get("default"))
        if kind == "enum":
            # The page sends a domain in lower case, and the host compares domains without
            # case: `aidc` is the schema's `AIDC`, or every panel taking it fails to draw.
            value = next(
                (v for v in spec["values"] if str(v).casefold() == str(value).casefold()), value
            )
            if value is None or str(value) not in spec["values"]:
                raise BiStoreError(
                    "param_invalid", f"參數 {name} 必須是 {'、'.join(spec['values'])} 之一"
                )
            values[name] = str(value)
        elif kind == "bool":
            if isinstance(value, str) and value.lower() in ("true", "1", "false", "0"):
                value = value.lower() in ("true", "1")
            if value is None:
                value = False
            if not isinstance(value, bool):
                raise BiStoreError("param_invalid", f"參數 {name} 必須是 true 或 false")
            values[name] = value
        elif kind == "date":
            value = today if value in (None, "", "today") else value
            if not isinstance(value, str) or not DATE_RE.match(value):
                raise BiStoreError("param_invalid", f"參數 {name} 必須是 YYYY-MM-DD 的日期")
            values[name] = value
        else:
            value = "" if value is None else value
            if not isinstance(value, str) or len(value) > MAX_TEXT_PARAM:
                raise BiStoreError(
                    "param_invalid", f"參數 {name} 必須是最多 {MAX_TEXT_PARAM} 字的文字"
                )
            values[name] = value
    return values


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


def is_number(value: Any) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool)


def default_chart(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> dict[str, Any]:
    """A bar for exactly one label and one number column, else a table."""
    if len(columns) != 2 or not rows:
        return {"type": "table"}
    kinds = []
    for index in range(2):
        values = [r[index] for r in rows if len(r) > index and r[index] is not None]
        kinds.append("number" if values and all(is_number(v) for v in values) else "label")
    if sorted(kinds) != ["label", "number"]:
        return {"type": "table"}
    label = columns[kinds.index("label")]
    number = columns[kinds.index("number")]
    return {"type": "bar", "x": label, "y": number}


def chart_for(chart: Any, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> dict[str, Any]:
    """The spec when it names the result's columns, else the default."""
    if chart:
        try:
            return checked_chart(chart, list(columns))
        except BiStoreError:
            pass
    return default_chart(columns, rows)


#: The fields of an analysis's content, in the order a person reads them.
CONTENT = ("title", "question", "kind", "code", "chart", "params", "requires")


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
    return params_problem(value.get("params")) or requires_problem(value.get("requires"))


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
    # `params` and `requires` are kept only when given, so an analysis without
    # them keeps the value (and digest) it had before they existed.
    problem = params_problem(given.get("params")) or requires_problem(given.get("requires"))
    if problem:
        raise BiStoreError("analysis_invalid", problem)
    if given.get("params"):
        value["params"] = dict(given["params"])
    if given.get("requires"):
        value["requires"] = {
            "types": list(given["requires"].get("types") or []),
            "fields": list(given["requires"].get("fields") or []),
        }
    return PREFIX + slug, value


def digest(value: Mapping[str, Any]) -> str:
    """The analysis's content id: what a cached result was computed from."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def content(value: Mapping[str, Any]) -> dict[str, Any]:
    """What an analysis is made of: an edit compares these and its base is their digest."""
    return {key: value[key] for key in CONTENT if value.get(key) not in (None, "", {})}


def changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The fields that differ, in `CONTENT`'s order."""
    old, new = content(before), content(after)
    return [
        {"field": key, "before": old.get(key), "after": new.get(key)}
        for key in CONTENT
        if old.get(key) != new.get(key)
    ]


def default_params(value: Mapping[str, Any], registry: Any | None, today: str) -> dict[str, Any]:
    return resolve_params(value.get("params"), {}, registry, today=today)


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


def dashboard_unit(home: str | None = None) -> str:
    """The vault's own Dashboard, which the feed and Atlas read, or a home's
    (`docs/phases/BI_PAGE_SIMPLE.md` §12)."""
    return f"{DASHBOARD_UNIT}:{home}" if home else DASHBOARD_UNIT


def uses_domain(item: Mapping[str, Any]) -> bool:
    """Whether an analysis narrows to a domain: it declares the parameter and its code reads
    it. Otherwise it shows the whole vault, whichever domain asks. A built-in analysis reads it
    as `D`, set in the helpers put before its code, so that line alone does not count."""
    if "domain" not in (item.get("params") or {}):
        return False
    return (
        _READS_DOMAIN.search(str(item.get("code") or "").replace(_PRELUDE_DOMAIN, "")) is not None
    )


def dashboard_layout(units: Mapping[str, Any], home: str | None = None) -> dict[str, list[str]]:
    """A Dashboard's unit = `{"order": [slug], "hidden": [slug]}` (JSON text)."""
    raw = units.get(dashboard_unit(home))
    try:
        value = json.loads(raw) if isinstance(raw, str) else {}
    except ValueError:
        value = {}
    if not isinstance(value, dict):
        value = {}
    return {
        key: [str(s) for s in value.get(key) or [] if isinstance(s, str)]
        for key in ("order", "hidden")
    }


def order(units: Mapping[str, Any], slugs: list[str], home: str | None = None) -> list[str]:
    """A Dashboard's order. The vault's: its order, then the rest by slug. A home's: only what
    it chose, so a new domain starts empty and nothing is borrowed. Hidden left out."""
    layout = dashboard_layout(units, home)
    hidden = set(layout["hidden"])
    listed = [s for s in dict.fromkeys(layout["order"]) if s in slugs and s not in hidden]
    if home:
        return listed
    return listed + sorted(s for s in slugs if s not in hidden and s not in listed)


def _checked_home(home: Any) -> str | None:
    if not home:
        return None
    if homes.home_problem(home):
        raise BiStoreError("home_invalid", "領域必須是應用資料夾或 library 的項目")
    return str(home)


def listing(workspace: Path, vault_id: str, home: Any = None) -> dict[str, Any]:
    """The working copy's analyses, each with its parameter `inputs` (enum
    values resolved), whether the schema `offered` it, what it is `missing` and whether it
    `filters_domain`; `order` is the Dashboard's (offered, not hidden) and `dashboard` the
    stored layout, the vault's or `home`'s."""
    home = _checked_home(home)
    from capabilities.bi_cards import vault

    units = vault.Vault(workspace, vault_id).repo.working_units()
    registry = _registry(workspace, vault_id)
    found = []
    for item in saved(units):
        found.append(
            {
                **item,
                "inputs": described_params(item.get("params"), registry),
                "offered": requires_met(item.get("requires"), registry),
                "missing": requires_missing(item.get("requires"), registry),
                "filters_domain": uses_domain(item),
            }
        )
    offered = [a["slug"] for a in found if a["offered"]]
    return {
        "analyses": found,
        "order": order(units, offered, home),
        "dashboard": dashboard_layout(units, home),
        "home": home,
    }


def add_to_home(workspace: Path, vault_id: str, slug: str, home: Any) -> dict[str, Any]:
    """Put an analysis on a home's Dashboard, last, shown."""
    from capabilities.bi_cards import vault

    home = _checked_home(home)
    layout = dashboard_layout(vault.Vault(workspace, vault_id).repo.working_units(), home)
    return set_dashboard(
        workspace,
        vault_id,
        {
            "order": [*[s for s in layout["order"] if s != slug], slug],
            "hidden": [s for s in layout["hidden"] if s != slug],
        },
        home,
    )


def set_dashboard(workspace: Path, vault_id: str, given: Any, home: Any = None) -> dict[str, Any]:
    """Stage a Dashboard's order and hidden analyses: `meta:dashboard`, or a home's."""
    from capabilities.bi_cards import vault

    home = _checked_home(home)
    if not isinstance(given, dict):
        raise BiStoreError("dashboard_invalid", "dashboard 必須是 {order, hidden}")
    layout = {}
    for key in ("order", "hidden"):
        slugs = given.get(key) or []
        if not isinstance(slugs, list) or not all(
            isinstance(s, str) and NAME_RE.match(s) for s in slugs
        ):
            raise BiStoreError("dashboard_invalid", f"{key} 必須是分析代號的清單")
        layout[key] = list(dict.fromkeys(slugs))
    target = vault._vault(workspace, vault_id)
    with target.lock, vault._repo_errors():
        target.repo.stage(dashboard_unit(home), json.dumps(layout, ensure_ascii=False))
    return listing(workspace, vault_id, home)


def _registry(workspace: Path, vault_id: str) -> Any | None:
    from capabilities.bi_cards import vault

    try:
        return vault.Vault(workspace, vault_id)._registry()
    except Exception:  # noqa: BLE001 - no schema: enums without values, nothing required met
        return None


def run_saved(
    workspace: Path, vault_id: str, slug: Any, given: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    found = next((a for a in listing(workspace, vault_id)["analyses"] if a["slug"] == slug), None)
    if found is None:
        raise BiStoreError("analysis_unknown", "沒有這個分析")
    values = resolve_params(
        found.get("params"),
        given or {},
        _registry(workspace, vault_id),
        today=date.today().isoformat(),
    )
    table = run(_db(workspace, vault_id), found["kind"], found["code"], values)
    return {"analysis": found, "params": values, "table": table}


def save(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Run it once with its default parameters (its chart must name columns
    of its result), then stage it."""
    from capabilities.bi_cards import vault

    key, value = checked(given)
    values = default_params(value, _registry(workspace, vault_id), date.today().isoformat())
    table = run(_db(workspace, vault_id), value["kind"], value["code"], values)
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
