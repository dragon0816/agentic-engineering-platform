"""Immutable source identity and provenance, not extracted or curated content."""

from pydantic import Field

from common.assets import RegistryContract
from common.base import Sha256, Symbol, Text


class KnowledgeSource(RegistryContract):
    source_id: Symbol
    original_ref: Text
    sha256: Sha256
    raw_ref: Text | None = None
    page: int | None = Field(default=None, ge=1, strict=True)
    slide: int | None = Field(default=None, ge=1, strict=True)
    parent_source_id: Symbol | None = None
