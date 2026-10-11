"""The ingest rules a vault carries (K3, owner 2026-10-11).

`docs/phases/KNOWLEDGE_K3.md`. A vault's `CLAUDE.md` is its Karpathy LLM Wiki
schema and the ingest system message. Each `skills/<name>/SKILL.md` whose
frontmatter names `applies_to: raw/<category>` adds that category's rules for
sources under that Raw folder; the most specific folder wins and other
categories' rules are not sent. Domain owners edit these files in Obsidian; no
release is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from knowledge.vault import Vault, VaultError, normalize

SCHEMA_FILE = "CLAUDE.md"
SKILLS_DIR = "skills"
SKILL_FILE = "SKILL.md"


@dataclass(frozen=True)
class Conventions:
    text: str
    schema_source: Literal["vault", "built_in"]
    skill: str | None = None


def _front(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    head, sep, body = text[4:].partition("\n---\n")
    if not sep:
        return {}, text
    fields = {}
    for line in head.splitlines():
        key, colon, value = line.partition(":")
        if colon and not line.startswith((" ", "\t")):
            fields[key.strip()] = value.strip().strip("\"'")
    return fields, body


def category_skill(vault: Vault, raw_ref: str) -> tuple[str, str] | None:
    """(name, rules) of the skill whose `applies_to` folder holds `raw_ref`."""
    folder = vault.root / SKILLS_DIR
    if not folder.is_dir():
        return None
    ref = normalize(raw_ref)
    best: tuple[int, str, str] | None = None
    for path in sorted(folder.glob(f"*/{SKILL_FILE}")):
        rel = path.relative_to(vault.root).as_posix()
        try:
            fields, body = _front(vault.read(rel))
        except (VaultError, UnicodeDecodeError):
            continue
        scope = normalize(fields.get("applies_to", "")).rstrip("/")
        if not scope or not ref.startswith(scope + "/"):
            continue
        if best is None or len(scope) > best[0]:
            best = (len(scope), fields.get("name") or path.parent.name, body.strip())
    return (best[1], best[2]) if best else None


def ingest_conventions(vault: Vault, raw_ref: str, built_in: str) -> Conventions:
    """The vault's schema plus the category rules for this source, or the
    built-in conventions when the vault has no schema."""
    schema = vault.read(SCHEMA_FILE).strip() if vault.exists(SCHEMA_FILE) else ""
    if not schema:
        return Conventions(built_in, "built_in")
    found = category_skill(vault, raw_ref)
    if found is None:
        return Conventions(schema, "vault")
    name, rules = found
    return Conventions(f"{schema}\n\n---\n\n# Rules for this source's category ({name})\n\n"
                       f"{rules}", "vault", name)
