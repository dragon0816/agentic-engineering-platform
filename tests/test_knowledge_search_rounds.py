"""Model-directed search rounds for wiki-primary Knowledge (owner 2026-10-10)."""

import json
from collections.abc import Iterator
from pathlib import Path

from test_knowledge_wiki_primary import TRACE, _wiki_vault

from common.execution import Failure
from knowledge.query import Passage, RetrievalSnapshot
from knowledge.search_rounds import PLANNER_PROMPT, search_rounds
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

ZH_PAGE = "wiki/concepts/示波器量測.md"


class _Planner:
    """Replies to each planner request in turn with the given decisions."""

    def __init__(self, *decisions: dict[str, object] | None) -> None:
        self.decisions = list(decisions)
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        assert request.messages[0].text == PLANNER_PROMPT
        decision = self.decisions.pop(0) if self.decisions else {"done": True}
        if decision is None:
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                failure=Failure(code="model_http_error", message="503"),
            )
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            text=json.dumps(decision, ensure_ascii=False),
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def _snapshot(tmp_path: Path) -> RetrievalSnapshot:
    vault = _wiki_vault(tmp_path)
    (tmp_path / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "wiki" / "concepts" / "示波器量測.md").write_text(
        "---\ntitle: 示波器量測\n---\n# 示波器量測\n\n示波器眼圖量測用於高速訊號完整性驗證，"
        "包含抖動、上升時間與眼高眼寬的判讀。\n",
        encoding="utf-8",
    )
    return RetrievalSnapshot(vault)


def _first(snapshot: RetrievalSnapshot) -> tuple[Passage, ...]:
    return snapshot.wiki_primary_passages(("ZNA option",))


def _rounds(snapshot: RetrievalSnapshot, planner: _Planner, rounds: int = 2) -> tuple[Passage, ...]:
    return search_rounds(
        snapshot,
        planner,
        "a",
        TRACE,
        "ZNA option",
        _first(snapshot),
        rounds=rounds,
    )


def test_no_rounds_keeps_the_first_retrieval_without_a_model_call(tmp_path: Path) -> None:
    snapshot, planner = _snapshot(tmp_path), _Planner()
    assert _rounds(snapshot, planner, rounds=0) == _first(snapshot)
    assert planner.requests == []


def test_a_page_found_by_a_later_search_leads_the_evidence(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    assert all(p.citation.wiki_page != ZH_PAGE for p in _first(snapshot))
    planner = _Planner(
        {"relevant_pages": [], "queries": ["示波器 眼圖"]},
        {"relevant_pages": ["示波器量測"], "done": True},
    )
    evidence = _rounds(snapshot, planner)
    assert evidence[0].citation.wiki_page == ZH_PAGE
    assert "示波器量測" in planner.requests[1].messages[1].text  # shown as a search result
    assert len(planner.requests) == 2


def test_a_page_the_search_never_showed_is_not_read(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    planner = _Planner({"relevant_pages": ["示波器量測"], "done": True})
    evidence = _rounds(snapshot, planner)
    assert all(p.citation.wiki_page != ZH_PAGE for p in evidence)


def test_a_failed_planner_keeps_the_first_retrieval(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    evidence = _rounds(snapshot, _Planner(None))
    first = _first(snapshot)
    assert {(p.citation.wiki_page, p.citation.raw_ref, p.citation.section) for p in evidence} == {
        (p.citation.wiki_page, p.citation.raw_ref, p.citation.section) for p in first
    }


def test_the_round_budget_bounds_planner_calls(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)  # reads the Vault lazily, on first search
    words = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot")
    for word in words:  # every search finds a page not seen before
        (tmp_path / "wiki" / "concepts" / f"{word}.md").write_text(
            f"---\ntitle: {word}\n---\n# {word}\n\nThe {word} measurement note explains "
            "a calibration step in detail.\n",
            encoding="utf-8",
        )
    decisions: list[dict[str, object] | None] = [
        {"relevant_pages": [], "queries": [word]} for word in words
    ]
    planner = _Planner(*decisions)
    _rounds(snapshot, planner, rounds=2)
    assert len(planner.requests) == 3  # the first look plus two more rounds


def test_the_skill_round_budget_turns_the_rounds_on_in_the_capability(tmp_path: Path) -> None:
    import asyncio

    from test_knowledge_wiki_primary import ASSET, _Catalog, _procedure

    from capabilities.knowledge_query.handlers import KnowledgeQueryHandler
    from common.execution import RequestContext

    class _Model(_Planner):
        def generate(self, request: ModelRequest) -> ModelResponse:
            if request.messages[0].text == PLANNER_PROMPT:
                return super().generate(request)
            self.requests.append(request)
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                text="No passage answers this.",
            )

    snapshot_vault = _snapshot(tmp_path)
    for rounds, planned in ((0, 0), (1, 1)):
        model = _Model({"relevant_pages": [], "done": True})
        handler = KnowledgeQueryHandler(_Catalog(snapshot_vault._vault), model, alias="a")  # type: ignore[arg-type]
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
            "procedure": _procedure(retrieval_rounds=rounds).model_dump(mode="json"),
        }
        try:
            asyncio.run(handler(context, request))  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 - only the planner calls matter here
            pass
        assert sum(1 for r in model.requests if r.messages[0].text == PLANNER_PROMPT) == planned


def test_the_skill_sets_how_many_sections_of_a_relevant_page_are_read(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)  # reads the Vault lazily
    (tmp_path / "wiki" / "concepts" / "示波器量測.md").write_text(
        "---\ntitle: 示波器量測\n---\n# 示波器量測\n\n示波器眼圖量測用於高速訊號完整性驗證，"
        "包含抖動、上升時間與眼高眼寬的判讀。\n\n## 抖動\n\n示波器抖動分析拆解隨機抖動與"
        "確定性抖動，用於高速串列介面的眼圖餘裕判讀。\n",
        encoding="utf-8",
    )
    for per_page, expected in ((1, 1), (3, 2)):
        planner = _Planner(
            {"relevant_pages": [], "queries": ["示波器 眼圖 抖動"]},
            {"relevant_pages": ["示波器量測"], "done": True},
        )
        evidence = search_rounds(
            snapshot,
            planner,
            "a",
            TRACE,
            "示波器 抖動",
            _first(snapshot),
            rounds=2,
            per_page=per_page,
        )
        assert sum(1 for p in evidence if p.citation.wiki_page == ZH_PAGE) == expected


def _deep_pages(tmp_path: Path) -> None:
    for name in ("alpha", "bravo"):
        sections = "".join(
            f"\n\n## {name} part {n}\n\nThe {name} jitter note {n} explains a calibration "
            "step of the oscilloscope in detail."
            for n in range(1, 7)
        )
        (tmp_path / "wiki" / "concepts" / f"{name}.md").write_text(
            f"---\ntitle: {name}\n---\n# {name}{sections}\n", encoding="utf-8"
        )


def test_every_relevant_page_gives_its_best_sections_before_any_goes_deeper(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    _deep_pages(tmp_path)
    planner = _Planner(
        {"relevant_pages": [], "queries": ["alpha jitter", "bravo jitter"]},
        {"relevant_pages": ["alpha", "bravo"], "done": True},
    )
    evidence = search_rounds(
        snapshot,
        planner,
        "a",
        TRACE,
        "jitter",
        _first(snapshot),
        rounds=2,
        k=6,
        per_page=8,
    )
    pages = [p.citation.wiki_page for p in evidence if p.citation.kind == "wiki"]
    assert pages.count("wiki/concepts/alpha.md") == 3
    assert pages.count("wiki/concepts/bravo.md") == 3


def test_relevant_page_sections_are_ranked_by_the_rank_text(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    _deep_pages(tmp_path)
    planner = _Planner(
        {"relevant_pages": [], "queries": ["alpha jitter"]},
        {"relevant_pages": ["alpha"], "done": True},
    )
    evidence = search_rounds(
        snapshot,
        planner,
        "a",
        TRACE,
        "jitter",
        _first(snapshot),
        rounds=2,
        k=1,
        per_page=8,
        rank_text="jitter note 5",
    )
    assert "alpha part 5" in evidence[0].text
