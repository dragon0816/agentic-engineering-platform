"""Bilingual retrieval for wiki-primary Knowledge (owner 2026-10-09)."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

from test_knowledge_wiki_primary import ASSET, TRACE, _Catalog, _procedure, _wiki_vault

from capabilities.knowledge_query.handlers import KnowledgeQueryHandler
from common.execution import Failure, RequestContext
from knowledge.query_rewrite import REWRITE_PROMPT, content_words, rewrite_queries
from knowledge.vault import Vault
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent


class _Model:
    """Answers the rewrite request with `rewrite`, then synthesizes from the prompt."""

    def __init__(self, rewrite: str | Exception | None, answer: str = "") -> None:
        self.rewrite = rewrite
        self.answer = answer
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if request.messages[0].text == REWRITE_PROMPT:
            if isinstance(self.rewrite, Exception):
                raise self.rewrite
            if self.rewrite is None:
                return ModelResponse(
                    trace=request.trace,
                    model_alias=request.model_alias,
                    failure=Failure(code="model_http_error", message="503"),
                )
            return ModelResponse(
                trace=request.trace, model_alias=request.model_alias, text=self.rewrite
            )
        prompt = request.messages[0].text
        number = next(
            (block.split("]")[0] for block in prompt.split("\n\n[")[1:] if "示波器" in block), "1"
        )
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            text=self.answer or f"示波器眼圖量測 [{number}].",
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def _vault(tmp_path: Path) -> Vault:
    vault = _wiki_vault(tmp_path)
    (tmp_path / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "wiki" / "concepts" / "示波器量測.md").write_text(
        "---\ntitle: 示波器量測\n---\n# 示波器量測\n\n示波器眼圖量測用於高速訊號完整性驗證，"
        "包含抖動、上升時間與眼高眼寬的判讀。\n",
        encoding="utf-8",
    )
    return vault


def _ask(vault: Vault, model: _Model, **update: object) -> None:
    handler = KnowledgeQueryHandler(_Catalog(vault), model, alias="a")  # type: ignore[arg-type]
    context = RequestContext(
        trace=TRACE,
        actor="engineer",
        namespace="engineering",
        message="ZNA option",
        channel="local",
    )
    request = {
        "asset": ASSET.model_dump(mode="json"),
        "question": "ZNA option",
        "procedure": _procedure(**update).model_dump(mode="json"),
    }
    asyncio.run(handler(context, request))  # type: ignore[arg-type]


def test_content_words_drop_english_function_words_only() -> None:
    assert content_words("What is EVM, and which product depends on it?") == "EVM product depends"
    assert content_words("what is it") == "what is it"  # nothing left: keep the question
    assert content_words("示波器 的 量測") == "示波器 的 量測"


def test_rewrite_queries_are_bounded_and_deduplicated() -> None:
    long = "x" * 200
    model = _Model(
        '{"queries": ["EVM  test", "EVM test", "誤差向量", 3, "", "' + long + '", "a", "b", "c"]}'
    )
    queries = rewrite_queries(model, "a", "What is EVM?", TRACE)
    assert queries[:2] == ("EVM test", "誤差向量")
    assert len(queries) == 6 and len(queries[2]) == 80


def test_a_failed_or_unparseable_rewrite_gives_no_queries() -> None:
    for rewrite in (None, RuntimeError("down"), "not json", '{"queries": "EVM"}'):
        assert rewrite_queries(_Model(rewrite), "a", "q", TRACE) == ()


def test_bilingual_retrieval_offers_a_page_only_the_rewrite_finds(tmp_path: Path) -> None:
    model = _Model('{"queries": ["示波器 眼圖"]}')
    try:
        _ask(_vault(tmp_path), model, bilingual_retrieval=True)
    except Exception:  # noqa: BLE001 - only what the model was offered matters here
        pass
    assert model.requests[0].messages[0].text == REWRITE_PROMPT
    assert "示波器眼圖量測用於" in model.requests[1].messages[0].text


def test_without_bilingual_retrieval_no_rewrite_is_asked(tmp_path: Path) -> None:
    model = _Model('{"queries": ["示波器 眼圖"]}', answer="ZNA-K2 time domain [1].")
    try:
        _ask(_vault(tmp_path), model)
    except Exception:  # noqa: BLE001 - only the requests matter here
        pass
    assert all(request.messages[0].text != REWRITE_PROMPT for request in model.requests)
    assert all("示波器眼圖量測用於" not in request.messages[0].text for request in model.requests)


def test_a_failed_rewrite_still_answers_from_the_question(tmp_path: Path) -> None:
    model = _Model(RuntimeError("gateway down"), answer="ZNA-K2 time domain [1].")
    try:
        _ask(_vault(tmp_path), model, bilingual_retrieval=True)
    except Exception:  # noqa: BLE001 - grounding of the stand-in answer is not tested here
        pass
    assert len(model.requests) == 2  # the rewrite, then the synthesis
