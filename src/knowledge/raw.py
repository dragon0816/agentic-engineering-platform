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

from pydantic import Field, ValidationError, field_validator, model_validator

from common.base import Contract, Symbol, Text
from knowledge.contracts import KnowledgeSource
from knowledge.vault import Vault, VaultError, normalize, provenance_lines

RAW_AREA = "raw/"
DROP_AREA = "drop/"
SECTION_MARKER = "<!-- raw-section"
# A body line that would read as a marker is escaped with a backslash on the
# way out and unescaped on the way in, so any text is representable.
_ESCAPED_MARKER = re.compile(r"^(\\*)" + re.escape(SECTION_MARKER))
_MARKER = re.compile(
    r"^<!-- raw-section (?P<index>\d+) kind=(?P<kind>text|table|image)"
    r"(?: page=(?P<page>\d+))?(?: slide=(?P<slide>\d+))?(?: image=(?P<image>\S+))? -->$"
)
_FRONTMATTER_LINE = re.compile(r"^(?P<key>[a-z0-9_]+): (?P<value>.+)$")
_PROVENANCE_KEYS = ("source_id", "source_sha256", "original_ref", "raw_ref", "extractor", "created")

SectionKind = Literal["text", "table", "image"]
IntakeStatus = Literal[
    "written", "duplicate", "drifted", "unsupported", "undecodable", "empty", "unrepresentable"
]


def _lines(text: str) -> str:
    """One line ending. `str.splitlines` would also split on form feeds and
    Unicode separators, so the file format only ever uses `\\n`."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


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
    def one_line_ending(cls, value: str) -> str:
        # Surrounding newlines would be lost by the file format anyway; drop
        # them here so a document equals its own round trip.
        return _lines(value).strip("\n") if isinstance(value, str) else value

    @field_validator("image_ref", mode="before")
    @classmethod
    def normalized_ref(cls, value: str | None) -> str | None:
        return normalize(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def shape_matches_kind(self) -> Self:
        if (self.kind == "image") != (self.image_ref is not None):
            raise ValueError("exactly an image section names an image")
        if self.kind != "image" and not self.text.strip():
            raise ValueError("a text or table section carries text")
        if self.image_ref is not None:
            if not self.image_ref.startswith(RAW_AREA):
                raise ValueError("an image lives under raw/")
            if any(char.isspace() for char in self.image_ref):
                raise ValueError("an image reference has no whitespace")
        return self


class RawDocument(Contract):
    """A Raw file: document-level provenance, the extractor that produced it,
    the source it supersedes when the same original drifted, and its sections."""

    source: KnowledgeSource
    extractor: Symbol
    created: date
    sections: tuple[RawSection, ...] = Field(min_length=1)
    supersedes: Symbol | None = None

    @model_validator(mode="after")
    def document_level_provenance(self) -> Self:
        if self.source.raw_ref is None or not self.source.raw_ref.startswith(RAW_AREA):
            raise ValueError("a raw document names its raw_ref under raw/")
        if self.source.page is not None or self.source.slide is not None:
            raise ValueError("document provenance has no page or slide; sections do")
        if self.supersedes == self.source.source_id:
            raise ValueError("a document does not supersede itself")
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
        *provenance_lines(source),
        f"original_ref: {source.original_ref}",
        f"raw_ref: {source.raw_ref}",
        f"extractor: {document.extractor}",
        f"created: {document.created.isoformat()}",
    ]
    if document.supersedes is not None:
        lines.append(f"supersedes: {document.supersedes}")
    lines.append("---")
    for index, section in enumerate(document.sections, 1):
        marker = f"{SECTION_MARKER} {index} kind={section.kind}"
        if section.page is not None:
            marker += f" page={section.page}"
        if section.slide is not None:
            marker += f" slide={section.slide}"
        if section.image_ref is not None:
            marker += f" image={section.image_ref}"
        lines += ["", marker + " -->"]
        for line in section.text.split("\n") if section.text else ():
            lines.append("\\" + line if _ESCAPED_MARKER.match(line) else line)
    return "\n".join(lines) + "\n"


def frontmatter(text: str) -> tuple[dict[str, str], int] | None:
    """The `key: value` head of a file and the line after it, or None when the
    file does not start with a closed frontmatter block."""
    lines = _lines(text).split("\n")
    if not lines or lines[0] != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        match = _FRONTMATTER_LINE.match(line)
        if match is None:
            return None
        fields[match.group("key")] = match.group("value").strip()
    return fields, end + 1


def _provenance(fields: dict[str, str], raw_ref: str | None = None) -> KnowledgeSource:
    return KnowledgeSource(
        source_id=fields["source_id"],
        original_ref=fields["original_ref"],
        sha256=fields["source_sha256"],
        raw_ref=raw_ref if raw_ref is not None else fields["raw_ref"],
    )


def parse(text: str) -> RawDocument:
    """The document a Raw file holds. Malformed input is a `ValueError`; a file
    without provenance frontmatter is not a Raw document of this platform."""
    head = frontmatter(text)
    if head is None:
        raise ValueError("a raw document starts with closed, well-formed frontmatter")
    fields, start = head
    missing = [key for key in _PROVENANCE_KEYS if key not in fields]
    if missing:
        raise ValueError(f"frontmatter is missing {missing[0]}")
    source = _provenance(fields)
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

    for line in _lines(text).split("\n")[start:]:
        match = _MARKER.match(line)
        if match is not None:
            close()
            current, body = match.groupdict(), []
            if int(match.group("index")) != len(sections) + 1:
                raise ValueError("section markers are numbered in order")
        elif current is not None:
            body.append(line[1:] if _ESCAPED_MARKER.match(line) else line)
        elif line.strip():
            raise ValueError("text before the first section marker")
    close()
    return RawDocument(
        source=source,
        extractor=fields["extractor"],
        created=date.fromisoformat(fields["created"]),
        sections=sections,
        supersedes=fields.get("supersedes"),
    )


class ExtractionError(Exception):
    def __init__(self, code: Literal["undecodable", "unsupported"]) -> None:
        self.code = code
        super().__init__(code)


class AssetSink(Protocol):
    """Where an extractor hands over image bytes. It answers with the `image_ref`
    the section should carry; whether and when the bytes reach disk is the
    intake's business, so an extractor never writes."""

    def put(self, data: bytes, suffix: str) -> str: ...


class StagedAssets:
    """Assets one extraction produced, named by their content under the Raw
    document's own assets directory and written only on apply."""

    def __init__(self, assets_dir: str) -> None:
        self.assets_dir = normalize(assets_dir)
        self.items: dict[str, bytes] = {}

    def put(self, data: bytes, suffix: str) -> str:
        clean = suffix.lower() if suffix.startswith(".") else f".{suffix.lower()}"
        ref = f"{self.assets_dir}/{hashlib.sha256(data).hexdigest()[:16]}{clean}"
        self.items.setdefault(ref, data)
        return ref


def assets_dir_for(raw_ref: str) -> str:
    """`raw/notes/hello.md` keeps its images under `raw/notes/hello/assets/`."""
    return normalize(raw_ref)[: -len(".md")] + "/assets"


class Extractor(Protocol):
    """Turns an original's bytes into sections. Names itself so a Raw file says
    what produced it; keyed by suffix so the intake can choose; hands images to
    the sink rather than writing anything."""

    @property
    def name(self) -> str: ...

    @property
    def suffixes(self) -> tuple[str, ...]: ...

    def extract(self, data: bytes, assets: AssetSink) -> tuple[RawSection, ...]: ...


def _decode(data: bytes) -> str:
    try:
        return _lines(data.decode("utf-8"))
    except UnicodeDecodeError:
        raise ExtractionError("undecodable") from None


class PlainTextExtractor:
    name = "plain-text.v1"
    suffixes = (".txt",)

    def extract(self, data: bytes, assets: AssetSink) -> tuple[RawSection, ...]:
        text = _decode(data)
        return (RawSection(kind="text", text=text),) if text.strip() else ()


class MarkdownExtractor:
    """Markdown is kept whole; its own frontmatter, if any, is dropped so the
    Raw file's provenance is the only frontmatter."""

    name = "markdown.v1"
    suffixes = (".md", ".markdown")

    def extract(self, data: bytes, assets: AssetSink) -> tuple[RawSection, ...]:
        text = _decode(data)
        lines = text.split("\n")
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
        if self.source is None and self.status in ("written", "drifted", "duplicate"):
            raise ValueError("an intake that reached the content names its source")
        return self


class RawEntry(Contract):
    """What the index knows about one Raw file from its head alone."""

    raw_ref: Text
    source: KnowledgeSource
    created: date
    supersedes: Symbol | None = None


class RawIndex:
    """The Raw files that carry this platform's provenance, read from their
    heads once and kept current with the intake's own writes."""

    def __init__(self, entries: Iterable[RawEntry] = ()) -> None:
        self.entries: list[RawEntry] = list(entries)

    @classmethod
    def scan(cls, vault: Vault) -> "RawIndex":
        """Files without provenance, or whose head cannot be read, are skipped —
        an existing vault's content is never a reason to fail, nor rewritten."""
        entries: list[RawEntry] = []
        for rel in vault.raw_files():
            head = frontmatter(vault.read_head(rel))
            if head is None or any(key not in head[0] for key in _PROVENANCE_KEYS):
                continue
            fields = head[0]
            try:
                entries.append(
                    RawEntry(
                        raw_ref=rel,
                        source=_provenance(fields, raw_ref=rel),
                        created=date.fromisoformat(fields["created"]),
                        supersedes=fields.get("supersedes"),
                    )
                )
            except (ValidationError, ValueError):
                continue
        return cls(entries)

    def by_content(self, sha256: str) -> RawEntry | None:
        return next((entry for entry in self.entries if entry.source.sha256 == sha256), None)

    def latest_for(self, original_ref: str) -> RawEntry | None:
        """The current Raw of an original: the one no later Raw supersedes."""
        chain = [entry for entry in self.entries if entry.source.original_ref == original_ref]
        superseded = {entry.supersedes for entry in chain if entry.supersedes is not None}
        heads = [entry for entry in chain if entry.source.source_id not in superseded]
        return max(heads, key=lambda entry: (entry.created, entry.raw_ref), default=None)

    def paths(self) -> set[str]:
        return {entry.raw_ref for entry in self.entries}

    def add(self, document: RawDocument) -> None:
        assert document.source.raw_ref is not None
        self.entries.append(
            RawEntry(
                raw_ref=document.source.raw_ref,
                source=document.source,
                created=document.created,
                supersedes=document.supersedes,
            )
        )


def raw_index(vault: Vault) -> tuple[RawEntry, ...]:
    return tuple(RawIndex.scan(vault).entries)


class DropIntake:
    """Reads originals from `drop/` and writes each to `raw/` once."""

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
        index: RawIndex | None = None,
    ) -> IntakeOutcome:
        """One original. The index is scanned once per call unless a batch
        passes its own, which the intake keeps current with what it writes."""
        original_ref = self.vault.original_ref(drop_rel)
        data = self.vault.read_original(original_ref)
        source = source_for(data, original_ref)
        known = index if index is not None else RawIndex.scan(self.vault)
        same_content = known.by_content(source.sha256)
        if same_content is not None:
            return IntakeOutcome(
                mode=mode,
                status="duplicate",
                original_ref=original_ref,
                source=same_content.source,
                raw_ref=same_content.raw_ref,
            )
        extractor = self._by_suffix.get(PurePosixPath(original_ref).suffix.lower())
        if extractor is None:
            return IntakeOutcome(mode=mode, status="unsupported", original_ref=original_ref)
        # The Raw's name is fixed before extraction so images can be named
        # under it; the same original path with other content is drift: the old
        # Raw is immutable and stays, the new one lives beside it under a name
        # that cannot collide, and both the file and the outcome say what it
        # supersedes.
        previous = known.latest_for(original_ref)
        raw_ref = self._raw_ref_for(original_ref, source, taken=known.paths())
        staged = StagedAssets(assets_dir_for(raw_ref))
        try:
            sections = extractor.extract(data, staged)
        except ExtractionError as error:
            return IntakeOutcome(mode=mode, status=error.code, original_ref=original_ref)
        except ValidationError:
            return IntakeOutcome(mode=mode, status="unrepresentable", original_ref=original_ref)
        if not sections:
            return IntakeOutcome(mode=mode, status="empty", original_ref=original_ref)
        placed = source.model_copy(update={"raw_ref": raw_ref})
        try:
            document = RawDocument(
                source=placed,
                extractor=extractor.name,
                created=today if today is not None else date.today(),
                sections=sections,
                supersedes=previous.source.source_id if previous is not None else None,
            )
        except ValidationError:
            return IntakeOutcome(mode=mode, status="unrepresentable", original_ref=original_ref)
        referenced = {section.image_ref for section in sections if section.image_ref}
        assets = tuple(ref for ref in staged.items if ref in referenced)
        if mode == "apply":
            # Assets first: they are content-named, so a Raw that fails to
            # write leaves nothing a later attempt cannot reuse.
            for ref in assets:
                self.vault.write_raw_bytes(ref, staged.items[ref])
            self.vault.write_raw(raw_ref, render(document))
            known.add(document)
        return IntakeOutcome(
            mode=mode,
            status="drifted" if previous is not None else "written",
            original_ref=original_ref,
            source=placed,
            raw_ref=raw_ref,
            supersedes=previous.source if previous is not None else None,
            written=(raw_ref, *assets),
        )

    def intake_all(
        self,
        drop_rels: Iterable[str],
        *,
        mode: Literal["dry_run", "apply"] = "dry_run",
        today: date | None = None,
    ) -> tuple[IntakeOutcome, ...]:
        """A batch over one index scan; a dry run sees its own would-be writes
        too, so it reports exactly what an apply of the same batch would do."""
        index = RawIndex.scan(self.vault)
        outcomes = []
        for drop_rel in drop_rels:
            outcome = self.intake(drop_rel, mode=mode, today=today, index=index)
            if mode == "dry_run" and outcome.written and outcome.source is not None:
                index.add(
                    RawDocument(
                        source=outcome.source,
                        extractor="pending",
                        created=today if today is not None else date.today(),
                        sections=(RawSection(text="pending"),),
                        supersedes=(outcome.supersedes.source_id if outcome.supersedes else None),
                    )
                )
            outcomes.append(outcome)
        return tuple(outcomes)

    def _raw_ref_for(self, original_ref: str, source: KnowledgeSource, *, taken: set[str]) -> str:
        relative = PurePosixPath(original_ref[len(DROP_AREA) :])
        plain = (PurePosixPath(RAW_AREA) / relative.with_suffix(".md")).as_posix()
        if plain not in taken and not self.vault.exists(plain):
            return plain
        # A legacy file may already sit where the hash-suffixed name would go;
        # the name is escalated until it is free, so a dry run and an apply agree.
        for attempt in range(1, 1000):
            suffix = source.sha256[:8] if attempt == 1 else f"{source.sha256[:8]}-{attempt}"
            candidate = (
                PurePosixPath(RAW_AREA) / relative.with_name(f"{relative.stem}--{suffix}.md")
            ).as_posix()
            if candidate not in taken and not self.vault.exists(candidate):
                return candidate
        raise VaultError("raw_exists", plain)
