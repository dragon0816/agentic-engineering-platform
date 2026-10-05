"""The Outlook draft building block (`outlook.draft`): draft, attach, never send."""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

import pytest
from test_gateway import request

from capabilities.mail_draft import handlers
from capabilities.mail_draft.handlers import (
    DRAFT_SPEC,
    MailDraftHandler,
    MailDraftRequest,
    MailDraftResult,
)
from capabilities.runtime import CapabilityRefused
from integrations.outlook_draft import DraftError, MailDraft, RecordingDraftWriter


def _run(handler: MailDraftHandler, **values: object) -> MailDraftResult:
    result = asyncio.run(handler(request("draft"), MailDraftRequest.model_validate(values)))
    assert isinstance(result, MailDraftResult)
    return result


def test_it_is_a_governed_write_with_no_send() -> None:
    assert DRAFT_SPEC.side_effect == "write"
    assert DRAFT_SPEC.policy.approval_required is True
    assert DRAFT_SPEC.policy.required_permissions == ("outlook.draft",)
    source = inspect.getsource(handlers)
    for forbidden in (".Send(", "Send()", "SendAndSave"):
        assert forbidden not in source


def test_a_draft_is_saved_with_the_document_attached(tmp_path: Path) -> None:
    document = tmp_path / "plan.docx"
    document.write_bytes(b"PK\x03\x04")
    writer = RecordingDraftWriter()
    result = _run(
        MailDraftHandler(lambda: writer),
        subject="公館站改善服務規劃", html_body="<p>已產出</p>",
        to=[" reviewer@example.com ", ""], cc=["lead@example.com"],
        attachments=[str(document)],
    )
    assert result.drafted is True and result.skipped is False
    assert result.to == ("reviewer@example.com",) and result.attachments == 1
    assert result.entry_id == "recorded-1"
    assert writer.drafts == [MailDraft(
        subject="公館站改善服務規劃", html_body="<p>已產出</p>",
        to=("reviewer@example.com",), cc=("lead@example.com",),
        attachments=(str(document),),
    )]


def test_a_skipped_step_touches_no_mailbox() -> None:
    def no_outlook() -> RecordingDraftWriter:
        raise AssertionError("Outlook must not be opened for a skipped draft")

    result = _run(MailDraftHandler(no_outlook), skip=True)
    assert result == MailDraftResult(drafted=False, skipped=True)


def test_refusals_carry_a_code_and_no_content(tmp_path: Path) -> None:
    writer = RecordingDraftWriter()
    handler = MailDraftHandler(lambda: writer)
    with pytest.raises(CapabilityRefused) as raised:
        _run(handler, subject="s", html_body="b", to=[" "])
    assert raised.value.code == "draft_recipient_missing"
    with pytest.raises(CapabilityRefused) as raised:
        _run(handler, subject=" ", html_body="b", to=["a@example.com"])
    assert raised.value.code == "draft_content_missing"
    with pytest.raises(CapabilityRefused) as raised:
        _run(handler, subject="s", html_body="b", to=["a@example.com"],
             attachments=[str(tmp_path / "absent.docx")])
    assert raised.value.code == "attachment_missing"

    class Broken:
        def save(self, draft: MailDraft) -> object:
            raise DraftError("draft_failed")

    with pytest.raises(CapabilityRefused) as raised:
        _run(MailDraftHandler(Broken), subject="s", html_body="b", to=["a@example.com"])
    assert raised.value.code == "draft_failed"
    assert writer.drafts == []


def test_a_best_effort_draft_reports_its_failure_instead_of_failing() -> None:
    class Broken:
        def save(self, draft: MailDraft) -> object:
            raise DraftError("outlook_missing")

    result = _run(MailDraftHandler(Broken), subject="s", html_body="b",
                  to=["a@example.com"], best_effort=True)
    assert result.drafted is False and result.error == "outlook_missing"
