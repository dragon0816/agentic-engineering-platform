"""The source loan tests as AEP's oracle: what changed, and nothing else.

rs_workflow_system@896046e8 `host-bridge/tests/test_loan_*.py` are vendored as
`tests/test_loan_*_source.py`. The only differences are the import paths (the
jobs are `capabilities.loan_reply.*` here), the source's `requests.ConnectionError`
for an unreachable Bridge (AEP has no HTTP Bridge and no `requests`; its
adapter raises the built-in `ConnectionError`) and a first line naming the
source. `tests/test_loan_reply_parity.py` rebuilds each vendored file from the
source clone with `REPLACEMENTS` and compares them text for text, so a test
cannot be weakened here without that comparison failing.
"""

from __future__ import annotations

from pathlib import Path

SOURCE_ROOT = Path(r"C:\Users\Chi_L\Documents\claude\n8n_workflow_system")
SOURCE_REVISION = "896046e8fe2170d21f9213e56e5ce2f93c05ba43"
TESTS = Path(__file__).resolve().parent

#: source test file -> vendored file
FILES = {
    "test_loan_rules.py": "test_loan_rules_source.py",
    "test_loan_queue.py": "test_loan_queue_source.py",
    "test_loan_templates.py": "test_loan_templates_source.py",
    "test_loan_scan_start.py": "test_loan_scan_start_source.py",
    "test_loan_process.py": "test_loan_process_source.py",
}

_IMPORTS = (
    ("from jobs import _loan_queue as q\n", "from capabilities.loan_reply import queue as q\n"),
    ("from jobs import _loan_rules as rules\n", "from capabilities.loan_reply import rules\n"),
    (
        "from jobs import _loan_templates as t\n",
        "from capabilities.loan_reply import templates as t\n",
    ),
    (
        "from jobs import loan_scan\n",
        "from capabilities.loan_reply import scan as loan_scan\n",
    ),
    (
        "from jobs.loan_scan import JobError\n",
        "from capabilities.loan_reply.scan import JobError\n",
    ),
    (
        "from jobs import edge_session, loan_process\n",
        "from capabilities.loan_reply import edge_session\n"
        "from capabilities.loan_reply import process as loan_process\n",
    ),
    (
        "from jobs._bridge_client import BridgeClientError\n",
        "from capabilities.loan_reply.bridge_api import BridgeClientError\n",
    ),
    ("import requests\n", ""),
    ("requests.ConnectionError(", "ConnectionError("),
)

#: (old, new) pairs applied in order, every occurrence.
REPLACEMENTS: dict[str, tuple[tuple[str, str], ...]] = {name: _IMPORTS for name in FILES}


def header(name: str) -> str:
    return (
        f"# Vendored oracle: rs_workflow_system@{SOURCE_REVISION[:8]} "
        f"host-bridge/tests/{name}; only tests/loan_oracle.py REPLACEMENTS differ.\n"
    )


def vendored(name: str, source_text: str) -> str:
    text = source_text.replace("\r\n", "\n")
    for old, new in REPLACEMENTS[name]:
        text = text.replace(old, new)
    return header(name) + text


def write_all() -> None:
    """Regenerate the vendored files from the source clone (run by hand)."""
    for name, target in FILES.items():
        source = (SOURCE_ROOT / "host-bridge" / "tests" / name).read_text(encoding="utf-8")
        (TESTS / target).write_text(vendored(name, source), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    write_all()
