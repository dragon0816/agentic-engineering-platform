"""A Skill install card names a switched-off Skill of the same name (owner 2026-10-20).

The card keeps its Install button; the line only tells the person that the
existing Skill can be switched on in Capabilities instead.
"""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from host_runtime.draft_cards import switched_off_twins

HERMES = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "hermes-skill-pack"
    / "manifests"
    / "hermes__business-cards__1.0.0.json"
)


def skills_dir(tmp_path: Path, *, enabled: bool) -> Path:
    folder = tmp_path / "skills"
    target = folder if enabled else folder / "disabled"
    target.mkdir(parents=True)
    shutil.copy(HERMES, target / HERMES.name)
    return folder


def identity(namespace: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(namespace=namespace, name=name, version="1.0.0")


def test_a_draft_named_like_a_switched_off_skill_gets_the_note(tmp_path: Path) -> None:
    name = json.loads(HERMES.read_text(encoding="utf-8"))["metadata"]["identity"]["name"]
    lines = switched_off_twins(skills_dir(tmp_path, enabled=False), identity("company", name))
    assert len(lines) == 1
    assert f"hermes/{name}" in lines[0] and "Capabilities" in lines[0]


def test_no_note_for_other_names_or_a_switched_on_skill(tmp_path: Path) -> None:
    name = json.loads(HERMES.read_text(encoding="utf-8"))["metadata"]["identity"]["name"]
    off = skills_dir(tmp_path / "off", enabled=False)
    assert switched_off_twins(off, identity("company", "something-else")) == []
    on = skills_dir(tmp_path / "on", enabled=True)
    assert switched_off_twins(on, identity("company", name)) == []
    assert switched_off_twins(tmp_path / "missing", identity("company", name)) == []
