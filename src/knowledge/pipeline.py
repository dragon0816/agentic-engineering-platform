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
import re
import shutil
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from common.base import Contract
from knowledge.conflicts import decisions_text
from knowledge.evolution import knowledge_digest
from knowledge.layered_index import KEYS, EnrichReport, IndexReport, LayeredIndex, read_entry
from knowledge.lint import scan
from knowledge.merge import (
    ROOT_FILES,
    TEXT_AREAS,
    MergeChange,
    MergeConflict,
    Resolution,
    read_tree,
    three_way,
)
from knowledge.migrate import adopt
from knowledge.planning import DEFAULT_CONVENTIONS, IngestPlanner
from knowledge.progress import reporter
from knowledge.questions import category as question_category
from knowledge.questions import default_sets, set_categories
from knowledge.questions import load as load_questions
from knowledge.questions import sets as question_set_counts
from knowledge.raw import (
    Describer,
    DropIntake,
    Extractor,
    MarkdownExtractor,
    PlainTextExtractor,
    RawIndex,
    load_document,
)
from knowledge.sandbox import BASE, Sandboxes, SandboxInfo
from knowledge.schema import front_fields, ingest_conventions
from knowledge.sections import like_endings, lost_lines
from knowledge.vault import Vault, WritePlan, normalize
from models.contracts import ModelClient

PLANS = ".plans"
MAX_FINDINGS = 50
# One dropped original; the Agent Web upload limit is smaller.
MAX_DROP_BYTES = 50 * 1024 * 1024
# A plan writes every page in full; 8,000 tokens truncated a 12-slide deck
# (K1.5 live run, 2026-10-11).
PLAN_MAX_OUTPUT_TOKENS = 16000


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
    # The category rules (skills/<name>/SKILL.md) added for this source, if any.
    skill: str | None = None


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


class AdoptSummary(Contract):
    sandbox_id: str
    mode: Literal["dry_run", "apply"]
    raw_adopted: int = 0
    raw_drifted: int = 0
    raw_skipped: int = 0
    pages_migrated: int = 0
    pages_unresolved: int = 0
    written: int = 0


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
        drop_roots: dict[str, Path] | None = None,
        questions_roots: dict[str, Path] | None = None,
        maintainers: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.sandboxes = sandboxes
        self.bases = dict(bases)
        # Where each project vault collects originals; default <vault>/drop.
        self.drop_roots = {name: (drop_roots or {}).get(name, root / "drop")
                           for name, root in self.bases.items()}
        self.maintainers = dict(maintainers or {})
        # Where each project vault keeps its question sets; default checks/questions.
        self.questions_roots = {
            name: (questions_roots or {}).get(name, root / "checks" / "questions")
            for name, root in self.bases.items()}
        self.extractors: tuple[Extractor, ...] = (
            PlainTextExtractor(), MarkdownExtractor(), *extractors)
        self.model = model
        self.alias = alias
        self.describer = describer

    # -- sandboxes -----------------------------------------------------------

    def create_sandbox(self, base: str, label: str, actor: str,
                       domain: str | None = None, scope: str | None = None,
                       progress_key: str | None = None) -> SandboxInfo:
        if base not in self.bases:
            raise PipelineError("unknown_base_vault")
        if domain is not None and domain not in KEYS:
            raise PipelineError("unknown_domain")
        if scope is not None:
            scope = self._scope(base, scope)
        return self.sandboxes.create(base, self.bases[base], label=label, actor=actor,
                                     domain=domain, scope=scope,
                                     progress=reporter(progress_key))

    def _scope(self, base: str, scope: str) -> str:
        """A folder the project vault collects (drop/) or holds (raw/)."""
        rel = normalize(scope).strip("/")
        if not rel or ".." in rel.split("/"):
            raise PipelineError("bad_scope")
        if not ((self.drop_roots[base] / rel).is_dir()
                or (self.bases[base] / "raw" / rel).is_dir()):
            raise PipelineError("unknown_scope")
        return rel

    def _open(self, sandbox_id: str) -> Vault:
        return self.sandboxes.open(sandbox_id)[1]

    def discard_sandbox(self, sandbox_id: str) -> None:
        self.sandboxes.discard(sandbox_id)

    # -- pull (collaboration design section 3) --------------------------------

    def drop_folders(self, base: str, depth: int = 3) -> DropFolders:
        """The project vault's drop/ folders a sandbox may pull, with file counts."""
        if base not in self.bases:
            raise PipelineError("unknown_base_vault")
        root = self.drop_roots[base]
        found = []
        if root.is_dir():
            for folder in sorted(p for p in root.rglob("*") if p.is_dir()):
                rel = folder.relative_to(root)
                if len(rel.parts) <= depth and not any(x.startswith(".") for x in rel.parts):
                    files = sum(1 for p in folder.rglob("*") if p.is_file())
                    found.append(DropFolder(path=rel.as_posix(), files=files))
        return DropFolders(base=base, folders=tuple(found))

    def pull(self, sandbox_id: str, folders: tuple[str, ...],
             progress_key: str | None = None) -> PullResult:
        """Copy the chosen drop/ folders of the project vault into the sandbox's
        drop/, keeping their paths. An original already ingested (same content
        hash) or already in the sandbox is skipped; nothing is replaced. The Raw
        documents of skipped originals are named, since a rule change is tried
        by ingesting them again, not by pulling."""
        info, vault = self.sandboxes.open(sandbox_id)
        root = self.drop_roots[info.base_name].resolve()
        if (early := reporter(progress_key)) is not None:
            early("reading", 0, 0, "the sandbox's Raw index")
        known = {entry.source.sha256: entry.raw_ref for entry in RawIndex.scan(vault).entries}
        legacy = _legacy_source_shas(vault)
        copied: list[str] = []
        already: list[str] = []
        already_raw: list[str] = []
        present: list[str] = []
        large: list[str] = []
        clean_folders = []
        progress = reporter(progress_key)
        chosen: list[Path] = []
        for folder in folders:
            rel = normalize(folder).strip("/")
            source = (root / rel).resolve()
            if not rel or rel.startswith("..") or (source != root and root not in source.parents):
                raise PipelineError("outside_drop")
            if not source.is_dir():
                raise PipelineError("unknown_drop_folder")
            if info.scope is not None and not _within(rel, info.scope):
                raise PipelineError("outside_scope")
            clean_folders.append(rel)
            chosen.extend(p for p in sorted(source.rglob("*")) if p.is_file())
        originals = list(dict.fromkeys(chosen))  # nested folders name a file once
        for index, path in enumerate(originals, 1):
            name = path.relative_to(root).as_posix()
            if progress is not None:
                progress("pulling", index - 1, len(originals), name)
            data = path.read_bytes()
            target = vault.root / "drop" / name
            if len(data) > MAX_DROP_BYTES:
                large.append(name)
            elif (raw_ref := _raw_holding(hashlib.sha256(data).hexdigest(), known,
                                          legacy)) is not None:
                already.append(name)
                already_raw.append(raw_ref)
            elif target.exists():
                present.append(name)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                copied.append(name)
        if progress is not None:
            progress("pulling", len(originals), len(originals), "")
        pulled = tuple(dict.fromkeys((*info.pulled, *clean_folders)))
        self.sandboxes.record(info.model_copy(update={"pulled": pulled}))
        return PullResult(sandbox_id=sandbox_id, folders=pulled, copied=tuple(copied),
                          already_ingested=tuple(already),
                          already_raw=tuple(dict.fromkeys(already_raw)),
                          already_in_sandbox=tuple(present),
                          too_large=tuple(large))

    # -- files: preview and rule editing (collaboration C2) --------------------

    def rule_files(self, sandbox_id: str) -> RuleFiles:
        """The rules that concern the sandbox's scope: its folder's ingest and
        answer skills (editable), the more general layers it inherits and the
        vault-wide schema (read only). Other folders' skills are not listed.
        A sandbox without a scope (made before scopes) may edit every rule."""
        info, vault = self.sandboxes.open(sandbox_id)
        rules = []
        paths = [SCHEMA] if (vault.root / SCHEMA).is_file() else []
        paths += sorted(p.relative_to(vault.root).as_posix()
                        for p in (vault.root / "skills").glob("*/SKILL.md"))
        for rel in paths:
            fields = front_fields((vault.root / rel).read_text(encoding="utf-8", errors="ignore"))
            access = _rule_access(info.scope, rel, fields)
            if access is not None:
                rules.append(RuleFile(
                    path=rel, access=access, applies_to=fields.get("applies_to") or None,
                    kind="schema" if rel == SCHEMA else (
                        "answer" if fields.get("mode", "").casefold() == "answer"
                        or rel.startswith("skills/ask-") else "ingest")))
        return RuleFiles(sandbox_id=sandbox_id, scope=info.scope,
                         files=tuple(rule.path for rule in rules), rules=tuple(rules))

    def skill_guide(self) -> SkillGuide:
        """The writing guide and the two templates shipped with the platform."""
        folder = Path(__file__).parent / "skill_guide"
        return SkillGuide(
            guide=(folder / "GUIDE.zh-TW.md").read_text(encoding="utf-8"),
            ingest_template=(folder / "ingest.SKILL.md").read_text(encoding="utf-8"),
            answer_template=(folder / "answer.SKILL.md").read_text(encoding="utf-8"))

    def read_file(self, sandbox_id: str, path: str) -> SandboxFile:
        """One Markdown file of the sandbox, for preview."""
        vault = self._open(sandbox_id)
        rel = _readable(path)
        target = vault.root / rel
        if not target.is_file():
            raise PipelineError("unknown_file")
        data = target.read_bytes()
        if len(data) > MAX_PREVIEW_BYTES:
            raise PipelineError("file_too_large")
        # Shown and edited with LF; a save restores the file's own line endings.
        return SandboxFile(sandbox_id=sandbox_id, path=rel,
                           text=data.decode("utf-8").replace("\r\n", "\n"))

    def write_rule(self, sandbox_id: str, path: str, text: str) -> SandboxFile:
        """Save the schema or one skill file in the sandbox; nothing else is
        writable this way. The change reaches the project vault only by a push."""
        info, vault = self.sandboxes.open(sandbox_id)
        rel = normalize(path)
        question = _QUESTION_FILE.fullmatch(rel) is not None
        if not (rel == SCHEMA or _SKILL_FILE.fullmatch(rel) or question):
            raise PipelineError("not_a_rule_file")
        if not text.strip() or len(text.encode("utf-8")) > MAX_PREVIEW_BYTES:
            raise PipelineError("bad_rule_text")
        target = vault.root / rel
        if question:
            # A question set is edited by the sandbox whose folder it tests
            # (`market`, `market_production` for Market); the general set and
            # other folders' sets are not, so no one weakens another's gate.
            if _question_access(info.scope, rel) != "edit":
                raise PipelineError("rule_outside_scope")
            target.parent.mkdir(parents=True, exist_ok=True)
            original = target.read_bytes().decode("utf-8") if target.is_file() else ""
            target.write_bytes(like_endings(text, original).encode("utf-8"))
            return SandboxFile(sandbox_id=sandbox_id, path=rel, text=text)
        # Both the file as it is and as it would be must belong to the scope,
        # so applies_to cannot be moved onto another folder's data either.
        current = (target.read_text(encoding="utf-8", errors="ignore")
                   if target.is_file() else text)
        if (_rule_access(info.scope, rel, front_fields(current)) != "edit"
                or _rule_access(info.scope, rel, front_fields(text)) != "edit"):
            raise PipelineError("rule_outside_scope")
        target.parent.mkdir(parents=True, exist_ok=True)
        original = target.read_bytes().decode("utf-8") if target.is_file() else ""
        target.write_bytes(like_endings(text, original).encode("utf-8"))
        return SandboxFile(sandbox_id=sandbox_id, path=rel, text=text)

    def plan_page(self, sandbox_id: str, plan_id: str, path: str) -> PlanPage:
        """A planned page before and after, so the person sees what an apply
        would change before applying it."""
        vault = self._open(sandbox_id)
        if not plan_id.startswith("plan-") or "/" in plan_id or "\\" in plan_id:
            raise PipelineError("unknown_plan")
        stored_path = vault.root / PLANS / f"{plan_id}.json"
        if not stored_path.is_file():
            raise PipelineError("unknown_plan")
        plan = json.loads(stored_path.read_text(encoding="utf-8"))["plan"]
        rel = normalize(path)
        page = next((p for p in plan["pages"] if normalize(p["path"]) == rel), None)
        if page is None:
            raise PipelineError("unknown_file")
        return PlanPage(sandbox_id=sandbox_id, plan_id=plan_id, path=rel,
                        before=vault.read(rel), after=page["content"].replace("\r\n", "\n"))

    def question_sets(self, sandbox_id: str) -> QuestionSets:
        """The sandbox's question sets with counts, the ones its pulled scope
        selects by default, and questions that have no terms to grade."""
        info, vault = self.sandboxes.open(sandbox_id)
        root = vault.root / "checks" / "questions"
        found = load_questions(root if root.is_dir() else self.questions_roots[info.base_name])
        counts = question_set_counts(found)
        scope = (info.scope,) if info.scope else info.pulled
        return QuestionSets(
            sandbox_id=sandbox_id, sets=counts, defaults=default_sets(counts, scope),
            ungraded=tuple(q.path for q in found if not (q.must or q.must_not)),
            questions=tuple(QuestionItem(
                path=f"checks/questions/{q.path}", set=q.set, text=q.text, must=len(q.must),
                must_not=len(q.must_not),
                editable=_question_access(info.scope, f"checks/questions/{q.path}") == "edit")
                for q in found))

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
                mode: Literal["dry_run", "apply"] = "dry_run",
                progress_key: str | None = None) -> ConvertResult:
        vault = self._open(sandbox_id)
        drop = vault.root / "drop"
        wanted = paths or tuple(
            p.relative_to(vault.root).as_posix() for p in sorted(drop.rglob("*")) if p.is_file())
        intake = DropIntake(vault, self.extractors, self.describer)
        index = RawIndex.scan(vault)
        items = []
        progress = reporter(progress_key)
        for number, rel in enumerate(wanted, 1):
            clean = normalize(rel)
            if not clean.startswith("drop/"):
                raise PipelineError("outside_drop")
            if progress is not None:
                progress("converting", number - 1, len(wanted), clean)

            def image(done: int, total: int, name: str = clean) -> None:
                if progress is not None:
                    progress("describing", done, total, name)

            outcome = intake.intake(clean, mode=mode, index=index, on_image=image)
            items.append(ConvertItem(
                path=clean, status=outcome.status, raw_ref=outcome.raw_ref,
                images=outcome.images_to_describe,
                described=sum(1 for d in outcome.descriptions if d.status == "described")))
        return ConvertResult(sandbox_id=sandbox_id, mode=mode, items=tuple(items))

    # -- ingest --------------------------------------------------------------

    def plan_ingest(self, sandbox_id: str, raw_ref: str) -> IngestPlanResult:
        if self.model is None or self.alias is None:
            raise PipelineError("no_model")
        vault = self._open(sandbox_id)
        entry = next((e for e in RawIndex.scan(vault).entries if e.raw_ref == normalize(raw_ref)),
                     None)
        if entry is None:
            raise PipelineError("unknown_raw")
        rules = ingest_conventions(vault, entry.raw_ref, DEFAULT_CONVENTIONS)
        planner = IngestPlanner(self.model, vault, alias=self.alias, conventions=rules.text,
                                max_output_tokens=PLAN_MAX_OUTPUT_TOKENS)
        outcome = planner.plan(load_document(vault, entry), today=date.today().isoformat(),
                               decisions=decisions_text(vault))
        base = IngestPlanResult(sandbox_id=sandbox_id, raw_ref=entry.raw_ref,
                                status=outcome.status, schema_source=rules.schema_source,
                                skill=rules.skill,
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

    # -- layered index (K2) ----------------------------------------------------

    def index_enrich(self, sandbox_id: str, limit: int = 60) -> EnrichReport:
        """Bilingual aliases, summary and categories for up to `limit` pages not
        yet enriched; call again until `remaining` is 0."""
        if self.model is None or self.alias is None:
            raise PipelineError("no_model")
        return LayeredIndex(self._open(sandbox_id), self.model, self.alias).enrich(limit=limit)

    def index_build(self, sandbox_id: str,
                    mode: Literal["dry_run", "apply"] = "dry_run") -> IndexReport:
        return LayeredIndex(self._open(sandbox_id)).build(mode=mode)

    # -- adopt ---------------------------------------------------------------

    def adopt(self, sandbox_id: str,
              mode: Literal["dry_run", "apply"] = "dry_run") -> AdoptSummary:
        """Adopt Raw written by earlier tooling (no platform provenance) so it can
        be ingested: a ledger records each file's content hash; Raw bytes stay
        untouched (knowledge.migrate)."""
        vault = self._open(sandbox_id)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        report = adopt(vault, mode=mode, today=date.today(), stamp=stamp)
        return AdoptSummary(
            sandbox_id=sandbox_id, mode=mode, raw_adopted=len(report.raw_adopted),
            raw_drifted=len(report.raw_drifted), raw_skipped=len(report.raw_skipped),
            pages_migrated=len(report.pages_migrated),
            pages_unresolved=len(report.pages_unresolved), written=len(report.written))

    # -- lint ----------------------------------------------------------------

    # -- merge (K3.3) ----------------------------------------------------------

    def merge(self, sandbox_id: str, mode: Literal["dry_run", "apply"] = "dry_run",
              resolutions: dict[str, Resolution] | None = None) -> MergeReport:
        """Three-way merge of a sandbox into its base vault. A preview writes
        nothing; apply writes a new candidate vault beside the sandboxes, never
        the published vault, and refuses while a conflict is unresolved."""
        info, vault = self.sandboxes.open(sandbox_id)
        published = Vault(Path(info.base_root))
        snapshot = vault.root / BASE
        if snapshot.is_dir():
            base = read_tree(snapshot, raw=False)
        elif knowledge_digest(published) == info.base_content_sha256:
            base = read_tree(published.root, raw=False)  # published has not moved
        else:
            raise PipelineError("no_base_snapshot")
        sandbox_files = read_tree(vault.root)
        scope = None
        if info.domain is not None:
            scope = {rel for rel in sandbox_files if rel.startswith("wiki/") and rel.endswith(".md")
                     and info.domain in read_entry(vault, rel).categories}
        merged = three_way(base, sandbox_files, read_tree(published.root), resolutions, scope)
        report = MergeReport(
            sandbox_id=sandbox_id, mode=mode, base_name=info.base_name,
            changes=tuple(merged.changes), conflicts=tuple(merged.conflicts),
            kept_removed=tuple(merged.kept_removed))
        if mode == "dry_run":
            return report
        if merged.conflicts:
            raise PipelineError("unresolved_conflicts")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        target = (self.sandboxes.root / CANDIDATES
                  / f"{info.base_name}-{stamp}-{uuid.uuid4().hex[:4]}")
        shutil.copytree(published.root, target,
                        ignore=lambda _dir, names: [n for n in names if n in _CANDIDATE_SKIP])
        for rel, data in merged.files.items():
            path = target / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        candidate = Vault(target)
        lost = _lost_sourced(published, vault, candidate)
        before, after = _lint_counts(published), _lint_counts(candidate)
        worse = {key: after[key] - before.get(key, 0) for key in after
                 if after[key] > before.get(key, 0)}
        return report.model_copy(update={
            "candidate_root": str(target), "lost_sourced_lines": lost, "lint_worse": worse,
            "written": tuple(sorted(merged.files))})

    # -- push (collaboration C4) -----------------------------------------------

    def may_push(self, base: str, actor: str) -> bool:
        """Co-developers listed for the project may push; an empty list means
        whoever runs this Agent (OneDrive sharing still decides who can write)."""
        allowed = self.maintainers.get(base, ())
        return not allowed or actor in allowed

    def sync_after_push(self, sandbox_id: str) -> None:
        """After a push, the project vault holds the sandbox's work and possibly
        others'. The sandbox and its `.base` take the project's wiki, rules and
        root files, so work continues from the pushed state and a later merge
        never mistakes others' pushes for edits the sandbox undid."""
        info, vault = self.sandboxes.open(sandbox_id)
        project = self.bases[info.base_name]
        for target in (vault.root, vault.root / BASE):
            for area in TEXT_AREAS:
                if (target / area).exists():
                    shutil.rmtree(target / area)
                if (project / area).is_dir():
                    shutil.copytree(project / area, target / area)
            for name in ROOT_FILES:
                if (project / name).is_file():
                    target.mkdir(exist_ok=True)
                    shutil.copy2(project / name, target / name)

    def write_push(self, base: str, candidate_root: str, written: tuple[str, ...],
                   push_id: str) -> str:
        """Copy the merged files from the candidate into the project vault in
        place; every file replaced is backed up first under
        `.ingest-backup/<push id>/`. Returns the backup folder."""
        if base not in self.bases:
            raise PipelineError("unknown_base_vault")
        project = self.bases[base].resolve()
        candidate = Path(candidate_root).resolve()
        if candidate.parent != (self.sandboxes.root / CANDIDATES).resolve():
            raise PipelineError("not_a_candidate")
        backup = project / ".ingest-backup" / push_id
        for rel in written:
            clean = normalize(rel)
            source, target = (candidate / clean).resolve(), (project / clean).resolve()
            if candidate not in source.parents or project not in target.parents:
                raise PipelineError("outside_vault")
            if target.is_file():
                saved = backup / clean
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(target.read_bytes())
        for rel in written:
            clean = normalize(rel)
            target = project / clean
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((candidate / clean).read_bytes())
        return str(backup)

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


CANDIDATES = "candidates"
_CANDIDATE_SKIP = {".ingest-backup", ".ingest-snapshot", ".plans", ".condense-cache", ".git"}


class MergeReport(Contract):
    sandbox_id: str
    mode: Literal["dry_run", "apply"]
    base_name: str
    changes: tuple[MergeChange, ...] = ()
    conflicts: tuple[MergeConflict, ...] = ()
    kept_removed: tuple[str, ...] = ()
    candidate_root: str | None = None
    lost_sourced_lines: int = 0
    lint_worse: dict[str, int] = Field(default_factory=dict)
    written: tuple[str, ...] = ()  # the files a push copies into the project vault


def _lint_counts(vault: Vault) -> dict[str, int]:
    report = scan(vault)
    return {"path_links": len(report.path_links),
            "missing_frontmatter": len(report.missing_frontmatter),
            "broken_source_path": len(report.broken_source_path),
            "unknown_source_id": len(report.unknown_source_id),
            "unreadable": len(report.unreadable)}


def _lost_sourced(published: Vault, sandbox: Vault, candidate: Vault) -> int:
    """Sourced lines of either side that the candidate no longer carries."""
    titles = {title.casefold() for rel, title in candidate.wiki_pages()
              if rel.startswith("wiki/sources/")}
    lost = 0
    for side in (published, sandbox):
        for rel in side.wiki_files():
            if rel.endswith(".md") and candidate.exists(rel):
                lost += len(lost_lines(side.read(rel), candidate.read(rel), titles))
    return lost



class DropFolder(Contract):
    path: str
    files: int = Field(ge=0)


class DropFolders(Contract):
    base: str
    folders: tuple[DropFolder, ...] = ()


class PullResult(Contract):
    sandbox_id: str
    folders: tuple[str, ...] = ()  # every folder pulled so far: the sandbox's scope
    copied: tuple[str, ...] = ()
    already_ingested: tuple[str, ...] = ()
    # The Raw documents that hold the already-ingested originals.
    already_raw: tuple[str, ...] = ()
    already_in_sandbox: tuple[str, ...] = ()
    too_large: tuple[str, ...] = ()



SCHEMA = "CLAUDE.md"
MAX_PREVIEW_BYTES = 1024 * 1024
_SKILL_FILE = re.compile(r"skills/[A-Za-z0-9][A-Za-z0-9._-]*/SKILL\.md")
_QUESTION_FILE = re.compile(r"checks/questions/(?:[^/]+/)?[^/]+\.md")
_READABLE_AREAS = ("wiki/", "raw/", "skills/", "checks/")
_READABLE_FILES = (SCHEMA, "index.md", "log.md", "decisions.md")


def _readable(path: str) -> str:
    rel = normalize(path)
    if ".." in rel.split("/") or not rel.endswith(".md") or not (
            rel in _READABLE_FILES or rel.startswith(_READABLE_AREAS)):
        raise PipelineError("not_previewable")
    return rel


class RuleFile(Contract):
    path: str
    kind: Literal["schema", "ingest", "answer"]
    # edit: this scope's rule; inherited: a more general layer it builds on;
    # shared: the vault-wide schema. Only `edit` can be saved in the sandbox.
    access: Literal["edit", "inherited", "shared"]
    applies_to: str | None = None


class RuleFiles(Contract):
    sandbox_id: str
    scope: str | None = None
    files: tuple[str, ...] = ()
    rules: tuple[RuleFile, ...] = ()


def _question_access(scope: str | None, rel: str) -> Literal["edit"] | None:
    """A question set belongs to the folders its name combines: `market_production`
    tests Market and Productions. The general set (no folder) is nobody's alone."""
    if scope is None:
        return "edit"
    parts = rel.split("/")
    if len(parts) < 4:
        return None
    # The same matching the benchmark uses: `productions` and `production` are one.
    folder = question_category(scope.split("/", 1)[0])
    return "edit" if folder in set_categories(parts[2]) else None


def _within(folder: str, scope: str) -> bool:
    return folder == scope or folder.startswith(scope + "/")


def _rule_access(scope: str | None, rel: str,
                 fields: dict[str, str]) -> Literal["edit", "inherited", "shared"] | None:
    """How a sandbox scoped to `scope` may treat one rule file; None hides it."""
    if scope is None:
        return "edit"
    if rel == SCHEMA:
        return "shared"
    applies = normalize(fields.get("applies_to", "")).strip("/")
    if applies:
        if not applies.startswith("raw/"):
            return None
        folder = applies[len("raw/"):]
        if _within(folder, scope):
            return "edit"
        return "inherited" if _within(scope, folder) else None
    # An answering skill written before applies_to existed: ask-<folder>.
    name = (fields.get("name") or rel.split("/")[1]).casefold()
    top = scope.split("/", 1)[0]
    if name == f"ask-{top.casefold()}":
        return "edit" if scope == top else "inherited"
    return None


class SandboxFile(Contract):
    sandbox_id: str
    path: str
    text: str


class PlanPage(Contract):
    sandbox_id: str
    plan_id: str
    path: str
    before: str  # empty for a new page
    after: str



class QuestionItem(Contract):
    path: str  # in the sandbox, e.g. checks/questions/market/q1.md
    set: str
    text: str
    must: int = Field(ge=0)
    must_not: int = Field(ge=0)
    editable: bool = False


class QuestionSets(Contract):
    sandbox_id: str
    sets: dict[str, int] = Field(default_factory=dict)  # "" is the general set
    defaults: tuple[str, ...] = ()
    ungraded: tuple[str, ...] = ()
    questions: tuple[QuestionItem, ...] = ()


_LEGACY_SHA = re.compile(r"^source_sha:\s*([0-9a-f]{12,64})\s*$", re.MULTILINE)


def _legacy_source_shas(vault: Vault) -> dict[str, str]:
    """Original-file hashes that earlier tooling recorded in its Raw files as
    `source_sha:` (a sha256 prefix), with the Raw that holds each. Adopted legacy
    Raw is identified by its own bytes, so without these a pull would take every
    original as new."""
    found: dict[str, str] = {}
    for path in sorted((vault.root / "raw").rglob("*.md")):
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                head = handle.read(2048)
        except OSError:
            continue
        for match in _LEGACY_SHA.finditer(head.split("\n---", 1)[0]):
            found.setdefault(match.group(1), path.relative_to(vault.root).as_posix())
    return found


def _raw_holding(digest: str, known: dict[str, str], legacy: dict[str, str]) -> str | None:
    """The Raw that already holds an original with this content hash, if any."""
    if digest in known:
        return known[digest]
    return next((raw_ref for prefix, raw_ref in legacy.items() if digest.startswith(prefix)),
                None)



class SkillGuide(Contract):
    guide: str
    ingest_template: str
    answer_template: str
