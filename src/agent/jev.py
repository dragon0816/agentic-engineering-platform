"""TypeSafe SystemOne adapter for one bounded installed-Skill decision.

The caller must authorize the complete candidate request before constructing
this provider. This adapter never decides data classification or permissions.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from agent.decisions import DecisionAcceleratorConfig, DecisionResult
from agent.gateway import SkillCandidateRequest
from models import wire

_QUESTION = "skill_candidate"
_PRESERVE_CATALOG = "0"
_MAX_REPLY_BYTES = 256_000


#: The suffix every Gateway tool description shares; it names the target,
#: not the purpose, and buried what told the tools apart.
_EXECUTES = re.compile(r"\s*Executes installed \w+ \S+@\S+\.?\s*$")


def _distinct(description: str) -> str:
    """A tool description without the shared execution suffix."""
    return _EXECUTES.sub("", description).strip() or description


def _state(request: SkillCandidateRequest) -> dict[str, str]:
    """The latest user message only.

    Sending the whole model request (system and persona text, earlier turns,
    tool schemas) buried the question: the self-hosted Laya SystemOne then
    chose near-uniformly with confidence about 0.02, while the same cases as
    a plain message were answered (docs/JEV_ADAPTER_READINESS.md, 2026-10-05).
    It also sends less than the classified candidate request.
    """
    for message in reversed(request.initial_request.messages):
        if message.role == "user" and message.text.strip():
            return {"message": message.text}
    return {"message": request.context.message}


class JEVSkillSelectionProvider:
    """Choose one installed command, or request the unchanged full catalog."""

    provider_id = "jev"

    def __init__(
        self,
        config: DecisionAcceleratorConfig,
        credential: Callable[[], str],
        *,
        transport: wire.Transport | None = None,
    ) -> None:
        if config.provider != "JEV" or not config.endpoint or not config.model_profile:
            raise ValueError("JEV skill selection needs endpoint and model profile")
        if "skill_selection" not in config.enabled_decision_types:
            raise ValueError("JEV skill selection must be enabled")
        self._config = config
        self._credential = credential
        self._transport = transport if transport is not None else wire.UrllibTransport()

    def decide(self, request: SkillCandidateRequest) -> DecisionResult[tuple[str, ...]]:
        names = tuple(tool.name for tool in request.tools)
        # Concrete wording measured on Laya (docs/JEV_ADAPTER_READINESS.md):
        # an abstract "preserve" lost to every tool on greetings and chat.
        criteria = {
            _PRESERVE_CATALOG: (
                "General chat, greetings, thanks, asking what you can do, or a request "
                "needing several tools 閒聊/打招呼/問能做什麼/一次多件事"
            )
        }
        criteria.update(
            {
                str(index): request.selector_hints.get(tool.name) or _distinct(tool.description)
                for index, tool in enumerate(request.tools, start=1)
            }
        )
        payload = {
            "model": self._config.model_profile,
            "state": _state(request),
            "questions": {
                _QUESTION: {
                    "type": "choice",
                    "instructions": (
                        "Select one installed tool only when this conversation clearly needs "
                        "that single tool. Otherwise choose 0. Do not infer permission."
                    ),
                    "criteria": criteria,
                }
            },
        }
        token = self._credential()
        if not token or not token.strip():
            raise ValueError("JEV credential is unavailable")
        reply = self._transport.send(
            str(self._config.endpoint),
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            {"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            self._config.timeout_ms / 1_000,
        )
        try:
            if reply.status != 200:
                raise ValueError("JEV returned a non-success status")
            raw = b""
            for chunk in reply.chunks():
                raw += chunk
                if len(raw) > _MAX_REPLY_BYTES:
                    raise ValueError("JEV response is too large")
        finally:
            wire.close_quietly(reply)
        body: Any = json.loads(raw)
        answer = body.get("answers", {}).get(_QUESTION) if isinstance(body, dict) else None
        if not isinstance(answer, dict) or answer.get("type") != "choice":
            raise ValueError("JEV choice answer is missing")
        usage = body.get("usage") if isinstance(body, dict) else None
        if not isinstance(usage, dict) or any(
            isinstance(usage.get(key), bool)
            or not isinstance(usage.get(key), int)
            or usage[key] < 0
            for key in ("input_tokens", "output_tokens")
        ):
            raise ValueError("JEV usage is invalid")
        metadata = {
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
        }
        choice = answer.get("choice")
        confidence = answer.get("confidence")
        if (
            not isinstance(choice, str)
            or choice not in criteria
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            raise ValueError("JEV choice answer is invalid")
        if choice == _PRESERVE_CATALOG:
            return DecisionResult(
                decision_type="skill_selection",
                value=names,
                accepted=False,
                confidence=float(confidence),
                reason_code="preserve_catalog",
                provider_id=self.provider_id,
                metadata=metadata,
            )
        return DecisionResult(
            decision_type="skill_selection",
            value=(names[int(choice) - 1],),
            confidence=float(confidence),
            reason_code="single_skill_candidate",
            provider_id=self.provider_id,
            metadata=metadata,
        )
