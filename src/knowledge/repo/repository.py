"""The common version layer of knowledge repositories (R1).

Design: `docs/phases/KNOWLEDGE_REPO.md` §4–§7. A repository is a folder (on a
local disk for one person, in a OneDrive or SharePoint library for several):

    repo.json                     written once: id, title, purpose, type
    REPO.md                       derived, for people
    schemas/ skills/ sources/     files, written once and never changed (the
                                  default areas; a type may have its own, `FileLayout`)
    commits/<author>/<seq>.json   pushed commits
    tags/<name>.json              tags, never moved
    publish/<author>/<seq>.json   publish records

The engine knows only **units**: a unit key and a JSON value. A commit's
operations each set one unit (`value` null removes it) and carry `base`, the
hash of the value the author changed. Each type (`wiki`, `bi`) maps its own
knowledge onto units and supplies the unit check and the push checks
(`RepoType`); the engine never reads a card or a page.

Every PC applies pushed commits in one total order, (clock, author, seq), into
its local `repo.sqlite`. An operation whose base is not the unit's value at
that point, and whose value differs from it, is not applied: it becomes an
open conflict, the same on every PC. A commit arriving late with an earlier
key, or an applied commit that changed or vanished, rebuilds the state from
all commits. A commit whose files are not all present yet waits; one whose
file content differs from its hash is reported and not applied.

Work happens in the PC's working copy (`work/`): uncommitted unit changes and
staged files, then local commits, which a push rebases onto the current head
unit by unit; a unit both sides changed differently is a conflict the person
resolves before anything is written.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

REPO_FORMAT = "aep.knowledge.repo/v1"
COMMIT_FORMAT = "aep.knowledge.commit/v1"
TAG_FORMAT = "aep.knowledge.tag/v1"
PUBLISH_FORMAT = "aep.knowledge.publish/v1"
REPO_FILE = "repo.json"
README_FILE = "REPO.md"
COMMITS_DIR = "commits"
SYNC_STAMP_FILE = "sync_stamp.json"
TAGS_DIR = "tags"
PUBLISH_DIR = "publish"
WITHDRAWN_DIR = "withdrawn"
#: The areas a commit may add files to, for a type with no layout of its own.
FILE_AREAS = ("schemas", "skills", "sources")
LOCAL_ROOT = "knowledge-repos"
REGISTRY_FILE = "registry.json"
WITHDRAWN_FORMAT = "aep.knowledge.withdrawn/v1"
DB_FILE = "repo.sqlite"
WORK_DIR = "work"

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_ID = 40
AUTHOR_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
MAX_AUTHOR = 40
TAG_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
MAX_TAG = 60
SEQ_NAME_RE = re.compile(r"^([1-9][0-9]{0,8})\.json$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
KINDS = ("change", "import", "revert", "schema")
MAX_PURPOSE = 500
MAX_UNIT_KEY = 300
MAX_PATH = 240
MAX_RECORD_BYTES = 64 * 1024 * 1024
#: Reserved units every type shares: the current schema version and the
#: current revision of each skill (design §8).
SCHEMA_UNIT = "schema"
SKILL_UNIT_PREFIX = "skill:"

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS units (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  commit_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS applied (
  file TEXT PRIMARY KEY,
  clock INTEGER NOT NULL,
  author TEXT NOT NULL,
  seq INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  commit_id TEXT NOT NULL,
  position INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS conflicts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file TEXT NOT NULL,
  commit_id TEXT NOT NULL,
  unit TEXT NOT NULL,
  value TEXT,
  current TEXT,
  status TEXT NOT NULL,
  resolved_by TEXT
);
CREATE TABLE IF NOT EXISTS file_hashes (
  path TEXT PRIMARY KEY,
  size INTEGER NOT NULL,
  mtime_ns INTEGER NOT NULL,
  sha256 TEXT NOT NULL
);
"""

# Tries before a replace that Windows keeps refusing is given up.
_REPLACE_ATTEMPTS = 6
# A folder holds many files to be scanned, so a rename waits longer: about 2 s in all.
_RENAME_ATTEMPTS = 10
# Past this a path gets Windows' long form: temporary names add a few characters to 260.
_LONG_PATH = 240
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def source_line(name: str, reads: Mapping[str, Any]) -> str:
    """The line under an answer naming the repository and the version read
    (`reads`: `{tag, commit}`, as a repository type's `reads` gives it)."""
    tag, commit = reads.get("tag"), reads.get("commit")
    if tag:
        return f"資料來源：知識庫 {name} 發佈版本 {tag}"
    if commit:
        return f"資料來源：知識庫 {name}（尚未發佈，已 push 的最新版本 {str(commit)[:8]}）"
    return f"資料來源：知識庫 {name}（還沒有已 push 的內容）"


class RepoError(Exception):
    """A refused repository operation: a stable `code` and a message for people."""

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


@dataclass(frozen=True)
class CheckReport:
    """A type's push checks: `blocking` findings stop the push; `notes` are
    shown with it (design §3)."""

    blocking: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class RepoType(Protocol):
    """What a knowledge type supplies to the common engine."""

    name: str

    def unit_problem(self, key: str, value: Any) -> str | None:
        """Why `value` cannot be unit `key`'s value; None when it can."""
        ...

    def check(self, before: Mapping[str, Any], after: Mapping[str, Any]) -> CheckReport:
        """The push checks on the head (`before`) and the pushed result."""
        ...


_TYPES: dict[str, RepoType] = {}


def register_type(kind: RepoType) -> None:
    _TYPES[kind.name] = kind


def registered() -> list[str]:
    return sorted(_TYPES)


def get_type(name: str) -> RepoType:
    try:
        return _TYPES[name]
    except KeyError:
        raise RepoError("repo_type_unknown", f"這台電腦不認得知識庫類型「{name}」") from None


# -- small helpers ---------------------------------------------------------------


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def value_hash(value: Any) -> str | None:
    """The `base` of an operation: the hash of the value it changed (None: absent)."""
    if value is None:
        return None
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def commit_id(record: Mapping[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k != "id"}
    return hashlib.sha256(canonical(body).encode()).hexdigest()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _lock(key: str) -> threading.RLock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def _pretty(document: Any) -> bytes:
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode()


def extended(path: Path) -> Path:
    """`path` in Windows' long form, which needs no `LongPathsEnabled`; what is built on
    it can pass 260 characters. Elsewhere the same path."""
    text = str(path)
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return path
    full = os.path.abspath(text)
    return Path("\\\\?\\UNC\\" + full[2:] if full.startswith("\\\\") else "\\\\?\\" + full)


def long_path(path: Path) -> Path:
    """`path`, in the long form only when it needs it: others stay as they were."""
    return extended(path) if len(str(path)) >= _LONG_PATH else path


def _write_atomic(path: Path, data: bytes) -> None:
    """Write `path` through a temporary file in the same folder and a rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex[:8]}.tmp"
    temporary.write_bytes(data)
    replace_retrying(temporary, path)


def replace_retrying(source: Path, target: Path) -> None:
    """`os.replace`, retried briefly: Windows refuses a replace while another
    process (a virus scanner, the search indexer, a drive client, a reader of
    a database) briefly holds the file. The source is removed on failure."""
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                source.unlink(missing_ok=True)
                raise
            time.sleep(0.05 * (attempt + 1))


def rename_retrying(source: Path, target: Path) -> None:
    """`Path.rename` of a folder, retried briefly: Windows refuses it while another
    process holds a file inside. The source stays on failure."""
    for attempt in range(_RENAME_ATTEMPTS):
        try:
            source.rename(target)
            return
        except PermissionError:
            if attempt == _RENAME_ATTEMPTS - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


def remove_retrying(folder: Path) -> bool:
    """`shutil.rmtree`, retried briefly for the same refusal; whether the folder went.
    One still held stays for the caller to try again later."""
    for attempt in range(_RENAME_ATTEMPTS):
        try:
            shutil.rmtree(extended(folder))
            return True
        except FileNotFoundError:
            return True
        except OSError:
            if attempt < _RENAME_ATTEMPTS - 1:
                time.sleep(0.05 * (attempt + 1))
    return False


def _copy_atomic(source: Path, path: Path) -> None:
    """Copy a file by stream through a temporary file and a rename: an original
    may be too large to hold in memory."""
    path, source = long_path(path), long_path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        shutil.copyfile(source, temporary)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    replace_retrying(temporary, path)


def _write_new(path: Path, data: bytes) -> None:
    """Write a file that must not exist yet (records are never replaced)."""
    if path.exists():
        raise RepoError("record_exists", f"{path.name} 已經存在，紀錄不能覆寫")
    _write_atomic(path, data)


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with long_path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_author(actor: str) -> str:
    """An author name from the person's name (`leo.chi via web` -> `leo.chi`)."""
    person = actor.removesuffix(" via web").strip().lower()
    slug = re.sub(r"[^a-z0-9._-]+", "-", person).strip("-._")
    slug = re.sub(r"[._-]{2,}", "-", slug)
    return slug[:MAX_AUTHOR].strip("-._") or "author"


def _checked_author(author: str) -> str:
    author = author.strip().lower()
    if len(author) > MAX_AUTHOR or AUTHOR_RE.match(author) is None:
        raise RepoError(
            "author_invalid", "作者名稱只能用小寫英數字與 . _ -（最多 40 個字），例如 leo.chi"
        )
    return author


def _checked_purpose(purpose: str) -> str:
    text = purpose.strip()
    if not text:
        raise RepoError("purpose_missing", "每個 commit 都要寫改動的目的")
    if len(text) > MAX_PURPOSE:
        raise RepoError("purpose_too_long", f"改動目的最多 {MAX_PURPOSE} 個字")
    return text


def path_problem(path: str, areas: tuple[str, ...] = FILE_AREAS) -> str | None:
    """Why `path` cannot be a repository file under `areas`; None when it can."""
    if not path or len(path) > MAX_PATH or "\\" in path or ":" in path:
        return "path invalid"
    parts = PurePosixPath(path).parts
    if len(parts) < 2 or parts[0] not in areas:
        return f"path must be under {', '.join(a + '/' for a in areas)}"
    if any(p in ("", ".", "..") or p.startswith(".") for p in parts):
        return "path invalid"
    return None


class FileLayout:
    """Where a type keeps its files. This is the default; a type with a `layout`
    attribute supplies its own, one without keeps these rules exactly."""

    #: The top folders a commit may add files to.
    areas: tuple[str, ...] = FILE_AREAS
    #: The ones a new repository starts with.
    new_areas: tuple[str, ...] = FILE_AREAS
    #: How to tell a person where sources go.
    source_hint = "sources/<folder>/"
    #: A skill revision's path, or None for the shared `skills/<name>/rev-…` form.
    skill_path_re: re.Pattern[str] | None = None

    def is_source_path(self, path: str) -> bool:
        """Whether a repository file is a source, so it can be withdrawn."""
        return path.startswith("sources/")

    def source_folder_problem(self, folder: str) -> str | None:
        """Why `folder` cannot be a folder of sources; None when it can."""
        parts = PurePosixPath(folder).parts
        if not parts or parts[0] != "sources":
            return "必須在 sources/ 底下"
        return None if folder == "sources" else path_problem(folder, self.areas)

    def skill_area(self, home: str) -> str:
        """The folder holding the skills of `home` (see `skills.Skill.home`)."""
        if home:
            raise RepoError("skill_invalid", f"這種知識庫的 skill 不分「{home}」")
        return "skills"


DEFAULT_LAYOUT = FileLayout()


def layout_of(kind: RepoType | None) -> FileLayout:
    """The file layout of a type: its own, else the default."""
    found = getattr(kind, "layout", None)
    return found if isinstance(found, FileLayout) else DEFAULT_LAYOUT


def unit_key_problem(key: Any) -> str | None:
    if not isinstance(key, str) or not key or len(key) > MAX_UNIT_KEY:
        return "unit key invalid"
    if any(ord(c) < 32 for c in key):
        return "unit key invalid"
    return None


# -- records ---------------------------------------------------------------------


def commit_problem(
    data: Any, *, repo: str, author: str, seq: int, kind: RepoType | None
) -> str | None:
    """Why a parsed commit file cannot be applied; None when it can."""
    if not isinstance(data, dict):
        return "not a JSON object"
    if data.get("format") != COMMIT_FORMAT:
        return f"format is not {COMMIT_FORMAT}"
    if data.get("repo") != repo:
        return "repo id differs"
    if data.get("author") != author:
        return "author differs from its folder"
    if data.get("seq") != seq:
        return "seq differs from its file name"
    clock = data.get("clock")
    if not isinstance(clock, int) or isinstance(clock, bool) or clock < 1:
        return "clock missing"
    if data.get("id") != commit_id(data):
        return "id does not match the content"
    purpose = data.get("purpose")
    if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > MAX_PURPOSE:
        return "purpose missing"
    if data.get("kind") not in KINDS:
        return "kind invalid"
    if data["kind"] == "revert" and not isinstance(data.get("restores"), str):
        return "revert without restores"
    if not isinstance(data.get("created"), str):
        return "created missing"
    if data.get("base") is not None and not isinstance(data.get("base"), str):
        return "base invalid"
    files = data.get("files")
    if not isinstance(files, list):
        return "files missing"
    areas = layout_of(kind).areas
    for index, item in enumerate(files):
        if not isinstance(item, dict) or path_problem(str(item.get("path") or ""), areas):
            return f"file {index}: path invalid"
        if not isinstance(item.get("sha256"), str) or not SHA256_RE.match(item["sha256"]):
            return f"file {index}: sha256 invalid"
        if not isinstance(item.get("bytes"), int) or item["bytes"] < 0:
            return f"file {index}: bytes invalid"
    ops = data.get("ops")
    if not isinstance(ops, list):
        return "ops missing"
    for index, op in enumerate(ops):
        if not isinstance(op, dict) or set(op) not in (
            {"unit", "value", "base"},
            {"unit", "value", "base", "bi_evidence"},
        ):
            return f"op {index}: not a unit operation"
        if "bi_evidence" in op:
            if kind is None or kind.name != "bi" or not str(op["unit"]).startswith("evidence:"):
                return f"op {index}: BI evidence context on another unit type"
            context = op["bi_evidence"]
            if not isinstance(context, dict) or set(context) != {"before", "field", "after_field"}:
                return f"op {index}: invalid BI evidence context"
            if context["before"] is not None and not isinstance(context["before"], list):
                return f"op {index}: invalid BI evidence base"
            if value_hash(context["before"]) != op["base"]:
                return f"op {index}: BI evidence base hash mismatch"
            if any(
                v is not None and (not isinstance(v, str) or not SHA256_RE.match(v))
                for v in (context["field"], context["after_field"])
            ):
                return f"op {index}: invalid BI evidence field hash"
        problem = unit_key_problem(op["unit"])
        if problem:
            return f"op {index}: {problem}"
        if op["base"] is not None and (
            not isinstance(op["base"], str) or not SHA256_RE.match(op["base"])
        ):
            return f"op {index}: base invalid"
        if kind is not None and op["value"] is not None:
            problem = kind.unit_problem(op["unit"], op["value"])
            if problem:
                return f"op {index}: {problem}"
    return None


@dataclass(frozen=True)
class CommitFile:
    name: str  # `<author>/<seq>`
    author: str
    seq: int
    clock: int
    sha256: str
    data: dict[str, Any]

    @property
    def key(self) -> tuple[int, str, int]:
        return (self.clock, self.author, self.seq)

    @property
    def id(self) -> str:
        return str(self.data["id"])


@dataclass
class Scan:
    commits: list[CommitFile] = field(default_factory=list)
    bad: list[dict[str, str]] = field(default_factory=list)
    incomplete: list[dict[str, str]] = field(default_factory=list)
    names: dict[str, set[int]] = field(default_factory=dict)  # every seq file per author


#: The last read-only scan of each repository folder, with the stamp it was made at.
_SCANS: dict[str, tuple[str, Scan]] = {}
_SCANS_LOCK = threading.Lock()


def apply_ops(
    units: dict[str, Any], ops: Iterable[Mapping[str, Any]], *, kind: RepoType | None = None
) -> list[dict[str, Any]]:
    """Apply unit operations to `units` in place; return the ones not applied
    because the unit changed under them (each as a conflict)."""
    prepare = getattr(kind, "prepare_ops", None)
    if prepare is not None:
        ops = prepare(units, list(ops))
    conflicts = []
    for op in ops:
        key, value = str(op["unit"]), op["value"]
        current = units.get(key)
        if value_hash(current) != op["base"] and canonical(current) != canonical(value):
            conflicts.append({"unit": key, "value": value, "current": current})
            continue
        if value is None:
            units.pop(key, None)
        else:
            units[key] = value
    return conflicts


# -- the local registry ------------------------------------------------------------


def local_root(workspace: Path) -> Path:
    return workspace / LOCAL_ROOT


def _registry(workspace: Path) -> list[dict[str, Any]]:
    try:
        document = json.loads((local_root(workspace) / REGISTRY_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = document.get("repos") if isinstance(document, dict) else None
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def _register(workspace: Path, item: dict[str, Any]) -> None:
    items = [i for i in _registry(workspace) if i.get("id") != item["id"]]
    items.append(item)
    items.sort(key=lambda i: str(i["id"]))
    _write_atomic(local_root(workspace) / REGISTRY_FILE, _pretty({"repos": items}))


def repositories(workspace: Path) -> list[dict[str, Any]]:
    """The repositories registered on this PC."""
    return _registry(workspace)


def read_repo_json(folder: Path) -> dict[str, Any]:
    try:
        document = json.loads((folder / REPO_FILE).read_text(encoding="utf-8"))
    except OSError:
        raise RepoError("repo_invalid", f"資料夾裡沒有 {REPO_FILE}，不是一個知識庫") from None
    except ValueError:
        raise RepoError("repo_invalid", f"{REPO_FILE} 不是有效的 JSON") from None
    if not isinstance(document, dict) or document.get("format") != REPO_FORMAT:
        raise RepoError("repo_invalid", f"{REPO_FILE} 的 format 必須是 {REPO_FORMAT}")
    repo_id = document.get("id")
    if not isinstance(repo_id, str) or len(repo_id) > MAX_ID or not ID_RE.match(repo_id):
        raise RepoError("repo_invalid", f"{REPO_FILE} 的 id 無效")
    for key in ("title", "type"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            raise RepoError("repo_invalid", f"{REPO_FILE} 缺少 {key}")
    return document


def _readme(document: Mapping[str, Any]) -> str:
    return (
        f"# {document['title']}\n\n{document.get('purpose') or ''}\n\n"
        f"Type `{document['type']}`, id `{document['id']}`. Maintained through AEP: work is "
        "committed with its purpose, pushed into this folder, tagged and published. Nobody "
        "edits or deletes a file here; every file is added once by its author.\n"
    )


def create(
    workspace: Path,
    parent: Path,
    *,
    repo_id: str,
    title: str,
    purpose: str,
    kind: str,
    author: str,
) -> Repository:
    """Create a repository folder `<parent>/<repo_id>` and register it here."""
    new_areas = layout_of(get_type(kind)).new_areas
    if len(repo_id) > MAX_ID or not ID_RE.match(repo_id):
        raise RepoError("repo_id_invalid", "知識庫 id 只能用小寫英數字與 -（最多 40 個字）")
    if not title.strip():
        raise RepoError("title_missing", "需要知識庫名稱")
    author = _checked_author(author)
    if not parent.is_absolute() or not parent.is_dir():
        raise RepoError("path_missing", f"找不到資料夾 {parent}")
    folder = parent / repo_id
    if folder.exists() and any(folder.iterdir()):
        raise RepoError("repo_exists", f"{folder} 已經存在而且不是空的")
    if any(i.get("id") == repo_id for i in _registry(workspace)):
        raise RepoError("repo_registered", f"這台電腦已經有知識庫「{repo_id}」")
    document = {
        "format": REPO_FORMAT,
        "id": repo_id,
        "title": title.strip(),
        "purpose": purpose.strip(),
        "type": kind,
        "created": _now(),
        "created_by": author,
    }
    for name in (*new_areas, COMMITS_DIR, TAGS_DIR, PUBLISH_DIR):
        (folder / name).mkdir(parents=True, exist_ok=True)
    _write_atomic(folder / REPO_FILE, _pretty(document))
    _write_atomic(folder / README_FILE, _readme(document).encode())
    _register(workspace, {"id": repo_id, "path": str(folder), "author": author, "type": kind})
    return Repository(workspace, repo_id)


def join(workspace: Path, folder: Path, *, author: str) -> Repository:
    """Register an existing repository folder on this PC."""
    document = read_repo_json(folder)
    get_type(document["type"])
    author = _checked_author(author)
    existing = next((i for i in _registry(workspace) if i.get("id") == document["id"]), None)
    if existing is not None and Path(str(existing.get("path"))) != folder:
        raise RepoError("repo_registered", f"這台電腦已經有知識庫「{document['id']}」在別的資料夾")
    _register(
        workspace,
        {"id": document["id"], "path": str(folder), "author": author, "type": document["type"]},
    )
    return Repository(workspace, document["id"])


# -- the repository ----------------------------------------------------------------


class Repository:
    """One registered repository on this PC: its folder, local state and working copy."""

    def __init__(self, workspace: Path, repo_id: str) -> None:
        entry = next((i for i in _registry(workspace) if i.get("id") == repo_id), None)
        if entry is None:
            raise RepoError("repo_unknown", f"這台電腦沒有知識庫「{repo_id}」")
        self.workspace = workspace
        self.id = repo_id
        self.folder = Path(str(entry["path"]))
        self.author = str(entry["author"])
        self.local = local_root(workspace) / repo_id
        self.work = self.local / WORK_DIR
        self.lock = _lock(str(self.local.resolve()))
        self._document: dict[str, Any] | None = None

    # -- the folder -----------------------------------------------------------

    @property
    def document(self) -> dict[str, Any]:
        if self._document is None:
            if not (self.folder / REPO_FILE).is_file():
                raise RepoError(
                    "repo_unreachable",
                    f"讀不到知識庫資料夾 {self.folder}（OneDrive 是否已同步、路徑是否改了？）",
                )
            self._document = read_repo_json(self.folder)
            if self._document["id"] != self.id:
                raise RepoError("repo_invalid", f"{REPO_FILE} 的 id 不是 {self.id}")
        return self._document

    @property
    def kind(self) -> RepoType:
        return get_type(self.document["type"])

    def _scan_records(self, area: str) -> tuple[list[tuple[str, int, bytes, Any]], Scan]:
        """Every `<area>/<author>/<seq>.json`: (author, seq, raw, parsed) plus
        the bad and incomplete ones."""
        found: list[tuple[str, int, bytes, Any]] = []
        scan = Scan()
        root = self.folder / area
        if not root.is_dir():
            return found, scan
        for author_dir in sorted(root.iterdir()):
            if author_dir.name.startswith("."):
                continue
            if not author_dir.is_dir() or AUTHOR_RE.match(author_dir.name) is None:
                scan.bad.append(
                    {"file": f"{area}/{author_dir.name}", "reason": "not an author folder"}
                )
                continue
            author = author_dir.name
            for path in sorted(author_dir.iterdir()):
                if path.name.startswith(".") or path.name.endswith(".tmp"):
                    continue  # a file still being written
                name = f"{area}/{author}/{path.name}"
                matched = SEQ_NAME_RE.match(path.name)
                if matched is None:
                    scan.bad.append({"file": name, "reason": "file name is not <seq>.json"})
                    continue
                seq = int(matched.group(1))
                scan.names.setdefault(author, set()).add(seq)
                try:
                    if path.stat().st_size > MAX_RECORD_BYTES:
                        scan.bad.append({"file": name, "reason": "file too large"})
                        continue
                    raw = path.read_bytes()
                    data = json.loads(raw.decode("utf-8"))
                except (OSError, ValueError) as failure:
                    scan.incomplete.append({"file": name, "reason": type(failure).__name__})
                    continue
                found.append((author, seq, raw, data))
        return found, scan

    def _read_only_scan(self) -> Scan:
        """`scan` for what only reads it, kept while the commit files' names, sizes and times
        stay (`_commits_stamp`, what a sync trusts too): a status on a large repository read and
        checked every commit twice, seconds each. Never for what hands on a commit's values,
        which a caller may change, and never a scan with a bad or half-arrived file, whose
        next read may differ with the stamp unchanged."""
        stamp, key = self._commits_stamp(), str(self.folder)
        with _SCANS_LOCK:
            known = _SCANS.get(key)
        if stamp and known is not None and known[0] == stamp:
            return known[1]
        scan = self.scan()
        if stamp and not scan.bad and not scan.incomplete:
            with _SCANS_LOCK:
                _SCANS[key] = (stamp, scan)
        return scan

    def scan(self) -> Scan:
        """Every commit file of the folder, valid ones in order."""
        found, scan = self._scan_records(COMMITS_DIR)
        kind = self.kind
        for author, seq, raw, data in found:
            problem = commit_problem(data, repo=self.id, author=author, seq=seq, kind=kind)
            if problem is not None:
                scan.bad.append({"file": f"{COMMITS_DIR}/{author}/{seq}.json", "reason": problem})
                continue
            scan.commits.append(
                CommitFile(
                    name=f"{author}/{seq}",
                    author=author,
                    seq=seq,
                    clock=int(data["clock"]),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    data=data,
                )
            )
        scan.commits.sort(key=lambda c: c.key)
        return scan

    def _connect(self) -> sqlite3.Connection:
        self.local.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.local / DB_FILE, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.executescript(DB_SCHEMA)
        return connection

    def _stored_sha(self, db: sqlite3.Connection, rel: str) -> str | None:
        """The hash of a repository file, cached by size and modification time;
        None while it is missing or cannot be read (a cloud-only file OneDrive
        cannot bring down now, or one a drive client holds): its commit waits."""
        path = long_path(self.folder / rel)
        try:
            stat = path.stat()
        except OSError:
            return None
        row = db.execute("SELECT * FROM file_hashes WHERE path = ?", (rel,)).fetchone()
        if row and row["size"] == stat.st_size and row["mtime_ns"] == stat.st_mtime_ns:
            return str(row["sha256"])
        try:
            sha = _file_sha(path)
        except OSError:
            return None
        db.execute(
            "INSERT OR REPLACE INTO file_hashes VALUES (?, ?, ?, ?)",
            (rel, stat.st_size, stat.st_mtime_ns, sha),
        )
        return sha

    # -- withdrawal: a file pushed by mistake -------------------------------------

    def withdrawn(self) -> dict[str, dict[str, Any]]:
        """Every withdrawn file by path: `{sha256, by, at, reason}`."""
        found, _ = self._scan_records(WITHDRAWN_DIR)
        files: dict[str, dict[str, Any]] = {}
        for author, _seq, _raw, data in found:
            if not isinstance(data, dict) or not isinstance(data.get("files"), list):
                continue
            for item in data["files"]:
                path = item.get("path") if isinstance(item, dict) else None
                sha = item.get("sha256") if isinstance(item, dict) else None
                if isinstance(path, str) and isinstance(sha, str) and SHA256_RE.match(sha):
                    files[path] = {
                        "sha256": sha,
                        "by": author,
                        "at": data.get("at"),
                        "reason": data.get("reason") or "",
                    }
        return files

    def withdraw(self, files: Iterable[Mapping[str, Any]], reason: str) -> dict[str, Any]:
        """Withdraw files from the folder: the record first, so a commit naming
        one never waits for good, then the files. What cannot be deleted now is
        listed in `left`. Callers make sure a person confirmed it."""
        chosen = [{"path": str(f["path"]), "sha256": str(f["sha256"])} for f in files]
        if not chosen:
            raise RepoError("nothing_to_withdraw", "沒有要撤回的檔案")
        layout = layout_of(self.kind)
        for item in chosen:
            if not layout.is_source_path(item["path"]) or path_problem(item["path"], layout.areas):
                raise RepoError("path_invalid", f"{item['path']} 不能撤回")
        with self.lock:
            seq = self._next_seq(WITHDRAWN_DIR)
            record = {
                "format": WITHDRAWN_FORMAT,
                "repo": self.id,
                "author": self.author,
                "seq": seq,
                "files": chosen,
                "reason": reason.strip()[:MAX_PURPOSE],
                "at": _now(),
            }
            _write_new(self.folder / WITHDRAWN_DIR / self.author / f"{seq}.json", _pretty(record))
            left = []
            for item in chosen:
                try:
                    (self.folder / item["path"]).unlink(missing_ok=True)
                except OSError:
                    left.append(item["path"])
            self.forget_withdrawn()
            return {**record, "left": left}

    def forget_withdrawn(self) -> None:
        """Drop this PC's staged copies of withdrawn files."""
        with self.lock:
            gone = self.withdrawn()
            pending = self._pending()
            for path in gone:
                long_path(self.work / "files" / path).unlink(missing_ok=True)
            kept = {k: v for k, v in pending["files"].items() if k not in gone}
            if len(kept) != len(pending["files"]):
                self._save_pending({"sets": pending["sets"], "files": kept})

    def _refuse_withdrawn(self, path: str) -> None:
        if path in self.withdrawn():
            raise RepoError("source_withdrawn", f"{path} 已經撤回，不能再放回共用資料夾")

    def _files_state(
        self,
        db: sqlite3.Connection,
        commit: CommitFile,
        gone: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> tuple[list[str], list[str]]:
        """A commit's files that are missing, and those whose content differs.
        A withdrawn file is neither: its commit stays applied."""
        missing, changed = [], []
        if gone is None:
            gone = self.withdrawn() if commit.data["files"] else {}
        for item in commit.data["files"]:
            if gone.get(item["path"], {}).get("sha256") == item["sha256"]:
                continue
            sha = self._stored_sha(db, item["path"])
            if sha is None:
                missing.append(item["path"])
            elif sha != item["sha256"]:
                changed.append(item["path"])
        return missing, changed

    # -- sync -----------------------------------------------------------------

    def _commits_stamp(self) -> str:
        """A digest of the commit files' names, sizes and times; reads none of them."""
        seen: list[tuple[str, str, int, int]] = []
        root = self.folder / COMMITS_DIR
        try:
            authors = sorted(os.scandir(root), key=lambda e: e.name)
        except OSError:
            return ""
        for author in authors:
            if not author.is_dir():
                seen.append((author.name, "", 0, 0))
                continue
            with os.scandir(author.path) as files:
                for item in files:
                    info = item.stat()
                    seen.append((author.name, item.name, info.st_size, info.st_mtime_ns))
        return hashlib.sha256(canonical(sorted(seen)).encode("utf-8")).hexdigest()

    def _stamp_path(self) -> Path:
        return self.local / SYNC_STAMP_FILE

    def _remember_stamp(self, stamp: str, ready: Sequence[CommitFile], clean: bool) -> None:
        """What `_nothing_arrived` compares with; only a sync with nothing waiting,
        changed or unreadable may be skipped next time."""
        if not clean or not stamp:
            self._stamp_path().unlink(missing_ok=True)
            return
        files = {f["path"]: f["sha256"] for c in ready for f in c.data["files"]}
        record = {
            "stamp": stamp,
            "applied": len(ready),
            "files": files,
            "policy": getattr(self.kind, "replay_version", 0),
        }
        # Local and under the lock: a fixed scratch name draws no random id.
        scratch = self._stamp_path().with_suffix(".tmp")
        scratch.write_text(json.dumps(record), encoding="utf-8")
        replace_retrying(scratch, self._stamp_path())

    def _nothing_arrived(self, db: sqlite3.Connection, stamp: str) -> bool:
        """The commit files are what the last clean sync applied, and every file they
        name is still there and the same (`_stored_sha` hashes only a changed one)."""
        try:
            record = json.loads(self._stamp_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if int(db.execute("PRAGMA user_version").fetchone()[0]) != getattr(
            self.kind, "replay_version", 0
        ):
            return False
        if not stamp or record.get("stamp") != stamp:
            return False
        count = int(db.execute("SELECT COUNT(*) FROM applied").fetchone()[0])
        if count != record.get("applied"):
            return False
        gone = self.withdrawn() if record["files"] else {}
        return all(
            gone.get(path, {}).get("sha256") == sha or self._stored_sha(db, path) == sha
            for path, sha in record["files"].items()
        )

    def fingerprint(self) -> str:
        """A digest of what a build from this repository reads: the applied commits,
        this PC's local commits and uncommitted changes, open conflicts and withdrawals.
        The same digest means the same build, whoever made the change."""
        local = []
        root = self.work / COMMITS_DIR
        if root.is_dir():
            for item in sorted(root.iterdir()):
                info = item.stat()
                local.append((item.name, info.st_size, info.st_mtime_ns))
        try:
            pending = hashlib.sha256(self._pending_path().read_bytes()).hexdigest()
        except OSError:
            pending = ""
        with closing(self._connect()) as db:
            applied = [
                (r["file"], r["sha256"], r["commit_id"])
                for r in db.execute("SELECT * FROM applied ORDER BY position")
            ]
            conflicts = [
                (r["id"], r["status"], r["unit"], r["value"])
                for r in db.execute("SELECT * FROM conflicts ORDER BY id")
            ]
        withdrawn = sorted((k, v["sha256"]) for k, v in self.withdrawn().items())
        state = [applied, local, pending, conflicts, withdrawn]
        return hashlib.sha256(canonical(state).encode("utf-8")).hexdigest()

    def applied_ids(self) -> set[str]:
        return {cid for _, cid in self._ordered()}

    def sync(self) -> dict[str, Any]:
        """Apply every pushed commit not applied yet, in order; rebuild from all
        commits when one arrived late with an earlier key or an applied one
        changed or vanished. Nothing arrived is told from the commit files' names,
        sizes and times, with none of them read."""
        with self.lock:
            stamp = self._commits_stamp()
            with closing(self._connect()) as db:
                if self._nothing_arrived(db, stamp):
                    return {
                        "applied": 0,
                        "rebuilt": False,
                        "conflicts": 0,
                        "waiting": [],
                        "changed": [],
                        "bad": [],
                        "incomplete": [],
                    }
            scan = self.scan()
            with closing(self._connect()) as db:
                waiting, changed, ready = [], [], []
                gone = self.withdrawn()
                for commit in scan.commits:
                    missing, differs = self._files_state(db, commit, gone)
                    if differs:
                        changed.append({"commit": commit.name, "files": differs})
                    elif missing:
                        waiting.append({"commit": commit.name, "files": missing})
                    else:
                        ready.append(commit)
                applied = {
                    r["file"]: ((int(r["clock"]), str(r["author"]), int(r["seq"])), r["sha256"])
                    for r in db.execute("SELECT * FROM applied")
                }
                present = {c.name: c for c in ready}
                new = [c for c in ready if c.name not in applied]
                old_policy = int(db.execute("PRAGMA user_version").fetchone()[0])
                rebuild = old_policy != getattr(self.kind, "replay_version", 0) or any(
                    name not in present or present[name].sha256 != sha
                    for name, (_, sha) in applied.items()
                )
                if new and applied and not rebuild:
                    rebuild = min(c.key for c in new) < max(key for key, _ in applied.values())
                todo = ready if rebuild else new
                clean = not (waiting or changed or scan.bad or scan.incomplete)
                if not todo and not rebuild:
                    self._remember_stamp(stamp, ready, clean)
                    return {
                        "applied": 0,
                        "rebuilt": False,
                        "conflicts": 0,
                        "waiting": waiting,
                        "changed": changed,
                        "bad": scan.bad,
                        "incomplete": scan.incomplete,
                    }
                db.execute("BEGIN IMMEDIATE")
                try:
                    if rebuild:
                        for table in ("units", "applied", "conflicts"):
                            db.execute(f"DELETE FROM {table}")
                    units = self._units(db)
                    before = dict(units)
                    owner: dict[str, str] = {}
                    position = int(
                        db.execute("SELECT COALESCE(MAX(position), 0) FROM applied").fetchone()[0]
                    )
                    conflicts = 0
                    for commit in todo:
                        position += 1
                        found = apply_ops(units, commit.data["ops"], kind=self.kind)
                        missed = {c["unit"] for c in found}
                        for op in commit.data["ops"]:
                            if op["unit"] not in missed:
                                owner[op["unit"]] = commit.id
                                db.execute(
                                    "UPDATE conflicts SET status = 'superseded', resolved_by = ? "
                                    "WHERE unit = ? AND status = 'open'",
                                    (commit.id, op["unit"]),
                                )
                        for item in found:
                            conflicts += 1
                            db.execute(
                                "INSERT INTO conflicts (file, commit_id, unit, value, current, "
                                "status) VALUES (?, ?, ?, ?, ?, 'open')",
                                (
                                    commit.name,
                                    commit.id,
                                    item["unit"],
                                    canonical(item["value"]),
                                    canonical(item["current"]),
                                ),
                            )
                        db.execute(
                            "INSERT INTO applied VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                commit.name,
                                commit.clock,
                                commit.author,
                                commit.seq,
                                commit.sha256,
                                commit.id,
                                position,
                            ),
                        )
                    for key in set(before) | set(units):
                        if key not in units:
                            db.execute("DELETE FROM units WHERE key = ?", (key,))
                        elif key in owner or canonical(before.get(key)) != canonical(units[key]):
                            db.execute(
                                "INSERT OR REPLACE INTO units VALUES (?, ?, ?)",
                                (key, canonical(units[key]), owner.get(key, "")),
                            )
                    db.execute(f"PRAGMA user_version = {getattr(self.kind, 'replay_version', 0)}")
                    db.execute("COMMIT")
                except BaseException:
                    db.execute("ROLLBACK")
                    raise
                self._remember_stamp(stamp, ready, clean)
            return {
                "applied": len(todo),
                "rebuilt": rebuild,
                "conflicts": conflicts,
                "waiting": waiting,
                "changed": changed,
                "bad": scan.bad,
                "incomplete": scan.incomplete,
            }

    @staticmethod
    def _units(db: sqlite3.Connection) -> dict[str, Any]:
        return {
            r["key"]: json.loads(r["value"]) for r in db.execute("SELECT key, value FROM units")
        }

    def units(self) -> dict[str, Any]:
        """The maintenance head as of the last sync."""
        with self.lock, closing(self._connect()) as db:
            return self._units(db)

    def _ordered(self) -> list[tuple[str, str]]:
        """The applied commits in order: (file, commit id)."""
        with closing(self._connect()) as db:
            return [
                (r["file"], r["commit_id"])
                for r in db.execute("SELECT file, commit_id FROM applied ORDER BY position")
            ]

    def head(self) -> str | None:
        ordered = self._ordered()
        return ordered[-1][1] if ordered else None

    def state_at(self, target: str) -> dict[str, Any]:
        """The units right after the applied commit `target` (an id)."""
        with self.lock:
            ordered = self._ordered()
            if target not in {cid for _, cid in ordered}:
                raise RepoError("commit_unknown", "這個版本還沒有套用到這台電腦（先同步）")
            commits = {c.name: c for c in self.scan().commits}
            units: dict[str, Any] = {}
            for name, cid in ordered:
                apply_ops(units, commits[name].data["ops"], kind=self.kind)
                if cid == target:
                    break
            return units

    def log(self) -> list[dict[str, Any]]:
        """Every applied commit in order with what each of its operations did:
        `{"commit": <the commit>, "changes": [{"unit", "before", "after",
        "applied"}]}`. A type derives its own history from it."""
        with self.lock:
            commits = {c.name: c for c in self.scan().commits}
            units: dict[str, Any] = {}
            entries = []
            for name, _ in self._ordered():
                commit = commits.get(name)
                if commit is None:
                    continue
                changes = []
                prepare = getattr(self.kind, "prepare_ops", None)
                operations = prepare(units, commit.data["ops"]) if prepare else commit.data["ops"]
                for op in operations:
                    before = units.get(op["unit"])
                    applied = not apply_ops(units, [op])
                    changes.append(
                        {
                            "unit": op["unit"],
                            "before": before,
                            "after": units.get(op["unit"]),
                            "applied": applied,
                        }
                    )
                entries.append({"commit": commit.data, "changes": changes})
            return entries

    def conflicts(self, status: str = "open") -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            return [
                {
                    "id": r["id"],
                    "commit": r["file"],
                    "commit_id": r["commit_id"],
                    "unit": r["unit"],
                    "value": json.loads(r["value"]),
                    "current": json.loads(r["current"]),
                    "status": r["status"],
                }
                for r in db.execute(
                    "SELECT * FROM conflicts WHERE status = ? ORDER BY id", (status,)
                )
            ]

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Applied commits, newest first, with their purpose."""
        commits = {c.name: c for c in self._read_only_scan().commits}
        rows = []
        for name, _ in reversed(self._ordered()):
            commit = commits.get(name)
            if commit is None:
                continue
            data = commit.data
            rows.append(
                {
                    "id": data["id"],
                    "file": name,
                    "author": data["author"],
                    "created": data["created"],
                    "purpose": data["purpose"],
                    "kind": data["kind"],
                    "restores": data.get("restores"),
                    "units": len(data["ops"]),
                    "files": [f["path"] for f in data["files"]],
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def diff(self, target: str) -> list[dict[str, Any]]:
        """What the applied commit `target` changed: unit, before, after."""
        ordered = [cid for _, cid in self._ordered()]
        if target not in ordered:
            raise RepoError("commit_unknown", "這個版本還沒有套用到這台電腦（先同步）")
        index = ordered.index(target)
        before = self.state_at(ordered[index - 1]) if index else {}
        after = self.state_at(target)
        keys = sorted(set(before) | set(after))
        return [
            {"unit": k, "before": before.get(k), "after": after.get(k)}
            for k in keys
            if canonical(before.get(k)) != canonical(after.get(k))
        ]

    # -- the working copy -------------------------------------------------------

    def _pending_path(self) -> Path:
        return self.work / "pending.json"

    def _pending(self) -> dict[str, Any]:
        try:
            document = json.loads(self._pending_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            document = {}
        return {
            "sets": dict(document.get("sets") or {}),
            "files": dict(document.get("files") or {}),
        }

    def _save_pending(self, pending: dict[str, Any]) -> None:
        _write_atomic(self._pending_path(), _pretty(pending))

    def _local_commits(self) -> list[tuple[Path, dict[str, Any]]]:
        root = self.work / COMMITS_DIR
        if not root.is_dir():
            return []
        found = []
        for path in root.iterdir():
            matched = SEQ_NAME_RE.match(path.name)
            if matched:
                found.append((int(matched.group(1)), path))
        return [(p, json.loads(p.read_text(encoding="utf-8"))) for _, p in sorted(found)]

    def working_units(self, *, pending: bool = True) -> dict[str, Any]:
        """The head with this PC's local commits (and uncommitted changes) on top."""
        units = self.units()
        for _, record in self._local_commits():
            for op in record["ops"]:
                if op["value"] is None:
                    units.pop(op["unit"], None)
                else:
                    units[op["unit"]] = op["value"]
        if pending:
            for key, value in self._pending()["sets"].items():
                if value is None:
                    units.pop(key, None)
                else:
                    units[key] = value
        return units

    def stage(self, key: str, value: Any) -> None:
        """Change one unit in the working copy (None removes it)."""
        self.stage_many({key: value})

    def stage_many(self, changes: Mapping[str, Any]) -> None:
        """Change several units with one write of the working copy; nothing is
        staged when one of them is invalid (an import stages thousands)."""
        for key, value in changes.items():
            problem = unit_key_problem(key)
            if problem is None and value is not None:
                problem = self.kind.unit_problem(key, value)
            if problem:
                raise RepoError("unit_invalid", f"{key}: {problem}")
        if not changes:
            return
        with self.lock:
            pending = self._pending()
            pending["sets"].update(changes)
            self._save_pending(pending)

    def stage_file(self, path: str, source: Path) -> dict[str, Any]:
        """Add a file to the working copy at repository path `path`."""
        problem = path_problem(path, layout_of(self.kind).areas)
        if problem:
            raise RepoError("path_invalid", f"{path}: {problem}")
        with self.lock:
            self._refuse_withdrawn(path)
            sha = _file_sha(source)
            existing = long_path(self.folder / path)
            if existing.is_file() and self._sha_or_refuse(existing, path) != sha:
                raise RepoError(
                    "path_taken", f"{path} 已經有另一份內容；檔案寫入後不能修改，請換檔名"
                )
            target = long_path(self.work / "files" / path)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            item = {"sha256": sha, "bytes": target.stat().st_size}
            pending = self._pending()
            pending["files"][path] = item
            self._save_pending(pending)
            return {"path": path, **item}

    def discard(self) -> None:
        """Drop every uncommitted change (local commits stay)."""
        with self.lock:
            self._save_pending({"sets": {}, "files": {}})

    def drop_local_commit(self, number: int) -> None:
        """Drop a local commit that has not been pushed (and later ones keep theirs)."""
        with self.lock:
            path = self.work / COMMITS_DIR / f"{number}.json"
            if not path.is_file():
                raise RepoError("commit_unknown", "沒有這個尚未 push 的 commit")
            path.unlink()

    def commit(
        self,
        purpose: str,
        *,
        kind: str = "change",
        restores: str | None = None,
        only: Callable[[str], bool] | None = None,
    ) -> dict[str, Any]:
        """Turn the uncommitted changes into one local commit with its purpose;
        with `only`, just the units and files it picks, the rest stay uncommitted."""
        purpose = _checked_purpose(purpose)
        if kind not in KINDS:
            raise RepoError("kind_invalid", "kind 無效")
        with self.lock:
            pending = self._pending()
            before = self.working_units(pending=False)
            ops = [
                {"unit": key, "value": value, "base": value_hash(before.get(key))}
                for key, value in sorted(pending["sets"].items())
                if canonical(before.get(key)) != canonical(value) and (only is None or only(key))
            ]
            annotate = getattr(self.kind, "annotate_ops", None)
            if annotate is not None:
                ops = annotate(before, ops)
            files = [
                {"path": p, **item}
                for p, item in sorted(pending["files"].items())
                if only is None or only(p)
            ]
            if not ops and not files:
                raise RepoError("nothing_to_commit", "沒有尚未 commit 的改動")
            record = self._new_local(purpose, kind, ops, files, restores)
            self._save_pending(
                {"sets": {}, "files": {}}
                if only is None
                else {
                    "sets": {k: v for k, v in pending["sets"].items() if not only(k)},
                    "files": {k: v for k, v in pending["files"].items() if not only(k)},
                }
            )
            return record

    def _new_local(
        self,
        purpose: str,
        kind: str,
        ops: list[dict[str, Any]],
        files: list[dict[str, Any]],
        restores: str | None,
    ) -> dict[str, Any]:
        existing = [int(p.stem) for p, _ in self._local_commits()]
        number = max(existing, default=0) + 1
        record: dict[str, Any] = {
            "number": number,
            "purpose": purpose,
            "kind": kind,
            "created": _now(),
            "ops": ops,
            "files": files,
        }
        if restores is not None:
            record["restores"] = restores
        _write_atomic(self.work / COMMITS_DIR / f"{number}.json", _pretty(record))
        return record

    def local_commits(self) -> list[dict[str, Any]]:
        return [record for _, record in self._local_commits()]

    # -- push -----------------------------------------------------------------

    def _resolutions(self) -> dict[str, Any]:
        try:
            document = json.loads((self.work / "resolutions.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return document if isinstance(document, dict) else {}

    def resolve(self, unit: str, choice: str, value: Any = None) -> None:
        """Decide a push conflict on `unit`: `mine`, `theirs` or `value`."""
        if choice not in ("mine", "theirs", "value"):
            raise RepoError("choice_invalid", "請選 mine、theirs 或 value")
        if choice == "value" and value is not None:
            problem = self.kind.unit_problem(unit, value)
            if problem:
                raise RepoError("unit_invalid", f"{unit}: {problem}")
        with self.lock:
            resolutions = self._resolutions()
            resolutions[unit] = {"choice": choice, "value": value}
            _write_atomic(self.work / "resolutions.json", _pretty(resolutions))

    def push(self) -> dict[str, Any]:
        """Push this PC's local commits into the repository folder.

        Returns `status` `pushed` (with the commits), `conflicts` (to resolve,
        nothing written), `blocked` (a push check failed, nothing written) or
        `nothing`."""
        with self.lock:
            local = self._local_commits()
            if not local:
                return {"status": "nothing"}
            self.sync()
            head_units = self.units()
            state = dict(head_units)
            resolutions = self._resolutions()
            conflicts: list[dict[str, Any]] = []
            rebased: list[dict[str, Any]] = []
            for _, record in local:
                ops = []
                prepare = getattr(self.kind, "prepare_ops", None)
                prepared = prepare(state, record["ops"]) if prepare else record["ops"]
                for op in prepared:
                    key = op["unit"]
                    current = state.get(key)
                    agreed = canonical(current) == canonical(op["value"])
                    if value_hash(current) == op["base"] or agreed:
                        ops.append(op)
                        continue
                    decision = resolutions.get(key)
                    if decision is None:
                        conflicts.append(
                            {
                                "unit": key,
                                "mine": op["value"],
                                "theirs": current,
                                "purpose": record["purpose"],
                            }
                        )
                        continue
                    if decision["choice"] == "theirs":
                        continue
                    chosen = op["value"] if decision["choice"] == "mine" else decision["value"]
                    ops.append({"unit": key, "value": chosen, "base": value_hash(current)})
                annotate = getattr(self.kind, "annotate_ops", None)
                if annotate is not None:
                    ops = annotate(state, ops)
                apply_ops(state, ops, kind=self.kind)
                if ops or record["files"]:
                    rebased.append({**record, "ops": ops})
            if conflicts:
                return {"status": "conflicts", "conflicts": conflicts}
            report = self.kind.check(head_units, state)
            if report.blocking:
                return {"status": "blocked", "blocking": report.blocking, "notes": report.notes}
            for record in rebased:
                for item in record["files"]:
                    self._copy_in(item)
            written = self._write_commits(rebased)
            for path, _ in local:
                path.unlink()
            (self.work / "resolutions.json").unlink(missing_ok=True)
            result = self.sync()
            return {"status": "pushed", "commits": written, "notes": report.notes, "sync": result}

    def _copy_in(self, item: Mapping[str, Any]) -> None:
        """Copy a staged file into the folder (before any commit names it). Another
        PC's unpushed commit must not bring a withdrawn file straight back."""
        self._refuse_withdrawn(item["path"])
        target = long_path(self.folder / item["path"])
        if target.is_file():
            if self._sha_or_refuse(target, item["path"]) != item["sha256"]:
                raise RepoError("path_taken", f"{item['path']} 已經有另一份內容")
            return
        source = long_path(self.work / "files" / item["path"])
        if not source.is_file() or _file_sha(source) != item["sha256"]:
            raise RepoError("file_missing", f"工作區裡的 {item['path']} 不見了或被改過")
        _copy_atomic(source, target)

    @staticmethod
    def _sha_or_refuse(path: Path, rel: str) -> str:
        """The hash of a repository file about to be relied on; one that cannot
        be read now is said in words, never as a crash."""
        try:
            return _file_sha(path)
        except OSError:
            raise RepoError(
                "file_unreadable",
                f"現在讀不到 {rel}；確認 OneDrive 已同步，並設為一律保留在此裝置上",
            ) from None

    def _max_clock(self) -> int:
        clocks = [c.clock for c in self.scan().commits]
        found, _ = self._scan_records(PUBLISH_DIR)
        clocks += [
            d["clock"]
            for _, _, _, d in found
            if isinstance(d, dict) and isinstance(d.get("clock"), int)
        ]
        return max(clocks, default=0)

    def _next_seq(self, area: str) -> int:
        _, scan = self._scan_records(area)
        return max(scan.names.get(self.author, set()), default=0) + 1

    def _write_commits(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        clock = self._max_clock()
        seq = self._next_seq(COMMITS_DIR)
        base = self.head()
        written = []
        for record in records:
            clock += 1
            data: dict[str, Any] = {
                "format": COMMIT_FORMAT,
                "repo": self.id,
                "author": self.author,
                "seq": seq,
                "clock": clock,
                "base": base,
                "created": record["created"],
                "purpose": record["purpose"],
                "kind": record["kind"],
                "files": record["files"],
                "ops": record["ops"],
            }
            if record.get("restores") is not None:
                data["restores"] = record["restores"]
            data["id"] = commit_id(data)
            _write_new(self.folder / COMMITS_DIR / self.author / f"{seq}.json", _pretty(data))
            written.append({"id": data["id"], "seq": seq, "purpose": data["purpose"]})
            base = data["id"]
            seq += 1
        return written

    # -- revert ---------------------------------------------------------------

    def resolve_version(self, target: str) -> str:
        """A tag name or a commit id (or a unique prefix of 8+ characters) -> commit id."""
        tag = self.tag_record(target) if TAG_RE.match(target) and len(target) <= MAX_TAG else None
        if tag is not None:
            return str(tag["commit"])
        ordered = [cid for _, cid in self._ordered()]
        matches = [
            cid for cid in ordered if cid == target or (len(target) >= 8 and cid.startswith(target))
        ]
        if len(matches) != 1:
            raise RepoError("version_unknown", f"找不到版本「{target}」（tag 名稱或 commit id）")
        return matches[0]

    def revert(self, target: str, purpose: str) -> dict[str, Any]:
        """A local commit that turns the head into version `target`."""
        purpose = _checked_purpose(purpose)
        with self.lock:
            if self._local_commits() or any(self._pending().values()):
                raise RepoError("work_not_clean", "回復版本前，請先 push 或捨棄尚未 push 的改動")
            self.sync()
            cid = self.resolve_version(target)
            wanted = self.state_at(cid)
            current = self.units()
            ops = [
                {"unit": k, "value": wanted.get(k), "base": value_hash(current.get(k))}
                for k in sorted(set(wanted) | set(current))
                if canonical(wanted.get(k)) != canonical(current.get(k))
            ]
            if not ops:
                raise RepoError("nothing_to_revert", "目前的內容已經和這個版本相同")
            return self._new_local(purpose, "revert", ops, [], cid)

    # -- tags and publish -------------------------------------------------------

    def tags(self) -> list[dict[str, Any]]:
        root = self.folder / TAGS_DIR
        found = []
        if root.is_dir():
            for path in sorted(root.glob("*.json")):
                record = self._read_tag(path)
                if record is not None:
                    found.append(record)
        return found

    def _read_tag(self, path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if (
            not isinstance(data, dict)
            or data.get("format") != TAG_FORMAT
            or data.get("name") != path.stem
            or not isinstance(data.get("commit"), str)
        ):
            return None
        return data

    def tag_record(self, name: str) -> dict[str, Any] | None:
        return self._read_tag(self.folder / TAGS_DIR / f"{name}.json")

    def tag(self, name: str, purpose: str, *, version: str | None = None) -> dict[str, Any]:
        """Name a pushed version (the head by default). A tag never moves."""
        if len(name) > MAX_TAG or not TAG_RE.match(name):
            raise RepoError(
                "tag_invalid", "tag 名稱只能用小寫英數字與 . -（最多 60 個字），例如 2026q4-review"
            )
        purpose = _checked_purpose(purpose)
        with self.lock:
            self.sync()
            cid = self.resolve_version(version) if version else self.head()
            if cid is None:
                raise RepoError("nothing_to_tag", "知識庫還沒有任何 commit")
            if (
                self.tag_record(name) is not None
                or (self.folder / TAGS_DIR / f"{name}.json").exists()
            ):
                raise RepoError("tag_exists", f"tag「{name}」已經存在；tag 不能移動，請換一個名稱")
            record = {
                "format": TAG_FORMAT,
                "name": name,
                "commit": cid,
                "by": self.author,
                "at": _now(),
                "purpose": purpose,
            }
            _write_new(self.folder / TAGS_DIR / f"{name}.json", _pretty(record))
            return record

    def publish(
        self, tag: str, extra: Callable[[str, str], Mapping[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Make tag `tag` the published version. Callers make sure a person
        confirmed it (design §7: never the model). `extra(tag, commit)` lets the
        knowledge type add what it wrote for this version to the record."""
        with self.lock:
            self.sync()
            record = self.tag_record(tag)
            if record is None:
                raise RepoError("tag_unknown", f"沒有 tag「{tag}」")
            if record["commit"] not in {cid for _, cid in self._ordered()}:
                raise RepoError("commit_unknown", "這個 tag 的版本還沒有套用到這台電腦（先同步）")
            added = {} if extra is None else dict(extra(tag, record["commit"]))
            seq = self._next_seq(PUBLISH_DIR)
            data = {
                **added,
                "format": PUBLISH_FORMAT,
                "repo": self.id,
                "author": self.author,
                "seq": seq,
                "clock": self._max_clock() + 1,
                "tag": tag,
                "commit": record["commit"],
                "at": _now(),
            }
            _write_new(self.folder / PUBLISH_DIR / self.author / f"{seq}.json", _pretty(data))
            return data

    def published(self) -> dict[str, Any] | None:
        """The newest publish record whose tag exists, in (clock, author, seq) order."""
        found, _ = self._scan_records(PUBLISH_DIR)
        records = []
        for author, seq, _, data in found:
            if (
                isinstance(data, dict)
                and data.get("format") == PUBLISH_FORMAT
                and data.get("repo") == self.id
                and data.get("author") == author
                and data.get("seq") == seq
                and isinstance(data.get("clock"), int)
                and isinstance(data.get("tag"), str)
            ):
                tag = self.tag_record(data["tag"])
                if tag is not None and tag["commit"] == data.get("commit"):
                    records.append(data)
        if not records:
            return None
        return max(records, key=lambda d: (d["clock"], d["author"], d["seq"]))

    def published_units(self) -> dict[str, Any]:
        """What the Agent reads (design §7): the published version, or the head
        of a repository never published. A published commit not applied here
        yet is served as the head until it arrives."""
        record = self.published()
        if record is not None and record["commit"] in {cid for _, cid in self._ordered()}:
            return self.state_at(record["commit"])
        return self.units()

    # -- status ---------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """The repository header: behind, ahead, uncommitted, conflicts, waiting."""
        with self.lock:
            scan = self._read_only_scan()
            with closing(self._connect()) as db:
                applied = {r["file"] for r in db.execute("SELECT file FROM applied")}
                waiting = []
                behind = 0
                for commit in scan.commits:
                    if commit.name in applied:
                        continue
                    missing, differs = self._files_state(db, commit)
                    if missing or differs:
                        waiting.append({"commit": commit.name, "files": missing + differs})
                    else:
                        behind += 1
                open_conflicts = db.execute(
                    "SELECT COUNT(*) FROM conflicts WHERE status = 'open'"
                ).fetchone()[0]
            pending = self._pending()
            published = self.published()
            units = self.units()
            return {
                "id": self.id,
                "title": self.document["title"],
                "type": self.document["type"],
                "author": self.author,
                "head": self.head(),
                "behind": behind,
                "ahead": len(self._local_commits()),
                "uncommitted": len(pending["sets"]) + len(pending["files"]),
                "conflicts": int(open_conflicts),
                "waiting": waiting,
                "bad": scan.bad,
                "published": None
                if published is None
                else {k: published[k] for k in ("tag", "commit", "author", "at")},
                "schema": units.get(SCHEMA_UNIT),
            }
