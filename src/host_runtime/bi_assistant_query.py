"""`aep_bi_query`: an external agent reads a BI vault (`BI_VAULT_ASKING.md` §5).

`host_runtime.assistant_tools` serves the tool and names no BI type (ADR-K10); this
is its BI side. A vault's published version through the Bridge and its grant, as
`bi__query`, without SQL.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from capabilities.bi_cards import vault
from capabilities.bi_cards.capability import QUERY_SPEC
from capabilities.bi_cards.store import VAULT_PREFIX
from common.execution import TraceIdentifiers
from common.local_agent import LocalCapabilityRequest
from host_runtime.bi_cards_tools import bi_skill_on
from knowledge.repo.repository import source_line

#: What `aep_bi_query` passes on to `bi-cards/query`; never `sql` or `chart`.
BI_QUERY_FIELDS = (
    "dataset",
    "analysis",
    "params",
    "entity_type",
    "text",
    "field",
    "value",
    "domain",
    "follow_links",
    "limit",
)


def answer(
    runtime: Any, args: dict[str, Any], *, enabled: bool, trace: TraceIdentifiers
) -> dict[str, Any]:
    if not enabled:
        return {
            "ok": False,
            "code": "bi_query_off",
            "message": "The owner has not turned this on (Agent Web, Settings > Coding "
            "agents). Say so; do not guess an answer.",
        }
    if "sql" in args:
        return {"ok": False, "code": "sql_not_allowed"}
    if not bi_skill_on(runtime.agent.gateway):
        return {"ok": False, "code": "bi_unavailable"}
    workspace = Path(runtime.layout.workspace_root)
    vaults = [
        {
            "dataset": vault.dataset_name(str(item["id"])),
            "title": item.get("title"),
            "purpose": item.get("purpose"),
        }
        for item in vault.listing(workspace)
    ]
    dataset = str(args.get("dataset") or "")
    if not dataset:
        return {"ok": False, "code": "dataset_missing", "vaults": vaults}
    known = dataset.startswith(VAULT_PREFIX) and vault.registry_entry(
        workspace, dataset[len(VAULT_PREFIX) :]
    )
    if not known:
        return {"ok": False, "code": "not_a_vault", "vaults": vaults}
    outcome = asyncio.run(
        runtime.agent.execute_capability(
            LocalCapabilityRequest(
                ingress="local",
                actor=runtime.actor,
                bridge_id=runtime.config.device.bridge_id,
                target=QUERY_SPEC.identity,
                arguments={k: args[k] for k in BI_QUERY_FIELDS if k in args},
                trace=trace,
            )
        )
    )
    result = outcome.capability
    if result is None or result.status != "succeeded":
        failure = None if result is None else result.failure
        code = failure.code if failure is not None else str(outcome.refusal or "failed")
        return {"ok": False, "code": code}
    data = dict(result.data or {})
    read = data.get("vault") or {}
    return {
        "ok": True,
        "dataset": data.get("dataset"),
        "total": data.get("total"),
        "cards": data.get("cards") or [],
        "analysis": data.get("analysis") or [],
        "scope_note": data.get("scope_note"),
        "source": source_line(dataset, read),
        "sample_note": data.get("sample_note") or "",
        "reads": {"tag": read.get("tag"), "commit": read.get("commit")},
    }
