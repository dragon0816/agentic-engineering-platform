"""`write_atomically` retries a replace Windows refuses for a moment."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from host_runtime import workspace


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
    target = tmp_path / "a" / "session.json"
    workspace.write_atomically(target, b"{}")
    assert target.read_bytes() == b"{}"
    assert not target.with_name("session.json.part").exists()


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
        workspace.write_atomically(tmp_path / "x.json", b"{}")
    assert len(calls) == workspace.REPLACE_ATTEMPTS
