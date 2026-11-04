"""Where a BI vault keeps its files: homes (`docs/phases/BI_CARD_MODEL.md` §4).

    applications/<application>/{sources,skills,tools,profile}/
    library/<entry>/{sources,skills,tools,profile}/
    library/skills/<name>/rev-<n>-<author>.md     a skill spanning every home (classify)

A **home** is an application or a library entry, handled alike. Its short form,
`<application>` or `library/<entry>`, names it in unit keys and in
`card_app_folders`, so an application called `products` is not the entry
`library/products`. Which applications and entries a vault has is data
(`meta:vault_segments`, `meta:vault_library`), so nothing here checks a list.

A path written before these homes (`skills/…`, `sources/…`, also
`sources/applications/<segment>/…`) stays valid: commits are immutable and name
their paths. Paths are immutable too, so everything new is spelled here.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

from knowledge.repo.repository import FileLayout, RepoError, path_problem

APPLICATIONS = "applications"
LIBRARY = "library"
SOURCES = "sources"
SKILLS = "skills"
TOOLS = "tools"
PROFILE = "profile"
HOME_FOLDERS = (SOURCES, SKILLS, TOOLS, PROFILE)
#: The owner's defaults, 2026-11-04. Applications are in `vault.SEGMENTS`.
LIBRARY_ENTRIES = ("products", "technologies", "competitors")
#: `library/skills/` holds what spans every home, so no entry can have that name.
RESERVED_ENTRY = SKILLS

_ID = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_AUTHOR = r"[a-z0-9]+(?:[._-][a-z0-9]+)*"
_HOME_DIR = rf"(?:{APPLICATIONS}/{_ID}|{LIBRARY}/(?!{RESERVED_ENTRY}/){_ID})"
_ID_RE = re.compile(rf"^{_ID}$")
_HOME_RE = re.compile(rf"^(?:{LIBRARY}/)?(?P<id>{_ID})$")
_SOURCE_FOLDER_RE = re.compile(rf"^{_HOME_DIR}/{SOURCES}(?:/.+)?$")
_SOURCE_FILE_RE = re.compile(rf"^{_HOME_DIR}/{SOURCES}/.+$")
_OWN_HOME_RE = re.compile(
    rf"^{APPLICATIONS}/(?P<app>{_ID})/|^{LIBRARY}/(?!{RESERVED_ENTRY}/)(?P<entry>{_ID})/"
)
_OLD_HOME_RE = re.compile(
    rf"^{SOURCES}/{APPLICATIONS}/(?P<app>{_ID})(?:/|$)|^{SOURCES}/{LIBRARY}/(?P<entry>{_ID})(?:/|$)"
)
SKILL_PATH_RE = re.compile(
    rf"^(?:{SKILLS}|{LIBRARY}/{SKILLS}|{_HOME_DIR}/{SKILLS})/"
    rf"(?P<name>{_ID})/rev-(?P<revision>[1-9][0-9]{{0,5}})-(?P<author>{_AUTHOR})\.md$"
)


def id_problem(value: Any) -> str | None:
    return None if isinstance(value, str) and _ID_RE.match(value) else "只能用小寫英數字與 -"


def entry_problem(value: Any) -> str | None:
    """Why `value` cannot name a library entry; None when it can."""
    if value == RESERVED_ENTRY:
        return f"「{RESERVED_ENTRY}」保留給跨領域的 skill，不能當項目名稱"
    return id_problem(value)


def home_problem(home: Any) -> str | None:
    """Why `home` is not a home's short form; None when it is."""
    matched = _HOME_RE.match(home) if isinstance(home, str) else None
    if matched is None:
        return "必須是 <application> 或 library/<entry>"
    return entry_problem(matched.group("id")) if home.startswith(f"{LIBRARY}/") else None


def _checked(home: str) -> str:
    problem = home_problem(home)
    if problem:
        raise RepoError("home_invalid", f"「{home}」{problem}")
    return home


def home_dir(home: str) -> str:
    """`aidc` → `applications/aidc`; `library/products` stays as it is."""
    return _checked(home) if home.startswith(f"{LIBRARY}/") else f"{APPLICATIONS}/{_checked(home)}"


def sources_dir(home: str) -> str:
    return f"{home_dir(home)}/{SOURCES}"


def skills_dir(home: str) -> str:
    """Where `home`'s skills go; no home is `library/skills`, what spans them all."""
    return f"{home_dir(home)}/{SKILLS}" if home else f"{LIBRARY}/{SKILLS}"


def tool_path(home: str, name: str, revision: int, author: str, suffix: str) -> str:
    """`suffix` is the file's, with its dot."""
    return f"{home_dir(home)}/{TOOLS}/{name}/rev-{revision}-{author}{suffix}"


def profile_path(home: str, revision: int, author: str) -> str:
    return f"{home_dir(home)}/{PROFILE}/rev-{revision}-{author}.json"


def home_of(folder: str) -> str | None:
    """The home a source folder or file lies in, by its short form; None for one
    outside them. An old `sources/applications/<segment>` path counts."""
    matched = _OWN_HOME_RE.match(folder) or _OLD_HOME_RE.match(folder)
    if matched is None:
        return None
    return matched.group("app") or f"{LIBRARY}/{matched.group('entry')}"


def domain_of_folder(domains: Any, folder: str | None) -> str | None:
    """The domain a source folder's application stands for: the schema's domain of that
    name (`aidc` is `AIDC`). A library entry spans domains, so it has none."""
    home = home_of(folder or "")
    if home is None or home.startswith(f"{LIBRARY}/"):
        return None
    return next((d for d in domains if d.lower() == home.lower()), None)


class BiLayout(FileLayout):
    """A BI vault's files; `skills` and `sources` remain for what old commits name."""

    areas = ("schemas", SKILLS, SOURCES, APPLICATIONS, LIBRARY)
    new_areas = ("schemas", APPLICATIONS, LIBRARY)
    source_hint = f"{APPLICATIONS}/<application>/{SOURCES}/"
    skill_path_re = SKILL_PATH_RE

    def is_source_path(self, path: str) -> bool:
        return path.startswith(f"{SOURCES}/") or _SOURCE_FILE_RE.match(path) is not None

    def source_folder_problem(self, folder: str) -> str | None:
        if folder == SOURCES:
            return None
        parts = PurePosixPath(folder).parts
        if parts[:1] != (SOURCES,) and _SOURCE_FOLDER_RE.match(folder) is None:
            return (
                f"必須在 {APPLICATIONS}/<application>/{SOURCES} 或 {LIBRARY}/<entry>/{SOURCES} 底下"
            )
        return path_problem(folder, self.areas)

    def skill_area(self, home: str) -> str:
        return skills_dir(home)


LAYOUT = BiLayout()
