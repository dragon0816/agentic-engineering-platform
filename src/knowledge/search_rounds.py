"""Model-directed search rounds for wiki-primary Knowledge (owner 2026-10-10).

Design: docs/phases/KNOWLEDGE_MULTI_ROUND_RETRIEVAL.md. After the first
retrieval, the Gateway model sees search results (page title, heading and a
short snippet), marks the pages that likely hold evidence, and asks for more
searches in the words the Vault uses. The Host runs the searches and reads the
pages. The model never supplies evidence text; it only chooses which Vault
pages are read, and the answer is still cited and Host-checked as before.

Measured offline on the 22 answerable knowledge_v1 core questions: recall of
the files the Claude Code references cite rose from 0.26 to 0.39 with two
extra rounds, at about 2.7 model calls per question.
"""

from __future__ import annotations

import json

from common.execution import TraceIdentifiers
from knowledge.query import Passage, RetrievalSnapshot
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

MAX_QUERIES = 6
MAX_SHOWN = 30
MAX_RELEVANT = 12
SECTIONS_PER_PAGE = 3
SNIPPET_CHARS = 160
PLANNER_PROMPT = (
    "You gather evidence from a bilingual (English / Traditional Chinese) engineering "
    "knowledge base to answer a question. You see search results: page titles with a "
    "matching heading and snippet. Reply with one JSON object "
    '{"relevant_pages": [exact titles from the results that likely hold evidence for the '
    'question], "queries": [up to 6 new short keyword searches, English or Traditional '
    'Chinese, using words the results show the knowledge base uses], "done": true|false}. '
    "Set done when the relevant pages already cover the question. Never answer the question."
)


def _line(passage: Passage, titles: dict[str, str]) -> str:
    page = passage.citation.wiki_page or ""
    head, _, body = passage.text.partition("\n")
    return f"- {titles.get(page, page)} — {head}: {' '.join(body.split())[:SNIPPET_CHARS]}"


def _plan(
    model: ModelClient, alias: str, trace: TraceIdentifiers, question: str,
    shown: list[Passage], relevant: list[str], titles: dict[str, str],
) -> dict[str, object]:
    request = ModelRequest(
        trace=trace, model_alias=alias,
        messages=(
            ModelMessage(role="system", text=PLANNER_PROMPT),
            ModelMessage(role="user", text=(
                f"Question: {question}\n\nAlready marked relevant: "
                f"{', '.join(titles.get(page, page) for page in relevant) or '(none)'}\n\n"
                "Search results:\n" + "\n".join(_line(item, titles) for item in shown))),
        ),
        requirements=ModelRequirements(structured_output=True),
        output_contract="knowledge_search_plan", max_output_tokens=1500,
    )
    try:
        response = model.generate(request)
    except Exception:  # noqa: BLE001 - the rounds are optional; evidence so far is used
        return {}
    if response.failure is not None:
        return {}
    data = response.structured_output
    if not isinstance(data, dict):
        try:
            data = json.loads(response.text or "")
        except ValueError:
            return {}
    return dict(data) if isinstance(data, dict) else {}


def search_rounds(
    snapshot: RetrievalSnapshot, model: ModelClient, alias: str, trace: TraceIdentifiers,
    question: str, first: tuple[Passage, ...], *, rounds: int,
    k: int = 36, max_chars: int = 40000,
) -> tuple[Passage, ...]:
    """The evidence set: pages the model marked relevant lead, then the first
    retrieval's Wiki passages fill the budget, then its Raw passages."""
    if rounds < 1:
        return first
    titles = snapshot.wiki_titles()
    by_title = {title.casefold(): page for page, title in titles.items()}
    seen: set[str] = set()
    shown: list[Passage] = []
    for passage in first:
        page = passage.citation.wiki_page
        if passage.citation.kind == "wiki" and page and page not in seen:
            seen.add(page)
            shown.append(passage)
    relevant: list[str] = []
    queries: list[str] = []
    for _ in range(rounds + 1):
        for query in queries[:MAX_QUERIES]:
            found = snapshot.search_wiki_pages(query, exclude=seen)
            seen.update(item.citation.wiki_page or "" for item in found)
            shown.extend(found)
        if not shown:
            break
        decision = _plan(model, alias, trace, question, shown[:MAX_SHOWN], relevant, titles)
        named = decision.get("relevant_pages")
        for title in named if isinstance(named, list) else []:
            page = by_title.get(str(title).casefold())
            # Only a page the search actually showed may be read.
            if page and page in seen and page not in relevant:
                relevant.append(page)
        asked = decision.get("queries")
        queries = [str(item) for item in asked if str(item).strip()] \
            if isinstance(asked, list) else []
        shown = []
        if decision.get("done") is True or not queries:
            break
    selected: list[Passage] = []
    keys: set[tuple[str | None, int | None]] = set()
    chars = 0

    def add(passage: Passage) -> None:
        nonlocal chars
        key = (passage.citation.wiki_page, passage.citation.section)
        if key in keys or len(selected) >= k or chars + len(passage.text) > max_chars:
            return
        keys.add(key)
        selected.append(passage)
        chars += len(passage.text)

    for page in relevant[:MAX_RELEVANT]:
        for passage in snapshot.wiki_page_sections(page, question, k=SECTIONS_PER_PAGE):
            add(passage)
    for passage in first:
        if passage.citation.kind == "wiki":
            add(passage)
    return (*selected, *(item for item in first if item.citation.kind == "raw"))
