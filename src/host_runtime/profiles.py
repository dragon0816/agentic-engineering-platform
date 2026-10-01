"""Validated local activation for inert, exact-version Agent profiles."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from agent.contracts import ActiveAgentProfile, AgentProfile
from agent.skills import SkillManifest
from common.assets import AssetIdentity
from common.authorization import DeviceAuthorization
from host_runtime.contracts import CompanyHostConfiguration, HostLayout
from host_runtime.workspace import write_atomically
from knowledge.evolution import KnowledgeManifest

ProfileErrorCode = Literal[
    "profile_not_selected",
    "profile_not_installed",
    "profile_invalid",
    "profile_delegation_unsupported",
    "profile_dependency_unavailable",
    "profile_model_unavailable",
    "profile_state_unwritable",
]


class ProfileError(Exception):
    def __init__(self, code: ProfileErrorCode) -> None:
        self.code = code
        super().__init__(code)


def _path(directory: Path, identity: AssetIdentity) -> Path:
    return directory / f"{identity.namespace}__{identity.name}__{identity.version}.json"


def _profile(layout: HostLayout, identity: AssetIdentity) -> AgentProfile:
    path = _path(layout.agents, identity)
    try:
        profile = AgentProfile.model_validate_json(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise ProfileError("profile_not_installed") from None
    except (OSError, ValidationError):
        raise ProfileError("profile_invalid") from None
    if profile.metadata.identity != identity or profile.metadata.lifecycle != "published":
        raise ProfileError("profile_invalid")
    return profile


def _installed(
    directory: Path, identity: AssetIdentity, model: type[SkillManifest | KnowledgeManifest]
) -> bool:
    try:
        item = model.model_validate_json(_path(directory, identity).read_text(encoding="utf-8-sig"))
    except (OSError, ValidationError):
        return False
    return item.metadata.identity == identity and item.metadata.lifecycle == "published"


def validate_profile(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    authorization: DeviceAuthorization | None,
    identity: AssetIdentity,
) -> AgentProfile:
    """Return a usable profile only when every reference is already allowed locally."""
    if authorization is None or not authorization.allows("agent", identity):
        raise ProfileError("profile_not_selected")
    profile = _profile(layout, identity)
    if profile.may_delegate_to:
        raise ProfileError("profile_delegation_unsupported")
    for skill in profile.skills:
        if not authorization.allows("skill", skill) or not _installed(
            layout.skills, skill, SkillManifest
        ):
            raise ProfileError("profile_dependency_unavailable")
    for knowledge in profile.knowledge:
        if not authorization.allows("knowledge", knowledge) or not _installed(
            layout.knowledge, knowledge, KnowledgeManifest
        ):
            raise ProfileError("profile_dependency_unavailable")
    if any(
        not authorization.allows("capability", capability)
        for capability in profile.allowed_capabilities
    ):
        raise ProfileError("profile_dependency_unavailable")
    binding = config.models
    endpoint = (
        None
        if binding is None or binding.routing_alias is None
        else binding.catalog.endpoint(binding.routing_alias)
    )
    if endpoint is None or not endpoint.capabilities.satisfies(profile.model_requirements):
        raise ProfileError("profile_model_unavailable")
    return profile


def activate_profile(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    authorization: DeviceAuthorization | None,
    identity: AssetIdentity,
    *,
    actor: str,
    now: datetime | None = None,
) -> ActiveAgentProfile:
    validate_profile(config, layout, authorization, identity)
    active = ActiveAgentProfile(
        profile=identity,
        actor=actor,
        activated_at=now if now is not None else datetime.now(UTC),
    )
    try:
        write_atomically(
            layout.active_profile,
            active.model_dump_json(indent=2).encode("utf-8") + b"\n",
        )
    except OSError:
        raise ProfileError("profile_state_unwritable") from None
    return active


def load_active_profile(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    authorization: DeviceAuthorization | None,
    *,
    actor: str,
) -> AgentProfile | None:
    if not layout.active_profile.is_file():
        return None
    try:
        active = ActiveAgentProfile.model_validate_json(
            layout.active_profile.read_text(encoding="utf-8-sig")
        )
    except (OSError, ValidationError):
        raise ProfileError("profile_invalid") from None
    if active.actor != actor:
        raise ProfileError("profile_invalid")
    return validate_profile(config, layout, authorization, active.profile)
