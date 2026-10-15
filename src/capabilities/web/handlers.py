"""`web/read`, `web/act` and `data/select`: building blocks for generated Workflows.

`web/read` replays a recorded procedure that only reads: it may open pages,
fill fields, follow links and submit GET forms, and a click that could
change the site is refused at run time. `web/act` may change the site; it is
an external side effect and needs an approved grant. Both stay on the
origins this host allows and use one browser profile of its own, which a
person signs in to by hand when a site needs it.

`data/select` keeps the rows of a table whose cells match and returns one
column, so a later step can act once per chosen row.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

from pydantic import Field, JsonValue

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract, Text
from common.execution import RequestContext
from integrations.web_script import ScriptMode, ScriptPage, ScriptRunner, WebScript, WebScriptError

READ_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "web", "name": "read", "version": "1.0.0"},
        "name": "web.read",
        "description": "Replay a recorded web procedure that only reads; return what it read",
        "input_contract": "web.script.v1",
        "output_contract": "web.script-result.v1",
        "side_effect": "read",
        "policy": {"required_permissions": ["web.read"], "policy_refs": ["web-origin-policy"]},
    }
)

ACT_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "web", "name": "act", "version": "1.0.0"},
        "name": "web.act",
        "description": "Replay a recorded web procedure that changes the site, once per item",
        "input_contract": "web.script.v1",
        "output_contract": "web.script-result.v1",
        "side_effect": "external_side_effect",
        "policy": {
            "risk": "medium",
            "approval_required": True,
            "required_permissions": ["web.act"],
            "policy_refs": ["web-origin-policy"],
        },
    }
)

SELECT_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "data", "name": "select", "version": "1.0.0"},
        "name": "data.select",
        "description": "Keep the table rows whose cells match and return one column",
        "input_contract": "data.select.input.v1",
        "output_contract": "data.select.output.v1",
        "side_effect": "read",
        "policy": {"required_permissions": ["data.select"], "policy_refs": ["data-policy"]},
    }
)


class WebHostBinding(Contract):
    """Trusted host wiring for web steps (host.json `web`)."""

    # Origins the Agent may operate; "*" (the default) is any http or https
    # site (owner 2026-10-08: company IT governs network access).
    allowed_origins: tuple[Text, ...] = Field(default=("*",), min_length=1)
    # A profile of its own; unset means `<workspace>/web-profile`.
    profile_dir: Text | None = None
    headless: bool = True
    timeout_seconds: int = Field(default=30, ge=5, le=300)


class SelectRequest(Contract):
    rows: tuple[dict[Text, JsonValue], ...] = Field(max_length=5000)
    where: dict[Text, Text] = Field(default_factory=dict)
    take: Text


class SelectResult(Contract):
    values: tuple[Text, ...]
    count: int


class SelectHandler:
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = SelectRequest.model_validate(inputs)
        chosen = [
            row
            for row in request.rows
            if all(str(row.get(column, "")) == wanted for column, wanted in request.where.items())
        ]
        if chosen and request.take not in chosen[0]:
            raise CapabilityRefused("data_column_missing")
        values = tuple(str(row.get(request.take, "")) for row in chosen)
        return SelectResult(values=values, count=len(values))


class OpenPage(AbstractContextManager[ScriptPage]):
    """One browser for one step: started on entry, closed on exit."""

    def __init__(self, profile: Path, *, headless: bool, timeout_s: float) -> None:
        from integrations.browser import Browser

        self._browser = Browser(profile, headless=headless, timeout_s=timeout_s)

    def __enter__(self) -> ScriptPage:
        self._browser.start()
        return self._browser

    def __exit__(self, *_: object) -> None:
        self._browser.close()


class WebScriptHandler:
    def __init__(
        self,
        binding: WebHostBinding,
        profile: Path,
        mode: ScriptMode,
        *,
        page_factory: Callable[[], AbstractContextManager[ScriptPage]] | None = None,
    ) -> None:
        self.binding = binding
        self.mode: ScriptMode = mode
        self._open: Callable[[], AbstractContextManager[ScriptPage]] = page_factory or (
            lambda: OpenPage(
                profile, headless=binding.headless, timeout_s=float(binding.timeout_seconds)
            )
        )

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        script = WebScript.model_validate(inputs)
        return await asyncio.to_thread(self._run, script)

    def _run(self, script: WebScript) -> Contract:
        try:
            with self._open() as page:
                return ScriptRunner(
                    page,
                    self.binding.allowed_origins,
                    timeout_s=float(self.binding.timeout_seconds),
                ).run(script, self.mode)
        except WebScriptError as error:
            raise CapabilityRefused(error.code) from None
        except Exception as error:  # noqa: BLE001 - the browser's own typed codes
            code = getattr(error, "code", None)
            raise CapabilityRefused(str(code) if code else "web_browser_failed") from None
