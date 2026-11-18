"""Feature mount points: what a built-in or installed feature adds to the Host.

AEP core calls these hooks instead of importing a feature's modules, so a
feature (BI Knowledge first) can ship outside the core wheel and be loaded at
Host start (docs/phases/FEATURE_PLUGIN_BI_STAGE2_PROPOSAL_DRAFT_20261115.md r3).
Every hook is optional: the `Feature` base answers "nothing to add", and an
empty `FeatureSet` is a core without that feature.

The active set is process-wide, like the Host itself: `active()` returns it,
`for_host()` loads it for a workspace at Host start and `use()` pins one (tests).
Features come from in-process feature plugins (`plugins.in_process`, Plugin API
1.2): bundled with AEP or installed on the Plugins page, loaded at start; a
plugin that fails to import is skipped and reported, and AEP starts without it.
`BUILTIN` names features that are part of core itself, imported by name.
"""

from __future__ import annotations

import contextlib
import importlib
import sys
import threading
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from common.plugins import DEFAULT_PAGE_ORDER

if TYPE_CHECKING:
    from plugins.in_process import FeatureSource

#: Page slots a feature may fill (`web_page.PAGE` placeholders).
PAGE_SLOTS = ("feature_css", "knowledge_pane", "feature_js")

#: Built-in features, as `module:attribute` of a `Feature` instance.
BUILTIN: tuple[str, ...] = ()


class PackageRefused(Exception):
    """A feature's package install refused, with a sync refusal code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PreparedPackage(Protocol):
    """A checked install: `commit` writes it, `rollback` takes it back."""

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class PackageInstaller(Protocol):
    """Installs one Shared Platform package kind this feature owns."""

    def prepare(
        self,
        workspace_root: Path,
        namespace: str,
        name: str,
        version: str,
        content: bytes,
        sha256: str,
    ) -> PreparedPackage:
        """Check a package whole; raises `PackageRefused`."""
        ...


class Feature:
    """One feature's contributions. Subclasses override what they add."""

    name = "feature"
    #: Its page fragments' place in their slots: lower first, equal ones in
    #: feature order (an in-process plugin's is its manifest's
    #: `in_process.page_order`, owner 2026-11-18 D4).
    page_order = DEFAULT_PAGE_ORDER

    def startup(self, workspace_root: Path) -> None:
        """Process-wide setup when the Host is assembled."""

    def capability_bindings(
        self, workspace_root: Path, approved: Sequence[str]
    ) -> Iterable[tuple[Any, Any, Any, Any]]:
        """`(spec, handler, request, response)` to register as capabilities."""
        return ()

    def host_tools(self, gateway: Any) -> Iterable[Any]:
        """Native tools offered to the model this turn."""
        return ()

    def shipped_skills(self) -> Iterable[Any]:
        """Skills shipped switched on with every install."""
        return ()

    def public_get(self, handler: Any, path: str, query: str, workspace_root: Path) -> bool:
        """Answer a GET before the page token is checked; True when answered."""
        return False

    def refuses_post(self, path: str) -> str | None:
        """A message when POST to this public path is not allowed."""
        return None

    def handle(self, handler: Any, method: str, parsed: Any) -> bool:
        """Answer an authorized request; True when answered."""
        return False

    def turn_context(self, item: Any) -> AbstractContextManager[None]:
        """What one chat turn runs inside (a context variable, say)."""
        return contextlib.nullcontext()

    def answer_files(self, result: Any) -> list[dict[str, Any]]:
        """Files a turn's tools produced that show under the answer."""
        return []

    def answer_embeds(self, result: Any) -> list[dict[str, Any]]:
        """Embedded panels a turn's tools asked for."""
        return []

    def finish_answer(self, text: str, result: Any) -> str:
        """The answer text after this feature's own additions."""
        return text

    def bypasses_knowledge(self, message: str, gateway: Any) -> bool:
        """True when a question belongs to this feature's tools, not Knowledge."""
        return False

    def assistant_tool(self, name: str) -> Callable[..., dict[str, Any]] | None:
        """The handler of an assistant MCP tool this feature answers."""
        return None

    def askable_vaults(self, web: Any, granted: Any, entry: Any) -> list[dict[str, Any]]:
        """This feature's knowledge bases the general chat can ask."""
        return []

    def observe_catalog(self, workspace_root: Path, platform: Any, discovered: Any) -> None:
        """Note what a Shared Platform catalog read says about this feature."""

    def page_fragments(self) -> Mapping[str, str]:
        """Text for `PAGE_SLOTS`; a missing slot adds nothing."""
        return {}

    def service(self, name: str) -> Any | None:
        """A named part of this feature core code asks for (`bi_chat_save`)."""
        return None

    def package_installer(self, kind: str) -> PackageInstaller | None:
        """The installer of a Shared Platform package kind this feature owns."""
        return None


class FeatureSet:
    """The features this Host runs, asked in order."""

    def __init__(self, features: Iterable[Feature] = ()) -> None:
        self.features: tuple[Feature, ...] = tuple(features)

    def __iter__(self) -> Iterator[Feature]:
        return iter(self.features)

    def startup(self, workspace_root: Path) -> None:
        for feature in self.features:
            feature.startup(workspace_root)

    def capability_bindings(
        self, workspace_root: Path, approved: Sequence[str]
    ) -> list[tuple[Any, Any, Any, Any]]:
        return [
            binding
            for feature in self.features
            for binding in feature.capability_bindings(workspace_root, approved)
        ]

    def host_tools(self, gateway: Any) -> tuple[Any, ...]:
        return tuple(tool for feature in self.features for tool in feature.host_tools(gateway))

    def shipped_skills(self) -> tuple[Any, ...]:
        return tuple(skill for feature in self.features for skill in feature.shipped_skills())

    def public_get(self, handler: Any, path: str, query: str, workspace_root: Path) -> bool:
        return any(f.public_get(handler, path, query, workspace_root) for f in self.features)

    def refuses_post(self, path: str) -> str | None:
        for feature in self.features:
            message = feature.refuses_post(path)
            if message is not None:
                return message
        return None

    def handle(self, handler: Any, method: str, parsed: Any) -> bool:
        return any(feature.handle(handler, method, parsed) for feature in self.features)

    @contextlib.contextmanager
    def turn_context(self, item: Any) -> Iterator[None]:
        with contextlib.ExitStack() as stack:
            for feature in self.features:
                stack.enter_context(feature.turn_context(item))
            yield

    def answer_files(self, result: Any) -> list[dict[str, Any]]:
        return [entry for feature in self.features for entry in feature.answer_files(result)]

    def answer_embeds(self, result: Any) -> list[dict[str, Any]]:
        return [embed for feature in self.features for embed in feature.answer_embeds(result)]

    def finish_answer(self, text: str, result: Any) -> str:
        for feature in self.features:
            text = feature.finish_answer(text, result)
        return text

    def bypasses_knowledge(self, message: str, gateway: Any) -> bool:
        return any(feature.bypasses_knowledge(message, gateway) for feature in self.features)

    def assistant_tool(self, name: str) -> Callable[..., dict[str, Any]] | None:
        for feature in self.features:
            found = feature.assistant_tool(name)
            if found is not None:
                return found
        return None

    def askable_vaults(self, web: Any, granted: Any, entry: Any) -> list[dict[str, Any]]:
        return [
            vault
            for feature in self.features
            for vault in feature.askable_vaults(web, granted, entry)
        ]

    def observe_catalog(self, workspace_root: Path, platform: Any, discovered: Any) -> None:
        for feature in self.features:
            feature.observe_catalog(workspace_root, platform, discovered)

    def service(self, name: str) -> Any | None:
        for feature in self.features:
            found = feature.service(name)
            if found is not None:
                return found
        return None

    def package_installer(self, kind: str) -> PackageInstaller | None:
        for feature in self.features:
            found = feature.package_installer(kind)
            if found is not None:
                return found
        return None

    def page_fragments(self) -> dict[str, str]:
        joined = {slot: "" for slot in PAGE_SLOTS}
        for feature in sorted(self.features, key=lambda item: item.page_order):
            for slot, text in feature.page_fragments().items():
                if slot not in joined:
                    raise ValueError(f"feature {feature.name} fills unknown page slot {slot}")
                joined[slot] += text
        return joined


def load(references: Iterable[str]) -> FeatureSet:
    """The features named `module:attribute`, imported in order."""
    found: list[Feature] = []
    for reference in references:
        module, _, attribute = reference.partition(":")
        feature = getattr(importlib.import_module(module), attribute)
        if not isinstance(feature, Feature):
            raise TypeError(f"{reference} is not a Feature")
        found.append(feature)
    return FeatureSet(found)


@dataclass(frozen=True)
class Loaded:
    """An in-process feature plugin this process imported."""

    plugin_id: str
    version: str
    origin: str
    python_root: Path


@dataclass(frozen=True)
class LoadFailure:
    plugin_id: str
    code: str
    message: str


_lock = threading.Lock()
_active: FeatureSet | None = None
_pinned = False
_loaded: dict[str, Loaded] = {}
_failures: dict[str, LoadFailure] = {}


def loaded() -> dict[str, Loaded]:
    """The feature plugins imported by this process, by plugin id."""
    with _lock:
        return dict(_loaded)


def failures() -> dict[str, LoadFailure]:
    """Feature plugins found but not loaded at the last start, and why."""
    with _lock:
        return dict(_failures)


def _import(source: FeatureSource) -> Feature:
    spec = source.manifest.in_process
    if spec is None:
        raise TypeError(f"{source.plugin_id} is not an in-process feature")
    held = _loaded.get(source.plugin_id)
    if held is not None and held.python_root != source.python_root:
        raise RuntimeError(
            f"version {held.version} is already loaded; restart AEP to use {source.version}"
        )
    if source.origin == "installed" and spec.package not in sys.modules:
        from plugins.package import clear_bytecode

        clear_bytecode(source.python_root)
    root = str(source.python_root)
    if root not in sys.path:
        sys.path.append(root)
    module = importlib.import_module(spec.entry)
    package_file = getattr(sys.modules.get(spec.package), "__file__", None)
    if package_file is None or not Path(package_file).resolve().is_relative_to(
        source.python_root.resolve()
    ):
        raise RuntimeError(f"{spec.package} is already provided by another folder")
    feature = getattr(module, spec.attribute)
    if not isinstance(feature, Feature):
        raise TypeError(f"{spec.entry}.{spec.attribute} is not a Feature")
    feature.page_order = spec.page_order  # the manifest places its fragments
    return feature


def load_sources(sources: Iterable[FeatureSource]) -> FeatureSet:
    """Import each feature plugin; one that fails is recorded and left out."""
    found: list[Feature] = []
    for source in sources:
        try:
            feature = _import(source)
        except Exception as error:  # noqa: BLE001 - a broken plugin must not stop AEP
            with _lock:
                _failures[source.plugin_id] = LoadFailure(
                    source.plugin_id, "plugin_load_failed", f"{type(error).__name__}: {error}"[:300]
                )
            continue
        with _lock:
            _loaded[source.plugin_id] = Loaded(
                source.plugin_id, source.version, source.origin, source.python_root
            )
            _failures.pop(source.plugin_id, None)
        found.append(feature)
    return FeatureSet(found)


def _discover(workspace_root: Path | None) -> FeatureSet:
    from plugins import in_process

    sources, skipped = in_process.resolve(workspace_root)
    with _lock:
        _failures.clear()
        for item in skipped:
            _failures[item.plugin_id] = LoadFailure(item.plugin_id, item.code, item.message)
    builtin = load(BUILTIN)
    plugins = load_sources(sources)
    return FeatureSet((*builtin, *plugins))


def active() -> FeatureSet:
    """The features this process runs; without a Host start, the bundled ones."""
    global _active
    with _lock:
        current = _active
    if current is None:
        current = _discover(None)
        with _lock:
            if _active is None:
                _active = current
            current = _active
    return current


def for_host(workspace_root: Path) -> FeatureSet:
    """Load this workspace's features at Host start (a pinned set stays)."""
    global _active
    with _lock:
        if _pinned and _active is not None:
            return _active
    chosen = _discover(workspace_root)
    with _lock:
        if not _pinned:
            _active = chosen
        return _active if _active is not None else chosen


@contextlib.contextmanager
def use(features: FeatureSet) -> Iterator[FeatureSet]:
    """Run with exactly these features, then restore the previous set."""
    global _active, _pinned
    with _lock:
        previous, was_pinned = _active, _pinned
        _active, _pinned = features, True
    try:
        yield features
    finally:
        with _lock:
            _active, _pinned = previous, was_pinned
