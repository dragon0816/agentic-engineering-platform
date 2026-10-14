"""Scoped assets, governance and explicit execution dependency metadata."""

import re
from typing import Annotated, Any, Literal, Self

from pydantic import (
    Field,
    JsonValue,
    SerializerFunctionWrapHandler,
    StrictBool,
    StrictStr,
    field_validator,
    model_serializer,
    model_validator,
)

from common.base import Contract, Sha256, Slug, Symbol, Text

SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?",
    re.ASCII,
)
SECRET_KEYS = r"password|api[_-]?key|access[_-]?token|secret[_-]?value|bot[_-]?token"
# What stands where a credential was. Named here because the pattern below
# must know it: a redaction is not itself a credential.
REDACTED = "[redacted]"
# What credential material looks like in text. Each alternative spans the
# whole secret, a quoted value with spaces in it or a private key block to
# its END line or the end of the text, so that a substitution removes all of
# it and not only its first word. None of them matches `REDACTED`, so the
# same pattern detects a credential and refuses to see one in its own
# replacement. `models.wire`, `common.evaluation`, `common.trace` and
# `channels.telegram` all detect and redact with this one definition. The
# last alternative is the shape of a Telegram bot token, which travels inside
# the Bot API URL and so would otherwise surface in any transport error.
SECRET_PATTERN = re.compile(
    rf"(?:{SECRET_KEYS})\s*[=:]\s*(?!\[redacted\])(?:\"[^\"]*\"|'[^']*'|\S+)"
    r"|\bBearer\s+(?!\[redacted\])\S+"
    r"|-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----[\s\S]*?(?:-----END (?:[A-Z]+ )?PRIVATE KEY-----|\Z)"
    r"|(?<!\d)\d{8,10}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)
# A field named for a secret holds one whatever the shape of its value.
SECRET_FIELD = re.compile(rf"^(?:{SECRET_KEYS})$", re.IGNORECASE)


def reject_embedded_secrets(value: object) -> None:
    """Reject recognizable credential material without echoing it in our errors."""
    if isinstance(value, str) and SECRET_PATTERN.search(value):
        raise ValueError("asset text must not contain credentials; declare a SecretRef")
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and SECRET_FIELD.fullmatch(key):
                raise ValueError("asset fields must not contain credential values")
            reject_embedded_secrets(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            reject_embedded_secrets(item)


class RegistryContract(Contract):
    @model_validator(mode="after")
    def no_embedded_credentials(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class AssetIdentity(Contract):
    namespace: Slug
    name: Slug
    version: Text

    @field_validator("version")
    @classmethod
    def semantic_version(cls, value: str) -> str:
        if not SEMVER.fullmatch(value):
            raise ValueError("version must be a full semantic version")
        return value

    @property
    def key(self) -> tuple[str, str, str]:
        return self.namespace, self.name, self.version


class Owner(Contract):
    type: Literal["user", "team", "organization", "service"]
    id: Symbol


class Review(Contract):
    status: Literal["pending", "approved", "rejected", "not_required"] = "pending"
    reviewer: Symbol | None = None
    evidence: Text | None = None

    @model_validator(mode="after")
    def decision_evidence(self) -> Self:
        if self.status != "pending" and (self.reviewer is None or self.evidence is None):
            raise ValueError("review decisions require reviewer and evidence")
        return self


class BusinessApproval(Review):
    """Domain correctness review; never grants runtime permission."""


class TechnicalPolicy(Review):
    risk: Literal["low", "medium", "high", "critical"] = "low"
    approval_required: StrictBool = True
    required_permissions: tuple[Symbol, ...] = ()
    policy_refs: tuple[Text, ...] = ()
    assessment: Literal["manual", "automated"] = "manual"

    @model_validator(mode="after")
    def privileged_review(self) -> Self:
        if self.risk in {"high", "critical"} and not self.approval_required:
            raise ValueError("high-risk capabilities require an explicit approval policy")
        if self.approval_required and self.status == "not_required":
            raise ValueError("required technical approval cannot be marked not_required")
        return self


class SecretRef(Contract):
    """Symbolic requirement; no value or backend fields are accepted."""

    name: Symbol


class CentralService(Contract):
    name: Symbol
    required: StrictBool


class ExecutionDependencies(Contract):
    local_capabilities: tuple[Symbol, ...] = ()
    central_services: tuple[CentralService, ...] = ()
    central_required: StrictBool

    @model_validator(mode="after")
    def explicit_connectivity(self) -> Self:
        if self.central_required != any(service.required for service in self.central_services):
            raise ValueError("central_required must match required central services")
        names = [service.name for service in self.central_services]
        if len(names) != len(set(names)):
            raise ValueError("central service names must be unique")
        if len(self.local_capabilities) != len(set(self.local_capabilities)):
            raise ValueError("local capability names must be unique")
        return self


class ExecutionLocation(Contract):
    mode: Literal["local", "central"]


class Provenance(Contract):
    source: Text
    revision: Text | None = None
    author: Symbol | None = None


class Compatibility(Contract):
    contract_version: Literal["1"] = "1"
    runtime: Text | None = None
    bridge: Text | None = None
    platforms: tuple[Text, ...] = ()


class PackageMetadata(Contract):
    artifact_ref: Text
    sha256: Sha256


class AssetMetadata(RegistryContract):
    identity: AssetIdentity
    owner: Owner
    visibility: Literal["private", "team", "organization", "public"]
    lifecycle: Literal["draft", "validated", "published", "deprecated"] = "draft"
    contributors: tuple[Symbol, ...] = ()
    # Discovery facets only. They never grant visibility, installation or
    # execution authority, and the empty default keeps older manifests valid.
    categories: tuple[Slug, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    dependencies: tuple[AssetIdentity, ...] = ()
    compatibility: Compatibility = Compatibility()
    business_approval: BusinessApproval = BusinessApproval()
    technical_policy: TechnicalPolicy = TechnicalPolicy()
    validation_refs: tuple[Text, ...] = ()
    evaluation_refs: tuple[Text, ...] = ()
    package: PackageMetadata | None = None
    deprecation_reason: Text | None = None
    replacement: AssetIdentity | None = None

    @model_validator(mode="after")
    def deprecation(self) -> Self:
        if self.lifecycle == "deprecated" and self.deprecation_reason is None:
            raise ValueError("deprecated assets require a reason")
        if self.replacement == self.identity:
            raise ValueError("an asset cannot replace itself")
        if len(self.categories) != len(set(self.categories)):
            raise ValueError("asset categories must be unique")
        return self


class ExecutableManifest(RegistryContract):
    metadata: AssetMetadata
    description: Text
    execution: ExecutionLocation
    dependencies: ExecutionDependencies
    secrets: tuple[SecretRef, ...] = ()
    input_contract: Symbol
    output_contract: Symbol

    @model_validator(mode="after")
    def execution_consistency(self) -> Self:
        if self.execution.mode == "central" and not self.dependencies.central_required:
            raise ValueError("central execution must declare its required central service")
        if len({ref.name for ref in self.secrets}) != len(self.secrets):
            raise ValueError("secret requirements must be unique")
        return self


class TaskManifest(ExecutableManifest):
    kind: Literal["task"] = "task"
    capability: AssetIdentity


PathPart = StrictStr | Annotated[int, Field(ge=0, strict=True)]


class RunInput(Contract):
    """Select an exact path in this run's arguments; empty path selects the root."""

    source: Literal["run"]
    path: tuple[PathPart, ...] = ()


class StepInput(Contract):
    """Select only validated data from an earlier, successful step in this run."""

    source: Literal["step"]
    step_index: int = Field(ge=0, strict=True)
    path: tuple[PathPart, ...] = ()


class FixedInput(Contract):
    """A value written into the Workflow itself, such as a recorded web
    procedure, a URL or a sheet name (owner decision 2026-10-06). It is part of
    the reviewed and versioned manifest, never a credential."""

    source: Literal["fixed"]
    value: JsonValue

    @model_validator(mode="after")
    def no_credential_material(self) -> Self:
        reject_embedded_secrets({"value": self.value})
        return self


class RetryPolicy(Contract):
    """Opt-in bounded retries; the installed capability decides whether it is safe."""

    max_attempts: int = Field(default=1, ge=1, le=3, strict=True)
    delay_ms: int = Field(default=100, ge=0, le=10000, strict=True)


class WorkflowStep(RegistryContract):
    capability: AssetIdentity
    inputs: dict[
        Symbol, Annotated[RunInput | StepInput | FixedInput, Field(discriminator="source")]
    ]
    retry: RetryPolicy = RetryPolicy()


ParameterKind = Literal[
    "text", "integer", "number", "date", "boolean", "select",
    "text_list", "emails", "file", "folder", "upload",
]
ParameterChannel = Literal["web", "telegram", "schedule", "agent"]
ALL_PARAMETER_CHANNELS: tuple[ParameterChannel, ...] = ("web", "telegram", "schedule", "agent")
_TEXT_KINDS = frozenset({"text", "select", "file", "folder", "upload"})
_LIST_KINDS = frozenset({"text_list", "emails"})
_PATH_KINDS = frozenset({"file", "folder", "upload"})
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_LATER_PARAMETER_FIELDS = frozenset({
    "default", "help", "examples", "order", "group", "pattern", "min_length", "choices",
    "choices_source", "needs", "multiple", "accept", "channels", "confirm", "allow_other",
})
CHOICES_SOURCE = re.compile(r"^(ref|fn):[A-Za-z0-9_.-]+(\?[^\s]*)?$")
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _omit_unused(
    model: Contract, handler: SerializerFunctionWrapHandler, names: frozenset[str]
) -> dict[str, Any]:
    """Serialize without the named later-added fields while they hold their
    default, so manifests published before those fields keep their bytes
    (and therefore their digests)."""
    data: dict[str, Any] = handler(model)
    fields = type(model).model_fields
    for name in names:
        if name in data and getattr(model, name) == fields[name].default:
            del data[name]
    return data


class ParameterChoice(RegistryContract):
    value: Text
    label: Text | None = None


class ProgressStep(Contract):
    """One user-visible stage a Workflow reports while it runs."""

    id: Symbol
    title: Text
    optional: StrictBool = False


class WorkflowParameter(RegistryContract):
    """Declarative field shared by host controls and a Workflow's run contract.

    One declaration generates the Agent Web and schedule forms, the Telegram
    question flow and the Agent tool schema (rs_workflow_system `PARAMS_SCHEMA`
    plus `x-ui`). Every field beyond the original ones is optional, so older
    manifests keep their meaning.
    """

    name: Symbol
    label: Text
    kind: ParameterKind
    scope: Literal["static", "runtime"] = "runtime"
    description: Text | None = None
    required: StrictBool = False
    options: tuple[Text, ...] = ()
    minimum: int | float | None = None
    maximum: int | float | None = None
    # Presentation and defaults.
    default: Any = None
    help: Text | None = None
    examples: tuple[Text, ...] = Field(default=(), max_length=5)
    order: int | None = Field(default=None, ge=0, le=99999, strict=True)
    group: Symbol | None = None
    # Text constraints.
    pattern: Text | None = None
    min_length: int | None = Field(default=None, ge=0, strict=True)
    # Choices: static labelled values, or a published set / host function
    # resolved at run time (`ref:<set>` or `fn:<name>?arg={field}`).
    choices: tuple[ParameterChoice, ...] = ()
    choices_source: Text | None = None
    # The choices are suggestions: any nonempty text is accepted ("pick or
    # type"), and the engine never consults the source at run time.
    allow_other: StrictBool = False
    needs: tuple[Symbol, ...] = ()
    multiple: StrictBool = False
    accept: tuple[Text, ...] = ()
    # Which generated interfaces show the field; () keeps it internal.
    channels: tuple[ParameterChannel, ...] = ALL_PARAMETER_CHANNELS
    # A privileged field: changing it needs an explicit confirmation.
    confirm: StrictBool = False

    @property
    def choice_values(self) -> tuple[str, ...]:
        return tuple(item.value for item in self.choices) or self.options

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        return _omit_unused(self, handler, _LATER_PARAMETER_FIELDS)

    @model_validator(mode="after")
    def kind_constraints(self) -> Self:
        if SECRET_FIELD.fullmatch(self.name):
            raise ValueError("credentials must be declared as SecretRef, not a parameter")
        if self.options and self.choices:
            raise ValueError("declare either options or choices, not both")
        values = self.choice_values
        if len(set(values)) != len(values):
            raise ValueError("parameter choices must be distinct")
        if self.kind == "select" and not values and self.choices_source is None:
            raise ValueError("select parameters require choices or a choices source")
        if self.kind not in ("select", "text_list") and (values or self.choices_source):
            raise ValueError("only select and text_list parameters may declare choices")
        if self.choices_source is not None and not CHOICES_SOURCE.fullmatch(self.choices_source):
            raise ValueError("choices_source must be ref:<set> or fn:<name>")
        if self.allow_other and (self.kind != "select" or self.multiple):
            raise ValueError("only single select parameters may allow other values")
        if self.kind not in ("integer", "number") and (
            self.minimum is not None or self.maximum is not None
        ):
            raise ValueError("only numeric parameters may declare bounds")
        if self.kind == "integer" and any(
            bound is not None and type(bound) is not int for bound in (self.minimum, self.maximum)
        ):
            raise ValueError("integer bounds must be whole numbers")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("parameter minimum must not exceed maximum")
        if (self.pattern is not None or self.min_length is not None) and self.kind not in (
            "text", "text_list"
        ):
            raise ValueError("only text parameters may declare a pattern or minimum length")
        if self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error:
                raise ValueError("parameter pattern must be a valid expression") from None
        if self.accept and self.kind not in _PATH_KINDS:
            raise ValueError("only file, folder and upload parameters may declare accept")
        if self.multiple and self.kind not in ("select", "file", "upload"):
            raise ValueError("only select, file and upload parameters may be multiple")
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("parameter channels must be distinct")
        if self.default is not None:
            problem = parameter_value_problem(self, self.default)
            if problem:
                raise ValueError(f"default: {problem}")
        return self


def parameter_value_problem(field: WorkflowParameter, value: Any) -> str | None:
    """Why `value` does not fit `field`, or None. Shared by defaults and runs."""
    kind = field.kind
    if field.multiple or kind in _LIST_KINDS:
        if not isinstance(value, list | tuple) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            return "must be a list of nonempty text"
        items: tuple[str, ...] = tuple(value)
    elif kind in _TEXT_KINDS:
        if not isinstance(value, str) or not value.strip():
            return "must be nonempty text"
        items = (value,)
    elif kind == "integer":
        if type(value) is not int:
            return "must be a whole number"
        items = ()
    elif kind == "number":
        if type(value) not in (int, float):
            return "must be a number"
        items = ()
    elif kind == "boolean":
        return None if type(value) is bool else "must be true or false"
    else:  # date
        from datetime import date

        try:
            parsed = date.fromisoformat(value) if isinstance(value, str) else None
        except ValueError:
            parsed = None
        if parsed is None or parsed.isoformat() != value:
            return "must be a YYYY-MM-DD date"
        return None
    if kind in ("integer", "number"):
        if field.minimum is not None and value < field.minimum:
            return "is below its minimum"
        if field.maximum is not None and value > field.maximum:
            return "is above its maximum"
        return None
    if kind == "emails" and not all(_EMAIL.fullmatch(item) for item in items):
        return "must be email addresses"
    values = field.choice_values
    if (
        values and field.choices_source is None and not field.allow_other
        and any(item not in values for item in items)
    ):
        return "must be a declared choice"
    for item in items:
        if field.min_length is not None and len(item) < field.min_length:
            return "is shorter than its minimum length"
        if field.pattern is not None and not re.fullmatch(field.pattern, item):
            return "does not match its pattern"
    return None


class WorkflowOutputCheck(Contract):
    """What a Workflow run must have produced to count as done (harness
    unification U3, owner 2026-10-09). Checked by the Host after the steps,
    never claimed by a step."""

    check_id: Symbol
    step_index: int = Field(ge=0, strict=True)
    kind: Literal["data_nonempty", "files_nonempty", "file_exists"]
    # A file-name glob (`*.xlsx`) for the file kinds.
    pattern: str | None = Field(default=None, max_length=200)


class WorkflowManifest(ExecutableManifest):
    kind: Literal["workflow"] = "workflow"
    # Optional numeric shortcut for a single installed workflow version.
    # Resolution refuses ambiguity; a shortcut never grants execution rights.
    run_alias: int | None = Field(default=None, ge=1, le=9999, strict=True)
    parameters: tuple[WorkflowParameter, ...] = ()
    steps: tuple[AssetIdentity | WorkflowStep, ...]
    # Stages shown while the Workflow runs (rs_workflow_system `STEPS`).
    progress_steps: tuple[ProgressStep, ...] = Field(default=(), max_length=12)
    # The run occupies the machine (a browser session, Excel or Outlook UI),
    # so it must not overlap another such run (rs_workflow_system `block`).
    occupies_machine: StrictBool = False
    # Output checks the Host runs after the steps; empty keeps older digests.
    checks: tuple[WorkflowOutputCheck, ...] = Field(default=(), max_length=20)

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        return _omit_unused(
            self, handler, frozenset({"progress_steps", "occupies_machine", "checks"})
        )

    @field_validator("parameters")
    @classmethod
    def unique_parameters(
        cls, value: tuple[WorkflowParameter, ...]
    ) -> tuple[WorkflowParameter, ...]:
        if len({item.name for item in value}) != len(value):
            raise ValueError("workflow parameter names must be unique")
        # A field that another field depends on must exist and be asked first:
        # by declared `order`, else by position in the manifest. A placeholder
        # may also name a setting (`scope: static`), which is never asked.
        position = {
            item.name: (item.order if item.order is not None else index, index)
            for index, item in enumerate(value)
        }
        settings = {item.name for item in value if item.scope == "static"}
        for item in value:
            placeholders = (
                _PLACEHOLDER.findall(item.choices_source) if item.choices_source else []
            )
            for name in placeholders:
                if name not in position:
                    raise ValueError(f"{item.name}: placeholder {{{name}}} names no parameter")
            asked = [name for name in placeholders if name not in settings]
            for name in (*item.needs, *asked):
                if name not in position:
                    raise ValueError(f"{item.name}: needs {name}, which is not declared")
                if position[name] >= position[item.name]:
                    raise ValueError(f"{item.name}: {name} must be asked before it")
        return value

    @field_validator("progress_steps")
    @classmethod
    def unique_progress_steps(cls, value: tuple[ProgressStep, ...]) -> tuple[ProgressStep, ...]:
        if len({item.id for item in value}) != len(value):
            raise ValueError("progress step ids must be unique")
        return value

    @field_validator("steps")
    @classmethod
    def nonempty_steps(
        cls, value: tuple[AssetIdentity | WorkflowStep, ...]
    ) -> tuple[AssetIdentity | WorkflowStep, ...]:
        if not value:
            raise ValueError("a workflow must declare at least one step")
        for index, step in enumerate(value):
            if isinstance(step, WorkflowStep) and any(
                isinstance(ref, StepInput) and ref.step_index >= index
                for ref in step.inputs.values()
            ):
                raise ValueError("step inputs may reference only earlier steps")
        return value
