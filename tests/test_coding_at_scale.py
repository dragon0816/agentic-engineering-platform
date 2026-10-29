"""`coding/change` on a large file, two files and a declared check (CODING_AT_SCALE S3).

Real git worktree, real restricted pytest and a real module check: the model
(scripted) reads a 100 KB+ CRLF file in parts, changes it with exact edits and
creates a second declared file; a host-declared check fails the first version
and the repair passes it.
"""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows execution limits")

from test_coding_change_capability import BASE_PYTHON, SITE, TRACE  # noqa: E402
from test_coding_model_author import Replies  # noqa: E402
from test_coding_worktree_pytest import git, repository, requires_win32  # noqa: E402

from capabilities.coding_change.contracts import (  # noqa: E402
    CodingChangeRequest,
    CodingChangeStepInput,
    CodingHostBinding,
)
from capabilities.coding_change.handlers import CodingChangeHandler  # noqa: E402
from capabilities.runtime import CapabilityRefused  # noqa: E402

BIG = "src/calc/big.py"
UNITS = "src/calc/units.py"
NO_PRINT = (
    "import sys\n\n"
    "bad = [p for p in sys.argv[1:] if 'print(' in open(p, encoding='utf-8').read()]\n"
    "for p in bad:\n    print(f'{p}: print() is not allowed in driver code')\n"
    "sys.exit(1 if bad else 0)\n"
)


def large_repository(tmp_path: Path) -> Path:
    repo = repository(tmp_path)
    # The practice repository's unimplemented test is not this change's business.
    git("rm", "-q", "tests/test_double.py", cwd=repo)
    filler = "".join(f"def cmd_{i}() -> int:\n    return {i}\n\n\n" for i in range(3000))
    text = filler + "def scale() -> int:\n    return 1\n"
    (repo / BIG).write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert (repo / BIG).stat().st_size > 100_000
    (repo / "tests" / "test_big.py").write_text(
        "from calc.big import cmd_7, scale\n\n\n"
        "def test_scale():\n    assert scale() == 2 and cmd_7() == 7\n"
    )
    (repo / "tools").mkdir()
    (repo / "tools" / "no_print.py").write_text(NO_PRINT)
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "add", ".", cwd=repo)
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "big", cwd=repo)
    return repo


def handler(tmp_path: Path, model: Replies, **binding: Any) -> tuple[CodingChangeHandler, Path]:
    repo = large_repository(tmp_path)
    config = CodingHostBinding.model_validate(
        {
            "runner_python": BASE_PYTHON,
            "repositories": [
                {
                    "name": "wmt",
                    "path": str(repo),
                    "writable": ["src/**/*.py"],
                    "checks": [
                        {"name": "no-print", "module": "tools.no_print", "args": ["{files}"]}
                    ],
                }
            ],
            "timeout_seconds": 120,
            **binding,
        }
    )
    return CodingChangeHandler(
        config,
        tmp_path / "runs",
        model=model,
        model_alias="gateway",
        rule_present=lambda _python: True,
        extra_env=SITE,
    ), repo


def ask(**changes: Any) -> CodingChangeStepInput:
    request = {
        "repository": "wmt",
        "requirement": "scale() returns the factor from calc.units.",
        "file": BIG,
        "more_files": [UNITS],
        "tests": ["tests/test_big.py"],
        "max_repairs": 1,
        **changes,
    }
    return CodingChangeStepInput(request=CodingChangeRequest.model_validate(request))


def edit(*edits: tuple[str, str, str]) -> dict[str, Any]:
    return {
        "action": "edit",
        "edits": [{"path": path, "old": old, "new": new} for path, old, new in edits],
    }


@requires_win32
def test_a_large_file_and_a_new_file_change_together_and_a_declared_check_is_repaired(
    tmp_path: Path,
) -> None:
    model = Replies(
        {"summary": "Read the factor from units", "purpose": "scale uses FACTOR"},
        {"action": "search", "text": "def scale", "glob": "src/**/*.py"},
        {"action": "read", "path": BIG, "start": 12001, "end": 12002},
        edit(
            (
                BIG,
                "def scale() -> int:\n    return 1",
                "def scale() -> int:\n    from calc.units import FACTOR\n\n"
                "    print('scaling')\n    return FACTOR",
            ),
            (UNITS, "", "FACTOR = 2\n"),
        ),
        {"action": "done"},
        edit((BIG, "    print('scaling')\n", "")),
        {"action": "done"},
    )
    run, repo = handler(tmp_path, model)
    result = run.change(TRACE, ask())
    assert [(item.command, item.status) for item in result.commands] == [
        ("pytest-new", "passed"),
        ("check-no-print", "failed"),
        ("pytest-new", "passed"),
        ("check-no-print", "passed"),
        ("pytest-suite", "passed"),
    ]
    assert "print() is not allowed" in result.commands[1].failures[0]
    worktree = Path(result.worktree)
    big = (worktree / BIG).read_bytes()
    assert big.count(b"\r\n") == big.count(b"\n")  # still CRLF: no whole-file churn
    assert big.endswith(b"    from calc.units import FACTOR\r\n\r\n    return FACTOR\r\n")
    assert (worktree / UNITS).read_text() == "FACTOR = 2\n"
    changed = [line for line in result.diff.splitlines() if line[:1] in "+-"]
    assert len(changed) < 12 and "+FACTOR = 2" in result.diff
    # The search found the function in a 12,000-line file the prompt never carried.
    assert "src/calc/big.py:12001: def scale() -> int:" in model.requests[2].messages[-1].text
    evidence = json.loads(Path(result.evidence).read_text(encoding="utf-8"))
    assert evidence["result"]["status"] == "validated"
    assert git("status", "--porcelain", cwd=repo).strip() == ""  # the checkout is untouched


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"more_files": ["tests/test_big.py"]}, "coding_file_is_a_test"),
        ({"more_files": ["tools/no_print.py"]}, "coding_file_not_writable"),
        ({"more_files": ["../x.py"]}, "coding_path_invalid"),
    ],
)
def test_every_extra_file_is_checked_like_the_primary_one(
    tmp_path: Path, changes: dict[str, Any], code: str
) -> None:
    run, _ = handler(tmp_path, Replies())
    with pytest.raises(CapabilityRefused) as refused:
        run.change(TRACE, ask(**changes))
    assert refused.value.code == code


def test_check_names_are_unique() -> None:
    with pytest.raises(ValueError, match="check names must be unique"):
        CodingHostBinding.model_validate(
            {
                "runner_python": BASE_PYTHON,
                "repositories": [
                    {
                        "name": "wmt",
                        "path": "C:/wmt",
                        "writable": ["src/*.py"],
                        "checks": [
                            {"name": "lint", "module": "pylint"},
                            {"name": "lint", "module": "ruff"},
                        ],
                    }
                ],
            }
        )
