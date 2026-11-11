"""Closed, Host-owned browser repair scope and exact approval payloads."""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import Field, model_validator

from capabilities.browser_session.handlers import BrowserRequest
from common.assets import AssetIdentity
from common.base import Contract, Sha256, Symbol, Text
from integrations.web_script import WebAction

PREFLIGHT_SOURCE = "authoring_browser_preflight"
PREFLIGHT_TOOL = "authoring__preflight_browser"
MAX_PREFLIGHT_ACTIONS = 8
MAX_PREFLIGHT_REQUESTS = 2


def validate_actions(actions: tuple[WebAction, ...]) -> None:
    if not 1 <= len(actions) <= MAX_PREFLIGHT_ACTIONS:
        raise ValueError("preflight requires one to eight browser actions")
    if any(a.do == "download" or a.pagination is not None for a in actions):
        raise ValueError("downloads and paginated exports require the full trial")


class BrowserRepairScope(Contract):
    actor: Symbol
    session_id: Text
    candidate_id: Symbol
    trial_run_id: Symbol
    trial_digest: Sha256
    trial_arguments_digest: Sha256
    repair_attempt: int = Field(ge=1, lt=3, strict=True)
    step_index: int = Field(ge=0, strict=True)
    capability: AssetIdentity
    origins: tuple[Text, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def browser_authority(self) -> BrowserRepairScope:
        if (self.capability.namespace, self.capability.name) != ("browser", "operate"):
            raise ValueError("preflight requires an approved browser capability")
        if len(set(self.origins)) != len(self.origins):
            raise ValueError("duplicate preflight origin")
        for origin in self.origins:
            parts = urlsplit(origin)
            if (
                parts.scheme not in ("http", "https")
                or not parts.hostname
                or parts.username is not None
                or parts.password is not None
                or parts.path
                or parts.query
                or parts.fragment
                or origin != f"{parts.scheme}://{parts.netloc}".lower()
            ):
                raise ValueError("preflight origins must be literal web origins")
            _ = parts.port
        return self


class BrowserPreflightRequest(Contract):
    candidate_id: Symbol
    base_digest: Sha256
    actions: tuple[WebAction, ...] = Field(min_length=1, max_length=MAX_PREFLIGHT_ACTIONS)

    @model_validator(mode="after")
    def bounded_actions(self) -> BrowserPreflightRequest:
        validate_actions(self.actions)
        return self


class BrowserPreflightCall(Contract):
    scope: BrowserRepairScope
    candidate_digest: Sha256
    browser: BrowserRequest

    @model_validator(mode="after")
    def single_batch(self) -> BrowserPreflightCall:
        validate_actions(self.browser.actions)
        if self.browser.for_each is not None:
            raise ValueError("preflight does not run collection loops")
        return self


class BrowserPreflightApprovalArguments(Contract):
    # An older BrowserRequest rejects this envelope before invoking its handler.
    authoring_browser_preflight: BrowserPreflightCall
