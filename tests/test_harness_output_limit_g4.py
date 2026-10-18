"""G4: a Harness result leaves the conversation loop at its domain's own output
limit, and a cut is never silent (owner 2026-10-18).

The Knowledge Harness declares its limit from the Skill procedure's synthesis
output tokens (4 characters per token bound English and Chinese text) plus the
Host's own source lines and notes. U7 found the loop cut answers at a fixed
12,000 characters while the direct route showed them whole.
"""

from __future__ import annotations

import asyncio
from typing import Any

from test_gateway import request
from test_knowledge_vault_tools import CallsVault, Recording, gateway

from agent.harness_handoff import DEFAULT_OUTPUT_LIMIT_CHARS
from host_runtime.knowledge_harness import OUTPUT_CHARS_PER_TOKEN, output_limit_chars
from knowledge.procedure import KnowledgeProcedure
from knowledge.query import DEFAULT_SYNTHESIS_MAX_OUTPUT_TOKENS
from models.contracts import ModelMessage


def converse(answer: dict[str, Any]) -> Any:
    model = CallsVault("knowledge__rs-knowledge", {"question": "q"})
    built = gateway(model, Recording())
    built.knowledge_harness = lambda question, asset, anchor: answer
    return asyncio.run(built.converse(request("q"), (ModelMessage(role="user", text="q"),)))


def test_an_answer_within_the_declared_limit_is_returned_whole() -> None:
    long = "x [1]. " * 3_000  # 21,000 characters: the old loop cut it at 12,000
    result = converse({"ok": True, "answer": long, "output_limit_chars": 40_000})
    assert result.text == long
    host = result.tools[0].host
    assert host is not None and isinstance(host.data, dict)
    assert host.data["answer"] == long and "truncated" not in host.data


def test_a_cut_says_so_and_how_to_get_the_full_answer() -> None:
    long = "y [1]. " * 3_000
    result = converse({"ok": True, "answer": long, "output_limit_chars": 1_000})
    assert result.text.startswith(long[:1_000])
    assert len(result.text) < len(long)
    assert "Host 註記" in result.text and "1000" in result.text.replace(",", "")
    assert "record" in result.text  # where the full answer is kept
    host = result.tools[0].host
    assert host is not None and isinstance(host.data, dict)
    assert host.data["truncated"] == {"limit_chars": 1_000, "full_chars": len(long)}


def test_a_harness_without_a_declared_limit_uses_the_default_synthesis_limit() -> None:
    assert (
        DEFAULT_OUTPUT_LIMIT_CHARS == DEFAULT_SYNTHESIS_MAX_OUTPUT_TOKENS * OUTPUT_CHARS_PER_TOKEN
    )
    long = "z" * (DEFAULT_OUTPUT_LIMIT_CHARS + 10)
    result = converse({"ok": True, "answer": long})
    assert "Host 註記" in result.text
    assert result.text.startswith(long[:DEFAULT_OUTPUT_LIMIT_CHARS])


def test_the_knowledge_limit_follows_the_skill_procedure_and_host_text() -> None:
    procedure = KnowledgeProcedure.model_validate(
        {
            "intent_patterns": ["x"],
            "facets": [
                {
                    "name": "f",
                    "request_patterns": ["x"],
                    "search_queries": ["x"],
                    "support_terms": ["x"],
                }
            ],
            "synthesis_max_output_tokens": 8192,
        }
    )
    assert output_limit_chars(procedure, "a" * 100, "a" * 100) == 8192 * OUTPUT_CHARS_PER_TOKEN
    # The Host's source list and notes are added on top of the model's text.
    assert output_limit_chars(procedure, "a" * 100, "a" * 150) == 8192 * 4 + 50
    assert output_limit_chars(None, "", "") == DEFAULT_SYNTHESIS_MAX_OUTPUT_TOKENS * 4
