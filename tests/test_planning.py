"""Ingest planning: two passes through the model interface, condensation cached
by content, the answer repaired where mechanical and validated by the vault."""

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from test_raw import make_vault

from common.execution import Failure
from knowledge.planning import (
    PLAN_CONTRACT,
    RELEVANCE_CONTRACT,
    IngestPlanner,
    ensure_provenance,
    extract_json,
    source_text,
)
from knowledge.raw import RawDocument, RawSection, source_for
from knowledge.vault import PlannedPage, Vault, WritePlan, provenance_lines
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

TODAY = date(2026, 9, 21)


def document(text: str = "MCP is a protocol for tools.", **changes: Any) -> RawDocument:
    source = source_for(text.encode(), "drop/notes/mcp.md").model_copy(
        update={"raw_ref": "raw/notes/mcp.md"}
    )
    data: dict[str, Any] = {
        "source": source,
        "extractor": "markdown.v1",
        "created": TODAY,
        "sections": (RawSection(text=text),),
    }
    data.update(changes)
    return RawDocument.model_validate(data)


def good_plan_json(source_page_extra: str = "") -> dict[str, Any]:
    return {
        "summary": "Adds the MCP source and an entity page.",
        "pages": [
            {
                "path": "wiki/sources/MCP notes.md",
                "action": "create",
                "content": (
                    f"---\ntitle: MCP notes\ntype: source\n{source_page_extra}---\nSee [[MCP]].\n"
                ),
            },
            {
                "path": "wiki/entities/MCP.md",
                "action": "update",
                "content": "---\ntitle: MCP\ntype: entity\n---\nMCP is a protocol for tools.\n",
            },
        ],
        "index_entries": [{"section": "Sources", "line": "- [[MCP notes]] — the MCP source."}],
        "log_body": "- Source: raw/notes/mcp.md.",
        "contradictions": [],
        "ignored_extra_key": True,
    }


class PlanningModel:
    """Answers each pass from a table keyed by output contract; condensation
    answers with a tag so the test can see which chunk was condensed."""

    def __init__(self, answers: dict[str, Any] | None = None, *, as_text: bool = False) -> None:
        self.requests: list[ModelRequest] = []
        self.answers: dict[str, Any] = answers if answers is not None else {}
        self.as_text = as_text
        self.fail_on: str | None = None

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.fail_on and request.output_contract == self.fail_on:
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                failure=Failure(code="model_unavailable", message="down"),
            )
        if request.output_contract is None:
            n = request.trace.request_id.rsplit("-", 1)[1]
            return ModelResponse(
                trace=request.trace, model_alias=request.model_alias, text=f"condensed part {n}"
            )
        answer = self.answers.get(request.output_contract)
        if self.as_text:
            import json

            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                text=f"Here you go:\n```json\n{json.dumps(answer)}\n```",
            )
        return ModelResponse(
            trace=request.trace, model_alias=request.model_alias, structured_output=answer
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def wiki(vault: Vault) -> None:
    root = vault.root
    (root / "wiki" / "entities").mkdir(parents=True, exist_ok=True)
    (root / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (root / "wiki" / "entities" / "MCP.md").write_text(
        "---\ntitle: MCP\ntype: entity\n---\nOld text.\n", encoding="utf-8"
    )
    (root / "wiki" / "concepts" / "Tool use.md").write_text(
        "---\ntitle: Tool use\n---\nConcept.\n", encoding="utf-8"
    )
    (root / "wiki" / "concepts" / "untitled.md").write_text("no frontmatter\n", encoding="utf-8")
    (root / "index.md").write_text("# Index\n\n## Sources\n\n## Entities\n", encoding="utf-8")


def test_source_text_reads_sections_in_order_with_images_in_place() -> None:
    doc = document(
        sections=(
            RawSection(text="Intro", page=1),
            RawSection(kind="image", image_ref="raw/notes/mcp/assets/a.png", page=1),
            RawSection(
                kind="image",
                image_ref="raw/notes/mcp/assets/b.png",
                text="A diagram",
                slide=2,
                described_by="v",
            ),
            RawSection(kind="table", text="| a |\n| --- |"),
        )
    )
    assert source_text(doc) == (
        "Intro\n\n[image on page 1: (no description)]\n\n"
        "[image on slide 2: A diagram]\n\n| a |\n| --- |"
    )


def test_json_is_extracted_from_fences_and_prose() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": [1, 2]} hope that helps') == {"a": [1, 2]}
    assert extract_json(' {"a": 1} ') == {"a": 1}
    with pytest.raises(ValueError):
        extract_json("not json at all")


def test_provenance_lines_are_repaired_into_the_sources_page() -> None:
    doc = document()
    plan = WritePlan(
        source=doc.source,
        pages=(
            PlannedPage(
                path="wiki/sources/A.md", action="create", content="---\ntitle: A\n---\nbody\n"
            ),
            PlannedPage(path="wiki/sources/B.md", action="create", content="no frontmatter\n"),
            PlannedPage(path="wiki/entities/C.md", action="create", content="---\ntitle: C\n---\n"),
        ),
    )
    repaired = ensure_provenance(plan)
    id_line, sha_line = provenance_lines(doc.source)
    assert repaired.pages[0].content == f"---\ntitle: A\n{id_line}\n{sha_line}\n---\nbody\n"
    assert repaired.pages[1].content == f"---\n{id_line}\n{sha_line}\n---\nno frontmatter\n"
    assert repaired.pages[2] == plan.pages[2]
    # Already correct pages are untouched; stale identity lines are replaced.
    stale = plan.pages[0].model_copy(
        update={"content": f"---\nsource_id: old\nsource_sha256: {'f' * 64}\ntitle: A\n---\n"}
    )
    fixed = ensure_provenance(plan.model_copy(update={"pages": (stale,)})).pages[0].content
    assert fixed == f"---\ntitle: A\n{id_line}\n{sha_line}\n---\n"
    assert ensure_provenance(repaired) == repaired


def test_two_passes_produce_a_plan_the_vault_accepts(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    wiki(vault)
    model = PlanningModel(
        {
            RELEVANCE_CONTRACT: {
                "relevant": ["wiki/entities/MCP.md", "wiki/nope.md", 7, "wiki/concepts/Tool use.md"]
            },
            PLAN_CONTRACT: good_plan_json(),
        }
    )
    planner = IngestPlanner(model, vault, alias="planner")
    outcome = planner.plan(
        document(), today="2026-09-21", decisions="## [2026-09-01] Skills\n- keep: x"
    )
    assert outcome.status == "planned" and outcome.problems == ()
    assert outcome.relevant == ("wiki/entities/MCP.md", "wiki/concepts/Tool use.md")
    assert outcome.condensed is False and outcome.cache_hit is False
    assert outcome.plan is not None and outcome.plan.summary.startswith("Adds")

    relevance, plan = model.requests
    assert relevance.output_contract == RELEVANCE_CONTRACT
    assert relevance.requirements.structured_output is True and relevance.model_alias == "planner"
    assert relevance.messages[0].role == "system"
    assert "[[Page Name]]" in relevance.messages[0].text
    assert "- wiki/entities/MCP.md — MCP" in relevance.messages[1].text
    assert "- wiki/concepts/untitled.md — untitled" in relevance.messages[1].text
    assert plan.output_contract == PLAN_CONTRACT and plan.trace.trace_id == relevance.trace.trace_id
    body = plan.messages[1].text
    assert "----- wiki/entities/MCP.md -----\n---\ntitle: MCP" in body and "Old text." in body
    assert "## [2026-09-01] Skills" in body and "# Index" in body and "Today is 2026-09-21" in body
    assert "MCP is a protocol for tools." in body

    # The provenance the model omitted was repaired in; the vault applies the plan as is.
    id_line, _ = provenance_lines(outcome.plan.source)
    assert id_line in outcome.plan.pages[0].content
    applied = vault.apply(outcome.plan, mode="apply", today=TODAY, stamp="s1")
    assert applied.accepted and vault.read("wiki/entities/MCP.md").endswith("for tools.\n")
    assert "- [[MCP notes]] — the MCP source." in vault.read("index.md")
    assert not (tmp_path / "raw" / "notes").exists()  # planning never writes raw


def test_answers_in_prose_are_parsed_and_invalid_plans_are_reported(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    wiki(vault)
    prose = PlanningModel(
        {RELEVANCE_CONTRACT: {"relevant": []}, PLAN_CONTRACT: good_plan_json()}, as_text=True
    )
    outcome = IngestPlanner(prose, vault, alias="p").plan(document(), today="2026-09-21")
    assert outcome.status == "planned" and outcome.relevant == ()
    assert "(no related pages)" in prose.requests[1].messages[1].text

    broken = good_plan_json()
    broken["pages"][1]["path"] = "raw/notes/mcp.md"
    broken["pages"].append({"path": "wiki/entities/X.md", "action": "create", "content": "[[a/b]]"})
    bad = PlanningModel({RELEVANCE_CONTRACT: {"relevant": []}, PLAN_CONTRACT: broken})
    outcome = IngestPlanner(bad, vault, alias="p").plan(document(), today="2026-09-21")
    assert outcome.status == "invalid" and outcome.plan is not None
    assert sorted(p.code for p in outcome.problems) == ["outside_wiki", "path_in_wikilink"]

    wrong_shape = PlanningModel(
        {RELEVANCE_CONTRACT: {"relevant": []}, PLAN_CONTRACT: {"pages": "x"}}
    )
    outcome = IngestPlanner(wrong_shape, vault, alias="p").plan(document(), today="2026-09-21")
    assert outcome.status == "unparseable" and outcome.failure is not None
    assert outcome.failure.code == "plan_shape" and outcome.plan is None

    class Prose(PlanningModel):
        def generate(self, request: ModelRequest) -> ModelResponse:
            self.requests.append(request)
            return ModelResponse(trace=request.trace, model_alias=request.model_alias, text="no")

    outcome = IngestPlanner(Prose(), vault, alias="p").plan(document(), today="2026-09-21")
    assert outcome.status == "unparseable" and outcome.failure is not None
    assert outcome.failure.code == "plan_unparseable"


def test_model_failures_are_statuses_on_either_pass(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    wiki(vault)
    model = PlanningModel({RELEVANCE_CONTRACT: {"relevant": []}, PLAN_CONTRACT: good_plan_json()})
    model.fail_on = RELEVANCE_CONTRACT
    outcome = IngestPlanner(model, vault, alias="p").plan(document(), today="2026-09-21")
    assert outcome.status == "model_failed" and outcome.failure is not None
    assert outcome.failure.code == "model_unavailable" and len(model.requests) == 1
    model.fail_on = PLAN_CONTRACT
    outcome = IngestPlanner(model, vault, alias="p").plan(document(), today="2026-09-21")
    assert outcome.status == "model_failed" and len(model.requests) == 3

    class Raising(PlanningModel):
        def generate(self, request: ModelRequest) -> ModelResponse:
            raise ConnectionError("refused")

    outcome = IngestPlanner(Raising(), vault, alias="p").plan(document(), today="2026-09-21")
    assert outcome.status == "model_failed" and outcome.failure is not None
    assert outcome.failure.code == "model_error" and outcome.failure.retryable is True
    with pytest.raises(ValueError, match="positive"):
        IngestPlanner(model, vault, alias="p", chunk_chars=0)


def test_long_sources_are_condensed_once_and_cached_by_content(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    wiki(vault)
    long_text = "word " * 3000  # 15,000 chars
    model = PlanningModel({RELEVANCE_CONTRACT: {"relevant": []}, PLAN_CONTRACT: good_plan_json()})
    planner = IngestPlanner(model, vault, alias="p", condense_over=10_000, chunk_chars=4_000)
    outcome = planner.plan(document(long_text), today="2026-09-21")
    assert outcome.status == "planned" and outcome.condensed and not outcome.cache_hit
    condense_requests = [r for r in model.requests if r.output_contract is None]
    assert len(condense_requests) == 4  # 15,000 / 4,000 rounded up
    assert condense_requests[0].requirements.structured_output is False
    assert [r.trace.request_id for r in condense_requests] == [
        f"condense-{n}" for n in (1, 2, 3, 4)
    ]
    assert "condensed part 4" in model.requests[-1].messages[1].text
    cache = tmp_path / ".ingest-cache" / f"{document(long_text).source.sha256}.md"
    assert cache.is_file() and "condensed part 1" in cache.read_text(encoding="utf-8")

    # A second planner (new process) reuses the cache: no condensation calls.
    fresh = PlanningModel({RELEVANCE_CONTRACT: {"relevant": []}, PLAN_CONTRACT: good_plan_json()})
    again = IngestPlanner(fresh, vault, alias="p", condense_over=10_000, chunk_chars=4_000)
    outcome = again.plan(document(long_text), today="2026-09-21")
    assert outcome.condensed and outcome.cache_hit and len(fresh.requests) == 2
    # A condensation failure part-way is a status and leaves no partial cache.
    failing = PlanningModel({RELEVANCE_CONTRACT: {"relevant": []}, PLAN_CONTRACT: good_plan_json()})

    class FailsCondensing(PlanningModel):
        def generate(self, request: ModelRequest) -> ModelResponse:
            if request.output_contract is None:
                return ModelResponse(
                    trace=request.trace,
                    model_alias=request.model_alias,
                    failure=Failure(code="model_unavailable", message="down"),
                )
            return super().generate(request)

    other = document("other " * 3000)
    outcome = IngestPlanner(
        FailsCondensing(failing.answers), vault, alias="p", condense_over=10_000, chunk_chars=4_000
    ).plan(other, today="2026-09-21")
    assert outcome.status == "model_failed"
    assert not (tmp_path / ".ingest-cache" / f"{other.source.sha256}.md").exists()


def test_the_cache_is_confined_and_keyed_by_hash(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    assert vault.cache_read("a" * 64) is None
    vault.cache_write("a" * 64, "text")
    assert vault.cache_read("a" * 64) == "text"
    assert (tmp_path / ".ingest-cache" / f"{'a' * 64}.md").read_text(encoding="utf-8") == "text"
    for bad in ("../x", "short", "A" * 64, "a" * 63 + "/"):
        with pytest.raises(ValueError, match="content hash"):
            vault.cache_write(bad, "x")
        with pytest.raises(ValueError, match="content hash"):
            vault.cache_read(bad)
    assert vault.wiki_pages() == ()
