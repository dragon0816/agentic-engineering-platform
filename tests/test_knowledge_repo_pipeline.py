"""The Knowledge tab's steps on a wiki repository's working folder (R4b).

A repository opens as `repo.<id>` through the same pipeline routes as a
sandbox; what a step writes is staged in the working copy, committed with a
purpose and pushed. Originals are pulled from this PC's intake folder and the
questions read from this PC's question folder. The working folder never undoes
someone else's change it had not seen. All data is fictional.
"""

from __future__ import annotations

import base64
import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from test_agent_web import base, fetch
from test_host_wiring import grant_record, membership_record, workspace
from test_knowledge_pipeline_web import _step
from test_knowledge_repos_api import (
    PAGE,
    _call,
    _deliver,
    _ok,
    _push,
    _refused,
    _two_pcs,
    _wiki_folder,
)
from test_knowledge_sandbox import _base

from aep_wiki.host.wiki_web import PIPELINE_STEPS
from aep_wiki.knowledge import wiki_work
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from knowledge import wiki_repos
from knowledge.repo import wiki

QUESTION = "---\nname: tester-options\n---\n\n# Tester X 有哪些選項？\n\n必須提到:\n  - K1\n"


@pytest.fixture
def served(tmp_path: Path) -> Iterator[AgentWebServer]:
    """Agent Web with every Knowledge tab step granted and a test vault."""
    vault = _base(tmp_path)
    grants = [
        *grant_record(),
        *(
            {
                "actor": "engineer",
                "asset": spec.identity.model_dump(mode="json"),
                "permissions": ["knowledge-pipeline.use"],
                "policy_refs": ["knowledge-sandbox-policy"],
                "approval_ref": "knowledge-pipeline-approval",
            }
            for spec in PIPELINE_STEPS.values()
        ),
    ]
    config, _ = workspace(
        tmp_path,
        membership=membership_record(),
        grants=grants,
        config_changes={"knowledge_pipeline": {"vaults": [{"name": "k-test", "root": str(vault)}]}},
    )
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _repo(server: AgentWebServer, tmp_path: Path) -> tuple[Path, str, str]:
    """A repository imported in the served Agent's workspace."""
    ws = server.web.runtime.layout.workspace_root
    drive = tmp_path / "drive"
    drive.mkdir()
    source = _wiki_folder(tmp_path / "src")
    made = _ok(_call(ws, "POST", "/import", {"source": str(source), "path": str(drive)}))
    repo_id = made["repo"]["id"]
    return ws, repo_id, "repo." + repo_id


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def test_steps_on_a_repository_become_changes_to_commit_and_push(
    served: AgentWebServer, tmp_path: Path
) -> None:
    server = served
    ws, repo_id, box = _repo(server, tmp_path)
    info = json.loads(fetch(base(server) + "/api/knowledge/pipeline", token=server.token).body)
    assert [r["id"] for r in info["repos"]] == [repo_id] and info["repo_prefix"] == "repo."
    added = _step(server, "drop-add", {"sandbox_id": box, "name": "Products/y.txt",
                                       "data_base64": _b64(b"Tester Y has K2.\n")})  # fmt: skip
    assert added["ok"] and [o.rsplit("-", 1)[-1] for o in added["captured"]["originals"]] == [
        "y.txt"
    ]
    converted = _step(server, "convert", {"sandbox_id": box, "mode": "apply"})
    assert converted["ok"] and converted["captured"]["raw"], converted
    rule = "---\nname: ingest-products\n---\nRead product sheets and their options.\n"
    path = "skills/ingest-products/SKILL.md"
    saved = _step(server, "rule-write", {"sandbox_id": box, "path": path, "text": rule})
    assert saved["ok"], saved
    assert saved["captured"]["skills"] == ["ingest-products"]
    listed = _step(server, "sandbox-contents", {"sandbox_id": box})
    assert "captured" not in listed  # reading steps stage nothing
    labels = {c["label"] for c in _ok(_call(ws, "GET", f"/{repo_id}/pending"))["uncommitted"]}
    assert "skill「ingest-products」" in labels
    assert any(label.startswith("raw/Products/") for label in labels)
    _ok(_call(ws, "POST", f"/{repo_id}/commit", {"purpose": "加入 Tester Y"}))
    _push(ws, repo_id)
    view = wiki_repos.reading_folder(ws, repo_id)
    assert any((view / "raw" / "Products").glob("y*"))
    assert "their options" in (view / "skills" / "ingest-products" / "SKILL.md").read_text(
        encoding="utf-8"
    )


def test_a_repository_has_no_merge_push_or_discard_of_the_sandbox_kind(
    served: AgentWebServer, tmp_path: Path
) -> None:
    server = served
    _, _, box = _repo(server, tmp_path)
    assert _step(server, "merge", {"sandbox_id": box})["code"] == "repository_uses_versions"
    assert _step(server, "sandbox-discard", {"sandbox_id": box})["code"] == (
        "repository_not_discarded"
    )
    body = {"sandbox_id": box, "sets": [], "resolutions": {}}
    reply = fetch(base(server) + "/api/knowledge/push/start", token=server.token, body=body)
    assert json.loads(reply.body) == {"ok": False, "code": "repository_uses_versions"}
    unknown = _step(server, "sandbox-contents", {"sandbox_id": "repo.nobody-000000"})
    assert unknown["ok"] is False and unknown["code"].endswith("_unknown")


def test_originals_come_from_the_intake_folder_and_questions_from_the_question_folder(
    served: AgentWebServer, tmp_path: Path
) -> None:
    server = served
    ws, repo_id, box = _repo(server, tmp_path)
    assert _step(server, "drop-folders", {"base": box})["code"] == "intake_not_set"
    assert _step(server, "question-sets", {"sandbox_id": box})["data"]["sets"] == {}
    benchmark = fetch(base(server) + "/api/knowledge/benchmark/start", token=server.token,
                      body={"sandbox_id": box, "sets": ["products"]})  # fmt: skip
    assert json.loads(benchmark.body) == {"ok": False, "code": "questions_not_set"}
    intake, questions = tmp_path / "intake", tmp_path / "questions"
    (intake / "Products").mkdir(parents=True)
    (intake / "Products" / "z.txt").write_bytes(b"Tester Z.\n")
    (questions / "products").mkdir(parents=True)
    (questions / "products" / "q1.md").write_bytes(QUESTION.encode("utf-8"))
    _refused(_call(ws, "POST", f"/{repo_id}/settings", {"intake": str(tmp_path / "none")}),
             400, "path_missing")  # fmt: skip
    chosen = _ok(_call(ws, "POST", f"/{repo_id}/settings",
                       {"intake": str(intake), "questions": str(questions)}))  # fmt: skip
    assert chosen["settings"]["intake"] == str(intake)
    assert _ok(_call(ws, "GET", f"/{repo_id}/settings"))["settings"] == chosen["settings"]
    folders = _step(server, "drop-folders", {"base": box})["data"]["folders"]
    assert [f["path"] for f in folders] == ["Products"]
    pulled = _step(server, "pull", {"sandbox_id": box, "folders": ["Products"]})
    assert pulled["data"]["copied"] == ["Products/z.txt"] and pulled["captured"]["originals"]
    assert wiki_work.settings(wiki_repos.repository(ws, repo_id))["pulled"] == ["Products"]
    sets = _step(server, "question-sets", {"sandbox_id": box})["data"]
    assert sets["sets"] == {"products": 1}
    edited = QUESTION.replace("K1", "K1 base")
    path = "checks/questions/products/q1.md"
    saved = _step(server, "rule-write", {"sandbox_id": box, "path": path, "text": edited})
    assert saved["ok"], saved
    assert (questions / "products" / "q1.md").read_text(encoding="utf-8") == edited
    folder = wiki_work.work_folder(wiki_repos.repository(ws, repo_id))
    assert not (folder / "checks").exists()  # questions are not repository content (yet)


def _edit_section(folder: Path, old: str, new: str) -> None:
    text = (folder / PAGE).read_text(encoding="utf-8")
    assert old in text
    (folder / PAGE).write_bytes(text.replace(old, new).encode("utf-8"))


def test_the_working_folder_never_undoes_a_change_it_had_not_seen(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    repo_a = wiki_repos.repository(a, repo_id)
    folder = wiki_work.open_work(repo_a)
    # Bob changes the Notes section of the page and pushes.
    repo_b = wiki_repos.repository(b, repo_id)
    text = wiki.pages(repo_b.working_units())[PAGE]
    wiki.stage_page(repo_b, PAGE, text.replace("Nothing yet.", "Shipping in Q3."))
    _ok(_call(b, "POST", f"/{repo_id}/commit", {"purpose": "出貨時程"}))
    _push(b, repo_id)
    _deliver(drive_b / repo_id, drive_a / repo_id)
    # Alice's PC syncs (the Agent reading does) while her folder still shows
    # the old Notes; she edits the Intro there.
    repo_a.sync()
    _edit_section(folder, "Intro.", "Intro, with options.")
    rebuilt = wiki_work.open_work(repo_a)  # captures her edit first, then rebuilds
    page = (rebuilt / PAGE).read_text(encoding="utf-8")
    assert "Intro, with options." in page and "Shipping in Q3." in page
    labels = {c["label"] for c in _ok(_call(a, "GET", f"/{repo_id}/pending"))["uncommitted"]}
    assert labels and f"{PAGE} 的「Notes」" not in labels
    _ok(_call(a, "POST", f"/{repo_id}/commit", {"purpose": "補開頭"}))
    _push(a, repo_id)
    assert "Shipping in Q3." in wiki.pages(repo_a.units())[PAGE]


def test_a_rebuild_keeps_drop_and_the_pipeline_records(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    repo = wiki_repos.repository(a, repo_id)
    folder = wiki_work.open_work(repo)
    (folder / "drop" / "Products").mkdir(parents=True)
    (folder / "drop" / "Products" / "w.pdf").write_bytes(b"%PDF w")
    (folder / ".plans").mkdir()
    (folder / ".plans" / "plan-1.json").write_text("{}", encoding="utf-8")
    _edit_section(folder, "Nothing yet.", "Draft.")
    _ok(_call(a, "POST", f"/{repo_id}/discard", {}))  # rebuilds without the edit
    rebuilt = wiki_work.open_work(repo)
    assert "Draft." not in (rebuilt / PAGE).read_text(encoding="utf-8")
    assert (rebuilt / "drop" / "Products" / "w.pdf").read_bytes() == b"%PDF w"
    assert (rebuilt / ".plans" / "plan-1.json").is_file()
