"""Who the platform decided someone is, and what that lets them use.

The owner's rule (2026-09-22): a Bridge is bound to a user, and the user's
authentication decides which Workflows and Skills they may use.

An authenticated actor carries who they are and until when, and never what
they belong to. A membership claim that travels with a request is a
membership claim that whoever sends it can widen, so groups are read from the
platform's own record of that user: the invitation said what accepting it
grants, and accepting it recorded that. Nothing here is a credential, a
session store or an authentication mechanism; this is the shape of the answer
an entry point gives once it has decided, and what the rest of the platform
may conclude from it.
"""

from datetime import datetime
from typing import Self

from pydantic import AwareDatetime, model_validator

from common.assets import AssetMetadata, RegistryContract
from common.base import Symbol


class AuthenticatedActor(RegistryContract):
    """What an entry point produces once it has decided who someone is.

    `method` names what it did, and the platform records it without
    interpreting it: how a member proves who they are is the entry point's
    business, and an evidence trail needs the name of it either way.
    """

    actor: Symbol
    method: Symbol
    authenticated_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def ends_after_it_begins(self) -> Self:
        if self.expires_at <= self.authenticated_at:
            raise ValueError("an authentication that has already expired decided nothing")
        return self

    def valid_at(self, now: datetime) -> bool:
        return self.authenticated_at <= now < self.expires_at


def entitled(metadata: AssetMetadata, actor: str, groups: tuple[str, ...]) -> bool:
    """Whether one member may use one published asset.

    The owner may always use what it owns, whether the owner is this actor or
    a group they belong to, and so may a recorded contributor. Beyond that,
    `public` and `organization` are for any member of the platform, and
    nothing else is for anybody else.

    That last line is where `team` and `private` are decided, and they come to
    the same answer for a group-owned asset: the members of the owning group
    may use it and nobody else may, because the owning group is the team. A
    user-owned asset marked `team` names no team to check, so it stays with
    its owner rather than widening to everyone.

    Being entitled to an asset is not permission to run it anywhere: a member
    still chooses which of their devices may, and the Bridge policy still
    authorizes every dispatch.
    """
    if metadata.lifecycle != "published":
        return False
    owner = metadata.owner
    owned = owner.id == actor if owner.type == "user" else owner.id in groups
    if owned or actor in metadata.contributors:
        return True
    return metadata.visibility in ("public", "organization")
