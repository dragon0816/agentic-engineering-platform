"""The gateway's settings writer retries a replace Windows refuses for a moment."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from llm_gateway import config


def test_a_replace_refused_for_a_moment_is_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = os.replace
    refusals = [PermissionError(13, "Access is denied")] * 2
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    def flaky(source: object, target: object) -> None:
        if refusals:
            raise refusals.pop()
        real(source, target)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", flaky)
    target = tmp_path / "gateway" / "settings.json"
    config.write_atomically(target, "{}\n")
    assert target.read_text(encoding="utf-8") == "{}\n"
    assert not target.with_name("settings.json.tmp").exists()


def test_a_replace_refused_every_time_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    def refuse(source: object, target: object) -> None:
        calls.append(target)
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(PermissionError):
        config.write_atomically(tmp_path / "settings.json", "{}")
    assert len(calls) == config.REPLACE_ATTEMPTS
