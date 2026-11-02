"""Read-only checks before the owner-attended R6 session (`docs/runbooks/R6_MARKET_BI.md`).

Only asks whether files exist and how they are named: it never opens a file and
never writes, so it does not make OneDrive download or change anything. Exit code
0 when nothing failed, 1 otherwise.

    python scripts/r6_precheck.py --shared "<OneDrive>/BI_Knowledge" \
        --base <wireless> --base <robotics> --base <aerospace> --base <module> --base <aidc> \
        --wiki-copy "%LOCALAPPDATA%/AEP/rs-k-v1.0.3" --real-wiki "<RS_Knowledge>" \
        --wiki-target <folder for the new wiki repository> \
        --workspace <AEP workspace> --vault-id <the new vault's id>
"""

from __future__ import annotations

import argparse
import json
import stat
import sys
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

VAULT_NAME = "market-bi"
#: What the old folder is renamed to; the runbook's rollback renames it back.
OLD_NAME = "market-bi.v4-old"
BASES = 5
#: Windows: the file's content is not on this PC (a OneDrive placeholder).
CLOUD_ONLY = 0x00400000 | 0x00040000 | stat.FILE_ATTRIBUTE_OFFLINE


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # ok | warn | fail
    detail: str


def vault_format(folder: Path) -> str:
    """`repository`, `v4`, `empty` or `unknown`, from the names in the folder only."""
    if (folder / "repo.json").is_file():
        return "repository"
    if (folder / "vault.json").is_file() or (folder / "changes").is_dir():
        return "v4"
    return "empty" if not any(folder.iterdir()) else "unknown"


def cloud_only(folder: Path) -> int:
    """How many files under `folder` have their content only in the cloud."""
    count = 0
    for path in folder.rglob("*"):
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        if path.is_file() and attributes & CLOUD_ONLY:
            count += 1
    return count


def inside(path: Path, parent: Path) -> bool:
    return path.resolve() == parent.resolve() or parent.resolve() in path.resolve().parents


def check_shared(shared: Path) -> Iterator[Check]:
    if not shared.is_dir():
        yield Check("shared_folder", "fail", f"找不到 {shared}")
        return
    yield Check("shared_folder", "ok", str(shared))
    old = shared / VAULT_NAME
    if not old.is_dir():
        yield Check("old_vault", "warn", f"{old} 不存在，沒有舊資料夾要改名")
    else:
        found = vault_format(old)
        status = "ok" if found == "v4" else "fail"
        meaning = {
            "v4": "舊格式，要重建",
            "repository": "已經是新格式：這個 R6 可能已經做過，先確認再繼續",
            "empty": "是空資料夾，不是預期的舊知識庫",
            "unknown": "看不出格式，不要動它，先確認",
        }[found]
        yield Check("old_vault", status, f"{old}：{meaning}")
        missing = cloud_only(old)
        yield Check(
            "old_vault_on_this_pc",
            "warn" if missing else "ok",
            f"{missing} 個檔案只在雲端" if missing else "檔案都在這台電腦",
        )
    if (shared / OLD_NAME).exists():
        yield Check("rename_target", "fail", f"{shared / OLD_NAME} 已存在，舊資料夾無法改名")
    else:
        yield Check("rename_target", "ok", f"{OLD_NAME} 可用")


def check_workspace(workspace: Path, vault_id: str) -> Iterator[Check]:
    """Whether AEP on this PC would accept `vault_id` for a new vault: creating
    one refuses a name it already holds (`vault_exists`)."""
    if not workspace.is_dir():
        yield Check("workspace", "fail", f"找不到 {workspace}")
        return
    taken = [
        path
        for path in (
            workspace / "bi" / f"vault-{vault_id}",
            workspace / "bi" / "vaults" / vault_id,
        )
        if path.exists()
    ]
    if taken:
        where = "、".join(str(path) for path in taken)
        yield Check("vault_id_free", "fail", f"這台電腦已經有「{vault_id}」（{where}）：換一個 id")
    else:
        yield Check("vault_id_free", "ok", f"「{vault_id}」可以用")


def check_bases(bases: Sequence[Path]) -> Iterator[Check]:
    yield Check(
        "base_count",
        "ok" if len(bases) == BASES else "warn",
        f"給了 {len(bases)} 個知識庫，紀錄上是 {BASES} 個",
    )
    for base in bases:
        name = f"base:{base.name}"
        if not base.is_dir():
            yield Check(name, "fail", f"找不到 {base}")
            continue
        seeds = sum(1 for _ in base.rglob("*.csv"))
        reports = sum(1 for p in base.rglob("*") if p.suffix.lower() in {".pdf", ".docx", ".pptx"})
        pages = sum(1 for _ in base.rglob("*.md"))
        missing = cloud_only(base)
        problems = []
        if not pages:
            problems.append("沒有卡片（.md）")
        if not seeds and not reports:
            problems.append("沒有 seed CSV 也沒有報告原檔")
        if missing:
            problems.append(f"{missing} 個檔案只在雲端")
        yield Check(
            name,
            "warn" if problems else "ok",
            f"{pages} 頁、{seeds} 個 CSV、{reports} 個報告原檔"
            + (("：" + "、".join(problems)) if problems else ""),
        )


def check_wiki(copy: Path, real: Path | None, target: Path | None) -> Iterator[Check]:
    if not copy.is_dir():
        yield Check("wiki_copy", "fail", f"找不到 {copy}")
        return
    if not (copy / "index.md").is_file() and not (copy / "wiki").is_dir():
        yield Check("wiki_copy", "fail", f"{copy} 沒有 index.md 也沒有 wiki/，不是 wiki 資料夾")
    else:
        yield Check("wiki_copy", "ok", str(copy))
    if real is None:
        yield Check("wiki_copy_is_a_copy", "warn", "沒有給 --real-wiki，無法確認這不是正本")
    elif inside(copy, real):
        yield Check("wiki_copy_is_a_copy", "fail", f"{copy} 在正本 {real} 裡面：只能匯入副本")
    else:
        yield Check("wiki_copy_is_a_copy", "ok", f"不在正本 {real} 裡")
    if target is None:
        yield Check("wiki_target", "warn", "沒有給 --wiki-target，無法確認新知識庫的位置")
    elif not target.is_dir():
        yield Check("wiki_target", "fail", f"找不到 {target}")
    elif inside(target, copy) or (real is not None and inside(target, real)):
        yield Check("wiki_target", "fail", f"{target} 不能在被匯入的資料夾裡")
    else:
        yield Check("wiki_target", "ok", str(target))


def run(
    shared: Path,
    bases: Sequence[Path],
    wiki_copy: Path | None = None,
    real_wiki: Path | None = None,
    wiki_target: Path | None = None,
    workspace: Path | None = None,
    vault_id: str = VAULT_NAME,
) -> list[Check]:
    found = [*check_shared(shared), *check_bases(bases)]
    if workspace is not None:
        found.extend(check_workspace(workspace, vault_id))
    if wiki_copy is not None:
        found.extend(check_wiki(wiki_copy, real_wiki, wiki_target))
    return found


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shared", type=Path, required=True, help="the BI_Knowledge folder")
    parser.add_argument("--base", type=Path, action="append", default=[], help="one raw base")
    parser.add_argument("--wiki-copy", type=Path, help="the wiki folder to import a copy of")
    parser.add_argument("--real-wiki", type=Path, help="the real wiki, never to be imported")
    parser.add_argument("--wiki-target", type=Path, help="where the new wiki repository goes")
    parser.add_argument("--workspace", type=Path, help="this PC's AEP workspace (only looked at)")
    parser.add_argument("--vault-id", default=VAULT_NAME, help="the new vault's id")
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)
    found = run(
        args.shared,
        args.base,
        args.wiki_copy,
        args.real_wiki,
        args.wiki_target,
        args.workspace,
        args.vault_id,
    )
    if args.json:
        print(json.dumps([asdict(item) for item in found], ensure_ascii=False, indent=2))
    else:
        for item in found:
            print(f"[{item.status}] {item.name}: {item.detail}")
    return 1 if any(item.status == "fail" for item in found) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.exit(main())
