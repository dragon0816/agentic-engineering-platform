"""Running a home's tool on a source during ingest (`BI_CARD_MODEL.md` P2-a).

    raw source → tool → CSV or Markdown → a new source → the same preview and review

A tool's output is only ever a source in the same folder, with the raw source's
classification and `derived_from` on its unit, so cards still come only through a
preview and a person's review, and a withdrawal of the raw source takes it along.

A tool runs under the guard of `analyses.run_python`: its own process (`-I`, empty
environment, a time limit); an audit hook refuses network, child processes, native
libraries and writes outside the output folder. It may still read files. **That is
a guard against mistakes and stray model output, not a boundary against a determined
attacker**, which is why a person reads the code first: the first run of a revision
on a PC needs that person's approval of exactly that code (by hash, kept per PC).

The AI of a skill session may draft a tool and try an approved draft (`draft`,
`try_draft`), never approve one and never write a source. Saving a draft as a
revision is the person's, through `vault_tools`.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from capabilities.bi_cards import analyses, card_model, homes, vault, vault_sources, vault_tools
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStoreError, now

APPROVALS_FILE = "tool_approvals.json"
DRAFTS_FILE = "tool_drafts.json"
PYTHON = ".py"
TOOL_SECONDS = 300.0
OUTPUT_SUFFIXES = (".csv", ".md")
MAX_OUTPUT_FILES = 20
MAX_OUTPUT_BYTES = 50 * 1024 * 1024
MAX_PRINTED = 4000
MAX_TRIED_TEXT = 8000

RUNNER = (
    analyses.GUARD
    + r"""
# What a tool commonly needs, imported before the guard (shutil imports _winapi). numpy is
# kept out: openpyxl uses it when installed, and it loads ctypes, which a tool must not
# have (the guard refuses to start with it loaded).
sys.modules.setdefault("numpy", None)
import csv, datetime, decimal, io, math, pathlib, re, shutil, statistics, zipfile
import xml.etree.ElementTree
try:
    import openpyxl
except ImportError:
    pass
sys.dont_write_bytecode = True
INPUT = os.path.realpath(sys.argv[1])
OUTPUT = os.path.realpath("output")
code = compile(open("tool.py", encoding="utf-8").read(), "tool.py", "exec")
space = {"__name__": "__aep_tool__", "INPUT": INPUT, "OUTPUT": OUTPUT}
_install(OUTPUT, "a tool", DENIED_EVENTS + ("sqlite3.connect",))
del _install
exec(code, space)
"""
)


@dataclass(frozen=True)
class Output:
    name: str
    data: bytes


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute(code: bytes, source_file: Path, source_name: str, seconds: float = TOOL_SECONDS) -> Any:
    """Run a tool on a copy of a source: `(the files it wrote, what it printed)`."""
    with tempfile.TemporaryDirectory(prefix="aep-bi-tool-", ignore_cleanup_errors=True) as scratch:
        folder = Path(scratch)
        (folder / "output").mkdir()
        (folder / "input").mkdir()
        safe = vault_sources._UNSAFE.sub("_", source_name).strip(" .") or "source"
        shutil.copyfile(source_file, folder / "input" / safe)
        (folder / "tool.py").write_bytes(code)
        (folder / "runner.py").write_text(RUNNER, encoding="utf-8")
        try:
            done = subprocess.run(  # noqa: S603 (our interpreter, our runner, fixed arguments)
                [sys.executable, "-I", "runner.py", f"input/{safe}"],
                cwd=folder,
                env={"SYSTEMROOT": os.environ.get("SYSTEMROOT", ""), "PYTHONIOENCODING": "utf-8"},
                capture_output=True,
                timeout=seconds,
                stdin=subprocess.DEVNULL,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise BiStoreError("tool_failed", f"工具超過 {seconds:.0f} 秒，已停止") from None
        if done.returncode != 0:
            err = done.stderr.decode("utf-8", errors="replace").strip()
            last = err.splitlines()[-1] if err else f"結束碼 {done.returncode}"
            raise BiStoreError("tool_failed", f"工具沒有成功：{last}")
        printed = done.stdout.decode("utf-8", errors="replace")[-MAX_PRINTED:]
        return _outputs(folder / "output"), printed


def _outputs(folder: Path) -> list[Output]:
    files = sorted(p for p in folder.iterdir() if p.is_file() and not p.is_symlink())
    wrong = [p.name for p in files if p.suffix.lower() not in OUTPUT_SUFFIXES]
    if wrong:
        raise BiStoreError("tool_output_invalid", f"工具只能寫出 .csv 或 .md：{'、'.join(wrong)}")
    if not files:
        raise BiStoreError("tool_output_invalid", "工具沒有在 OUTPUT 寫出 .csv 或 .md")
    if len(files) > MAX_OUTPUT_FILES:
        raise BiStoreError("tool_output_invalid", f"工具最多寫出 {MAX_OUTPUT_FILES} 個檔案")
    if sum(p.stat().st_size for p in files) > MAX_OUTPUT_BYTES:
        raise BiStoreError("tool_output_invalid", "工具寫出的檔案太大（上限 50 MB）")
    if any(p.stat().st_size == 0 for p in files):
        raise BiStoreError("tool_output_invalid", "工具寫出了空檔案")
    return [Output(p.name, p.read_bytes()) for p in files]


# -- what this PC's person approved ----------------------------------------------------


def _local_json(workspace: Path, vault_id: str, name: str) -> dict[str, Any]:
    try:
        found = json.loads((vault.local_dir(workspace, vault_id) / name).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def _write_local_json(workspace: Path, vault_id: str, name: str, value: dict[str, Any]) -> None:
    path = vault.local_dir(workspace, vault_id) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def is_approved(workspace: Path, vault_id: str, sha256: str) -> bool:
    return sha256 in _local_json(workspace, vault_id, APPROVALS_FILE)


def _refuse_unapproved(workspace: Path, vault_id: str, sha256: str, label: str, code: str) -> None:
    if not is_approved(workspace, vault_id, sha256):
        raise BiStoreError(
            "tool_needs_approval",
            f"「{label}」這個版本還沒在這台電腦核准：請先看過程式碼再核准",
            sha256=sha256,
            code_text=code,
        )


# -- revisions and drafts ---------------------------------------------------------------


def _read_revision(repo: Any, value: Mapping[str, Any]) -> bytes:
    for root in (Path(repo.folder), Path(repo.work) / "files"):
        path = root / str(value["path"])
        if path.is_file():
            data = path.read_bytes()
            if _sha(data) == value["sha256"]:
                return data
    raise BiStoreError("tool_missing", f"讀不到 {value['path']}（OneDrive 是否還在同步？）")


def listing(workspace: Path, vault_id: str) -> dict[str, Any]:
    """Every current tool and waiting draft with its code, for a person to read."""
    target = vault._vault(workspace, vault_id)
    tools = []
    for item in vault_tools.current_tools(target.repo.working_units()):
        try:
            code = _read_revision(target.repo, item).decode("utf-8", errors="replace")
        except BiStoreError as failure:
            tools.append({**item, "problem": failure.message})
            continue
        approved = is_approved(workspace, vault_id, str(item["sha256"]))
        tools.append({**item, "code": code, "approved": approved})
    current = {str(t["sha256"]) for t in tools}
    drafts = [
        {**d, "approved": is_approved(workspace, vault_id, sha)}
        for sha, d in sorted(_local_json(workspace, vault_id, DRAFTS_FILE).items())
        if sha not in current
    ]
    return {"tools": tools, "drafts": drafts, "guard": "防止失誤，不是防範蓄意攻擊的邊界"}


def approve(workspace: Path, vault_id: str, given: Mapping[str, Any], actor: str) -> dict[str, Any]:
    """Only a person's confirm calls this. `sha256` must be code this PC can show,
    so what is approved is what was read."""
    if given.get("confirm") is not True:
        raise BiStoreError("confirm_required", "核准要由人按確認")
    sha256 = str(given.get("sha256") or "")
    known = listing(workspace, vault_id)
    found = next((t for t in [*known["tools"], *known["drafts"]] if t["sha256"] == sha256), None)
    if found is None:
        raise BiStoreError("tool_unknown", "沒有這份程式碼；重新整理後再看一次")
    approvals = _local_json(workspace, vault_id, APPROVALS_FILE)
    approvals[sha256] = {"name": found["name"], "by": actor, "at": now()}
    _write_local_json(workspace, vault_id, APPROVALS_FILE, approvals)
    return {"approved": sha256, "name": found["name"]}


def draft(workspace: Path, vault_id: str, given: Mapping[str, Any], actor: str) -> dict[str, Any]:
    """Keep a proposed tool on this PC for the person to read; nothing is staged."""
    home, name = str(given.get("home") or ""), str(given.get("name") or "")
    code = given.get("code")
    problem = homes.home_problem(home) or homes.id_problem(name)
    if problem or not isinstance(code, str) or not code.strip():
        raise BiStoreError("tool_invalid", "工具要有 home、name 和程式碼")
    if len(code) > vault_tools.MAX_TEXT:
        raise BiStoreError("tool_invalid", f"工具內容最多 {vault_tools.MAX_TEXT} 字")
    sha256 = _sha(code.encode())
    drafts = _local_json(workspace, vault_id, DRAFTS_FILE)
    drafts[sha256] = {
        "sha256": sha256,
        "name": f"{home}/{name}",
        "home": home,
        "tool": name,
        "code": code,
        "by": actor,
        "at": now(),
    }
    _write_local_json(workspace, vault_id, DRAFTS_FILE, drafts)
    return {
        "sha256": sha256,
        "name": f"{home}/{name}",
        "approved": is_approved(workspace, vault_id, sha256),
    }


def try_draft(workspace: Path, vault_id: str, sha256: str, source_id: str) -> dict[str, Any]:
    """Run an approved draft on a source. Its output is only shown; no source is kept."""
    found = _local_json(workspace, vault_id, DRAFTS_FILE).get(sha256)
    if not isinstance(found, dict):
        raise BiStoreError("tool_unknown", "沒有這份草稿")
    _refuse_unapproved(workspace, vault_id, sha256, str(found["name"]), str(found["code"]))
    target = vault._vault(workspace, vault_id)
    staging = Staging(workspace, target.dataset)
    source = staging.source(source_id)
    if source is None:
        raise BiStoreError("source_unknown", "找不到這個來源")
    outputs, printed = execute(
        str(found["code"]).encode(), staging.stored_file(source_id), source["name"]
    )
    return {
        "printed": printed,
        "files": [
            {
                "name": o.name,
                "bytes": len(o.data),
                "text": o.data.decode("utf-8", errors="replace")[:MAX_TRIED_TEXT],
            }
            for o in outputs
        ],
    }


# -- running a revision ------------------------------------------------------------------


def _keep_output(
    staging: Staging,
    target: Any,
    output: Output,
    raw: Mapping[str, Any],
    folder: str | None,
    provenance: Mapping[str, Any],
    actor: str,
) -> dict[str, Any]:
    kept = staging.add_source(
        output.name,
        content_base64=base64.b64encode(output.data).decode("ascii"),
        classification=raw["classification"],
        folder=folder,
        actor=actor,
    )
    key = vault_sources.unit_key(kept["sha256"])
    value = target.repo.working_units().get(key)
    if isinstance(value, dict) and "derived_from" not in value:
        target.repo.stage(key, {**value, "derived_from": dict(provenance)})
    return {"id": kept["id"], "name": kept["name"], "already": bool(kept.get("already"))}


def run(workspace: Path, vault_id: str, given: Mapping[str, Any], actor: str) -> dict[str, Any]:
    """Run the current revision of tool `name` on source `source_id`; its output becomes
    new sources, staged in the raw source's folder for the usual preview and review."""
    target = vault._vault(workspace, vault_id)
    name = str(given.get("name") or "")
    units = target.repo.working_units()
    value = units.get(f"{card_model.TOOL_PREFIX}{name}")
    if not isinstance(value, dict):
        raise BiStoreError("tool_unknown", f"沒有工具「{name}」")
    if not str(value["path"]).lower().endswith(PYTHON):
        raise BiStoreError("tool_not_python", "目前只能執行 Python 工具（.py）")
    code = _read_revision(target.repo, value)
    label = f"{name} 第 {value['revision']} 版"
    text = code.decode("utf-8", errors="replace")
    _refuse_unapproved(workspace, vault_id, str(value["sha256"]), label, text)
    staging = Staging(workspace, target.dataset)
    staging.store.refuse_write()
    source = staging.source(str(given.get("source_id") or ""))
    if source is None:
        raise BiStoreError("source_unknown", "找不到這個來源")
    outputs, printed = execute(code, staging.stored_file(source["id"]), source["name"])
    provenance = {
        "source": source["id"],
        "sha256": source["sha256"],
        "tool": name,
        "revision": value["revision"],
        "tool_sha256": value["sha256"],
    }
    folder = vault_sources.folder_of(units, source["sha256"])
    return {
        "sources": [
            _keep_output(staging, target, o, source, folder, provenance, actor) for o in outputs
        ],
        "printed": printed,
        "tool": {"name": name, "revision": value["revision"]},
    }
