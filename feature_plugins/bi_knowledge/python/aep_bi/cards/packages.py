"""A working domain's skills and tools as one package (`aep.bi.package/v1`).

Design: `docs/phases/BI_SKILL_TOOL_PACKAGE_IMPORT_DESIGN_20261119.md`; owner choices:
`docs/DECISIONS.md` "2026-11-19 — BI skill/tool package import: owner choices"; contract:
`docs/CONTRACTS.md` "BI skill and tool packages".

    <any name>/                 a zip may hold this level or one folder around it
      aep-bi-package.json       the manifest; without it the contents are inferred
      skills/<name>.md          a skill revision file (frontmatter + instructions)
      tools/<name>.py           a single-file tool that reads INPUT and writes OUTPUT
      <any>.json                a schema file (owner 2026-11-20: one 匯入 for schema,
                                skills and tools), installed as its id@version

Import is preview first, then apply in batches of `BATCH`: each item is staged with the
same calls the page uses (`vault.save_skill`, `vault.save_tool`) into the current working
domain only, as uncommitted vault changes a person commits, pushes or discards. Nothing in a
package is run or sent to a model here: a tool is only parsed (`ast`), a skill only read.
A command-line script that does not follow the INPUT/OUTPUT contract is imported with
`needs_rewrite` (「需改寫」), kept but not runnable until a rewritten revision replaces it.

What was uploaded is kept outside the vault folder, under the vault's local folder, for
`TOKEN_SECONDS`; every apply re-reads the vault, so an item already staged reads as the
same and is never staged twice.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import re
import shutil
import stat
import sys
import time
import uuid
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from aep_bi.cards import catalog, homes, tool_runs, tool_session, vault, vault_tools
from aep_bi.cards.store import BiStoreError, now
from knowledge.repo import repository as repo_engine
from knowledge.repo import skills as repo_skills
from knowledge.repo.repository import RepoError

FORMAT = "aep.bi.package/v1"
MANIFEST = "aep-bi-package.json"
README = "README.md"
SKILLS = "skills"
TOOLS = "tools"
#: Limits (design §4). A zip as uploaded; everything unpacked; files and items in it.
MAX_ZIP_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_FILES = 200
MAX_ITEMS = 100
#: A zip member may unpack to at most this many times its packed size, once it is larger
#: than `RATIO_FROM` (a small, very regular file such as an empty README packs well too).
MAX_RATIO = 100
RATIO_FROM = 64 * 1024
MAX_TEXT = vault_tools.MAX_TEXT
MAX_NAME = 60
BATCH = 10
TOKEN_SECONDS = 3600
IMPORTS_DIR = "package_imports"
READ_SUFFIXES = (".json", ".md", ".py", ".txt")
GUARD = "工具的沙箱是防止失誤，不是防範蓄意攻擊的邊界；只匯入你信任的來源的包。"

NEW, UPDATE, SAME, CONFLICT, INVALID = "new", "update", "same", "conflict", "invalid"
AS_NEW_REVISION, AS_RENAME = "new_revision", "rename"

_WINDOWS_RESERVED = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{n}" for n in range(1, 10)),
        *(f"lpt{n}" for n in range(1, 10)),
    }
)
_DRIVE = re.compile(r"^[A-Za-z]:")
_SKIPPED_PARTS = ("__MACOSX", "__pycache__")
#: What the tool sandbox refuses (`analyses.GUARD`): network, child processes, native code.
_BLOCKED_MODULES = frozenset(
    {"socket", "ssl", "subprocess", "ctypes", "urllib", "http", "ftplib", "smtplib",
     "multiprocessing", "requests", "httpx", "numpy", "pandas"}
)  # fmt: skip
_SANDBOX_EXTRA = frozenset({"openpyxl"})


def _refuse(message: str) -> BiStoreError:
    return BiStoreError("package_invalid", message)


# -- reading a package: names, limits and files -----------------------------------------


def path_problem(name: str) -> str | None:
    """Why a member name cannot be in a package; None when it can."""
    if not name or "\0" in name or "\\" in name:
        return "檔名含有反斜線或 NUL"
    if name.startswith("/") or _DRIVE.match(name) or ":" in name:
        return "檔名是絕對路徑或含有磁碟代號"
    parts = name.rstrip("/").split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "檔名含有 .. 或空的資料夾"
    for part in parts:
        if part.split(".")[0].lower() in _WINDOWS_RESERVED:
            return f"「{part}」是 Windows 保留的名稱"
    return None


@dataclass
class Unpacked:
    """A package's files, as `path → text` (None when not UTF-8), and what was left out."""

    files: dict[str, str | None] = field(default_factory=dict)
    skipped: list[dict[str, str]] = field(default_factory=list)


def _checked_names(names: Iterable[str]) -> None:
    seen: dict[str, str] = {}
    for name in names:
        problem = path_problem(name)
        if problem:
            raise _refuse(f"包裡的「{name}」不能匯入：{problem}")
        folded = name.casefold()
        if folded in seen and seen[folded] != name:
            raise _refuse(f"包裡的「{seen[folded]}」和「{name}」只差在大小寫")
        seen[folded] = name


def _strip_top(paths: list[str]) -> str:
    """The one folder around everything, when there is one (only one level is taken off)."""
    tops = {p.split("/", 1)[0] for p in paths}
    if len(tops) == 1 and all("/" in p for p in paths):
        return next(iter(tops)) + "/"
    return ""


def _left_out(path: str) -> str | None:
    parts = path.split("/")
    if any(part in _SKIPPED_PARTS or part.startswith(".") for part in parts):
        return "系統或隱藏檔"
    if PurePosixPath(path).suffix.lower() not in READ_SUFFIXES:
        return "不支援的檔案類型"
    return None


def _decoded(data: bytes) -> str | None:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def _collect(found: Mapping[str, bytes | str]) -> Unpacked:
    top = _strip_top(list(found))
    out = Unpacked()
    for raw_path in sorted(found):
        path = raw_path[len(top) :]
        reason = _left_out(path)
        if reason:
            out.skipped.append({"file": path, "reason": reason})
            continue
        content = found[raw_path]
        out.files[path] = _decoded(content) if isinstance(content, bytes) else content
    return out


def read_zip(data: bytes) -> Unpacked:
    """A zip's files after every structural check (design §4); refused as a whole when one
    fails: a bad name, a link, an encrypted member, or a size, count or ratio over a limit.
    Each member's header is checked before anything is unpacked."""
    if len(data) > MAX_ZIP_BYTES:
        raise _refuse(f"zip 太大（上限 {MAX_ZIP_BYTES // 1048576} MB）")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, ValueError):
        raise _refuse("這不是 zip 檔") from None
    with archive:
        members = archive.infolist()
        if len(members) > MAX_FILES:
            raise _refuse(f"zip 裡有 {len(members)} 個項目，上限 {MAX_FILES}")
        # `orig_filename` too: on Windows zipfile turns a backslash into `/` when reading.
        _checked_names(m.filename for m in members)
        _checked_names(m.orig_filename for m in members)
        total = 0
        for member in members:
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise _refuse(f"「{member.filename}」是捷徑（symlink），不能匯入")
            if member.flag_bits & 0x1:
                raise _refuse(f"「{member.filename}」有加密，不能匯入")
            total += member.file_size
            if total > MAX_TOTAL_BYTES:
                raise _refuse(f"解壓後超過 {MAX_TOTAL_BYTES // 1048576} MB")
            if member.file_size >= RATIO_FROM and member.file_size > MAX_RATIO * max(
                member.compress_size, 1
            ):
                raise _refuse(f"「{member.filename}」的壓縮比超過 {MAX_RATIO} 倍（疑似 zip bomb）")
        found: dict[str, bytes | str] = {}
        for member in members:
            if member.is_dir():
                continue
            if _left_out(member.filename) is not None:
                found[member.filename] = ""
                continue
            # The header may understate: read one byte more than it says and refuse that.
            with archive.open(member) as handle:
                content = handle.read(member.file_size + 1)
            if len(content) > member.file_size:
                raise _refuse(f"「{member.filename}」的大小和 zip 標頭不符")
            found[member.filename] = content
    return _collect(found)


def read_files(files: Any) -> Unpacked:
    """A folder the browser read, as `[{"path", "text"}]` (its own name first)."""
    if not isinstance(files, list) or not files:
        raise _refuse("資料夾裡沒有可以讀的檔案")
    if len(files) > MAX_FILES:
        raise _refuse(f"資料夾裡有 {len(files)} 個檔案，上限 {MAX_FILES}")
    found: dict[str, bytes | str] = {}
    total = 0
    for item in files:
        path = item.get("path") if isinstance(item, dict) else None
        text = item.get("text") if isinstance(item, dict) else None
        if not isinstance(path, str) or not isinstance(text, str):
            raise _refuse("每個檔案要有 path 和 text")
        total += len(text.encode("utf-8"))
        if total > MAX_TOTAL_BYTES:
            raise _refuse(f"資料夾超過 {MAX_TOTAL_BYTES // 1048576} MB")
        found[path] = text
    _checked_names(found)
    return _collect(found)


# -- what a package holds -----------------------------------------------------------------


@dataclass
class Entry:
    """One skill or tool of a package, before it is compared with the vault."""

    kind: str
    name: str
    file: str
    text: str | None
    description: str = ""
    problems: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.kind}:{self.name}"


def _slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")[:MAX_NAME]


def _name_problem(name: Any) -> str | None:
    if not isinstance(name, str) or homes.id_problem(name) or len(name) > MAX_NAME:
        return f"名稱只能用小寫英數字與 -（最多 {MAX_NAME} 個字）"
    return None


def _manifest(text: str | None) -> dict[str, Any]:
    try:
        document = json.loads(text or "")
    except ValueError:
        raise _refuse(f"{MANIFEST} 不是有效的 JSON") from None
    if not isinstance(document, dict) or document.get("format") != FORMAT:
        raise _refuse(f"{MANIFEST} 的 format 必須是 {FORMAT}")
    contents = document.get("contents")
    if not isinstance(contents, list):
        raise _refuse(f"{MANIFEST} 要有 contents 清單")
    if len(contents) > MAX_ITEMS:
        raise _refuse(f"包裡有 {len(contents)} 項，上限 {MAX_ITEMS}")
    return document


def _listed(document: Mapping[str, Any], unpacked: Unpacked) -> list[Entry]:
    entries: list[Entry] = []
    for given in document["contents"]:
        given = given if isinstance(given, dict) else {}
        kind, name, file = given.get("kind"), given.get("name"), given.get("file")
        entry = Entry(
            kind=str(kind or ""),
            name=str(name or ""),
            file=str(file or ""),
            text=None,
            description=" ".join(str(given.get("description") or "").split())[:300],
        )
        folder = {"skill": SKILLS, "tool": TOOLS}.get(entry.kind)
        suffix = {"skill": ".md", "tool": ".py"}.get(entry.kind)
        if folder is None:
            entry.kind = entry.kind or "?"
            entry.problems.append("kind 必須是 skill 或 tool")
        elif not entry.file.startswith(folder + "/") or not entry.file.endswith(str(suffix)):
            entry.problems.append(f"檔案必須是 {folder}/<名稱>{suffix}")
        elif entry.file not in unpacked.files:
            entry.problems.append(f"包裡沒有 {entry.file}")
        else:
            entry.text = unpacked.files[entry.file]
        problem = _name_problem(entry.name)
        if problem:
            entry.problems.append(problem)
        entries.append(entry)
    named = {e.file for e in entries}
    for path in unpacked.files:
        if path.startswith((SKILLS + "/", TOOLS + "/")) and path not in named:
            unpacked.skipped.append({"file": path, "reason": f"沒有列在 {MANIFEST}"})
        elif path.endswith(".json") and path != MANIFEST:
            ref = _schema_ref(unpacked.files[path])
            if ref is not None:  # a schema file beside the manifest is imported too
                entries.append(Entry("schema", ref, path, unpacked.files[path]))
    return entries


def _looks_like_skill(text: str | None) -> bool:
    if text is None or not text.lstrip("﻿").startswith("---"):
        return False
    try:
        repo_skills.parse_skill(text, layout=homes.LAYOUT)
    except RepoError:
        # A frontmatter that names a role is meant as a skill; its problems are shown.
        return re.search(r"^role\s*:", text, re.MULTILINE) is not None
    return True


def _schema_ref(text: str | None) -> str | None:
    """`<id>@<version>` of a schema file; None for any other JSON."""
    try:
        document = json.loads(text or "")
    except ValueError:
        return None
    if not isinstance(document, dict) or not isinstance(document.get("types"), (dict, list)):
        return None
    schema_id, version = document.get("schema_id"), document.get("version")
    if not isinstance(schema_id, str) or not isinstance(version, str):
        return None
    return f"{schema_id}@{version}"


def _inferred(unpacked: Unpacked) -> list[Entry]:
    """Without a manifest (owner: inferred, then confirmed in the preview): a `.py` is a
    tool and a `.md` with a skill's frontmatter a skill, named after the file."""
    entries: list[Entry] = []
    for path, text in unpacked.files.items():
        stem = _slug(PurePosixPath(path).stem)
        if path.endswith(".py"):
            entries.append(Entry("tool", stem, path, text))
        elif path.endswith(".md") and _looks_like_skill(text):
            matched = re.search(r"^name\s*:\s*([a-z0-9-]+)\s*$", text or "", re.MULTILINE)
            entries.append(Entry("skill", matched.group(1) if matched else stem, path, text))
        elif path.endswith(".json") and (ref := _schema_ref(text)) is not None:
            entries.append(Entry("schema", ref, path, text))
        elif path != README:
            unpacked.skipped.append({"file": path, "reason": "不是判讀規則或工具"})
    if len(entries) > MAX_ITEMS:
        raise _refuse(f"包裡有 {len(entries)} 項，上限 {MAX_ITEMS}")
    return entries


def _entries(unpacked: Unpacked) -> tuple[list[Entry], dict[str, Any]]:
    """Every entry (duplicates marked) and what the package says about itself."""
    if MANIFEST in unpacked.files:
        document = _manifest(unpacked.files[MANIFEST])
        entries = _listed(document, unpacked)
        about = {
            "name": _slug(str(document.get("name") or "")) or "package",
            "version": str(document.get("version") or "")[:40],
            "description": str(document.get("description") or "")[:500],
            "schema": str(document.get("schema") or ""),
            "exported_from": document.get("exported_from")
            if isinstance(document.get("exported_from"), dict)
            else None,
            "inferred": False,
        }
    else:
        entries = _inferred(unpacked)
        about = {"name": "", "version": "", "description": "", "schema": "", "inferred": True}
    seen: set[str] = set()
    for entry in entries:
        if entry.id in seen:
            entry.problems.append("包裡已經有同名的項目")
        seen.add(entry.id)
    readme = unpacked.files.get(README)
    about["readme"] = (readme or "")[:2000]
    return entries, about


# -- comparing with the vault -----------------------------------------------------------


@dataclass
class Target:
    """The working domain an import goes into, read once per preview or batch."""

    workspace: Path
    vault: vault.Vault
    home: str
    units: dict[str, Any]
    pending: set[str]
    types: set[str]
    schema: str

    @classmethod
    def read(cls, workspace: Path, vault_id: str, home: Any) -> Target:
        problem = homes.home_problem(home)
        if problem:
            raise BiStoreError("home_invalid", "先選一個工作領域：包只匯入到目前的工作領域")
        target = vault._vault(workspace, vault_id)
        target._require_folder()
        reg = target._registry()
        units = target.repo.working_units()
        schema = units.get(repo_engine.SCHEMA_UNIT)
        return cls(
            workspace=workspace,
            vault=target,
            home=str(home),
            units=units,
            pending=set(target.repo._pending()["sets"]),
            types=set(reg.types),
            schema=str(schema.get("ref") if isinstance(schema, dict) else schema or ""),
        )


def _skill_digest(
    role: str, applies_to: Iterable[str], card_types: Iterable[str], body: str
) -> str:
    """What makes two skill revisions the same, whatever their revision, author or schema."""
    shape = {
        "role": role,
        "applies_to": [a.rstrip("/") for a in applies_to],
        "card_types": list(card_types),
        "body": body.strip("\n"),
    }
    return hashlib.sha256(repo_engine.canonical(shape).encode("utf-8")).hexdigest()


def _in_home(home: str, folder: str) -> str | None:
    """A package's home-relative folder in the target home; None when it names another."""
    folder = folder.strip().rstrip("/")
    if folder == homes.SOURCES or folder.startswith(homes.SOURCES + "/"):
        return f"{homes.home_dir(home)}/{folder}"
    if folder == homes.sources_dir(home) or folder.startswith(homes.sources_dir(home) + "/"):
        return folder
    return None


def _free_name(units: Mapping[str, Any], key_of: Any, name: str, suffix: str) -> str:
    base = f"{name}-{suffix}"[:MAX_NAME].rstrip("-")
    found, n = base, 2
    while key_of(found) in units:
        found = f"{base[: MAX_NAME - len(str(n)) - 1].rstrip('-')}-{n}"
        n += 1
    return found


def _item(entry: Entry, **values: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": entry.id,
        "kind": entry.kind,
        "name": entry.name,
        "file": entry.file,
        "description": entry.description,
        "status": NEW,
        "reasons": list(entry.problems),
        "warnings": [],
        "needs_rewrite": False,
        "action": None,
        "rename_to": None,
    }
    item.update(values)
    if item["reasons"]:
        item["status"] = INVALID
    item["default"] = item["status"] in (NEW, UPDATE)
    return item


def _plan_skill(target: Target, entry: Entry, package: str) -> tuple[dict[str, Any], Any]:
    """A skill's row, and what `vault.save_skill` is given for it."""
    if entry.problems or entry.text is None:
        return _item(entry, reasons=entry.problems or ["不是 UTF-8 文字檔"]), None
    try:
        parsed = repo_skills.parse_skill(entry.text, layout=homes.LAYOUT)
    except RepoError as failure:
        return _item(entry, reasons=[failure.message]), None
    reasons: list[str] = []
    warnings: list[str] = []
    if parsed.role != "extract":
        reasons.append("分類規則（classify）由 schema 產生、跨所有領域，不從包匯入")
    missing = [t for t in parsed.card_types if t not in target.types]
    if missing:
        reasons.append(f"這個知識庫的 schema 沒有這些卡片類型：{'、'.join(missing)}")
    folders: list[str] = []
    for folder in parsed.applies_to:
        placed = _in_home(target.home, folder)
        if placed is None:
            reasons.append(f"applies_to 的 {folder} 不在這個工作領域")
        else:
            folders.append(placed)
            if not (target.vault.folder / placed).is_dir():
                warnings.append(f"{placed} 這個資料夾還不存在，放進來源後才會用到這條規則")
    if parsed.table_recipes:
        warnings.append("table_recipes 不會匯入")
    if parsed.schema != target.schema:
        warnings.append(f"包是為 {parsed.schema} 寫的；匯入後綁到目前的 {target.schema}")
    if reasons:
        return _item(entry, reasons=reasons, warnings=warnings), None
    applies = folders or [homes.sources_dir(target.home)]
    digest = _skill_digest(parsed.role, applies, parsed.card_types, parsed.body)
    given = {
        "home": target.home,
        "name": entry.name,
        "role": parsed.role,
        "body": parsed.body,
        "applies_to": applies,
        "card_types": list(parsed.card_types),
    }
    key = repo_skills.skill_unit(f"{target.home}/{entry.name}")
    current = target.units.get(key)
    if not isinstance(current, dict):
        return _item(entry, warnings=warnings), given
    try:
        have = repo_skills.read_skill(
            target.vault.repo, f"{target.home}/{entry.name}", target.units
        )
    except RepoError:
        have = None
    if have is not None and digest == _skill_digest(
        have.role, have.applies_to, have.card_types, have.body
    ):
        return _item(entry, status=SAME, warnings=warnings), given
    revision = int(current.get("revision") or 0)
    if str(current.get("role") or "") != parsed.role:
        renamed = _free_name(
            target.units,
            lambda n: repo_skills.skill_unit(f"{target.home}/{n}"),
            entry.name,
            package,
        )
        why = f"這個領域的「{entry.name}」是{current.get('role')}規則，包裡的是{parsed.role}規則"
        return _item(
            entry,
            status=CONFLICT,
            warnings=[why, *warnings],
            action=AS_RENAME,
            rename_to=renamed,
            revision=revision,
        ), given
    if key in target.pending:
        why = f"「{entry.name}」在這台電腦有還沒 commit 的改動"
        return _item(
            entry,
            status=CONFLICT,
            warnings=[why, *warnings],
            action=AS_NEW_REVISION,
            revision=revision,
        ), given
    return _item(entry, status=UPDATE, warnings=warnings, revision=revision), given


def _module_names(tree: ast.AST) -> tuple[set[str], bool]:
    """The top-level modules a tool imports, and whether it imports from its own package."""
    names: set[str] = set()
    relative = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative = True
            elif node.module:
                names.add(node.module.split(".")[0])
    return names, relative


def _uses_command_line(tree: ast.AST, modules: set[str]) -> bool:
    if "argparse" in modules or "click" in modules or "typer" in modules:
        return True
    return any(
        isinstance(node, ast.Attribute)
        and node.attr == "argv"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
        for node in ast.walk(tree)
    )


def tool_check(text: str, siblings: Iterable[str] = ()) -> dict[str, Any]:
    """A tool's static check (nothing runs): why it cannot be imported (`reasons`), why it
    needs a rewrite before it can run (`rewrite`), and what will fail in the sandbox."""
    if len(text) > MAX_TEXT:
        return {"reasons": [f"程式最多 {MAX_TEXT} 字"], "rewrite": [], "warnings": []}
    if not text.strip():
        return {"reasons": ["程式是空的"], "rewrite": [], "warnings": []}
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return {
            "reasons": [f"無法編譯：第 {error.lineno} 行 {error.msg}"],
            "rewrite": [],
            "warnings": [],
        }
    modules, relative = _module_names(tree)
    rewrite: list[str] = []
    if _uses_command_line(tree, modules):
        rewrite.append("這是命令列腳本（argparse／sys.argv），要改寫成讀 INPUT、寫到 OUTPUT")
    if tool_session.check_code(text):
        rewrite.append("沒有用 INPUT 和 OUTPUT：工具讀 INPUT 這個檔，把 .csv 或 .md 寫到 OUTPUT")
    warnings: list[str] = []
    own = sorted(m for m in modules if m in set(siblings))
    if own or relative:
        warnings.append(
            "用到同一包的其他模組"
            + (f"（{'、'.join(own)}）" if own else "")
            + "：工具只支援單檔，執行會失敗"
        )
    blocked = sorted(m for m in modules if m in _BLOCKED_MODULES)
    if blocked:
        warnings.append(f"沙箱擋網路、子程序和原生函式庫：{'、'.join(blocked)} 執行會失敗")
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    absent = sorted(
        m
        for m in modules
        if m not in stdlib
        and m not in _SANDBOX_EXTRA
        and m not in _BLOCKED_MODULES
        and m not in own
        and m != "__future__"
    )
    if absent:
        warnings.append(f"沙箱沒有 {'、'.join(absent)}，執行會失敗")
    return {"reasons": [], "rewrite": rewrite, "warnings": warnings}


def _plan_tool(target: Target, entry: Entry, siblings: set[str]) -> tuple[dict[str, Any], Any]:
    """A tool's row, and what `vault.save_tool` is given for it."""
    if entry.problems or entry.text is None:
        return _item(entry, reasons=entry.problems or ["不是 UTF-8 文字檔"]), None
    checked = tool_check(entry.text, siblings - {PurePosixPath(entry.file).stem})
    if checked["reasons"]:
        return _item(entry, reasons=checked["reasons"]), None
    description = vault_tools.description_of(entry.text) or entry.description
    rewrite = checked["rewrite"]
    given = {
        "home": target.home,
        "name": entry.name,
        "suffix": ".py",
        "text": entry.text,
        "description": description,
        "needs_rewrite": bool(rewrite),
    }
    values: dict[str, Any] = {
        "description": description,
        "warnings": [*rewrite, *checked["warnings"]],
        "needs_rewrite": bool(rewrite),
    }
    key = vault_tools.unit_key(target.home, entry.name)
    current = target.units.get(key)
    if not isinstance(current, dict):
        return _item(entry, **values), given
    revision = int(current.get("revision") or 0)
    if current.get("sha256") == hashlib.sha256(entry.text.encode()).hexdigest():
        return _item(entry, status=SAME, revision=revision, **values), given
    if key in target.pending:
        why = f"「{entry.name}」在這台電腦有還沒 commit 的改動"
        values["warnings"] = [why, *values["warnings"]]
        return _item(
            entry, status=CONFLICT, action=AS_NEW_REVISION, revision=revision, **values
        ), given
    return _item(entry, status=UPDATE, revision=revision, **values), given


def _plan_schema(target: Target, entry: Entry) -> tuple[dict[str, Any], Any]:
    """A schema file's row: checked as 安裝 schema checks it, installed on apply as its
    id@version (an installed version is never changed), and offered as an upgrade."""
    document = json.loads(entry.text or "")
    _clean, errors = catalog.validate(document)
    if errors:
        reasons = [f"{e.get('path') or '$'}：{e.get('message')}" for e in errors[:5]]
        return _item(entry, reasons=reasons), None
    staged = {"filename": PurePosixPath(entry.file).name, "json_text": entry.text}
    known = next((r for r in catalog.available(target.workspace) if r.ref == entry.name), None)
    if known is not None:
        return _item(entry, status=SAME), staged
    warnings = []
    if target.schema.split("@", 1)[0] == entry.name.split("@", 1)[0]:
        warnings.append("安裝後，步驟 2 的「可以升級到的版本」會列出它")
    return _item(entry, warnings=warnings), staged


def _plan(target: Target, unpacked: Unpacked, package: str) -> list[tuple[dict[str, Any], Any]]:
    entries, _about = _entries(unpacked)
    siblings = {PurePosixPath(p).stem for p in unpacked.files if p.endswith(".py")}
    planned = []
    for entry in entries:
        if entry.kind == "skill":
            planned.append(_plan_skill(target, entry, package))
        elif entry.kind == "tool":
            planned.append(_plan_tool(target, entry, siblings))
        elif entry.kind == "schema":
            planned.append(_plan_schema(target, entry))
        else:
            planned.append((_item(entry), None))
    return planned


# -- the uploaded package, kept for an hour ------------------------------------------------


def _imports_dir(workspace: Path, vault_id: str) -> Path:
    return vault.local_dir(workspace, vault_id) / IMPORTS_DIR


def _expire(workspace: Path, vault_id: str) -> None:
    root = _imports_dir(workspace, vault_id)
    if not root.is_dir():
        return
    for folder in root.iterdir():
        try:
            old = time.time() - folder.stat().st_mtime > TOKEN_SECONDS
        except OSError:
            continue
        if old:
            shutil.rmtree(folder, ignore_errors=True)


def _token_dir(workspace: Path, vault_id: str, token: Any) -> Path:
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{24}", token):
        raise BiStoreError("package_expired", "這次預覽已經過期，請重新選包")
    folder = _imports_dir(workspace, vault_id) / token
    if not (folder / "package.json").is_file():
        raise BiStoreError("package_expired", "這次預覽已經過期（超過一小時或已放棄），請重新選包")
    return folder


def _stored(workspace: Path, vault_id: str, token: Any) -> tuple[Path, dict[str, Any]]:
    folder = _token_dir(workspace, vault_id, token)
    kept = json.loads((folder / "package.json").read_text(encoding="utf-8"))
    if time.time() - float(kept.get("created") or 0) > TOKEN_SECONDS:
        shutil.rmtree(folder, ignore_errors=True)
        raise BiStoreError("package_expired", "這次預覽已經過期（超過一小時），請重新選包")
    return folder, kept


def _preview_of(
    workspace: Path, vault_id: str, token: str, kept: Mapping[str, Any]
) -> dict[str, Any]:
    unpacked = Unpacked(files=dict(kept["files"]), skipped=list(kept["skipped"]))
    target = Target.read(workspace, vault_id, kept["home"])
    _entries_, about = _entries(Unpacked(files=dict(kept["files"]), skipped=[]))
    package = about["name"] or kept.get("fallback") or "import"
    items = [row for row, _ in _plan(target, unpacked, package)]
    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    counts["needs_rewrite"] = sum(1 for i in items if i["needs_rewrite"])
    label = next(
        (d["label"] for d in vault._working_domains(target.vault, target.units)
         if d["home"] == target.home),
        target.home,
    )  # fmt: skip
    return {
        "format": FORMAT,
        "token": token,
        "home": target.home,
        "home_label": label,
        "package": {**about, "name": package},
        "items": items,
        "skipped": unpacked.skipped,
        "counts": counts,
        "batch": BATCH,
        "guard": GUARD,
        "expires_in": TOKEN_SECONDS,
    }


def preview(
    workspace: Path, vault_id: str, home: Any, unpacked: Unpacked, fallback: str = ""
) -> dict[str, Any]:
    """Keep what was uploaded and say what importing it into `home` would do; nothing in
    the vault changes."""
    Target.read(workspace, vault_id, home)  # the domain is checked before anything is kept
    _entries(Unpacked(files=dict(unpacked.files), skipped=[]))  # a bad manifest is refused now
    _expire(workspace, vault_id)
    token = uuid.uuid4().hex[:24]
    folder = _imports_dir(workspace, vault_id) / token
    folder.mkdir(parents=True)
    kept = {
        "home": home,
        "created": time.time(),
        "fallback": _slug(fallback),
        "files": unpacked.files,
        "skipped": unpacked.skipped,
    }
    (folder / "package.json").write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
    return _preview_of(workspace, vault_id, token, kept)


def preview_zip(
    workspace: Path, vault_id: str, home: Any, data: bytes, name: str = ""
) -> dict[str, Any]:
    return preview(workspace, vault_id, home, read_zip(data), PurePosixPath(name).stem)


def _applied(folder: Path) -> dict[str, Any]:
    try:
        found = json.loads((folder / "applied.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def apply_batch(workspace: Path, vault_id: str, given: Mapping[str, Any]) -> dict[str, Any]:
    """Stage up to `BATCH` items of a previewed package (`token`, `items: [{"id", "as"}]`).
    Each item is compared with the vault again first, so one staged before reads as the
    same, and a repeated batch changes nothing (at most once)."""
    wanted = given.get("items")
    if not isinstance(wanted, list) or not wanted:
        raise BiStoreError("package_invalid", "沒有選要匯入的項目")
    if len(wanted) > BATCH:
        raise BiStoreError("package_invalid", f"一次最多匯入 {BATCH} 項")
    folder, kept = _stored(workspace, vault_id, given.get("token"))
    applied = _applied(folder)
    target = Target.read(workspace, vault_id, kept["home"])
    _entries_, about = _entries(Unpacked(files=dict(kept["files"]), skipped=[]))
    package = about["name"] or kept.get("fallback") or "import"
    planned = {
        row["id"]: (row, staged)
        for row, staged in _plan(target, Unpacked(files=dict(kept["files"])), package)
    }
    results = []
    for want in wanted:
        want = want if isinstance(want, dict) else {}
        item_id = str(want.get("id") or "")
        found = planned.get(item_id)
        if found is None:
            results.append({"id": item_id, "result": "failed", "message": "包裡沒有這一項"})
            continue
        row, staged = found
        if item_id in applied:
            results.append({"id": item_id, "result": "already", **applied[item_id]})
            continue
        if row["status"] == SAME:
            results.append({"id": item_id, "result": "same", "name": row["name"]})
            continue
        if row["status"] == INVALID or staged is None:
            results.append(
                {"id": item_id, "result": "failed", "message": "；".join(row["reasons"])}
            )
            continue
        choice = str(want.get("as") or row["action"] or AS_NEW_REVISION)
        if row["status"] == CONFLICT and want.get("as") not in (AS_NEW_REVISION, AS_RENAME):
            results.append(
                {
                    "id": item_id,
                    "result": "failed",
                    "message": "衝突的項目要選「存成新版本」或「改名匯入」",
                }
            )
            continue
        if choice == AS_RENAME:
            if row["rename_to"]:
                name = row["rename_to"]
            else:
                key_of = (
                    (lambda n: repo_skills.skill_unit(f"{target.home}/{n}"))
                    if row["kind"] == "skill"
                    else (lambda n: vault_tools.unit_key(target.home, n))
                )
                name = _free_name(target.units, key_of, row["name"], package)
            staged = {**staged, "name": name}
        try:
            if row["kind"] == "schema":
                installed = catalog.install(workspace, staged["filename"], staged["json_text"])
                saved = {"name": f"{installed['id']}@{installed['version']}", "revision": None}
            elif row["kind"] == "skill":
                saved = vault.save_skill(workspace, vault_id, staged)["skill"]
            else:
                saved = vault.save_tool(workspace, vault_id, staged)["tool"]
        except (BiStoreError, RepoError, catalog.SchemaInstallError) as failure:
            results.append({"id": item_id, "result": "failed", "message": failure.message})
            continue
        done = {"name": str(saved["name"]), "revision": saved["revision"], "at": now()}
        applied[item_id] = done
        (folder / "applied.json").write_text(
            json.dumps(applied, ensure_ascii=False), encoding="utf-8"
        )
        target.units = target.vault.repo.working_units()
        results.append({"id": item_id, "result": "staged", **done})
    return {"results": results, "status": target.vault.status()}


def discard(workspace: Path, vault_id: str, token: Any) -> dict[str, Any]:
    """Forget an uploaded package; what was already staged stays staged."""
    try:
        folder = _token_dir(workspace, vault_id, token)
    except BiStoreError:
        return {"discarded": False}
    shutil.rmtree(folder, ignore_errors=True)
    return {"discarded": True}


# -- export ------------------------------------------------------------------------------


def _relative(home: str, folder: str) -> str:
    base = homes.home_dir(home) + "/"
    return folder[len(base) :] if folder.startswith(base) else folder


def exportable(workspace: Path, vault_id: str, home: Any) -> list[dict[str, Any]]:
    """The working domain's current skills and tools, as export lists them."""
    target = Target.read(workspace, vault_id, home)
    prefix = f"{repo_engine.SKILL_UNIT_PREFIX}{target.home}/"
    found = []
    for key in sorted(target.units):
        value = target.units[key]
        if not isinstance(value, dict):
            continue
        if key.startswith(prefix):
            found.append(
                {
                    "id": f"skill:{key[len(prefix) :]}",
                    "kind": "skill",
                    "name": key[len(prefix) :],
                    "role": value.get("role"),
                    "revision": value.get("revision"),
                    "uncommitted": key in target.pending,
                }
            )
        elif key.startswith(vault_tools.unit_key(target.home, "")):
            name = key[len(vault_tools.unit_key(target.home, "")) :]
            if "/" in name:
                continue
            found.append(
                {
                    "id": f"tool:{name}",
                    "kind": "tool",
                    "name": name,
                    "revision": value.get("revision"),
                    "python": str(value.get("path") or "").endswith(".py"),
                    "uncommitted": key in target.pending,
                }
            )
    return found


def export_zip(workspace: Path, vault_id: str, home: Any, items: Any = None) -> bytes:
    """A zip of the working domain's skills and tools (all, or the `items` ids), with its
    manifest: `applies_to` without the home, each file's sha256 and revision."""
    target = Target.read(workspace, vault_id, home)
    chosen = exportable(workspace, vault_id, home)
    if items:
        wanted = set(items if isinstance(items, list) else str(items).split(","))
        chosen = [c for c in chosen if c["id"] in wanted]
    chosen = [c for c in chosen if c["kind"] == "skill" or c.get("python")]
    if not chosen:
        raise BiStoreError("package_empty", "這個工作領域沒有可以匯出的判讀規則或工具")
    contents: list[dict[str, Any]] = []
    files: dict[str, bytes] = {}
    for item in chosen:
        if item["kind"] == "skill":
            skill = repo_skills.read_skill(
                target.vault.repo, f"{target.home}/{item['name']}", target.units
            )
            relative = tuple(_relative(target.home, a) for a in skill.applies_to)
            text = repo_skills.render_skill(
                repo_skills.Skill(
                    name=skill.name,
                    revision=skill.revision,
                    schema=skill.schema,
                    role=skill.role,
                    applies_to=relative,
                    body=skill.body,
                    card_types=skill.card_types,
                    table_recipes=skill.table_recipes,
                )
            )
            data = text.encode("utf-8")
            path = f"{SKILLS}/{item['name']}.md"
            entry = {
                "kind": "skill",
                "name": item["name"],
                "file": path,
                "role": skill.role,
                "applies_to": list(relative),
                "card_types": list(skill.card_types),
            }
        else:
            value = target.units[vault_tools.unit_key(target.home, item["name"])]
            data = tool_runs._read_revision(target.vault.repo, value)
            path = f"{TOOLS}/{item['name']}.py"
            entry = {
                "kind": "tool",
                "name": item["name"],
                "file": path,
                "description": str(value.get("description") or ""),
            }
            if value.get("needs_rewrite") is True:
                entry["needs_rewrite"] = True
        files[path] = data
        contents.append(
            {
                **entry,
                "sha256": hashlib.sha256(data).hexdigest(),
                "from_revision": item["revision"],
                **({"uncommitted": True} if item["uncommitted"] else {}),
            }
        )
    manifest = {
        "format": FORMAT,
        "name": _slug(target.home.replace("/", "-")) or "package",
        "version": "1.0.0",
        "description": f"{target.home} 的判讀規則與資料處理工具",
        "schema": target.schema,
        "exported_from": {
            "vault": vault_id,
            "home": target.home,
            "commit": target.vault.repo.head(),
            "at": now(),
        },
        "contents": contents,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
        for path, data in files.items():
            archive.writestr(path, data)
    return buffer.getvalue()


def export_name(home: str) -> str:
    return f"aep-bi-{_slug(home.replace('/', '-')) or 'package'}.zip"
