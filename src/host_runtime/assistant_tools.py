"""Authenticated assistant MCP tools served by the loaded Agent Web host.

Installed Bridge/MCP tools execute without application grant or approval cards.
New generic native result contents are withheld when receiving-model eligibility
is not established; execution status remains truthful. Existing Knowledge/BI
content endpoints retain their own data-route contracts. An older Copilot content
approval does not classify arbitrary new tool output or extend to other backends.
"""

from __future__ import annotations

import json
import secrets
import uuid
from pathlib import Path
from typing import Any

from common.assets import AssetIdentity, WorkflowManifest
from common.execution import TraceIdentifiers
from host_runtime.tool_access import ToolAccess, mcp_definitions, tool_context
from knowledge.query import RetrievalSnapshot
from knowledge.vault import normalize

TOKEN_FILE = "assistant-mcp-token"
MAX_PAGE_CHARS = 40_000
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCTIONS = (
    "AEP assistant tools. For company knowledge (R&S products, options, standards, "
    "markets, competitors), search with aep_knowledge_search, read pages with "
    "aep_knowledge_read and cite the page paths you used; aep_knowledge_ask returns "
    "AEP's validated, cited answer. aep_bi_query reads BI cards and saved analyses of a "
    "knowledge base when the owner turned it on. aep_workflows lists installed Workflows; "
    "aep_run_workflow runs an installed Workflow. Return actual results and never "
    "repeat a succeeded side effect. Draft does not mean send."
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
    "aep_bi_query": (
        "Read BI knowledge cards (customers, opportunities, competitors, trends) or a saved "
        "analysis of a knowledge base (vault), from its published version; quote the `source` "
        "line it returns. Give dataset (vault-<id>) and either analysis (a slug, `all` or "
        "`quality`) or a search (entity_type, text, field, value, domain). No SQL. It is off "
        "until the owner turns it on in Agent Web, Settings > Coding agents: a call then "
        "answers bi_query_off; tell the person and do not guess an answer.",
        {
            "type": "object",
            "properties": {
                "dataset": _Q,
                "analysis": _Q,
                "params": {"type": "object"},
                "entity_type": _Q,
                "text": _Q,
                "field": _Q,
                "value": _Q,
                "domain": _Q,
                "follow_links": {"type": "boolean"},
                "limit": {"type": "integer"},
                "hops": {"type": "integer"},
            },
        },
    ),
    "aep_workflows": (
        "List the installed Workflows: id, description, parameters, and whether it only reads.",
        {"type": "object", "properties": {}},
    ),
    "aep_run_workflow": (
        "Run an installed Workflow by id (namespace/name@version) with its parameters. "
        "Runs under the actual execution environment, without an AEP approval card.",
        {
            "type": "object",
            "properties": {"workflow": _Q, "arguments": {"type": "object"}},
            "required": ["workflow"],
        },
    ),
}
TOOLS.update(mcp_definitions())


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


def _trace() -> TraceIdentifiers:
    value = uuid.uuid4().hex
    return TraceIdentifiers(
        trace_id=f"trace-{value}", request_id=f"request-{value}", span_id=f"span-{value}"
    )


def _identity(text: str) -> AssetIdentity:
    names, _, version = text.strip().partition("@")
    namespace, _, name = names.partition("/")
    return AssetIdentity(namespace=namespace, name=name, version=version)


class AssistantTools:
    def __init__(
        self, web: Any, *, session_id: str | None = None, backend: str | None = None
    ) -> None:
        self.web = web
        self.session_id = session_id
        self.backend = backend

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
        skill = harness_skill(
            self.web.runtime.agent.gateway.router.commands.skills, knowledge[0].asset
        )
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

    # -- BI cards ----------------------------------------------------------

    def bi_query_on(self) -> bool:
        return bool(getattr(getattr(self.web.runtime, "config", None), "assistant_bi_query", False))

    def listed(self) -> tuple[str, ...]:
        """The tools this Agent Web offers now; `aep_bi_query` only while on."""
        return tuple(n for n in TOOLS if n != "aep_bi_query" or self.bi_query_on())

    def bi_query(self, args: dict[str, Any]) -> dict[str, Any]:
        from host_runtime import bi_assistant_query

        return bi_assistant_query.answer(
            self.web.runtime, args, enabled=self.bi_query_on(), trace=_trace()
        )

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
        result = self.web.launch_workflow(
            WorkflowLaunchRequest(
                workflow=identity,
                arguments=arguments or {},
                idempotency_key=f"assistant-{uuid.uuid4().hex}",
                session_id=self.session_id,
            )
        )
        return {"ok": bool(result.get("ok")), "answer": result.get("answer")}

    # -- dispatch ----------------------------------------------------------

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            if name in mcp_definitions():
                runtime = self.web.runtime
                return ToolAccess(runtime.agent.gateway.bridge, mcp=runtime.mcp).native_call(
                    name,
                    args,
                    tool_context(
                        runtime.actor,
                        runtime.config.namespace or "engineering",
                        self.session_id,
                    ),
                    self.backend,
                )
            if name == "aep_knowledge_search":
                return self.knowledge_search(
                    str(args.get("query") or ""), int(args.get("limit") or 8)
                )
            if name == "aep_knowledge_read":
                return self.knowledge_read(str(args.get("path") or ""))
            if name == "aep_knowledge_ask":
                return self.knowledge_ask(str(args.get("question") or ""))
            if name == "aep_bi_query":
                return self.bi_query(args)
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
                    if name in tools.listed()
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
