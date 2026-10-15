"""Installed Skill procedures and explicit route bindings, without executable imports."""

import re
from typing import Annotated, Any, Literal, Self

from pydantic import (
    Field,
    JsonValue,
    SerializerFunctionWrapHandler,
    StringConstraints,
    field_validator,
    model_serializer,
    model_validator,
)

from common.assets import AssetIdentity, AssetMetadata, RegistryContract
from common.base import Contract, Symbol, Text

CommandName = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")]


class CommandBinding(Contract):
    name: CommandName
    kind: Literal["capability", "workflow"] = "capability"
    target: AssetIdentity


class KeywordRule(Contract):
    """Trusted installation configuration; never accept regexes from model output."""

    pattern: str = Field(min_length=1, max_length=512)
    command: CommandName

    @field_validator("pattern")
    @classmethod
    def valid_regex(cls, value: str) -> str:
        try:
            re.compile(value, re.IGNORECASE)
        except re.error:
            raise ValueError("invalid routing regular expression") from None
        return value


HarnessDomain = Literal["workflow", "knowledge", "coding", "conversation"]


class SkillHarnessGuidance(Contract):
    """Procedural hints; never an execution grant or host validation override."""

    domains: tuple[HarnessDomain, ...] = Field(min_length=1, max_length=4)
    required_evidence: tuple[Symbol, ...] = Field(default=(), max_length=20)
    context_required: bool = False
    fallback: Literal["needs_input", "stop", "retry"] = "needs_input"
    max_retries: int = Field(default=0, ge=0, le=3, strict=True)

    @model_validator(mode="after")
    def distinct_scope(self) -> Self:
        if len(self.domains) != len(set(self.domains)):
            raise ValueError("harness domains must be unique")
        if len(self.required_evidence) != len(set(self.required_evidence)):
            raise ValueError("required evidence must be unique")
        if self.fallback == "retry" and self.max_retries == 0:
            raise ValueError("retry fallback requires a positive retry budget")
        return self


class SkillManifest(RegistryContract):
    metadata: AssetMetadata
    alias: CommandName
    instructions: Text
    commands: tuple[CommandBinding, ...] = ()
    rules: tuple[KeywordRule, ...] = ()
    default_command: CommandName | None = None
    # Supporting executable resources remain separately governed capabilities.
    script_tools: tuple[AssetIdentity, ...] = ()
    harness_guidance: SkillHarnessGuidance | None = None
    # Domain adapters validate this JSON procedure before use; the common
    # harness carries no Knowledge-, Workflow- or Coding-specific fields.
    procedure: dict[str, JsonValue] = Field(default_factory=dict)
    # One short line, English and Chinese keywords, that tells a Skill
    # selector (JEV SystemOne) what this Skill is for and how it differs from
    # the others; `instructions` stays the guidance for the model.
    selector_hint: Annotated[str, StringConstraints(min_length=1, max_length=240)] | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        # Manifests published before the hint keep their bytes and digests.
        data: dict[str, Any] = handler(self)
        if self.selector_hint is None:
            data.pop("selector_hint", None)
        return data

    @model_validator(mode="after")
    def explicit_bindings(self) -> Self:
        names = [command.name for command in self.commands]
        if len(names) != len(set(names)):
            raise ValueError("command names must be unique within a Skill")
        if self.default_command is not None and self.default_command not in names:
            raise ValueError("default_command must reference a declared command")
        if any(rule.command not in names for rule in self.rules):
            raise ValueError("keyword rules must reference declared commands")
        if len({item.key for item in self.script_tools}) != len(self.script_tools):
            raise ValueError("script tool references must be unique")
        return self


class SkillRegistry:
    """Explicit host-installed versions. Registration order defines keyword precedence."""

    def __init__(self) -> None:
        self._skills: dict[tuple[str, str], str] = {}

    def register(self, manifest: SkillManifest) -> None:
        checked = SkillManifest.model_validate(manifest)
        key = (checked.metadata.identity.namespace, checked.alias)
        if key in self._skills:
            raise ValueError("Skill alias already installed in this namespace")
        self._skills[key] = checked.model_dump_json()

    def remove(self, identity: AssetIdentity) -> bool:
        """Stop offering one exact Skill version (switched off or removed)."""
        for key, payload in list(self._skills.items()):
            if SkillManifest.model_validate_json(payload).metadata.identity == identity:
                del self._skills[key]
                return True
        return False

    def get(self, namespace: str, alias: str) -> SkillManifest | None:
        payload = self._skills.get((namespace, alias))
        return SkillManifest.model_validate_json(payload) if payload is not None else None

    def manifests(self) -> tuple[SkillManifest, ...]:
        """Every installed Skill, in registration order."""
        return tuple(
            SkillManifest.model_validate_json(payload) for payload in self._skills.values()
        )

    def discover(self, namespace: str) -> tuple[SkillManifest, ...]:
        return tuple(
            SkillManifest.model_validate_json(payload)
            for (scope, _), payload in self._skills.items()
            if scope == namespace
        )
