"""Image description at intake: vision declared, image as a data URI, every
failure a closed status, a model failure stopping the write, and the
description written into the Raw file marked with what described it."""

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
    render,
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

    def __init__(self, *, fail: bool = False, blank: bool = False, raise_: bool = False) -> None:
        self.requests: list[ModelRequest] = []
        self.fail = fail
        self.blank = blank
        self.raise_ = raise_

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.raise_:
            raise TimeoutError("read timed out")
        if self.fail:
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                failure=Failure(code="model_unavailable", message="no vision model"),
            )
        text = "" if self.blank else f" A chart ({len(request.messages[0].images[0])} chars)\r\n"
        return ModelResponse(trace=request.trace, model_alias=request.model_alias, text=text)

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


class ImageExtractor:
    """Emits two pictures — the second twice — and a paragraph, like a deck would.
    The original's first byte chooses whether a third, new picture appears."""

    name = "images.v1"
    suffixes = (".img",)

    def extract(self, data: bytes, assets: AssetSink) -> tuple[RawSection, ...]:
        first = assets.put(PNG, ".png")
        second = assets.put(SECOND, ".png")
        sections = [
            RawSection(text="Intro", slide=1),
            RawSection(kind="image", image_ref=first, slide=1),
            RawSection(kind="image", image_ref=second, slide=2),
            RawSection(kind="image", image_ref=second, slide=3),
            RawSection(kind="image", text="already captioned", image_ref=first, slide=4),
        ]
        if data.startswith(b"v2"):
            sections.append(RawSection(kind="image", image_ref=assets.put(PNG + b"3", ".png")))
        return tuple(sections)


def trace() -> TraceIdentifiers:
    return TraceIdentifiers(trace_id="t", request_id="r", span_id="s")


def test_a_description_request_declares_vision_and_carries_the_image_inline() -> None:
    model = VisionModel()
    describer = ImageDescriber(model, alias="vision-default")
    described = describer.describe("raw/deck/assets/abc.png", PNG, trace=trace())
    assert described.status == "described" and described.text == EXPECTED
    (request,) = model.requests
    assert request.requirements.vision is True and request.model_alias == "vision-default"
    assert request.messages[0].text == DEFAULT_PROMPT
    assert request.messages[0].images == (data_uri(PNG, "image/png"),)
    assert request.max_output_tokens == 400 and request.trace == trace()


def test_every_failure_is_a_closed_status() -> None:
    failing = ImageDescriber(VisionModel(fail=True), alias="v")
    result = failing.describe("raw/a/assets/x.png", PNG, trace=trace())
    assert result.status == "model_failed" and result.failure is not None
    assert result.failure.code == "model_unavailable" and result.text == ""
    # An adapter that raises is a status too, marked retryable.
    raising = ImageDescriber(VisionModel(raise_=True), alias="v")
    raised = raising.describe("raw/a/assets/x.png", PNG, trace=trace())
    assert raised.status == "model_failed" and raised.failure is not None
    assert raised.failure.code == "model_error" and raised.failure.retryable is True
    assert "TimeoutError" in raised.failure.message
    blank = ImageDescriber(VisionModel(blank=True), alias="v")
    assert blank.describe("raw/a/assets/x.png", PNG, trace=trace()).status == "empty_answer"
    small_model = VisionModel()
    small = ImageDescriber(small_model, alias="v", max_bytes=4)
    assert small.describe("raw/a/assets/x.png", PNG, trace=trace()).status == "too_large"
    assert small_model.requests == []
    odd_model = VisionModel()
    odd = ImageDescriber(odd_model, alias="v")
    for suffix in (".svg", ".bmp", ".tiff", ".emf"):
        assert odd.describe(f"raw/a/assets/x{suffix}", PNG, trace=trace()).status == (
            "unsupported_type"
        )
    assert odd_model.requests == []
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
    # A model's words are marked as such; the source's caption is not.
    assert [s.described_by for s in updated] == [None, "v", "v", "v", None]
    assert [r.status for r in results] == ["described", "described"]
    assert len(model.requests) == 2  # the repeated picture was asked about once
    assert {r.trace.trace_id for r in model.requests} == {"intake-1"}
    assert [r.trace.span_id for r in model.requests] == ["image-1", "image-2"]
    assert (
        [r.trace.request_id for r in model.requests]
        == [
            f"describe-{sections[1].image_ref.rsplit('/', 1)[1][:-4]}",  # type: ignore[union-attr]
            f"describe-{sections[2].image_ref.rsplit('/', 1)[1][:-4]}",  # type: ignore[union-attr]
        ]
    )
    # Memoised by content across calls: the same bytes under another name cost nothing.
    again = describer.describe("raw/other/assets/renamed.png", PNG, trace=trace())
    assert again.status == "described" and again.text == EXPECTED and len(model.requests) == 2
    # Bytes the sink never held are a status, not an exception, and spans count requests only.
    orphan = (
        RawSection(kind="image", image_ref="raw/deck/assets/nope.png"),
        RawSection(kind="image", image_ref="raw/deck/assets/new.png"),
    )
    _, missing = describer.describe_sections(
        orphan, {"raw/deck/assets/new.png": b"fresh"}, trace_id="intake-2"
    )
    assert [m.status for m in missing] == ["missing_bytes", "described"]
    assert model.requests[-1].trace.span_id == "image-1"


def test_descriptions_are_normalized_and_marked_in_the_raw_file(tmp_path: Path) -> None:
    section = RawSection(
        kind="image", image_ref="raw/d/assets/a.png", text="Line one\r\nline two", described_by="v"
    )
    assert section.text == "Line one\nline two"
    with pytest.raises(ValidationError, match="what described it"):
        RawSection(text="plain", described_by="v")
    with pytest.raises(ValidationError, match="what described it"):
        RawSection(kind="image", image_ref="raw/d/assets/a.png", described_by="v")
    vault = make_vault(tmp_path)
    intake = DropIntake(
        vault, [ImageExtractor()], describer=ImageDescriber(VisionModel(), alias="v")
    )
    drop(vault, "drop/deck.img", b"anything")
    intake.intake("drop/deck.img", mode="apply", today=TODAY)
    text = vault.read("raw/deck.md")
    assert " described=v -->" in text
    stored = parse(text)
    assert render(stored) == text
    assert [s.described_by for s in stored.sections] == [None, "v", "v", "v", None]
    assert [s.text for s in stored.sections][1:4] == [EXPECTED, EXPECTED_SECOND, EXPECTED_SECOND]


def test_intake_describes_on_apply_and_only_counts_on_dry_run(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    model = VisionModel()
    intake = DropIntake(vault, [ImageExtractor()], describer=ImageDescriber(model, alias="v"))
    drop(vault, "drop/deck.img", b"anything")
    preview = intake.intake("drop/deck.img", today=TODAY)
    assert preview.status == "written" and preview.images_to_describe == 2
    assert preview.descriptions == () and model.requests == []
    batch = intake.intake_all(["drop/deck.img"], today=TODAY)
    assert batch[0].images_to_describe == 2 and model.requests == []

    applied = intake.intake("drop/deck.img", mode="apply", today=TODAY)
    assert applied.status == "written" and applied.images_to_describe == 0
    assert [d.status for d in applied.descriptions] == ["described", "described"]
    assert len(model.requests) == 2


def test_a_model_failure_stops_the_write_so_it_can_be_retried(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    flaky = VisionModel(fail=True)
    intake = DropIntake(vault, [ImageExtractor()], describer=ImageDescriber(flaky, alias="v"))
    drop(vault, "drop/deck.img", b"anything")
    outcome = intake.intake("drop/deck.img", mode="apply", today=TODAY)
    assert outcome.status == "description_failed" and outcome.written == ()
    assert outcome.source is not None and outcome.raw_ref is None
    assert [d.status for d in outcome.descriptions] == ["model_failed", "model_failed"]
    assert outcome.images_to_describe == 2
    assert vault.raw_files() == () and not (tmp_path / "raw" / "deck").exists()
    # The model recovers: the same original is not a duplicate, and is written now.
    flaky.fail = False
    retried = intake.intake("drop/deck.img", mode="apply", today=TODAY)
    assert retried.status == "written" and vault.raw_files() == ("raw/deck.md",)
    with pytest.raises(ValidationError, match="stops the write"):
        IntakeOutcome(mode="apply", status="description_failed", original_ref="drop/x.img")


def test_a_drifted_original_reuses_the_descriptions_it_already_paid_for(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    model = VisionModel()
    intake = DropIntake(vault, [ImageExtractor()], describer=ImageDescriber(model, alias="v"))
    drop(vault, "drop/deck.img", b"v1")
    intake.intake("drop/deck.img", mode="apply", today=TODAY)
    assert len(model.requests) == 2
    # A fresh describer (new process, empty memo) still asks only about the new picture.
    fresh = VisionModel()
    later = DropIntake(vault, [ImageExtractor()], describer=ImageDescriber(fresh, alias="v2"))
    drop(vault, "drop/deck.img", b"v2")
    outcome = later.intake("drop/deck.img", mode="apply", today=TODAY)
    assert outcome.status == "drifted" and len(fresh.requests) == 1
    assert [d.status for d in outcome.descriptions] == ["described"]
    stored = parse(vault.read(outcome.raw_ref or ""))
    assert [s.described_by for s in stored.sections] == [None, "v", "v", "v", None, "v2"]
    assert stored.sections[1].text == EXPECTED


def test_without_a_describer_nothing_is_asked(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    intake = DropIntake(vault, [ImageExtractor()])
    drop(vault, "drop/deck.img", b"anything")
    outcome = intake.intake("drop/deck.img", mode="apply", today=TODAY)
    assert outcome.status == "written"
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
    with pytest.raises(ValidationError, match="reached a document"):
        IntakeOutcome(mode="apply", status="empty", original_ref="drop/x.img", images_to_describe=1)
