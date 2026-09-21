"""Image description at intake: vision declared, image as a data URI, every
failure a closed status, and the description written into the Raw file."""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_raw import drop, make_vault

from common.execution import Failure, TraceIdentifiers
from knowledge.describe import DEFAULT_PROMPT, ImageDescriber, data_uri
from knowledge.raw import (
    AssetSink,
    DropIntake,
    ImageDescription,
    IntakeOutcome,
    RawSection,
    StagedAssets,
    parse,
)
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

TODAY = date(2026, 9, 21)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
SECOND = PNG + b"2"
# The fake model echoes the inline image's length, so expectations are computed.
EXPECTED = f"A chart ({len(data_uri(PNG, 'image/png'))} chars)"
EXPECTED_SECOND = f"A chart ({len(data_uri(SECOND, 'image/png'))} chars)"


class VisionModel:
    """Answers with a description built from the request, or fails on demand."""

    def __init__(self, *, fail: bool = False, blank: bool = False) -> None:
        self.requests: list[ModelRequest] = []
        self.fail = fail
        self.blank = blank

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.fail:
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                failure=Failure(code="model_unavailable", message="no vision model"),
            )
        text = "" if self.blank else f"  A chart ({len(request.messages[0].images[0])} chars)  "
        return ModelResponse(trace=request.trace, model_alias=request.model_alias, text=text)

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


class ImageExtractor:
    """Emits two pictures — the second twice — and a paragraph, like a deck would."""

    name = "images.v1"
    suffixes = (".img",)

    def extract(self, data: bytes, assets: AssetSink) -> tuple[RawSection, ...]:
        first = assets.put(PNG, ".png")
        second = assets.put(SECOND, ".png")
        return (
            RawSection(text="Intro", slide=1),
            RawSection(kind="image", image_ref=first, slide=1),
            RawSection(kind="image", image_ref=second, slide=2),
            RawSection(kind="image", image_ref=second, slide=3),
            RawSection(kind="image", text="already captioned", image_ref=first, slide=4),
        )


def test_a_description_request_declares_vision_and_carries_the_image_inline() -> None:
    model = VisionModel()
    describer = ImageDescriber(model, alias="vision-default")
    trace = TraceIdentifiers(trace_id="t", request_id="r", span_id="s")
    described = describer.describe("raw/deck/assets/abc.png", PNG, trace=trace)
    assert described.status == "described" and described.text == EXPECTED
    (request,) = model.requests
    assert request.requirements.vision is True and request.model_alias == "vision-default"
    assert request.messages[0].text == DEFAULT_PROMPT
    assert request.messages[0].images == (data_uri(PNG, "image/png"),)
    assert request.max_output_tokens == 400 and request.trace == trace


def test_every_failure_is_a_closed_status() -> None:
    trace = TraceIdentifiers(trace_id="t", request_id="r", span_id="s")
    failing = ImageDescriber(VisionModel(fail=True), alias="v")
    result = failing.describe("raw/a/assets/x.png", PNG, trace=trace)
    assert result.status == "model_failed" and result.failure is not None
    assert result.failure.code == "model_unavailable" and result.text == ""
    blank = ImageDescriber(VisionModel(blank=True), alias="v")
    assert blank.describe("raw/a/assets/x.png", PNG, trace=trace).status == "empty_answer"
    small = ImageDescriber(VisionModel(), alias="v", max_bytes=4)
    assert small.describe("raw/a/assets/x.png", PNG, trace=trace).status == "too_large"
    assert small.model.requests == []  # type: ignore[attr-defined]
    odd = ImageDescriber(VisionModel(), alias="v")
    assert odd.describe("raw/a/assets/x.svg", PNG, trace=trace).status == "unsupported_type"
    with pytest.raises(ValueError, match="positive"):
        ImageDescriber(VisionModel(), alias="v", max_output_tokens=0)
    with pytest.raises(ValidationError, match="described"):
        ImageDescription(image_ref="raw/a/x.png", status="described")
    with pytest.raises(ValidationError, match="failure"):
        ImageDescription(image_ref="raw/a/x.png", status="model_failed")


def test_sections_are_described_once_per_image_and_captions_are_kept() -> None:
    model = VisionModel()
    describer = ImageDescriber(model, alias="v")
    staged = StagedAssets("raw/deck/assets")
    sections = ImageExtractor().extract(b"", staged)
    updated, results = describer.describe_sections(sections, staged.items, trace_id="intake-1")
    assert [s.text for s in updated] == [
        "Intro",
        EXPECTED,
        EXPECTED_SECOND,
        EXPECTED_SECOND,
        "already captioned",
    ]
    assert (
        [(r.image_ref[-7:], r.status) for r in results]
        == [
            (sections[1].image_ref[-7:], "described"),  # type: ignore[index]
            (sections[2].image_ref[-7:], "described"),  # type: ignore[index]
        ]
    )
    assert len(model.requests) == 2  # the repeated picture was asked about once
    assert {r.trace.trace_id for r in model.requests} == {"intake-1"}
    assert len({r.trace.request_id for r in model.requests}) == 2
    # Bytes the sink never held are a status, not an exception.
    orphan = (RawSection(kind="image", image_ref="raw/deck/assets/nope.png"),)
    _, missing = describer.describe_sections(orphan, {}, trace_id="intake-2")
    assert [m.status for m in missing] == ["missing_bytes"]


def test_intake_describes_on_apply_and_only_counts_on_dry_run(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    model = VisionModel()
    intake = DropIntake(vault, [ImageExtractor()], describer=ImageDescriber(model, alias="v"))
    drop(vault, "drop/deck.img", b"anything")
    preview = intake.intake("drop/deck.img", today=TODAY)
    assert preview.status == "written" and preview.images_to_describe == 2
    assert preview.descriptions == () and model.requests == []

    applied = intake.intake("drop/deck.img", mode="apply", today=TODAY)
    assert applied.images_to_describe == 0
    assert [d.status for d in applied.descriptions] == ["described", "described"]
    assert len(model.requests) == 2
    stored = parse(vault.read("raw/deck.md"))
    assert [s.text for s in stored.sections][1:4] == [EXPECTED, EXPECTED_SECOND, EXPECTED_SECOND]
    assert stored.sections[4].text == "already captioned"
    # A failing model still writes the document; the outcome says what was not described.
    (tmp_path / "second").mkdir()
    vault2 = make_vault(tmp_path / "second")
    failing = DropIntake(
        vault2, [ImageExtractor()], describer=ImageDescriber(VisionModel(fail=True), alias="v")
    )
    drop(vault2, "drop/deck.img", b"anything")
    outcome = failing.intake("drop/deck.img", mode="apply", today=TODAY)
    assert outcome.status == "written"
    assert [d.status for d in outcome.descriptions] == ["model_failed", "model_failed"]
    assert parse(vault2.read("raw/deck.md")).sections[1].text == ""


def test_without_a_describer_nothing_is_asked(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    intake = DropIntake(vault, [ImageExtractor()])
    drop(vault, "drop/deck.img", b"anything")
    outcome = intake.intake("drop/deck.img", mode="apply", today=TODAY)
    assert outcome.images_to_describe == 2 and outcome.descriptions == ()
    with pytest.raises(ValidationError, match="apply"):
        IntakeOutcome(
            mode="dry_run",
            status="written",
            original_ref="drop/x.img",
            source=outcome.source,
            raw_ref="raw/x.md",
            written=("raw/x.md",),
            descriptions=(ImageDescription(image_ref="raw/x/a.png", status="empty_answer"),),
        )
    with pytest.raises(ValidationError, match="only an intake that writes"):
        IntakeOutcome(mode="apply", status="empty", original_ref="drop/x.img", images_to_describe=1)
