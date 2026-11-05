"""Skills inside a knowledge repository (R3, the part every type shares).

Design: `docs/phases/KNOWLEDGE_REPO.md` §8. A skill revision is a file
`skills/<name>/rev-<n>-<author>.md`, written once: Markdown with a frontmatter
head (`name`, `revision`, `schema`, `role`, `applies_to`, optional
`card_types` and `table_recipes`) and the instructions as its body.

A revision becomes current through the unit `skill:<name>`, whose value names
the revision's path, its schema version, role and folders; so a skill is
committed, pushed, merged and reverted with everything else. A type whose layout
has homes (`FileLayout.skill_area`) also keeps skills in them: the unit is
`skill:<home>/<name>`, and that longer form is the name `current_skills` lists
and `read_skill` takes; the file's own `name` stays short. A skill whose
`schema` is not the repository's current `schema` unit needs an update and is
not run (owner decision 3).

The frontmatter is the small dialect AEP writes: one `key: value` per line,
lists and objects as JSON (which is also YAML flow syntax), strings plain or
JSON-quoted. No YAML library is needed.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from knowledge.repo.repository import (
    AUTHOR_RE,
    DEFAULT_LAYOUT,
    SCHEMA_UNIT,
    SKILL_UNIT_PREFIX,
    FileLayout,
    RepoError,
    Repository,
    layout_of,
)

SKILLS_DIR = "skills"
ROLES = ("classify", "extract", "ingest")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME = 60
REVISION_PATH_RE = re.compile(
    r"^skills/(?P<name>[a-z0-9]+(?:-[a-z0-9]+)*)/rev-(?P<revision>[1-9][0-9]{0,5})-"
    r"(?P<author>[a-z0-9]+(?:[._-][a-z0-9]+)*)\.md$"
)
KNOWN_KEYS = ("name", "revision", "schema", "role", "applies_to", "card_types", "table_recipes")
_LINE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*):(?P<value>.*)$")
_PLAIN = re.compile(r"^[^\s\"'\[\]{}#&*!|>%@`,][^:#]*$")


@dataclass(frozen=True)
class Skill:
    """One skill revision."""

    name: str
    revision: int
    schema: str
    role: str
    applies_to: tuple[str, ...]
    body: str
    card_types: tuple[str, ...] = ()
    table_recipes: tuple[dict[str, Any], ...] = ()
    extra: dict[str, str] = field(default_factory=dict)
    #: Which part of the repository owns it, in a layout with homes; never in the file.
    home: str = ""

    @property
    def unit_name(self) -> str:
        """The name in its unit key: `<home>/<name>`, or `<name>` with no home."""
        return f"{self.home}/{self.name}" if self.home else self.name

    def path(self, author: str, area: str = SKILLS_DIR) -> str:
        return revision_path(self.name, self.revision, author, area)

    def unit_value(self, author: str, area: str = SKILLS_DIR) -> dict[str, Any]:
        """The value of `skill:<name>` that makes this revision current."""
        return {
            "path": self.path(author, area),
            "revision": self.revision,
            "schema": self.schema,
            "role": self.role,
            "applies_to": list(self.applies_to),
        }


def _invalid(message: str) -> RepoError:
    return RepoError("skill_invalid", message)


def skill_unit(name: str) -> str:
    return SKILL_UNIT_PREFIX + name


def revision_path(name: str, revision: int, author: str, area: str = SKILLS_DIR) -> str:
    """The repository path of a skill revision."""
    if len(name) > MAX_NAME or not NAME_RE.match(name):
        raise _invalid("skill 名稱只能用小寫英數字與 -（最多 60 個字）")
    if revision < 1:
        raise _invalid("revision 必須是正整數")
    if not AUTHOR_RE.match(author):
        raise RepoError("author_invalid", "作者名稱無效")
    return f"{area}/{name}/rev-{revision}-{author}.md"


def _scalar(text: str) -> Any:
    text = text.strip()
    if text[:1] in ('"', "[", "{"):
        try:
            return json.loads(text)
        except ValueError:
            if text.startswith("[") and text.endswith("]"):
                inner = text[1:-1].strip()
                return [p.strip().strip("'\"") for p in inner.split(",")] if inner else []
            raise _invalid(f"frontmatter 的值無法讀取：{text}") from None
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1]
    return text


def _front(text: str) -> tuple[dict[str, Any], str]:
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        raise _invalid("skill 檔案必須以 --- 開頭的 frontmatter 開始")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise _invalid("frontmatter 沒有結束的 ---") from None
    fields: dict[str, Any] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        matched = _LINE.match(line)
        if matched is None:
            raise _invalid(f"frontmatter 這一行看不懂：{line}")
        value = matched.group("value")
        # A trailing comment after plain text (`role: extract  # …`) is not part of it.
        if value.strip()[:1] not in ('"', "[", "{", "'"):
            value = value.split(" #", 1)[0]
        fields[matched.group("key")] = _scalar(value)
    return fields, "\n".join(lines[end + 1 :]).strip("\n")


def _strings(value: Any, key: str) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise _invalid(f"{key} 必須是文字清單")
    return tuple(v.strip() for v in value)


def parse_skill(
    text: str, *, path: str | None = None, layout: FileLayout = DEFAULT_LAYOUT
) -> Skill:
    """A skill revision from its file text; `skill_invalid` when it is not one.
    With `path`, its name and revision must match the file name."""
    fields, body = _front(text)
    name = fields.get("name")
    if not isinstance(name, str) or len(name) > MAX_NAME or not NAME_RE.match(name):
        raise _invalid("name 必須是小寫英數字與 -（最多 60 個字）")
    revision = fields.get("revision")
    if isinstance(revision, str) and revision.isdigit():
        revision = int(revision)
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise _invalid("revision 必須是正整數")
    schema = fields.get("schema")
    if not isinstance(schema, str) or "@" not in schema or not schema.split("@")[-1]:
        raise _invalid("schema 必須寫出 schema 版本，例如 bi.schema/v1.1@2.0.0")
    role = fields.get("role")
    if role not in ROLES:
        raise _invalid(f"role 必須是 {'、'.join(ROLES)} 之一")
    applies_to = tuple(p.rstrip("/") for p in _strings(fields.get("applies_to"), "applies_to"))
    for prefix in applies_to:
        problem = layout.source_folder_problem(prefix)
        if problem:
            raise _invalid(f"applies_to 的 {prefix} {problem}")
    recipes = fields.get("table_recipes") or []
    if not isinstance(recipes, list) or not all(isinstance(r, dict) for r in recipes):
        raise _invalid("table_recipes 必須是物件清單")
    if not body.strip():
        raise _invalid("skill 的說明（frontmatter 之後的內容）不能是空的")
    extra = {k: str(v) for k, v in fields.items() if k not in KNOWN_KEYS}
    skill = Skill(
        name=name,
        revision=revision,
        schema=schema,
        role=str(role),
        applies_to=applies_to,
        body=body.strip("\n"),
        card_types=_strings(fields.get("card_types"), "card_types"),
        table_recipes=tuple(recipes),
        extra=extra,
    )
    if path is not None:
        matched = (layout.skill_path_re or REVISION_PATH_RE).match(path)
        if matched is None:
            raise _invalid(f"{path} 不是 skills/<name>/rev-<n>-<author>.md")
        if matched.group("name") != skill.name or int(matched.group("revision")) != skill.revision:
            raise _invalid(f"{path} 的名稱或 revision 和檔案內容不同")
    return skill


def _render_value(value: Any) -> str:
    if isinstance(value, str) and _PLAIN.match(value) and value == value.strip():
        return value
    return json.dumps(value, ensure_ascii=False)


def render_skill(skill: Skill) -> str:
    """The file text of a skill revision; `parse_skill` reads it back unchanged."""
    head: list[tuple[str, Any]] = [
        ("name", skill.name),
        ("revision", skill.revision),
        ("schema", skill.schema),
        ("role", skill.role),
        ("applies_to", list(skill.applies_to)),
    ]
    if skill.card_types:
        head.append(("card_types", list(skill.card_types)))
    if skill.table_recipes:
        head.append(("table_recipes", list(skill.table_recipes)))
    head += sorted(skill.extra.items())
    lines = [
        "---",
        *(f"{k}: {_render_value(v)}" for k, v in head),
        "---",
        "",
        skill.body.strip("\n"),
    ]
    return "\n".join(lines) + "\n"


# -- skills in a repository --------------------------------------------------------


def current_skills(
    repo: Repository, units: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    """The current skills (working units by default), with `needs_update` when a
    skill's schema is not the repository's schema."""
    units = repo.working_units() if units is None else units
    schema = units.get(SCHEMA_UNIT)
    schema_ref = schema.get("ref") if isinstance(schema, dict) else schema
    # A type may tell which skills a schema change really touches; by default all of them.
    review = getattr(repo.kind, "skill_review", None)
    found = []
    for key in sorted(units):
        if not key.startswith(SKILL_UNIT_PREFIX):
            continue
        value = units[key]
        if not isinstance(value, dict):
            continue
        found.append(
            {
                "name": key.removeprefix(SKILL_UNIT_PREFIX),
                "revision": value.get("revision"),
                "path": value.get("path"),
                "schema": value.get("schema"),
                "role": value.get("role"),
                "applies_to": list(value.get("applies_to") or []),
                "needs_update": bool(schema_ref) and value.get("schema") != schema_ref,
                **(
                    {}
                    if review is None
                    else review(repo, key.removeprefix(SKILL_UNIT_PREFIX), value, units)
                ),
            }
        )
    return found


def read_skill(repo: Repository, name: str, units: Mapping[str, Any] | None = None) -> Skill:
    """The current revision of skill `name`: from the folder, or from the working
    copy when it is staged and not pushed yet."""
    units = repo.working_units() if units is None else units
    value = units.get(skill_unit(name))
    if not isinstance(value, dict) or not isinstance(value.get("path"), str):
        raise RepoError("skill_unknown", f"知識庫裡沒有 skill「{name}」")
    path = value["path"]
    layout = layout_of(repo.kind)
    for root in (repo.folder, repo.work / "files"):
        candidate = root / path
        if candidate.is_file():
            skill = parse_skill(candidate.read_text(encoding="utf-8"), path=path, layout=layout)
            return replace(skill, home=name.rpartition("/")[0])
    raise RepoError("skill_missing", f"找不到 {path}（OneDrive 是否還在同步？）")


def stage_skill(repo: Repository, skill: Skill) -> dict[str, Any]:
    """Stage a new revision of `skill` (its revision is set to the next one) and
    make it current in the working copy. Returns the unit value."""
    units = repo.working_units()
    layout = layout_of(repo.kind)
    area = layout.skill_area(skill.home)
    current = units.get(skill_unit(skill.unit_name))
    revision = int(current.get("revision") or 0) + 1 if isinstance(current, dict) else 1
    revised = replace(skill, revision=revision)
    # A type may say what a revision is written against; by default the schema it names.
    binding = getattr(repo.kind, "skill_binding", None)
    extra = dict(binding(units, revised.schema)) if binding is not None else {}
    revised = replace(revised, schema=str(extra.pop("schema", revised.schema)))
    text = render_skill(revised)
    parse_skill(text, layout=layout)  # the file reads back as written
    path = revised.path(repo.author, area)
    draft = repo.local / "drafts" / f"{uuid.uuid4().hex[:8]}.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(text, encoding="utf-8")
    try:
        repo.stage_file(path, draft)
    finally:
        draft.unlink(missing_ok=True)
    value = {**revised.unit_value(repo.author, area), **extra}
    repo.stage(skill_unit(skill.unit_name), value)
    return value


def _matches(prefix: str, source: str) -> bool:
    return prefix == "sources" or source == prefix or source.startswith(prefix + "/")


def skill_for(
    repo: Repository,
    source: str,
    role: str,
    units: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """The skill of `role` for the source at repository path `source`: the one
    whose `applies_to` folder is the longest prefix of it; a skill with no
    `applies_to` applies to every source, after any that names a folder."""
    found: list[tuple[int, str, dict[str, Any]]] = []
    for item in current_skills(repo, units):
        if item["role"] != role:
            continue
        prefixes = item["applies_to"] or ["sources"]
        lengths = [len(p) if p != "sources" else 0 for p in prefixes if _matches(p, source)]
        if lengths:
            found.append((max(lengths), item["name"], item))
    if not found:
        return None
    # The longest folder wins; equal ones go to the first name, the same on every PC.
    return min(found, key=lambda f: (-f[0], f[1]))[2]


def runnable(repo: Repository, name: str, units: Mapping[str, Any] | None = None) -> Skill:
    """Skill `name` ready to run; `skill_needs_update` when it was written for
    another schema version than the repository's (decision 3)."""
    units = repo.working_units() if units is None else units
    item = next((s for s in current_skills(repo, units) if s["name"] == name), None)
    if item is None:
        raise RepoError("skill_unknown", f"知識庫裡沒有 skill「{name}」")
    if item["needs_update"] and item.get("update_blocks", True):
        schema = units.get(SCHEMA_UNIT)
        current = schema.get("ref") if isinstance(schema, dict) else schema
        raise RepoError(
            "skill_needs_update",
            f"skill「{name}」是為 {item['schema']} 寫的，知識庫現在用 {current}；"
            "請先更新這個 skill",
            skill=name,
            skill_schema=item["schema"],
            schema=current,
        )
    return read_skill(repo, name, units)


def skill_paths(folder: Path) -> list[str]:
    """Every skill revision file in a repository folder (repository paths)."""
    root = folder / SKILLS_DIR
    if not root.is_dir():
        return []
    return sorted(
        p.relative_to(folder).as_posix()
        for p in root.glob("*/rev-*.md")
        if REVISION_PATH_RE.match(p.relative_to(folder).as_posix())
    )
