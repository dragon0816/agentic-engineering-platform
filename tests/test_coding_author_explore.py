"""The change author explores, then edits (CODING_AT_SCALE S2)."""

from pathlib import Path
from typing import Any

import pytest
from test_coding_model_author import TRACE, Replies

from harness.contracts import (
    CodingHarnessRequest,
    CommandOutcome,
    HarnessPlan,
    PlannedChange,
    ValidationFailure,
    WorkspaceSnapshot,
)
from harness.model_author import AuthorUnavailable, ModelChangeAuthor
from harness.pytest_commands import NEW_COMMAND, SUITE_COMMAND, new_cases, suite_case
from harness.repo_reader import RepoReader

DRIVER = "src/wmt/driver.py"
TABLE = "src/wmt/op2_table.py"


def scale_request(root: Path, *paths: str) -> CodingHarnessRequest:
    return CodingHarnessRequest(
        workspace=WorkspaceSnapshot(root=str(root), starting_revision="0" * 64),
        requirement="Send OP2 with the new channel key.",
        artifact_path=paths[0],
        allowed_paths=paths,
        allowed_commands=(NEW_COMMAND, SUITE_COMMAND),
        cases=(*new_cases(("tests/test_driver.py",)), suite_case()),
        skill_versions=("coding@1.0.0",),
    )


def big_repository(tmp_path: Path) -> Path:
    root = tmp_path / "wmt"
    (root / "src" / "wmt").mkdir(parents=True)
    filler = "".join(f"    def cmd_{i}(self):\n        return {i}\n\n" for i in range(3000))
    text = "class Driver:\n" + filler + "    def op2(self):\n        return {'band': 1}\n"
    assert len(text) > 100_000  # far beyond what one prompt or answer could carry
    (root / DRIVER).write_bytes(text.replace("\n", "\r\n").encode())
    return root


def plan_for(request: CodingHarnessRequest) -> HarnessPlan:
    return HarnessPlan(
        summary="add channel",
        changes=tuple(PlannedChange(path=p, purpose="p") for p in request.allowed_paths),
        validation_commands=request.allowed_commands,
    )


def author(model: Replies, root: Path, **kwargs: Any) -> ModelChangeAuthor:
    return ModelChangeAuthor(
        model,
        "gateway",
        TRACE,
        {"tests/test_driver.py": "def test_op2(): ..."},
        reader=RepoReader(root),
        **kwargs,
    )


def edit(path: str, old: str, new: str) -> dict[str, Any]:
    return {"action": "edit", "edits": [{"path": path, "old": old, "new": new}]}


DONE = {"action": "done"}


def test_a_large_crlf_file_is_read_in_parts_and_changed_by_an_exact_edit(tmp_path: Path) -> None:
    root = big_repository(tmp_path)
    request = scale_request(root, DRIVER, TABLE)
    model = Replies(
        {"action": "search", "text": "def op2", "glob": "src/**/*.py"},
        {"action": "read", "path": DRIVER, "start": 9002, "end": 9004},
        edit(DRIVER, "return {'band': 2}", "x"),
        {
            "action": "edit",
            "edits": [
                {
                    "path": DRIVER,
                    "old": "        return {'band': 1}",
                    "new": "        return {'band': 1, **OP2_EXTRA}",
                },
                {"path": TABLE, "old": "", "new": "OP2_EXTRA = {'channel': 6}\n"},
            ],
        },
        DONE,
    )
    changes = author(model, root).initial_change(request, plan_for(request))
    assert [change.path for change in changes] == [DRIVER, TABLE]
    driver = changes[0].content
    assert driver.count("\r\n") == driver.count("\n")  # still CRLF throughout
    assert driver.endswith("        return {'band': 1, **OP2_EXTRA}\r\n")
    assert changes[1].content == "OP2_EXTRA = {'channel': 6}\n"
    opening = model.requests[0].messages[1].text
    assert f"- {DRIVER} (primary)" in opening and "class Driver: lines 1-9003" in opening
    assert "read the rest in ranges" in opening  # a 3000-method outline is cut too
    assert f"- {TABLE}: does not exist yet" in opening
    assert len(opening) < 10_000  # an outline, not the file
    seen = [sent.messages[-1].text for sent in model.requests[1:]]
    assert seen[0] == f"{DRIVER}:9002: def op2(self):"
    assert seen[1].startswith("9002:     def op2(self):")
    assert seen[2].startswith('Refused: the "old" text was not found')
    assert seen[3] == f"Applied. Changed: {DRIVER}, {TABLE}"
    assert all(sent.max_output_tokens == 8_000 for sent in model.requests)


def test_a_repair_sees_the_failure_and_the_diff_and_starts_from_the_tested_files(
    tmp_path: Path,
) -> None:
    root = big_repository(tmp_path)
    request = scale_request(root, DRIVER)
    model = Replies(
        edit(DRIVER, "{'band': 1}", "{'band': 9}"),
        DONE,
        edit(DRIVER, "{'band': 9}", "{'band': 1, 'ch': 6}"),
        DONE,
    )
    writer = author(model, root)
    plan = plan_for(request)
    (first,) = writer.initial_change(request, plan)
    (root / DRIVER).write_bytes(first.content.encode())  # what the harness does
    failure = CommandOutcome(
        command=NEW_COMMAND,
        status="failed",
        failures=(ValidationFailure(case="new-1", code="test_failed", message="KeyError: 'ch'"),),
    )
    (repaired,) = writer.repair(request, plan, failure, 1)
    assert repaired.content.endswith("return {'band': 1, 'ch': 6}\r\n")
    opening = model.requests[2].messages[1].text
    assert "KeyError: 'ch'" in opening
    assert "-        return {'band': 1}" in opening and "+        return {'band': 9}" in opening


def test_done_without_a_change_is_sent_back_and_turns_run_out(tmp_path: Path) -> None:
    root = big_repository(tmp_path)
    request = scale_request(root, DRIVER)
    model = Replies(DONE, {"action": "fly"}, DONE, DONE)
    with pytest.raises(AuthorUnavailable) as stopped:
        author(model, root, max_turns=4).initial_change(request, plan_for(request))
    assert stopped.value.code == "author_turns_exhausted"
    assert model.requests[1].messages[-1].text.startswith("You have not changed any file yet")
    assert model.requests[2].messages[-1].text.startswith("Unknown action 'fly'")
    # Turns that run out after an edit still hand the edit to the tests.
    edited = Replies(
        edit(DRIVER, "{'band': 1}", "{'band': 2}"), {"action": "outline", "path": DRIVER}
    )
    (change,) = author(edited, root, max_turns=2).initial_change(request, plan_for(request))
    assert "{'band': 2}" in change.content


def test_old_outputs_are_elided_when_the_conversation_grows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import harness.model_author as model_author

    monkeypatch.setattr(model_author, "MAX_TRANSCRIPT_CHARS", 30_000)
    root = big_repository(tmp_path)
    request = scale_request(root, DRIVER)
    reads = [
        {"action": "read", "path": DRIVER, "start": 1 + 400 * i, "end": 400 * (i + 1)}
        for i in range(5)
    ]
    model = Replies(*reads, edit(DRIVER, "{'band': 1}", "{'band': 2}"), DONE)
    author(model, root).initial_change(request, plan_for(request))
    last = model.requests[-1].messages
    assert sum(len(message.text) for message in last) < 30_000 + len(model_author.SYSTEM)
    assert last[3].text == model_author.ELIDED and last[1].text.startswith("Requirement:")


def test_a_change_that_looks_like_a_credential_stops_the_run(tmp_path: Path) -> None:
    root = big_repository(tmp_path)
    request = scale_request(root, DRIVER)
    model = Replies(edit(DRIVER, "return {'band': 1}", "password = 'hunter22'"), DONE)
    with pytest.raises(AuthorUnavailable) as stopped:
        author(model, root).initial_change(request, plan_for(request))
    assert stopped.value.code == "author_change_has_credential"


def test_a_file_that_is_not_utf8_cannot_be_changed(tmp_path: Path) -> None:
    root = big_repository(tmp_path)
    (root / DRIVER).write_bytes("x = 'caf\xe9'\n".encode("latin-1"))
    request = scale_request(root, DRIVER)
    with pytest.raises(AuthorUnavailable) as stopped:
        author(Replies(), root).initial_change(request, plan_for(request))
    assert stopped.value.code == "author_file_not_utf8"
