"""Validated local activation for inert, exact-version Agent profiles."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from agent.contracts import ActiveAgentProfile, AgentProfile
from agent.skills import SkillManifest
from common.assets import AssetIdentity
from common.authorization import DeviceAuthorization, RunnableKind
from host_runtime.contracts import CompanyHostConfiguration, HostLayout
from host_runtime.workspace import write_atomically
from knowledge.evolution import KnowledgeManifest

ProfileErrorCode = Literal[
    "profile_not_selected",
    "profile_not_installed",
    "profile_invalid",
    "profile_delegation_unsupported",
    "profile_delegation_target_unavailable",
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


def _check_references(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    allows: Callable[[RunnableKind, AssetIdentity], bool],
    profile: AgentProfile,
) -> None:
    """Check exact procedure/source references and model requirements.

    Tool declarations are not application execution permissions.
    """
    for skill in profile.skills:
        if not allows("skill", skill) or not _installed(layout.skills, skill, SkillManifest):
            raise ProfileError("profile_dependency_unavailable")
    for knowledge in profile.knowledge:
        if not allows("knowledge", knowledge) or not _installed(
            layout.knowledge, knowledge, KnowledgeManifest
        ):
            raise ProfileError("profile_dependency_unavailable")
    # Tool declarations are role guidance; OS/service access is checked at execution.
    binding = config.models
    endpoint = (
        None
        if binding is None or binding.routing_alias is None
        else binding.catalog.endpoint(binding.routing_alias)
    )
    if endpoint is None or not endpoint.capabilities.satisfies(profile.model_requirements):
        raise ProfileError("profile_model_unavailable")


def validate_profile(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    authorization: DeviceAuthorization | None,
    identity: AssetIdentity,
) -> AgentProfile:
    """Return a usable profile only when every reference is already allowed locally.

    `may_delegate_to` is refused unless multi-agent delegation is switched on
    (`multi_agent.enabled`); then every target must itself be a usable
    delegation target (`delegation_target`). A target's own targets are not
    followed: delegation is one level deep."""
    if authorization is None or not authorization.allows("agent", identity):
        raise ProfileError("profile_not_selected")
    profile = _profile(layout, identity)
    if profile.may_delegate_to and not config.multi_agent.enabled:
        raise ProfileError("profile_delegation_unsupported")
    _check_references(config, layout, authorization.allows, profile)
    for target in profile.may_delegate_to:
        try:
            delegation_target(config, layout, authorization, target)
        except ProfileError:
            raise ProfileError("profile_delegation_target_unavailable") from None
    return profile


def delegation_target(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    authorization: DeviceAuthorization | None,
    identity: AssetIdentity,
) -> AgentProfile:
    """A profile a parent may delegate to (multi-agent V1): installed,
    published, selected, with every reference allowed and installed.

    In owner mode (no Shared Platform authorization and
    `local_owner_grants`) the owner holds every installed asset, so an
    installed profile needs no selection; its Skills and Knowledge must
    still be installed. Without either, nothing qualifies (fail closed).
    The target's own `may_delegate_to` is ignored (depth 1)."""
    if not config.multi_agent.enabled:
        raise ProfileError("profile_delegation_unsupported")
    allows: Callable[[RunnableKind, AssetIdentity], bool]
    if authorization is not None:
        if not authorization.allows("agent", identity):
            raise ProfileError("profile_not_selected")
        allows = authorization.allows
    elif config.local_owner_grants:
        allows = _owner_allows
    else:
        raise ProfileError("profile_not_selected")
    profile = _profile(layout, identity)
    _check_references(config, layout, allows, profile)
    return profile


def _owner_allows(kind: RunnableKind, identity: AssetIdentity) -> bool:
    """Owner mode: every installed asset is the owner's (installation is
    checked separately)."""
    return True


def installed_profiles(layout: HostLayout) -> tuple[AssetIdentity, ...]:
    """The identities of the profile files under `agents/`, as their names say
    (validation happens when one is used)."""
    found: list[AssetIdentity] = []
    try:
        paths = sorted(layout.agents.glob("*__*__*.json"))
    except OSError:
        return ()
    for path in paths:
        namespace, _, rest = path.stem.partition("__")
        name, _, version = rest.partition("__")
        try:
            found.append(AssetIdentity(namespace=namespace, name=name, version=version))
        except ValidationError:
            continue
    return tuple(found)


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
