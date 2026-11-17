"""BI vault phase V2 (`docs/phases/BI_VAULT.md` §5, owner 2026-10-28).

Every source is converted to Markdown when it is added (CSV/TSV/Excel to
tables, PDF/Word/PowerPoint to headings, paragraphs and tables, Markdown and
text as is), kept beside the untouched original and editable: each edit is a
new, immutable revision. Runs read the current revision and record it, so
evidence lines point into it. A PDF without text is refused (no OCR); a
missing converter library is a clear error.

All documents, notes and tables here are fictional fixtures built in the
test; every test uses a temporary workspace.
"""

from __future__ import annotations

import base64
import io
import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from test_bi_extract import Scripted

from aep_bi.cards import convert, readers
from aep_bi.cards.ai_runs import AiRuntime
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStoreError
from aep_bi.host.bi_cards_api import route

ACTOR = "tester"
TECH_CSV = (
    "技術,領域,成熟度,新增測試需求\n"
    "EtherCAT,robotics,mature,週期抖動;同步精度\n"
    "TSN,robotics,growth,時間同步(802.1AS)\n"
)


class Jobs:
    """Background work held until `run_all`, as a thread would run it later."""

    def __init__(self) -> None:
        self.pending: list[tuple[str, Callable[[], None]]] = []

    def __call__(self, title: str, work: Callable[[], None]) -> None:
        self.pending.append((title, work))

    def run_all(self) -> None:
        while self.pending:
            self.pending.pop(0)[1]()


def _call(
    tmp_path: Path, method: str, path: str, body: Any = None, ai: Any = None, **q: str
) -> Any:
    return route(tmp_path, ACTOR, method, path, q, body, None, ai)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _refused(answer: Any, status: int, code: str) -> dict[str, Any]:
    assert (answer[0], answer[1].get("code")) == (status, code), answer
    return dict(answer[1])


def _add(tmp_path: Path, name: str, *, text: str | None = None, data: bytes | None = None) -> Any:
    body: dict[str, Any] = {"dataset": "demo", "name": name}
    if data is not None:
        body["content_base64"] = base64.b64encode(data).decode("ascii")
    else:
        body["text"] = text
    return _call(tmp_path, "POST", "/api/bi/sources", body)


def _source(tmp_path: Path, name: str, **given: Any) -> dict[str, Any]:
    return dict(_ok(_add(tmp_path, name, **given))["source"])


def _markdown(tmp_path: Path, source_id: str, rev: int | None = None) -> dict[str, Any]:
    path = f"/api/bi/sources/{source_id}/markdown" + (f"/{rev}" if rev else "")
    return _ok(_call(tmp_path, "GET", path, dataset="demo"))


def _save(tmp_path: Path, source_id: str, markdown: str, base_rev: Any, note: str = "") -> Any:
    return _call(
        tmp_path,
        "POST",
        f"/api/bi/sources/{source_id}/markdown",
        {"dataset": "demo", "markdown": markdown, "base_rev": base_rev, "note": note},
    )


# -- fixtures (fictional) --------------------------------------------------------


def _docx() -> bytes:
    import docx

    document = docx.Document()
    document.add_heading("市場觀察（虛構範例）", level=1)
    document.add_paragraph("客戶 B 公司正在評估 Wi-Fi 7 的量產測試。")
    document.add_paragraph("第一個需求：多連結同步", style="List Bullet")
    document.add_paragraph("第二個需求：功耗", style="List Bullet")
    document.add_heading("規格", level=2)
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "項目"
    table.cell(0, 1).text = "數值"
    table.cell(1, 0).text = "頻寬"
    table.cell(1, 1).text = "320 MHz | 寬頻"
    document.add_paragraph("會後再確認。")
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def _pptx() -> bytes:
    import pptx
    from pptx.util import Inches

    deck = pptx.Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    assert slide.shapes.title is not None
    slide.shapes.title.text = "車用雷達（虛構範例）"
    body = slide.placeholders[1].text_frame
    body.text = "77 GHz 雷達模組需求上升"
    point = body.add_paragraph()
    point.text = "測試時間要縮短"
    point.level = 1
    shape = slide.shapes.add_table(2, 2, Inches(1), Inches(4), Inches(4), Inches(1))
    shape.table.cell(0, 0).text = "廠商"
    shape.table.cell(0, 1).text = "產品"
    shape.table.cell(1, 0).text = "虛構車電"
    shape.table.cell(1, 1).text = "雷達模組"
    notes = slide.notes_slide.notes_text_frame
    assert notes is not None
    notes.text = "講者備註：只是示範"
    out = io.BytesIO()
    deck.save(out)
    return out.getvalue()


def _pdf(lines: list[str]) -> bytes:
    """A one-page PDF with a text layer (ASCII, Helvetica), built by hand."""
    ops = ["BT", "/F1 12 Tf", "72 720 Td"]
    for line in lines:
        ops.append(f"({line}) Tj")
        ops.append("0 -16 Td")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out.getvalue()


def _blank_pdf() -> bytes:
    import pypdf

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _workbook() -> bytes:
    import openpyxl

    book = openpyxl.Workbook()
    first = book.active
    assert first is not None
    first.title = "Competitors"
    first.append(["廠商", "產品線"])
    first.append(["虛構量測", "網路分析儀|頻譜"])
    book.create_sheet("Empty")
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


# -- conversion ---------------------------------------------------------------


def test_tables_convert_to_markdown_that_reads_back_exactly() -> None:
    text = '名稱,說明\nA|B,"第一行\n第二行"\n,\nC:\\temp,x\n'
    markdown = convert.convert("notes.csv", text.encode("utf-8"))
    assert markdown.splitlines()[:3] == [
        "| 名稱 | 說明 |",
        "| --- | --- |",
        "| A\\|B | 第一行<br>第二行 |",
    ]
    (table,) = readers.markdown_tables(markdown, "notes.csv", exact=True)
    assert table["title"] == "notes.csv" and table["columns"] == ["名稱", "說明"]
    # The blank CSV row is left out, as the CSV reader leaves it out.
    assert [r["cells"] for r in table["rows"]] == [
        {"名稱": "A|B", "說明": "第一行\n第二行"},
        {"名稱": "C:\\temp", "說明": "x"},
    ]
    assert [r["row"] for r in table["rows"]] == [3, 4]
    tsv = convert.convert("t.tsv", b"a\tb\n1\t2\n")
    assert tsv == "| a | b |\n| --- | --- |\n| 1 | 2 |\n"


def test_excel_converts_to_one_table_per_sheet() -> None:
    markdown = convert.convert("study.xlsx", _workbook())
    assert markdown.splitlines() == [
        "## Competitors",
        "",
        "| 廠商 | 產品線 |",
        "| --- | --- |",
        "| 虛構量測 | 網路分析儀\\|頻譜 |",
        "",
        "## Empty",
        "",
        "（這個工作表是空的）",
    ]
    (table,) = readers.markdown_tables(markdown, "study.xlsx", exact=True)
    assert table["title"] == "Competitors"
    assert table["rows"] == [{"row": 5, "cells": {"廠商": "虛構量測", "產品線": "網路分析儀|頻譜"}}]


def test_word_converts_headings_paragraphs_lists_and_tables_in_order() -> None:
    markdown = convert.convert("market.docx", _docx())
    assert markdown.splitlines() == [
        "# 市場觀察（虛構範例）",
        "",
        "客戶 B 公司正在評估 Wi-Fi 7 的量產測試。",
        "",
        "- 第一個需求：多連結同步",
        "- 第二個需求：功耗",
        "",
        "## 規格",
        "",
        "| 項目 | 數值 |",
        "| --- | --- |",
        "| 頻寬 | 320 MHz \\| 寬頻 |",
        "",
        "會後再確認。",
    ]


def test_powerpoint_converts_slides_text_tables_and_notes() -> None:
    markdown = convert.convert("radar.pptx", _pptx())
    lines = markdown.splitlines()
    assert lines[0] == "## 投影片 1：車用雷達（虛構範例）"
    assert "77 GHz 雷達模組需求上升" in lines
    assert "- 測試時間要縮短" in lines
    assert "| 虛構車電 | 雷達模組 |" in lines
    assert lines[-1] == "講者備註：只是示範" and "### 備註" in lines


def test_a_pdf_with_text_converts_by_page_and_one_without_is_refused() -> None:
    markdown = convert.convert("brief.pdf", _pdf(["Fictional brief", "Demand for 6G FR3 tests"]))
    assert markdown.startswith("## 第 1 頁\n\n")
    assert "Fictional brief" in markdown and "Demand for 6G FR3 tests" in markdown
    with pytest.raises(BiStoreError) as caught:
        convert.convert("scan.pdf", _blank_pdf())
    assert caught.value.code == "source_no_text" and "OCR" in caught.value.message


def test_a_missing_converter_library_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "docx", None)
    with pytest.raises(BiStoreError) as caught:
        convert.convert("market.docx", b"PK")
    assert caught.value.code == "converter_missing" and "python-docx" in caught.value.message
    with pytest.raises(BiStoreError) as other:
        convert.convert("photo.png", b"\x89PNG")
    assert other.value.code == "file_type_unsupported"


# -- the sources API ------------------------------------------------------------


def test_documents_upload_as_base64_and_are_converted_when_added(tmp_path: Path) -> None:
    word = _source(tmp_path, "market.docx", data=_docx())
    deck = _source(tmp_path, "radar.pptx", data=_pptx())
    brief = _source(tmp_path, "brief.pdf", data=_pdf(["Fictional brief"]))
    for source in (word, deck, brief):
        assert source["parse"] == "text" and source["format"] == "document"
        assert source["markdown_rev"] == 1 and source["convert_error"] is None
    table = _source(tmp_path, "tech.csv", text=TECH_CSV)
    assert (table["format"], table["parse"], table["markdown_rev"]) == ("table", "table", 1)
    view = _markdown(tmp_path, word["id"])
    assert view["current_rev"] == 1 and view["markdown"].startswith("# 市場觀察")
    assert view["revision"]["origin"] == "conversion" and view["revision"]["by"] == "tester via web"
    assert view["revision"]["converter"] == convert.CONVERTER
    stored = tmp_path / "bi" / "demo" / "markdown" / word["id"] / "rev-1.md"
    assert stored.read_text(encoding="utf-8") == view["markdown"]


def test_a_pdf_without_text_is_refused_and_nothing_is_kept(tmp_path: Path) -> None:
    refused = _refused(_add(tmp_path, "scan.pdf", data=_blank_pdf()), 400, "source_no_text")
    assert "OCR" in refused["message"]
    assert _ok(_call(tmp_path, "GET", "/api/bi/sources", dataset="demo"))["sources"] == []
    assert not (tmp_path / "bi" / "demo" / "sources").exists()


def test_a_source_that_cannot_be_converted_is_kept_with_the_reason(tmp_path: Path) -> None:
    broken = _source(tmp_path, "deck.pptx", text="not a presentation")
    assert broken["markdown_rev"] == 0
    assert broken["convert_error"]["code"] == "source_parse_failed"
    _refused(
        _call(tmp_path, "GET", f"/api/bi/sources/{broken['id']}/markdown", dataset="demo"),
        400,
        "source_parse_failed",
    )
    # A person may type the Markdown instead: it becomes revision 1.
    saved = _ok(_save(tmp_path, broken["id"], "# 手動整理（虛構）\n\n重點一\n", 0, "手動整理"))
    assert saved["revision"]["rev"] == 1 and saved["revision"]["origin"] == "edit"
    assert saved["source"]["convert_error"] is None


# -- text sources in other encodings (a Big5 .md was read as garbage) --------

NOTE_ZH = "# 虛構會議紀錄\r\n\r\n電源模組 FACT-POWER-1 的效率。\r\n"
NOTE_MD = NOTE_ZH.replace("\r\n", "\n")


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("big5.md", NOTE_ZH.encode("cp950")),
        ("utf16-le.md", NOTE_ZH.encode("utf-16")),  # with its byte order mark
        ("utf16-be.markdown", b"\xfe\xff" + NOTE_ZH.encode("utf-16-be")),
        ("big5.txt", NOTE_ZH.encode("cp950")),
    ],
)
def test_a_text_source_in_big5_or_utf16_converts_to_its_characters(
    tmp_path: Path, name: str, data: bytes
) -> None:
    assert convert.convert(name, data) == NOTE_MD
    source = _source(tmp_path, name, data=data)
    assert source["markdown_rev"] == 1 and source["convert_error"] is None
    markdown = _markdown(tmp_path, source["id"])["markdown"]
    assert markdown == NOTE_MD and "�" not in markdown


def test_utf8_text_sources_convert_as_before(tmp_path: Path) -> None:
    for data in (NOTE_ZH.encode("utf-8"), b"\xef\xbb\xbf" + NOTE_ZH.encode("utf-8")):
        assert convert.convert("note.md", data) == NOTE_MD
    typed = _source(tmp_path, "typed.md", text=NOTE_ZH)
    assert _markdown(tmp_path, typed["id"])["markdown"] == NOTE_MD


def test_a_text_source_no_encoding_reads_is_kept_with_the_reason(tmp_path: Path) -> None:
    data = b"# \xff\xff\x81 \x80\n"
    with pytest.raises(BiStoreError) as refused:
        convert.convert("broken.md", data)
    assert refused.value.code == "source_decode_failed"
    with pytest.raises(BiStoreError) as rule_path:
        readers.decode(data)
    assert rule_path.value.code == refused.value.code  # the rule path's reason
    source = _source(tmp_path, "broken.md", data=data)
    assert source["markdown_rev"] == 0
    assert source["convert_error"]["code"] == "source_decode_failed"
    assert "�" not in str(source["convert_error"])
    _refused(
        _call(tmp_path, "GET", f"/api/bi/sources/{source['id']}/markdown", dataset="demo"),
        400,
        "source_decode_failed",
    )


def test_edits_are_new_revisions_and_the_original_never_changes(tmp_path: Path) -> None:
    source = _source(tmp_path, "tech.csv", text=TECH_CSV)
    original = tmp_path / "bi" / "demo" / "sources"
    before = {p.name: p.read_bytes() for p in original.iterdir()}
    first = _markdown(tmp_path, source["id"])
    edited = first["markdown"].replace("| TSN | robotics | growth |", "| TSN | robotics | mature |")
    saved = _ok(_save(tmp_path, source["id"], edited, 1, "TSN 已成熟"))
    assert saved["already"] is False and saved["current_rev"] == 2
    assert saved["revision"]["note"] == "TSN 已成熟" and saved["revision"]["by"] == "tester via web"
    assert saved["source"]["markdown_rev"] == 2
    again = _ok(_save(tmp_path, source["id"], edited, 2))
    assert again["already"] is True and again["current_rev"] == 2
    stale = _refused(_save(tmp_path, source["id"], edited + "\n多一行\n", 1), 409, "markdown_stale")
    assert stale["current_rev"] == 2
    view = _markdown(tmp_path, source["id"])
    assert view["current_rev"] == 2 and view["markdown"] == edited
    assert [r["rev"] for r in view["revisions"]] == [2, 1]
    assert [r["origin"] for r in view["revisions"]] == ["edit", "conversion"]
    assert _markdown(tmp_path, source["id"], 1)["markdown"] == first["markdown"]
    assert _markdown(tmp_path, source["id"], 1)["revision"]["rev"] == 1
    assert {p.name: p.read_bytes() for p in original.iterdir()} == before
    _refused(
        _call(tmp_path, "GET", f"/api/bi/sources/{source['id']}/markdown/9", dataset="demo"),
        404,
        "markdown_rev_unknown",
    )
    _refused(_save(tmp_path, source["id"], "  ", 2), 400, "markdown_missing")
    _refused(_save(tmp_path, source["id"], edited, None), 400, "base_rev_missing")
    _refused(_save(tmp_path, "nope", edited, 1), 404, "source_unknown")


# -- runs read the current revision ---------------------------------------------


def test_a_rule_run_reads_the_current_revision_and_records_it(tmp_path: Path) -> None:
    source = _source(tmp_path, "tech.csv", text=TECH_CSV)
    edited = "# 技術清單（人工整理，虛構）\n\n" + _markdown(tmp_path, source["id"])[
        "markdown"
    ].replace("| TSN | robotics | growth |", "| TSN | robotics | mature |")
    _ok(_save(tmp_path, source["id"], edited, 1))
    body = {"dataset": "demo", "kind": "trial", "source_id": source["id"]}
    run = _ok(_call(tmp_path, "POST", "/api/bi/runs", body))["run"]
    assert run["markdown_rev"] == 2
    detail = _ok(_call(tmp_path, "GET", f"/api/bi/runs/{run['id']}", dataset="demo"))
    tsn = next(c for c in detail["candidates"] if c["canonical_key"] == "TSN")
    maturity = next(f for f in tsn["fields"] if f["field"] == "maturity")
    assert maturity["value"] == "mature"
    # Line 6 of revision 2: heading, blank, header, separator, EtherCAT, TSN.
    assert maturity["evidence"][0]["locator"] == {"table": 0, "line": 6, "column": "成熟度"}
    assert edited.split("\n")[5].startswith("| TSN |")


def test_a_source_from_before_v2_is_converted_on_first_need(tmp_path: Path) -> None:
    source = _source(tmp_path, "tech.csv", text=TECH_CSV)
    staging = Staging(tmp_path, "demo")
    # As a source added before V2: no Markdown revision at all.
    connection = sqlite3.connect(staging.path)
    connection.execute("DELETE FROM markdown")
    connection.commit()
    connection.close()
    (tmp_path / "bi" / "demo" / "markdown" / source["id"] / "rev-1.md").unlink()
    assert staging.source(source["id"])["markdown_rev"] == 0  # type: ignore[index]
    body = {"dataset": "demo", "kind": "trial", "source_id": source["id"]}
    run = _ok(_call(tmp_path, "POST", "/api/bi/runs", body))["run"]
    assert run["markdown_rev"] == 1 and run["summary"]["create"] == 2
    revision = _markdown(tmp_path, source["id"])["revision"]
    assert revision["origin"] == "conversion" and revision["by"] == source["by"]


ANSWER = {
    "candidates": [
        {
            "entity_type": "Signal",
            "name": "B 公司評估 Wi-Fi 7",
            "fields": {
                "summary": {
                    "value": "客戶 B 公司正在評估 Wi-Fi 7 的量產測試",
                    "basis": "fact",
                    "quote": "客戶 B 公司正在評估 Wi-Fi 7 的量產測試",
                }
            },
            "links": [],
        }
    ],
    "notes": "",
}


def test_documents_go_to_the_ai_path_on_their_markdown(tmp_path: Path) -> None:
    jobs = Jobs()
    model = Scripted(ANSWER)
    ai = AiRuntime(model=lambda: (model, "test-model"), background=jobs)
    word = _source(tmp_path, "market.docx", data=_docx())
    body = {"dataset": "demo", "kind": "trial", "source_id": word["id"]}
    run = _ok(_call(tmp_path, "POST", "/api/bi/runs", body, ai))["run"]
    assert run["status"] == "extracting" and run["markdown_rev"] == 1
    jobs.run_all()
    sent = model.requests[0].messages[1].text
    assert "# 市場觀察（虛構範例）" in sent and "| 頻寬 | 320 MHz \\| 寬頻 |" in sent
    detail = _ok(_call(tmp_path, "GET", f"/api/bi/runs/{run['id']}", dataset="demo"))
    assert detail["run"]["status"] == "review"
    (signal,) = detail["candidates"]
    summary = next(f for f in signal["fields"] if f["field"] == "summary")
    # Line 3 of the Markdown revision the run read.
    assert summary["evidence"][0]["locator"] == {"line_start": 3, "line_end": 3}


def test_a_person_may_send_a_table_to_the_ai_path(tmp_path: Path) -> None:
    jobs = Jobs()
    model = Scripted({"candidates": [], "notes": ""})
    ai = AiRuntime(model=lambda: (model, "test-model"), background=jobs)
    table = _source(tmp_path, "tech.csv", text=TECH_CSV)
    body = {"dataset": "demo", "kind": "trial", "source_id": table["id"], "path": "ai"}
    run = _ok(_call(tmp_path, "POST", "/api/bi/runs", body, ai))["run"]
    assert run["method_ref"] == "llm:default" and run["markdown_rev"] == 1
    jobs.run_all()
    assert "| EtherCAT | robotics | mature |" in model.requests[0].messages[1].text
    # By default a table still takes the rule path; a bad path is refused.
    plain = _ok(_call(tmp_path, "POST", "/api/bi/runs", {**body, "path": None}, ai))["run"]
    assert plain["model"] is None and plain["status"] == "review"
    _refused(
        _call(tmp_path, "POST", "/api/bi/runs", {**body, "path": "x"}, ai), 400, "path_invalid"
    )
    word = _source(tmp_path, "market.docx", data=_docx())
    rules = {"dataset": "demo", "kind": "trial", "source_id": word["id"], "path": "rules"}
    _refused(_call(tmp_path, "POST", "/api/bi/runs", rules, ai), 400, "source_not_table")
