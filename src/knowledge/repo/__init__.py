"""Knowledge repositories: one version mechanism for every knowledge base (R1).

Design: `docs/phases/KNOWLEDGE_REPO.md`; contract: `docs/CONTRACTS.md`
"Knowledge repositories: folder, commits, push, revert, tags".
"""

from knowledge.repo.readme import readme_text, write_readme
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
from knowledge.repo.skills import Skill, parse_skill, render_skill

__all__ = [
    "REPO_FILE",
    "CheckReport",
    "Skill",
    "RepoError",
    "RepoType",
    "Repository",
    "create",
    "get_type",
    "join",
    "parse_skill",
    "readme_text",
    "register_type",
    "registered",
    "render_skill",
    "write_readme",
]
