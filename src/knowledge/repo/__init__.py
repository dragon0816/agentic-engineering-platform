"""Knowledge repositories: one version mechanism for every knowledge base (R1).

Design: `docs/phases/KNOWLEDGE_REPO.md`; contract: `docs/CONTRACTS.md`
"Knowledge repositories: folder, commits, push, revert, tags".
"""

from knowledge.repo.repository import (
    REPO_FILE,
    CheckReport,
    RepoError,
    Repository,
    RepoType,
    create,
    get_type,
    join,
    register_type,
    registered,
)

__all__ = [
    "REPO_FILE",
    "CheckReport",
    "RepoError",
    "RepoType",
    "Repository",
    "create",
    "get_type",
    "join",
    "register_type",
    "registered",
]
