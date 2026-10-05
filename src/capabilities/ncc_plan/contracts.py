"""Contracts for Workflow 14: the NCC 改善服務規劃 document.

`prepare` reads the catalogue and resolves every string the document will
carry, so `render` only edits the template and needs no catalogue. A dry run
stops after `prepare`, which is the source job's preview.
"""

from __future__ import annotations

from pydantic import Field

from common.base import Contract

#: The eleven 表一 ticks, named as the source parameters and the catalogue's
#: `systems[].field` name them, so a catalogue written for the source works.
SYSTEM_FIELDS = (
    "transmitter", "amplifier", "mixer", "satDecoder", "satAntenna", "gpsAntenna",
    "dvbtAntenna", "aircon", "voltageStabiliser", "ups", "isolationTransformer",
)


class NccPlanRequest(Contract):
    """The run's answers plus this install's Workflow settings."""

    # Per-install settings (`scope: static`).
    catalogue_file: str
    template_file: str
    output_dir: str
    photo_dir: str = ""
    # Run-time parameters.
    station: str
    channels: str = ""
    confirm_date: str = ""
    completion_date: str = ""
    draft_to: tuple[str, ...] = ()
    dry_run: bool = False
    transmitter: bool = False
    amplifier: bool = False
    mixer: bool = False
    satDecoder: bool = False  # noqa: N815 - the catalogue's field name
    satAntenna: bool = False  # noqa: N815
    gpsAntenna: bool = False  # noqa: N815
    dvbtAntenna: bool = False  # noqa: N815
    aircon: bool = False
    voltageStabiliser: bool = False  # noqa: N815
    ups: bool = False
    isolationTransformer: bool = False  # noqa: N815

    def ticks(self) -> dict[str, bool]:
        return {name: bool(getattr(self, name)) for name in SYSTEM_FIELDS}


class NccPlanStepInput(Contract):
    request: NccPlanRequest


class ServiceLine(Contract):
    item: str
    quantity: int


class Verdict(Contract):
    """`ok` is None for a dry run: it wrote nothing, so it has no pass or fail."""

    ok: bool | None
    summary: str


class OutputFile(Contract):
    name: str
    path: str


class NccDocument(Contract):
    """Every string the template edit writes, already resolved."""

    authority_line: str
    title_line: str
    contractor_line: str = ""
    channel_sentence: str
    start_year_line: str
    area_line: str
    confirm_line: str = ""
    system_rows: tuple[tuple[str, ...], ...]
    service_rows: tuple[tuple[str, ...], ...]
    plan_lines: tuple[str, ...] = ()
    fault_intro: str = ""
    fault_captions: tuple[str, ...] = ()


class NccMail(Contract):
    """The `outlook.draft` step's input; `skip` when there is nothing to draft."""

    skip: bool
    subject: str = ""
    html_body: str = ""
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    attachments: tuple[str, ...] = ()
    # The document is on disk before the draft; losing the covering note is
    # not a reason to report a failed run (source `create_draft`).
    best_effort: bool = True


class NccPlan(Contract):
    station: str
    authority: str
    built_year: str
    area: str
    population: int | None
    coverage_is_own: bool
    channels: tuple[str, ...]
    service_channels: tuple[str, ...]
    services: tuple[ServiceLine, ...]
    total: int
    expected_photos: tuple[str, ...]
    missing_photos: tuple[str, ...]
    unmatched: tuple[str, ...] = ()
    output_name: str
    output_path: str
    template_file: str
    dry_run: bool
    preview: tuple[str, ...] = Field(default_factory=tuple)
    verdict: Verdict
    document: NccDocument
    mail: NccMail


class NccRenderStepInput(Contract):
    plan: NccPlan


class NccRendered(Contract):
    written: bool
    output: str | None = None
    verdict: Verdict
    files: tuple[OutputFile, ...] = ()
    missing_photos: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
