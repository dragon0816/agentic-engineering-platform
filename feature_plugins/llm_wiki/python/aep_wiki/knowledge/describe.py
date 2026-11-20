"""Image description lives in core `knowledge.describe` (owner 2026-11-20): the BI
source conversion describes pictures the same way the LLM Wiki intake does. This
name stays so existing imports keep working."""

from knowledge.describe import (
    DEFAULT_PROMPT,
    MAX_IMAGE_BYTES,
    MEDIA_TYPES,
    ImageDescriber,
    data_uri,
)

__all__ = ["DEFAULT_PROMPT", "MAX_IMAGE_BYTES", "MEDIA_TYPES", "ImageDescriber", "data_uri"]
