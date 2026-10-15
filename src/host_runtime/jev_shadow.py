"""JEV Skill selection on a host: the accelerator, its egress approval, its shadow log.

Nothing is sent unless `decision_accelerator` names JEV **and** carries the
owner's `egress_approval`; the adapter then sends only the latest user message.
In `shadow` mode the accelerator runs in the background and this log records
what it would have chosen next to the tools the model actually called, so
thresholds and list lengths can be chosen from real use
(`python -m evaluation.jev_shadow_report`). The log holds tool names,
probabilities, confidence and timings: never message text.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.decisions import DecisionAcceleratorConfig, DecisionShadow
from agent.gateway import GatewayConversationResult, SkillCandidateRequest
from agent.jev import JEVSkillSelectionProvider
from models.credentials import CredentialResolver

SHADOW_LOG_FILE = "jev-shadow.jsonl"


class JevShadowLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _append(self, record: dict[str, Any]) -> None:
        line = json.dumps(
            {"at": datetime.now(UTC).isoformat(), **record},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def decision(self, request: SkillCandidateRequest, shadow: DecisionShadow) -> None:
        self._append(
            {
                "kind": "shadow",
                "trace_id": request.context.trace.trace_id,
                "offered": [tool.name for tool in request.tools],
                "outcome": shadow.outcome,
                "chosen": shadow.value,
                "confidence": shadow.confidence,
                "reason": shadow.reason_code,
                "latency_ms": round(shadow.latency_ms, 1),
                "probabilities": shadow.metadata.get("probabilities"),
                "choice_confidence": shadow.metadata.get("choice_confidence"),
            }
        )

    def conversation(self, result: GatewayConversationResult) -> None:
        self._append(
            {
                "kind": "turn",
                "trace_id": result.trace.trace_id,
                "status": result.status,
                "called": [item.name for item in result.tools],
            }
        )


def skill_accelerator(
    config: DecisionAcceleratorConfig, resolver: CredentialResolver
) -> tuple[
    Callable[[], JEVSkillSelectionProvider] | None,
    Callable[[SkillCandidateRequest], bool] | None,
]:
    """The factory and authorizer for a JEV Skill selector, or (None, None).

    The authorizer admits a request only when the owner recorded an egress
    approval; the credential is resolved per call, after that admission."""
    if (
        config.provider != "JEV"
        or "skill_selection" not in config.enabled_decision_types
        or config.credential is None
        or not config.model_profile
    ):
        return None, None
    credential = config.credential

    def factory() -> JEVSkillSelectionProvider:
        return JEVSkillSelectionProvider(
            config, lambda: resolver.resolve(credential), max_tools=config.skill_max_tools
        )

    def authorize(_request: SkillCandidateRequest) -> bool:
        return config.egress_approval is not None

    return factory, authorize
