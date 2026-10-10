"""Convert, ingest and lint inside a personal sandbox (K1, owner 2026-10-11).

`docs/phases/KNOWLEDGE_K1.md`. Every step names a sandbox; nothing here writes
to a base vault. Ingest uses the sandbox vault's own schema file (`CLAUDE.md`,
the Karpathy LLM Wiki schema) as the planner's conventions when it has one,
and the built-in conventions otherwise. A plan is stored in the sandbox and
applied only while the Raw document and the pages it touches are unchanged.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from common.base import Contract
from knowledge.conflicts import decisions_text
from knowledge.lint import scan
from knowledge.planning import DEFAULT_CONVENTIONS, IngestPlanner
from knowledge.raw import (
    Describer,
    DropIntake,
    Extractor,
    MarkdownExtractor,
    PlainTextExtractor,
    RawIndex,
    load_document,
)
from knowledge.sandbox import Sandboxes, SandboxInfo
from knowledge.vault import Vault, WritePlan, normalize
from models.contracts import ModelClient

SCHEMA_FILE = "CLAUDE.md"
PLANS = ".plans"
MAX_FINDINGS = 50
# One dropped original; the Agent Web upload limit is smaller.
MAX_DROP_BYTES = 50 * 1024 * 1024


class PipelineError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ConvertItem(Contract):
    path: str
    status: str
    raw_ref: str | None = None
    images: int = Field(default=0, ge=0)
    described: int = Field(default=0, ge=0)


class ConvertResult(Contract):
    sandbox_id: str
    mode: Literal["dry_run", "apply"]
    items: tuple[ConvertItem, ...] = ()


class PagePreview(Contract):
    path: str
    change: Literal["new", "changed"]
    chars: int = Field(ge=0)


class IngestPlanResult(Contract):
    sandbox_id: str
    raw_ref: str
    status: str
    plan_id: str | None = None
    summary: str = ""
    pages: tuple[PagePreview, ...] = ()
    index_entries: int = 0
    contradictions: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()
    failure_code: str | None = None
    schema_source: Literal["vault", "built_in"] = "built_in"


class IngestApplyResult(Contract):
    sandbox_id: str
    plan_id: str
    status: Literal["applied", "rejected"]
    written: tuple[str, ...] = ()
    backed_up: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()


class PlanRecord(Contract):
    plan_id: str
    raw_ref: str


class SandboxContents(Contract):
    sandbox_id: str
    drop: tuple[str, ...] = ()
    raw: tuple[str, ...] = ()
    plans: tuple[PlanRecord, ...] = ()


class LintSummary(Contract):
    sandbox_id: str
    pages: int
    clean: bool
    counts: dict[str, int] = Field(default_factory=dict)
    findings: tuple[str, ...] = ()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class KnowledgePipeline:
    def __init__(
        self,
        sandboxes: Sandboxes,
        bases: dict[str, Path],
        *,
        extractors: tuple[Extractor, ...] = (),
        model: ModelClient | None = None,
        alias: str | None = None,
        describer: Describer | None = None,
    ) -> None:
        self.sandboxes = sandboxes
        self.bases = dict(bases)
        self.extractors: tuple[Extractor, ...] = (
            PlainTextExtractor(), MarkdownExtractor(), *extractors)
        self.model = model
        self.alias = alias
        self.describer = describer

    # -- sandboxes -----------------------------------------------------------

    def create_sandbox(self, base: str, label: str, actor: str) -> SandboxInfo:
        if base not in self.bases:
            raise PipelineError("unknown_base_vault")
        return self.sandboxes.create(base, self.bases[base], label=label, actor=actor)

    def _open(self, sandbox_id: str) -> Vault:
        return self.sandboxes.open(sandbox_id)[1]

    def discard_sandbox(self, sandbox_id: str) -> None:
        self.sandboxes.discard(sandbox_id)

    def add_drop(self, sandbox_id: str, name: str, data: bytes) -> str:
        """Put one original into the sandbox's drop/; never replaces a file."""
        vault = self._open(sandbox_id)
        clean = normalize(f"drop/{name}")
        target = (vault.root / clean).resolve()
        drop = (vault.root / "drop").resolve()
        if not name.strip() or drop not in target.parents:
            raise PipelineError("outside_drop")
        if len(data) > MAX_DROP_BYTES:
            raise PipelineError("drop_too_large")
        if target.exists():
            raise PipelineError("drop_exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return clean

    def contents(self, sandbox_id: str) -> SandboxContents:
        vault = self._open(sandbox_id)
        drop = tuple(p.relative_to(vault.root).as_posix()
                     for p in sorted((vault.root / "drop").rglob("*")) if p.is_file())
        raw = tuple(sorted(e.raw_ref for e in RawIndex.scan(vault).entries))
        plans = []
        for path in sorted((vault.root / PLANS).glob("plan-*.json")):
            stored = json.loads(path.read_text(encoding="utf-8"))
            plans.append(PlanRecord(plan_id=stored["plan_id"], raw_ref=stored["raw_ref"]))
        return SandboxContents(sandbox_id=sandbox_id, drop=drop, raw=raw, plans=tuple(plans))

    # -- convert -------------------------------------------------------------

    def convert(self, sandbox_id: str, paths: tuple[str, ...] = (),
                mode: Literal["dry_run", "apply"] = "dry_run") -> ConvertResult:
        vault = self._open(sandbox_id)
        drop = vault.root / "drop"
        wanted = paths or tuple(
            p.relative_to(vault.root).as_posix() for p in sorted(drop.rglob("*")) if p.is_file())
        intake = DropIntake(vault, self.extractors, self.describer)
        index = RawIndex.scan(vault)
        items = []
        for rel in wanted:
            clean = normalize(rel)
            if not clean.startswith("drop/"):
                raise PipelineError("outside_drop")
            outcome = intake.intake(clean, mode=mode, index=index)
            items.append(ConvertItem(
                path=clean, status=outcome.status, raw_ref=outcome.raw_ref,
                images=outcome.images_to_describe,
                described=sum(1 for d in outcome.descriptions if d.status == "described")))
        return ConvertResult(sandbox_id=sandbox_id, mode=mode, items=tuple(items))

    # -- ingest --------------------------------------------------------------

    def _conventions(self, vault: Vault) -> tuple[str, Literal["vault", "built_in"]]:
        schema = vault.read(SCHEMA_FILE).strip()
        return (schema, "vault") if schema else (DEFAULT_CONVENTIONS, "built_in")

    def plan_ingest(self, sandbox_id: str, raw_ref: str) -> IngestPlanResult:
        if self.model is None or self.alias is None:
            raise PipelineError("no_model")
        vault = self._open(sandbox_id)
        entry = next((e for e in RawIndex.scan(vault).entries if e.raw_ref == normalize(raw_ref)),
                     None)
        if entry is None:
            raise PipelineError("unknown_raw")
        conventions, schema_source = self._conventions(vault)
        planner = IngestPlanner(self.model, vault, alias=self.alias, conventions=conventions)
        outcome = planner.plan(load_document(vault, entry), today=date.today().isoformat(),
                               decisions=decisions_text(vault))
        base = IngestPlanResult(sandbox_id=sandbox_id, raw_ref=entry.raw_ref,
                                status=outcome.status, schema_source=schema_source,
                                problems=tuple(p.code for p in outcome.problems),
                                failure_code=outcome.failure.code if outcome.failure else None)
        if outcome.plan is None or outcome.status != "planned":
            return base
        plan = outcome.plan
        plan_id = f"plan-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
        touched = {normalize(p.path): _sha(vault.read(p.path)) for p in plan.pages
                   if vault.exists(p.path)}
        folder = vault.root / PLANS
        folder.mkdir(exist_ok=True)
        (folder / f"{plan_id}.json").write_text(json.dumps({
            "plan_id": plan_id, "raw_ref": entry.raw_ref, "raw_sha256": entry.source.sha256,
            "touched": touched, "plan": json.loads(plan.model_dump_json())},
            ensure_ascii=False), encoding="utf-8")
        pages = tuple(PagePreview(path=normalize(p.path),
                                  change="changed" if normalize(p.path) in touched else "new",
                                  chars=len(p.content)) for p in plan.pages)
        return base.model_copy(update={
            "plan_id": plan_id, "summary": plan.summary, "pages": pages,
            "index_entries": len(plan.index_entries), "contradictions": plan.contradictions})

    def apply_ingest(self, sandbox_id: str, plan_id: str) -> IngestApplyResult:
        vault = self._open(sandbox_id)
        if not plan_id.startswith("plan-") or "/" in plan_id or "\\" in plan_id:
            raise PipelineError("unknown_plan")
        stored_path = vault.root / PLANS / f"{plan_id}.json"
        if not stored_path.is_file():
            raise PipelineError("unknown_plan")
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        entry = next((e for e in RawIndex.scan(vault).entries if e.raw_ref == stored["raw_ref"]),
                     None)
        stale = entry is None or entry.source.sha256 != stored["raw_sha256"] or any(
            _sha(vault.read(path)) != digest for path, digest in stored["touched"].items())
        if stale:
            return IngestApplyResult(sandbox_id=sandbox_id, plan_id=plan_id, status="rejected",
                                     problems=("stale_plan",))
        outcome = vault.apply(WritePlan.model_validate(stored["plan"]), mode="apply")
        if outcome.problems:
            return IngestApplyResult(sandbox_id=sandbox_id, plan_id=plan_id, status="rejected",
                                     problems=tuple(p.code for p in outcome.problems))
        return IngestApplyResult(sandbox_id=sandbox_id, plan_id=plan_id, status="applied",
                                 written=outcome.written, backed_up=outcome.backed_up)

    # -- lint ----------------------------------------------------------------

    def lint(self, sandbox_id: str) -> LintSummary:
        report = scan(self._open(sandbox_id))
        counts = {
            "orphans": len(report.orphans), "dangling": len(report.dangling),
            "path_links": len(report.path_links),
            "missing_frontmatter": len(report.missing_frontmatter),
            "broken_source_path": len(report.broken_source_path),
            "unknown_source_id": len(report.unknown_source_id),
            "pending_sources": len(report.pending_sources),
            "open_conflicts": len(report.open_conflicts), "unreadable": len(report.unreadable)}
        findings = [
            *(f"open conflict: {c.page}:{c.line}: {c.text}" for c in report.open_conflicts),
            *(f"dangling link: [[{d.target}]] ({d.count}x)" for d in report.dangling),
            *(f"missing frontmatter: {p}" for p in report.missing_frontmatter),
            *(f"pending source: {p}" for p in report.pending_sources),
            *(f"orphan: {p}" for p in report.orphans)]
        return LintSummary(sandbox_id=sandbox_id, pages=report.pages, clean=report.clean,
                           counts=counts, findings=tuple(findings[:MAX_FINDINGS]))
