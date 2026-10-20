"""What the ported loan jobs ask of their host (AEP port of the source's
`jobs._bridge_client`).

The source jobs spoke HTTP to the rs_workflow_system Bridge. In AEP the same
calls go to `capabilities.loan_reply.bridge.LoanBridge`, which drives this
computer's Outlook and Edge directly; tests pass fakes with the same shape.
The method names and payloads are the source's, so the ported job code and
the source tests keep reading the same.
"""

from __future__ import annotations

from typing import Any, Protocol


class BridgeClientError(RuntimeError):
    """An operation the host refused or could not finish (the source's
    `BridgeClientError`: a code and a message)."""

    def __init__(self, code: str, message: str, detail: Any = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.detail = detail


class BridgeUnavailable(ConnectionError):
    """The browser or Outlook cannot be reached at all. Like the source's
    unreachable Bridge it says nothing about the form, so the item is handed
    back to the queue rather than failed."""


class Bridge(Protocol):
    """The calls the ported jobs make. Payload keys are the source Bridge's."""

    def post(self, path: str, body: dict[str, Any], timeout: int | None = None) -> Any: ...

    def email_list(self, **kw: Any) -> Any: ...

    def email_draft(self, **kw: Any) -> Any: ...

    def browser_open(self, **kw: Any) -> Any: ...

    def browser_goto(self, session_id: str, url: str, **kw: Any) -> Any: ...

    def browser_close(self, session_id: str) -> Any: ...
