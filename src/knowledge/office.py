"""Office extraction: PDF, PPTX and DOCX originals into Raw sections.

Each extractor keeps the relationship the Roadmap asks for — text, tables and
images with the page or slide they came from — and hands image bytes to the
intake's `AssetSink` rather than writing anything. The libraries are an
optional dependency (`pip install .[office]`); nothing else in the platform
imports them, and every import here is lazy so a host without the extra still
loads this module and gets `unsupported` for these suffixes only if it never
registers these extractors.
"""

import io
from collections.abc import Iterable, Sequence
from pathlib import PurePosixPath

from knowledge.raw import AssetSink, ExtractionError, RawSection


def table_markdown(rows: Sequence[Sequence[str]]) -> str:
    """A GitHub-style table; the first row is the header. Cells are flattened
    to one line and pipes escaped, so the table stays a table in Markdown."""
    if not rows:
        return ""
    width = max(len(row) for row in rows)

    def cell(text: str) -> str:
        return " ".join(text.split()).replace("|", "\\|")

    padded = [[cell(text) for text in row] + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(padded[0]) + " |", "|" + " --- |" * width]
    lines += ["| " + " | ".join(row) + " |" for row in padded[1:]]
    return "\n".join(lines)


def _text_section(parts: list[str], **place: int | None) -> RawSection | None:
    body = "\n\n".join(part for part in parts if part.strip())
    parts.clear()
    return RawSection(kind="text", text=body, **place) if body.strip() else None


class PdfExtractor:
    """Text per page and embedded images per page. PDF has no table model, so
    tables arrive as text in reading order; that is a known limitation."""

    name = "pdf.v1"
    suffixes = (".pdf",)

    def extract(self, data: bytes, assets: AssetSink) -> tuple[RawSection, ...]:
        from pypdf import PdfReader

        sections: list[RawSection] = []
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted and not reader.decrypt(""):
                raise ExtractionError("undecodable")
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                if text.strip():
                    sections.append(RawSection(kind="text", text=text, page=number))
                for image in page.images:
                    suffix = PurePosixPath(image.name).suffix or ".png"
                    ref = assets.put(image.data, suffix)
                    sections.append(RawSection(kind="image", image_ref=ref, page=number))
        except ExtractionError:
            raise
        except Exception:
            # A third-party parser raises an open set of types on a corrupt or
            # unsupported file; the intake needs one closed status for all of it.
            raise ExtractionError("undecodable") from None
        return tuple(sections)


class PptxExtractor:
    """Per slide, in shape order: text frames gathered into one text section,
    tables as Markdown, pictures as image sections. Speaker notes are not
    extracted."""

    name = "pptx.v1"
    suffixes = (".pptx",)

    def extract(self, data: bytes, assets: AssetSink) -> tuple[RawSection, ...]:
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE
        from pptx.shapes.picture import Picture

        sections: list[RawSection] = []
        try:
            deck = Presentation(io.BytesIO(data))
            for number, slide in enumerate(deck.slides, 1):
                texts: list[str] = []
                for shape in slide.shapes:
                    if getattr(shape, "has_table", False) and shape.has_table:
                        if (gathered := _text_section(texts, slide=number)) is not None:
                            sections.append(gathered)
                        rows = [[cell.text for cell in row.cells] for row in shape.table.rows]
                        table = table_markdown(rows)
                        if table:
                            sections.append(RawSection(kind="table", text=table, slide=number))
                    elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE and isinstance(shape, Picture):
                        if (gathered := _text_section(texts, slide=number)) is not None:
                            sections.append(gathered)
                        ref = assets.put(shape.image.blob, shape.image.ext)
                        sections.append(RawSection(kind="image", image_ref=ref, slide=number))
                    elif shape.has_text_frame:
                        texts.append(shape.text_frame.text)
                if (gathered := _text_section(texts, slide=number)) is not None:
                    sections.append(gathered)
        except ExtractionError:
            raise
        except Exception:
            raise ExtractionError("undecodable") from None
        return tuple(sections)


class DocxExtractor:
    """Body elements in document order: paragraphs gathered into text sections
    (headings keep their level as Markdown `#`), tables as Markdown, inline
    pictures as image sections. Word has no fixed pages, so sections carry no
    page number."""

    name = "docx.v1"
    suffixes = (".docx",)

    def extract(self, data: bytes, assets: AssetSink) -> tuple[RawSection, ...]:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        sections: list[RawSection] = []
        try:
            document = Document(io.BytesIO(data))
            texts: list[str] = []
            for child in document.element.body.iterchildren():
                if child.tag == qn("w:p"):
                    paragraph = Paragraph(child, document._body)
                    texts.append(
                        _heading(paragraph.style.name if paragraph.style else "", paragraph.text)
                    )
                    for blip in child.iter(qn("a:blip")):
                        relationship = blip.get(qn("r:embed"))
                        if not relationship:
                            continue
                        part = document.part.related_parts[relationship]
                        if (gathered := _text_section(texts)) is not None:
                            sections.append(gathered)
                        suffix = PurePosixPath(str(part.partname)).suffix or ".png"
                        ref = assets.put(part.blob, suffix)
                        sections.append(RawSection(kind="image", image_ref=ref))
                elif child.tag == qn("w:tbl"):
                    if (gathered := _text_section(texts)) is not None:
                        sections.append(gathered)
                    table = Table(child, document._body)
                    rows = [[cell.text for cell in row.cells] for row in table.rows]
                    markdown = table_markdown(rows)
                    if markdown:
                        sections.append(RawSection(kind="table", text=markdown))
            if (gathered := _text_section(texts)) is not None:
                sections.append(gathered)
        except ExtractionError:
            raise
        except Exception:
            raise ExtractionError("undecodable") from None
        return tuple(sections)


def _heading(style: str, text: str) -> str:
    if style.startswith("Heading ") and style[8:].isdigit() and text.strip():
        return "#" * min(int(style[8:]), 6) + " " + text.strip()
    return text


def office_extractors() -> Iterable[PdfExtractor | PptxExtractor | DocxExtractor]:
    return (PdfExtractor(), PptxExtractor(), DocxExtractor())
