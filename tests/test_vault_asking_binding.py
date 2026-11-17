"""Binding a wiki repository to the Agent, and why a vault cannot be asked yet.

`docs/phases/BI_VAULT_ASKING.md` V2. Each state `askable` reports is checked against
a real chat turn in that state where it says the chat can or cannot answer. All data
is fictional.
"""

from __future__ import annotations

import io
import json
import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

import pytest
import test_bi_vault as bi
import test_knowledge_repos_api as repos
from test_agent_web import base, fetch
from test_host_wiring import host_json
from test_knowledge_sandbox import _base
from test_vault_asking_e2e import (
    LINE,
    WIKI_ARGUMENTS,
    _ask,
    _bi_host,
    _bi_join,
    _bi_model,
    _bi_published,
    _Model,
    _served,
    _wiki_host,
    _wiki_join,
    _wiki_published,
)

from aep_bi.cards.store import VAULT_REGISTRY, VAULTS_DIR
from common.change_proposal import KINDS, PROPOSE_GUIDANCE, TELEGRAM_KINDS
from host_runtime import knowledge_binding
from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.host import HostError, build_knowledge_catalog, build_runtime
from host_runtime.knowledge_binding import askable
from host_runtime.web import AgentWeb, AgentWebServer


def _web(config: Any, layout: Any, tmp_path: Path, model: Any = None) -> Any:
    runtime = build_runtime(config, layout=layout, model_transport=model)
    path = host_json(tmp_path, config)
    web = AgentWeb(runtime, config_path=path)
    web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
    return runtime, web


@contextmanager
def _opened(config: Any, layout: Any, tmp_path: Path, model: Any = None) -> Iterator[Any]:
    runtime, web = _web(config, layout, tmp_path, model)
    with runtime:
        yield web


def _codes(entry: dict[str, Any]) -> list[str]:
    return [reason["code"] for reason in entry["reasons"]]


def _propose(web: Any, **values: Any) -> dict[str, Any]:
    card = web.proposals.propose(
        "knowledge_binding", values, "test", session_id="s", actor="engineer", channel="local"
    )
    return dict(card.model_dump(mode="json"))


def _unbound_host(tmp_path: Path, **changes: Any) -> tuple[Any, Any, str, Path]:
    """A host with no binding that joined a published wiki repository."""
    publisher, drive, repo_id = _wiki_published(tmp_path)
    config, layout = _wiki_host(tmp_path, repo_id, **changes)
    config = config.model_copy(update={"knowledge": ()})
    _wiki_join(layout.workspace_root, drive / repo_id)
    return config, layout, repo_id, publisher


def _saved(web: Any) -> CompanyHostConfiguration:
    return CompanyHostConfiguration.model_validate_json(
        Path(web.config_path).read_text(encoding="utf-8-sig")
    )


def test_the_kind_is_web_only_and_the_model_is_told() -> None:
    assert "knowledge_binding" in KINDS and "knowledge_binding" not in TELEGRAM_KINDS
    assert "wiki knowledge repository" in PROPOSE_GUIDANCE


def test_a_repository_bound_through_the_card_is_answered_after_a_restart(tmp_path: Path) -> None:
    config, layout, repo_id, _ = _unbound_host(tmp_path)
    with _opened(config, layout, tmp_path) as web:
        (entry,) = askable(web)["repos"]
        assert entry["askable"] is False and _codes(entry)[0] == "not_bound"
        assert entry["reads"]["tag"] == "v1"
        before = Path(web.config_path).read_bytes()
        card = _propose(web, repo=repo_id)
        # Nothing changes before the person's press.
        assert Path(web.config_path).read_bytes() == before
        assert card["web_only"] is True and card["status"] == "pending"
        assert any("重新啟動" in effect for effect in card["effects"])
        assert any(row["after"].endswith("v1") for row in card["rows"])
        assert web.proposals.decide(card["card_id"], "apply", channel="telegram")["code"] == (
            "web_only"
        )
        done = web.proposals.decide(card["card_id"], "apply")
        assert done["ok"] is True, done
        assert "重新啟動" in done["message"]
        saved = _saved(web)
        (bound,) = saved.knowledge
        assert bound.repo == repo_id and bound.asset.name == repo_id
        assert (entry := askable(web)["repos"][0])["askable"] is False
        assert "restart_pending" in _codes(entry)
        backups = list(Path(web.config_path).parent.glob("*.bak-*-knowledge"))
        assert len(backups) == 1 and backups[0].read_bytes() == before

    # The host that starts on the saved file reads the repository.
    model = _Model(f"__{repo_id}", WIKI_ARGUMENTS)
    with _served(saved, layout, model) as server:
        answer = _ask(server)
        (entry,) = askable(server.web)["repos"]
    assert "FACT-PUBLISHED" in answer and f"資料來源：知識庫 {repo_id} 發佈版本 v1" in answer
    assert entry["askable"] is True and _codes(entry) == []


def test_the_manifest_goes_first_so_a_binding_never_stops_the_host(tmp_path: Path) -> None:
    config, layout, repo_id, _ = _unbound_host(tmp_path)
    with _opened(config, layout, tmp_path) as web:
        card = _propose(web, repo=repo_id)
        web.proposals.decide(card["card_id"], "apply")
        saved = _saved(web)
    assert build_knowledge_catalog(saved, layout).manifests()
    # What the guard is for: the same binding without its manifest stops the host.
    for path in layout.knowledge.glob("*.json"):
        if repo_id in path.name:
            path.unlink()
    with pytest.raises(HostError):
        build_knowledge_catalog(saved, layout)


def test_unbind_goes_through_a_card_and_leaves_a_host_that_starts(tmp_path: Path) -> None:
    config, layout, repo_id, _ = _unbound_host(tmp_path)
    with _opened(config, layout, tmp_path) as web:
        web.proposals.decide(_propose(web, repo=repo_id)["card_id"], "apply")
        card = _propose(web, repo=repo_id, action="unbind")
        assert web.proposals.decide(card["card_id"], "apply")["ok"] is True
        saved = _saved(web)
    assert saved.knowledge == ()
    with build_runtime(saved, layout=layout):
        pass


@pytest.mark.parametrize(
    ("values", "says"),
    [
        ({"repo": "no-such-repo"}, "沒有 wiki 知識庫"),
        ({"repo": "x", "action": "move"}, "action"),
        ({"repo": "no-such-repo", "action": "unbind"}, "沒有綁定"),
        ({"repo": "x", "grants": ["all"]}, "permission"),
    ],
)
def test_a_proposal_is_refused_with_the_reason(
    tmp_path: Path, values: dict[str, Any], says: str
) -> None:
    config, layout, _, _ = _unbound_host(tmp_path)
    with _opened(config, layout, tmp_path) as web:
        with pytest.raises(Exception, match=says):
            _propose(web, **values)
        assert _saved(web).knowledge == ()


def test_a_second_binding_of_the_same_repository_is_refused_and_a_stale_card_changes_nothing(
    tmp_path: Path,
) -> None:
    config, layout, repo_id, _ = _unbound_host(tmp_path)
    with _opened(config, layout, tmp_path) as web:
        first, second = _propose(web, repo=repo_id), _propose(web, repo=repo_id)
        assert web.proposals.decide(first["card_id"], "apply")["ok"] is True
        stale = web.proposals.decide(second["card_id"], "apply")
        assert stale["code"] == "proposal_stale"
        assert len(_saved(web).knowledge) == 1
        with pytest.raises(Exception, match="已經綁定"):
            _propose(web, repo=repo_id)


def test_a_manifest_this_flow_did_not_write_is_not_overwritten(tmp_path: Path) -> None:
    config, layout, repo_id, _ = _unbound_host(tmp_path)
    layout.knowledge.mkdir(parents=True, exist_ok=True)
    theirs = layout.knowledge / f"{config.namespace}__{repo_id}__1.0.0.json"
    theirs.write_text(json.dumps({"metadata": {"validation_refs": ["hand"]}}), encoding="utf-8")
    with _opened(config, layout, tmp_path) as web:
        with pytest.raises(Exception, match="不能覆蓋"):
            _propose(web, repo=repo_id)
    assert "hand" in theirs.read_text(encoding="utf-8")


def test_a_second_vault_stays_askable_says_what_changes_and_the_first_stays_first(
    tmp_path: Path,
) -> None:
    config, layout, repo_id, _ = _unbound_host(tmp_path)
    source = repos._wiki_folder(tmp_path / "other")
    drive = tmp_path / "other-drive"
    drive.mkdir()
    repos._ok(
        repos._call(layout.workspace_root, "POST", "/import",
                    {"source": str(source), "path": str(drive), "id": "other-wiki",
                     "title": "Other", "author": "bob"})
    )  # fmt: skip
    with _opened(config, layout, tmp_path) as web:
        web.proposals.decide(_propose(web, repo=repo_id)["card_id"], "apply")
        card = _propose(web, repo="other-wiki")
        assert any(
            "aep_knowledge_ask" in effect and repo_id in effect for effect in card["effects"]
        )
        web.proposals.decide(card["card_id"], "apply")
        saved = _saved(web)
    assert [item.repo for item in saved.knowledge] == [repo_id, "other-wiki"]
    with _served(saved, layout, _Model(f"__{repo_id}", WIKI_ARGUMENTS)) as server:
        report = askable(server.web)
        answer = _ask(server)
    assert [note["code"] for note in report["notes"]] == ["several_vaults"]
    assert all(entry["askable"] for entry in report["repos"])
    assert "FACT-PUBLISHED" in answer


def test_a_wiki_repository_says_when_the_grant_or_the_skill_is_missing(tmp_path: Path) -> None:
    _, drive, repo_id = _wiki_published(tmp_path)
    config, layout = _wiki_host(tmp_path / "no-grant", repo_id, granted=False)
    _wiki_join(layout.workspace_root, drive / repo_id)
    with _opened(config, layout, tmp_path / "no-grant") as web:
        assert askable(web)["repos"][0]["askable"] is True
        assert "not_granted" not in _codes(askable(web)["repos"][0])
    config, layout = _wiki_host(tmp_path / "no-skill", repo_id)
    (layout.skills / "knowledge-evidence.json").unlink()
    _wiki_join(layout.workspace_root, drive / repo_id, "carol")
    with _opened(config, layout, tmp_path / "no-skill") as web:
        (entry,) = askable(web)["repos"]
    assert "skill_off" in _codes(entry) and entry["askable"] is False


def test_a_repository_with_only_its_schema_says_nothing_is_pushed(tmp_path: Path) -> None:
    drive = tmp_path / "drive"
    drive.mkdir()
    config, layout = _wiki_host(tmp_path, "empty-wiki")
    repos._ok(
        repos._call(layout.workspace_root, "POST", "",
                    {"path": str(drive), "id": "empty-wiki", "title": "Empty", "author": "bob"})
    )  # fmt: skip
    with _opened(config, layout, tmp_path) as web:
        (entry,) = askable(web)["repos"]
    assert "nothing_pushed" in _codes(entry)


def test_a_never_published_repository_is_askable_with_a_note(tmp_path: Path) -> None:
    source = repos._wiki_folder(tmp_path)
    drive = tmp_path / "drive"
    drive.mkdir()
    config, layout = _wiki_host(tmp_path, "tester-wiki")
    repos._ok(
        repos._call(layout.workspace_root, "POST", "/import",
                    {"source": str(source), "path": str(drive), "id": "tester-wiki",
                     "title": "T", "author": "bob"})
    )  # fmt: skip
    repos._edit(layout.workspace_root, "tester-wiki", "Nothing yet.", LINE.format("A"), "加")
    repos._push(layout.workspace_root, "tester-wiki")
    with _opened(config, layout, tmp_path) as web:
        (entry,) = askable(web)["repos"]
    assert entry["askable"] is True and _codes(entry) == ["never_published"]
    assert entry["reads"]["tag"] is None


# -- BI vaults ------------------------------------------------------------------------------


def test_a_bi_vault_says_why_it_cannot_be_asked(tmp_path: Path) -> None:
    folder, vault_id, dataset, _ = _bi_published(tmp_path)
    config, layout = _bi_host(tmp_path / "ok")
    _bi_join(layout.workspace_root, folder)
    with _served(config, layout, _bi_model(dataset)) as server:
        (entry,) = askable(server.web)["vaults"]
        answer = _ask(server)
    assert entry["askable"] is True and entry["reads"]["tag"] == "v1"
    assert "FACT-PUBLISHED" in answer

    config, layout = _bi_host(tmp_path / "no-grant", granted=False)
    _bi_join(layout.workspace_root, folder, "dave")
    with _opened(config, layout, tmp_path / "no-grant") as web:
        assert askable(web)["vaults"][0]["askable"] is True
        assert "not_granted" not in _codes(askable(web)["vaults"][0])

    config, layout = _bi_host(tmp_path / "skill-off", skill_on=False)
    _bi_join(layout.workspace_root, folder, "erin")
    with _opened(config, layout, tmp_path / "skill-off") as web:
        (entry,) = askable(web)["vaults"]
    assert "skill_off" in _codes(entry) or "capability_missing" in _codes(entry)
    assert entry["askable"] is False
    assert vault_id == entry["id"]


def test_a_vault_with_no_pushed_cards_says_so_and_never_published_is_a_note(tmp_path: Path) -> None:
    drive, vault_id, dataset, publisher, _ = bi._two_pcs(tmp_path)
    config, layout = _bi_host(tmp_path)
    _bi_join(layout.workspace_root, drive.parent("a") / vault_id)
    with _opened(config, layout, tmp_path) as web:
        (entry,) = askable(web)["vaults"]
        assert "nothing_pushed" in _codes(entry) and entry["askable"] is False
        bi._import(publisher, dataset, bi._row("TSN", standard_body="FACT-X"))
        assert "nothing_pushed" in _codes(askable(web)["vaults"][0])  # a local commit only
        bi._push(publisher, vault_id)
        (entry,) = askable(web)["vaults"]
    assert entry["askable"] is True and _codes(entry) == ["never_published"]


def test_a_folder_in_the_old_format_is_named_and_a_missing_folder_is_unreachable(
    tmp_path: Path,
) -> None:
    config, layout = _bi_host(tmp_path)
    folder = tmp_path / "old-vault"
    (folder / "changes").mkdir(parents=True)
    (folder / "vault.json").write_text('{"id": "old"}', encoding="utf-8")
    registry = layout.workspace_root / "bi" / VAULTS_DIR
    registry.mkdir(parents=True, exist_ok=True)
    (registry / VAULT_REGISTRY).write_text(
        json.dumps(
            {
                "vaults": [
                    {"id": "old", "path": str(folder), "author": "x", "joined": "t"},
                    {"id": "gone", "path": str(tmp_path / "gone"), "author": "x", "joined": "t"},
                ]
            }
        ),
        encoding="utf-8",
    )
    with _opened(config, layout, tmp_path) as web:
        codes = {entry["id"]: _codes(entry) for entry in askable(web)["vaults"]}
    assert "unreadable_format" in codes["old"] and "unreachable" in codes["gone"]


# -- the page -------------------------------------------------------------------------------


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_knowledge_page_explains_and_binds_through_the_card(tmp_path: Path) -> None:
    from integrations.browser import Browser, BrowserError

    pipeline = {"vaults": [{"name": "k-test", "root": str(_base(tmp_path / "base"))}]}
    config, layout, repo_id, _ = _unbound_host(tmp_path, knowledge_pipeline=pipeline)
    with _opened(config, layout, tmp_path) as web:
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()

        def wait(expression: str) -> Any:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    value = browser._evaluate(expression)
                except BrowserError:
                    value = None
                if value:
                    return value
                time.sleep(0.1)
            raise AssertionError(expression)

        def shows(words: str) -> str:
            return (
                f"document.getElementById('kp-askable').textContent.includes({json.dumps(words)})"
            )

        def press(label: str) -> None:
            browser._evaluate(
                "[...document.querySelectorAll('#kp-askable button')]"
                f".find((b) => b.textContent.trim() === {json.dumps(label)}).click()"
            )

        try:
            browser.navigate(server.address)
            wait("!!document.getElementById('nav-knowledge')")
            browser._evaluate("document.getElementById('nav-knowledge').click()")
            wait(shows("還不能在對話裡問"))
            assert browser._evaluate("!!document.querySelector('#kp-askable li')")
            wait(shows("Agent 還沒有綁定這個知識庫"))
            press("讓 Agent 可以問這個知識庫")
            wait("!!document.querySelector('#kp-askable .action-card')")
            assert _saved(web).knowledge == ()  # nothing before the press
            press("Apply")
            wait(shows("已綁定，但執行中的 Agent 還沒有載入"))
            (bound,) = _saved(web).knowledge
            assert bound.repo == repo_id
            wait(shows("解除 Agent 的綁定"))
        finally:
            browser.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


# -- the routes -----------------------------------------------------------------------------


def test_the_routes_need_the_token_and_open_the_same_card(tmp_path: Path) -> None:
    config, layout, repo_id, _ = _unbound_host(tmp_path)
    with _opened(config, layout, tmp_path) as web:
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = base(server) + "/api/knowledge/askable"
            assert fetch(url).status == 401
            listed = fetch(url, token=server.token).json()
            assert listed["repos"][0]["id"] == repo_id
            propose = url + "/propose"
            made = fetch(propose, token=server.token, body={"repo": repo_id}).json()
            assert made["ok"] is True and made["card"]["kind"] == "change_proposal"
            assert made["card"]["card_id"] in {card["card_id"] for card in web.cards(None)["cards"]}
            no = fetch(propose, token=server.token, body={"repo": "no-such"})
            assert no.status == 409 and no.json()["code"] == "proposal_refused"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


class _Answered:
    """The little of a request handler `handle` uses."""

    def __init__(self) -> None:
        self.server = SimpleNamespace(web=object())
        self.answers: list[tuple[int, dict[str, Any]]] = []
        self.headers = {"Content-Length": "2"}
        self.rfile = io.BytesIO(b"{}")

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        self.answers.append((status, payload))


def _flaky(monkeypatch: pytest.MonkeyPatch, refusals: int) -> list[str]:
    asked: list[str] = []

    def route(_web: Any, method: str, _path: str, _given: Any) -> tuple[int, dict[str, Any]]:
        asked.append(method)
        if len(asked) <= refusals:
            raise PermissionError(13, "Access is denied", "fictional-file.json")
        return 200, {"ok": True}

    monkeypatch.setattr(knowledge_binding, "route", route)
    monkeypatch.setattr("host_runtime.knowledge_binding.time.sleep", lambda _s: None)
    return asked


def test_a_read_waits_out_a_file_held_for_a_moment(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _flaky(monkeypatch, 2)
    handler = _Answered()
    assert knowledge_binding.handle(handler, "GET", urlparse(knowledge_binding.PREFIX))
    assert handler.answers == [(200, {"ok": True})] and len(asked) == 3


def test_a_lasting_refusal_is_answered_and_its_trace_is_kept(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    asked = _flaky(monkeypatch, 99)
    handler = _Answered()
    with caplog.at_level(logging.ERROR, logger=knowledge_binding.__name__):
        knowledge_binding.handle(handler, "GET", urlparse(knowledge_binding.PREFIX))
    ((status, payload),) = handler.answers
    assert status == 500 and payload["code"] == "askable_error" and len(asked) == 3
    assert "fictional-file" not in payload["message"]  # the page says the kind only
    (record,) = caplog.records
    assert record.exc_info is not None and "fictional-file" in caplog.text


def test_a_write_is_never_asked_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _flaky(monkeypatch, 1)
    handler = _Answered()
    path = urlparse(knowledge_binding.PREFIX + "/propose")
    knowledge_binding.handle(handler, "POST", path)
    assert asked == ["POST"] and handler.answers[0][0] == 500
