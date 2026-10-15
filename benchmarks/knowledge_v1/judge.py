"""The reasonableness review: the company Gateway model reads the question, the
answer and only the passages the answer cites, and says whether the answer's
claims follow from them.

The reviewer sees no Vault and no other source, so "reasonable" means
reasonable *on the cited evidence*. Its verdict and reasons are stored with
each question for a person to spot-check. The credential is read from the
environment variable the Host maps for the endpoint, never stored.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from common.execution import TraceIdentifiers  # noqa: E402
from models.catalog import ModelEndpoint  # noqa: E402
from models.contracts import ModelMessage, ModelRequest, ModelRequirements  # noqa: E402
from models.openai_compatible import OpenAICompatible  # noqa: E402

JUDGE_VERSION = "1.1"
MAX_PASSAGE_CHARS = 1500
# 1.1 (owner, 2026-10-12): 16 passages hid the later citations of answers built
# on wider evidence, so supported claims were judged unsupported. 48 passages of
# at most 1,500 characters stay well inside the reviewer's context.
MAX_PASSAGES = 48

RUBRIC = """You review one answer from a company knowledge assistant. You get the
question, the answer, and the numbered passages the answer cites. Judge only
against those passages; do not use your own knowledge of the facts.

The bar is "a reasonable, evidence-backed answer", not a line-by-line audit
(owner, 2026-10-07). Decide:
- supported: the answer's main points rest on the cited passages. Framing,
  connecting sentences and modest explanation around a supported point do not
  make it unsupported; a main point the passages do not back, or contradict,
  does.
- reasonable: the conclusion is a fair reading of that evidence and addresses
  the question asked, or says clearly which part the evidence cannot answer.
If the answer says the knowledge base lacks the evidence, judge whether it says
so honestly without inventing facts.
List, for reference, any individual claims that go beyond the passages.

Reply with one JSON object:
{"supported": true|false, "reasonable": true|false,
 "overreach": ["short quote", ...], "reason": "one or two sentences",
 "confidence": "high"|"medium"|"low"}"""


def endpoint_from_host(host_json: Path, alias: str = "company") -> tuple[ModelEndpoint, str]:
    """The Host's model endpoint and the environment variable holding its key."""
    host = json.loads(host_json.read_text(encoding="utf-8"))
    entry = next(e for e in host["models"]["catalog"]["endpoints"] if e["alias"] == alias)
    secret = entry.get("credential", {}).get("name")
    mapped = next(
        (s.get("environment_variable") for s in _secrets(host) if s.get("secret") == secret), None
    )
    if not mapped:
        raise SystemExit(f"host.json maps no environment variable for {secret!r}")
    return ModelEndpoint.model_validate(entry), mapped


def _secrets(host: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if "environment_variable" in value and "secret" in value:
                found.append(value)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(host)
    return found


class Judge:
    def __init__(self, host_json: Path) -> None:
        endpoint, variable = endpoint_from_host(host_json)
        self.alias = endpoint.alias
        self.client = OpenAICompatible(
            endpoint, credential=lambda: os.environ[variable], timeout_s=180.0
        )

    def review(self, question: str, answer: str, passages: list[dict[str, Any]]) -> dict[str, Any]:
        def source(passage: dict[str, Any]) -> str:
            citation = passage.get("citation") or {}
            return str(citation.get("wiki_page") or citation.get("raw_ref") or "")

        shown = (
            "\n\n".join(
                f"[{p['number']}] ({source(p)})\n{str(p.get('text') or '')[:MAX_PASSAGE_CHARS]}"
                for p in passages[:MAX_PASSAGES]
            )
            or "(the answer cites no passages)"
        )
        request = ModelRequest(
            trace=TraceIdentifiers(
                trace_id="knowledge-v1-judge", request_id="judge", span_id="judge"
            ),
            model_alias=self.alias,
            messages=(
                ModelMessage(role="system", text=RUBRIC),
                ModelMessage(
                    role="user",
                    text=f"Question:\n{question}\n\nAnswer:\n{answer}\n\nCited passages:\n{shown}",
                ),
            ),
            requirements=ModelRequirements(structured_output=True),
            output_contract="knowledge_v1_review",
            max_output_tokens=4000,
        )
        response = self.client.generate(request)
        if response.failure is not None:
            return {"ok": False, "error": response.failure.code, "version": JUDGE_VERSION}
        verdict = response.structured_output
        if not isinstance(verdict, dict):
            try:
                verdict = json.loads(response.text)
            except ValueError:
                return {"ok": False, "error": "unparseable_review", "version": JUDGE_VERSION}
        if not isinstance(verdict.get("supported"), bool) or not isinstance(
            verdict.get("reasonable"), bool
        ):
            return {"ok": False, "error": "incomplete_review", "version": JUDGE_VERSION}
        return {
            "ok": True,
            "version": JUDGE_VERSION,
            **{
                k: verdict.get(k)
                for k in ("supported", "reasonable", "overreach", "reason", "confidence")
            },
        }
