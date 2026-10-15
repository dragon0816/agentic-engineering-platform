"""Workflow 13 parity: the original job and AEP, same inputs, compared.

Each case gets two identical isolated roots (a copy of one seeded bare
`origin`, the inbox and the AEP marker). The original job runs in one, through
source_runner.py with the system Python. AEP's prepare, then commit, runs in
the other. Then the comparison covers:

- branch, branch state, versions, requirements, committed/pushed;
- the commit message;
- the committed tree, every path with its blob hash (or, for a dry run, the
  working copy status and every changed file's bytes).

Nothing is pushed, and no remote outside the isolated root is reachable: the
source runner refuses `git push` and any folder outside the root, and AEP's
settings accept only a local origin inside the marked root.

    .venv\\Scripts\\python.exe benchmarks\\w13_parity\\parity.py --run-id p001 \\
        --source C:\\Users\\Chi_L\\Documents\\claude\\n8n_workflow_system
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from capabilities.release_package.apply_isolated import (  # noqa: E402
    ISOLATED_MARKER,
    ISOLATED_MARKER_VALUE,
)
from capabilities.release_package.release_run import (  # noqa: E402
    ReleaseRunRequest,
    ReleaseRunSettings,
    commit_release,
    prepare_release,
)

SYSTEM_PYTHON = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312" / "python.exe"
)
FIXED = {
    "GIT_AUTHOR_NAME": "Parity",
    "GIT_AUTHOR_EMAIL": "parity@example.test",
    "GIT_COMMITTER_NAME": "Parity",
    "GIT_COMMITTER_EMAIL": "parity@example.test",
    "GIT_AUTHOR_DATE": "2026-10-08T10:00:00+08:00",
    "GIT_COMMITTER_DATE": "2026-10-08T10:00:00+08:00",
}
REPO = "rs-wmt-sw-release.git"

CASES: dict[str, dict[str, Any]] = {
    "new-branch": {
        "companyName": "Acme Labs",
        "chipsetId": "kt326",
        "info": "demo",
        "cmpKtOption": "KT160",
        "chipsetVersion": "2.0.17",
        "generalTestcaseVersion": "v3.0.17",
        "suffix": "X1",
        "notes": 'fixed the "throughput" plan `again`',
        "testPlans": ["throughput.json"],
        "configurations": ["lab.yaml"],
        "overlays": ["patch.txt"],
    },
    "existing-branch": {
        "companyName": "Foxconn",
        "chipsetId": "kt326",
        "cmpKtOption": "KT161",
        "chipsetVersion": "2.0.18",
        "generalTestcaseVersion": "3.0.18",
        "notes": "second release",
        "testPlans": ["throughput.json"],
    },
    "dry-run": {
        "companyName": "Foxconn",
        "chipsetId": "kt326",
        "cmpKtOption": "KT161",
        "chipsetVersion": "2.0.18",
        "generalTestcaseVersion": "3.0.18",
        "dryRun": True,
        "configurations": ["lab.yaml"],
    },
    "explicit-version": {
        "companyName": "Foxconn",
        "chipsetId": "kt326",
        "cmpKtOption": "KT161",
        "chipsetVersion": "2.0.18",
        "generalTestcaseVersion": "3.0.18",
        "releaseVersion": "1.2.3",
    },
}


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, **FIXED},
    ).stdout


def seed(base: Path) -> Path:
    """One bare origin: `template`, and `Foxconn_kt326` at VERSION 0.0.15."""
    work = base / "seed-work"
    work.mkdir(parents=True)
    git("init", "-q", "-b", "template", cwd=work)
    (work / "rswmt").mkdir()
    (work / "rswmt" / "base.py").write_text("print('base')\n", encoding="utf-8")
    (work / "README.md").write_text("release template\n", encoding="utf-8")
    git("add", "-A", cwd=work)
    git("commit", "-q", "-m", "template", cwd=work)
    git("checkout", "-q", "-b", "Foxconn_kt326", cwd=work)
    (work / "release.yaml").write_text("NAME: Foxconn_kt326\nVERSION: 0.0.15\n", encoding="utf-8")
    (work / "testplans").mkdir()
    (work / "testplans" / "old.json").write_text("{}", encoding="utf-8")
    git("add", "-A", cwd=work)
    git("commit", "-q", "-m", "earlier release", cwd=work)
    git("checkout", "-q", "template", cwd=work)
    bare = base / "seed.git"
    git("clone", "-q", "--bare", str(work), str(bare), cwd=base)
    return bare


def isolated_root(where: Path, bare: Path) -> Path:
    where.mkdir(parents=True)
    (where / ISOLATED_MARKER).write_text(ISOLATED_MARKER_VALUE, encoding="utf-8")
    shutil.copytree(bare, where / REPO)
    inbox = where / "inbox"
    inbox.mkdir()
    (inbox / "throughput.json").write_text('{"plan": "throughput", "loops": 3}\n', encoding="utf-8")
    (inbox / "lab.yaml").write_text("lab:\n  station: 7\n", encoding="utf-8")
    (inbox / "patch.txt").write_bytes(b"overlay\r\nbytes\n")
    return where


def snapshot(repo: Path, committed: bool) -> dict[str, Any]:
    if committed:
        return {
            "message": git("log", "-1", "--format=%B", cwd=repo),
            "tree": git("ls-tree", "-r", "HEAD", cwd=repo).splitlines(),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo).strip(),
        }
    status = sorted(git("status", "--porcelain", "-uall", cwd=repo).splitlines())
    files = {}
    for line in status:
        path = repo / line[3:]
        if path.is_file():
            files[line[3:]] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "status": status,
        "files": files,
        "branch": git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo).strip(),
        "head": git("log", "-1", "--format=%s", cwd=repo).strip(),
    }


def run_source(source: Path, root: Path, params: dict[str, Any], folder: Path) -> dict[str, Any]:
    job = {
        "root": str(root),
        "params": {
            **params,
            "push": False,
            # Forward slashes: the source takes the folder name after the last "/".
            "_git": {"releaseRepoUrl": (root / REPO).as_posix(), "templateBranch": "template"},
            "_paths": {"workRoot": str(root / "work"), "inbox": str(root / "inbox")},
            "_release": {},
            "_ops": {},
            "_artifactory": {},
        },
    }
    (folder / "source-job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    subprocess.run(
        [
            str(SYSTEM_PYTHON),
            str(HERE / "source_runner.py"),
            str(source),
            str(folder / "source-job.json"),
            str(folder / "source-result.json"),
        ],
        check=True,
        env={**os.environ, **FIXED},
        timeout=900,
    )
    return json.loads((folder / "source-result.json").read_text(encoding="utf-8"))


def run_aep(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    os.environ.update(FIXED)
    settings = ReleaseRunSettings(
        release_repo_url=(root / REPO).as_posix(),
        work_root=str(root / "work"),
        inbox_path=str(root / "inbox"),
        allowed_root=str(root),
    )
    prepared = prepare_release(settings, ReleaseRunRequest.model_validate(params))
    done = commit_release(settings, prepared.branch, prepared.fingerprint[:16])
    return {
        "prepared": json.loads(prepared.model_dump_json()),
        "commit": json.loads(done.model_dump_json()),
    }


def compare(
    case: str, source: dict[str, Any], aep: dict[str, Any], src_root: Path, aep_root: Path
) -> dict[str, Any]:
    if not source.get("ok"):
        return {"case": case, "match": False, "source_error": source.get("error")}
    s = source["result"]
    p = aep["prepared"]
    fields = {
        "branch": (s["branch"], p["branch"]),
        "branchState": (s["branchState"], p["branch_state"]),
        "chipsetVersion": (s["chipsetVersion"], p["chipset_version"]),
        "previousVersion": (s["previousVersion"], p["previous_version"]),
        "releaseVersion": (s["releaseVersion"], p["release_version"]),
        "requirements": (list(s["requirements"]), list(p["requirements"])),
        "changedFiles": (s["changedFiles"], p["changed_files"]),
        "committed": (s["committed"], aep["commit"]["committed"]),
        "pushed": (s["pushed"], aep["commit"]["pushed"]),
    }
    committed = bool(s["committed"])
    trees = (snapshot(Path(s["repoDir"]), committed), snapshot(Path(p["repo_dir"]), committed))
    fields["repository"] = trees
    mismatched = sorted(k for k, (a, b) in fields.items() if a != b)
    return {
        "case": case,
        "match": not mismatched,
        "mismatched": mismatched,
        "fields": {k: {"source": a, "aep": b} for k, (a, b) in fields.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    run = HERE / "runs" / args.run_id
    work = run / "work"
    if work.exists():
        # Git keeps its objects read-only.
        shutil.rmtree(work, onexc=lambda _, path, __: (os.chmod(path, 0o700), os.unlink(path)))
    work.mkdir(parents=True)
    revision = git("rev-parse", "HEAD", cwd=args.source).strip()
    bare = seed(work)
    results = []
    for case, params in CASES.items():
        folder = work / case
        src_root = isolated_root(folder / "source", bare)
        aep_root = isolated_root(folder / "aep", bare)
        source = run_source(args.source, src_root, params, folder)
        aep = run_aep(aep_root, params)
        outcome = compare(case, source, aep, src_root, aep_root)
        results.append(outcome)
        why = outcome.get("mismatched") or outcome.get("source_error")
        print(f"{case}: {'MATCH' if outcome['match'] else f'DIFF {why}'}", flush=True)
    report = {"source_revision": revision, "cases": results}
    (run / "results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if all(item["match"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
