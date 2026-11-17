"""Convert a BI source to Markdown (BI vault phase V2, owner 2026-10-28).

`docs/phases/BI_VAULT.md` §5: every source is converted once to Markdown,
kept beside the untouched original, shown and editable; extraction reads the
Markdown, not the original. One readable text form means the rule path, the
AI path, the search index and a person all look at the same thing, and an
evidence line number points at something a person can open.

| Source | Markdown |
|---|---|
| CSV, TSV | one pipe table |
| Excel (`.xlsx`, `.xlsm`) | per sheet a `## <sheet>` heading and one table |
| PDF with a text layer | per page a `## 第 n 頁` heading and its text (no OCR) |
| Word (`.docx`) | headings, paragraphs, list items and tables in order |
| PowerPoint (`.pptx`) | per slide a heading, its text, tables and notes |
| Markdown, text | as is |

Table cells are written so they read back exactly (`table_cell` /
`readers.split_row`): `\\` and `|` are escaped and a line break becomes
`<br>`. The rule path reads converted tables in that exact mode, so a cell
keeps its text; a Markdown report a person wrote keeps the phase 3 reading
(links, bold and code marks removed).

The office libraries (`pypdf`, `python-docx`, `python-pptx`, `openpyxl`) are
the `office` extra; each is imported only when its kind of file is
converted, and a missing one is `converter_missing`. A PDF without any text
is `source_no_text`: scanned pages are not read (no OCR).
"""

from __future__ import annotations

import codecs
import io
import re
from collections.abc import Iterable
from pathlib import PurePath
from typing import Any

from aep_bi.cards import readers
from aep_bi.cards.store import BiStoreError

#: Recorded with every converted revision, so a later converter can tell.
CONVERTER = "aep.bi.convert/1"

TABLES = (*readers.DELIMITED, *readers.EXCEL)
DOCUMENTS = (".pdf", ".docx", ".pptx")
TEXTS = (".md", ".markdown", ".txt")
CONVERTIBLE = (*TABLES, *DOCUMENTS, *TEXTS)

NO_TEXT_MESSAGE = (
    "這個 PDF 沒有可擷取的文字（可能是掃描檔）；AEP 不做文字辨識（OCR），"
    "請改用含文字層的 PDF、Word 檔，或把內容貼成文字"
)


def kind(name: str) -> str | None:
    """`table`, `document`, `text`, or None when the file cannot be converted."""
    suffix = readers.suffix(name)
    if suffix in TABLES:
        return "table"
    if suffix in DOCUMENTS:
        return "document"
    if suffix in TEXTS:
        return "text"
    return None


def convert(name: str, data: bytes) -> str:
    """The Markdown of a source; raises `BiStoreError` when it cannot be read."""
    suffix = readers.suffix(name)
    if suffix in readers.DELIMITED:
        text = readers.decode(data)
        table = readers.delimited_table(name, text, "\t" if suffix == ".tsv" else ",")
        return _tables_markdown([table], headings=False)
    if suffix in readers.EXCEL:
        return _tables_markdown(readers.excel_tables(data), headings=True)
    if suffix == ".pdf":
        return pdf_markdown(data)
    if suffix == ".docx":
        return docx_markdown(data)
    if suffix == ".pptx":
        return pptx_markdown(data)
    if suffix in TEXTS:
        return decode_text(data).replace("\r\n", "\n")
    raise BiStoreError(
        "file_type_unsupported",
        f"「{PurePath(name).name}」無法轉成 Markdown；可用 CSV、TSV、Excel、PDF、Word、"
        "PowerPoint、Markdown 或文字檔",
    )


#: Tried in order for a text source without a UTF-16 byte order mark: UTF-8 (with or
#: without its mark), then Big5 as Traditional Chinese Windows saves it.
TEXT_ENCODINGS = ("utf-8-sig", "cp950")


def decode_text(data: bytes) -> str:
    """A Markdown or text source's characters, decoded strictly: UTF-16 by its byte
    order mark, else `TEXT_ENCODINGS`. Bytes none of them reads are
    `source_decode_failed` (as `readers.decode`), never text with U+FFFD in it."""
    utf16 = data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE))
    for encoding in ("utf-16",) if utf16 else TEXT_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise BiStoreError(
        "source_decode_failed",
        "來源不是 UTF-8、UTF-16 或 Big5 文字，無法轉成 Markdown；請另存為 UTF-8 後再加入",
    )


def _missing(library: str) -> BiStoreError:
    return BiStoreError(
        "converter_missing",
        f"這台電腦沒有安裝轉檔元件 {library}（AEP 的 office 套件）；請安裝後再轉檔",
    )


# -- tables ------------------------------------------------------------------


def table_cell(value: Any) -> str:
    """A cell that reads back exactly with `readers.split_row`."""
    text = str(value if value is not None else "")
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    return re.sub(r"\r\n|\r|\n", "<br>", text).strip()


def markdown_table(columns: list[str], rows: Iterable[list[str]]) -> list[str]:
    """A pipe table's lines; a row is cut or padded to the header's width."""
    width = max(len(columns), 1)
    header = [table_cell(c) for c in columns] or [""]
    lines = ["| " + " | ".join(header) + " |", "|" + " --- |" * width]
    for row in rows:
        cells = [table_cell(v) for v in list(row)[:width]]
        cells += [""] * (width - len(cells))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def _tables_markdown(tables: list[dict[str, Any]], *, headings: bool) -> str:
    lines: list[str] = []
    for table in tables:
        if headings:
            if lines:
                lines.append("")
            lines += [f"## {table['title']}", ""]
        if not table["columns"]:
            lines.append("（這個工作表是空的）")
            continue
        columns = [str(c) for c in table["columns"]]
        lines += markdown_table(
            columns, ([row["cells"].get(c, "") for c in columns] for row in table["rows"])
        )
    return "\n".join(lines) + ("\n" if lines else "")


# -- PDF ---------------------------------------------------------------------


def _tidy(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    joined = "\n".join(lines).strip("\n")
    return re.sub(r"\n{3,}", "\n\n", joined)


def pdf_markdown(data: bytes) -> str:
    try:
        import pypdf
    except ImportError as error:
        raise _missing("pypdf") from error
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as error:  # pypdf raises many unrelated types
        raise BiStoreError("source_parse_failed", "無法讀取這個 PDF 檔") from error
    parts = []
    for number, text in enumerate(pages, start=1):
        body = _tidy(text)
        if body.strip():
            parts.append(f"## 第 {number} 頁\n\n{body}")
    if not parts:
        raise BiStoreError("source_no_text", NO_TEXT_MESSAGE)
    return "\n\n".join(parts) + "\n"


# -- Word --------------------------------------------------------------------


def _heading_level(style: str) -> int | None:
    if style == "Title":
        return 1
    found = re.fullmatch(r"Heading (\d)", style)
    return min(int(found.group(1)), 6) if found else None


def docx_markdown(data: bytes) -> str:
    try:
        import docx
        from docx.table import Table
    except ImportError as error:
        raise _missing("python-docx") from error
    try:
        document = docx.Document(io.BytesIO(data))
        blocks: list[str] = []
        for item in document.iter_inner_content():
            if isinstance(item, Table):
                rows = [[cell.text for cell in row.cells] for row in item.rows]
                if rows:
                    blocks.append("\n".join(markdown_table(rows[0], rows[1:])))
                continue
            text = item.text.strip()
            if not text:
                continue
            style = item.style.name if item.style is not None else ""
            level = _heading_level(style or "")
            if level is not None:
                blocks.append(f"{'#' * level} {text}")
            elif (style or "").startswith("List"):
                blocks.append(f"- {text}")
            else:
                blocks.append(text)
    except BiStoreError:
        raise
    except Exception as error:  # python-docx raises many unrelated types
        raise BiStoreError("source_parse_failed", "無法讀取這個 Word 檔") from error
    return _join_blocks(blocks)


def _join_blocks(blocks: list[str]) -> str:
    """Blocks separated by a blank line, except consecutive list items."""
    out: list[str] = []
    for block in blocks:
        listed = block.lstrip().startswith("- ") and out and out[-1].lstrip().startswith("- ")
        if out and not listed:
            out.append("")
        out.append(block)
    return "\n".join(out) + ("\n" if out else "")


# -- PowerPoint --------------------------------------------------------------


def _shapes(shapes: Any) -> Iterable[Any]:
    """Every shape, group members in place."""
    for shape in shapes:
        if getattr(shape, "shapes", None) is not None and not getattr(shape, "has_table", False):
            yield from _shapes(shape.shapes)
        else:
            yield shape


def pptx_markdown(data: bytes) -> str:
    try:
        import pptx
    except ImportError as error:
        raise _missing("python-pptx") from error
    try:
        deck = pptx.Presentation(io.BytesIO(data))
        blocks: list[str] = []
        for number, slide in enumerate(deck.slides, start=1):
            title_shape = slide.shapes.title
            title = title_shape.text_frame.text.strip() if title_shape is not None else ""
            blocks.append(f"## 投影片 {number}" + (f"：{title}" if title else ""))
            for shape in _shapes(slide.shapes):
                if title_shape is not None and shape.shape_id == title_shape.shape_id:
                    continue
                if getattr(shape, "has_table", False) and shape.has_table:
                    rows = [[cell.text for cell in row.cells] for row in shape.table.rows]
                    if rows:
                        blocks.append("\n".join(markdown_table(rows[0], rows[1:])))
                    continue
                if not getattr(shape, "has_text_frame", False) or not shape.has_text_frame:
                    continue
                for paragraph in shape.text_frame.paragraphs:
                    text = "".join(run.text for run in paragraph.runs).strip()
                    if not text:
                        continue
                    if paragraph.level:
                        blocks.append(f"{'  ' * (paragraph.level - 1)}- {text}")
                    else:
                        blocks.append(text)
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame
                text = _tidy(notes.text) if notes is not None else ""
                if text.strip():
                    blocks.append(f"### 備註\n\n{text}")
    except BiStoreError:
        raise
    except Exception as error:  # python-pptx raises many unrelated types
        raise BiStoreError("source_parse_failed", "無法讀取這個 PowerPoint 檔") from error
    return _join_blocks(blocks)
