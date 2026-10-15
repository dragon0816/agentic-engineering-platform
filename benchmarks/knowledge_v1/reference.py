"""Reference answers written by Claude Code from the Vault (owner 2026-10-09).

The owner asked for Claude Code to answer the coverage-selected questions first,
so the Harness + company LLM can be measured against those answers. Claude Code
runs headless with read-only tools (Read, Grep, Glob), inside the Vault folder
only. It must answer from the Vault, list the key points a correct answer has
to cover, and quote each source verbatim. This program then checks every quote
against the cited file, so an unsupported key point is marked, not trusted.

    .venv\\Scripts\\python.exe benchmarks\\knowledge_v1\\reference.py --ids Q0011,Q1001
    .venv\\Scripts\\python.exe benchmarks\\knowledge_v1\\reference.py --tier core
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import questions as Q  # noqa: E402

VAULT = Path(r"C:\Users\Chi_L\AppData\Local\AEP\rs-k")
OUT = HERE / "references"
TIMEOUT_SECONDS = 900

PROMPT = chr(10).join(
    (
        "You are writing a REFERENCE ANSWER for a benchmark question about the R&S Knowledge Vault in the current folder.",  # noqa: E501
        "Answer ONLY from files in this folder. Search with Grep and Glob, read with Read. Do not use outside knowledge.",  # noqa: E501
        "If the Vault does not contain enough evidence, say so (sufficient=false) and say what is missing.",  # noqa: E501
        "",
        "Question ({qid}): {question}",
        "",
        "Reply with ONE JSON object and nothing else:",
        '{{"answer": "a concise answer, 3-8 sentences, only what the Vault supports",',
        ' "key_points": [{{"point": "one fact a correct answer must contain",',
        '                  "source": "relative/path/inside/the/vault.md",',
        '                  "quote": "a short VERBATIM excerpt (10-200 characters) copied exactly from that file"}}],',  # noqa: E501
        ' "sufficient": true,',
        ' "missing": "what the Vault lacks, or empty"}}',
        "Give 2-8 key points. Every key point needs a source file and an exact quote.",
    )
)


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def verify(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each quote must appear in the cited Vault file (whitespace-insensitive)."""
    checked = []
    for point in points:
        source = str(point.get("source") or "")
        path = (VAULT / source).resolve()
        found = False
        if source and path.is_relative_to(VAULT.resolve()) and path.is_file():
            body = _normal(path.read_text(encoding="utf-8", errors="replace"))
            found = _normal(str(point.get("quote") or "")) in body
        checked.append({**point, "verified": found})
    return checked


def _json_object(text: str) -> dict[str, Any] | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def answer(question: dict[str, Any]) -> dict[str, Any]:
    claude = shutil.which("claude")
    if claude is None:
        raise SystemExit("claude is not on PATH")
    prompt = PROMPT.format(qid=question["id"], question=question["text"])
    started = time.monotonic()
    done = subprocess.run(
        [
            claude,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--allowedTools",
            "Read",
            "Grep",
            "Glob",
            "--disallowedTools",
            "Bash",
            "Edit",
            "Write",
            "WebFetch",
            "WebSearch",
            "--strict-mcp-config",
        ],
        cwd=VAULT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_SECONDS,
        stdin=subprocess.DEVNULL,
    )
    seconds = round(time.monotonic() - started, 1)
    try:
        envelope = json.loads(done.stdout)
    except ValueError:
        envelope = {"result": done.stdout, "is_error": True}
    body = _json_object(str(envelope.get("result") or "")) or {}
    points = verify(list(body.get("key_points") or []))
    return {
        "id": question["id"],
        "question": question["text"],
        "tags": {k: v for k, v in question.items() if k not in ("id", "text")},
        "answer": body.get("answer"),
        "sufficient": body.get("sufficient"),
        "missing": body.get("missing"),
        "key_points": points,
        "verified_points": sum(1 for p in points if p["verified"]),
        "author": "claude-code",
        "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seconds": seconds,
        "num_turns": envelope.get("num_turns"),
        "cost_usd_estimate": envelope.get("total_cost_usd"),
        "error": None if body else (str(envelope.get("result") or done.stderr)[:500]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", help="comma-separated question ids")
    parser.add_argument("--tier", choices=("core", "intents"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    bank = {q["id"]: q for q in Q.load()}
    if args.ids:
        wanted = [item.strip() for item in args.ids.split(",") if item.strip()]
    else:
        wanted = json.loads((HERE / "questions" / "coverage.json").read_text())[args.tier or "core"]
    OUT.mkdir(exist_ok=True)
    for qid in wanted:
        target = OUT / f"{qid}.json"
        if target.exists() and not args.force:
            print(f"{qid}: kept")
            continue
        record = answer(bank[qid])
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            f"{qid}: {record['verified_points']}/{len(record['key_points'])} points verified, "
            f"sufficient={record['sufficient']}, {record['seconds']} s, "
            f"{record['num_turns']} turns, ~${record['cost_usd_estimate']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
