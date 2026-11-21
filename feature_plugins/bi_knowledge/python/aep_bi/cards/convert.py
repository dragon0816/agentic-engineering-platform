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
| Web page (`.html`, `.htm`) | provenance, title, summary, image, visible text (`html_markdown`) |

Table cells are written so they read back exactly (`table_cell` /
`readers.split_row`): `\\` and `|` are escaped and a line break becomes
`<br>`. The rule path reads converted tables in that exact mode, so a cell
keeps its text; a Markdown report a person wrote keeps the phase 3 reading
(links, bold and code marks removed).

The office libraries (`pypdf`, `python-docx`, `python-pptx`, `openpyxl`) are
the `office` extra; each is imported only when its kind of file is
converted, and a missing one is `converter_missing`. A PDF without any text
is `source_no_text`: scanned pages are not read (no OCR).

Pictures (owner 2026-11-20, "as Knowledge maintenance does"): a PDF page's
embedded images, a Word document's inline pictures and a slide's pictures are
taken out with the same core helpers as the LLM Wiki intake
(`knowledge.office`), kept beside the Markdown as `assets/<content hash>.<ext>`
and referenced in place as `![圖 n](assets/...)`. A model with vision then
adds a description under each (`image_describe`), as a later revision.
"""

from __future__ import annotations

import codecs
import io
import re
from collections.abc import Iterable
from pathlib import PurePath
from typing import Any

from aep_bi.cards import html_markdown, readers
from aep_bi.cards.store import BiStoreError
from knowledge.office import docx_pictures, pdf_page_images, pptx_picture
from knowledge.raw import AssetSink, StagedAssets

#: Recorded with every converted revision, so a later converter can tell.
#: `/2` keeps a document's pictures as assets referenced in the Markdown.
CONVERTER = "aep.bi.convert/2"
#: Where a source's pictures live, relative to its Markdown revisions.
ASSETS_DIR = "assets"
#: An image line a conversion wrote: `![圖 n](assets/<name>)`, alone on its line.
IMAGE_LINE = re.compile(r"^!\[(?P<alt>[^\]\n]*)\]\((?P<ref>assets/[0-9a-f]{16}\.[a-z0-9]{1,8})\)$")
#: A picture's file name under `ASSETS_DIR`.
ASSET_NAME = re.compile(r"^[0-9a-f]{16}\.[a-z0-9]{1,8}$")

TABLES = (*readers.DELIMITED, *readers.EXCEL)
DOCUMENTS = (".pdf", ".docx", ".pptx")
TEXTS = (".md", ".markdown", ".txt")
#: A web page a person shared (Telegram link collection P1), read without running it.
PAGES = (".html", ".htm")
CONVERTIBLE = (*TABLES, *DOCUMENTS, *TEXTS, *PAGES)

NO_TEXT_MESSAGE = (
    "這個 PDF 沒有可擷取的文字（可能是掃描檔）；AEP 不做文字辨識（OCR），"
    "請改用含文字層的 PDF、Word 檔，或把內容貼成文字"
)


def kind(name: str) -> str | None:
    """`table`, `document`, `text`, or None when the file cannot be converted."""
    suffix = readers.suffix(name)
    if suffix in TABLES:
        return "table"
    if suffix in DOCUMENTS or suffix in PAGES:
        return "document"
    if suffix in TEXTS:
        return "text"
    return None


def convert_with_assets(name: str, data: bytes) -> tuple[str, dict[str, bytes]]:
    """The Markdown of a source and the pictures it references (`assets/<name>` ->
    bytes); raises `BiStoreError` when it cannot be read."""
    staged = StagedAssets(ASSETS_DIR)
    text = convert(name, data, staged)
    return text, dict(staged.items)


class _Pictures:
    """Numbers a document's pictures and hands their bytes to the sink."""

    def __init__(self, assets: AssetSink | None) -> None:
        self.assets = assets
        self.count = 0

    def line(self, blob: bytes, suffix: str) -> str | None:
        if self.assets is None:
            return None
        self.count += 1
        return f"![圖 {self.count}]({self.assets.put(blob, suffix)})"


def convert(name: str, data: bytes, assets: AssetSink | None = None) -> str:
    """The Markdown of a source; raises `BiStoreError` when it cannot be read.
    With `assets`, a document's pictures are put there and referenced in place."""
    suffix = readers.suffix(name)
    if suffix in readers.DELIMITED:
        text = readers.decode(data)
        table = readers.delimited_table(name, text, "\t" if suffix == ".tsv" else ",")
        return _tables_markdown([table], headings=False)
    if suffix in readers.EXCEL:
        return _tables_markdown(readers.excel_tables(data), headings=True)
    if suffix == ".pdf":
        return pdf_markdown(data, assets)
    if suffix == ".docx":
        return docx_markdown(data, assets)
    if suffix == ".pptx":
        return pptx_markdown(data, assets)
    if suffix in TEXTS:
        return decode_text(data).replace("\r\n", "\n")
    if suffix in PAGES:
        return html_markdown.markdown(html_markdown.decode(data))
    raise BiStoreError(
        "file_type_unsupported",
        f"「{PurePath(name).name}」無法轉成 Markdown；可用 CSV、TSV、Excel、PDF、Word、"
        "PowerPoint、Markdown、網頁或文字檔",
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


def pdf_markdown(data: bytes, assets: AssetSink | None = None) -> str:
    try:
        import pypdf
    except ImportError as error:
        raise _missing("pypdf") from error
    pictures = _Pictures(assets)
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        pages: list[tuple[str, list[str]]] = []
        for page in reader.pages:
            images: list[str] = []
            if assets is not None:
                found = (pictures.line(b, s) for b, s in pdf_page_images(page))
                images = [line for line in found if line]
            pages.append((page.extract_text() or "", images))
    except Exception as error:  # pypdf raises many unrelated types
        raise BiStoreError("source_parse_failed", "無法讀取這個 PDF 檔") from error
    parts = []
    has_text = False
    for number, (text, images) in enumerate(pages, start=1):
        body = _tidy(text)
        has_text = has_text or bool(body.strip())
        blocks = [block for block in (body, *images) if block.strip()]
        if blocks:
            parts.append(f"## 第 {number} 頁\n\n" + "\n\n".join(blocks))
    if not has_text:
        raise BiStoreError("source_no_text", NO_TEXT_MESSAGE)
    return "\n\n".join(parts) + "\n"


# -- Word --------------------------------------------------------------------


def _heading_level(style: str) -> int | None:
    if style == "Title":
        return 1
    found = re.fullmatch(r"Heading (\d)", style)
    return min(int(found.group(1)), 6) if found else None


def docx_markdown(data: bytes, assets: AssetSink | None = None) -> str:
    try:
        import docx
        from docx.table import Table
    except ImportError as error:
        raise _missing("python-docx") from error
    pictures = _Pictures(assets)
    try:
        document = docx.Document(io.BytesIO(data))
        blocks: list[str] = []

        def images_in(element: Any) -> list[str]:
            if assets is None:
                return []
            found = (pictures.line(b, s) for b, s in docx_pictures(document, element))
            return [line for line in found if line]

        for item in document.iter_inner_content():
            if isinstance(item, Table):
                rows = [[cell.text for cell in row.cells] for row in item.rows]
                if rows:
                    blocks.append("\n".join(markdown_table(rows[0], rows[1:])))
                blocks += images_in(item._element)
                continue
            text = item.text.strip()
            images = images_in(item._element)
            if not text:
                blocks += images
                continue
            style = item.style.name if item.style is not None else ""
            level = _heading_level(style or "")
            if level is not None:
                blocks.append(f"{'#' * level} {text}")
            elif (style or "").startswith("List"):
                blocks.append(f"- {text}")
            else:
                blocks.append(text)
            blocks += images
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


def pptx_markdown(data: bytes, assets: AssetSink | None = None) -> str:
    try:
        import pptx
        from pptx.shapes.picture import Picture
    except ImportError as error:
        raise _missing("python-pptx") from error
    pictures = _Pictures(assets)
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
                if isinstance(shape, Picture):
                    found = pptx_picture(shape) if assets is not None else None
                    line = pictures.line(*found) if found is not None else None
                    if line:
                        blocks.append(line)
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
