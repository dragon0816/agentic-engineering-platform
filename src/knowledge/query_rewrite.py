"""Bilingual search queries for a Knowledge question (owner 2026-10-09).

The Vault mixes English and Traditional Chinese, and its curated pages often
name a topic differently from the question (a Chinese UAV supply-chain page for
an English "Aerospace / Defense" question). Lexical retrieval cannot bridge
that, so before retrieval the Gateway model writes a few short keyword queries
in both languages. They only widen what is retrieved: every answer claim is
still cited and Host-checked against the retrieved passages.

Measured on the 22 answerable knowledge_v1 core questions against the Claude
Code reference sources: recall of the reference files rose from 0.12 to 0.26
together with the other retrieval changes of the same day.
"""

from __future__ import annotations

import json
import re

from common.execution import TraceIdentifiers
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

MAX_QUERIES = 6
MAX_QUERY_CHARS = 80
REWRITE_PROMPT = (
    "You write search queries for a bilingual (English and Traditional Chinese) "
    "engineering knowledge base about test and measurement equipment, markets and "
    "technologies. Given a question, reply with one JSON object "
    '{"queries": [...]}: 6 short keyword queries (2-6 words each), 3 in English '
    "and 3 in Traditional Chinese, covering the question's main subject, its "
    "synonyms, related test topics and the product or market names. Keywords "
    "only; never answer the question."
)
# Only English function words: question templates add noise words such as
# "what" and "which" that outweigh a short topic word like "EVM".
STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been before
being below between both but by can could did do does doing down during each few for
from further had has have having he her here hers him his how i if in into is it its
itself just me more most my no nor not now of off on once only or other our out over own
same she should so some such than that the their them then there these they this those
through to too under until up very was we were what when where which while who whom why
will with would you your
""".split())
_WORD = re.compile(r"\w+", re.UNICODE)


def content_words(text: str) -> str:
    """The question without English function words, for lexical retrieval."""
    kept = [word for word in _WORD.findall(text) if word.casefold() not in STOPWORDS]
    return " ".join(kept) or text


def rewrite_queries(
    model: ModelClient, alias: str, question: str, trace: TraceIdentifiers,
) -> tuple[str, ...]:
    """Up to six keyword queries; none when the model fails, so retrieval goes on."""
    request = ModelRequest(
        trace=trace, model_alias=alias,
        messages=(ModelMessage(role="system", text=REWRITE_PROMPT),
                  ModelMessage(role="user", text=question)),
        requirements=ModelRequirements(structured_output=True),
        output_contract="knowledge_query_rewrite", max_output_tokens=800,
    )
    try:
        response = model.generate(request)
    except Exception:  # noqa: BLE001 - a rewrite is optional; retrieval still runs
        return ()
    if response.failure is not None:
        return ()
    data = response.structured_output
    if not isinstance(data, dict):
        try:
            data = json.loads(response.text or "")
        except ValueError:
            return ()
    items = data.get("queries") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return ()
    queries = [
        " ".join(item.split())[:MAX_QUERY_CHARS]
        for item in items if isinstance(item, str) and item.strip()
    ]
    return tuple(dict.fromkeys(queries))[:MAX_QUERIES]
