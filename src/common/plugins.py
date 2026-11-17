"""Feature plugin contract: a closed manifest, an inert package envelope and
the typed messages the plugin manager and Agent Web exchange (Slice 1,
`docs/phases/FEATURE_PLUGIN_SLICE1_PLAN_20261113.md`).

A plugin owns exactly one asset namespace: its capabilities, routes, pages and
bundled Skills/Workflows all live in `identity.namespace`, and its worker code
lives in the Python package `aep_plugin_<namespace>`. The manager lets at most
one plugin own a namespace, so ownership is decidable from an identity alone.

Nothing here executes, installs or authorizes anything. The package digest
proves the bytes are the bytes the manifest describes; it is not a signature,
a publisher trust claim or a review. Pages are structured data that the core
renders as text: there is no HTML, script, URL, link, image or action field
anywhere in the contract. A read route is an exact declared `read` capability
of the plugin's own worker, so the existing JSON-lines invoke request carries
it and no new wire protocol exists.

Plugin API 1.1 (owner consent 2026-11-15, H1/H4 only,
`docs/phases/FEATURE_PLUGIN_BI_OVERVIEW_PLAN_20261114.md`) adds two optional
fields: `PluginData.reads` declares that the worker reads an existing Host data
area (only `bi`), as context, not an access grant; and
`PluginCapability.expose_as_tool=False` marks a read capability a page route
uses as a page service, not an Agent tool. A manifest using either must declare
`core_api.minimum >= FEATURE_API_MINIMUM`. Both keys are left out of the wire
form at their defaults (and only they: every pre-existing default stays), so a
v1 package keeps its exact bytes and `content_sha256`. A Plugin API 1.0 Host has
a closed schema and refuses a package carrying either key as
`plugin_package_invalid`, before any API range check; it is not reported as
`plugin_core_api_incompatible`.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from typing import Annotated, Any, Literal, Protocol, Self

from pydantic import (
    Field,
    JsonValue,
    SerializerFunctionWrapHandler,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    ValidationError,
    create_model,
    field_validator,
    model_serializer,
    model_validator,
)

from capabilities.contracts import CapabilitySpec
from common.assets import SEMVER, AssetIdentity, RegistryContract
from common.base import Contract, Sha256, Symbol
from common.ownership import version_key

PLUGIN_MANIFEST_FORMAT: Literal["aep-plugin/1"] = "aep-plugin/1"
PLUGIN_PACKAGE_FORMAT: Literal["aep-plugin-package/1"] = "aep-plugin-package/1"
#: The Feature Plugin API this core implements; manifests declare a range.
CORE_PLUGIN_API_VERSION = "1.2.0"
#: The lowest core Plugin API a manifest using `data.reads` or a page service
#: (`expose_as_tool=False`) may declare as its `core_api.minimum`.
FEATURE_API_MINIMUM = "1.1.0"
#: The lowest core Plugin API an in-process feature plugin (`in_process`) may declare.
IN_PROCESS_API_MINIMUM = "1.2.0"
#: The existing Bridge Extension JSON-lines protocol, reused unchanged.
WORKER_PROTOCOL: Literal["aep-extension-jsonl/v1"] = "aep-extension-jsonl/v1"

# Limits. Module globals so one place states them; validators read them at call time.
MAX_PACKAGE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_FILE_BYTES = 6 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 256
MAX_PATH_LENGTH = 160
MAX_PATH_PART = 64
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
MAX_TITLE = 80
MAX_TEXT = 4000
MAX_MESSAGE = 500
MAX_STRING_FIELD = 4000
MAX_CAPABILITIES = 32
MAX_ROUTES = 32
MAX_FIELDS = 32
MAX_PAGES = 16
MAX_BLOCKS = 32
MAX_TABLE_COLUMNS = 12
MAX_TABLE_ROWS = 200
MAX_ASSETS = 64
MAX_DEPENDENCIES = 16

#: Namespaces the core or its integrations use; a plugin cannot own them.
RESERVED_NAMESPACES = frozenset(
    {
        "aep",
        "builtin",
        "company-agent",
        "core",
        "engineering",
        "host",
        "mcp",
        "native",
        "plugin",
        "plugins",
        "preview",
        "system",
    }
)

_NAMESPACE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_LOCAL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_PATH_PART = re.compile(r"^[a-z0-9_][a-z0-9_.-]*$")
_DEVICE = re.compile(r"^(?:con|prn|aux|nul|com[0-9]|lpt[0-9])$")
_WORKER_SUFFIXES = (".py", ".json")
#: Files an in-process feature plugin ships under `python/`: code and its data.
_PYTHON_SUFFIXES = (".py", ".json", ".csv", ".md", ".typed")

ShortText = Annotated[str, StringConstraints(min_length=1, max_length=MAX_TITLE, pattern=r"\S")]
LongText = Annotated[str, StringConstraints(min_length=1, max_length=MAX_TEXT, pattern=r"\S")]
Message = Annotated[str, StringConstraints(min_length=1, max_length=MAX_MESSAGE, pattern=r"\S")]
LocalId = Annotated[str, StringConstraints(max_length=40, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
FieldName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]
ModuleName = Annotated[
    str, StringConstraints(max_length=120, pattern=r"^[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*){0,3}$")
]
PluginId = Annotated[
    str,
    StringConstraints(
        max_length=81, pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$"
    ),
]
SemVer = Annotated[str, StringConstraints(max_length=64)]

PluginErrorCode = Literal[
    "plugin_package_too_large",
    "plugin_package_invalid",
    "plugin_path_invalid",
    "plugin_digest_mismatch",
    "plugin_staged_changed",
    "plugin_version_exists",
    "plugin_version_conflict",
    "plugin_downgrade_refused",
    "plugin_core_api_incompatible",
    "plugin_runtime_incompatible",
    "plugin_dependency_missing",
    "plugin_dependency_inactive",
    "plugin_dependent_active",
    "plugin_namespace_owned",
    "plugin_contribution_collision",
    "plugin_data_newer",
    "plugin_data_foreign",
    "plugin_migration_unsupported",
    "plugin_environment_failed",
    "plugin_health_failed",
    "plugin_worker_failed",
    "plugin_invocation_failed",
    "plugin_timeout",
    "plugin_request_too_large",
    "plugin_response_too_large",
    "plugin_busy",
    "plugin_not_installed",
    "plugin_not_active",
    "plugin_version_stale",
    "plugin_route_unknown",
    #: An in-process feature failed to import or start (Plugin API 1.2).
    "plugin_load_failed",
]


class PluginContractError(Exception):
    """A payload is not a plugin package. The code is the whole message: no
    payload bytes, path or manifest text is echoed."""

    def __init__(self, code: PluginErrorCode) -> None:
        self.code: PluginErrorCode = code
        super().__init__(code)


def _semver(value: str) -> str:
    if not SEMVER.fullmatch(value):
        raise ValueError("version must be a full semantic version")
    return value


def json_size(value: object) -> int:
    """Bytes of the compact UTF-8 JSON form, the size a bound applies to."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return len(text.encode("utf-8"))


def worker_package_for(namespace: str) -> str:
    """`hello-lab` -> `aep_plugin_hello_lab`; injective because namespaces have no `_`."""
    return "aep_plugin_" + namespace.replace("-", "_")


def plugin_path_problem(path: str) -> str | None:
    """Why `path` cannot name a file in a plugin package; None when it can.

    Paths are lowercase relative POSIX paths in two areas only: `worker/...`
    (`.py`/`.json`) and `assets/skills|workflows/<file>.json`. Lowercase-only
    removes case collisions on Windows; the part pattern excludes `..`, hidden
    files, drive letters, backslashes, `:` (alternate data streams), spaces
    and non-ASCII; device names and trailing dots are refused explicitly."""
    if not path or len(path) > MAX_PATH_LENGTH:
        return "path is empty or too long"
    parts = path.split("/")
    for part in parts:
        if not _PATH_PART.fullmatch(part) or len(part) > MAX_PATH_PART:
            return "path part is not a canonical lowercase name"
        if part.endswith(".") or _DEVICE.fullmatch(part.split(".", 1)[0]):
            return "path part is a reserved Windows name"
    if parts[0] == "worker":
        if len(parts) < 3 or len(parts) > 6 or not path.endswith(_WORKER_SUFFIXES):
            return "worker files are .py or .json inside the worker package"
        return None
    if parts[0] == "python":
        if len(parts) < 3 or len(parts) > 7 or not path.endswith(_PYTHON_SUFFIXES):
            return "python files are .py/.json/.csv/.md inside the python package"
        return None
    if parts[0] == "assets":
        if len(parts) != 3 or parts[1] not in {"skills", "workflows"}:
            return "assets are assets/skills/<file> or assets/workflows/<file>"
        if not parts[2].endswith(".json"):
            return "asset files are JSON manifests"
        return None
    return "path is outside the worker, python and assets areas"


def _package_path(value: str) -> str:
    problem = plugin_path_problem(value)
    if problem is not None:
        raise ValueError(problem)
    return value


# -- manifest -------------------------------------------------------------------------


class PluginApiRange(Contract):
    """Core Plugin API versions this plugin works with: `minimum <= core < below`."""

    minimum: SemVer
    below: SemVer

    @field_validator("minimum", "below")
    @classmethod
    def full_version(cls, value: str) -> str:
        return _semver(value)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if version_key(self.minimum) >= version_key(self.below):
            raise ValueError("plugin API range minimum must be below its bound")
        return self

    def includes(self, version: str) -> bool:
        key = version_key(_semver(version))
        return version_key(self.minimum) <= key < version_key(self.below)


class PluginHealth(Contract):
    startup_timeout_seconds: int = Field(default=15, ge=1, le=60, strict=True)
    request_timeout_seconds: int = Field(default=30, ge=1, le=120, strict=True)
    max_crashes: int = Field(default=3, ge=1, le=10, strict=True)


class PluginRuntime(Contract):
    """A worker module run by the AEP interpreter itself (stdlib and the
    dependencies AEP already has); nothing is installed into any environment."""

    interpreter: Literal["aep"] = "aep"
    module: ModuleName
    protocol: Literal["aep-extension-jsonl/v1"] = WORKER_PROTOCOL
    health: PluginHealth = PluginHealth()

    @property
    def module_path(self) -> str:
        """The package file holding `module`."""
        return "worker/" + self.module.replace(".", "/") + ".py"


InProcessPackage = Annotated[
    str, StringConstraints(max_length=40, pattern=r"^aep_[a-z][a-z0-9_]*$")
]


class PluginInProcess(Contract):
    """A feature loaded into the AEP process at Host start (Plugin API 1.2,
    owner 2026-11-16): `python/<package>/...` goes on the import path and
    `<entry>.<attribute>` is its `host_runtime.features.Feature`. It runs with
    AEP's own rights; installing or updating it takes effect at the next start."""

    package: InProcessPackage
    entry: ModuleName
    attribute: Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,39}$")] = (
        "FEATURE"
    )

    @model_validator(mode="after")
    def entry_in_package(self) -> Self:
        if self.package.startswith("aep_plugin_"):
            raise ValueError("aep_plugin_* names belong to worker plugins")
        if not self.entry.startswith(self.package + "."):
            raise ValueError("the entry module lives in the plugin's own python package")
        return self

    @property
    def entry_path(self) -> str:
        """The package file holding `entry`."""
        return "python/" + self.entry.replace(".", "/") + ".py"


class PluginField(Contract):
    """One closed field of a capability's input or output. `rows` (outputs
    only) is a bounded list of flat objects whose keys are `columns`."""

    name: FieldName
    type: Literal["string", "integer", "number", "boolean", "rows"]
    required: StrictBool = True
    description: ShortText | None = None
    max_length: int | None = Field(default=None, ge=1, le=MAX_STRING_FIELD, strict=True)
    columns: tuple[FieldName, ...] = Field(default=(), max_length=MAX_TABLE_COLUMNS)

    @model_validator(mode="after")
    def type_options(self) -> Self:
        if self.max_length is not None and self.type != "string":
            raise ValueError("only string fields have a maximum length")
        if (self.type == "rows") != bool(self.columns):
            raise ValueError("rows fields, and only they, declare columns")
        if len(self.columns) != len(set(self.columns)):
            raise ValueError("row columns are unique")
        return self


def _unique_fields(fields: tuple[PluginField, ...]) -> tuple[PluginField, ...]:
    names = [item.name for item in fields]
    if len(names) != len(set(names)):
        raise ValueError("field names are unique")
    return fields


class PluginCapability(RegistryContract):
    """A typed tool the plugin's worker serves; the Bridge registers it with
    models built by `capability_models`, never by importing plugin code."""

    spec: CapabilitySpec
    inputs: tuple[PluginField, ...] = Field(default=(), max_length=MAX_FIELDS)
    outputs: tuple[PluginField, ...] = Field(default=(), max_length=MAX_FIELDS)
    #: False: a page service only (a read capability a route uses), never
    #: registered as a Bridge/Agent tool. Plugin API 1.1.
    expose_as_tool: StrictBool = True

    @model_serializer(mode="wrap")
    def _wire(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if self.expose_as_tool:
            data.pop("expose_as_tool", None)  # the v1 form, byte for byte
        return data

    @field_validator("inputs", "outputs")
    @classmethod
    def unique(cls, value: tuple[PluginField, ...]) -> tuple[PluginField, ...]:
        return _unique_fields(value)

    @model_validator(mode="after")
    def honest_typed_spec(self) -> Self:
        if any(item.type == "rows" for item in self.inputs):
            raise ValueError("capability inputs are scalar fields")
        name = self.spec.name
        if (self.spec.input_contract, self.spec.output_contract) != (
            f"{name}.input",
            f"{name}.output",
        ):
            raise ValueError("plugin capability contracts are named <tool>.input/<tool>.output")
        policy = self.spec.policy
        if policy.status != "pending" or policy.reviewer is not None or policy.evidence:
            raise ValueError("a package cannot claim a review; installation is not a review")
        return self

    def output(self, name: str) -> PluginField | None:
        return next((item for item in self.outputs if item.name == name), None)


class PluginRoute(Contract):
    """`/api/plugins/<plugin_id>/<route_id>` -> one declared read capability."""

    route_id: LocalId
    capability: Symbol
    description: ShortText | None = None


class TextBlock(Contract):
    kind: Literal["text"]
    text: LongText


class MetricBlock(Contract):
    kind: Literal["metric"]
    label: ShortText
    route_id: LocalId
    field: FieldName


class TableColumn(Contract):
    key: FieldName
    label: ShortText


class TableBlock(Contract):
    kind: Literal["table"]
    title: ShortText | None = None
    route_id: LocalId
    field: FieldName
    columns: tuple[TableColumn, ...] = Field(min_length=1, max_length=MAX_TABLE_COLUMNS)

    @field_validator("columns")
    @classmethod
    def unique_columns(cls, value: tuple[TableColumn, ...]) -> tuple[TableColumn, ...]:
        if len({item.key for item in value}) != len(value):
            raise ValueError("table columns are unique")
        return value


PageBlock = Annotated[TextBlock | MetricBlock | TableBlock, Field(discriminator="kind")]


class PluginPage(Contract):
    """Declarative page data; the core renders every string as text."""

    page_id: LocalId
    title: ShortText
    blocks: tuple[PageBlock, ...] = Field(min_length=1, max_length=MAX_BLOCKS)


class PluginAsset(Contract):
    """A bundled Skill/Workflow manifest file, installed through the existing
    asset ledger; its own metadata is checked when it is installed."""

    kind: Literal["skill", "workflow"]
    identity: AssetIdentity
    path: str
    sha256: Sha256
    switched_on: StrictBool = True

    @field_validator("path")
    @classmethod
    def package_path(cls, value: str) -> str:
        return _package_path(value)

    @model_validator(mode="after")
    def kind_area(self) -> Self:
        if not self.path.startswith(f"assets/{self.kind}s/"):
            raise ValueError("an asset file lives in its kind's area")
        return self


class PluginData(Contract):
    """Version of the plugin's workspace data layout. Slice 1 has no
    migrations: data written by another schema version is refused."""

    schema_version: int = Field(default=0, ge=0, le=1_000_000, strict=True)
    #: Existing Host data areas the worker reads, as declared context (Plugin
    #: API 1.1); not an access grant and never created by installation.
    reads: tuple[Literal["bi"], ...] = Field(default=(), max_length=1)

    @model_serializer(mode="wrap")
    def _wire(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if not self.reads:
            data.pop("reads", None)  # the v1 form, byte for byte
        return data


class PluginManifest(RegistryContract):
    format: Literal["aep-plugin/1"]
    identity: AssetIdentity
    title: ShortText
    description: LongText
    core_api: PluginApiRange
    requires: tuple[AssetIdentity, ...] = Field(default=(), max_length=MAX_DEPENDENCIES)
    runtime: PluginRuntime | None = None
    capabilities: tuple[PluginCapability, ...] = Field(default=(), max_length=MAX_CAPABILITIES)
    routes: tuple[PluginRoute, ...] = Field(default=(), max_length=MAX_ROUTES)
    pages: tuple[PluginPage, ...] = Field(default=(), max_length=MAX_PAGES)
    assets: tuple[PluginAsset, ...] = Field(default=(), max_length=MAX_ASSETS)
    data: PluginData = PluginData()
    in_process: PluginInProcess | None = None

    @model_serializer(mode="wrap")
    def _wire(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if self.in_process is None:
            data.pop("in_process", None)  # the 1.0/1.1 form, byte for byte
        return data

    @property
    def plugin_id(self) -> str:
        return f"{self.identity.namespace}.{self.identity.name}"

    @property
    def worker_package(self) -> str:
        return worker_package_for(self.identity.namespace)

    def capability(self, name: str) -> PluginCapability:
        found = next((item for item in self.capabilities if item.spec.name == name), None)
        if found is None:
            raise KeyError(name)
        return found

    @property
    def tool_capabilities(self) -> tuple[PluginCapability, ...]:
        """Capabilities registered as Bridge/Agent tools."""
        return tuple(item for item in self.capabilities if item.expose_as_tool)

    @property
    def page_services(self) -> tuple[PluginCapability, ...]:
        """Read capabilities only the plugin's page routes call."""
        return tuple(item for item in self.capabilities if not item.expose_as_tool)

    def route(self, route_id: str) -> PluginRoute:
        found = next((item for item in self.routes if item.route_id == route_id), None)
        if found is None:
            raise KeyError(route_id)
        return found

    @model_validator(mode="after")
    def owned_and_cross_checked(self) -> Self:
        namespace = self.identity.namespace
        if not _NAMESPACE.fullmatch(namespace) or namespace in RESERVED_NAMESPACES:
            raise ValueError("plugin namespace is reserved or not addressable")
        if len(self.plugin_id) > 81:
            raise ValueError("plugin id is too long")
        self._check_requires(namespace)
        self._check_runtime_and_capabilities(namespace)
        self._check_routes_and_pages()
        self._check_assets(namespace)
        self._check_api_features()
        self._check_in_process()
        return self

    def _check_in_process(self) -> None:
        if self.in_process is None:
            return
        if self.runtime or self.capabilities or self.routes or self.pages or self.assets:
            raise ValueError(
                "an in-process feature declares no worker, capabilities, routes, pages or assets"
            )
        if self.data.reads:
            raise ValueError("an in-process feature reads Host data directly, not via data.reads")
        if version_key(self.core_api.minimum) < version_key(IN_PROCESS_API_MINIMUM):
            raise ValueError("an in-process feature needs plugin API 1.2 or later")

    def _check_api_features(self) -> None:
        routed = {route.capability for route in self.routes}
        for item in self.page_services:
            if item.spec.side_effect != "read" or item.spec.name not in routed:
                raise ValueError("a page service is a read capability a route uses")
        uses_features = bool(self.data.reads or self.page_services)
        if uses_features and (
            version_key(self.core_api.minimum) < version_key(FEATURE_API_MINIMUM)
        ):
            raise ValueError("data.reads and page services need plugin API 1.1 or later")

    def _check_requires(self, namespace: str) -> None:
        names = [(item.namespace, item.name) for item in self.requires]
        if len(names) != len(set(names)):
            raise ValueError("a plugin requires each other plugin once, at one exact version")
        if any(item.namespace == namespace for item in self.requires):
            raise ValueError("a plugin cannot require a plugin of its own namespace")

    def _check_runtime_and_capabilities(self, namespace: str) -> None:
        if (self.runtime is None) != (not self.capabilities):
            raise ValueError("a worker runtime is declared exactly when capabilities are")
        if self.runtime is not None:
            module = self.runtime.module
            if module != self.worker_package and not module.startswith(self.worker_package + "."):
                raise ValueError("the worker module lives in the plugin's own worker package")
        identities: set[tuple[str, str]] = set()
        names: set[str] = set()
        for item in self.capabilities:
            spec = item.spec
            prefix, _, local = spec.name.partition(".")
            if (
                spec.identity.namespace != namespace
                or spec.identity.version != self.identity.version
                or prefix != namespace
                or not _LOCAL_NAME.fullmatch(local)
            ):
                raise ValueError(
                    "capabilities are <namespace>.<name> at the plugin's namespace and version"
                )
            key = (spec.identity.namespace, spec.identity.name)
            if key in identities or spec.name in names:
                raise ValueError("capability identities and names are unique")
            identities.add(key)
            names.add(spec.name)

    def _check_routes_and_pages(self) -> None:
        by_name = {item.spec.name: item for item in self.capabilities}
        routes: dict[str, PluginCapability] = {}
        for route in self.routes:
            if route.route_id in routes:
                raise ValueError("route ids are unique")
            target = by_name.get(route.capability)
            if target is None or target.spec.side_effect != "read":
                raise ValueError("a route names one of the plugin's read capabilities")
            routes[route.route_id] = target
        page_ids = [page.page_id for page in self.pages]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("page ids are unique")
        for page in self.pages:
            for block in page.blocks:
                if isinstance(block, TextBlock):
                    continue
                target = routes.get(block.route_id)
                if target is None:
                    raise ValueError("a page block reads a declared route")
                if any(item.required for item in target.inputs):
                    raise ValueError("a page reads routes that need no input")
                field = target.output(block.field)
                if isinstance(block, MetricBlock):
                    if field is None or field.type == "rows":
                        raise ValueError("a metric shows a scalar output field")
                elif field is None or field.type != "rows":
                    raise ValueError("a table shows a rows output field")
                elif any(column.key not in field.columns for column in block.columns):
                    raise ValueError("table columns are columns of the rows field")

    def _check_assets(self, namespace: str) -> None:
        identities = [
            (item.kind, item.identity.namespace, item.identity.name) for item in self.assets
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("a bundled Skill or Workflow is declared once")
        if any(item.identity.namespace != namespace for item in self.assets):
            raise ValueError("bundled assets live in the plugin's namespace")
        paths = [item.path for item in self.assets]
        if len(paths) != len(set(paths)):
            raise ValueError("bundled asset paths are unique")


def core_api_supported(manifest: PluginManifest, core: str = CORE_PLUGIN_API_VERSION) -> bool:
    return manifest.core_api.includes(core)


# -- inert package envelope ----------------------------------------------------------------


class PluginFile(Contract):
    path: str
    sha256: Sha256
    size: int = Field(ge=0, strict=True)
    content: StrictStr

    @field_validator("path")
    @classmethod
    def package_path(cls, value: str) -> str:
        return _package_path(value)

    @model_validator(mode="after")
    def exact_bytes(self) -> Self:
        raw = self.raw
        if len(raw) != self.size or self.size > MAX_FILE_BYTES:
            raise ValueError("plugin file size does not match or exceeds the limit")
        if hashlib.sha256(raw).hexdigest() != self.sha256:
            raise ValueError("plugin file digest does not match")
        return self

    @property
    def raw(self) -> bytes:
        try:
            return base64.b64decode(self.content, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("plugin file content is base64") from None

    @classmethod
    def of(cls, path: str, raw: bytes) -> Self:
        return cls(
            path=path,
            sha256=hashlib.sha256(raw).hexdigest(),
            size=len(raw),
            content=base64.b64encode(raw).decode("ascii"),
        )


class PluginPackage(Contract):
    """Closed JSON envelope (no ZIP). `content_sha256` covers the manifest and
    every file's path, size and digest; it proves consistency, not origin."""

    format: Literal["aep-plugin-package/1"] = PLUGIN_PACKAGE_FORMAT
    manifest: PluginManifest
    files: tuple[PluginFile, ...]
    content_sha256: Sha256

    @staticmethod
    def digest_of(manifest: PluginManifest, files: tuple[PluginFile, ...]) -> str:
        document = {
            "format": PLUGIN_PACKAGE_FORMAT,
            "manifest": manifest.model_dump(mode="json"),
            "files": sorted(
                ({"path": f.path, "sha256": f.sha256, "size": f.size} for f in files),
                key=lambda item: str(item["path"]),
            ),
        }
        canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def complete_and_consistent(self) -> Self:
        if len(self.files) > MAX_FILES:
            raise ValueError("plugin package has too many files")
        if sum(item.size for item in self.files) > MAX_TOTAL_FILE_BYTES:
            raise ValueError("plugin package content exceeds the limit")
        paths = {item.path: item for item in self.files}
        if len(paths) != len(self.files):
            raise ValueError("plugin package paths are unique")
        for path in paths:
            if any(other.startswith(path + "/") for other in paths):
                raise ValueError("a plugin package path is both a file and a folder")
        manifest = self.manifest
        worker_root = f"worker/{manifest.worker_package}/"
        worker = [path for path in paths if path.startswith("worker/")]
        if manifest.runtime is None:
            if worker:
                raise ValueError("worker files need a declared runtime")
        else:
            if any(not path.startswith(worker_root) for path in worker):
                raise ValueError("worker files live in the plugin's worker package")
            if manifest.runtime.module_path not in paths:
                raise ValueError("the runtime module file is in the package")
        python = [path for path in paths if path.startswith("python/")]
        if manifest.in_process is None:
            if python:
                raise ValueError("python files need a declared in-process feature")
        else:
            root = f"python/{manifest.in_process.package}/"
            if any(not path.startswith(root) for path in python):
                raise ValueError("python files live in the feature's own python package")
            if manifest.in_process.entry_path not in paths:
                raise ValueError("the in-process entry module file is in the package")
        declared = {item.path: item for item in manifest.assets}
        present = {path for path in paths if path.startswith("assets/")}
        if present != set(declared):
            raise ValueError("asset files and declared assets match exactly")
        if any(paths[path].sha256 != item.sha256 for path, item in declared.items()):
            raise ValueError("asset file digest does not match its declaration")
        if self.content_sha256 != self.digest_of(manifest, self.files):
            raise ValueError("plugin package content digest does not match")
        return self

    def file(self, path: str) -> PluginFile:
        found = next((item for item in self.files if item.path == path), None)
        if found is None:
            raise KeyError(path)
        return found

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")

    @classmethod
    def build(cls, manifest: PluginManifest, files: Mapping[str, bytes]) -> Self:
        """Envelope for a publisher tool or a test fixture."""
        items = tuple(PluginFile.of(path, files[path]) for path in sorted(files))
        return cls(manifest=manifest, files=items, content_sha256=cls.digest_of(manifest, items))


def parse_plugin_package(payload: bytes) -> PluginPackage:
    """Bound, then validate, an envelope; refuse anything else (ZIP included)."""
    if len(payload) > MAX_PACKAGE_BYTES:
        raise PluginContractError("plugin_package_too_large")
    try:
        return PluginPackage.model_validate_json(payload)
    except (ValidationError, ValueError):
        raise PluginContractError("plugin_package_invalid") from None


# -- workspace data marker -----------------------------------------------------------------


class PluginDataMarker(Contract):
    """`.aep-data.json` in the plugin's workspace data folder."""

    plugin_id: PluginId
    schema_version: int = Field(ge=0, le=1_000_000, strict=True)
    written_by: AssetIdentity


def data_marker_problem(
    manifest: PluginManifest, marker: PluginDataMarker | None
) -> PluginErrorCode | None:
    """Whether this version can use existing data as it is; no migration exists."""
    if marker is None:
        return None
    if marker.plugin_id != manifest.plugin_id:
        return "plugin_data_foreign"
    if marker.schema_version > manifest.data.schema_version:
        return "plugin_data_newer"
    if marker.schema_version < manifest.data.schema_version:
        return "plugin_migration_unsupported"
    return None


# -- typed Bridge registration models -------------------------------------------------------

_Scalar = StrictStr | StrictInt | StrictFloat | StrictBool | None


def _model_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_") or "Plugin"


def _annotation(field: PluginField, row: type[Contract] | None) -> Any:
    if field.type == "string":
        if field.max_length is None:
            return StrictStr
        return Annotated[str, StringConstraints(strict=True, max_length=field.max_length)]
    if field.type == "integer":
        return StrictInt
    if field.type == "number":
        return StrictInt | StrictFloat
    if field.type == "boolean":
        return StrictBool
    return Annotated[tuple[row, ...], Field(max_length=MAX_TABLE_ROWS)]  # type: ignore[valid-type]


def _fields_model(name: str, fields: tuple[PluginField, ...]) -> type[Contract]:
    definitions: dict[str, Any] = {}
    for field in fields:
        row = None
        if field.type == "rows":
            row = create_model(  # type: ignore[call-overload]
                _model_name(f"{name}_{field.name}_row"),
                __base__=Contract,
                **{column: (_Scalar, None) for column in field.columns},
            )
        annotation = _annotation(field, row)
        if field.required:
            definitions[field.name] = (annotation, Field(description=field.description))
        else:
            definitions[field.name] = (
                annotation | None,
                Field(default=None, description=field.description),
            )
    model: type[Contract] = create_model(_model_name(name), __base__=Contract, **definitions)
    return model


def capability_models(capability: PluginCapability) -> tuple[type[Contract], type[Contract]]:
    """Closed input and output models for `InstalledCapabilities.register`,
    built from the declaration alone (no plugin code is imported)."""
    return (
        _fields_model(capability.spec.input_contract, capability.inputs),
        _fields_model(capability.spec.output_contract, capability.outputs),
    )


# -- manager and Web messages ----------------------------------------------------------------

PluginState = Literal["active", "disabled", "failed"]
PluginAction = Literal["install", "enable", "disable", "uninstall"]


class PluginOrigin(Contract):
    """Who asked, through which authenticated channel; recorded, not a permission."""

    actor: Symbol
    channel: Symbol
    source: ShortText | None = None
    turn_ref: Symbol | None = None


class PluginFailure(Contract):
    code: PluginErrorCode
    message: Message


class PluginStatus(Contract):
    plugin_id: PluginId
    identity: AssetIdentity
    title: ShortText
    state: PluginState
    content_sha256: Sha256
    installed_by: PluginOrigin
    failure: PluginFailure | None = None
    capabilities: tuple[AssetIdentity, ...] = ()
    routes: tuple[LocalId, ...] = ()
    pages: tuple[PluginPage, ...] = ()
    #: Plugin API 1.2: an in-process feature, and whether what this process
    #: loaded differs from what the next AEP start loads.
    in_process: StrictBool = False
    restart_required: StrictBool = False

    @model_serializer(mode="wrap")
    def _wire(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        for key in ("in_process", "restart_required"):
            if not data.get(key):
                data.pop(key, None)  # the 1.0/1.1 form
        return data

    @model_validator(mode="after")
    def state_shape(self) -> Self:
        if self.plugin_id != f"{self.identity.namespace}.{self.identity.name}":
            raise ValueError("plugin id names its identity")
        if self.state == "active" and self.failure is not None:
            raise ValueError("an active plugin carries no failure")
        if self.state == "failed" and self.failure is None:
            raise ValueError("a failed plugin carries its actual failure")
        if self.state != "active" and (self.capabilities or self.routes or self.pages):
            raise ValueError("an inactive plugin exposes no contributions")
        return self


class PluginSnapshot(Contract):
    plugins: tuple[PluginStatus, ...] = ()
    #: Feature plugins shipped with AEP and not replaced by an installed copy
    #: (Plugin API 1.2); they cannot be uninstalled, only switched off.
    bundled: tuple[PluginStatus, ...] = ()

    @model_serializer(mode="wrap")
    def _wire(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if not self.bundled:
            data.pop("bundled", None)
        return data

    @model_validator(mode="after")
    def one_owner(self) -> Self:
        namespaces = [item.identity.namespace for item in self.plugins]
        if len(namespaces) != len(set(namespaces)):
            raise ValueError("one installed plugin owns a namespace")
        return self

    def get(self, plugin_id: str) -> PluginStatus | None:
        return next((item for item in self.plugins if item.plugin_id == plugin_id), None)


class PluginActionResult(Contract):
    action: PluginAction
    status: Literal["succeeded", "failed"]
    plugin_id: PluginId | None = None
    plugin: PluginStatus | None = None
    failure: PluginFailure | None = None

    @model_validator(mode="after")
    def outcome_shape(self) -> Self:
        if (self.status == "succeeded") != (self.failure is None):
            raise ValueError("a failed action carries its failure; success has none")
        if self.status == "succeeded" and self.action != "uninstall" and self.plugin is None:
            raise ValueError("a succeeded action returns the plugin's status")
        if self.plugin is not None and self.plugin.plugin_id != self.plugin_id:
            raise ValueError("the returned status is the named plugin's")
        return self


class PluginReadRequest(Contract):
    """One authenticated Web read: an exact installed version and route."""

    request_id: Symbol
    plugin_id: PluginId
    version: SemVer
    route_id: LocalId
    arguments: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("version")
    @classmethod
    def full_version(cls, value: str) -> str:
        return _semver(value)

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if json_size(self.arguments) > MAX_REQUEST_BYTES:
            raise ValueError("plugin request exceeds the limit")
        return self


class PluginReadResponse(Contract):
    request_id: Symbol
    plugin_id: PluginId
    version: SemVer
    route_id: LocalId
    status: Literal["succeeded", "failed"]
    data: JsonValue = None
    failure: PluginFailure | None = None

    @model_validator(mode="after")
    def honest_and_bounded(self) -> Self:
        if (self.status == "succeeded") != (self.failure is None):
            raise ValueError("a failed read carries its failure; success has none")
        if self.status == "failed" and self.data is not None:
            raise ValueError("a failed read returns no data")
        if json_size(self.data) > MAX_RESPONSE_BYTES:
            raise ValueError("plugin response exceeds the limit")
        return self


class PluginManagerProtocol(Protocol):
    """What Host, Web and CLI use; no HostRuntime or Web handler is exposed.

    `install` takes envelope bytes; every method returns a typed outcome
    rather than raising for an expected refusal. `call_read` maps the route
    to its declared read capability and the worker's actual answer."""

    def snapshot(self) -> PluginSnapshot: ...

    def install(self, payload: bytes, origin: PluginOrigin) -> PluginActionResult: ...

    def enable(self, plugin_id: str, origin: PluginOrigin) -> PluginActionResult: ...

    def disable(self, plugin_id: str, origin: PluginOrigin) -> PluginActionResult: ...

    def uninstall(self, plugin_id: str, origin: PluginOrigin) -> PluginActionResult: ...

    def call_read(
        self, request: PluginReadRequest, *, timeout_seconds: float
    ) -> PluginReadResponse: ...

    def set_busy_probe(self, probe: Callable[[], bool] | None) -> None: ...

    def close(self) -> None: ...
