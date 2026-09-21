"""Image description through the model interface, at intake time.

Raw is write-once, so a description has to be part of the document when it is
written: the intake hands the staged image bytes to an `ImageDescriber`, which
asks a `ModelClient` with `vision=True` declared and attaches the answer to the
image section as its text, marked with the alias that produced it so a model's
words are never mistaken for the source's. No provider is named here; the
image travels as a `data:` URI inside the provider-neutral `ModelMessage`, so
any adapter can consume it without file access, and every failure — the
adapter raising included — is a closed status, never a lost document.
"""

import base64
import hashlib
from collections.abc import Mapping
from pathlib import PurePosixPath

from common.base import Symbol, Text
from common.execution import Failure, TraceIdentifiers
from knowledge.raw import ImageDescription, RawSection, needs_description, one_line_ending
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

MAX_IMAGE_BYTES = 5_000_000
# What vision endpoints accept in general; anything else is `unsupported_type`
# before a byte is sent, rather than a provider rejection dressed as an outage.
MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
DEFAULT_PROMPT = (
    "Describe this image for a knowledge base: what it shows, and any text, numbers, "
    "labels, axes or legends it contains, as written. Be factual and specific; do not "
    "guess at what is not visible."
)


def data_uri(data: bytes, media_type: str) -> str:
    return f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"


class ImageDescriber:
    """Describes image sections one request each. Results are memoised by the
    image's content for the describer's lifetime, so a picture repeated in a
    document, across documents or across versions of one is described once."""

    def __init__(
        self,
        model: ModelClient,
        *,
        alias: Symbol,
        prompt: Text = DEFAULT_PROMPT,
        max_output_tokens: int = 400,
        max_bytes: int = MAX_IMAGE_BYTES,
    ) -> None:
        if max_output_tokens < 1 or max_bytes < 1:
            raise ValueError("limits are positive")
        self.model = model
        self.alias = alias
        self.prompt = prompt
        self.max_output_tokens = max_output_tokens
        self.max_bytes = max_bytes
        self._by_content: dict[str, str] = {}

    def describe(self, image_ref: str, data: bytes, *, trace: TraceIdentifiers) -> ImageDescription:
        media_type = MEDIA_TYPES.get(PurePosixPath(image_ref).suffix.lower())
        if media_type is None:
            return ImageDescription(image_ref=image_ref, status="unsupported_type")
        if len(data) > self.max_bytes:
            return ImageDescription(image_ref=image_ref, status="too_large")
        digest = hashlib.sha256(data).hexdigest()
        known = self._by_content.get(digest)
        if known is not None:
            return ImageDescription(image_ref=image_ref, status="described", text=known)
        request = ModelRequest(
            trace=trace,
            model_alias=self.alias,
            messages=(
                ModelMessage(role="user", text=self.prompt, images=(data_uri(data, media_type),)),
            ),
            requirements=ModelRequirements(vision=True),
            max_output_tokens=self.max_output_tokens,
        )
        try:
            response = self.model.generate(request)
        except Exception as error:  # noqa: BLE001 - an adapter's failure is a status here
            failure = Failure(
                code="model_error",
                message=f"{type(error).__name__}: {error}"[:200].strip() or type(error).__name__,
                retryable=True,
            )
            return ImageDescription(image_ref=image_ref, status="model_failed", failure=failure)
        if response.failure is not None:
            return ImageDescription(
                image_ref=image_ref, status="model_failed", failure=response.failure
            )
        text = one_line_ending(response.text).strip()
        if not text:
            return ImageDescription(image_ref=image_ref, status="empty_answer")
        self._by_content[digest] = text
        return ImageDescription(image_ref=image_ref, status="described", text=text)

    def describe_sections(
        self,
        sections: tuple[RawSection, ...],
        assets: Mapping[str, bytes],
        *,
        trace_id: str,
    ) -> tuple[tuple[RawSection, ...], tuple[ImageDescription, ...]]:
        """Every image section that needs a description gets one attempt; a
        section that already carries text is left alone. Bytes the sink does not
        hold (an image that was never staged) are `missing_bytes`."""
        results: dict[str, ImageDescription] = {}
        issued = 0
        updated: list[RawSection] = []
        for section in sections:
            ref = section.image_ref
            if ref is None or not needs_description(section):
                updated.append(section)
                continue
            if ref not in results:
                data = assets.get(ref)
                if data is None:
                    results[ref] = ImageDescription(image_ref=ref, status="missing_bytes")
                else:
                    issued += 1
                    trace = TraceIdentifiers(
                        trace_id=trace_id,
                        request_id=f"describe-{PurePosixPath(ref).stem}",
                        span_id=f"image-{issued}",
                    )
                    results[ref] = self.describe(ref, data, trace=trace)
            outcome = results[ref]
            if outcome.status == "described":
                updated.append(
                    RawSection.model_validate(
                        {**section.model_dump(), "text": outcome.text, "described_by": self.alias}
                    )
                )
            else:
                updated.append(section)
        return tuple(updated), tuple(results.values())
