"""No model transport is used before host-admin data approval is checked."""

from collections.abc import Iterator

from common.execution import TraceIdentifiers
from models.approved import ApprovedModelClient
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelStreamEvent


class ForbiddenTransport:
    def generate(self, request: ModelRequest) -> ModelResponse:
        raise AssertionError("unapproved request reached the provider")

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise AssertionError("unapproved stream reached the provider")
        yield  # pragma: no cover


def test_unapproved_generate_and_stream_never_contact_provider() -> None:
    request = ModelRequest(
        trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
        model_alias="company",
        messages=(ModelMessage(role="user", text="sensitive context"),),
    )
    client = ApprovedModelClient(ForbiddenTransport(), None)
    answer = client.generate(request)
    assert answer.failure is not None and answer.failure.code == "gateway_not_approved"
    events = tuple(client.stream(request))
    assert len(events) == 1 and events[0].kind == "failed"
    assert events[0].failure is not None and events[0].failure.code == "gateway_not_approved"
    assert "sensitive context" not in repr(answer)
