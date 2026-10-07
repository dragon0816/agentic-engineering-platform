"""Agent Web avatars: per-person pixel-art characters (owner 2026-10-07)."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from test_agent_web import base, fetch, served  # noqa: F401 - the server fixture

from host_runtime.avatars import UserPreferences, UserPreferencesStore, catalog
from host_runtime.web import AgentWebServer
from host_runtime.web_page import PAGE


def test_the_catalog_has_ten_characters_each_with_an_idle_frame_and_motion() -> None:
    characters = catalog()
    assert [c["id"] for c in characters] == [
        "luffy", "zoro", "nami", "chopper", "robin", "sanji", "usopp", "franky", "brook", "jinbe"]
    for character in characters:
        assert len(character["frames"]) >= 7, character["id"]
        for frame in character["frames"]:
            assert frame.startswith("data:image/png;base64,")
            assert base64.b64decode(frame.split(",", 1)[1])[:8] == b"\x89PNG\r\n\x1a\n"


def test_each_person_keeps_their_own_avatar(tmp_path: Path) -> None:
    store = UserPreferencesStore(tmp_path)
    assert store.load("alice").avatar is None
    store.save("alice", UserPreferences(avatar="zoro"))
    assert store.load("alice").avatar == "zoro"
    assert store.load("bob").avatar is None
    store.save("alice", UserPreferences(avatar=None))
    assert store.load("alice").avatar is None


def test_only_a_listed_character_can_be_chosen_and_names_stay_inside(tmp_path: Path) -> None:
    store = UserPreferencesStore(tmp_path)
    with pytest.raises(ValueError):
        store.save("alice", UserPreferences(avatar="not-a-character"))
    store.save("../../outside", UserPreferences(avatar="nami"))
    written = list((tmp_path / "user-preferences").glob("*.json"))
    assert len(written) == 1 and written[0].parent == tmp_path / "user-preferences"
    written[0].write_text("{not json", encoding="utf-8")
    assert store.load("../../outside").avatar is None


def test_the_web_api_lists_avatars_and_saves_the_choice(
    served: AgentWebServer,  # noqa: F811
) -> None:
    url, token = base(served), served.token
    listed = fetch(url + "/api/avatars", token=token).json()
    assert len(listed["characters"]) == 10
    assert fetch(url + "/api/preferences", token=token).json()["preferences"]["avatar"] is None
    saved = fetch(url + "/api/preferences", token=token, body={"avatar": "chopper"}).json()
    assert saved["preferences"]["avatar"] == "chopper"
    assert fetch(url + "/api/preferences", token=token).json()["preferences"]["avatar"] == "chopper"
    refused = fetch(url + "/api/preferences", token=token, body={"avatar": "nobody"})
    assert refused.status == 400
    assert fetch(url + "/api/avatars").status == 401   # the token is required


def test_the_page_shows_the_avatar_and_animates_it_while_a_turn_runs() -> None:
    assert 'id="avatar-stage"' in PAGE and 'id="avatar-choices"' in PAGE
    assert "loadAvatars()" in PAGE
    assert "avatarWorking(1);" in PAGE and "finally { avatarWorking(-1); }" in PAGE
    assert "prefers-reduced-motion" in PAGE
