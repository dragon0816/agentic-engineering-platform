"""`desktop/operate@1.0.0`: operate a registered Windows application for a task (lab gap L2).

Owner direction 2026-10-06: desktop applications are operated through Windows
UI Automation with what .NET Framework already provides, no third-party
package. The work is done by `integrations.desktop`, a small compiled helper
that addresses controls by AutomationId.

One call optionally starts the application, replays a short list of actions
(set, invoke, select_row, read, read_table, dialog, dismiss, save_as,
wait_dialog, wait) against that application's own windows and returns what
they read plus a look at the window: its controls with their ids, values and
enabled state, and any open dialog's title, texts and buttons. The process
stays up between calls, so a conversation can work through the application
step by step, and a drafted Workflow can carry the same actions as a step.

Bounds: only applications the host registered (`desktop.applications` in
host.json) are started, and only that process's windows are touched (the
helper is given its pid); a Save As path must lie in an `output/` folder of a
task workspace under an allowed root; window content is data returned to the
caller, never instructions.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import Field, JsonValue, model_validator

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract, Symbol, Text
from common.execution import RequestContext
from integrations.desktop import DesktopToolError, ensure_helper, run_actions

SPEC = CapabilitySpec.model_validate({
    "identity": {"namespace": "desktop", "name": "operate", "version": "1.0.0"},
    "name": "desktop.operate",
    "description": "Operate a registered Windows application: set, invoke, read, export",
    "input_contract": "desktop.operate.input.v1",
    "output_contract": "desktop.operate.output.v1",
    "side_effect": "external_side_effect",
    "policy": {
        "risk": "medium",
        "approval_required": True,
        "required_permissions": ["desktop.operate"],
        "policy_refs": ["desktop-application-policy"],
    },
})
MAX_LOOK_CHARS = 8_000

ActionKind = Literal["set", "invoke", "select_row", "read", "read_table", "dialog", "dismiss",
                     "save_as", "wait_dialog", "wait"]
_NEEDS: dict[str, tuple[str, ...]] = {
    "set": ("id", "value"),
    "invoke": ("id",),
    "select_row": ("id", "name"),
    "read": ("id", "save_as"),
    "read_table": ("id", "save_as"),
    "save_as": ("path",),
}


class DesktopApplication(Contract):
    """One application this host may start and operate (host.json `desktop.applications`)."""

    name: Symbol
    command: tuple[Text, ...] = Field(min_length=1)
    # Substring of the main window's title; empty takes the process's first window.
    window_title: str = ""


class DesktopHostBinding(Contract):
    """Trusted host wiring for `desktop/operate` (host.json `desktop`)."""

    applications: tuple[DesktopApplication, ...] = Field(min_length=1)
    timeout_seconds: int = Field(default=180, ge=10, le=900, strict=True)
    # A Save As target must lie in an `output/` folder of a workspace under one of these.
    workspace_roots: tuple[Text, ...] = ()

    def application(self, name: str) -> DesktopApplication | None:
        return next((item for item in self.applications if item.name == name), None)


class DesktopAction(Contract):
    """One step; controls are addressed by their UI Automation id (AutomationId)."""

    do: ActionKind
    id: str | None = None
    # `set`: the text, or a combobox item's name ("" selects the blank item).
    value: str | None = None
    # `select_row`: the row's name, i.e. its first cell.
    name: str | None = None
    save_as: Symbol | None = None
    # `save_as`: absolute file path in a task workspace's output folder.
    path: str | None = None
    # `wait_dialog`: part of the dialog title; `dismiss`: the button to press (default: first).
    title: str | None = None
    button: str | None = None
    seconds: float | None = Field(default=None, ge=0, le=60)

    @model_validator(mode="after")
    def _complete(self) -> DesktopAction:
        missing = [field for field in _NEEDS.get(self.do, ()) if getattr(self, field) is None]
        if missing:
            raise ValueError(f"`{self.do}` needs {', '.join(missing)}")
        return self


class DesktopRequest(Contract):
    app: Symbol
    # Start the application if it is not running (it is started on demand anyway).
    launch: bool = False
    actions: tuple[DesktopAction, ...] = Field(default=(), max_length=50)
    # Run values for `{placeholders}` in an action's value, name, path or title,
    # so a Workflow step replays the same actions with new values.
    values: dict[Symbol, JsonValue] = Field(default_factory=dict)
    look: bool = True


class DesktopResult(Contract):
    app: Symbol
    data: dict[Symbol, JsonValue] = Field(default_factory=dict)
    look: str = ""


class Process(Protocol):
    pid: int

    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


Runner = Callable[[dict[str, Any], float], dict[str, Any]]
Launcher = Callable[[list[str]], Process]


class DesktopSessionHandler:
    """Keeps one process per registered application and serializes its use."""

    def __init__(
        self,
        binding: DesktopHostBinding,
        cache_dir: Path,
        *,
        runner: Runner | None = None,
        launcher: Launcher | None = None,
    ) -> None:
        self.binding = binding
        self.cache_dir = cache_dir
        self.workspace_roots = tuple(Path(root).resolve() for root in binding.workspace_roots)
        self._runner = runner or self._helper
        self._launcher: Launcher = launcher or _popen
        self._processes: dict[str, Process] = {}
        self._lock = threading.Lock()

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = DesktopRequest.model_validate(inputs)
        return await asyncio.to_thread(self.run, request)

    def close(self) -> None:
        with self._lock:
            for process in self._processes.values():
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(10)
                    except Exception:  # noqa: BLE001 - closing is best effort
                        pass
            self._processes.clear()

    def _helper(self, request: dict[str, Any], timeout_s: float) -> dict[str, Any]:
        return run_actions(ensure_helper(self.cache_dir), request, timeout_s)

    def _process(self, app: DesktopApplication) -> Process:
        running = self._processes.get(app.name)
        if running is not None and running.poll() is None:
            return running
        try:
            started = self._launcher(list(app.command))
        except OSError:
            raise CapabilityRefused("desktop_app_would_not_start") from None
        self._processes[app.name] = started
        return started

    def _save_path(self, raw: str) -> str:
        path = Path(raw.strip())
        if not path.is_absolute():
            raise CapabilityRefused("desktop_path_not_allowed")
        resolved = path.resolve()
        for root in self.workspace_roots:
            if root not in resolved.parents:
                continue
            # The file sits somewhere under an `output` folder below the root.
            if "output" in resolved.relative_to(root).parts[:-1]:
                if resolved.exists():
                    # Save As would stop on its overwrite question.
                    raise CapabilityRefused("desktop_path_exists")
                resolved.parent.mkdir(parents=True, exist_ok=True)
                return str(resolved)
        raise CapabilityRefused("desktop_path_not_allowed")

    def run(self, request: DesktopRequest) -> DesktopResult:
        app = self.binding.application(request.app)
        if app is None:
            raise CapabilityRefused("desktop_app_not_allowed")
        actions: list[dict[str, Any]] = []
        for action in request.actions:
            item = action.model_dump(exclude_none=True)
            for field in ("value", "name", "path", "title"):
                if isinstance(item.get(field), str):
                    item[field] = _fill(item[field], request.values)
            if action.do == "save_as" and isinstance(item.get("path"), str):
                item["path"] = self._save_path(item["path"])
            actions.append(item)
        with self._lock:
            process = self._process(app)
            helper_request = {"pid": process.pid, "window": app.window_title,
                              "actions": actions, "look": request.look}
            try:
                answer = self._runner(helper_request, float(self.binding.timeout_seconds))
            except DesktopToolError as error:
                raise CapabilityRefused(error.code) from None
        if not answer.get("ok"):
            code = str(answer.get("code") or "failed")
            raise CapabilityRefused(code if code.startswith("desktop_") else f"desktop_{code}")
        data = answer.get("data")
        look = answer.get("look")
        return DesktopResult(
            app=app.name,
            data=data if isinstance(data, dict) else {},
            look=described(look) if request.look and isinstance(look, dict) else "",
        )


_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _fill(text: str, values: dict[str, JsonValue]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values or values[name] is None:
            raise CapabilityRefused("desktop_value_missing")
        return str(values[name])

    return _PLACEHOLDER.sub(replace, text)


def _popen(command: list[str]) -> Process:
    return subprocess.Popen(command)


def _value(text: Any) -> str:
    return " ".join(str(text).split())


def described(look: dict[str, Any], limit: int = MAX_LOOK_CHARS) -> str:
    """The helper's look as compact text a model reads."""
    lines = [f"Window: {look.get('title', '')}", "Controls (id [type] value):"]

    def control_lines(controls: Any, indent: str) -> None:
        for control in controls if isinstance(controls, list) else []:
            if not isinstance(control, dict):
                continue
            line = f"{indent}{control.get('id', '')} [{control.get('type', '')}]"
            name = control.get("name")
            if name and name != control.get("id"):
                line += f" '{_value(name)}'"
            if "value" in control:
                line += f" = {_value(control['value'])!r}"
            if control.get("enabled") is False:
                line += " (disabled)"
            lines.append(line)

    control_lines(look.get("controls"), "  ")
    dialogs = look.get("dialogs")
    for dialog in dialogs if isinstance(dialogs, list) else []:
        if not isinstance(dialog, dict):
            continue
        lines.append(f"Dialog: {dialog.get('title', '')}")
        for text in dialog.get("texts") or []:
            lines.append(f"  text: {_value(text)}")
        buttons = dialog.get("buttons") or []
        if buttons:
            lines.append("  buttons: " + ", ".join(str(button) for button in buttons))
        control_lines(dialog.get("controls"), "  ")
    text = "\n".join(lines)
    return text if len(text) <= limit else text[:limit] + "\n…"
