"""Revising an installed Workflow from a conversation (owner 2026-10-19).

`docs/phases/WORKFLOW_REVISION.md`. The Agent could not build on an
installed Workflow: `authoring__get_workflow` read only chat candidates, and a
Workflow whose logic ships as a capability package had no readable source, so
the Agent rewrote it from scratch. These are the pure parts of the fix:

- resolving a Workflow reference (`namespace/name@version`, `name@version`,
  `namespace/name` or a bare name) among the installed manifests the actor
  may read, and the view of one manifest the model gets, paged under a size
  cap;
- the revision summary the in-chat install card shows (changed steps, inputs
  and parameters, the script line delta);
- the read-only, size-capped view of a capability package's Python source
  shipped inside AEP.

`ChatAuthoring` owns the records; nothing here writes a file.
"""

from __future__ import annotations

import difflib
import json
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from common.assets import (
    SECRET_PATTERN,
    AssetMetadata,
    FixedInput,
    WorkflowManifest,
    WorkflowStep,
)

#: The most JSON characters one view returns; the rest is read with `offset`.
MAX_VIEW_CHARS = 20_000
#: The most source characters one capability-source call returns.
MAX_SOURCE_CHARS = 20_000
#: Lines of the summary a card shows per kind of change.
MAX_DIFF_LINES = 12

_REFERENCE = re.compile(
    r"^(?:(?P<namespace>[a-z0-9]+(?:-[a-z0-9]+)*)/)?(?P<name>[a-z0-9]+(?:-[a-z0-9]+)*)"
    r"(?:@(?P<version>[0-9][0-9A-Za-z.+-]*))?$"
)


def key(identity: Any) -> str:
    return f"{identity.namespace}/{identity.name}@{identity.version}"


def _version_order(version: str) -> tuple[int, ...]:
    core = version.split("-", 1)[0].split("+", 1)[0]
    try:
        return tuple(int(part) for part in core.split("."))
    except ValueError:
        return (0,)


# -- who may read which installed Workflow ---------------------------------------


def readable(metadata: AssetMetadata, actor: str) -> bool:
    """Whether a Workflow installed on this Host may be shown to this actor.

    Its owner and recorded contributors always may. Otherwise it must be
    published, and either owned by a team, organization or service (it came
    with the bundle, the Marketplace or a Shared Platform selection, which
    already decided the actor may use it) or visible to the organization. A
    person's own `private` or `team` Workflow stays with that person."""
    owner = metadata.owner
    if (owner.type == "user" and owner.id == actor) or actor in metadata.contributors:
        return True
    if metadata.lifecycle != "published":
        return False
    return owner.type != "user" or metadata.visibility in ("organization", "public")


def may_revise_in_place(metadata: AssetMetadata, actor: str, namespace: str) -> bool:
    """The owner or a co-editor (a recorded contributor) publishes the next
    version of the same name; anyone else forks it under a new name."""
    if metadata.identity.namespace != namespace:
        return False
    owner = metadata.owner
    return (owner.type == "user" and owner.id == actor) or actor in metadata.contributors


def parse_reference(text: str) -> tuple[str | None, str, str | None] | None:
    match = _REFERENCE.fullmatch(text.strip())
    if match is None:
        return None
    return match.group("namespace"), match.group("name"), match.group("version")


def resolve(
    manifests: Iterable[WorkflowManifest], reference: str, actor: str
) -> tuple[WorkflowManifest | None, str, list[str]]:
    """The one readable installed Workflow `reference` names: the exact
    version, or the highest installed version of a name. Returns it, or None
    with a code and the readable names that come closest (never another
    actor's private ones)."""
    visible = [m for m in manifests if readable(m.metadata, actor)]
    parsed = parse_reference(reference)
    if parsed is None:
        return None, "workflow_reference_invalid", []
    namespace, name, version = parsed
    found = [
        m
        for m in visible
        if m.metadata.identity.name == name
        and (namespace is None or m.metadata.identity.namespace == namespace)
        and (version is None or m.metadata.identity.version == version)
    ]
    if not found:
        names = sorted({key(m.metadata.identity) for m in visible})
        close = (
            difflib.get_close_matches(reference.strip(), names, n=5, cutoff=0.3)
            or [item for item in names if name in item][:5]
        )
        return None, "workflow_unknown", close
    spaces = {m.metadata.identity.namespace for m in found}
    if len(spaces) > 1:
        return None, "workflow_ambiguous", sorted(key(m.metadata.identity) for m in found)
    best = max(found, key=lambda m: _version_order(m.metadata.identity.version))
    return best, "", []


# -- the view the model reads ------------------------------------------------------


def view(manifest: WorkflowManifest) -> dict[str, JsonValue]:
    """Everything the model needs to revise a Workflow: its parameters and
    steps with every input (an embedded script is a fixed input), checks and
    progress stages. Approvals, validation references and package details are
    left out; a manifest never holds a credential (`RegistryContract`) and
    secrets appear by name only."""
    metadata = manifest.metadata
    body: dict[str, JsonValue] = {
        "workflow": key(metadata.identity),
        "owner": f"{metadata.owner.type}:{metadata.owner.id}",
        "visibility": metadata.visibility,
        "lifecycle": metadata.lifecycle,
        "description": manifest.description,
        "parameters": [p.model_dump(mode="json") for p in manifest.parameters],
        "steps": [step.model_dump(mode="json") for step in manifest.steps],
    }
    if manifest.checks:
        body["checks"] = [c.model_dump(mode="json") for c in manifest.checks]
    if manifest.progress_steps:
        body["progress_steps"] = [p.model_dump(mode="json") for p in manifest.progress_steps]
    if manifest.occupies_machine:
        body["occupies_machine"] = True
    if manifest.secrets:
        body["secret_names"] = [ref.name for ref in manifest.secrets]
    return body


def page(
    body: dict[str, JsonValue], offset: int = 0, limit: int = MAX_VIEW_CHARS
) -> dict[str, JsonValue]:
    """`body` itself when it fits; otherwise one slice of its JSON text with
    a notice saying it was cut and how to read the rest."""
    text = json.dumps(body, ensure_ascii=False)
    if offset <= 0 and len(text) <= limit:
        return body
    start = max(0, min(offset, len(text)))
    end = min(len(text), start + limit)
    more = end < len(text)
    return {
        "workflow": body.get("workflow"),
        "truncated": more or start > 0,
        "total_chars": len(text),
        "offset": start,
        "next_offset": end if more else None,
        "json_text": text[start:end],
        "notice": (
            f"The full Workflow is {len(text)} characters of JSON; this shows characters "
            f"{start}-{end}. "
            + (
                f"Call again with the same reference and offset={end} for the rest; join the "
                "slices before editing."
                if more
                else "This is the last slice."
            )
        ),
    }


# -- what the install card says about a revision ----------------------------------


def _fixed_texts(value: JsonValue, path: str = "") -> dict[str, str]:
    """Every string in a fixed value, by its dotted path."""
    found: dict[str, str] = {}
    if isinstance(value, str):
        found[path] = value
    elif isinstance(value, dict):
        for name, item in value.items():
            found.update(_fixed_texts(item, f"{path}.{name}" if path else str(name)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.update(_fixed_texts(item, f"{path}[{index}]"))
    return found


def _line_delta(before: str, after: str) -> tuple[int, int]:
    added = removed = 0
    for line in difflib.ndiff(before.splitlines(), after.splitlines()):
        if line.startswith("+ "):
            added += 1
        elif line.startswith("- "):
            removed += 1
    return added, removed


def _step_label(index: int, step: object) -> str:
    if isinstance(step, WorkflowStep):
        return f"step {index + 1} ({key(step.capability)})"
    return f"step {index + 1}"


def revision_summary(base: WorkflowManifest, draft: WorkflowManifest) -> list[str]:
    """Short lines: changed steps and inputs, parameters, and for each
    multi-line fixed text (an embedded script) its line delta. Empty when
    the draft does exactly what the base does."""
    lines: list[str] = []
    if base.description != draft.description:
        lines.append("Description changed.")
    old_params = {p.name: p.model_dump(mode="json") for p in base.parameters}
    new_params = {p.name: p.model_dump(mode="json") for p in draft.parameters}
    added = [name for name in new_params if name not in old_params]
    removed = [name for name in old_params if name not in new_params]
    changed = [
        name for name in new_params if name in old_params and new_params[name] != old_params[name]
    ]
    for label, names in (("added", added), ("removed", removed), ("changed", changed)):
        if names:
            lines.append(f"Parameters {label}: {', '.join(names[:MAX_DIFF_LINES])}")
    steps: list[str] = []
    count = max(len(base.steps), len(draft.steps))
    for index in range(count):
        old = base.steps[index] if index < len(base.steps) else None
        new = draft.steps[index] if index < len(draft.steps) else None
        if old is None and new is not None:
            steps.append(f"{_step_label(index, new)} added")
            continue
        if new is None and old is not None:
            steps.append(f"{_step_label(index, old)} removed")
            continue
        if old == new:
            continue
        if not isinstance(old, WorkflowStep) or not isinstance(new, WorkflowStep):
            steps.append(f"{_step_label(index, new)} replaced")
            continue
        if old.capability != new.capability:
            steps.append(f"step {index + 1}: {key(old.capability)} → {key(new.capability)}")
        names = sorted(set(old.inputs) | set(new.inputs))
        touched = [n for n in names if old.inputs.get(n) != new.inputs.get(n)]
        details: list[str] = []
        for name in touched:
            before, after = old.inputs.get(name), new.inputs.get(name)
            shown = len(details)
            if isinstance(before, FixedInput) and isinstance(after, FixedInput):
                old_texts = _fixed_texts(before.value)
                new_texts = _fixed_texts(after.value)
                for path in sorted(set(old_texts) | set(new_texts)):
                    a, b = old_texts.get(path, ""), new_texts.get(path, "")
                    if a != b and ("\n" in a or "\n" in b):
                        plus, minus = _line_delta(a, b)
                        where = f"{name}.{path}" if path else name
                        details.append(f"{where} +{plus}/−{minus} lines")
            if len(details) == shown:
                details.append(f"input {name} changed")
        if old.retry != new.retry:
            details.append("retry changed")
        if details:
            steps.append(f"{_step_label(index, new)}: " + "; ".join(details))
    lines.extend(steps[:MAX_DIFF_LINES])
    if len(steps) > MAX_DIFF_LINES:
        lines.append(f"… and {len(steps) - MAX_DIFF_LINES} more step changes")
    if base.checks != draft.checks:
        lines.append("Output checks changed.")
    return lines


# -- the source of a capability that ships in AEP ----------------------------------


def capabilities_root() -> Path:
    import capabilities

    return Path(capabilities.__file__).resolve().parent


def _packages(root: Path) -> list[str]:
    return sorted(
        item.name
        for item in root.iterdir()
        if item.is_dir() and (item / "__init__.py").is_file() and not item.name.startswith("_")
    )


def _allowed(path: Path) -> bool:
    """Python sources, and manifest files; never caches or anything else."""
    if "__pycache__" in path.parts or path.name.startswith("."):
        return False
    if path.suffix == ".py":
        return True
    return path.stem.startswith("manifest") and path.suffix in (".json", ".yaml", ".yml")


def _files(package: Path) -> list[Path]:
    return sorted(path for path in package.rglob("*") if path.is_file() and _allowed(path))


def package_of(reference: str, handlers: Sequence[tuple[str, str, object]]) -> str | None:
    """The capability package a reference names: a package folder
    (`weekly_report`, `capabilities.weekly_report`), or an installed
    capability (`engineering/weekly-report@1.0.0`, its target without the
    version, or its registered name), found through its handler's module."""
    text = reference.strip()
    root = capabilities_root()
    packages = _packages(root)
    bare = text.removeprefix("capabilities.").split(".", 1)[0]
    if bare in packages:
        return bare
    for target, name, handler in handlers:
        if text not in (target, target.split("@", 1)[0], name, target.split("/", 1)[-1]):
            continue
        func = getattr(handler, "func", handler)
        module = getattr(func, "__module__", None) or type(func).__module__
        parts = str(module).split(".")
        if len(parts) >= 2 and parts[0] == "capabilities" and parts[1] in packages:
            return parts[1]
    return None


def capability_source(
    reference: str,
    file: str | None,
    offset: int,
    handlers: Sequence[tuple[str, str, object]],
    *,
    root: Path | None = None,
    limit: int = MAX_SOURCE_CHARS,
) -> dict[str, JsonValue]:
    """Read-only. Without `file`, the package's readable files; with it,
    that file's text, a slice at a time. Anything outside the package's
    folder, or not a Python or manifest file, is refused."""
    base = (root or capabilities_root()).resolve()
    package_name = (
        package_of(reference, handlers)
        if root is None
        else (reference if reference in _packages(base) else None)
    )
    if package_name is None:
        return {
            "ok": False,
            "code": "capability_package_unknown",
            "packages": list(_packages(base)),
            "next": "name a package from this list, or an installed capability target",
        }
    package = (base / package_name).resolve()
    files = _files(package)
    listing: list[JsonValue] = [
        {
            "file": path.relative_to(package).as_posix(),
            "chars": len(path.read_text(encoding="utf-8", errors="replace")),
        }
        for path in files
    ]
    common: dict[str, JsonValue] = {
        "package": f"capabilities.{package_name}",
        "read_only": True,
        "how_to_change": (
            "This code ships inside AEP and is never edited here. To change what a Workflow "
            "built on it does, revise the Workflow (authoring__revise_workflow): adjust a "
            "parameter or fixed input when the capability offers one, or replace the step "
            "with a coding/run-python step carrying the adjusted logic."
        ),
    }
    if not file:
        return {"ok": True, **common, "files": listing}
    wanted = file.replace("\\", "/").strip()
    if (
        not wanted
        or wanted.startswith("/")
        or ":" in wanted
        or any(part in ("..", "") for part in wanted.split("/"))
    ):
        return {"ok": False, "code": "capability_file_refused", **common, "files": listing}
    target = (package / wanted).resolve()
    if not target.is_relative_to(package) or target not in files:
        return {"ok": False, "code": "capability_file_refused", **common, "files": listing}
    text = target.read_text(encoding="utf-8", errors="replace")
    # Shipped code holds no credential; a line that looks like one is masked anyway.
    text = SECRET_PATTERN.sub("[redacted]", text)
    start = max(0, min(offset, len(text)))
    end = min(len(text), start + limit)
    more = end < len(text)
    return {
        "ok": True,
        **common,
        "file": wanted,
        "total_chars": len(text),
        "offset": start,
        "next_offset": end if more else None,
        "truncated": more or start > 0,
        "source": text[start:end],
        **(
            {"notice": f"Cut at {end} of {len(text)} characters; call again with offset={end}."}
            if more
            else {}
        ),
    }
