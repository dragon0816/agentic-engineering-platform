"""Feature plugin manager: several active plugins, each with its own worker,
owned capability bindings, declarative pages and bundled assets (Slice 1,
`docs/phases/FEATURE_PLUGIN_SLICE1_PLAN_20261113.md`).

An authenticated Web/CLI action, or an authorized agent action, installs a
package directly: there is no approval card, signer list or IT gate. The
package digest proves consistency only. Everything an install needs is
checked before anything is registered (compatibility, dependencies, data
marker, namespace ownership, tool collisions, bundled manifests, health of a
started worker), and a failure afterwards undoes what was done, so no half
plugin is left. The previous version keeps running until the new one is
healthy and registered.

Version switches, disabling and removal wait for quiet: they return
`plugin_busy` while the injected probe reports running work (tasks, turns,
channel flows) or a plugin call is in flight. Within a turn, a write that
succeeded under one version is refused under another (`plugin_version_stale`)
through the turn's existing `TurnEffects.operations`, so a version change can
never execute the same effect twice. Nothing is retried after a worker
failure, and no effect is promised to survive a restart.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock, RLock
from time import monotonic
from typing import Any

from pydantic import JsonValue, ValidationError

from agent.turn_effects import current as current_effects
from agent.turn_effects import effect_key
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused, InstalledCapabilities
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from common.ownership import version_key
from common.plugins import (
    MAX_RESPONSE_BYTES,
    PluginAction,
    PluginActionResult,
    PluginCapability,
    PluginContractError,
    PluginDataMarker,
    PluginErrorCode,
    PluginFailure,
    PluginManifest,
    PluginOrigin,
    PluginPackage,
    PluginReadRequest,
    PluginReadResponse,
    PluginSnapshot,
    PluginStatus,
    capability_models,
    core_api_supported,
    data_marker_problem,
    json_size,
    parse_plugin_package,
)
from host_runtime.contracts import HostLayout
from plugins import assets as bundled
from plugins.ledger import (
    LedgerUnreadable,
    PendingInstall,
    PluginLedger,
    PluginRecord,
    read_ledger,
    write_ledger,
)
from plugins.package import (
    PART_PREFIX,
    PluginStageError,
    linked,
    owned_path,
    remove_tree,
    safe_directory,
    stage_package,
    verify_staged,
)
from plugins.process import WorkerFailure, WorkerRefusal, WorkerSession, invoke, start_worker

DATA_MARKER = ".aep-data.json"
#: Seconds the Bridge allows beyond the worker's own request timeout.
BINDING_MARGIN_SECONDS = 5

_MESSAGES: dict[str, str] = {
    "plugin_package_too_large": "The plugin package exceeds the size limit.",
    "plugin_package_invalid": "The file is not a valid plugin package.",
    "plugin_path_invalid": "The plugin folder is a link or not a plain folder.",
    "plugin_staged_changed": "The installed plugin files changed since installation.",
    "plugin_version_exists": "This plugin version is already staged.",
    "plugin_version_conflict": "This version is installed with different content.",
    "plugin_downgrade_refused": "A newer version of this plugin is installed.",
    "plugin_core_api_incompatible": "The plugin needs a different AEP plugin API version.",
    "plugin_runtime_incompatible": "The plugin needs a different runtime.",
    "plugin_dependency_missing": "A plugin it requires is not installed at that version.",
    "plugin_dependency_inactive": "A plugin it requires is not active.",
    "plugin_dependent_active": "An active plugin requires this plugin.",
    "plugin_namespace_owned": "Another plugin or core capability owns this namespace.",
    "plugin_contribution_collision": "A tool name or identity is already taken.",
    "plugin_data_newer": "The plugin data was written by a newer schema version.",
    "plugin_data_foreign": "The plugin data folder belongs to another plugin.",
    "plugin_migration_unsupported": "The plugin data needs a migration, not supported yet.",
    "plugin_environment_failed": "The plugin could not be prepared on this computer.",
    "plugin_health_failed": "The plugin worker did not start healthy.",
    "plugin_worker_failed": "The plugin worker stopped or gave an invalid answer.",
    "plugin_timeout": "The plugin worker did not answer in time and was stopped.",
    "plugin_request_too_large": "The request exceeds the plugin request limit.",
    "plugin_response_too_large": "The plugin answer exceeds the response limit.",
    "plugin_busy": "Work is running; try again when it has finished.",
    "plugin_not_installed": "The plugin is not installed.",
    "plugin_not_active": "The plugin is not active.",
    "plugin_version_stale": "That plugin version is no longer the active one.",
    "plugin_route_unknown": "The plugin has no such route.",
}


def _failure(code: PluginErrorCode, message: str | None = None) -> PluginFailure:
    return PluginFailure(code=code, message=message or _MESSAGES.get(code, code))


class _CallError(Exception):
    def __init__(self, code: PluginErrorCode, message: str | None = None) -> None:
        self.code: PluginErrorCode = code
        self.message = message
        super().__init__(code)


@dataclass
class _Binding:
    capability: PluginCapability
    handler: _Handler
    input_model: type[Contract]
    output_model: type[Contract]
    timeout_seconds: float


@dataclass
class _Active:
    manifest: PluginManifest
    content_sha256: str
    root: Path
    data_root: Path
    session: WorkerSession | None = None
    bindings: dict[str, _Binding] = field(default_factory=dict)
    crashes: list[float] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)
    retired: bool = False

    @property
    def plugin_id(self) -> str:
        return self.manifest.plugin_id

    def close(self) -> None:
        self.retired = True
        with self.lock:
            if self.session is not None:
                self.session.close()
                self.session = None


class _Handler:
    """Bridge handler for one exact plugin capability version."""

    def __init__(
        self,
        manager: PluginManager,
        plugin_id: str,
        capability: PluginCapability,
        output_model: type[Contract],
    ) -> None:
        self.manager = manager
        self.plugin_id = plugin_id
        self.capability = capability
        self.output_model = output_model
        self.version = capability.spec.identity.version

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        spec = self.capability.spec
        arguments = inputs.model_dump(mode="json", exclude_none=True)
        effects = current_effects() if spec.side_effect != "read" else None
        key = None
        if effects is not None:
            key = effect_key(
                "plugin-capability",
                {
                    "plugin": self.plugin_id,
                    "tool": spec.name,
                    "actor": context.actor,
                    "namespace": context.namespace,
                    "arguments": arguments,
                },
            )
            with effects.operations_lock:
                earlier = effects.operations.get(key)
            if earlier is not None and earlier != self.version:
                raise CapabilityRefused("plugin_version_stale")
        try:
            data = await asyncio.to_thread(
                self.manager._call, self.plugin_id, self.version, spec.identity, arguments, None
            )
        except _CallError as error:
            raise CapabilityRefused(error.code) from None
        try:
            checked = self.output_model.model_validate_json(json.dumps(data), strict=True)
        except (ValidationError, TypeError, ValueError):
            raise CapabilityRefused("plugin_invocation_failed") from None
        if effects is not None and key is not None:
            with effects.operations_lock:
                effects.operations.setdefault(key, self.version)
        return checked


class PluginManager:
    """Implements `common.plugins.PluginManagerProtocol` for one workspace."""

    def __init__(
        self,
        layout: HostLayout,
        installed: InstalledCapabilities,
        *,
        reserved_names: Callable[[], Iterable[str]] | None = None,
        assets_changed: Callable[[str], None] | None = None,
        busy: Callable[[], bool] | None = None,
        interpreter: str | None = None,
    ) -> None:
        self._layout = layout
        self._installed = installed
        self._reserved = reserved_names
        self._assets_changed = assets_changed
        self._busy = busy
        self._interpreter = interpreter or sys.executable
        self._lock = RLock()
        self._active: dict[str, _Active] = {}
        self._failures: dict[str, PluginFailure] = {}
        self._inflight = 0
        self._inflight_lock = Lock()

    # -- paths ------------------------------------------------------------------------

    @property
    def _ws(self) -> Path:
        """The anchor every path this manager writes or deletes must stay under."""
        return self._layout.workspace_root

    @property
    def _root(self) -> Path:
        return self._layout.workspace_root / "plugins"

    @property
    def _packages(self) -> Path:
        return self._root / "packages"

    @property
    def _ledger_path(self) -> Path:
        return self._root / "ledger.json"

    def _data_root(self, manifest: PluginManifest) -> Path:
        identity = manifest.identity
        return self._layout.workspace_root / "plugin-data" / identity.namespace / identity.name

    def _version_dir(self, namespace: str, name: str, version: str) -> Path:
        return self._packages / namespace / name / version

    # -- small helpers ------------------------------------------------------------------

    def set_busy_probe(self, probe: Callable[[], bool] | None) -> None:
        self._busy = probe

    def _is_busy(self) -> bool:
        with self._inflight_lock:
            if self._inflight:
                return True
        probe = self._busy
        if probe is None:
            return False
        try:
            return bool(probe())
        except Exception:  # noqa: BLE001 - an unknown activity state is treated as busy
            return True

    def _owned_tree(self) -> None:
        """The plugin folders are plain folders of this workspace, or refused."""
        try:
            owned_path(self._ws, self._packages)
            owned_path(self._ws, self._ledger_path)
        except PluginStageError as error:
            raise LedgerUnreadable(error.code) from None

    def _ledger(self) -> PluginLedger:
        self._owned_tree()
        return read_ledger(self._ledger_path)

    def _write(self, ledger: PluginLedger) -> None:
        self._owned_tree()
        write_ledger(self._ledger_path, ledger)

    def _remove(self, path: Path) -> bool:
        """Delete an owned folder; a redirected path is left untouched."""
        try:
            remove_tree(path, anchor=self._ws)
        except PluginStageError:
            return False
        return True

    def _notify(self, namespace: str) -> None:
        """Refresh the live Skill/Workflow registries of `namespace`; may raise."""
        if self._assets_changed is not None:
            self._assets_changed(namespace)

    def _refreshed(self, namespace: str) -> bool:
        """`_notify` where a refresh failure must not mask a primary outcome
        (rollback, recovery, startup); False when the refresh failed."""
        try:
            self._notify(namespace)
        except Exception:  # noqa: BLE001 - the caller reports or keeps its own outcome
            return False
        return True

    @staticmethod
    def _fail(
        action: PluginAction,
        plugin_id: str | None,
        code: PluginErrorCode,
        message: str | None = None,
    ) -> PluginActionResult:
        return PluginActionResult(
            action=action, status="failed", plugin_id=plugin_id, failure=_failure(code, message)
        )

    def _status(self, record: PluginRecord) -> PluginStatus:
        active = self._active.get(record.plugin_id)
        if active is not None and active.manifest.identity == record.identity:
            manifest = active.manifest
            return PluginStatus(
                plugin_id=record.plugin_id,
                identity=record.identity,
                title=manifest.title,
                state="active",
                content_sha256=record.content_sha256,
                installed_by=record.installed_by,
                capabilities=tuple(item.spec.identity for item in manifest.tool_capabilities),
                routes=tuple(item.route_id for item in manifest.routes),
                pages=manifest.pages,
            )
        title = self._title(record)
        if record.enabled:
            return PluginStatus(
                plugin_id=record.plugin_id,
                identity=record.identity,
                title=title,
                state="failed",
                content_sha256=record.content_sha256,
                installed_by=record.installed_by,
                failure=self._failures.get(record.plugin_id) or _failure("plugin_not_active"),
            )
        return PluginStatus(
            plugin_id=record.plugin_id,
            identity=record.identity,
            title=title,
            state="disabled",
            content_sha256=record.content_sha256,
            installed_by=record.installed_by,
        )

    def _title(self, record: PluginRecord) -> str:
        identity = record.identity
        envelope = self._version_dir(identity.namespace, identity.name, identity.version)
        try:
            owned_path(self._ws, envelope / "package.json")
            text = (envelope / "package.json").read_bytes()
            return parse_plugin_package(text).manifest.title
        except (OSError, PluginContractError, PluginStageError):
            return record.plugin_id

    def snapshot(self) -> PluginSnapshot:
        """Installed plugins. An unreadable ledger raises
        `PluginContractError("plugin_environment_failed")` and a redirected
        plugin folder `PluginContractError("plugin_path_invalid")` rather than
        looking like "nothing installed"; active registrations stay as they are."""
        with self._lock:
            try:
                ledger = self._ledger()
            except LedgerUnreadable as error:
                raise PluginContractError(error.code) from None
            return PluginSnapshot(plugins=tuple(self._status(r) for r in ledger.plugins))

    # -- checks -------------------------------------------------------------------------

    def _data_problem(self, manifest: PluginManifest) -> PluginErrorCode | None:
        marker = self._data_root(manifest) / DATA_MARKER
        try:
            owned_path(self._ws, marker)
        except PluginStageError:
            return "plugin_path_invalid"
        if not marker.is_file():
            return None
        try:
            found = PluginDataMarker.model_validate_json(marker.read_bytes())
        except (OSError, ValidationError, ValueError):
            return "plugin_data_foreign"
        return data_marker_problem(manifest, found)

    def _preflight(
        self, package: PluginPackage, ledger: PluginLedger
    ) -> tuple[PluginErrorCode | None, tuple[bundled.BundledAsset, ...]]:
        manifest = package.manifest
        plugin_id = manifest.plugin_id
        namespace = manifest.identity.namespace
        if not core_api_supported(manifest):
            return "plugin_core_api_incompatible", ()
        try:
            assets = bundled.parse_assets(package)
        except PluginStageError as error:
            return error.code, ()
        if assets and bundled.folders_problem(self._layout) is not None:
            return "plugin_path_invalid", ()
        for record in ledger.plugins:
            if record.plugin_id != plugin_id and record.identity.namespace == namespace:
                return "plugin_namespace_owned", ()
        for required in manifest.requires:
            needed = ledger.get(f"{required.namespace}.{required.name}")
            if needed is None or needed.identity != required:
                return "plugin_dependency_missing", ()
            if needed.plugin_id not in self._active:
                return "plugin_dependency_inactive", ()
        problem = self._data_problem(manifest)
        if problem is not None:
            return problem, ()
        return self._collision(manifest), assets

    def _collision(self, manifest: PluginManifest) -> PluginErrorCode | None:
        namespace = manifest.identity.namespace
        current = self._active.get(manifest.plugin_id)
        own = (
            {item.spec.identity.key for item in current.manifest.capabilities}
            if current is not None
            else set()
        )
        live: list[CapabilitySpec] = [*self._installed.discover(), *self._installed.offered()]
        names: set[str] = set()
        for spec in live:
            if spec.identity.key in own:
                continue
            if spec.identity.namespace == namespace:
                return "plugin_namespace_owned"
            names.add(spec.name)
        if self._reserved is not None:
            names.update(self._reserved())
        # Only Agent tools are registered; a page service (H4) takes no tool name.
        for item in manifest.tool_capabilities:
            if item.spec.name in names:
                return "plugin_contribution_collision"
            if item.spec.identity.key not in own and self._installed.get(item.spec.identity):
                return "plugin_contribution_collision"
        return None

    # -- activation ------------------------------------------------------------------------

    def _start(self, package: PluginPackage, root: Path) -> _Active:
        manifest = package.manifest
        identity = manifest.identity
        try:
            data_root = safe_directory(
                self._ws / "plugin-data", identity.namespace, identity.name, anchor=self._ws
            )
        except PluginStageError as error:
            raise _CallError(error.code) from None
        except OSError:
            raise _CallError("plugin_environment_failed") from None
        active = _Active(manifest, package.content_sha256, root, data_root)
        for item in manifest.capabilities:
            input_model, output_model = capability_models(item)
            timeout = manifest.runtime.health.request_timeout_seconds if manifest.runtime else 30
            active.bindings[item.spec.name] = _Binding(
                item,
                _Handler(self, manifest.plugin_id, item, output_model),
                input_model,
                output_model,
                float(timeout + BINDING_MARGIN_SECONDS),
            )
        if manifest.runtime is not None:
            try:
                active.session = start_worker(
                    manifest,
                    root,
                    data_root,
                    interpreter=self._interpreter,
                    bi_root=self._bi_root(manifest),
                )
            except WorkerFailure as error:
                raise _CallError(error.code) from None
        return active

    def _bi_root(self, manifest: PluginManifest) -> Path | None:
        """The Host's own `bi/` folder for a manifest declaring it (H1), checked
        as a plain folder of this workspace; it may be missing and is never made."""
        if "bi" not in manifest.data.reads:
            return None
        try:
            return owned_path(self._ws, self._ws / "bi")
        except PluginStageError as error:
            raise _CallError(error.code) from None

    def _register(self, active: _Active) -> None:
        done: list[_Binding] = []
        try:
            for binding in self._tools(active):
                self._installed.register(
                    binding.capability.spec,
                    binding.handler,
                    binding.input_model,
                    binding.output_model,
                    ExecutionDependencies(central_required=False),
                    timeout_seconds=binding.timeout_seconds,
                )
                done.append(binding)
        except ValueError:
            for binding in done:
                self._installed.unregister(binding.capability.spec.identity)
            raise _CallError("plugin_contribution_collision") from None

    @staticmethod
    def _tools(active: _Active) -> list[_Binding]:
        """Bindings registered with the Bridge; page services (H4) are not."""
        return [b for b in active.bindings.values() if b.capability.expose_as_tool]

    def _unregister(self, active: _Active) -> None:
        for binding in self._tools(active):
            current = self._installed.get(binding.capability.spec.identity)
            if current is not None and current.handler is binding.handler:
                self._installed.unregister(binding.capability.spec.identity)

    def _write_marker(self, active: _Active) -> None:
        marker = active.data_root / DATA_MARKER
        if marker.is_file():
            return
        value = PluginDataMarker(
            plugin_id=active.plugin_id,
            schema_version=active.manifest.data.schema_version,
            written_by=active.manifest.identity,
        )
        marker.write_text(value.model_dump_json(indent=2) + "\n", encoding="utf-8")

    # -- calls -------------------------------------------------------------------------------

    def _session(self, active: _Active) -> WorkerSession:
        with active.lock:
            if active.retired:
                raise _CallError("plugin_version_stale")
            if active.session is not None and active.session.alive:
                return active.session
            runtime = active.manifest.runtime
            assert runtime is not None
            now = monotonic()
            window = 300.0
            active.crashes = [stamp for stamp in active.crashes if now - stamp <= window]
            if len(active.crashes) >= runtime.health.max_crashes:
                raise _CallError("plugin_worker_failed")
            try:
                # A replacement process loads staged code again. Recheck the
                # recorded package and data path just as on first activation.
                verify_staged(active.root, active.content_sha256, anchor=self._ws)
                owned_path(self._ws, active.data_root)
                active.session = start_worker(
                    active.manifest,
                    active.root,
                    active.data_root,
                    interpreter=self._interpreter,
                    bi_root=self._bi_root(active.manifest),
                )
            except PluginStageError as error:
                raise _CallError(error.code) from None
            except WorkerFailure as error:
                active.crashes.append(monotonic())
                raise _CallError(error.code) from None
            return active.session

    def _crashed(self, active: _Active) -> None:
        runtime = active.manifest.runtime
        with active.lock:
            active.crashes.append(monotonic())
            over = runtime is not None and len(active.crashes) >= runtime.health.max_crashes
        if not over:
            return
        with self._lock:
            if self._active.get(active.plugin_id) is active:
                self._unregister(active)
                del self._active[active.plugin_id]
                self._failures[active.plugin_id] = _failure("plugin_worker_failed")
        active.close()

    def _call(
        self,
        plugin_id: str,
        version: str,
        capability: Any,
        arguments: dict[str, JsonValue],
        timeout_seconds: float | None,
    ) -> JsonValue:
        with self._lock:
            active = self._active.get(plugin_id)
            if active is None:
                raise _CallError("plugin_not_active")
            if active.manifest.identity.version != version:
                raise _CallError("plugin_version_stale")
            with self._inflight_lock:
                self._inflight += 1
        try:
            runtime = active.manifest.runtime
            if runtime is None:
                raise _CallError("plugin_not_active")
            session = self._session(active)
            limit = float(runtime.health.request_timeout_seconds)
            timeout = limit if timeout_seconds is None else max(0.001, min(timeout_seconds, limit))
            try:
                return invoke(session, capability, arguments, timeout)
            except WorkerRefusal as refusal:
                raise _CallError(
                    "plugin_invocation_failed", f"The plugin refused the request ({refusal.code})."
                ) from None
            except WorkerFailure as error:
                if error.code != "plugin_request_too_large":
                    self._crashed(active)
                raise _CallError(error.code) from None
        finally:
            with self._inflight_lock:
                self._inflight -= 1

    def call_read(
        self, request: PluginReadRequest, *, timeout_seconds: float
    ) -> PluginReadResponse:
        def failed(code: PluginErrorCode, message: str | None = None) -> PluginReadResponse:
            return PluginReadResponse(
                request_id=request.request_id,
                plugin_id=request.plugin_id,
                version=request.version,
                route_id=request.route_id,
                status="failed",
                failure=_failure(code, message),
            )

        with self._lock:
            active = self._active.get(request.plugin_id)
        if active is None:
            return failed("plugin_not_active")
        manifest = active.manifest
        if manifest.identity.version != request.version:
            return failed("plugin_version_stale")
        try:
            route = manifest.route(request.route_id)
        except KeyError:
            return failed("plugin_route_unknown")
        binding = active.bindings[route.capability]
        try:
            inputs = binding.input_model.model_validate_json(
                json.dumps(request.arguments), strict=True
            )
        except (ValidationError, ValueError):
            return failed("plugin_invocation_failed", "The request does not match the route input.")
        try:
            data = self._call(
                request.plugin_id,
                request.version,
                binding.capability.spec.identity,
                inputs.model_dump(mode="json", exclude_none=True),
                timeout_seconds,
            )
        except _CallError as error:
            return failed(error.code, error.message)
        try:
            checked = binding.output_model.model_validate_json(json.dumps(data), strict=True)
        except (ValidationError, TypeError, ValueError):
            return failed(
                "plugin_invocation_failed", "The plugin answer does not match its declared output."
            )
        result = checked.model_dump(mode="json")
        if json_size(result) > MAX_RESPONSE_BYTES:
            return failed("plugin_response_too_large")
        return PluginReadResponse(
            request_id=request.request_id,
            plugin_id=request.plugin_id,
            version=request.version,
            route_id=request.route_id,
            status="succeeded",
            data=result,
        )

    # -- lifecycle actions ------------------------------------------------------------------

    def install(self, payload: bytes, origin: PluginOrigin) -> PluginActionResult:
        try:
            package = parse_plugin_package(payload)
        except PluginContractError as error:
            return self._fail("install", None, error.code)
        manifest = package.manifest
        plugin_id = manifest.plugin_id
        with self._lock:
            try:
                ledger = self._ledger()
            except LedgerUnreadable as error:
                return self._fail("install", plugin_id, error.code)
            record = ledger.get(plugin_id)
            if record is not None:
                new, old = (
                    version_key(manifest.identity.version),
                    version_key(record.identity.version),
                )
                if new < old:
                    return self._fail("install", plugin_id, "plugin_downgrade_refused")
                if new == old:
                    if manifest.identity != record.identity or (
                        record.content_sha256 != package.content_sha256
                    ):
                        return self._fail("install", plugin_id, "plugin_version_conflict")
                    if plugin_id in self._active:
                        return PluginActionResult(
                            action="install",
                            status="succeeded",
                            plugin_id=plugin_id,
                            plugin=self._status(record),
                        )
                    return self._activate_record("install", record, origin, ledger)
                if plugin_id in self._active and self._is_busy():
                    return self._fail("install", plugin_id, "plugin_busy")
                if self._dependents(ledger, record):
                    # Requirements are exact versions: an upgrade would strand them.
                    return self._fail("install", plugin_id, "plugin_dependent_active")
            return self._install_new(package, record, origin, ledger)

    def _install_new(
        self,
        package: PluginPackage,
        record: PluginRecord | None,
        origin: PluginOrigin,
        ledger: PluginLedger,
    ) -> PluginActionResult:
        manifest = package.manifest
        plugin_id = manifest.plugin_id
        identity = manifest.identity
        problem, assets = self._preflight(package, ledger)
        if problem is not None:
            return self._fail("install", plugin_id, problem)
        target = self._version_dir(identity.namespace, identity.name, identity.version)
        try:
            if target.exists() or linked(target):
                # An orphan of an interrupted install; no record names it.
                remove_tree(target, anchor=self._ws)
            stage_package(package, self._packages, anchor=self._ws)
            verify_staged(target, package.content_sha256, anchor=self._ws)
        except PluginStageError as error:
            if error.code != "plugin_path_invalid":
                self._remove(target)
            return self._fail("install", plugin_id, error.code)
        except OSError:
            self._remove(target)
            return self._fail("install", plugin_id, "plugin_environment_failed")
        try:
            candidate = self._start(package, target)
        except _CallError as error:
            self._remove(target)
            return self._fail("install", plugin_id, error.code)
        return self._commit("install", candidate, assets, record, origin, ledger, staged_new=True)

    def _commit(
        self,
        action: PluginAction,
        candidate: _Active,
        assets: tuple[bundled.BundledAsset, ...],
        record: PluginRecord | None,
        origin: PluginOrigin,
        ledger: PluginLedger,
        *,
        staged_new: bool,
    ) -> PluginActionResult:
        """Register, install assets and record; undo all of it on failure."""
        manifest = candidate.manifest
        plugin_id = manifest.plugin_id
        namespace = manifest.identity.namespace
        previous = self._active.get(plugin_id)
        expected = bundled.expected(assets)
        pending = PendingInstall(
            version=manifest.identity.version,
            content_sha256=candidate.content_sha256,
            new_record=record is None,
            assets=expected,
        )
        base = record or PluginRecord(
            plugin_id=plugin_id,
            identity=manifest.identity,
            content_sha256=candidate.content_sha256,
            enabled=False,
            installed_by=origin,
        )
        old_assets = base.assets if record is not None else ()
        present = bundled.present(self._layout, old_assets)
        touched = False
        try:
            self._write(ledger.put(base.model_copy(update={"pending": pending})))
            if previous is not None:
                self._unregister(previous)
            self._register(candidate)
            self._active[plugin_id] = candidate
            choices = {item.key: item.switched_on for item in old_assets}
            touched = bool(assets or old_assets)
            owned = bundled.install_assets(self._layout, assets, choices)
            self._write_marker(candidate)
            if touched and not self._refreshed(namespace):
                raise _CallError(
                    "plugin_environment_failed", "The live Skill/Workflow refresh failed."
                )
            final = PluginRecord(
                plugin_id=plugin_id,
                identity=manifest.identity,
                content_sha256=candidate.content_sha256,
                enabled=True,
                installed_by=origin if action == "install" else base.installed_by,
                assets=owned,
                # Earlier unfinished retirements carry over; one entry per file.
                retiring=tuple(
                    {
                        a.key: a
                        for a in (*base.retiring, *old_assets)
                        if a.key not in {item.key for item in owned}
                    }.values()
                ),
            )
            self._write(ledger.put(final))
        except (_CallError, OSError, LedgerUnreadable) as error:
            code: PluginErrorCode = (
                error.code
                if isinstance(error, (_CallError, LedgerUnreadable))
                else "plugin_environment_failed"
            )
            self._unregister(candidate)
            candidate.close()
            if previous is not None:
                self._active[plugin_id] = previous
                try:
                    self._register(previous)
                except _CallError:
                    self._active.pop(plugin_id, None)
                    previous.close()
                    self._failures[plugin_id] = _failure(code)
            else:
                self._active.pop(plugin_id, None)
            bundled.remove_owned(self._layout, (a for a in expected if a.key not in present))
            bundled.restore_places(self._layout, (a for a in old_assets if a.key in present))
            if staged_new:
                self._remove(candidate.root)
            try:
                self._write(ledger)
            except (OSError, LedgerUnreadable):
                pass  # the pending entry stays; the next restore undoes it
            if touched:
                self._refreshed(namespace)  # the primary failure is what is reported
            message = error.message if isinstance(error, _CallError) else None
            return self._fail(action, plugin_id, code, message)
        if final.retiring:
            bundled.remove_owned(self._layout, final.retiring)
            final = final.model_copy(update={"retiring": ()})
            try:
                self._write(ledger.put(final))
            except (OSError, LedgerUnreadable):
                pass  # the next restore finishes the removal
            # The new bundle was refreshed before the commit; this drops the old one.
            self._refreshed(namespace)
        if previous is not None and previous is not candidate:
            previous.close()
            if previous.root != candidate.root:
                self._remove(previous.root)
        if record is not None and record.identity.version != manifest.identity.version:
            self._remove(
                self._version_dir(namespace, manifest.identity.name, record.identity.version)
            )
        self._failures.pop(plugin_id, None)
        return PluginActionResult(
            action=action, status="succeeded", plugin_id=plugin_id, plugin=self._status(final)
        )

    def _activate_record(
        self,
        action: PluginAction,
        record: PluginRecord,
        origin: PluginOrigin,
        ledger: PluginLedger,
    ) -> PluginActionResult:
        identity = record.identity
        target = self._version_dir(identity.namespace, identity.name, identity.version)
        try:
            package = verify_staged(target, record.content_sha256, anchor=self._ws)
        except PluginStageError as error:
            self._failures[record.plugin_id] = _failure(error.code)
            return self._fail(action, record.plugin_id, error.code)
        problem, assets = self._preflight(package, ledger)
        if problem is not None:
            return self._fail(action, record.plugin_id, problem)
        try:
            candidate = self._start(package, target)
        except _CallError as error:
            return self._fail(action, record.plugin_id, error.code)
        return self._commit(action, candidate, assets, record, origin, ledger, staged_new=False)

    def _dependents(self, ledger: PluginLedger, record: PluginRecord) -> bool:
        key = (record.identity.namespace, record.identity.name)
        return any(
            other.plugin_id in self._active
            and any(
                (item.namespace, item.name) == key
                for item in self._active[other.plugin_id].manifest.requires
            )
            for other in ledger.plugins
            if other.plugin_id != record.plugin_id
        )

    def enable(self, plugin_id: str, origin: PluginOrigin) -> PluginActionResult:
        with self._lock:
            try:
                ledger = self._ledger()
            except LedgerUnreadable as error:
                return self._fail("enable", None, error.code)
            record = ledger.get(plugin_id)
            if record is None:
                return self._fail("enable", None, "plugin_not_installed")
            if plugin_id in self._active:
                return PluginActionResult(
                    action="enable",
                    status="succeeded",
                    plugin_id=plugin_id,
                    plugin=self._status(record),
                )
            if self._is_busy():
                return self._fail("enable", plugin_id, "plugin_busy")
            return self._activate_record("enable", record, origin, ledger)

    def _deactivate(
        self, action: PluginAction, plugin_id: str
    ) -> tuple[PluginLedger, PluginRecord] | PluginActionResult:
        """The checked ledger and record, before anything changes."""
        try:
            ledger = self._ledger()
        except LedgerUnreadable as error:
            return self._fail(action, None, error.code)
        record = ledger.get(plugin_id)
        if record is None:
            return self._fail(action, None, "plugin_not_installed")
        if self._is_busy():
            return self._fail(action, plugin_id, "plugin_busy")
        if self._dependents(ledger, record):
            return self._fail(action, plugin_id, "plugin_dependent_active")
        if action == "uninstall":
            identity = record.identity
            try:
                owned_path(self._ws, self._packages / identity.namespace / identity.name)
                owned_path(
                    self._ws,
                    self._version_dir(identity.namespace, identity.name, identity.version),
                )
            except PluginStageError as error:
                return self._fail(action, plugin_id, error.code)
        return ledger, record

    def _teardown(self, record: PluginRecord) -> None:
        """After the ledger records the change: stop, unregister, remove owned files."""
        active = self._active.pop(record.plugin_id, None)
        if active is not None:
            self._unregister(active)
            active.close()
        bundled.remove_owned(self._layout, record.assets)
        self._failures.pop(record.plugin_id, None)

    def _after_teardown(
        self, action: PluginAction, record: PluginRecord, result: PluginActionResult
    ) -> PluginActionResult:
        if record.assets and not self._refreshed(record.identity.namespace):
            done = "Disabled" if action == "disable" else "Uninstalled"
            return self._fail(
                action,
                record.plugin_id,
                "plugin_environment_failed",
                f"{done}; the live Skill/Workflow refresh failed.",
            )
        return result

    def disable(self, plugin_id: str, origin: PluginOrigin) -> PluginActionResult:
        with self._lock:
            outcome = self._deactivate("disable", plugin_id)
            if isinstance(outcome, PluginActionResult):
                return outcome
            ledger, record = outcome
            planned = bundled.planned_removal(self._layout, record.assets)
            updated = record.model_copy(update={"enabled": False, "assets": planned})
            try:
                self._write(ledger.put(updated))
            except LedgerUnreadable as error:
                return self._fail("disable", plugin_id, error.code)
            except OSError:
                return self._fail("disable", plugin_id, "plugin_environment_failed")
            self._teardown(record)
            return self._after_teardown(
                "disable",
                record,
                PluginActionResult(
                    action="disable",
                    status="succeeded",
                    plugin_id=plugin_id,
                    plugin=self._status(updated),
                ),
            )

    def uninstall(self, plugin_id: str, origin: PluginOrigin) -> PluginActionResult:
        with self._lock:
            outcome = self._deactivate("uninstall", plugin_id)
            if isinstance(outcome, PluginActionResult):
                return outcome
            ledger, record = outcome
            try:
                self._write(ledger.drop(plugin_id))
            except LedgerUnreadable as error:
                return self._fail("uninstall", plugin_id, error.code)
            except OSError:
                return self._fail("uninstall", plugin_id, "plugin_environment_failed")
            self._teardown(record)
            name_dir = self._packages / record.identity.namespace / record.identity.name
            self._remove(name_dir)
            self._remove_empty(name_dir.parent)
            return self._after_teardown(
                "uninstall",
                record,
                PluginActionResult(action="uninstall", status="succeeded", plugin_id=plugin_id),
            )

    def _remove_empty(self, folder: Path) -> None:
        try:
            owned_path(self._ws, folder)
            folder.rmdir()
        except (OSError, PluginStageError):
            pass

    # -- startup and shutdown -----------------------------------------------------------------

    def restore(self) -> PluginSnapshot:
        """Undo interrupted installs, drop partial or orphan versions and start
        every enabled plugin. Failures become `failed` states; nothing raises
        for an expected refusal, and an absent ledger creates nothing. An
        unreadable ledger keeps the Host starting: nothing is cleaned, started
        or rewritten, and `snapshot()` reports the failure."""
        with self._lock:
            try:
                ledger = self._ledger()
            except LedgerUnreadable:
                return PluginSnapshot()
            ledger = self._recover(ledger)
            self._remove_orphans(ledger)
            waiting = [r for r in ledger.plugins if r.enabled and r.plugin_id not in self._active]
            # A plugin whose requirement is not active yet waits for a later pass,
            # so requirements start first whatever the record order.
            while waiting:
                deferred = [r for r in waiting if self._restore_one(r, ledger)]
                if len(deferred) == len(waiting):
                    break
                waiting = deferred
            try:
                return self.snapshot()
            except PluginContractError:
                return PluginSnapshot()  # the ledger became unreadable; snapshot() reports it

    def _restore_one(self, record: PluginRecord, ledger: PluginLedger) -> bool:
        """Start one enabled plugin; True when it waits for a requirement."""
        identity = record.identity
        target = self._version_dir(identity.namespace, identity.name, identity.version)
        try:
            package = verify_staged(target, record.content_sha256, anchor=self._ws)
        except PluginStageError as error:
            self._failures[record.plugin_id] = _failure(error.code)
            return False
        problem, _ = self._preflight(package, ledger)
        if problem is not None:
            self._failures[record.plugin_id] = _failure(problem)
            return problem == "plugin_dependency_inactive"
        try:
            candidate = self._start(package, target)
        except _CallError as error:
            self._failures[record.plugin_id] = _failure(error.code)
            return False
        try:
            self._register(candidate)
            self._write_marker(candidate)
        except (_CallError, OSError) as error:
            self._unregister(candidate)
            candidate.close()
            code: PluginErrorCode = (
                error.code if isinstance(error, _CallError) else "plugin_environment_failed"
            )
            self._failures[record.plugin_id] = _failure(code)
            return False
        self._active[record.plugin_id] = candidate
        self._failures.pop(record.plugin_id, None)
        return False

    def _recover(self, ledger: PluginLedger) -> PluginLedger:
        changed: set[str] = set()
        updated = ledger
        for record in ledger.plugins:
            if record.retiring and record.pending is None:
                bundled.remove_owned(self._layout, record.retiring)
                updated = updated.put(record.model_copy(update={"retiring": ()}))
                changed.add(record.identity.namespace)
            pending = record.pending
            if pending is None:
                continue
            kept = {item.key for item in record.assets} if record.enabled else set()
            bundled.remove_owned(self._layout, (a for a in pending.assets if a.key not in kept))
            if record.enabled:
                bundled.restore_places(self._layout, record.assets)
            changed.add(record.identity.namespace)
            identity = record.identity
            if pending.new_record:
                updated = updated.drop(record.plugin_id)
                self._remove(self._packages / identity.namespace / identity.name)
            else:
                updated = updated.put(record.model_copy(update={"pending": None}))
                if pending.version != identity.version:
                    self._remove(
                        self._version_dir(identity.namespace, identity.name, pending.version)
                    )
        if updated != ledger:
            try:
                self._write(updated)
            except (OSError, LedgerUnreadable):
                return ledger
        for namespace in sorted(changed):
            self._refreshed(namespace)
        return updated

    def _remove_orphans(self, ledger: PluginLedger) -> None:
        """Remove partial and unrecorded versions. A redirected folder is
        neither followed nor removed; `_remove` checks every path first."""
        try:
            owned_path(self._ws, self._packages)
        except PluginStageError:
            return
        if not self._packages.is_dir():
            return
        current = {
            (r.identity.namespace, r.identity.name, r.identity.version) for r in ledger.plugins
        }
        for namespace in list(self._packages.iterdir()):
            if linked(namespace):
                continue
            if not namespace.is_dir():
                self._remove(namespace)
                continue
            for name in list(namespace.iterdir()):
                if linked(name):
                    continue
                if not name.is_dir():
                    self._remove(name)
                    continue
                for version in list(name.iterdir()):
                    if linked(version):
                        continue
                    if version.name.startswith(PART_PREFIX) or (
                        (namespace.name, name.name, version.name) not in current
                    ):
                        self._remove(version)
                self._remove_empty(name)
            self._remove_empty(namespace)

    def close(self) -> None:
        with self._lock:
            for active in list(self._active.values()):
                self._unregister(active)
                active.close()
            self._active.clear()
