"""BI vaults: a shared folder of change files is the truth (BI vaults phase V4).

Design: `docs/phases/BI_VAULT.md` §3 and §4; contract: `docs/CONTRACTS.md`
"BI vaults: folder, change files, sync".

A vault is a folder (a SharePoint library synced by OneDrive) holding
`vault.json`, `VAULT.md`, the segment and library folders, `schemas/`,
`skills/` and `changes/<author>/<seq>.json`. No database is ever in the
folder: each PC keeps `<workspace>/bi/vaults/<vault id>/bi.sqlite`, built by
applying every change file in one total order, (Lamport clock, author, seq).

A write to the vault's dataset (`vault-<id>`) runs the store's own write
method on the local database inside a transaction that is always rolled back
(`capture`): what the method changed (history rows, proposals, evidence,
cards, imports, meta) becomes the operations of one new change file in this
PC's own author folder, and that file is then applied like any other. So the
local database is only ever a function of the files, and two PCs with the
same files have the same cards.

Applying is deterministic. A field operation carries the value it was made
from (`base`); when the field holds something else at that point of the order
the operation becomes a pending proposal (as an import over a person's value
does) and a conflict row. A card created twice with the same type and key is
one card with a `merge` flag. A file whose run id was applied already is
recorded and skipped. A file arriving late with an earlier order key, or an
applied file that changed or vanished, rebuilds the database from all files.
A malformed file is skipped and reported; a file that is not valid JSON yet
(OneDrive still syncing it) is retried on the next sync.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from capabilities.bi_cards import catalog
from capabilities.bi_cards.store import (
    DATASET_RE,
    DB_FILE,
    SCHEMA,
    SUBSCRIBED_DIR,
    VAULT_PREFIX,
    VAULT_REGISTRY,
    VAULTS_DIR,
    BiStore,
    BiStoreError,
    is_subscribed,
    now,
    vault_registry,
)

VAULT_FORMAT = "bi.vault/v1"
CHANGE_FORMAT = "bi.vault.change/v1"
VAULT_FILE = "vault.json"
README_FILE = "VAULT.md"
CHANGES_DIR = "changes"
STATE_FILE = "vault_sync.json"
VAULT_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_VAULT_ID = 40 - len(VAULT_PREFIX)
AUTHOR_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
MAX_AUTHOR = 40
CHANGE_NAME_RE = re.compile(r"^([1-9][0-9]{0,8})\.json$")
MAX_CHANGE_BYTES = 64 * 1024 * 1024

#: The 11 market segments of the owner's chart (BI_VAULT.md §4, §6.2):
#: folder name and label. A vault may name its own at creation.
SEGMENTS: tuple[tuple[str, str], ...] = (
    ("cell-phone", "Cell Phone"),
    ("ap-cpe", "AP/CPE"),
    ("module-iot", "Module/IoT"),
    ("aidc-computing", "AIDC Computing"),
    ("aidc-power", "AIDC Power"),
    ("car-ebus-electronics", "Car/eBus electronics"),
    ("robotics-amr", "Robotics/AMR"),
    ("space-satellite", "Space Satellite"),
    ("uav", "UAV"),
    ("radar-ew", "Radar/EW"),
    ("osat", "OSAT"),
)
LIBRARY = ("products", "competitors", "technologies")

#: The vault's own tables in the local `bi.sqlite` (never in the folder).
VAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_applied (
  file TEXT PRIMARY KEY,
  author TEXT NOT NULL,
  seq INTEGER NOT NULL,
  clock INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  outcome TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS vault_pkeys (
  pkey TEXT PRIMARY KEY,
  proposal_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS vault_conflicts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file TEXT NOT NULL,
  kind TEXT NOT NULL,
  card_id TEXT,
  field TEXT,
  proposal_id INTEGER,
  detail TEXT NOT NULL,
  at TEXT NOT NULL
);
"""
#: Every table a rebuild empties, in the store and the vault's own.
TABLES = (
    "cards",
    "fields",
    "history",
    "proposals",
    "meta",
    "imports",
    "evidence",
    "vault_applied",
    "vault_pkeys",
    "vault_conflicts",
)

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock(key: str) -> threading.RLock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def _dump(value: Any) -> str:
    """A stored value's text, exactly as the store writes it."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _text(value: Any) -> str | None:
    return None if value is None else _dump(value)


def _load(text: str | None) -> Any:
    return None if text is None else json.loads(text)


def card_id_for(entity_type: str, canonical_key: str) -> str:
    """A card's id in a vault: the same on every PC."""
    digest = hashlib.sha256(f"{entity_type}\0{canonical_key}".encode()).hexdigest()
    return digest[:12]


def dataset_name(vault_id: str) -> str:
    return VAULT_PREFIX + vault_id


def local_dir(workspace: Path, vault_id: str) -> Path:
    return workspace / "bi" / VAULTS_DIR / vault_id


# -- the registry (per PC) ---------------------------------------------------


def _registry_path(workspace: Path) -> Path:
    return workspace / "bi" / VAULTS_DIR / VAULT_REGISTRY


def registry_entry(workspace: Path, vault_id: str) -> dict[str, Any] | None:
    return next((i for i in vault_registry(workspace) if i["id"] == vault_id), None)


def _register(workspace: Path, item: dict[str, Any]) -> None:
    items = [i for i in vault_registry(workspace) if i["id"] != item["id"]]
    items.append(item)
    items.sort(key=lambda i: str(i["id"]))
    _write_atomic(_registry_path(workspace), _pretty({"vaults": items}))


def _pretty(document: Any) -> bytes:
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode()


def _write_atomic(path: Path, data: bytes) -> None:
    """Write `path` through a temporary file in the same folder and a rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex[:8]}.tmp"
    temporary.write_bytes(data)
    os.replace(temporary, path)


# -- the folder ----------------------------------------------------------------


def read_vault_json(folder: Path) -> dict[str, Any]:
    """The folder's `vault.json`, checked; `vault_invalid` when it is not one."""
    try:
        document = json.loads((folder / VAULT_FILE).read_text(encoding="utf-8"))
    except OSError:
        raise BiStoreError(
            "vault_invalid", f"資料夾裡沒有 {VAULT_FILE}，不是一個知識庫", path=str(folder)
        ) from None
    except ValueError:
        raise BiStoreError("vault_invalid", f"{VAULT_FILE} 不是有效的 JSON") from None
    problems = []
    if not isinstance(document, dict):
        raise BiStoreError("vault_invalid", f"{VAULT_FILE} 必須是 JSON 物件")
    if document.get("format") != VAULT_FORMAT:
        problems.append(f"format 必須是 {VAULT_FORMAT}")
    vault_id = document.get("id")
    if not isinstance(vault_id, str) or not _valid_vault_id(vault_id):
        problems.append("id 無效")
    for key in ("title", "schema"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            problems.append(f"缺少 {key}")
    if not isinstance(document.get("purpose", ""), str):
        problems.append("purpose 必須是文字")
    if problems:
        raise BiStoreError("vault_invalid", f"{VAULT_FILE} 有問題：" + "；".join(problems))
    return document


def _valid_vault_id(vault_id: str) -> bool:
    return len(vault_id) <= MAX_VAULT_ID and VAULT_ID_RE.match(vault_id) is not None


def _slug(text: str, limit: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:limit].strip("-")


def default_author(actor: str) -> str:
    """An author folder name from the person's name (`leo.chi via web` -> `leo.chi`)."""
    person = actor.removesuffix(" via web").strip().lower()
    slug = re.sub(r"[^a-z0-9._-]+", "-", person).strip("-._")
    slug = re.sub(r"[._-]{2,}", "-", slug)
    return slug[:MAX_AUTHOR].strip("-._") or "author"


def _checked_author(value: Any, actor: str) -> str:
    author = str(value or "").strip().lower() or default_author(actor)
    if len(author) > MAX_AUTHOR or AUTHOR_RE.match(author) is None:
        raise BiStoreError(
            "author_invalid", "作者名稱只能用小寫英數字與 . _ -（最多 40 個字），例如 leo.chi"
        )
    return author


def _folder(value: Any, *, must_exist: bool) -> Path:
    text = str(value or "").strip()
    if not text:
        raise BiStoreError("path_missing", "需要資料夾路徑")
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise BiStoreError("path_invalid", "請給完整的資料夾路徑（例如 C:\\Users\\...\\Vaults）")
    if must_exist and not path.is_dir():
        raise BiStoreError("path_missing", f"找不到資料夾 {path}")
    return path


def _readme(document: dict[str, Any]) -> str:
    segments = "\n".join(
        f"- `applications/{item['folder']}/sources/` — {item['label']}"
        for item in document["folders"]["applications"]
    )
    library = "\n".join(f"- `library/{name}/sources/`" for name in LIBRARY)
    return (
        f"# {document['title']}\n\n"
        f"{document.get('purpose') or ''}\n\n"
        "## When the AEP Agent should use this vault\n\n"
        "When a question matches the purpose above. The cards are the vault's knowledge; "
        "every value keeps its source and evidence.\n\n"
        "## Folders\n\n"
        f"{segments}\n{library}\n"
        "- `schemas/` — published schema versions (never edited)\n"
        "- `skills/` — extraction Skill revisions (never edited)\n"
        "- `changes/<author>/<seq>.json` — every write, one new file each (never edited)\n\n"
        "## How to maintain it\n\n"
        "Write only through AEP. Each person adds files to their own `changes/<author>/` folder "
        "and never edits or deletes another file. Keep this folder 「一律保留在此裝置上」 in "
        "OneDrive so every file is on disk. Schema: "
        f"`{document['schema']}`; vault id `{document['id']}`.\n"
    )


def _segments(value: Any) -> list[dict[str, str]]:
    if value is None:
        return [{"folder": folder, "label": label} for folder, label in SEGMENTS]
    if not isinstance(value, list) or not value:
        raise BiStoreError("segments_invalid", "segments 必須是非空清單")
    found = []
    for item in value:
        label = str(item.get("label") if isinstance(item, dict) else item or "").strip()
        folder = str(item.get("folder") or "") if isinstance(item, dict) else ""
        folder = folder or _slug(label, 40)
        if not label or VAULT_ID_RE.match(folder) is None:
            raise BiStoreError("segments_invalid", f"應用領域「{label}」需要英數字的資料夾名稱")
        found.append({"folder": folder, "label": label})
    if len({f["folder"] for f in found}) != len(found):
        raise BiStoreError("segments_invalid", "應用領域的資料夾名稱重複")
    return found


def _lay_out(folder: Path, document: dict[str, Any]) -> None:
    for item in document["folders"]["applications"]:
        (folder / "applications" / item["folder"] / "sources").mkdir(parents=True, exist_ok=True)
    for name in LIBRARY:
        (folder / "library" / name / "sources").mkdir(parents=True, exist_ok=True)
    for name in ("schemas", "skills", CHANGES_DIR):
        (folder / name).mkdir(parents=True, exist_ok=True)
    _write_atomic(folder / VAULT_FILE, _pretty(document))
    _write_atomic(folder / README_FILE, _readme(document).encode())


def _schema_file_name(schema_id: str, version: str) -> str:
    return f"{schema_id.replace('/', '__')}@{version}.json"


def _export_schema(workspace: Path, folder: Path, ref: str) -> None:
    """Copy an installed schema into `schemas/` so every PC can install it;
    the shipped schema is on every PC already. A published file is never
    replaced."""
    try:
        reg = catalog.resolve(workspace, ref)
    except BiStoreError:
        return
    if reg.source != "installed":
        return
    target = folder / "schemas" / _schema_file_name(reg.schema_id, reg.version)
    if target.is_file():
        return
    source = catalog.schema_path(workspace, reg.schema_id, reg.version)
    _write_atomic(target, source.read_bytes())


# -- change files --------------------------------------------------------------


@dataclass(frozen=True)
class ChangeFile:
    name: str  # `<author>/<seq>`
    author: str
    seq: int
    clock: int
    sha256: str
    data: dict[str, Any]

    @property
    def key(self) -> tuple[int, str, int]:
        return (self.clock, self.author, self.seq)


def _problem(data: Any, author: str, seq: int, vault_id: str) -> str | None:
    """Why a parsed change file cannot be applied; None when it can."""
    if not isinstance(data, dict):
        return "not a JSON object"
    if data.get("format") != CHANGE_FORMAT:
        return f"format is not {CHANGE_FORMAT}"
    if data.get("vault") != vault_id:
        return "vault id differs"
    if data.get("author") != author:
        return "author differs from its folder"
    if data.get("seq") != seq:
        return "seq differs from its file name"
    clock = data.get("clock")
    if not isinstance(clock, int) or isinstance(clock, bool) or clock < 1:
        return "clock missing"
    if not isinstance(data.get("at"), str):
        return "at missing"
    ops = data.get("ops")
    if not isinstance(ops, list):
        return "ops missing"
    for index, op in enumerate(ops):
        found = _op_problem(op)
        if found:
            return f"op {index}: {found}"
    return None


#: The keys every operation must carry, all strings.
OP_KEYS: dict[str, tuple[str, ...]] = {
    "meta": ("key",),
    "import": ("id", "filename", "entity_type", "at", "by"),
    "card": ("type", "key", "name"),
    "field": ("type", "key", "field"),
    "propose": ("pkey", "type", "key", "field", "kind", "ref", "at"),
    "proposal": ("pkey", "status"),
    "evidence": ("type", "key", "field", "run_id"),
    "card_delete": ("type", "key"),
    "import_undone": ("id",),
    "snapshot": (),
}


def _op_problem(op: Any) -> str | None:
    if not isinstance(op, dict) or op.get("op") not in OP_KEYS:
        return "unknown op"
    name = op["op"]
    for key in OP_KEYS[name]:
        if not isinstance(op.get(key), str):
            return f"{name}.{key} missing"
    if name == "field":
        history = op.get("history")
        if not isinstance(history, dict) or not all(
            isinstance(history.get(k), str) for k in ("kind", "ref", "by", "at")
        ):
            return "field.history missing"
    if name == "snapshot":
        for key in ("cards", "history", "proposals", "evidence", "imports"):
            if not isinstance(op.get(key), list):
                return f"snapshot.{key} missing"
        if not isinstance(op.get("meta"), dict):
            return "snapshot.meta missing"
    return None


# -- the vault -----------------------------------------------------------------


class Vault:
    """One registered vault on this PC."""

    def __init__(self, workspace: Path, vault_id: str) -> None:
        entry = registry_entry(workspace, vault_id)
        if entry is None:
            raise BiStoreError("vault_unknown", f"這台電腦沒有知識庫「{vault_id}」")
        self.workspace = workspace
        self.id = vault_id
        self.folder = Path(str(entry.get("path") or ""))
        self.author = str(entry.get("author") or "")
        self.dataset = dataset_name(vault_id)
        self.local = local_dir(workspace, vault_id)
        self.db_path = self.local / DB_FILE
        self.lock = _lock(str(self.local.resolve()))

    # -- reading the folder ----------------------------------------------

    @property
    def reachable(self) -> bool:
        return (self.folder / VAULT_FILE).is_file()

    def _require_folder(self) -> None:
        if not self.reachable:
            raise BiStoreError(
                "vault_unreachable",
                f"讀不到知識庫資料夾 {self.folder}（OneDrive 是否已同步、路徑是否改了？）",
            )

    def scan(self) -> tuple[list[ChangeFile], list[dict[str, str]], list[dict[str, str]]]:
        """Every change file of the folder: (valid ones, bad ones, incomplete
        ones). Incomplete = unreadable or not valid JSON yet (still syncing)."""
        valid: list[ChangeFile] = []
        bad: list[dict[str, str]] = []
        incomplete: list[dict[str, str]] = []
        root = self.folder / CHANGES_DIR
        if not root.is_dir():
            return valid, bad, incomplete
        for author_dir in sorted(root.iterdir()):
            if author_dir.name.startswith("."):
                continue
            if not author_dir.is_dir():
                bad.append({"file": author_dir.name, "reason": "not an author folder"})
                continue
            author = author_dir.name
            if AUTHOR_RE.match(author) is None:
                bad.append({"file": f"{author}/", "reason": "author folder name invalid"})
                continue
            for path in sorted(author_dir.iterdir()):
                if path.name.startswith(".") or path.name.endswith(".tmp"):
                    continue  # a file still being written
                name = f"{author}/{path.name}"
                matched = CHANGE_NAME_RE.match(path.name)
                if matched is None:
                    bad.append({"file": name, "reason": "file name is not <seq>.json"})
                    continue
                seq = int(matched.group(1))
                try:
                    if path.stat().st_size > MAX_CHANGE_BYTES:
                        bad.append({"file": name, "reason": "file too large"})
                        continue
                    raw = path.read_bytes()
                    data = json.loads(raw.decode("utf-8"))
                except (OSError, ValueError) as failure:
                    incomplete.append({"file": name, "reason": type(failure).__name__})
                    continue
                problem = _problem(data, author, seq, self.id)
                if problem is not None:
                    bad.append({"file": name, "reason": problem})
                    continue
                valid.append(
                    ChangeFile(
                        name=f"{author}/{seq}",
                        author=author,
                        seq=seq,
                        clock=int(data["clock"]),
                        sha256=hashlib.sha256(raw).hexdigest(),
                        data=data,
                    )
                )
        valid.sort(key=lambda f: f.key)
        return valid, bad, incomplete

    # -- the local database ------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        self.local.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.executescript(SCHEMA)
        columns = {r[1] for r in connection.execute("PRAGMA table_info(imports)")}
        if "run_id" not in columns:
            connection.execute("ALTER TABLE imports ADD COLUMN run_id TEXT")
        connection.executescript(VAULT_SCHEMA)
        return connection

    def _install_schemas(self) -> list[dict[str, str]]:
        """Install the schemas the vault published (idempotent)."""
        problems: list[dict[str, str]] = []
        root = self.folder / "schemas"
        if not root.is_dir():
            return problems
        for path in sorted(root.glob("*.json")):
            try:
                catalog.install(self.workspace, path.name, path.read_text(encoding="utf-8"))
            except catalog.SchemaInstallError as failure:
                problems.append({"file": f"schemas/{path.name}", "reason": failure.code})
            except OSError as failure:
                problems.append({"file": f"schemas/{path.name}", "reason": type(failure).__name__})
        return problems

    def sync(self) -> dict[str, Any]:
        """Apply every change file not applied yet, in order; rebuild from all
        files when one arrived late with an earlier key or an applied one
        changed or vanished. Returns what happened."""
        with self.lock:
            self._require_folder()
            schema_problems = self._install_schemas()
            files, bad, incomplete = self.scan()
            present = {f.name: f for f in files}
            with closing(self._connect()) as db:
                applied = {
                    r["file"]: ((int(r["clock"]), str(r["author"]), int(r["seq"])), r["sha256"])
                    for r in db.execute("SELECT * FROM vault_applied")
                }
                new = [f for f in files if f.name not in applied]
                rebuild = any(
                    name not in present or present[name].sha256 != sha
                    for name, (_, sha) in applied.items()
                )
                if new and applied and not rebuild:
                    rebuild = min(f.key for f in new) < max(key for key, _ in applied.values())
                todo = files if rebuild else new
                outcomes: dict[str, int] = {}
                conflicts_before = 0 if rebuild else _count(db, "vault_conflicts")
                if todo or rebuild:
                    db.execute("BEGIN IMMEDIATE")
                    try:
                        if rebuild:
                            for table in TABLES:
                                db.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed names
                            db.execute("DELETE FROM sqlite_sequence")
                        for item in todo:
                            outcome = self._apply_file(db, item)
                            outcomes[outcome] = outcomes.get(outcome, 0) + 1
                        db.execute("COMMIT")
                    except BaseException:
                        db.execute("ROLLBACK")
                        raise
                conflicts = _count(db, "vault_conflicts") - conflicts_before
            report = {
                "ok": True,
                "applied": len(todo),
                "rebuilt": rebuild,
                "outcomes": outcomes,
                "conflicts": conflicts,
                "bad": bad,
                "incomplete": incomplete,
                "schema_problems": schema_problems,
                "files": len(files),
                "at": now(),
            }
            _write_atomic(self.local / STATE_FILE, _pretty(report))
            return report

    def _apply_file(self, db: sqlite3.Connection, item: ChangeFile) -> str:
        """Apply one file inside the open transaction; a file that fails part
        way is rolled back alone and recorded as `failed`."""
        db.execute("SAVEPOINT change_file")
        try:
            outcome, detail = _Applier(db, item).run()
            db.execute("RELEASE change_file")
        except (KeyError, TypeError, ValueError, AttributeError, sqlite3.Error) as failure:
            db.execute("ROLLBACK TO change_file")
            db.execute("RELEASE change_file")
            outcome, detail = "failed", f"{type(failure).__name__}: {failure}"
        db.execute(
            "INSERT OR REPLACE INTO vault_applied (file, author, seq, clock, sha256, outcome, "
            "detail) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (item.name, item.author, item.seq, item.clock, item.sha256, outcome, detail),
        )
        return outcome

    # -- writing change files --------------------------------------------

    def _next(self, db: sqlite3.Connection) -> tuple[int, int]:
        """(seq, clock) of this PC's next change file."""
        own = self.folder / CHANGES_DIR / self.author
        seqs = [0]
        if own.is_dir():
            for path in own.iterdir():
                matched = CHANGE_NAME_RE.match(path.name)
                if matched:
                    seqs.append(int(matched.group(1)))
        row = db.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM vault_applied WHERE author = ?", (self.author,)
        ).fetchone()
        seqs.append(int(row[0]))
        clock = int(db.execute("SELECT COALESCE(MAX(clock), 0) FROM vault_applied").fetchone()[0])
        return max(seqs) + 1, clock + 1

    def emit(
        self,
        ops: list[dict[str, Any]],
        *,
        action: str,
        seq: int,
        clock: int,
    ) -> str:
        """Write one change file (never replacing one) and return its name."""
        if not self.author or AUTHOR_RE.match(self.author) is None:
            raise BiStoreError("author_invalid", "這台電腦在這個知識庫沒有作者名稱，請重新加入")
        run_ids = [op.get("run_id") for op in ops if op.get("op") == "import"]
        document = {
            "format": CHANGE_FORMAT,
            "vault": self.id,
            "author": self.author,
            "seq": seq,
            "clock": clock,
            "at": now(),
            "action": action,
            "run_id": next((r for r in run_ids if r), None),
            "ops": ops,
        }
        own = self.folder / CHANGES_DIR / self.author
        own.mkdir(parents=True, exist_ok=True)
        target = own / f"{seq}.json"
        if target.exists():
            raise BiStoreError("change_exists", f"變更檔 {self.author}/{seq}.json 已經存在")
        _write_atomic(target, _pretty(document))
        return f"{self.author}/{seq}"

    @contextmanager
    def capture(self, store: BiStore) -> Iterator[sqlite3.Connection]:
        """Run a store write on the local database, turn its effect into one
        change file, roll it back, and apply the file."""
        with self.lock:
            self.sync()
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            try:
                before = _State.read(connection)
                yield connection
                seq, clock = self._next(connection)
                ops = _diff(connection, before, f"{self.author}/{seq}")
            finally:
                connection.rollback()
                connection.close()
            if not ops:
                return
            for op in ops:
                if op["op"] == "meta" and op["key"] == "schema" and op.get("value"):
                    # A schema upgrade: publish the new version before the change.
                    _export_schema(self.workspace, self.folder, str(op["value"]))
            self.emit(ops, action=_action(ops), seq=seq, clock=clock)
            self.sync()

    # -- status ------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Applied, behind, conflicts and bad files, without applying anything."""
        reachable = self.reachable
        files: list[ChangeFile] = []
        bad: list[dict[str, str]] = []
        incomplete: list[dict[str, str]] = []
        if reachable:
            files, bad, incomplete = self.scan()
        applied: dict[str, dict[str, Any]] = {}
        conflicts: list[dict[str, Any]] = []
        cards = 0
        if self.db_path.is_file():
            with closing(sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)) as db:
                db.row_factory = sqlite3.Row
                applied = {r["file"]: dict(r) for r in db.execute("SELECT * FROM vault_applied")}
                pending = {
                    int(r[0])
                    for r in db.execute("SELECT id FROM proposals WHERE status = 'pending'")
                }
                for r in db.execute("SELECT * FROM vault_conflicts ORDER BY id"):
                    proposal = r["proposal_id"]
                    conflicts.append(
                        {
                            "id": r["id"],
                            "kind": r["kind"],
                            "file": r["file"],
                            "card_id": r["card_id"],
                            "field": r["field"],
                            "proposal_id": proposal,
                            "open": proposal is not None and int(proposal) in pending,
                            "detail": _load(r["detail"]),
                            "at": r["at"],
                        }
                    )
                cards = _count(db, "cards")
        state: dict[str, Any] = {}
        try:
            state = json.loads((self.local / STATE_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
        names = {f.name for f in files}
        return {
            "vault": self.describe(),
            "reachable": reachable,
            "files": len(files),
            "applied": sum(1 for name in applied if name in names),
            "behind": sum(1 for name in names if name not in applied),
            "skipped": [
                {"file": name, "outcome": item["outcome"], "detail": item["detail"]}
                for name, item in sorted(applied.items())
                if item["outcome"] != "applied"
            ],
            "conflicts": [c for c in conflicts if c["kind"] != "merge"],
            "merges": [c for c in conflicts if c["kind"] == "merge"],
            "bad": bad,
            "incomplete": incomplete,
            "cards": cards,
            "clock": max((int(a["clock"]) for a in applied.values()), default=0),
            "last_sync": state.get("at"),
        }

    def describe(self) -> dict[str, Any]:
        document: dict[str, Any] = {}
        try:
            document = read_vault_json(self.folder)
        except BiStoreError:
            document = {}
        return {
            "id": self.id,
            "dataset": self.dataset,
            "title": document.get("title"),
            "purpose": document.get("purpose"),
            "schema": document.get("schema"),
            "path": str(self.folder),
            "author": self.author,
            "reachable": bool(document),
        }


def _count(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])  # noqa: S608


# -- capturing a store write ---------------------------------------------------


@dataclass
class _State:
    cards: dict[str, dict[str, Any]]
    history: int
    proposals: dict[int, str]
    proposal_max: int
    evidence: int
    meta: dict[str, str]
    imports: dict[str, dict[str, Any]]

    @classmethod
    def read(cls, db: sqlite3.Connection) -> _State:
        return cls(
            cards={r["id"]: dict(r) for r in db.execute("SELECT * FROM cards")},
            history=int(db.execute("SELECT COALESCE(MAX(seq), 0) FROM history").fetchone()[0]),
            proposals={int(r["id"]): r["status"] for r in db.execute("SELECT * FROM proposals")},
            proposal_max=int(
                db.execute("SELECT COALESCE(MAX(id), 0) FROM proposals").fetchone()[0]
            ),
            evidence=int(db.execute("SELECT COALESCE(MAX(seq), 0) FROM evidence").fetchone()[0]),
            meta={r["key"]: r["value"] for r in db.execute("SELECT * FROM meta")},
            imports={r["id"]: dict(r) for r in db.execute("SELECT * FROM imports")},
        )


def _source(row: Any) -> dict[str, Any]:
    return {k: row[k] for k in ("kind", "ref", "by", "at")}


def _diff(db: sqlite3.Connection, before: _State, name: str) -> list[dict[str, Any]]:
    """The operations a write made, in the order they are applied."""
    after = _State.read(db)

    def ident(card_id: str) -> tuple[str, str]:
        card = after.cards.get(card_id) or before.cards[card_id]
        return str(card["entity_type"]), str(card["canonical_key"])

    ops: list[dict[str, Any]] = []
    for key in sorted(set(before.meta) | set(after.meta)):
        if before.meta.get(key) != after.meta.get(key):
            ops.append(
                {
                    "op": "meta",
                    "key": key,
                    "base": before.meta.get(key),
                    "value": after.meta.get(key),
                }
            )
    for import_id, row in after.imports.items():
        if import_id not in before.imports:
            ops.append(
                {
                    "op": "import",
                    "id": import_id,
                    "filename": row["filename"],
                    "entity_type": row["entity_type"],
                    "at": row["at"],
                    "by": row["by"],
                    "run_id": row.get("run_id"),
                }
            )
    history = list(
        db.execute("SELECT * FROM history WHERE seq > ? ORDER BY seq", (before.history,))
    )
    proposals = list(
        db.execute("SELECT * FROM proposals WHERE id > ? ORDER BY id", (before.proposal_max,))
    )
    evidence = list(
        db.execute("SELECT * FROM evidence WHERE seq > ? ORDER BY seq", (before.evidence,))
    )
    touched = {r["card_id"] for r in [*history, *proposals, *evidence]}
    touched |= {i for i, c in after.cards.items() if before.cards.get(i) != c}
    for card_id in sorted(touched & set(after.cards), key=ident):
        card = after.cards[card_id]
        earlier = before.cards.get(card_id)
        ops.append(
            {
                "op": "card",
                "type": card["entity_type"],
                "key": card["canonical_key"],
                "name": card["name"],
                "synthetic": bool(card["synthetic"]),
                "new": earlier is None,
                "version": int(card["version"]),
                "delta": int(card["version"]) - (0 if earlier is None else int(earlier["version"])),
                "created": card["created"],
                "updated": card["updated"],
                "created_by_import": card["created_by_import"],
            }
        )
    last = {(r["card_id"], r["field"]): r["seq"] for r in history}
    for row in history:
        entity_type, key = ident(row["card_id"])
        source = None
        if row["new"] is not None:
            source = {"kind": row["kind"], "ref": row["ref"], "by": row["by"], "at": row["at"]}
            if last[(row["card_id"], row["field"])] == row["seq"]:
                stored = db.execute(
                    "SELECT * FROM fields WHERE card_id = ? AND field = ?",
                    (row["card_id"], row["field"]),
                ).fetchone()
                if stored is not None:
                    source = _source(stored)
        ops.append(
            {
                "op": "field",
                "type": entity_type,
                "key": key,
                "field": row["field"],
                "base": _load(row["old"]),
                "value": _load(row["new"]),
                "source": source,
                "history": {
                    "kind": row["kind"],
                    "ref": row["ref"],
                    "by": row["by"],
                    "at": row["at"],
                    "import_id": row["import_id"],
                    "reason": row["reason"],
                    "old_source": _load(row["old_source"]),
                },
            }
        )
    for index, row in enumerate(proposals):
        entity_type, key = ident(row["card_id"])
        ops.append(
            {
                "op": "propose",
                "pkey": f"{name}#p{index}",
                "type": entity_type,
                "key": key,
                "field": row["field"],
                "value": _load(row["value"]),
                "kind": row["kind"],
                "ref": row["ref"],
                "at": row["at"],
                "import_id": row["import_id"],
                "status": row["status"],
            }
        )
    for proposal_id, status in sorted(before.proposals.items()):
        if after.proposals.get(proposal_id) != status:
            found = db.execute(
                "SELECT pkey FROM vault_pkeys WHERE proposal_id = ? ORDER BY pkey LIMIT 1",
                (proposal_id,),
            ).fetchone()
            ops.append(
                {
                    "op": "proposal",
                    "pkey": "" if found is None else str(found[0]),
                    "status": after.proposals.get(proposal_id) or "withdrawn",
                }
            )
    for row in evidence:
        entity_type, key = ident(row["card_id"])
        stored = db.execute(
            "SELECT value FROM fields WHERE card_id = ? AND field = ?",
            (row["card_id"], row["field"]),
        ).fetchone()
        ops.append(
            {
                "op": "evidence",
                "type": entity_type,
                "key": key,
                "field": row["field"],
                "value": None if stored is None else _load(stored[0]),
                "run_id": row["run_id"],
                "source_id": row["source_id"],
                "source_name": row["source_name"],
                "locator": _load(row["locator"]),
                "excerpt": row["excerpt"],
                "basis": row["basis"],
                "at": row["at"],
            }
        )
    for card_id in sorted(set(before.cards) - set(after.cards), key=ident):
        entity_type, key = ident(card_id)
        ops.append({"op": "card_delete", "type": entity_type, "key": key})
    for import_id, row in after.imports.items():
        earlier = before.imports.get(import_id)
        if earlier is not None and row["undone"] and not earlier["undone"]:
            ops.append({"op": "import_undone", "id": import_id})
    return ops


def _action(ops: list[dict[str, Any]]) -> str:
    """What a change file did, for people reading the folder."""
    names = {op["op"] for op in ops}
    if any(op["op"] == "import" and op.get("run_id") for op in ops):
        return "commit_run"
    if "import" in names:
        return "import"
    if "import_undone" in names:
        return "undo_import"
    if any(op["op"] == "meta" and op["key"] == "schema" for op in ops):
        return "upgrade_schema"
    if "field" in names:
        return "edit"
    if "proposal" in names:
        return "decide_proposal"
    return "change"


# -- applying a change file ----------------------------------------------------


class _Applier:
    """Applies one change file's operations to the open transaction."""

    def __init__(self, db: sqlite3.Connection, item: ChangeFile) -> None:
        self.db = db
        self.item = item
        self.at = str(item.data["at"])
        self.applied_cards: set[str] = set()
        self.inserted: set[str] = set()

    def run(self) -> tuple[str, str]:
        ops: list[dict[str, Any]] = list(self.item.data["ops"])
        for op in ops:
            if op["op"] == "import":
                run_id = op.get("run_id")
                if (
                    run_id
                    and self.db.execute(
                        "SELECT 1 FROM imports WHERE run_id = ?", (run_id,)
                    ).fetchone()
                ):
                    self._conflict("duplicate_run", None, None, None, {"run_id": run_id})
                    return "duplicate_run", str(run_id)
                if self.db.execute("SELECT 1 FROM imports WHERE id = ?", (op["id"],)).fetchone():
                    self._conflict("duplicate_import", None, None, None, {"import_id": op["id"]})
                    return "duplicate_import", str(op["id"])
        by_kind: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        for index, op in enumerate(ops):
            by_kind.setdefault(op["op"], []).append((index, op))
        for _, op in by_kind.get("meta", []):
            self._meta(op)
        for _, op in by_kind.get("import", []):
            self._import(op)
        for _, op in by_kind.get("snapshot", []):
            self._snapshot(op)
        for _, op in by_kind.get("card", []):
            self._ensure(op)
        field_cards = {(op["type"], op["key"]) for _, op in by_kind.get("field", [])}
        for index, op in by_kind.get("field", []):
            self._field(index, op)
        for _, op in by_kind.get("propose", []):
            self._propose(op)
        for _, op in by_kind.get("proposal", []):
            self._decide(op)
        for _, op in by_kind.get("evidence", []):
            self._evidence(op)
        for _, op in by_kind.get("card_delete", []):
            self._delete(op)
        for _, op in by_kind.get("card", []):
            self._bump(op, (op["type"], op["key"]) in field_cards)
        for _, op in by_kind.get("import_undone", []):
            self.db.execute("UPDATE imports SET undone = 1 WHERE id = ?", (op["id"],))
        return "applied", ""

    # -- helpers -----------------------------------------------------------

    def _conflict(
        self,
        kind: str,
        card_id: str | None,
        field: str | None,
        proposal_id: int | None,
        detail: dict[str, Any],
    ) -> None:
        self.db.execute(
            "INSERT INTO vault_conflicts (file, kind, card_id, field, proposal_id, detail, at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (self.item.name, kind, card_id, field, proposal_id, _dump(detail), self.at),
        )

    def _card_id(self, entity_type: str, key: str) -> str | None:
        row = self.db.execute(
            "SELECT id FROM cards WHERE entity_type = ? AND canonical_key = ?", (entity_type, key)
        ).fetchone()
        return None if row is None else str(row[0])

    def _insert_card(self, card: dict[str, Any], wanted: str | None = None) -> str:
        card_id = wanted or card_id_for(card["type"], card["key"])
        if self.db.execute("SELECT 1 FROM cards WHERE id = ?", (card_id,)).fetchone():
            card_id = card_id_for(card["type"], card["key"])
        self.db.execute(
            "INSERT INTO cards (id, entity_type, canonical_key, name, version, synthetic, "
            "created, updated, created_by_import) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                card_id,
                card["type"],
                card["key"],
                card["name"],
                int(card.get("version") or 1),
                int(bool(card.get("synthetic"))),
                str(card.get("created") or self.at),
                str(card.get("updated") or self.at),
                card.get("created_by_import"),
            ),
        )
        self.inserted.add(card_id)
        return card_id

    def _ensure(self, op: dict[str, Any]) -> None:
        card_id = self._card_id(op["type"], op["key"])
        if card_id is None:
            card_id = self._insert_card(op)
            if not op.get("new"):
                # Deleted here (an undo elsewhere) but written on from an older state.
                self._conflict("recreated", card_id, None, None, {"name": op["name"]})
        elif op.get("new"):
            # Two PCs created the same type and key: one card, flagged for a person.
            self._conflict(
                "merge",
                card_id,
                None,
                None,
                {"type": op["type"], "key": op["key"], "name": op["name"]},
            )

    def _bump(self, op: dict[str, Any], has_fields: bool) -> None:
        card_id = self._card_id(op["type"], op["key"])
        if card_id is None or card_id in self.inserted:
            return
        if has_fields and card_id not in self.applied_cards:
            return  # every value it carried became a proposal
        delta = int(op.get("delta") or 0)
        if delta:
            self.db.execute(
                "UPDATE cards SET version = version + ?, updated = ? WHERE id = ?",
                (delta, str(op.get("updated") or self.at), card_id),
            )
        if op.get("synthetic"):
            self.db.execute("UPDATE cards SET synthetic = 1 WHERE id = ?", (card_id,))

    def _meta(self, op: dict[str, Any]) -> None:
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (op["key"],)).fetchone()
        current = None if row is None else str(row[0])
        value = op.get("value")
        if current == value:
            return
        if current != op.get("base"):
            self._conflict(
                "meta",
                None,
                op["key"],
                None,
                {"base": op.get("base"), "current": current, "value": value},
            )
            return
        if value is None:
            self.db.execute("DELETE FROM meta WHERE key = ?", (op["key"],))
        else:
            self.db.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (op["key"], str(value))
            )

    def _import(self, op: dict[str, Any]) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO imports (id, filename, entity_type, at, by, undone, run_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                op["id"],
                op["filename"],
                op["entity_type"],
                op["at"],
                op["by"],
                int(bool(op.get("undone"))),
                op.get("run_id"),
            ),
        )

    def _field(self, index: int, op: dict[str, Any]) -> None:
        history: dict[str, Any] = op["history"]
        value_text = _text(op.get("value"))
        card_id = self._card_id(op["type"], op["key"])
        if card_id is None:
            if value_text is None:
                return  # removing a value of a card that is gone already
            card_id = self._insert_card({"type": op["type"], "key": op["key"], "name": op["key"]})
            self._conflict("recreated", card_id, op["field"], None, {"name": op["key"]})
        stored = self.db.execute(
            "SELECT * FROM fields WHERE card_id = ? AND field = ?", (card_id, op["field"])
        ).fetchone()
        current = None if stored is None else str(stored["value"])
        if current == value_text:
            return  # the same value already: nothing to change
        if current != _text(op.get("base")):
            self._kept(index, card_id, op, current)
            return
        if value_text is None:
            self.db.execute(
                "DELETE FROM fields WHERE card_id = ? AND field = ?", (card_id, op["field"])
            )
        else:
            source = op.get("source") or {k: history.get(k) for k in ("kind", "ref", "by", "at")}
            self.db.execute(
                "INSERT OR REPLACE INTO fields (card_id, field, value, kind, ref, by, at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    card_id,
                    op["field"],
                    value_text,
                    source["kind"],
                    source["ref"],
                    source["by"],
                    source["at"],
                ),
            )
        old_source = history.get("old_source")
        self.db.execute(
            "INSERT INTO history (card_id, field, old, new, kind, ref, by, at, import_id, "
            "reason, old_source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                card_id,
                op["field"],
                current,
                value_text,
                history["kind"],
                history["ref"],
                history["by"],
                history["at"],
                history.get("import_id"),
                history.get("reason"),
                None if old_source is None else _dump(old_source),
            ),
        )
        self.applied_cards.add(card_id)

    def _kept(self, index: int, card_id: str, op: dict[str, Any], current: str | None) -> None:
        """A change made from another value than the field holds now: a
        pending proposal for a person, never a silent overwrite."""
        history: dict[str, Any] = op["history"]
        value_text = _text(op.get("value")) or "null"
        pending = self.db.execute(
            "SELECT id FROM proposals WHERE card_id = ? AND field = ? AND value = ? AND "
            "status = 'pending'",
            (card_id, op["field"], value_text),
        ).fetchone()
        if pending is None:
            cursor = self.db.execute(
                "INSERT INTO proposals (card_id, field, value, kind, ref, at, import_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    card_id,
                    op["field"],
                    value_text,
                    history["kind"],
                    f"vault:{self.item.name}#{index}",
                    history["at"],
                    history.get("import_id"),
                ),
            )
            proposal_id = int(cursor.lastrowid or 0)
        else:
            proposal_id = int(pending[0])
        self.db.execute(
            "INSERT OR REPLACE INTO vault_pkeys (pkey, proposal_id) VALUES (?, ?)",
            (f"{self.item.name}#c{index}", proposal_id),
        )
        self._conflict(
            "field",
            card_id,
            op["field"],
            proposal_id,
            {
                "base": op.get("base"),
                "current": _load(current),
                "value": op.get("value"),
                "by": history.get("by"),
                "author": self.item.author,
                "evidence": [],
            },
        )

    def _propose(self, op: dict[str, Any]) -> None:
        card_id = self._card_id(op["type"], op["key"])
        if card_id is None:
            card_id = self._insert_card({"type": op["type"], "key": op["key"], "name": op["key"]})
            self._conflict("recreated", card_id, op["field"], None, {"name": op["key"]})
        value_text = _dump(op.get("value"))
        status = str(op.get("status") or "pending")
        pending = self.db.execute(
            "SELECT id FROM proposals WHERE card_id = ? AND field = ? AND value = ? AND "
            "status = 'pending'",
            (card_id, op["field"], value_text),
        ).fetchone()
        if pending is not None and status == "pending":
            proposal_id = int(pending[0])
        else:
            cursor = self.db.execute(
                "INSERT INTO proposals (card_id, field, value, kind, ref, at, import_id, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    card_id,
                    op["field"],
                    value_text,
                    op["kind"],
                    op["ref"],
                    op["at"],
                    op.get("import_id"),
                    status,
                ),
            )
            proposal_id = int(cursor.lastrowid or 0)
        self.db.execute(
            "INSERT OR REPLACE INTO vault_pkeys (pkey, proposal_id) VALUES (?, ?)",
            (op["pkey"], proposal_id),
        )

    def _decide(self, op: dict[str, Any]) -> None:
        found = self.db.execute(
            "SELECT p.id, p.status, p.card_id, p.field FROM vault_pkeys k "
            "JOIN proposals p ON p.id = k.proposal_id WHERE k.pkey = ?",
            (op["pkey"],),
        ).fetchone()
        if found is None:
            self._conflict("proposal", None, None, None, {"pkey": op["pkey"], "missing": True})
            return
        if found["status"] == op["status"]:
            return
        if found["status"] != "pending":
            # Decided elsewhere first: keep that decision, report this one.
            self._conflict(
                "proposal",
                found["card_id"],
                found["field"],
                int(found["id"]),
                {"pkey": op["pkey"], "status": op["status"], "current": found["status"]},
            )
            return
        self.db.execute("UPDATE proposals SET status = ? WHERE id = ?", (op["status"], found["id"]))

    def _evidence(self, op: dict[str, Any]) -> None:
        card_id = self._card_id(op["type"], op["key"])
        stored = (
            None
            if card_id is None
            else self.db.execute(
                "SELECT value FROM fields WHERE card_id = ? AND field = ?", (card_id, op["field"])
            ).fetchone()
        )
        if card_id is None or stored is None or str(stored[0]) != _text(op.get("value")):
            # The value it supports was not applied (it became a proposal).
            row = self.db.execute(
                "SELECT id, detail FROM vault_conflicts WHERE file = ? AND card_id IS ? AND "
                "field = ? AND kind = 'field' ORDER BY id DESC LIMIT 1",
                (self.item.name, card_id, op["field"]),
            ).fetchone()
            item = {k: op.get(k) for k in ("run_id", "source_id", "source_name", "locator")}
            item.update({k: op.get(k) for k in ("excerpt", "basis", "at")})
            if row is not None:
                detail = _load(row["detail"]) or {}
                detail.setdefault("evidence", []).append(item)
                self.db.execute(
                    "UPDATE vault_conflicts SET detail = ? WHERE id = ?", (_dump(detail), row["id"])
                )
            else:
                self._conflict("evidence", card_id, op["field"], None, item)
            return
        self.db.execute(
            "INSERT INTO evidence (card_id, field, run_id, source_id, source_name, locator, "
            "excerpt, basis, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                card_id,
                op["field"],
                op["run_id"],
                str(op.get("source_id") or ""),
                str(op.get("source_name") or ""),
                _dump(op.get("locator") or {}),
                str(op.get("excerpt") or ""),
                str(op.get("basis") or "fact"),
                str(op.get("at") or self.at),
            ),
        )

    def _delete(self, op: dict[str, Any]) -> None:
        card_id = self._card_id(op["type"], op["key"])
        if card_id is None:
            return
        left = self.db.execute(
            "SELECT COUNT(*) FROM fields WHERE card_id = ?", (card_id,)
        ).fetchone()[0]
        if left:
            self._conflict("delete_kept", card_id, None, None, {"fields": int(left)})
            return
        self.db.execute("DELETE FROM cards WHERE id = ?", (card_id,))

    def _snapshot(self, op: dict[str, Any]) -> None:
        """A whole dataset (dataset to vault): its cards with their ids,
        values, history, proposals and evidence, inserted as they were. A card
        that exists already is flagged `merge`; its differing values become
        proposals."""
        for key, value in sorted(op["meta"].items()):
            self._meta({"op": "meta", "key": key, "base": None, "value": value})
        for item in op["imports"]:
            self._import(item)
        ids: dict[str, str] = {}  # the snapshot's card id -> the id here (inserted ones)
        for index, card in enumerate(op["cards"]):
            existing = self._card_id(card["type"], card["key"])
            if existing is not None:
                self._conflict(
                    "merge",
                    existing,
                    None,
                    None,
                    {"type": card["type"], "key": card["key"], "name": card["name"]},
                )
                for name, field in sorted(card.get("fields", {}).items()):
                    self._field(
                        index,
                        {
                            "type": card["type"],
                            "key": card["key"],
                            "field": name,
                            "base": None,
                            "value": field["value"],
                            "source": field,
                            "history": {**field, "import_id": None, "reason": None},
                        },
                    )
                continue
            card_id = self._insert_card(card, str(card.get("id") or "") or None)
            ids[str(card.get("id") or card_id)] = card_id
            for name, field in sorted(card.get("fields", {}).items()):
                self.db.execute(
                    "INSERT INTO fields (card_id, field, value, kind, ref, by, at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        card_id,
                        name,
                        _dump(field["value"]),
                        field["kind"],
                        field["ref"],
                        field["by"],
                        field["at"],
                    ),
                )
        for row in op["history"]:
            target = ids.get(str(row["card"]))
            if target is None:
                continue
            self.db.execute(
                "INSERT INTO history (card_id, field, old, new, kind, ref, by, at, import_id, "
                "reason, old_source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    target,
                    row["field"],
                    _text(row.get("old")),
                    _text(row.get("new")),
                    row["kind"],
                    row["ref"],
                    row["by"],
                    row["at"],
                    row.get("import_id"),
                    row.get("reason"),
                    _text(row.get("old_source")),
                ),
            )
        for row in op["proposals"]:
            target = ids.get(str(row["card"]))
            if target is None:
                continue
            cursor = self.db.execute(
                "INSERT INTO proposals (card_id, field, value, kind, ref, at, import_id, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    target,
                    row["field"],
                    _dump(row.get("value")),
                    row["kind"],
                    row["ref"],
                    row["at"],
                    row.get("import_id"),
                    row["status"],
                ),
            )
            self.db.execute(
                "INSERT OR REPLACE INTO vault_pkeys (pkey, proposal_id) VALUES (?, ?)",
                (row["pkey"], int(cursor.lastrowid or 0)),
            )
        for row in op["evidence"]:
            target = ids.get(str(row["card"]))
            if target is None:
                continue
            self.db.execute(
                "INSERT INTO evidence (card_id, field, run_id, source_id, source_name, locator, "
                "excerpt, basis, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    target,
                    row["field"],
                    row["run_id"],
                    row["source_id"],
                    row["source_name"],
                    _dump(row.get("locator")),
                    row["excerpt"],
                    row["basis"],
                    row["at"],
                ),
            )


# -- the store hook ------------------------------------------------------------


@contextmanager
def capture(store: BiStore) -> Iterator[sqlite3.Connection]:
    """`BiStore._db(write=True)` of a vault dataset (see `Vault.capture`)."""
    if store.vault_id is None:
        raise BiStoreError("vault_unknown", "不是知識庫資料集")
    with Vault(store.workspace, store.vault_id).capture(store) as connection:
        yield connection


# -- create, join, convert, list -----------------------------------------------


def _free_name(workspace: Path, vault_id: str) -> None:
    if registry_entry(workspace, vault_id) is not None:
        raise BiStoreError("vault_exists", f"這台電腦已經有知識庫「{vault_id}」")
    if (workspace / "bi" / dataset_name(vault_id)).exists():
        raise BiStoreError(
            "vault_exists", f"已經有一個名為「{dataset_name(vault_id)}」的本機資料集，請換一個 id"
        )
    if local_dir(workspace, vault_id).exists():
        raise BiStoreError("vault_exists", f"本機已有知識庫「{vault_id}」的資料夾")


def _new_vault(
    workspace: Path,
    given: dict[str, Any],
    actor: str,
    schema_ref: str,
) -> tuple[Vault, Path]:
    parent = _folder(given.get("path"), must_exist=True)
    title = str(given.get("title") or "").strip()
    if not title:
        raise BiStoreError("title_missing", "需要知識庫名稱")
    purpose = str(given.get("purpose") or "").strip()
    vault_id = str(given.get("id") or "").strip().lower()
    if not vault_id:
        base = _slug(title, MAX_VAULT_ID - 7) or "vault"
        vault_id = f"{base}-{uuid.uuid4().hex[:6]}"
    if not _valid_vault_id(vault_id):
        raise BiStoreError(
            "vault_id_invalid", f"知識庫 id 只能用小寫英數字與 -，最多 {MAX_VAULT_ID} 個字"
        )
    _free_name(workspace, vault_id)
    author = _checked_author(given.get("author"), actor)
    coverage = given.get("coverage")
    if coverage is not None and not isinstance(coverage, dict):
        raise BiStoreError("coverage_invalid", "coverage 必須是 JSON 物件")
    folder = parent / vault_id
    if folder.exists():
        raise BiStoreError("vault_exists", f"資料夾 {folder} 已經存在")
    document = {
        "format": VAULT_FORMAT,
        "id": vault_id,
        "title": title,
        "purpose": purpose,
        "schema": schema_ref,
        "created": now(),
        "created_by": author,
        "folders": {
            "applications": _segments(given.get("segments")),
            "library": list(LIBRARY),
        },
        "coverage": coverage,
    }
    _lay_out(folder, document)
    _export_schema(workspace, folder, schema_ref)
    _register(workspace, {"id": vault_id, "path": str(folder), "author": author, "joined": now()})
    return Vault(workspace, vault_id), folder


def create(workspace: Path, given: dict[str, Any], actor: str) -> dict[str, Any]:
    """A new vault folder under `path`, bound to `schema`, and this PC joined."""
    reg = catalog.resolve(workspace, str(given.get("schema") or ""))
    vault, _ = _new_vault(workspace, given, actor, reg.ref)
    with vault.lock, closing(vault._connect()) as db:
        seq, clock = vault._next(db)
    vault.emit(
        [{"op": "meta", "key": "schema", "base": None, "value": reg.ref}],
        action="create",
        seq=seq,
        clock=clock,
    )
    report = vault.sync()
    return {"vault": vault.describe(), "sync": report}


def join(workspace: Path, given: dict[str, Any], actor: str) -> dict[str, Any]:
    """Use an existing vault folder on this PC."""
    folder = _folder(given.get("path"), must_exist=True)
    document = read_vault_json(folder)
    vault_id = str(document["id"])
    author = _checked_author(given.get("author"), actor)
    known = registry_entry(workspace, vault_id)
    if known is not None and Path(str(known.get("path"))) != folder:
        # The same vault at a new place (the folder was moved or re-synced).
        _register(workspace, {**known, "path": str(folder)})
    elif known is None:
        _free_name(workspace, vault_id)
        own = folder / CHANGES_DIR / author
        if own.is_dir() and any(own.glob("*.json")) and not given.get("resume"):
            raise BiStoreError(
                "author_taken",
                f"知識庫裡已經有作者「{author}」的變更檔；若是你本人換電腦，請勾選「接續」"
                "（resume），否則請用別的作者名稱",
                author=author,
            )
        _register(
            workspace, {"id": vault_id, "path": str(folder), "author": author, "joined": now()}
        )
    vault = Vault(workspace, vault_id)
    report = vault.sync()
    return {"vault": vault.describe(), "sync": report}


def convert(workspace: Path, given: dict[str, Any], actor: str) -> dict[str, Any]:
    """A new vault holding a local dataset: one initial change file with every
    card, value, history row, proposal and piece of evidence. The dataset
    itself is left as it was."""
    name = str(given.get("dataset") or "").strip()
    if not DATASET_RE.match(name) or is_subscribed(name) or name == SUBSCRIBED_DIR:
        raise BiStoreError("dataset_invalid", "只能轉換這台電腦自己的資料集")
    source = BiStore(workspace, name)
    if source.vault_id is not None:
        raise BiStoreError("dataset_invalid", "這個資料集已經是知識庫")
    if not source.exists:
        raise BiStoreError("dataset_unknown", f"沒有這個資料集「{name}」")
    snapshot = _snapshot(source)
    vault, _ = _new_vault(workspace, {"title": name, **given}, actor, source.schema_ref())
    with vault.lock, closing(vault._connect()) as db:
        seq, clock = vault._next(db)
    vault.emit([snapshot], action="convert", seq=seq, clock=clock)
    report = vault.sync()
    return {"vault": vault.describe(), "sync": report, "dataset": name}


def _snapshot(store: BiStore) -> dict[str, Any]:
    with closing(sqlite3.connect(f"file:{store.path}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        cards = list(db.execute("SELECT * FROM cards ORDER BY entity_type, canonical_key"))
        fields: dict[str, dict[str, Any]] = {}
        for r in db.execute("SELECT * FROM fields ORDER BY card_id, field"):
            fields.setdefault(r["card_id"], {})[r["field"]] = {
                "value": _load(r["value"]),
                **_source(r),
            }
        history = [
            {
                "card": r["card_id"],
                "field": r["field"],
                "old": _load(r["old"]),
                "new": _load(r["new"]),
                "kind": r["kind"],
                "ref": r["ref"],
                "by": r["by"],
                "at": r["at"],
                "import_id": r["import_id"],
                "reason": r["reason"],
                "old_source": _load(r["old_source"]),
            }
            for r in db.execute("SELECT * FROM history ORDER BY seq")
        ]
        proposals = [
            {
                "pkey": f"convert:{store.dataset}#p{r['id']}",
                "card": r["card_id"],
                "field": r["field"],
                "value": _load(r["value"]),
                "kind": r["kind"],
                "ref": r["ref"],
                "at": r["at"],
                "import_id": r["import_id"],
                "status": r["status"],
            }
            for r in db.execute("SELECT * FROM proposals ORDER BY id")
        ]
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        evidence = (
            [
                {
                    "card": r["card_id"],
                    "field": r["field"],
                    "run_id": r["run_id"],
                    "source_id": r["source_id"],
                    "source_name": r["source_name"],
                    "locator": _load(r["locator"]),
                    "excerpt": r["excerpt"],
                    "basis": r["basis"],
                    "at": r["at"],
                }
                for r in db.execute("SELECT * FROM evidence ORDER BY seq")
            ]
            if "evidence" in tables
            else []
        )
        columns = {r[1] for r in db.execute("PRAGMA table_info(imports)")}
        imports = [
            {
                "id": r["id"],
                "filename": r["filename"],
                "entity_type": r["entity_type"],
                "at": r["at"],
                "by": r["by"],
                "undone": bool(r["undone"]),
                "run_id": r["run_id"] if "run_id" in columns else None,
            }
            for r in db.execute("SELECT * FROM imports ORDER BY at, id")
        ]
        meta = (
            {r["key"]: r["value"] for r in db.execute("SELECT * FROM meta")}
            if "meta" in tables
            else {}
        )
    meta.setdefault("schema", store.schema_ref())
    return {
        "op": "snapshot",
        "dataset": store.dataset,
        "meta": meta,
        "imports": imports,
        "cards": [
            {
                "id": c["id"],
                "type": c["entity_type"],
                "key": c["canonical_key"],
                "name": c["name"],
                "version": int(c["version"]),
                "synthetic": bool(c["synthetic"]),
                "created": c["created"],
                "updated": c["updated"],
                "created_by_import": c["created_by_import"],
                "fields": fields.get(c["id"], {}),
            }
            for c in cards
        ],
        "history": history,
        "proposals": proposals,
        "evidence": evidence,
    }


def listing(workspace: Path) -> list[dict[str, Any]]:
    """The vaults this PC uses, with their purpose and card count."""
    found = []
    for item in vault_registry(workspace):
        vault = Vault(workspace, str(item["id"]))
        described = vault.describe()
        store = BiStore(workspace, vault.dataset)
        described["cards"] = len(store.card_rows())
        found.append(described)
    return found


def sync(workspace: Path, vault_id: str) -> dict[str, Any]:
    return Vault(workspace, vault_id).sync()


def status(workspace: Path, vault_id: str) -> dict[str, Any]:
    return Vault(workspace, vault_id).status()
