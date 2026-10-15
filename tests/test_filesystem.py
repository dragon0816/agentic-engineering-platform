"""Publishing a staged directory waits out brief Windows locks, and only those."""

import sys
from pathlib import Path

import pytest

from common.filesystem import publish_directory


def _refusal(winerror: int) -> PermissionError:
    error = PermissionError(13, "Access is denied")
    error.winerror = winerror
    return error


class _FakeReplace:
    """Refuse the first ``refusals`` renames, then really rename."""

    def __init__(self, refusals: int, error: OSError) -> None:
        self.refusals = refusals
        self.error = error
        self.calls = 0

    def __call__(self, source: Path, target: Path) -> None:
        self.calls += 1
        if self.calls <= self.refusals:
            raise self.error
        source.rename(target)


@pytest.fixture
def staged(tmp_path: Path) -> tuple[Path, Path]:
    stage = tmp_path / ".part-1234abcd"
    stage.mkdir()
    (stage / "file.txt").write_bytes(b"content")
    return stage, tmp_path / "1.0.0"


def test_staged_directory_appears_whole_under_the_target(staged: tuple[Path, Path]) -> None:
    stage, target = staged

    publish_directory(stage, target)

    assert not stage.exists()
    assert (target / "file.txt").read_bytes() == b"content"


@pytest.mark.parametrize("winerror", (5, 32))
def test_a_brief_windows_lock_is_waited_out(
    staged: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, winerror: int
) -> None:
    stage, target = staged
    replace = _FakeReplace(3, _refusal(winerror))
    sleeps: list[float] = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr("common.filesystem.os.replace", replace)
    monkeypatch.setattr("common.filesystem.time.sleep", sleeps.append)

    publish_directory(stage, target)

    assert replace.calls == 4
    assert sleeps == [0.02, 0.04, 0.08]
    assert (target / "file.txt").read_bytes() == b"content"


def test_a_lock_that_outlasts_the_budget_is_raised(
    staged: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    stage, target = staged
    refusal = _refusal(5)
    replace = _FakeReplace(1_000, refusal)
    clock = [0.0]
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr("common.filesystem.os.replace", replace)
    monkeypatch.setattr("common.filesystem.time.monotonic", lambda: clock[0])
    monkeypatch.setattr(
        "common.filesystem.time.sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds)
    )

    with pytest.raises(PermissionError) as raised:
        publish_directory(stage, target, budget_seconds=2.0)

    assert raised.value is refusal
    assert clock[0] <= 2.0
    assert 1 < replace.calls < 1_000
    assert stage.exists() and not target.exists()


@pytest.mark.parametrize(
    "error",
    (FileExistsError(17, "exists"), _refusal(183), OSError(28, "No space left on device")),
)
def test_other_failures_are_raised_at_once(
    staged: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, error: OSError
) -> None:
    stage, target = staged
    replace = _FakeReplace(1, error)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr("common.filesystem.os.replace", replace)
    monkeypatch.setattr("common.filesystem.time.sleep", pytest.fail)

    with pytest.raises(OSError) as raised:
        publish_directory(stage, target)

    assert raised.value is error
    assert replace.calls == 1


def test_access_denied_is_not_retried_outside_windows(
    staged: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    stage, target = staged
    replace = _FakeReplace(1, _refusal(5))
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("common.filesystem.os.replace", replace)
    monkeypatch.setattr("common.filesystem.time.sleep", pytest.fail)

    with pytest.raises(PermissionError):
        publish_directory(stage, target)

    assert replace.calls == 1
