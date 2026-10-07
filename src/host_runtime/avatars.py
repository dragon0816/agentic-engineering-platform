"""Agent Web avatars: the pixel-art characters a person picks (owner 2026-10-07).

The frames ship with the package under `avatars/`, cut from the owner's sheet
by `scripts/slice_avatars.py`; `manifest.json` lists each character's frames in
order. Frame 1 is the idle picture and the rest play while the Agent works.
Frames reach the page as data URIs through the authorized API, so no image
route is served without the token.

Each person's choice is their own: it is kept per actor under the workspace's
`user-preferences/`, and only a character the manifest lists can be chosen.
"""

from __future__ import annotations

import base64
import hashlib
import json
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import Field

from common.base import Contract
from host_runtime.workspace import write_atomically

FRAMES = Path(__file__).resolve().parent / "avatars"


@cache
def catalog() -> tuple[dict[str, Any], ...]:
    """Every character with its frames as PNG data URIs, in manifest order."""
    manifest = json.loads((FRAMES / "manifest.json").read_text(encoding="utf-8"))
    characters = []
    for character in manifest["characters"]:
        frames = [
            "data:image/png;base64,"
            + base64.b64encode((FRAMES / frame["file"]).read_bytes()).decode("ascii")
            for frame in character["frames"]
        ]
        characters.append({"id": character["id"], "name": character["name"],
                           "height": character["row_height"], "frames": frames})
    return tuple(characters)


def known(avatar: str) -> bool:
    return any(character["id"] == avatar for character in catalog())


class UserPreferences(Contract):
    """One person's Agent Web choices. `avatar` is a catalog id, or None."""

    avatar: str | None = Field(default=None, max_length=40)


class UserPreferencesStore:
    def __init__(self, workspace_root: Path) -> None:
        self.root = workspace_root / "user-preferences"

    def _path(self, actor: str) -> Path:
        # The actor names the file only through a digest, so no actor id can
        # reach outside the folder.
        return self.root / (hashlib.sha256(actor.encode("utf-8")).hexdigest()[:32] + ".json")

    def load(self, actor: str) -> UserPreferences:
        path = self._path(actor)
        if not path.is_file():
            return UserPreferences()
        try:
            loaded = UserPreferences.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            return UserPreferences()
        # A character removed from the catalog falls back to none.
        if loaded.avatar is not None and not known(loaded.avatar):
            return UserPreferences()
        return loaded

    def save(self, actor: str, preferences: UserPreferences) -> UserPreferences:
        checked = UserPreferences.model_validate(preferences)
        if checked.avatar is not None and not known(checked.avatar):
            raise ValueError("unknown avatar")
        self.root.mkdir(parents=True, exist_ok=True)
        write_atomically(self._path(actor), checked.model_dump_json().encode("utf-8") + b"\n")
        return checked
