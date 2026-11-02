"""A vault asked from the general chat, the whole chain (`docs/phases/BI_VAULT_ASKING.md` V1).

Real Host, real Agent Web route (`POST /api/conversations/turn`), a scripted model
at the model transport: it asks the vault's tool, then answers only with the fact
tokens (`FACT-...`) it was actually given, so an answer shows what reached the
model. A wiki repository and a BI vault are each made on one PC, pushed and
published, then joined and asked on another. All data is fictional.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import test_bi_vault as bi
import test_knowledge_repos_api as repos
from test_agent_web import base, fetch
from test_host_models import GatewayReply, binding, endpoint
from test_host_wiring import grant_record, membership_record, workspace
from test_knowledge_repo_agent import ASSET as WIKI_ASSET
from test_knowledge_repo_agent import _template

from capabilities.bi_cards.capability import QUERY_SPEC
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from host_runtime import skill_packs
from host_runtime.assets import shipped
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer

FACT = re.compile(r"FACT-[A-Z0-9]+")
PASSAGE = re.compile(r"^\[(\d+)\] [A-Z]+: (.*?)(?=^\[\d+\] |^Form: |\Z)", re.MULTILINE | re.DOTALL)
SKILL = Path(__file__).parent / "fixtures/harness_skills/knowledge-evidence.json"
QUESTION = "Tester X Notes shipping 寫了什麼？"
#: The fact as a page holds it, so retrieval finds it for the question.
LINE = "Tester X Notes shipping: FACT-{}"
#: What the shipped Knowledge Skill's procedure says about citing (wiki first);
#: its intent matches nothing, so the turn takes the conversation's tool route.
PROCEDURE = {"kind": "knowledge_query_v1", "intent_patterns": ["no-such-intent"],
             "citation_policy": "wiki_primary",
             "facets": [{"name": "unused", "request_patterns": ["no-such-facet"],
                         "search_queries": ["unused"], "support_terms": ["unused"]}]}  # fmt: skip


class _Model:
    """Asks the tool it is told to, then answers from what it was given."""

    def __init__(self, tool: str, arguments: Mapping[str, Any]) -> None:
        self.tool, self.arguments = tool, arguments
        self.offered: list[str] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        payload = json.loads(body)
        offered = [t["function"]["name"] for t in payload.get("tools") or ()]
        self.offered = self.offered or offered
        used = any(m["role"] == "tool" for m in payload["messages"])
        name = next((n for n in offered if n.endswith(self.tool)), None)
        if name is not None and not used:
            function = {"name": name, "arguments": json.dumps(self.arguments)}
            call = {"id": "c1", "type": "function", "function": function}
            message: dict[str, Any] = {"role": "assistant", "content": None, "tool_calls": [call]}
        else:
            message = {"role": "assistant", "content": self._answer(payload, bool(offered))}
        return GatewayReply(
            200,
            {
                "id": "scripted",
                "model": "fixture-model",
                "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    @staticmethod
    def _answer(payload: dict[str, Any], chatting: bool) -> str:
        """The chat relays a tool's answer; a synthesis call states and cites
        each passage that holds a fact. No fact given, no fact said."""
        if chatting:
            read = [m["content"] for m in payload["messages"] if m["role"] == "tool"]
            found = sorted(set(FACT.findall(json.dumps(read, ensure_ascii=False))))
            return " ".join(found) if found else "我查不到這項資料。"
        prompt = "\n".join(str(m["content"]) for m in payload["messages"])
        cited = [
            f"Tester X Notes shipping: {' '.join(FACT.findall(m[2]))} [{m[1]}]."
            for m in PASSAGE.finditer(prompt)
            if FACT.search(m[2])
        ]
        return " ".join(cited) if cited else "No passage supports an answer."


def _grant(spec: Any) -> dict[str, Any]:
    return {
        "actor": "engineer",
        "asset": spec.identity.model_dump(mode="json"),
        "permissions": list(spec.policy.required_permissions),
        "policy_refs": list(spec.policy.policy_refs),
    }


def _config(tmp_path: Path, spec: Any, granted: bool, **changes: Any) -> tuple[Any, Any]:
    root = tmp_path / "reader"
    root.mkdir(parents=True, exist_ok=True)
    return workspace(
        root,
        membership=membership_record(),
        grants=[*grant_record(), *([_grant(spec)] if granted else [])],
        config_changes={
            "models": binding(
                catalog={
                    "endpoints": [endpoint(credential=None, model="fixture-model")],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            ),
            **changes,
        },
    )


@contextmanager
def _served(config: Any, layout: Any, model: _Model) -> Iterator[AgentWebServer]:
    with build_runtime(config, layout=layout, model_transport=model) as runtime:
        web = AgentWeb(runtime)
        web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _ask(server: AgentWebServer) -> str:
    """One turn in a new general chat, through the real route."""
    made = server.web.create_conversation()["conversation"]["session_id"]
    reply = fetch(
        base(server) + "/api/conversations/turn",
        token=server.token,
        body={"session_id": made, "message": QUESTION},
    )
    assert reply.status == 200, reply.body
    return str(reply.json()["answer"]["answer"])


# -- wiki repository ------------------------------------------------------------------------


def _wiki_host(tmp_path: Path, repo_id: str, *, granted: bool = True) -> tuple[Any, Any]:
    bound = {"asset": WIKI_ASSET.model_dump(mode="json"), "repo": repo_id}
    config, layout = _config(tmp_path, KNOWLEDGE_QUERY_SPEC, granted, knowledge=[bound])
    layout.knowledge.mkdir(parents=True, exist_ok=True)
    (layout.knowledge / "tester-knowledge.json").write_text(
        _template().model_dump_json(), encoding="utf-8"
    )
    # The conversation offers a Skill's tools only in the host's own namespace.
    skill = json.loads(SKILL.read_text(encoding="utf-8"))
    skill["metadata"]["identity"]["namespace"] = config.namespace
    skill["procedure"] = PROCEDURE
    (layout.skills / "knowledge-evidence.json").write_text(json.dumps(skill), encoding="utf-8")
    return config, layout


WIKI_TOOL = "__tester-knowledge"
WIKI_ARGUMENTS = {"question": QUESTION}


def _wiki_published(tmp_path: Path) -> tuple[Path, Path, str]:
    """A wiki copy imported on the publisher's PC, a fact pushed and published as v1."""
    publisher, drive = tmp_path / "publisher", tmp_path / "drive"
    publisher.mkdir()
    drive.mkdir()
    source = repos._wiki_folder(tmp_path)
    made = repos._ok(
        repos._call(publisher, "POST", "/import",
                    {"source": str(source), "path": str(drive), "title": "Tester wiki",
                     "author": "alice"})
    )  # fmt: skip
    repo_id = str(made["repo"]["id"])
    repos._edit(publisher, repo_id, "Nothing yet.", LINE.format("PUBLISHED"), "第一項事實")
    repos._push(publisher, repo_id)
    repos._ok(
        repos._call(publisher, "POST", f"/{repo_id}/tag", {"name": "v1", "purpose": "第一版"})
    )
    repos._ok(repos._call(publisher, "POST", f"/{repo_id}/publish", {"tag": "v1", "confirm": True}))
    return publisher, drive, repo_id


def _wiki_join(ws: Path, folder: Path, author: str = "bob") -> None:
    repos._ok(repos._call(ws, "POST", "/join", {"path": str(folder), "author": author}))


def test_a_joined_wiki_repository_is_answered_and_cited_from_its_published_version(
    tmp_path: Path,
) -> None:
    publisher, drive, repo_id = _wiki_published(tmp_path)
    config, layout = _wiki_host(tmp_path, repo_id)
    reader = layout.workspace_root
    _wiki_join(reader, drive / repo_id)
    with _served(config, layout, _Model(WIKI_TOOL, WIKI_ARGUMENTS)) as server:
        answer = _ask(server)
        assert "FACT-PUBLISHED" in answer
        assert "資料來源：知識庫 tester-knowledge 發佈版本 v1" in answer
        # This PC's local commit, the publisher's push after v1 and an
        # uncommitted edit are all there, and none is answered.
        repos._edit(reader, repo_id, "Intro.", LINE.format("LOCAL"), "本機")
        repos._edit(publisher, repo_id, "Intro.", LINE.format("PUSHED"), "發佈後")
        repos._push(publisher, repo_id)
        repos._edit(reader, repo_id, "- K1 base", LINE.format("DRAFT"))
        later = _ask(server)
    assert "FACT-PUBLISHED" in later and "發佈版本 v1" in later
    assert not {"FACT-LOCAL", "FACT-PUSHED", "FACT-DRAFT"} & set(FACT.findall(later))


def test_an_imported_copy_never_published_is_answered_from_the_pushed_head_and_says_so(
    tmp_path: Path,
) -> None:
    source = repos._wiki_folder(tmp_path)
    drive = tmp_path / "drive"
    drive.mkdir()
    config, layout = _wiki_host(tmp_path, "tester-wiki")
    ws = layout.workspace_root
    repos._ok(
        repos._call(ws, "POST", "/import",
                    {"source": str(source), "path": str(drive), "id": "tester-wiki",
                     "title": "Tester wiki", "author": "alice"})
    )  # fmt: skip
    repos._edit(ws, "tester-wiki", "Nothing yet.", LINE.format("PUSHED"), "推送")
    repos._push(ws, "tester-wiki")
    repos._edit(ws, "tester-wiki", "Intro.", LINE.format("LOCAL"), "本機")
    with _served(config, layout, _Model(WIKI_TOOL, WIKI_ARGUMENTS)) as server:
        answer = _ask(server)
    assert "FACT-PUSHED" in answer and "FACT-LOCAL" not in answer
    assert "資料來源：知識庫 tester-knowledge（尚未發佈，已 push 的最新版本" in answer


def test_a_wiki_repository_without_the_grant_or_the_skill_answers_nothing(tmp_path: Path) -> None:
    _, drive, repo_id = _wiki_published(tmp_path)
    config, layout = _wiki_host(tmp_path / "no-grant", repo_id, granted=False)
    _wiki_join(layout.workspace_root, drive / repo_id)
    with _served(config, layout, _Model(WIKI_TOOL, WIKI_ARGUMENTS)) as server:
        assert "FACT-PUBLISHED" not in _ask(server)
    config, layout = _wiki_host(tmp_path / "no-skill", repo_id)
    (layout.skills / "knowledge-evidence.json").unlink()
    _wiki_join(layout.workspace_root, drive / repo_id, "carol")
    model = _Model(WIKI_TOOL, WIKI_ARGUMENTS)
    with _served(config, layout, model) as server:
        assert "FACT-PUBLISHED" not in _ask(server)
    assert not any(name.endswith(WIKI_TOOL) for name in model.offered)


# -- BI vault -------------------------------------------------------------------------------


def _bi_published(tmp_path: Path) -> tuple[Path, str, str, Path]:
    """A vault made on the publisher's PC, a card pushed and published as v1;
    the shared folder as this PC sees it."""
    drive, vault_id, dataset, publisher, _ = bi._two_pcs(tmp_path)
    bi._import(publisher, dataset, bi._row("TSN", standard_body="FACT-PUBLISHED"))
    bi._push(publisher, vault_id)
    route = f"/api/bi/vaults/{vault_id}"
    bi._ok(bi._call(publisher, "POST", f"{route}/tag", {"name": "v1", "purpose": "第一版"}))
    bi._ok(bi._call(publisher, "POST", f"{route}/publish", {"tag": "v1", "confirm": True}))
    return drive.parent("a") / vault_id, vault_id, dataset, publisher


def _bi_host(tmp_path: Path, *, granted: bool = True, skill_on: bool = True) -> tuple[Any, Any]:
    config, layout = _config(tmp_path, QUERY_SPEC, granted)
    if skill_on:
        skill_packs.install_bundle(layout, None, shipped=shipped())
    else:
        skill_packs.install_bundle(layout, None, shipped_off=shipped())
    return config, layout


def _bi_join(ws: Path, folder: Path, author: str = "carol") -> None:
    bi._ok(bi._call(ws, "POST", "/api/bi/vaults/join", {"path": str(folder), "author": author}))


def _bi_model(dataset: str) -> _Model:
    return _Model("bi__query", {"dataset": dataset, "entity_type": "Technology", "text": "TSN"})


def test_a_joined_bi_vault_is_answered_and_cited_from_its_published_version(
    tmp_path: Path,
) -> None:
    folder, vault_id, dataset, publisher = _bi_published(tmp_path)
    config, layout = _bi_host(tmp_path)
    reader = layout.workspace_root
    _bi_join(reader, folder)
    with _served(config, layout, _bi_model(dataset)) as server:
        answer = _ask(server)
        assert "FACT-PUBLISHED" in answer
        assert f"資料來源：知識庫 {dataset} 發佈版本 v1" in answer
        # A push after v1 and this PC's own uncommitted edit are not answered.
        bi._ok(bi._edit(publisher, dataset, "TSN", "standard_body", "FACT-PUSHED", "alice"))
        bi._commit(publisher, vault_id, "發佈後")
        bi._push(publisher, vault_id)
        bi._ok(bi._edit(reader, dataset, "TSN", "standard_body", "FACT-DRAFT", "carol"))
        later = _ask(server)
    assert "FACT-PUBLISHED" in later and "發佈版本 v1" in later
    assert not {"FACT-PUSHED", "FACT-DRAFT"} & set(FACT.findall(later))


def test_a_vault_never_published_is_answered_from_the_pushed_head_and_says_so(
    tmp_path: Path,
) -> None:
    drive, vault_id, dataset, publisher, _ = bi._two_pcs(tmp_path)
    bi._import(publisher, dataset, bi._row("TSN", standard_body="FACT-PUSHED"))
    bi._push(publisher, vault_id)
    config, layout = _bi_host(tmp_path)
    _bi_join(layout.workspace_root, drive.parent("a") / vault_id)
    with _served(config, layout, _bi_model(dataset)) as server:
        answer = _ask(server)
    assert "FACT-PUSHED" in answer
    assert f"資料來源：知識庫 {dataset}（尚未發佈，已 push 的最新版本" in answer


def test_a_bi_vault_without_the_grant_or_the_skill_answers_nothing(tmp_path: Path) -> None:
    folder, _, dataset, _ = _bi_published(tmp_path)
    config, layout = _bi_host(tmp_path / "no-grant", granted=False)
    _bi_join(layout.workspace_root, folder)
    with _served(config, layout, _bi_model(dataset)) as server:
        assert "FACT-PUBLISHED" not in _ask(server)
    config, layout = _bi_host(tmp_path / "skill-off", skill_on=False)
    _bi_join(layout.workspace_root, folder, "dave")
    model = _bi_model(dataset)
    with _served(config, layout, model) as server:
        assert "FACT-PUBLISHED" not in _ask(server)
    assert "bi__query" not in model.offered
