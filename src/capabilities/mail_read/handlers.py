"""`outlook.search` and `outlook.read`: the person's mail, read only, in their scope.

The scope (folders, days back, excluded senders and folders) is the one set
in Agent Web Settings > Agent mode, read on every call, so a Workflow and the
coding agent see the same mail. Bodies have credential-shaped text cut out.
Nothing here writes to the mailbox; attachments are saved only by the
agent-mode tool, into the conversation's own folder.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime

from pydantic import Field

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.assets import REDACTED, SECRET_PATTERN
from common.base import Contract
from common.execution import RequestContext
from integrations.outlook_mail import (
    MailError,
    MailReader,
    MailScope,
    read,
    search,
)


def _spec(name: str, description: str) -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": {"namespace": "outlook", "name": name, "version": "1.0.0"},
            "name": f"outlook.{name}",
            "description": description,
            "input_contract": f"outlook.{name}.input.v1",
            "output_contract": f"outlook.{name}.output.v1",
            "side_effect": "read",
            "policy": {
                "risk": "low",
                "approval_required": False,
                "required_permissions": [f"outlook.{name}"],
                "policy_refs": ["outlook-read-policy"],
            },
        }
    )


SEARCH_SPEC = _spec(
    "search",
    "Search the person's Outlook mail within the scope set in "
    "Settings (folders, days, excluded senders); read only",
)
READ_SPEC = _spec("read", "Read one Outlook message within the scope set in Settings; read only")


class MailSearchRequest(Contract):
    query: str = Field(default="", max_length=400)
    sender: str = Field(default="", max_length=200)
    folder: str = Field(default="", max_length=200)
    days: int | None = Field(default=None, ge=1, le=365)
    limit: int = Field(default=20, ge=1, le=50)


class MailSearchItem(Contract):
    message_id: str
    folder: str
    sender: str
    to: str = ""
    subject: str = ""
    received: datetime
    attachments: tuple[str, ...] = ()
    snippet: str = ""


class MailSearchResult(Contract):
    messages: tuple[MailSearchItem, ...] = ()


class MailReadRequest(Contract):
    message_id: str = Field(min_length=1, max_length=400)


class MailReadResult(MailSearchItem):
    cc: str = ""
    body: str = ""


def scrub(text: str) -> str:
    """Credential-shaped text cut out: a secret is never read into a conversation."""
    return SECRET_PATTERN.sub(REDACTED, text)


class MailSearchHandler:
    def __init__(self, reader: Callable[[], MailReader], scope: Callable[[], MailScope]) -> None:
        self._reader, self._scope = reader, scope

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = MailSearchRequest.model_validate(inputs)
        try:
            found = await asyncio.to_thread(
                lambda: search(
                    self._reader(),
                    self._scope(),
                    query=request.query,
                    sender=request.sender,
                    folder=request.folder,
                    days=request.days,
                    limit=request.limit,
                )
            )
        except MailError as error:
            raise CapabilityRefused(error.code) from None
        return MailSearchResult(
            messages=tuple(
                MailSearchItem(
                    **{
                        **item.model_dump(),
                        "snippet": scrub(item.snippet),
                        "subject": scrub(item.subject),
                    }
                )
                for item in found
            )
        )


class MailReadHandler:
    def __init__(self, reader: Callable[[], MailReader], scope: Callable[[], MailScope]) -> None:
        self._reader, self._scope = reader, scope

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = MailReadRequest.model_validate(inputs)
        try:
            message = await asyncio.to_thread(
                lambda: read(self._reader(), self._scope(), request.message_id)
            )
        except MailError as error:
            raise CapabilityRefused(error.code) from None
        data = message.model_dump()
        data.update(
            body=scrub(message.body), snippet=scrub(message.snippet), subject=scrub(message.subject)
        )
        return MailReadResult(**data)
