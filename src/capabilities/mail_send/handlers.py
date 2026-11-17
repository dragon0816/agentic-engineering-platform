"""Send a saved Outlook draft through the signed-in service identity."""

import asyncio
from collections.abc import Callable

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract, Sha256, Text
from common.execution import RequestContext
from integrations.outlook_send import DraftSender, SendError

SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "outlook", "name": "send-draft", "version": "1.0.0"},
        "name": "outlook.send_draft",
        "description": (
            "Send a saved draft when sending was requested. Use entry_id/fingerprint "
            "from outlook/draft output; never ask the user for this technical receipt. "
            "Does not create a draft or ask for AEP approval. Outlook/IT permissions apply."
        ),
        "input_contract": "outlook.send-draft.input.v1",
        "output_contract": "outlook.send-draft.output.v1",
        "side_effect": "external_side_effect",
        "policy": {"approval_required": False, "required_permissions": [], "policy_refs": []},
    }
)


class MailSendRequest(Contract):
    entry_id: Text
    fingerprint: Sha256


class MailSendResult(Contract):
    entry_id: Text
    sent: bool


class MailSendHandler:
    def __init__(self, sender: Callable[[], DraftSender]) -> None:
        self.sender = sender

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = MailSendRequest.model_validate(inputs)
        try:
            await asyncio.to_thread(self.sender().send, request.entry_id, request.fingerprint)
        except SendError as error:
            raise CapabilityRefused(error.code) from None
        return MailSendResult(entry_id=request.entry_id, sent=True)
