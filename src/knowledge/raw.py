"""Drop → Raw: originals become Raw Markdown that carries its own provenance.

Identity is the content. `source_for` derives a `KnowledgeSource` from the
bytes of an original, so the same file dropped under two names is one source
and a changed file is a new one — the path-keyed dedup of the source tooling
(docs/PHASE_4_MIGRATION.md) is deliberately not migrated. A `RawDocument`
renders to Markdown whose frontmatter is the provenance and whose sections each
carry their page, slide or image, and parses back exactly.
"""

import hashlib
import re
from collections.abc import Iterable
from datetime import date
from pathlib import PurePosixPath
from typing import Literal, Protocol, Self

from pydantic import Field, field_validator, model_validator

from common.base import Contract, Symbol, Text
from knowledge.contracts import KnowledgeSource
from knowledge.vault import Vault, VaultError, normalize

RAW_AREA = "raw/"
DROP_AREA = "drop/"
SECTION_MARKER = "<!-- raw-section"
_MARKER = re.compile(
    r"^<!-- raw-section (?P<index>\d+) kind=(?P<kind>text|table|image)"
    r"(?: page=(?P<page>\d+))?(?: slide=(?P<slide>\d+))?(?: image=(?P<image>\S+))? -->$"
)
_FRONTMATTER_LINE = re.compile(r"^(?P<key>[a-z0-9_]+): (?P<value>.+)$")

SectionKind = Literal["text", "table", "image"]
IntakeStatus = Literal["written", "duplicate", "drifted", "unsupported", "undecodable", "empty"]


class RawSection(Contract):
    """One extracted unit with the place it came from. An image section names
    its file and may carry a description; text and tables carry their text."""

    kind: SectionKind = "text"
    text: str = ""
    page: int | None = Field(default=None, ge=1, strict=True)
    slide: int | None = Field(default=None, ge=1, strict=True)
    image_ref: Text | None = None

    @field_validator("text", mode="before")
    @classmethod
    def trimmed_lines(cls, value: str) -> str:
        # Surrounding newlines would be lost by the file format anyway; drop
        # them here so a document equals its own round trip.
        return value.strip("\n") if isinstance(value, str) else value

    @model_validator(mode="after")
    def shape_matches_kind(self) -> Self:
        if (self.kind == "image") != (self.image_ref is not None):
            raise ValueError("exactly an image section names an image")
        if self.kind != "image" and not self.text.strip():
            raise ValueError("a text or table section carries text")
        if self.image_ref is not None and not normalize(self.image_ref).startswith(RAW_AREA):
            raise ValueError("an image lives under raw/")
        if SECTION_MARKER in self.text:
            raise ValueError("section text may not contain a section marker")
        if self.text.strip().startswith("---") and "\n---" in self.text:
            raise ValueError("section text may not contain a frontmatter block")
        return self


class RawDocument(Contract):
    """A Raw file: document-level provenance, the extractor that produced it,
    and its sections in order."""

    source: KnowledgeSource
    extractor: Symbol
    created: date
    sections: tuple[RawSection, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def document_level_provenance(self) -> Self:
        if self.source.raw_ref is None or not normalize(self.source.raw_ref).startswith(RAW_AREA):
            raise ValueError("a raw document names its raw_ref under raw/")
        if self.source.page is not None or self.source.slide is not None:
            raise ValueError("document provenance has no page or slide; sections do")
        return self


def source_for(data: bytes, original_ref: str) -> KnowledgeSource:
    """Identity from the bytes: the same content is the same source anywhere."""
    digest = hashlib.sha256(data).hexdigest()
    return KnowledgeSource(
        source_id=f"src-{digest[:16]}", original_ref=normalize(original_ref), sha256=digest
    )


def render(document: RawDocument) -> str:
    source = document.source
    lines = [
        "---",
        f"source_id: {source.source_id}",
        f"source_sha256: {source.sha256}",
        f"original_ref: {source.original_ref}",
        f"raw_ref: {source.raw_ref}",
        f"extractor: {document.extractor}",
        f"created: {document.created.isoformat()}",
        "---",
    ]
    for index, section in enumerate(document.sections, 1):
        marker = f"{SECTION_MARKER} {index} kind={section.kind}"
        if section.page is not None:
            marker += f" page={section.page}"
        if section.slide is not None:
            marker += f" slide={section.slide}"
        if section.image_ref is not None:
            marker += f" image={normalize(section.image_ref)}"
        lines += ["", marker + " -->"]
        if section.text:
            lines.append(section.text)
    return "\n".join(lines) + "\n"


def parse(text: str) -> RawDocument:
    """The document a Raw file holds. Malformed input is a `ValueError`; a file
    without provenance frontmatter is not a Raw document of this platform."""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("raw document starts with frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError("unterminated frontmatter") from None
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        match = _FRONTMATTER_LINE.match(line)
        if match is None:
            raise ValueError("malformed frontmatter line")
        fields[match.group("key")] = match.group("value").strip()
    try:
        source = KnowledgeSource(
            source_id=fields["source_id"],
            original_ref=fields["original_ref"],
            sha256=fields["source_sha256"],
            raw_ref=fields["raw_ref"],
        )
        extractor, created = fields["extractor"], date.fromisoformat(fields["created"])
    except KeyError as missing:
        raise ValueError(f"frontmatter is missing {missing.args[0]}") from None
    sections: list[RawSection] = []
    current: dict[str, str | None] | None = None
    body: list[str] = []

    def close() -> None:
        if current is not None:
            sections.append(
                RawSection(
                    kind=current["kind"],
                    text="\n".join(body),
                    page=int(current["page"]) if current["page"] else None,
                    slide=int(current["slide"]) if current["slide"] else None,
                    image_ref=current["image"],
                )
            )

    for line in lines[end + 1 :]:
        match = _MARKER.match(line)
        if match is not None:
            close()
            current, body = match.groupdict(), []
            if int(match.group("index")) != len(sections) + 1:
                raise ValueError("section markers are numbered in order")
        elif current is not None:
            body.append(line)
        elif line.strip():
            raise ValueError("text before the first section marker")
    close()
    return RawDocument(source=source, extractor=extractor, created=created, sections=sections)


class ExtractionError(Exception):
    def __init__(self, code: Literal["undecodable", "unsupported"]) -> None:
        self.code = code
        super().__init__(code)


class Extractor(Protocol):
    """Turns an original's bytes into sections. Names itself so a Raw file says
    what produced it; keyed by suffix so the intake can choose."""

    @property
    def name(self) -> str: ...

    @property
    def suffixes(self) -> tuple[str, ...]: ...

    def extract(self, data: bytes) -> tuple[RawSection, ...]: ...


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ExtractionError("undecodable") from None


class PlainTextExtractor:
    name = "plain-text.v1"
    suffixes = (".txt",)

    def extract(self, data: bytes) -> tuple[RawSection, ...]:
        text = _decode(data)
        return (RawSection(kind="text", text=text),) if text.strip() else ()


class MarkdownExtractor:
    """Markdown is kept whole; its own frontmatter, if any, is dropped so the
    Raw file's provenance is the only frontmatter."""

    name = "markdown.v1"
    suffixes = (".md", ".markdown")

    def extract(self, data: bytes) -> tuple[RawSection, ...]:
        text = _decode(data)
        lines = text.splitlines()
        if lines and lines[0] == "---" and "---" in lines[1:]:
            lines = lines[lines.index("---", 1) + 1 :]
        body = "\n".join(lines)
        return (RawSection(kind="text", text=body),) if body.strip() else ()


class IntakeOutcome(Contract):
    """What one intake did, or would do. Only `written` and `drifted` write;
    `duplicate` names the Raw that already holds the content."""

    mode: Literal["dry_run", "apply"]
    status: IntakeStatus
    original_ref: Text
    source: KnowledgeSource | None = None
    raw_ref: Text | None = None
    supersedes: KnowledgeSource | None = None
    written: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def status_matches_payload(self) -> Self:
        writes = self.status in ("written", "drifted")
        if writes != bool(self.written):
            raise ValueError("exactly a written or drifted intake lists writes")
        if (self.status == "drifted") != (self.supersedes is not None):
            raise ValueError("exactly a drifted intake names what it supersedes")
        if (self.raw_ref is not None) != (self.status in ("written", "drifted", "duplicate")):
            raise ValueError("a raw_ref belongs to content that is, or now is, in raw/")
        if self.source is None and self.status not in ("unsupported", "undecodable", "empty"):
            raise ValueError("an intake that reached the content names its source")
        return self


class RawEntry(Contract):
    """What the intake's index knows about one Raw file without reading its body."""

    raw_ref: Text
    source: KnowledgeSource


_INDEX_KEYS = ("source_id", "source_sha256", "original_ref")


def raw_index(vault: Vault) -> tuple[RawEntry, ...]:
    """Every Raw file that carries this platform's provenance. Files without it
    (an existing vault's content) are skipped, never rewritten."""
    entries: list[RawEntry] = []
    for rel in vault.raw_files():
        head = vault.read(rel).split("\n---", 1)[0].splitlines()
        if not head or head[0] != "---":
            continue
        fields: dict[str, str] = {}
        for line in head[1:]:
            match = _FRONTMATTER_LINE.match(line)
            if match is not None:
                fields[match.group("key")] = match.group("value").strip()
        if not all(key in fields for key in _INDEX_KEYS):
            continue
        try:
            source = KnowledgeSource(
                source_id=fields["source_id"],
                original_ref=fields["original_ref"],
                sha256=fields["source_sha256"],
                raw_ref=rel,
            )
        except ValueError:
            continue
        entries.append(RawEntry(raw_ref=rel, source=source))
    return tuple(entries)


class DropIntake:
    """Reads one original from `drop/` and writes it to `raw/` once."""

    def __init__(self, vault: Vault, extractors: Iterable[Extractor]) -> None:
        self.vault = vault
        self._by_suffix: dict[str, Extractor] = {}
        for extractor in extractors:
            for suffix in extractor.suffixes:
                self._by_suffix[suffix.lower()] = extractor

    def intake(
        self,
        drop_rel: str,
        *,
        mode: Literal["dry_run", "apply"] = "dry_run",
        today: date | None = None,
    ) -> IntakeOutcome:
        original_ref = normalize(drop_rel)
        if not original_ref.startswith(DROP_AREA):
            raise VaultError("outside_drop", drop_rel)
        data = self.vault.read_original(original_ref)
        source = source_for(data, original_ref)
        index = raw_index(self.vault)
        same_content = next((e for e in index if e.source.sha256 == source.sha256), None)
        if same_content is not None:
            return IntakeOutcome(
                mode=mode,
                status="duplicate",
                original_ref=original_ref,
                source=same_content.source,
                raw_ref=same_content.raw_ref,
            )
        suffix = PurePosixPath(original_ref).suffix.lower()
        extractor = self._by_suffix.get(suffix)
        if extractor is None:
            return IntakeOutcome(mode=mode, status="unsupported", original_ref=original_ref)
        try:
            sections = extractor.extract(data)
        except ExtractionError as error:
            return IntakeOutcome(mode=mode, status=error.code, original_ref=original_ref)
        if not sections:
            return IntakeOutcome(mode=mode, status="empty", original_ref=original_ref)

        # The same original path with other content is drift: the old Raw is
        # immutable and stays, the new one lives beside it under a name that
        # cannot collide, and the outcome says which it supersedes.
        previous = next((e for e in index if e.source.original_ref == original_ref), None)
        raw_ref = self._raw_ref_for(original_ref, source, taken={e.raw_ref for e in index})
        placed = source.model_copy(update={"raw_ref": raw_ref})
        document = RawDocument(
            source=placed,
            extractor=extractor.name,
            created=today if today is not None else date.today(),
            sections=sections,
        )
        status: IntakeStatus = "drifted" if previous is not None else "written"
        if mode == "apply":
            self.vault.write_raw(raw_ref, render(document))
        return IntakeOutcome(
            mode=mode,
            status=status,
            original_ref=original_ref,
            source=placed,
            raw_ref=raw_ref,
            supersedes=previous.source if previous is not None else None,
            written=(raw_ref,),
        )

    def _raw_ref_for(self, original_ref: str, source: KnowledgeSource, *, taken: set[str]) -> str:
        relative = PurePosixPath(original_ref[len(DROP_AREA) :])
        plain = str(PurePosixPath(RAW_AREA) / relative.with_suffix(".md"))
        if plain not in taken and not self.vault.exists(plain):
            return plain
        suffixed = relative.with_name(f"{relative.stem}--{source.sha256[:8]}.md")
        return str(PurePosixPath(RAW_AREA) / suffixed)
