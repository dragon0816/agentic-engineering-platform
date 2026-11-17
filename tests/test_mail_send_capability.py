"""Draft intent and send intent stay distinct; execution has no AEP approval."""

import asyncio

from test_gateway import request

from capabilities.mail_draft.handlers import MailDraftHandler, MailDraftRequest, MailDraftResult
from capabilities.mail_send.handlers import MailSendHandler, MailSendRequest, MailSendResult
from integrations.outlook_draft import RecordingDraftWriter
from integrations.outlook_send import RecordingDraftSender


def test_draft_sends_nothing_and_explicit_send_uses_the_saved_receipt() -> None:
    writer = RecordingDraftWriter()
    sender = RecordingDraftSender()
    draft = asyncio.run(
        MailDraftHandler(lambda: writer)(
            request("draft"),
            MailDraftRequest(
                subject="fixture",
                html_body="<p>fixture</p>",
                to=("fixture@example.test",),
            ),
        )
    )
    assert isinstance(draft, MailDraftResult) and draft.drafted
    assert sender.sent == [] and draft.fingerprint
    sender.fingerprints[draft.entry_id] = draft.fingerprint
    sent = asyncio.run(
        MailSendHandler(lambda: sender)(
            request("send"),
            MailSendRequest(
                entry_id=draft.entry_id,
                fingerprint=draft.fingerprint,
            ),
        )
    )
    assert isinstance(sent, MailSendResult) and sent.sent
    assert sender.sent == [draft.entry_id]
