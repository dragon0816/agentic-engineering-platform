"""Port the Hermes agent's skills into AEP (owner request 2026-10-15).

Reads a Hermes skills folder (`<root>/<category>/<name>/SKILL.md` plus its
supporting files; read only) and writes, for every ported skill:

- an AEP `SkillManifest` (`manifests/hermes__<name>__<version>.json`) whose
  instructions are the SKILL.md body with Hermes tool names put in neutral
  words, a short note on where the supporting files are, and nothing that
  looks like a credential;
- the skill folder itself for Claude Code / Copilot agent mode
  (`skills/vendor/hermes-<name>/`), byte for byte except the frontmatter
  `name` (which must match the folder) and the few adaptations listed in
  `pack.json`.

The MIT skills and the scrubbed `business-cards` form the repository's
Hermes skill pack (`packages/hermes-skill-pack`); the other internal skills
are written only with `--personal-out`, to a folder outside the repository.
Every ported skill is meant to be installed switched off. See
`docs/phases/HERMES_SKILL_PACK.md`.

    python scripts/port_hermes_skills.py --source %LOCALAPPDATA%/hermes/skills \
        --out packages/hermes-skill-pack [--personal-out <folder outside the repo>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from agent.skills import SkillManifest  # noqa: E402
from common.assets import SECRET_PATTERN  # noqa: E402

NAMESPACE = "hermes"
FOLDER_PREFIX = "hermes-"
PACK_VERSION = "1.0.0"
MAX_INSTRUCTIONS_CHARS = 20_000  # host_runtime.skill_authoring.MAX_INSTRUCTIONS_CHARS
MAX_SELECTOR_HINT = 240

#: Owner decision 2026-10-15: macOS/Linux-only skills and Hermes' own skills.
SKIPPED = frozenset(
    {
        "apple/apple-notes",
        "apple/apple-reminders",
        "apple/findmy",
        "apple/imessage",
        "social-media/xurl",
        "software-development/python-debugpy",
        "autonomous-ai-agents/hermes-agent",
        "software-development/hermes-agent-skill-authoring",
        "software-development/inspecting-hermes-desktop-dom",
    }
)
#: The owner's own skills (license UNLICENSED): this PC only, never the repo.
PERSONAL = frozenset(
    {
        "email/outlook-email-workflows",
        "productivity/business-cards",
        "productivity/html-report-delivery",
        "productivity/leo-work-automation",
        "productivity/pdf-linked-markdown",
        "productivity/rs-workflow-jobs",
        "research/rs-knowledge-base",
        "software-development/aep-platform-testing",
    }
)
#: Personal skills that also ship, after the scrub below.
SHARED_PERSONAL = frozenset({"productivity/business-cards"})
#: A skill whose frontmatter has no license, with the upstream's license.
KNOWN_UPSTREAM_LICENSE = {
    "ui-ux-pro-max": (
        "MIT",
        "nextlevelbuilder (https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)",
    ),
}
#: Never copied: build output, caches.
IGNORED_PARTS = frozenset({"__pycache__", ".pytest_cache", ".DS_Store"})
IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})

TEAM_OWNER = {"type": "organization", "id": "aep"}
PERSONAL_OWNER = {"type": "user", "id": "leo.chi"}

#: Hermes tools named in backticks, and the neutral words AEP uses instead.
TOOL_WORDS = {
    "terminal": "shell",
    "read_file": "read file",
    "write_file": "write file",
    "patch": "edit file",
    "search_files": "file search",
    "web_search": "web search",
    "web_extract": "web page reader",
    "vision_analyze": "image reading",
    "delegate_task": "sub-agent",
    "cronjob": "scheduler",
    "skill_view": "read a skill",
    "skill_manage": "edit a skill",
    "clarify": "ask the person",
    "send_message": "send a message",
    "browser_vision": "browser screenshot reading",
}
_BACKTICKED = re.compile(r"(?<!`)`([a-z_]+)`(?!`)")
_BROWSER_TOOL = re.compile(r"(?<!`)`browser_([a-z_]+)`(?!`)")

# What a real credential looks like in a file (not a placeholder such as
# `$AIRTABLE_API_KEY`). Any hit stops the port.
REAL_CREDENTIAL = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,}"
    r"|\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{32,}|\bxox[abpr]-[A-Za-z0-9-]{10,}"
    r"|\bAKIA[0-9A-Z]{16}\b|\bAIza[0-9A-Za-z_-]{35}\b"
    r"|\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
    r"|-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"
    r"|(?<!\d)\d{8,10}:AA[A-Za-z0-9_-]{33}(?![A-Za-z0-9_-])"
)
# What would identify the owner, his computer or his company's network.
PERSONAL_MARKERS = re.compile(
    r"\bLeo\b|\bChi_L\b|leo\.chi|dragon0816"
    r"|172\.25\.|rohde-schwarz\.com|\brsint\b|\.rsint\.|RS_Knowledge",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
#: Example and public addresses that may stay: documentation domains, and the
#: public contact of an upstream author kept for attribution.
ALLOWED_EMAIL_DOMAINS = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "company.com",
        "co.com",
        "gmail.com",
        "icloud.com",
        "github.com",
        "users.noreply.github.com",
        "cocoon-ai.com",
        "agent.ai",
        "anthropic.com",
    }
)


@dataclass(frozen=True)
class Scrub:
    """One reviewed replacement in a shipped copy. `pattern` is a regular
    expression (so the example names on the original card need not be
    written here); it must match exactly `count` times."""

    path: str
    pattern: str
    new: str
    why: str
    count: int = 1


def _literal(text: str) -> str:
    return re.escape(text).replace("\\\n", r"\r?\n")


#: business-cards, as it ships to colleagues: no owner name, no Hermes
#: delivery command, no owner data path, no names from a real card (2026-10-15).
BUSINESS_CARDS_SCRUB = (
    Scrub(
        "SKILL.md",
        _literal("description: Read a business card photo Leo sends on Telegram,"),
        "description: Read a business card photo the user sends,",
        "owner name and channel in the description",
    ),
    Scrub(
        "SKILL.md",
        r"(?m)^author: [^\r\n]*",
        "author: AEP (from an internal Hermes skill)",
        "owner name as author",
    ),
    Scrub(
        "SKILL.md",
        r"(?m)^license: UNLICENSED(?=\r?$)",
        "license: Internal use",
        "internal licence stated",
    ),
    Scrub(
        "SKILL.md",
        r"related_skills: \[rs-workflow-jobs\]",
        "related_skills: []",
        "reference to a personal skill",
    ),
    Scrub(
        "SKILL.md",
        _literal("Leo photographs cards and sends them on Telegram."),
        "The user photographs cards and sends them in the chat.",
        "owner name and channel",
    ),
    Scrub(
        "SKILL.md",
        r"costs Leo a call to nobody; a flagged one costs him a",
        "costs the user a call to nobody; a flagged one costs them a",
        "owner name",
    ),
    Scrub("SKILL.md", r"thing Leo wants", "thing the user wants", "owner name"),
    Scrub(
        "SKILL.md", r"contact data Leo collected", "contact data the user collected", "owner name"
    ),
    Scrub(
        "SKILL.md",
        r"showing both \S+ and [A-Z][a-z]+-[A-Z][a-z]+ [A-Z][a-z]+ stores \S+",
        "showing both 王小明 and Hsiao-Ming Wang stores 王小明",
        "example person name replaced by a placeholder name",
    ),
    Scrub(
        "SKILL.md",
        r'--name "[^"]+"',
        '--name "王小明"',
        "example person name replaced by a placeholder name",
    ),
    Scrub(
        "SKILL.md",
        r'--company "[^"]+"',
        '--company "範例公司"',
        "example company name replaced by a placeholder",
        count=2,
    ),
    Scrub(
        "SKILL.md",
        r"Then send it: `hermes send -t telegram [^`]+`, or attach it to\r?\n"
        r"your reply if the run already delivers to Telegram\.",
        "Then give it to the user: attach the PNG to your reply, or tell them its path.",
        "Hermes Telegram delivery command",
    ),
    Scrub(
        "SKILL.md",
        r"The store is SQLite at `%LOCALAPPDATA%\\hermes\\business-cards\\cards\.db`\.",
        "The store is SQLite at `cards.db` in the folder named by `BUSINESS_CARDS_HOME`\n"
        "(default `~/.business-cards`).",
        "owner's Hermes data path",
    ),
    Scrub(
        "scripts/cards.py",
        _literal(
            'HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))\n'
            'DB = HOME / "business-cards" / "cards.db"'
        ),
        'HOME = Path(os.environ.get("BUSINESS_CARDS_HOME", Path.home() / ".business-cards"))\n'
        'DB = HOME / "cards.db"',
        "own data folder instead of the Hermes one",
    ),
    Scrub(
        "scripts/cards.py",
        _literal('c.add_argument("--out", default=str(HOME / "business-cards" / "org.png"))'),
        'c.add_argument("--out", default=str(HOME / "org.png"))',
        "chart default in the same folder",
    ),
)
SCRUBS: dict[str, tuple[Scrub, ...]] = {"productivity/business-cards": BUSINESS_CARDS_SCRUB}


@dataclass
class Frontmatter:
    fields: dict[str, str]
    tags: list[str]
    platforms: list[str]
    commands: list[str]
    env_vars: list[str]
    homepage: str | None
    category: str | None


@dataclass
class Ported:
    key: str
    name: str
    version: str
    license: str
    author: str
    personal: bool
    shipped: bool
    source_sha256: str
    manifest: dict[str, Any]
    adaptations: list[str] = field(default_factory=list)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace('\\"', '"') if value[0] == '"' else inner.replace("''", "'")
    return value


def _flow_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    return [_unquote(item) for item in value[1:-1].split(",") if item.strip()]


def split_frontmatter(text: str) -> tuple[str, str]:
    """(frontmatter, body) of a SKILL.md; the frontmatter is between the
    first two `---` lines."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md has no frontmatter")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "".join(lines[1:index]), "".join(lines[index + 1 :])
    raise ValueError("SKILL.md frontmatter is not closed")


def parse_frontmatter(text: str) -> Frontmatter:
    """The fields a port needs, from the small YAML subset Hermes writes
    (top-level scalars, flow lists, `metadata.hermes.*`, `prerequisites.*`)."""
    fields: dict[str, str] = {}
    tags: list[str] = []
    platforms: list[str] = []
    commands: list[str] = []
    env_vars: list[str] = []
    homepage: str | None = None
    category: str | None = None
    parents: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or raw.lstrip().startswith("- "):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key, sep, value = raw.strip().partition(":")
        if not sep:
            continue
        while parents and parents[-1][0] >= indent:
            parents.pop()
        path = [name for _, name in parents] + [key]
        if not value.strip():
            parents.append((indent, key))
            continue
        if indent == 0:
            fields[key] = _unquote(value)
        if key == "tags" and (path == ["tags"] or path == ["metadata", "hermes", "tags"]):
            tags.extend(_flow_list(value))
        elif path == ["platforms"]:
            platforms = _flow_list(value)
        elif path == ["prerequisites", "commands"]:
            commands = _flow_list(value)
        elif path == ["prerequisites", "env_vars"]:
            env_vars = _flow_list(value)
        elif path == ["metadata", "hermes", "homepage"]:
            homepage = _unquote(value)
        elif path == ["metadata", "hermes", "category"]:
            category = _unquote(value)
    return Frontmatter(fields, tags, platforms, commands, env_vars, homepage, category)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def neutral_tools(text: str) -> str:
    """Hermes tool names in backticks become neutral words."""
    text = _BROWSER_TOOL.sub(
        lambda m: (
            m.group(0)
            if f"browser_{m.group(1)}" in TOOL_WORDS
            else f"browser ({m.group(1).replace('_', ' ')})"
        ),
        text,
    )
    return _BACKTICKED.sub(
        lambda m: TOOL_WORDS[m.group(1)] if m.group(1) in TOOL_WORDS else m.group(0), text
    )


def skill_dir_paths(text: str, category: str, name: str) -> str:
    """`~/.hermes/skills/[<category>/]<name>/` is this skill's own folder."""
    for prefix in (f"~/.hermes/skills/{category}/{name}/", f"~/.hermes/skills/{name}/"):
        text = text.replace(prefix, "<this skill's folder>/")
    return text


def redact_credentials(text: str) -> tuple[str, list[str]]:
    """Whatever the host's credential pattern sees becomes `[redacted]`;
    the placeholders it replaced (variable names, not values) are returned."""
    replaced: list[str] = []

    def one(match: re.Match[str]) -> str:
        found = match.group(0)
        replaced.append(found)
        if found.startswith("-----BEGIN"):
            return "[redacted]"
        if found.lower().startswith("bearer"):
            head_text, value = found[: len("bearer")], found[len("bearer") :].lstrip()
        else:
            head = re.match(r"^(.*?[=:]\s*)", found)
            head_text = head.group(1) if head else ""
            value = found[len(head_text) :]
        # An unquoted value swallowed the quote or bracket that closes the
        # surrounding code; give it back. A quoted value is replaced whole.
        closing = ""
        if value[:1] not in ("'", '"'):
            tail = re.search(r"[\"'`),;\]}]*$", value)
            closing = tail.group(0) if tail else ""
        separator = " " if found.lower().startswith("bearer") else ""
        return f"{head_text}{separator}[redacted]{closing}"

    return SECRET_PATTERN.sub(one, text), replaced


def _shorten(body: str, budget: int, folder: str) -> tuple[str, list[str]]:
    """Cut at the last `## ` heading that fits and name what was left out."""
    if len(body) <= budget:
        return body, []
    note_room = 1200
    cut = body.rfind("\n## ", 0, budget - note_room)
    if cut <= 0:
        cut = body.rfind("\n", 0, budget - note_room)
    kept, rest = body[:cut].rstrip(), body[cut:]
    omitted = [line[3:].strip() for line in rest.splitlines() if line.startswith("## ")]
    names = "; ".join(omitted)[:800] or "the remaining text"
    note = (
        f"\n\n(AEP: shortened to fit a Skill's instruction limit. Left out here: {names}. "
        f"The full text is in the coding-agent copy `{folder}/SKILL.md`.)"
    )
    return kept + note, omitted


def instructions_for(
    *,
    key: str,
    name: str,
    description: str,
    body: str,
    front: Frontmatter,
    license_name: str,
    author: str,
) -> tuple[str, list[str]]:
    category = key.split("/")[0]
    folder = FOLDER_PREFIX + name
    adaptations: list[str] = []
    text = skill_dir_paths(body.strip(), category, name)
    neutral = neutral_tools(text)
    if neutral != text:
        adaptations.append("Hermes tool names in neutral words")
    text, redacted = redact_credentials(neutral)
    if redacted:
        adaptations.append(f"{len(redacted)} credential placeholder(s) shown as [redacted]")
    placeholders = sorted(
        {name for item in redacted for name in re.findall(r"\$\{?([A-Z][A-Z0-9_]+)", item)}
    )
    needs = []
    if front.commands:
        needs.append("commands " + ", ".join(front.commands))
    if front.env_vars:
        needs.append("environment variables " + ", ".join(front.env_vars))
    header = (
        f"{description}\n\n"
        f"(AEP note: ported from the Hermes agent skill `{key}`, {license_name}, author "
        f"{author}. Hermes tool names are given in neutral words; a call written like "
        f"terminal(command=...) means: run it in a shell, if this runtime lets you. Use the "
        f"equivalent this runtime offers, and if it has none, say so instead of pretending. "
        f"`~/.hermes` and HERMES_HOME are the Hermes agent's own folders. Scripts, "
        f"references and templates named below are in the coding-agent copy of this Skill, "
        f"folder `{folder}`."
        + (f" Needs: {'; '.join(needs)}." if needs else "")
        + (
            " Values shown as [redacted] come from the environment, never from text"
            + (f" ({', '.join(placeholders)})" if placeholders else "")
            + "."
            if redacted
            else ""
        )
        + ")\n\n"
    )
    body_text, omitted = _shorten(text, MAX_INSTRUCTIONS_CHARS - len(header), folder)
    if omitted:
        adaptations.append(f"instructions shortened ({len(omitted)} section(s) left out)")
    return header + body_text, adaptations


def selector_hint(description: str, name: str) -> str:
    hint = re.sub(r"\s+", " ", description).strip() or name
    if len(hint) > MAX_SELECTOR_HINT:
        hint = hint[: MAX_SELECTOR_HINT - 1].rsplit(" ", 1)[0].rstrip(",;:.") + "…"
    return hint


def build_manifest(
    *,
    key: str,
    name: str,
    version: str,
    instructions: str,
    description: str,
    front: Frontmatter,
    license_name: str,
    author: str,
    source_sha256: str,
    personal: bool,
) -> dict[str, Any]:
    category = key.split("/")[0]
    categories: list[str] = []
    for item in [NAMESPACE, category, *(front.category or "").split(), *front.tags]:
        value = slug(item)
        if value and value not in categories:
            categories.append(value)
    if personal:
        source = f"Hermes agent skill {key} (internal, this PC only)"
    else:
        source = f"Hermes agent skill {key} ({license_name}; author {author}"
        source += f"; {front.homepage})" if front.homepage else ")"
    manifest: dict[str, Any] = {
        "metadata": {
            "identity": {"namespace": NAMESPACE, "name": name, "version": version},
            "owner": PERSONAL_OWNER if personal else TEAM_OWNER,
            "visibility": "private" if personal else "organization",
            "lifecycle": "published",
            "categories": categories,
            "provenance": [{"source": source, "revision": f"sha256:{source_sha256}"}],
            "compatibility": {"contract_version": "1", "platforms": front.platforms},
        },
        "alias": name.replace("-", "_"),
        "instructions": instructions,
        "selector_hint": selector_hint(description, name),
    }
    checked = SkillManifest.model_validate(manifest)
    return checked.model_dump(mode="json")


def _copy_tree(source: Path, target: Path) -> list[str]:
    copied: list[str] = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in IGNORED_PARTS for part in relative.parts) or path.suffix in IGNORED_SUFFIXES:
            continue
        if path.is_dir():
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        copied.append(relative.as_posix())
    return copied


def _rename_frontmatter(skill_md: Path, folder: str) -> None:
    data = skill_md.read_bytes()
    text = data.decode("utf-8")
    new, count = re.subn(r"(?m)^name:[^\r\n]*", f"name: {folder}", text, count=1)
    if count != 1:
        raise ValueError(f"{skill_md}: no frontmatter name")
    skill_md.write_bytes(new.encode("utf-8"))


def _constant(value: str) -> Callable[[re.Match[str]], str]:
    return lambda _: value


def _apply_scrubs(folder: Path, scrubs: tuple[Scrub, ...]) -> list[str]:
    done: list[str] = []
    for scrub in scrubs:
        path = folder / scrub.path
        text = path.read_bytes().decode("utf-8")
        newline = "\r\n" if "\r\n" in text else "\n"
        pattern = re.compile(scrub.pattern)
        found = len(pattern.findall(text))
        if found != scrub.count:
            raise ValueError(
                f"{scrub.path}: expected {scrub.count} match(es) for {scrub.why}, found {found}"
            )
        # A callable keeps backslashes in the replacement literal.
        text = pattern.sub(_constant(scrub.new.replace("\n", newline)), text)
        path.write_bytes(text.encode("utf-8"))
        done.append(f"{scrub.path}: {scrub.why}")
    return done


def scan_text(path: str, text: str, *, personal: bool) -> list[str]:
    """Problems that keep a file out of the repository."""
    problems: list[str] = []
    if REAL_CREDENTIAL.search(text):
        problems.append(f"{path}: looks like it holds a real credential")
    if personal:
        return problems
    for match in PERSONAL_MARKERS.finditer(text):
        problems.append(f"{path}: personal marker {match.group(0)!r}")
    for match in _EMAIL.finditer(text):
        domain = match.group(1).lower()
        if domain not in ALLOWED_EMAIL_DOMAINS and not domain.endswith(".example.com"):
            problems.append(f"{path}: email address at {domain}")
    return problems


def scan_tree(folder: Path, *, personal: bool) -> list[str]:
    problems: list[str] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        problems.extend(scan_text(path.relative_to(folder).as_posix(), text, personal=personal))
    return problems


def discover(source: Path) -> list[tuple[str, Path]]:
    """(category/name, folder) of every active Hermes skill; a skill folder
    directly under the root (no category) is keyed by its own name."""
    found: list[tuple[str, Path]] = []
    for skill_md in sorted(source.rglob("SKILL.md")):
        relative = skill_md.parent.relative_to(source)
        if any(part.startswith(".") for part in relative.parts):
            continue
        found.append((relative.as_posix(), skill_md.parent))
    return found


def port_one(
    key: str, folder: Path, target_root: Path, *, personal: bool, scrubs: tuple[Scrub, ...]
) -> Ported:
    name = key.rsplit("/", 1)[-1]
    agent_folder = FOLDER_PREFIX + name
    destination = target_root / "skills" / "vendor" / agent_folder
    if destination.exists():
        shutil.rmtree(destination)
    _copy_tree(folder, destination)
    adaptations = [f"frontmatter name set to {agent_folder}"]
    adaptations.extend(_apply_scrubs(destination, scrubs))
    skill_md = destination / "SKILL.md"
    text = skill_md.read_bytes().decode("utf-8")
    replaced = skill_dir_paths(text, key.split("/")[0], name)
    if replaced != text:
        skill_md.write_bytes(replaced.encode("utf-8"))
        adaptations.append("Hermes skill-folder paths written as <this skill's folder>")
    _rename_frontmatter(skill_md, agent_folder)

    original = (folder / "SKILL.md").read_bytes()
    source_sha256 = hashlib.sha256(original).hexdigest()
    front_text, body = split_frontmatter(skill_md.read_bytes().decode("utf-8"))
    front = parse_frontmatter(front_text)
    license_name = front.fields.get("license", "")
    author = front.fields.get("author", "")
    if not license_name and name in KNOWN_UPSTREAM_LICENSE:
        license_name, author = KNOWN_UPSTREAM_LICENSE[name]
        adaptations.append("license taken from the upstream repository (not in frontmatter)")
    version = front.fields.get("version") or "1.0.0"
    description = front.fields.get("description", name)
    instructions, more = instructions_for(
        key=key,
        name=name,
        description=description,
        body=body,
        front=front,
        license_name=license_name or "license not stated",
        author=author or "unknown",
    )
    adaptations.extend(more)
    manifest = build_manifest(
        key=key,
        name=name,
        version=version,
        instructions=instructions,
        description=description,
        front=front,
        license_name=license_name,
        author=author,
        source_sha256=source_sha256,
        personal=personal,
    )
    manifest_path = target_root / "manifests" / f"{NAMESPACE}__{name}__{version}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return Ported(
        key=key,
        name=name,
        version=version,
        license=license_name,
        author=author,
        personal=personal,
        shipped=not personal or key in SHARED_PERSONAL,
        source_sha256=source_sha256,
        manifest=manifest,
        adaptations=adaptations,
    )


def _index(ported: list[Ported]) -> dict[str, Any]:
    return {
        "pack": "hermes",
        "pack_version": PACK_VERSION,
        "namespace": NAMESPACE,
        "agent_folder_prefix": FOLDER_PREFIX,
        "default_enabled": False,
        "source": "Hermes agent skills folder (<category>/<name>/SKILL.md), read only",
        "skipped": sorted(SKIPPED),
        "skills": [
            {
                "source": item.key,
                "name": item.name,
                "version": item.version,
                "license": item.license,
                "author": item.author,
                "source_sha256": item.source_sha256,
                "manifest": f"manifests/{NAMESPACE}__{item.name}__{item.version}.json",
                "agent_folder": f"skills/vendor/{FOLDER_PREFIX}{item.name}",
                "default_enabled": False,
                "adaptations": item.adaptations,
            }
            for item in ported
        ],
    }


def _notice(ported: list[Ported]) -> str:
    lines = [
        "# Hermes skill pack: sources and licenses",
        "",
        "These skills are ported from the Hermes agent's skills folder",
        "(`<category>/<name>/SKILL.md` and supporting files) by",
        "`scripts/port_hermes_skills.py`. Each keeps its original license and",
        "authors, listed below; the license text a skill ships with (`LICENSE` in",
        "its folder) is kept with it. The MIT License grants permission to use, copy,",
        "modify and distribute the software provided the copyright notice and",
        "permission notice are included; the frontmatter `author` and `license`",
        "fields of every `SKILL.md` are kept unchanged for that reason.",
        "",
        "`business-cards` is an internal skill of this platform's owner, shared",
        "with colleagues after the scrub recorded in `pack.json` (no owner name,",
        "data path or delivery command); it is for use inside the company only.",
        "",
        "Every skill installs switched off. Changes made in the port are listed",
        "per skill in `pack.json` (`adaptations`).",
        "",
        "| Skill | Hermes source | Version | License | Authors |",
        "|---|---|---|---|---|",
    ]
    for item in ported:
        lines.append(
            f"| {FOLDER_PREFIX}{item.name} | {item.key} | {item.version} | "
            f"{item.license} | {item.author.replace('|', '/')} |"
        )
    lines.append("")
    return "\n".join(lines)


def port(
    source: Path,
    out: Path,
    *,
    personal_out: Path | None = None,
    log: Callable[[str], None] = print,
) -> tuple[list[Ported], list[Ported]]:
    """Port every active skill; returns (shipped, personal-only)."""
    shipped: list[Ported] = []
    personal_only: list[Ported] = []
    problems: list[str] = []
    seen = {key for key, _ in discover(source)}
    for expected in sorted(SKIPPED | PERSONAL):
        if expected not in seen:
            log(f"note: {expected} is not in the source folder")
    out.mkdir(parents=True, exist_ok=True)
    for target in (out / "skills" / "vendor", out / "manifests"):
        if target.exists():
            shutil.rmtree(target)
    if personal_out is not None:
        personal_out.mkdir(parents=True, exist_ok=True)
        for target in (personal_out / "skills" / "vendor", personal_out / "manifests"):
            if target.exists():
                shutil.rmtree(target)
    for key, folder in discover(source):
        if key in SKIPPED:
            continue
        if key in PERSONAL:
            if personal_out is not None:
                item = port_one(key, folder, personal_out, personal=True, scrubs=())
                problems.extend(
                    scan_tree(
                        personal_out / "skills" / "vendor" / (FOLDER_PREFIX + item.name),
                        personal=True,
                    )
                )
                personal_only.append(item)
            if key not in SHARED_PERSONAL:
                continue
            item = port_one(key, folder, out, personal=False, scrubs=SCRUBS.get(key, ()))
        else:
            item = port_one(key, folder, out, personal=False, scrubs=())
            if item.license != "MIT":
                problems.append(f"{key}: license {item.license!r} is not MIT")
        problems.extend(
            scan_tree(out / "skills" / "vendor" / (FOLDER_PREFIX + item.name), personal=False)
        )
        problems.extend(
            scan_text(
                f"manifest {item.name}",
                json.dumps(item.manifest, ensure_ascii=False),
                personal=False,
            )
        )
        shipped.append(item)
    if problems:
        raise SystemExit("port refused:\n  " + "\n  ".join(problems))
    (out / "pack.json").write_text(
        json.dumps(_index(shipped), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (out / "NOTICE.md").write_text(_notice(shipped), encoding="utf-8", newline="\n")
    if personal_out is not None:
        (personal_out / "pack.json").write_text(
            json.dumps(_index(personal_only), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return shipped, personal_only


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--source", type=Path, required=True, help="Hermes skills folder")
    parser.add_argument("--out", type=Path, required=True, help="the pack folder to write")
    parser.add_argument(
        "--personal-out",
        type=Path,
        help="where the internal skills go (outside the repository; this PC only)",
    )
    args = parser.parse_args(argv)
    if args.personal_out is not None and args.personal_out.resolve().is_relative_to(REPO):
        parser.error("--personal-out must be outside the repository")
    shipped, personal_only = port(args.source, args.out, personal_out=args.personal_out)
    by_category: dict[str, int] = {}
    for item in shipped:
        category = item.key.split("/")[0] if "/" in item.key else "(none)"
        by_category[category] = by_category.get(category, 0) + 1
    print(f"pack: {len(shipped)} skills -> {args.out}")
    for category, count in sorted(by_category.items()):
        print(f"  {category}: {count}")
    if args.personal_out is not None:
        print(f"personal: {len(personal_only)} skills -> {args.personal_out}")
    for item in shipped + personal_only:
        extra = [a for a in item.adaptations if not a.startswith("frontmatter name")]
        if extra:
            print(f"  {item.key}: {'; '.join(extra)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
