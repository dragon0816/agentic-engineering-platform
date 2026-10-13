"""Progress of sandbox creation and pull for the page's bar (owner, 2026-10-13)."""

from pathlib import Path

from test_knowledge_scope import _project

from host_runtime.web_page import PAGE
from knowledge import progress


def test_creating_a_sandbox_reports_every_file_copied(tmp_path: Path) -> None:
    pipeline, _ = _project(tmp_path)
    key = "create-key-0001"
    pipeline.create_sandbox("rs-k", "p", "leo", scope="Knowledge", progress_key=key)
    final = progress.read(key)
    assert final is not None and final["phase"] == "checking"
    assert final["done"] == final["total"] > 0


def test_a_pull_reports_its_originals(tmp_path: Path) -> None:
    pipeline, _ = _project(tmp_path)
    sandbox = pipeline.create_sandbox("rs-k", "p", "leo", scope="Productions").sandbox_id
    seen: list[tuple[int, int]] = []
    original = progress.report

    def spy(key: str, phase: str, done: int, total: int, current: str = "") -> None:
        seen.append((done, total))
        original(key, phase, done, total, current)

    progress.report = spy  # type: ignore[assignment]
    try:
        pipeline.pull(sandbox, ("Productions",), progress_key="pull-key-0001")
    finally:
        progress.report = original  # type: ignore[assignment]
    assert seen[-1] == (2, 2) and (0, 2) in seen  # VNA/x.txt and CMX/x.txt


def test_keys_are_checked_and_unknown_keys_read_nothing() -> None:
    assert progress.reporter(None) is None and progress.reporter("../x") is None
    assert progress.read("no-such-key-123") is None and progress.read("bad key") is None


def test_the_page_shows_a_progress_bar_for_long_steps() -> None:
    for hook in ('id="kp-progress-bar"', "kpWithProgress", "/api/knowledge/progress",
                 "progress_key: key", "Opening the sandbox: rules (2/5)"):
        assert hook in PAGE


def test_the_page_key_format_passes_the_request_contracts() -> None:
    import pytest
    from pydantic import ValidationError

    from capabilities.knowledge_pipeline.contracts import PullRequest, SandboxCreateRequest

    key = "p" + "0a" * 12  # what kpKey() makes: a letter, then 24 hex digits
    assert progress.reporter(key) is not None
    SandboxCreateRequest(base="rs-k", label="x", progress_key=key)
    PullRequest(sandbox_id="sb-x", folders=("Market",), progress_key=key)
    with pytest.raises(ValidationError):  # the first version's keys began with a digit
        PullRequest(sandbox_id="sb-x", folders=("Market",), progress_key="0a" * 12)
    assert '"p" + Array.from(crypto.getRandomValues' in PAGE
