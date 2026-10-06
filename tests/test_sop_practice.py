"""The SOP to Workflow practice target (SOP_TO_WORKFLOW W1)."""

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from evaluation.sop_practice import (
    HEADERS,
    SHEET_NAME,
    PracticeSite,
    write_sop_pdf,
    write_workbook,
)


def fetch(url: str, data: dict[str, str] | None = None) -> str:
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    with urllib.request.urlopen(url, data=body, timeout=10) as reply:
        return reply.read().decode("utf-8")


def test_the_site_searches_lists_and_records_a_notification() -> None:
    site = PracticeSite()
    site.start()
    try:
        assert "客戶代碼" in fetch(site.url + "/")
        listing = fetch(site.url + "/orders?customer=c001")
        assert listing.count("<tr>") == 5 and "SO-1004" in listing and "SO-2001" not in listing
        assert listing.count("標記已通知") == 2
        after = fetch(site.url + "/notify", {"order": "SO-1002"})
        assert after.count("標記已通知") == 1 and "已通知" in after
        assert json.loads(fetch(site.url + "/state.json")) == {"notified": ["SO-1002"]}
        assert "查無訂單" in fetch(site.url + "/orders?customer=C999")
    finally:
        site.close()


def test_the_workbook_holds_a_stale_and_an_unrelated_order(tmp_path: Path) -> None:
    from openpyxl import load_workbook

    sheet = load_workbook(write_workbook(tmp_path / "book.xlsx"))[SHEET_NAME]
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0] == (*HEADERS, "備註")
    assert [row[0] for row in rows[1:]] == ["SO-1001", "SO-0999"]


@pytest.mark.skipif(sys.platform != "win32", reason="prints with the installed Edge")
def test_the_sop_pdf_carries_the_routine_as_text(tmp_path: Path) -> None:
    from pypdf import PdfReader

    from integrations.browser import browser_path

    if browser_path() is None:
        pytest.skip("no Chromium browser installed")
    from capabilities.runtime import InstalledCapabilities
    from capabilities.workflow_author.handlers import DraftWorkflowHandler

    pdf = write_sop_pdf(tmp_path / "sop.pdf")
    raw = "".join(page.extract_text() or "" for page in PdfReader(pdf).pages)
    # Found here: Edge's PDF makes pypdf return 客⼾ (a Kangxi radical) for 客戶.
    assert "⼾" in raw and "客戶代碼" not in raw
    author = DraftWorkflowHandler(
        InstalledCapabilities(), model=None, model_alias="none", workspace_root=tmp_path
    )
    text = author._read_pdf(str(pdf))
    assert text is not None
    for phrase in ("客戶代碼", "出貨追蹤.xlsx", "標記已通知", "訂單號"):
        assert phrase in text, phrase

