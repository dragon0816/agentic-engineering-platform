from dataclasses import replace
from typing import Any

import pytest

from benchmarks.voice_to_knowledge.submission import (
    Claim,
    Identity,
    MockSubmission,
    Submission,
    SubmissionError,
    digest,
)


def payload() -> Submission:
    text = "Synthetic: UWB result is uncertain."
    return Submission(
        source_id="synthetic-1",
        audio_sha256="a" * 64,
        transcript=text,
        transcript_sha256=digest(text),
        skill_version="mock@0",
        model_version="fake@0",
        claims=(Claim(kind="uncertain", text=text, start=0, end=len(text)),),
    )


def identity(actor: str = "alice", tenant: str = "lab") -> Identity:
    return Identity(tenant, actor, frozenset({"draft.create", "draft.read.own"}))


def test_exact_replay_conflict_and_no_publish() -> None:
    mock = MockSubmission()
    first = mock.create(identity(), "key", payload(), "r1")
    again = mock.create(identity(), "key", payload(), "r2")
    assert first.draft_id == again.draft_id and again.request_id == "r2"
    assert first.status == "draft" and first.mock and first.revision == 1
    assert mock.read(identity(), first.draft_id).submission == payload()
    assert not hasattr(mock, "publish")
    with pytest.raises(SubmissionError, match="idempotency_conflict"):
        mock.create(identity(), "key", replace(payload(), model_version="fake@1"), "r3")


def test_permissions_checked_even_on_replay_and_cross_scope_reads() -> None:
    mock = MockSubmission()
    draft = mock.create(identity(), "key", payload(), "r1")
    with pytest.raises(SubmissionError, match="permission_denied"):
        mock.create(Identity("lab", "alice", frozenset()), "key", payload(), "r2")
    for caller in [identity("bob"), identity(tenant="other")]:
        with pytest.raises(SubmissionError, match="not_found"):
            mock.read(caller, draft.draft_id)
    assert mock.create(identity("bob"), "key", payload(), "r3").draft_id != draft.draft_id


@pytest.mark.parametrize(
    "change",
    [
        {"transcript_sha256": "0" * 64},
        {"audio_sha256": "bad"},
        {"source_id": ""},
        {"claims": (Claim(kind="fact", text="invented", start=0, end=3),)},
        {"claims": (Claim(kind="inference", text="guess", start=0, end=9),)},
        {"claims": (Claim(kind="fact", text="Synthetic", start=-1, end=8),)},
    ],
)
def test_invalid_provenance_is_refused(change: dict[str, Any]) -> None:
    with pytest.raises(SubmissionError, match="invalid_request"):
        MockSubmission().create(identity(), "key", replace(payload(), **change), "r1")


def test_inference_records_basis_but_remains_unverified() -> None:
    value = payload()
    value = replace(
        value, claims=(Claim("inference", "Needs checking", 0, 10, basis=value.transcript[:10]),)
    )
    mock = MockSubmission()
    receipt = mock.create(identity(), "key", value, "r1")
    draft = mock.read(identity(), receipt.draft_id)
    assert draft.submission.transcript == value.transcript
    assert "Needs checking" in draft.markdown
    assert draft.submission.claims[0].verification_status == "unverified"
