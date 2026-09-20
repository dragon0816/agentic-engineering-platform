"""Installed Skill procedures and explicit route bindings, without executable imports."""

import re
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from common.assets import AssetIdentity, AssetMetadata, RegistryContract
from common.base import Contract, Text

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


class SkillManifest(RegistryContract):
    metadata: AssetMetadata
    alias: CommandName
    instructions: Text
    commands: tuple[CommandBinding, ...] = ()
    rules: tuple[KeywordRule, ...] = ()
    default_command: CommandName | None = None

    @model_validator(mode="after")
    def explicit_bindings(self) -> Self:
        names = [command.name for command in self.commands]
        if len(names) != len(set(names)):
            raise ValueError("command names must be unique within a Skill")
        if self.default_command is not None and self.default_command not in names:
            raise ValueError("default_command must reference a declared command")
        if any(rule.command not in names for rule in self.rules):
            raise ValueError("keyword rules must reference declared commands")
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

    def get(self, namespace: str, alias: str) -> SkillManifest | None:
        payload = self._skills.get((namespace, alias))
        return SkillManifest.model_validate_json(payload) if payload is not None else None

    def discover(self, namespace: str) -> tuple[SkillManifest, ...]:
        return tuple(
            SkillManifest.model_validate_json(payload)
            for (scope, _), payload in self._skills.items()
            if scope == namespace
        )
