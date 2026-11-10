"""Files attached to a conversation turn (owner 2026-10-08)."""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch, served  # noqa: F401 - the server fixture

from host_runtime.attachments import (
    MAX_FILE_BYTES,
    AttachmentError,
    AttachmentStore,
    for_model,
    safe_name,
)
from host_runtime.web import AgentWebServer
from host_runtime.web_page import PAGE

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def zipped(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_each_kind_reaches_the_model_as_text_paths_and_pictures(tmp_path: Path) -> None:
    store = AttachmentStore(tmp_path)
    files = [
        store.add("s1", "data.csv", b"name,price\nA,10\n"),
        store.add("s1", "config.yaml", b"key: value\n"),
        store.add("s1", "shot.png", PNG),
        store.add("s1", "bundle.zip", zipped({"logs/a.txt": b"x", "b.json": b"{}"})),
    ]
    note, images = for_model(files)
    assert "name,price" in note and "key: value" in note
    assert all(file.path in note for file in files)
    assert all(f"Host attachment_id: {file.file_id}" in note for file in files)
    assert Path(files[0].path).read_bytes() == b"name,price\nA,10\n"
    assert images == ("data:image/png;base64," + base64.b64encode(PNG).decode(),)
    assert files[3].entries == ("logs/a.txt", "b.json")
    assert (Path(files[3].unpacked or "") / "logs" / "a.txt").read_bytes() == b"x"
    assert "data only" in note
    assert "prefill known inputs" in note and "ask only for missing required values" in note


def test_unsupported_large_and_unsafe_files_are_refused(tmp_path: Path) -> None:
    store = AttachmentStore(tmp_path)
    for name, data, code in (
        ("tool.exe", b"MZ", "attachment_type_not_supported"),
        ("big.txt", b"x" * (MAX_FILE_BYTES + 1), "attachment_too_large"),
        ("evil.zip", zipped({"../../outside.txt": b"x"}), "attachment_zip_unsafe_path"),
        ("broken.zip", b"not a zip", "attachment_zip_invalid"),
    ):
        with pytest.raises(AttachmentError) as refused:
            store.add("s1", name, data)
        assert refused.value.code == code, name
    assert not (tmp_path / "outside.txt").exists()
    assert safe_name("C:\\Users\\x\\..\\report?.txt") == "report_.txt"


def test_a_file_belongs_to_its_conversation_and_goes_with_it(tmp_path: Path) -> None:
    store = AttachmentStore(tmp_path)
    saved = store.add("s1", "notes.md", b"# hi")
    assert store.get("s1", saved.file_id).filename == "notes.md"
    with pytest.raises(AttachmentError):
        store.get("s2", saved.file_id)
    with pytest.raises(AttachmentError):
        store.get("s1", "../../etc")
    store.delete_session("s1")
    with pytest.raises(AttachmentError):
        store.get("s1", saved.file_id)


def test_a_turn_carries_the_files_to_the_model_and_remembers_their_paths(
    served: AgentWebServer,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.gateway import GatewayConversationResult
    from common.execution import TraceIdentifiers
    from host_runtime.agent import LocalConversationOutcome

    trace = TraceIdentifiers(trace_id="t", request_id="r", span_id="s")
    seen: list[Any] = []

    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        seen.append(history)
        return LocalConversationOutcome(
            trace=trace,
            ingress="local",
            actor=request.actor,
            conversation=GatewayConversationResult.model_validate(
                {
                    "trace": trace,
                    "status": "answered",
                    "text": "read it",
                    "model_turns": 1,
                    "tools": (),
                }
            ),
        )

    monkeypatch.setattr(served.web.runtime.agent, "converse", converse)
    url, token = base(served), served.token
    session = fetch(url + "/api/conversations", token=token, body={}).json()
    session_id = session["conversation"]["session_id"]
    uploaded = fetch(
        url + "/api/attachments",
        token=token,
        body={
            "session_id": session_id,
            "filename": "prices.csv",
            "data": base64.b64encode(b"stock,price\n2330,1000\n").decode(),
        },
    ).json()
    assert uploaded["ok"] and uploaded["attachment"]["kind"] == "text"
    picture = fetch(
        url + "/api/attachments",
        token=token,
        body={
            "session_id": session_id,
            "filename": "chart.png",
            "data": base64.b64encode(PNG).decode(),
        },
    ).json()
    turn = fetch(
        url + "/api/conversations/turn",
        token=token,
        body={
            "session_id": session_id,
            "message": "整理這份資料",
            "attachments": [uploaded["attachment"]["file_id"], picture["attachment"]["file_id"]],
        },
    ).json()
    newest = seen[0][-1]
    assert "2330,1000" in newest.text and "prices.csv" in newest.text
    assert len(newest.images) == 1
    stored = turn["conversation"]["messages"][-2]
    assert [file["filename"] for file in stored["attachments"]] == ["prices.csv", "chart.png"]
    fetch(
        url + "/api/conversations/turn",
        token=token,
        body={"session_id": session_id, "message": "再算平均"},
    )
    earlier = [m.text for m in seen[1] if m.role == "user"][0]
    assert "[附件]" in earlier and "prices.csv" in earlier and not seen[1][0].images
    other = fetch(
        url + "/api/attachments",
        token=token,
        body={"session_id": "conversation-unknown", "filename": "a.txt", "data": "eA=="},
    )
    assert other.status == 400
    unknown = fetch(
        url + "/api/conversations/turn",
        token=token,
        body={
            "session_id": session_id,
            "message": "x",
            "attachments": ["att-20260101000000-00000000"],
        },
    )
    assert unknown.json()["code"] == "attachment_unknown"


def test_the_page_offers_attaching_dropping_and_pasting() -> None:
    assert 'id="attach"' in PAGE and 'id="attach-input"' in PAGE
    assert "/api/attachments" in PAGE and 'addEventListener("drop"' in PAGE
    assert 'addEventListener("paste"' in PAGE


def test_pdf_preview_includes_page_text_and_embedded_pictures(tmp_path: Path) -> None:
    from test_office import make_pdf

    item = AttachmentStore(tmp_path).add(
        "s1", "sop.pdf", make_pdf(["Open Sales Order", "Export to Excel"], image=True)
    )
    note, images = for_model([item])
    assert "Page 1" in note and "Page 2" in note
    assert "Open Sales Order" in note and "Export to Excel" in note
    assert len(images) == 1 and images[0].startswith("data:image/")
    assert "Picture 1" in note


def test_word_preview_preserves_tables_and_pictures(tmp_path: Path) -> None:
    from test_office import make_docx

    original = make_docx()
    item = AttachmentStore(tmp_path).add("s1", "sop.docx", original)
    note, images = for_model([item])
    assert note.index("First paragraph") < note.index("| Name | Value |")
    assert note.index("| x | 42 |") < note.index("After the table")
    assert len(images) == 1 and "Picture 1" in note
    assert Path(item.path).read_bytes() == original


def test_excel_preview_names_sheets_rows_and_keeps_formulas(tmp_path: Path) -> None:
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = "Sales mapping"
    sheet.append(["Sales Name / Owner", "Sub-Dept.", "Calculation"])
    sheet.append(["Example Owner", "SAS", "=1+2"])
    book.create_sheet("Output template").append(["Month", "Net Value"])
    buffer = io.BytesIO()
    book.save(buffer)
    original = buffer.getvalue()
    item = AttachmentStore(tmp_path).add("s1", "mapping.xlsx", original)
    note, images = for_model([item])
    assert "Sales mapping" in note and "Output template" in note
    assert "Sales Name / Owner" in note and "Sub-Dept." in note
    assert "Example Owner" in note and "=1+2" in note
    assert "Row 2" in note and not images
    assert Path(item.path).read_bytes() == original


@pytest.mark.parametrize("filename", ["broken.pdf", "broken.docx", "broken.xlsx"])
def test_document_failure_is_explicit_and_keeps_original(tmp_path: Path, filename: str) -> None:
    item = AttachmentStore(tmp_path).add("s1", filename, b"broken document")
    note, images = for_model([item])
    assert "document_unreadable" in note and item.path in note
    assert not images and Path(item.path).read_bytes() == b"broken document"


def test_document_picture_budget_is_shared_across_files(tmp_path: Path) -> None:
    from test_office import make_pdf

    from host_runtime.attachment_documents import MAX_DOCUMENT_IMAGES

    store = AttachmentStore(tmp_path)
    items = [
        store.add("s1", f"sop-{i}.pdf", make_pdf(["Export"], image=True))
        for i in range(MAX_DOCUMENT_IMAGES + 1)
    ]
    note, images = for_model(items)
    assert len(images) == MAX_DOCUMENT_IMAGES
    assert "picture limit" in note


def test_chat_picker_accepts_office_documents() -> None:
    picker = PAGE.split('id="attach-input"', 1)[1].split(">", 1)[0]
    assert ".xlsx" in picker and ".docx" in picker
    drag_types = PAGE.split("const ATTACHMENT_TYPES = ", 1)[1].split(";", 1)[0]
    assert '".xlsx"' in drag_types and '".docx"' in drag_types


def test_pdf_links_are_available_without_opening_the_site(tmp_path: Path) -> None:
    from pypdf import PdfReader, PdfWriter
    from pypdf.annotations import Link
    from test_office import make_pdf

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(make_pdf(["Home - SAP Cloud for Customer"]))))
    writer.add_annotation(0, Link(rect=(0, 0, 100, 100), url="https://c4c.example.invalid/home"))
    buffer = io.BytesIO()
    writer.write(buffer)
    item = AttachmentStore(tmp_path).add("s1", "sop.pdf", buffer.getvalue())
    note, _ = for_model([item])
    assert "[Page 1 link] https://c4c.example.invalid/home" in note


def test_workbook_preview_reports_limits_and_does_not_follow_links(tmp_path: Path) -> None:
    from openpyxl import Workbook

    from host_runtime.attachment_documents import MAX_WORKBOOK_ROWS

    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["Owner", "Department"])
    sheet.cell(MAX_WORKBOOK_ROWS + 1, 1, "outside-preview")
    buffer = io.BytesIO()
    book.save(buffer)
    item = AttachmentStore(tmp_path).add("s1", "mapping.xlsx", buffer.getvalue())
    note, _ = for_model([item])
    assert "preview truncated" in note and "outside-preview" not in note


def test_missing_document_reader_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import builtins

    from test_office import make_pdf

    original_import = builtins.__import__

    def without_reader(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "pypdf":
            raise ImportError("optional dependency not installed")
        return original_import(name, *args, **kwargs)

    item = AttachmentStore(tmp_path).add("s1", "sop.pdf", make_pdf(["Export"]))
    monkeypatch.setattr(builtins, "__import__", without_reader)
    note, images = for_model([item])
    assert "document_reader_unavailable" in note and not images


def test_long_cell_truncation_is_visible_in_a_short_workbook_preview(tmp_path: Path) -> None:
    from openpyxl import Workbook

    book = Workbook()
    assert book.active is not None
    book.active.append(["x" * 1200])
    buffer = io.BytesIO()
    book.save(buffer)
    item = AttachmentStore(tmp_path).add("s1", "long-cell.xlsx", buffer.getvalue())
    note, _ = for_model([item])
    assert "x" * 1000 in note and "x" * 1001 not in note
    assert "cell text limit reached" in note and "preview truncated" in note


def test_word_sop_hyperlink_target_is_available_without_opening_it(tmp_path: Path) -> None:
    from docx import Document
    from docx.opc.constants import RELATIONSHIP_TYPE
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    document = Document()
    paragraph = document.add_paragraph("Open ")
    relationship = document.part.relate_to(
        "https://c4c.example.invalid/home", RELATIONSHIP_TYPE.HYPERLINK, is_external=True
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship)
    run, label = OxmlElement("w:r"), OxmlElement("w:t")
    label.text = "C4C Home"
    run.append(label)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)
    buffer = io.BytesIO()
    document.save(buffer)
    item = AttachmentStore(tmp_path).add("s1", "sop.docx", buffer.getvalue())
    note, _ = for_model([item])
    assert "C4C Home" in note
    assert "[Document hyperlink] https://c4c.example.invalid/home" in note
