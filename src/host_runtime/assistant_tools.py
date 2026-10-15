"""AEP's assistant tools for an external agent such as GitHub Copilot (CP1).

`docs/phases/COPILOT_INTEGRATION.md`. Served by the running Agent Web at
`POST /mcp` (MCP over HTTP, JSON-RPC 2.0), so Copilot in Agent Web or in
VS Code uses the Host's loaded Knowledge and models. The tools are read only:
Knowledge search, page reading and the Knowledge Harness's validated answer,
the installed Workflows, and running an installed Workflow that only reads.
A Workflow that changes something is left to the person in Agent Web, because
an agent chose it (owner mode: model-chosen side effects wait for a person).

Unlike the authoring tools (statuses and codes only), these return content:
the owner approved sending all data to Copilot (2026-10-12).
"""

from __future__ import annotations

import json
import secrets
import uuid
from pathlib import Path
from typing import Any

from common.assets import AssetIdentity, WorkflowManifest
from knowledge.query import RetrievalSnapshot
from knowledge.vault import normalize

TOKEN_FILE = "assistant-mcp-token"
MAX_PAGE_CHARS = 40_000
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCTIONS = (
    "AEP assistant tools. For company knowledge (R&S products, options, standards, "
    "markets, competitors), search with aep_knowledge_search, read pages with "
    "aep_knowledge_read and cite the page paths you used; aep_knowledge_ask returns "
    "AEP's validated, cited answer. aep_workflows lists installed Workflows; "
    "aep_run_workflow runs one that only reads. Never claim to have run a Workflow "
    "that the tool said must be run by the person."
)

_Q = {"type": "string"}
TOOLS: dict[str, tuple[str, dict[str, Any]]] = {
    "aep_knowledge_search": (
        "Search the company knowledge base (curated wiki and raw sources). Returns page "
        "paths, titles and the best matching section. Try English and Chinese wording.",
        {
            "type": "object",
            "properties": {"query": _Q, "limit": {"type": "integer"}},
            "required": ["query"],
        },
    ),
    "aep_knowledge_read": (
        "Read one knowledge page in full by its path (wiki/... or raw/...).",
        {"type": "object", "properties": {"path": _Q}, "required": ["path"]},
    ),
    "aep_knowledge_ask": (
        "Ask AEP's Knowledge Harness: a validated answer with its cited sources.",
        {"type": "object", "properties": {"question": _Q}, "required": ["question"]},
    ),
    "aep_workflows": (
        "List the installed Workflows: id, description, parameters, and whether it only reads.",
        {"type": "object", "properties": {}},
    ),
    "aep_run_workflow": (
        "Run an installed Workflow by id (namespace/name@version) with its parameters. "
        "Only Workflows that only read run here; others must be run by the person.",
        {
            "type": "object",
            "properties": {"workflow": _Q, "arguments": {"type": "object"}},
            "required": ["workflow"],
        },
    ),
}


def assistant_token(workspace: Path) -> str:
    """A token only for these tools, stable across Agent Web restarts, so a
    VS Code MCP configuration keeps working."""
    path = workspace / TOKEN_FILE
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError:
        token = ""
    if len(token) < 32:
        token = secrets.token_urlsafe(32)
        path.write_text(token, encoding="utf-8")
    return token


def _identity(text: str) -> AssetIdentity:
    names, _, version = text.strip().partition("@")
    namespace, _, name = names.partition("/")
    return AssetIdentity(namespace=namespace, name=name, version=version)


class AssistantTools:
    def __init__(self, web: Any) -> None:
        self.web = web

    # -- knowledge ---------------------------------------------------------

    def _vault(self) -> Any:
        from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC

        installed = self.web.runtime.agent.gateway.bridge.installed.get(
            KNOWLEDGE_QUERY_SPEC.identity
        )
        catalog = getattr(getattr(installed, "handler", None), "catalog", None)
        if catalog is None or not catalog.manifests():
            raise LookupError("knowledge_unavailable")
        return catalog.get(catalog.manifests()[0].metadata.identity)[1]

    def knowledge_search(self, query: str, limit: int = 8) -> dict[str, Any]:
        vault = self._vault()
        snapshot = RetrievalSnapshot.cached(vault)
        limit = max(1, min(int(limit or 8), 20))
        titles = snapshot.wiki_titles()
        results = [
            {
                "kind": "wiki",
                "path": p.citation.wiki_page,
                "title": titles.get(p.citation.wiki_page or "", ""),
                "text": p.text[:1500],
            }
            for p in snapshot.search_wiki_pages(query, exclude=set(), limit=limit)
        ]
        raw = [p for p in snapshot.batch((query,), k=limit)[0] if p.citation.kind == "raw"]
        results += [
            {"kind": "raw", "path": p.citation.raw_ref, "title": "", "text": p.text[:1500]}
            for p in raw[: max(2, limit // 2)]
        ]
        return {"ok": True, "results": results}

    def knowledge_read(self, path: str) -> dict[str, Any]:
        rel = normalize(path)
        if (
            ".." in rel.split("/")
            or not rel.endswith(".md")
            or not rel.startswith(("wiki/", "raw/"))
        ):
            return {"ok": False, "code": "not_a_knowledge_page"}
        vault = self._vault()
        if not vault.exists(rel):
            return {"ok": False, "code": "unknown_page"}
        text = vault.read(rel)
        return {
            "ok": True,
            "path": rel,
            "text": text[:MAX_PAGE_CHARS],
            "truncated": len(text) > MAX_PAGE_CHARS,
        }

    def knowledge_ask(self, question: str) -> dict[str, Any]:
        from host_runtime.contracts import KnowledgeAskRequest
        from host_runtime.knowledge_harness import harness_skill, knowledge_source_lines

        knowledge = self.web.runtime.config.knowledge
        if not knowledge:
            return {"ok": False, "code": "knowledge_unavailable"}
        skill = harness_skill(self.web.runtime.agent.gateway.router.commands.skills)
        reply = self.web.knowledge_harness.ask(
            KnowledgeAskRequest(asset=knowledge[0].asset, question=question, skill=skill)
        )
        record = reply.get("record") or {}
        return {
            "ok": bool(reply.get("ok")),
            "validated": bool(reply.get("ok")),
            "answer": str(reply.get("answer") or ""),
            "sources": knowledge_source_lines(record) if record else [],
        }

    # -- workflows ---------------------------------------------------------

    def _installed(self) -> list[WorkflowManifest]:
        from host_runtime.web import manifests  # web imports this module

        return list(manifests(self.web.runtime.layout.workflows, WorkflowManifest))

    def workflows(self) -> dict[str, Any]:
        chat = self.web.runtime.chat_authoring
        items = []
        for manifest in self._installed():
            identity = manifest.metadata.identity
            items.append(
                {
                    "workflow": f"{identity.namespace}/{identity.name}@{identity.version}",
                    "description": getattr(manifest, "description", "") or "",
                    "parameters": json.loads(
                        json.dumps(
                            [
                                p.model_dump(mode="json")
                                for p in getattr(manifest, "parameters", ())
                            ],
                            default=str,
                        )
                    ),
                    "read_only": bool(chat.read_only(manifest)) if chat is not None else False,
                }
            )
        return {"ok": True, "workflows": items}

    def run_workflow(self, workflow: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        from host_runtime.contracts import WorkflowLaunchRequest

        try:
            identity = _identity(workflow)
        except ValueError:
            return {"ok": False, "code": "workflow_id_invalid"}
        manifest = next((m for m in self._installed() if m.metadata.identity == identity), None)
        if manifest is None:
            return {"ok": False, "code": "workflow_not_installed"}
        chat = self.web.runtime.chat_authoring
        if chat is None or not chat.read_only(manifest):
            return {
                "ok": False,
                "code": "needs_person",
                "message": "This Workflow changes something; the person must run it from "
                "Agent Web. Do not say it ran.",
            }
        result = self.web.launch_workflow(
            WorkflowLaunchRequest(
                workflow=identity,
                arguments=arguments or {},
                idempotency_key=f"assistant-{uuid.uuid4().hex}",
            )
        )
        return {"ok": bool(result.get("ok")), "answer": result.get("answer")}

    # -- dispatch ----------------------------------------------------------

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "aep_knowledge_search":
                return self.knowledge_search(
                    str(args.get("query") or ""), int(args.get("limit") or 8)
                )
            if name == "aep_knowledge_read":
                return self.knowledge_read(str(args.get("path") or ""))
            if name == "aep_knowledge_ask":
                return self.knowledge_ask(str(args.get("question") or ""))
            if name == "aep_workflows":
                return self.workflows()
            if name == "aep_run_workflow":
                arguments = args.get("arguments")
                return self.run_workflow(
                    str(args.get("workflow") or ""),
                    arguments if isinstance(arguments, dict) else {},
                )
        except LookupError as error:
            return {"ok": False, "code": str(error)}
        except Exception as error:  # noqa: BLE001 - a tool error, never a crash
            return {"ok": False, "code": f"failed:{type(error).__name__}"}
        return {"ok": False, "code": "unknown_tool"}


def handle(tools: AssistantTools, message: dict[str, Any]) -> dict[str, Any] | None:
    """One MCP JSON-RPC message; None for a notification."""
    method, ident = message.get("method"), message.get("id")
    params = message.get("params") or {}
    if ident is None:
        return None
    if method == "initialize":
        asked = str(params.get("protocolVersion") or "")
        return _result(
            ident,
            {
                "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "aep", "version": "assistant-1"},
                "instructions": INSTRUCTIONS,
            },
        )
    if method == "ping":
        return _result(ident, {})
    if method == "tools/list":
        return _result(
            ident,
            {
                "tools": [
                    {"name": name, "description": text, "inputSchema": schema}
                    for name, (text, schema) in TOOLS.items()
                ]
            },
        )
    if method == "tools/call":
        name = str(params.get("name") or "")
        if name not in TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": ident,
                "error": {"code": -32602, "message": f"unknown tool {name}"},
            }
        arguments = params.get("arguments")
        outcome = tools.call(name, arguments if isinstance(arguments, dict) else {})
        return _result(
            ident,
            {
                "content": [{"type": "text", "text": json.dumps(outcome, ensure_ascii=False)}],
                "structuredContent": outcome,
                "isError": outcome.get("ok") is False,
            },
        )
    return {
        "jsonrpc": "2.0",
        "id": ident,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


def _result(ident: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "result": result}
