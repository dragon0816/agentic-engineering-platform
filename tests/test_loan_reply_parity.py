"""Parity of the loan port with rs_workflow_system 06 / 06b.

1. The vendored oracle tests are the source tests apart from the declared
   replacements (tests/loan_oracle.py).
2. `rules`, `templates` and `queue` are the source modules apart from the
   replacements below; the browser-driving parts of `process` and the scan's
   configuration are the source's text.
3. The message texts shipped as data are the source's built-in text.
4. Normalised output: the same fake mailbox, portal and C4C through the source
   job and through the AEP steps give the same queue, the same dry-run plan and
   the same drafts.

Parts 1, 2 and 4 need the source clone and are skipped without it; nothing
here writes into it (its queue, stamp and screenshot folders are moved to
tmp_path, and its Edge start-up is stubbed as its own tests stub it).
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from loan_oracle import FILES, SOURCE_ROOT, TESTS, vendored

from capabilities.loan_reply import edge_session, handlers, process, queue, scan, templates
from capabilities.loan_reply.contracts import ReplyRequest, ScanRequest

JOBS = SOURCE_ROOT / "host-bridge" / "jobs"
PACKAGE = Path(__file__).resolve().parents[1] / "src" / "capabilities" / "loan_reply"
needs_source = pytest.mark.skipif(
    not (JOBS / "_loan_rules.py").is_file(), reason="the source clone is not on this machine"
)

#: source module -> (AEP module, replacements). Everything else is identical.
MODULES: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {
    "_loan_rules.py": (
        "rules.py",
        (
            (
                "from typing import Any, Iterable, Mapping\n",
                "from collections.abc import Iterable, Mapping\nfrom typing import Any\n",
            ),
            (
                "from jobs import _loan_templates as templates\n",
                "from capabilities.loan_reply import templates\n",
            ),
        ),
    ),
    "_loan_templates.py": (
        "templates.py",
        (
            (
                "from app.config import REPO_ROOT\n",
                "#: The folder relative override paths resolve against, and that ships the\n"
                "#: source installation's `config/loan-templates` files (AEP port).\n"
                "REPO_ROOT = Path(__file__).resolve().parent\n",
            ),
            (
                'DEFAULT_TEMPLATE_DIR = REPO_ROOT / "config" / "loan-templates"\n',
                'DEFAULT_TEMPLATE_DIR = REPO_ROOT / "loan-templates"\n',
            ),
        ),
    ),
    "_loan_queue.py": (
        "queue.py",
        (
            (
                "from typing import Any, Iterator, Mapping\n",
                "from collections.abc import Iterator, Mapping\nfrom typing import Any\n",
            ),
            (
                "from app.config import REPO_ROOT\n\n"
                'QUEUE_ROOT = REPO_ROOT / "state" / "loan-queue"\n',
                "#: The queue's folder. The AEP host passes its workspace folder on every call;\n"
                "#: this default is only for a caller that names none (AEP port).\n"
                'REPO_ROOT = Path.home() / ".aep-loan-reply"\n\n'
                'QUEUE_ROOT = REPO_ROOT / "state" / "loan-queue"\n',
            ),
            (
                '        return json.loads(path.read_text(encoding="utf-8"))\n',
                '        data = json.loads(path.read_text(encoding="utf-8"))\n'
                "        return data if isinstance(data, dict) else None\n",
            ),
            (
                "            import psutil\n\n            if not psutil.pid_exists(pid):\n",
                "            from capabilities.loan_reply.processes import pid_exists\n\n"
                "            if not pid_exists(pid):\n",
            ),
        ),
    ),
}

#: `process` names whose source text is unchanged: everything that drives the
#: two web systems and decides what a page says.
PROCESS_UNCHANGED = (
    "is_navigation_race",
    "_Page",
    "_Edge",
    "_suppress",
    "account_tile",
    "page_name",
    "read_loan_form",
    "open_accounts",
    "read_delivery_blocks",
    "_attachments",
    "load_config",
)
PROCESS_CONSTANTS = (
    "C4C_HOME",
    "DEFAULTS",
    "BUSY_JS",
    "URL_JS",
    "_NAVIGATION_RACE_MARKERS",
    "READ_FORM_FIELDS",
    "FIELD_CUSTOMER",
    "FIELD_EMAIL",
    "FIELD_BORROW_NO",
    "LOGIN_BUTTON",
    "FORM_PAGE",
    "LOGIN_PAGE",
    "ERROR_PAGE",
    "IDP_HOST",
    "ACCOUNT_TILE",
    "NAV_ATTEMPTS",
    "ACCOUNTS_READY",
    "RESULT_LINKS",
    "SCROLL_TO_BLOCKS",
    "READ_BLOCKS",
    "NAV_CUSTOMERS",
    "NAV_ACCOUNTS",
    "SEARCH_BUTTON",
    "SEARCH_FIELD",
    "FIRST_RESULT",
    "DETAILS_TAB",
    "REQUIRED_BRIDGE_METHODS",
)
SCAN_UNCHANGED = ("load_config",)
SCAN_CONSTANTS = ("DEFAULTS", "PARAMS_SCHEMA")


@pytest.fixture
def source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[types.SimpleNamespace]:
    """The source jobs, imported from the clone with their state in tmp_path."""
    # Read only: no bytecode is written next to the source jobs.
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.syspath_prepend(str(SOURCE_ROOT / "host-bridge"))
    for name in [key for key in sys.modules if key.split(".")[0] in ("jobs", "app")]:
        monkeypatch.delitem(sys.modules, name)
    if "requests" not in sys.modules and importlib.util.find_spec("requests") is None:
        # AEP has no `requests`; the source client imports it at module load.
        stub = types.ModuleType("requests")

        class RequestError(OSError):
            pass

        class ConnectionFailure(RequestError):
            pass

        stub.RequestException = RequestError  # type: ignore[attr-defined]
        stub.ConnectionError = ConnectionFailure  # type: ignore[attr-defined]
        stub.Session = object  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "requests", stub)
    import jobs._loan_queue as source_queue  # type: ignore[import-not-found]
    import jobs.loan_process as source_process  # type: ignore[import-not-found]
    import jobs.loan_scan as source_scan  # type: ignore[import-not-found]

    monkeypatch.setattr(source_queue, "QUEUE_ROOT", tmp_path / "source-queue")
    monkeypatch.setattr(source_process, "SHOT_DIR", tmp_path / "source-shots")
    for module in (source_process, process):
        monkeypatch.setattr(
            module.edge_session,
            "open_session",
            lambda *_a, **_k: {"leaseId": "lease"},
        )
        monkeypatch.setattr(module.edge_session, "close_session", lambda *_a, **_k: {})
        monkeypatch.setattr(module.edge_session, "release_lease", lambda *_a, **_k: (True, 0))
        monkeypatch.setattr(module.time, "sleep", lambda *_a: None)
    yield types.SimpleNamespace(queue=source_queue, scan=source_scan, process=source_process)


# -- 1 and 2: text ------------------------------------------------------------------


@needs_source
def test_the_vendored_tests_are_the_source_tests() -> None:
    for name, target in FILES.items():
        original = (SOURCE_ROOT / "host-bridge" / "tests" / name).read_text(encoding="utf-8")
        assert (TESTS / target).read_text(encoding="utf-8") == vendored(name, original), target


@needs_source
def test_rules_templates_and_queue_are_the_source_modules() -> None:
    for name, (target, replacements) in MODULES.items():
        expected = (JOBS / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        for old, new in replacements:
            assert expected.count(old) == 1, (name, old)
            expected = expected.replace(old, new)
        assert (PACKAGE / target).read_text(encoding="utf-8") == expected, target


@needs_source
def test_the_web_driving_and_configuration_are_the_source_text(
    source: types.SimpleNamespace,
) -> None:
    for name in PROCESS_UNCHANGED:
        mine = inspect.getsource(getattr(process, name))
        assert mine == inspect.getsource(getattr(source.process, name)), name
    for name in PROCESS_CONSTANTS:
        assert getattr(process, name) == getattr(source.process, name), name
    for name in SCAN_UNCHANGED:
        assert inspect.getsource(getattr(scan, name)) == inspect.getsource(
            getattr(source.scan, name)
        ), name
    for name in SCAN_CONSTANTS:
        assert getattr(scan, name) == getattr(source.scan, name), name
    assert edge_session.PROFILE_PORTS == {"c4c": 9222, "loan": 9223}


# -- 3: the message texts --------------------------------------------------------------


def test_the_shipped_texts_are_the_built_in_text() -> None:
    folder = PACKAGE / "loan-templates"
    for name, text in templates.DEFAULTS.items():
        assert (folder / f"{name}.txt").read_text(encoding="utf-8").rstrip("\n") == text, name
        assert templates.load(name)[1] == str(folder / f"{name}.txt")


@pytest.mark.skipif(
    not (SOURCE_ROOT / "config" / "loan-templates").is_dir(),
    reason="the source installation's template folder is not on this machine",
)
def test_the_shipped_texts_are_the_source_installations_files() -> None:
    for path in sorted((SOURCE_ROOT / "config" / "loan-templates").glob("*.txt")):
        mine = (PACKAGE / "loan-templates" / path.name).read_text(encoding="utf-8")
        assert mine == path.read_text(encoding="utf-8").replace("\r\n", "\n"), path.name


# -- 4: normalised output ---------------------------------------------------------------

PORTAL = "https://rstw-portal.rsint.net"
FORM_URL = f"{PORTAL}/FlowSingle.aspx?accessId=abc"


def _mail(borrow: str, notice: str = "簽核通知", entry: str = "") -> dict[str, Any]:
    href = f"{PORTAL}/FastView.aspx?action=flow&amp;accessId={borrow}"
    return {
        "entryId": entry or f"m-{borrow}",
        "subject": f"{notice}--(展示機出借申請單 - 一般 {borrow} )",
        "senderEmail": "workflow@rohde-schwarz.com",
        "receivedTime": "2026-08-01T09:00:00",
        "htmlBody": f'<a href="{href}">{borrow}</a>',
    }


MAILBOX = [
    _mail("DR26270135"),
    _mail("DRHQ26270004"),
    _mail("DRL26270065"),
    _mail("DRS26270011"),
    _mail("DR26270148", notice="否決"),
    _mail("DR26270135", entry="again"),
    {"entryId": "x", "subject": "Lunch", "htmlBody": "<p>hi</p>", "receivedTime": "2026-08-01T09"},
    {"entryId": "y", "subject": "no date", "htmlBody": ""},
]
CONFIG = {"processFrom": "2026-01-01 00:00", "excludeCategories": ["S"]}


class _Mailbox:
    def email_list(self, **_kw: Any) -> dict[str, Any]:
        return {"messages": [dict(item) for item in MAILBOX]}


def _mailbox() -> Any:
    return _Mailbox()


def _queue_files(root: Path) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {}
    for state in queue.STATES:
        rows = []
        for path in sorted((root / state).glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for key in ("enqueuedAt", "finishedAt"):
                data.pop(key, None)
            result = data.get("result")
            if isinstance(result, dict):
                for key in ("screenshot", "draft"):
                    result.pop(key, None)
            rows.append(data)
        found[state] = rows
    return found


@needs_source
def test_the_scan_queues_and_plans_what_the_source_job_does(
    source: types.SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(source.scan, "_bridge", lambda: _Mailbox())
    dry_source = source.scan.run({"_config": dict(CONFIG), "dryRun": True}, log=lambda _m: None)
    real_source = source.scan.run({"_config": dict(CONFIG), "dryRun": False}, log=lambda _m: None)

    root = tmp_path / "aep-queue"
    request = ScanRequest(process_from="2026-01-01 00:00", exclude_categories=("S",))
    plan = handlers.scan_mail(request.model_copy(update={"dry_run": True}), _mailbox, root)
    assert list(plan.candidates) == dry_source["enqueuedItems"]
    assert list(plan.skipped) == dry_source["skippedItems"]
    for key, mine in (
        ("notLoanForms", plan.not_loan_forms),
        ("undated", plan.undated),
        ("byCategory", plan.by_category),
        ("byNotice", plan.by_notice),
        ("loanForms", plan.loan_forms),
    ):
        assert mine == dry_source[key], key
    assert handlers.enqueue(plan, root).enqueued == ()  # a dry run writes nothing
    assert queue.counts(root)["pending"] == 0

    scanned = handlers.scan_mail(request, _mailbox, root)
    written = handlers.enqueue(scanned, root)
    assert list(written.enqueued) == [item["borrowNo"] for item in real_source["enqueuedItems"]]
    assert written.queue == real_source["queue"]
    assert _queue_files(root) == _queue_files(tmp_path / "source-queue")


def _source_fake(module: Any, **kw: Any) -> Any:
    from test_loan_process_source import FakeBridge

    maker: Any = FakeBridge
    return maker(**kw)


SCENARIOS: dict[str, dict[str, Any]] = {
    "shipping": {},
    "blocked": {"blocks": {"classificationDeliveryBlock": "Z1 Credit", "deliveryBlock": "01"}},
    "customer-not-found": {"rows": []},
    "fields-unreadable": {
        "blocks": {"classificationDeliveryBlock": None, "deliveryBlock": None},
    },
    "form-failed": {"fields": {"單據編號": "DR26270135"}},
}


def _mails(fake: Any) -> list[tuple[Any, ...]]:
    out: list[tuple[Any, ...]] = []
    for path, body in fake.calls:
        if path == "/email/reply":
            out.append(("reply", body["entryId"], body["body"], body["attachments"], body["send"]))
        elif path == "draft":
            out.append(
                (
                    "draft",
                    tuple(body["to"]),
                    body["subject"],
                    body["body"],
                    body.get("attachments", []),
                    body["send"],
                )
            )
    return out


@needs_source
@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
@pytest.mark.parametrize("dry_run", [False, True])
def test_the_reply_drafts_what_the_source_job_drafts(
    source: types.SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    dry_run: bool,
) -> None:
    item = {"borrowNo": "DR26270135", "loanUrl": FORM_URL, "entryId": "mail-1", "category": "一般"}
    config = {
        **source.process.DEFAULTS,
        "settleMs": 0,
        "busyTimeoutMs": 100,
        "alertRecipient": "ops@example.com",
    }

    source_root = tmp_path / "source-queue"
    source.queue.enqueue(dict(item), source_root)
    source_fake = _source_fake(source.process, **SCENARIOS[scenario])
    monkeypatch.setattr(source.process, "_bridge", lambda: source_fake)
    ran = source.process.run({"_config": config, "dryRun": dry_run}, log=lambda _m: None)

    root = tmp_path / "aep-queue"
    queue.enqueue(dict(item), root)
    aep_fake = _source_fake(process, **SCENARIOS[scenario])
    request = ReplyRequest(
        alert_recipient=("ops@example.com",),
        settle_ms=0,
        busy_timeout_ms=1000,
        dry_run=dry_run,
    )
    looked = handlers.look_up_all(request, lambda: aep_fake, root)
    drafts = handlers.draft_all(looked, lambda: aep_fake, root)
    result = handlers.offer_send(drafts, None)

    assert _mails(aep_fake) == _mails(source_fake)
    assert result.queue == ran["queue"]
    assert _queue_files(root) == _queue_files(source_root)
    finished = [look for look in looked.items if not look.error]
    failed = [look for look in looked.items if look.error]
    assert [(look.borrow_no, look.error) for look in failed] == [
        (entry["borrowNo"], entry["error"]) for entry in ran["failures"]
    ]
    if dry_run:
        assert [look.body for look in finished] == [entry["bodyPreview"] for entry in ran["items"]]
        assert [look.outcome for look in finished] == [entry["outcome"] for entry in ran["items"]]
    else:
        assert result.drafted == ran["processed"] and result.failed == ran["failed"]
