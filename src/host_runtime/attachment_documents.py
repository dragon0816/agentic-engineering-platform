"""Local, bounded document previews for conversation attachments.

Original files are never changed. Pictures are returned to the same approved
model request as the document's text, with source labels rather than OCR guesses.
"""

from __future__ import annotations

import base64
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from knowledge.office import DocxExtractor

MAX_DOCUMENT_IMAGES = 12
MAX_DOCUMENT_IMAGE_BYTES = 5 * 1024 * 1024
MAX_DOCUMENT_PAGES = 40
MAX_WORKBOOK_SHEETS = 10
MAX_WORKBOOK_ROWS = 100
MAX_WORKBOOK_COLUMNS = 40
MAX_PACKAGE_BYTES = 200 * 1024 * 1024
MAX_PACKAGE_ENTRIES = 2000
MAX_PREVIEW_CHARS = 24_000
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


@dataclass
class DocumentPreview:
    text: str = ""
    pictures: list[tuple[str, str]] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)


class _Pictures:
    def __init__(self, preview: DocumentPreview, limit: int) -> None:
        self.preview = preview
        self.limit = limit
        self.references: dict[str, str] = {}

    def put(self, data: bytes, suffix: str) -> str:
        # The shared Office extractor requires a Raw-shaped reference; this is
        # an in-memory key only, never a Knowledge write or a filesystem path.
        ref = f"raw/attachment/picture-{len(self.references) + 1}{suffix}"
        media_type = IMAGE_TYPES.get(suffix.lower())
        if len(self.preview.pictures) >= self.limit:
            label = "picture limit reached; remaining pictures are not shown"
        elif len(data) > MAX_DOCUMENT_IMAGE_BYTES:
            label = "picture exceeds size limit; not shown"
        elif media_type is None:
            label = "unsupported picture format; not shown"
        else:
            label = f"Picture {len(self.preview.pictures) + 1}"
            uri = f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"
            self.preview.pictures.append((label, uri))
        self.references[ref] = label
        return ref


def _package_check(data: bytes) -> None:
    """Office ZIP containers have the same expansion bounds as attached ZIPs."""
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        members = package.infolist()
        if (
            len(members) > MAX_PACKAGE_ENTRIES
            or sum(m.file_size for m in members) > MAX_PACKAGE_BYTES
        ):
            raise ValueError("document package exceeds limits")


def document_preview(path: Path, picture_limit: int) -> DocumentPreview:
    result = DocumentPreview()
    pictures = _Pictures(result, max(0, picture_limit))
    try:
        data = path.read_bytes()
        if path.suffix.lower() == ".pdf":
            _pdf(data, result, pictures)
        else:
            _package_check(data)
            if path.suffix.lower() == ".docx":
                sections = DocxExtractor().extract(data, pictures)
                result.text = "\n\n".join(
                    pictures.references[section.image_ref] if section.image_ref else section.text
                    for section in sections
                )
                result.text += _docx_links(data)
            else:
                result.text = _workbook(data)
        if len(result.text) > MAX_PREVIEW_CHARS:
            result.text = result.text[:MAX_PREVIEW_CHARS]
            result.notices.append("document preview truncated; original file remains at its path")
        if not result.text.strip() and not result.pictures:
            result.notices.append("document_empty: no readable text or supported pictures")
    except ImportError:
        result = DocumentPreview(notices=["document_reader_unavailable: install the office extra"])
    except Exception:  # noqa: BLE001 - bad user documents must not abort a conversation
        result = DocumentPreview(notices=["document_unreadable: original file remains at its path"])
    return result


def _pdf(data: bytes, result: DocumentPreview, pictures: _Pictures) -> None:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("encrypted PDF")
    lines: list[str] = []
    for number, page in enumerate(reader.pages):
        if number >= MAX_DOCUMENT_PAGES:
            result.notices.append("page limit reached; remaining PDF pages are not shown")
            break
        lines.append(f"[Page {number + 1}]")
        lines.append((page.extract_text() or "")[:MAX_PREVIEW_CHARS])
        for annotation in page.get("/Annots", []):
            action = annotation.get_object().get("/A", {})
            uri = action.get("/URI")
            if isinstance(uri, str) and uri.startswith(("https://", "http://")):
                lines.append(f"[Page {number + 1} link] {uri}")
        for key in page.images.keys():
            if len(result.pictures) >= pictures.limit:
                result.notices.append("picture limit reached; remaining pictures are not shown")
                break
            try:
                image = page.images[key]
                ref = pictures.put(image.data, Path(image.name).suffix)
                label = f"Page {number + 1} — {pictures.references[ref]}"
                lines.append(label)
                if result.pictures and result.pictures[-1][0] == pictures.references[ref]:
                    result.pictures[-1] = (label, result.pictures[-1][1])
            except Exception:  # noqa: BLE001 - one bad picture must not hide readable text
                result.notices.append(f"Page {number + 1}: picture_unreadable")
    result.text = "\n".join(lines)


def _workbook(data: bytes) -> str:
    from openpyxl import load_workbook

    book = load_workbook(io.BytesIO(data), read_only=True, data_only=False, keep_links=False)
    lines = ["Workbook preview (formulas are source expressions, not calculated results)"]
    try:
        for index, sheet in enumerate(book):
            if index >= MAX_WORKBOOK_SHEETS:
                lines.append("sheet limit reached; remaining sheets are not shown")
                break
            lines.append(f"[Sheet: {sheet.title}]")
            cells_truncated = False
            # Iterate within fixed bounds even when a workbook declares enormous dimensions.
            for number, row in enumerate(
                sheet.iter_rows(
                    max_row=MAX_WORKBOOK_ROWS, max_col=MAX_WORKBOOK_COLUMNS, values_only=True
                ),
                1,
            ):
                raw_cells = [str(value) if value is not None else "" for value in row]
                cells_truncated |= any(len(value) > 1000 for value in raw_cells)
                cells = [value[:1000] for value in raw_cells]
                if any(cells):
                    lines.append(f"Row {number}: " + " | ".join(cells).rstrip(" |"))
            if cells_truncated:
                lines.append("cell text limit reached; workbook preview truncated")
            if (sheet.max_row or 0) > MAX_WORKBOOK_ROWS or (
                sheet.max_column or 0
            ) > MAX_WORKBOOK_COLUMNS:
                lines.append("row/column limit reached; workbook preview truncated")
    finally:
        book.close()
    return "\n".join(lines)


def _docx_links(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        if "word/_rels/document.xml.rels" not in package.namelist():
            return ""
        relationships = ElementTree.fromstring(package.read("word/_rels/document.xml.rels"))
    links = [
        element.get("Target", "")
        for element in relationships
        if element.get("Type", "").endswith("/hyperlink")
        and element.get("Target", "").startswith(("https://", "http://"))
    ]
    return "".join(f"\n[Document hyperlink] {uri}" for uri in links)
