"""The LLM Wiki maintenance on Agent Web: its routes and their work.

The Knowledge tab's `知識庫維護` (docs/phases/KNOWLEDGE_K1.md, collaboration
C3-C4, knowledge repositories R4a-R4b): the pipeline's steps as the person who
pressed them, convert, re-ingest, benchmark, push, refresh and publish, the
Skill assistant, and the wiki repositories' routes (`knowledge_repos_api`).
These were `AgentWeb` methods and `_Handler` branches; they moved here
unchanged (docs/phases/FEATURE_PLUGIN_WIKI_PROPOSAL_DRAFT_20261118.md stage A)
and the feature serves them after the page token, through `handle`. Asking a
vault (`knowledge_binding`, `/api/knowledge/ask`) stays with Agent Web.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs

from aep_wiki.capabilities.handlers import (
    ADOPT_SPEC,
    CONVERT_SPEC,
    DROP_ADD_SPEC,
    DROP_FOLDERS_SPEC,
    FILE_READ_SPEC,
    INDEX_BUILD_SPEC,
    INDEX_ENRICH_SPEC,
    INGEST_APPLY_SPEC,
    INGEST_PLAN_SPEC,
    LINT_SPEC,
    MERGE_SPEC,
    PLAN_PAGE_SPEC,
    PULL_SPEC,
    QUESTION_SETS_SPEC,
    RULE_FILES_SPEC,
    RULE_WRITE_SPEC,
    SANDBOX_CONTENTS_SPEC,
    SANDBOX_CREATE_SPEC,
    SANDBOX_DISCARD_SPEC,
    SANDBOX_LIST_SPEC,
    SKILL_GUIDE_SPEC,
)
from aep_wiki.host import knowledge_repos_api, wiki_bench
from aep_wiki.host.knowledge_bench import latest as latest_benchmark
from aep_wiki.host.knowledge_bench import run_benchmark
from aep_wiki.host.knowledge_convert import ConvertRun, run_convert
from aep_wiki.host.knowledge_publish import (
    PublishError,
    publish_candidate,
    refresh_from_project,
)
from aep_wiki.host.knowledge_push import latest_push, run_push
from aep_wiki.host.knowledge_reingest import MAX_DOCUMENTS as MAX_REINGEST
from aep_wiki.host.knowledge_reingest import RUNS as REINGEST_RUNS
from aep_wiki.host.knowledge_reingest import ReingestRun, run_reingest
from aep_wiki.host.knowledge_reingest import latest as latest_reingest
from aep_wiki.host.knowledge_reingest import report as reingest_report
from aep_wiki.host.skill_assist import Turn, assist
from aep_wiki.knowledge.pipeline import KnowledgePipeline, PipelineError
from aep_wiki.knowledge.progress import read as knowledge_progress
from aep_wiki.knowledge.sandbox import REPO_PREFIX, SandboxError, Sandboxes
from aep_wiki.knowledge.wiki_work import capture as capture_work
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC
from common.execution import TraceIdentifiers
from common.local_agent import LocalCapabilityRequest
from host_runtime.contracts import KnowledgeAskRequest
from host_runtime.knowledge_harness import KnowledgeHarness, harness_skill
from host_runtime.review_routes import read_proposal
from host_runtime.tasks import TaskLog, TaskStatus
from knowledge.evolution import KnowledgeCatalog
from knowledge.vault import Vault
from knowledge.wiki_repos import listing as wiki_repo_listing

# The Knowledge tab's pipeline steps (docs/phases/KNOWLEDGE_K1.md), by the short
# name the page sends; nothing else can be called through its route.
PIPELINE_STEPS = {
    spec.identity.name: spec
    for spec in (
        SANDBOX_CREATE_SPEC,
        SANDBOX_LIST_SPEC,
        SANDBOX_CONTENTS_SPEC,
        SANDBOX_DISCARD_SPEC,
        DROP_ADD_SPEC,
        CONVERT_SPEC,
        INGEST_PLAN_SPEC,
        INGEST_APPLY_SPEC,
        LINT_SPEC,
        ADOPT_SPEC,
        INDEX_ENRICH_SPEC,
        INDEX_BUILD_SPEC,
        MERGE_SPEC,
        DROP_FOLDERS_SPEC,
        PULL_SPEC,
        QUESTION_SETS_SPEC,
        RULE_FILES_SPEC,
        FILE_READ_SPEC,
        RULE_WRITE_SPEC,
        PLAN_PAGE_SPEC,
        SKILL_GUIDE_SPEC,
    )
}
#: GET routes the maintenance answers, by path.
GET_ROUTES = (
    "/api/knowledge/pipeline",
    "/api/knowledge/skill-assist",
    "/api/knowledge/push",
    "/api/knowledge/review-proposal",
    "/api/knowledge/convert",
    "/api/knowledge/progress",
    "/api/knowledge/reingest",
    "/api/knowledge/benchmark",
)
#: POST routes the maintenance answers, by path.
POST_ROUTES = (
    "/api/knowledge/pipeline/call",
    "/api/knowledge/pipeline/publish",
    "/api/knowledge/benchmark/start",
    "/api/knowledge/push/start",
    "/api/knowledge/reingest/start",
    "/api/knowledge/convert/start",
    "/api/knowledge/convert/stop",
    "/api/knowledge/reingest/stop",
    "/api/knowledge/refresh",
    "/api/knowledge/skill-assist",
)


def _trace() -> TraceIdentifiers:
    value = uuid.uuid4().hex
    return TraceIdentifiers(
        trace_id=f"trace-{value}", request_id=f"request-{value}", span_id=f"span-{value}"
    )


class WikiWeb:
    """The maintenance work of one Agent Web (`AgentWeb.wiki`)."""

    def __init__(self, web: Any) -> None:
        self.web = web

    @property
    def runtime(self) -> Any:
        return self.web.runtime

    @property
    def config_path(self) -> Path | None:
        path: Path | None = self.web.config_path
        return path

    @property
    def knowledge_harness(self) -> KnowledgeHarness:
        harness: KnowledgeHarness = self.web.knowledge_harness
        return harness

    @property
    def _one_at_a_time(self) -> Any:
        return self.web._one_at_a_time

    def tasks(self) -> TaskLog:
        log: TaskLog = self.web.tasks()
        return log

    # -- Reviews: a review sandbox (E5) ------------------------------------------------

    def review_outcome(self, route: str | None) -> str:
        """How far an accepted proposal got: its review sandbox's last push."""
        if not route or not route.startswith("sandbox:"):
            return ""
        boxes = self._sandboxes()
        if boxes is None:
            return ""
        try:
            _, sandbox = boxes.open(route[len("sandbox:") :])
        except SandboxError:
            return "sandbox discarded"
        push = latest_push(sandbox)
        if push is None:
            return "in the sandbox, not pushed yet"
        found = push.get("benchmark")
        bench: dict[str, Any] = found if isinstance(found, dict) else {}
        return f"push {push.get('status')}" + (
            f": sandbox {bench.get('sandbox_score')} / project vault "
            f"{bench.get('project_score')} of {bench.get('total')}"
            if bench
            else ""
        )

    def review_proposal(self, sandbox_id: str) -> dict[str, Any]:
        """The proposal a review sandbox was opened for, for the Knowledge page."""
        boxes = self._sandboxes()
        if boxes is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        try:
            _, sandbox = boxes.open(sandbox_id)
        except SandboxError as error:
            return {"ok": False, "code": error.code}
        return {"ok": True, "proposal": read_proposal(sandbox.root)}

    # -- the Knowledge tab's steps (K1-K3, collaboration C3-C4) ----------------------

    def knowledge_pipeline(self) -> dict[str, Any]:
        """What the Knowledge tab may offer: the configured base vaults."""
        binding = self.runtime.config.knowledge_pipeline
        vaults = list(binding.vaults) if binding else []
        # A project vault (one the Agent's Knowledge is refreshed from) comes first, so
        # the start form does not default to a test vault (seen live, 2026-10-14).
        vaults.sort(key=lambda item: item.knowledge_asset is None)
        return {
            "enabled": binding is not None,
            # Wiki repositories on this PC (R4b), opened as `repo.<id>`.
            "repos": wiki_repo_listing(self.runtime.layout.workspace_root),
            "repo_prefix": REPO_PREFIX,
            "bases": [item.name for item in vaults],
            "vaults": [
                {
                    "name": item.name,
                    "project": item.knowledge_asset is not None,
                    "asset": item.knowledge_asset,
                }
                for item in vaults
            ],
        }

    def pipeline_call(self, step: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """One pipeline step through the Agent, as the person who pressed it."""
        spec = PIPELINE_STEPS.get(step)
        if spec is None or self.runtime.config.knowledge_pipeline is None:
            return {"ok": False, "code": "unknown_pipeline_step"}
        local = LocalCapabilityRequest(
            ingress="local",
            actor=self.runtime.actor,
            bridge_id=self.runtime.config.device.bridge_id,
            target=spec.identity,
            arguments=arguments,
            trace=_trace(),
        )
        import asyncio

        outcome = asyncio.run(self.runtime.agent.execute_capability(local))
        if outcome.refusal is not None:
            return {"ok": False, "code": str(outcome.refusal)}
        capability = outcome.capability
        if capability is None or capability.status != "succeeded":
            failure = capability.failure if capability is not None else None
            return {"ok": False, "code": failure.code if failure else "pipeline_step_failed"}
        if spec.side_effect != "read":
            # What a step wrote into a wiki repository's working folder is
            # staged in its working copy (R4b).
            captured = self._capture_repo(str(arguments.get("sandbox_id") or ""))
            if captured is not None:
                return {"ok": True, "data": capability.data, "captured": captured}
        return {"ok": True, "data": capability.data}

    def _capture_repo(self, sandbox_id: str) -> dict[str, Any] | None:
        """Stage what a step wrote into a wiki repository's working folder;
        None for a sandbox."""
        boxes = self._sandboxes()
        if boxes is None or not sandbox_id.startswith(REPO_PREFIX):
            return None
        try:
            return capture_work(boxes.repository(sandbox_id))
        except SandboxError:
            return None

    def publish_knowledge(self, base: str, candidate_root: str) -> dict[str, Any]:
        """Publish a merged candidate as the base's new version (K3.4). Only a
        person's confirmed click reaches this; the model has no such tool."""
        if self.config_path is None or self.runtime.config.knowledge_pipeline is None:
            return {"ok": False, "code": "publish_unavailable"}
        with self._one_at_a_time:
            try:
                result = publish_candidate(
                    self.config_path, self.runtime.layout, base, candidate_root, self.runtime.actor
                )
            except PublishError as error:
                return {"ok": False, "code": error.code}
        return {"ok": True, "restart_required": True, "data": result.model_dump(mode="json")}

    def _sandboxes(self) -> Sandboxes | None:
        binding = self.runtime.config.knowledge_pipeline
        if binding is None:
            return None
        return Sandboxes(
            self.runtime.layout.workspace_root,
            root=Path(binding.sandbox_root) if binding.sandbox_root else None,
        )

    def start_benchmark(self, sandbox_id: str, sets: list[str]) -> dict[str, Any]:
        """Run the chosen question sets in the background (collaboration C3)."""
        boxes = self._sandboxes()
        binding = self.runtime.config.knowledge_pipeline
        if boxes is None or binding is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        try:
            info, sandbox = boxes.open(sandbox_id)
        except SandboxError as error:
            return {"ok": False, "code": error.code}
        if not sets or not all(isinstance(name, str) for name in sets):
            return {"ok": False, "code": "no_question_sets"}
        if info.repo is not None and not info.questions_root:
            return {"ok": False, "code": "questions_not_set"}
        entry = next((v for v in binding.vaults if v.name == info.base_name), None)
        fallback = (
            Path(info.questions_root)
            if info.questions_root
            else Path(entry.questions_root)
            if entry and entry.questions_root
            else Path(info.base_root) / "checks" / "questions"
        )
        skill = harness_skill(self.runtime.agent.gateway.router.commands.skills)
        run_id = f"bench-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:4]}"

        def ask(request: KnowledgeAskRequest, catalog: KnowledgeCatalog) -> dict[str, Any]:
            return self.knowledge_harness.ask(request, catalog=catalog)

        def work() -> tuple[TaskStatus, str]:
            if info.repo is not None:
                # A repository's working folder against its pushed head; the
                # report is what its push check reads (R4a).
                report = wiki_bench.run(
                    self.runtime.layout.workspace_root,
                    info.repo,
                    ask,
                    sets=tuple(sets),
                    actor=self.runtime.actor,
                    skill=skill,
                    questions_fallback=fallback,
                    run_id=run_id,
                )
            else:
                report = run_benchmark(
                    ask,
                    sandbox_id=sandbox_id,
                    sandbox=sandbox,
                    project=Vault(Path(info.base_root)),
                    sets=tuple(sets),
                    actor=self.runtime.actor,
                    skill=skill,
                    questions_fallback=fallback,
                    run_id=run_id,
                )
            return (
                "succeeded" if report.status == "finished" else "failed",
                f"sandbox {report.sandbox_score} / project vault {report.project_score} "
                f"of {report.total}",
            )

        threading.Thread(
            target=self.tasks().tracked(
                "benchmark", "Benchmark " + ", ".join(sets), sandbox_id, work
            ),
            daemon=True,
        ).start()
        return {"ok": True, "run_id": run_id}

    def _pipeline(self) -> KnowledgePipeline | None:
        """The pipeline for merge and push; no model is needed for either."""
        binding = self.runtime.config.knowledge_pipeline
        boxes = self._sandboxes()
        if binding is None or boxes is None:
            return None
        return KnowledgePipeline(
            boxes,
            {item.name: Path(item.root) for item in binding.vaults},
            questions_roots={
                item.name: Path(item.questions_root)
                for item in binding.vaults
                if item.questions_root
            },
            maintainers={item.name: tuple(item.maintainers) for item in binding.vaults},
        )

    def start_push(
        self, sandbox_id: str, sets: list[str], resolutions: dict[str, str]
    ) -> dict[str, Any]:
        """Merge, benchmark and, when the gate passes, write into the project
        vault, in the background (collaboration C4)."""
        pipeline = self._pipeline()
        if pipeline is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        if sandbox_id.startswith(REPO_PREFIX):
            return {"ok": False, "code": "repository_uses_versions"}
        try:
            info, _ = pipeline.sandboxes.open(sandbox_id)
        except SandboxError as error:
            return {"ok": False, "code": error.code}
        if not pipeline.may_push(info.base_name, self.runtime.actor):
            return {"ok": False, "code": "not_a_maintainer"}
        chosen: dict[str, Literal["sandbox", "published"]] = {
            key: "sandbox" if value == "sandbox" else "published"
            for key, value in resolutions.items()
            if value in ("sandbox", "published")
        }
        push_id = f"push-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:4]}"
        skill = harness_skill(self.runtime.agent.gateway.router.commands.skills)

        def work() -> tuple[TaskStatus, str]:
            report = run_push(
                pipeline,
                lambda request, catalog: self.knowledge_harness.ask(request, catalog=catalog),
                sandbox_id=sandbox_id,
                actor=self.runtime.actor,
                sets=tuple(sets),
                resolutions=chosen,
                skill=skill,
                push_id=push_id,
                questions_fallback=pipeline.questions_roots.get(info.base_name),
            )
            status: TaskStatus = (
                "succeeded"
                if report.status == "pushed"
                else "needs_input"
                if report.status == "conflicts"
                else "failed"
            )
            return status, report.status + (f": {report.reason}" if report.reason else "")

        threading.Thread(
            target=self.tasks().tracked("push", f"Push to {info.base_name}", sandbox_id, work),
            daemon=True,
        ).start()
        return {"ok": True, "push_id": push_id}

    def push_status(self, sandbox_id: str) -> dict[str, Any]:
        boxes = self._sandboxes()
        if boxes is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        try:
            _, sandbox = boxes.open(sandbox_id)
        except SandboxError as error:
            return {"ok": False, "code": error.code}
        return {"ok": True, "push": latest_push(sandbox)}

    def start_convert(self, sandbox_id: str, mode: str) -> dict[str, Any]:
        """Convert (or preview) every original in the sandbox's drop/ in the
        background, one at a time (owner 2026-10-13)."""
        installed = self.runtime.agent.gateway.bridge.installed.get(CONVERT_SPEC.identity)
        pipeline = getattr(getattr(installed, "handler", None), "pipeline", None)
        if not isinstance(pipeline, KnowledgePipeline) or mode not in ("dry_run", "apply"):
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        try:
            paths = pipeline.contents(sandbox_id).drop
        except (SandboxError, PipelineError) as error:
            return {"ok": False, "code": error.code}
        if not paths:
            return {"ok": False, "code": "drop_empty"}
        self._convert_stops: dict[str, threading.Event] = getattr(self, "_convert_stops", {})
        self._convert_runs: dict[str, ConvertRun] = getattr(self, "_convert_runs", {})
        if sandbox_id in self._convert_stops:
            return {"ok": False, "code": "convert_running"}
        stop = threading.Event()
        self._convert_stops[sandbox_id] = stop
        run = ConvertRun(
            run_id=f"convert-{uuid.uuid4().hex[:8]}",
            sandbox_id=sandbox_id,
            mode="apply" if mode == "apply" else "dry_run",
            paths=paths,
            progress_key=f"cv{uuid.uuid4().hex[:16]}",
            started=datetime.now(UTC).isoformat(timespec="seconds"),
        )

        def remember(current: ConvertRun) -> None:
            self._convert_runs[sandbox_id] = current

        def work() -> tuple[TaskStatus, str]:
            try:
                done = run_convert(
                    lambda box, chosen, how, key: pipeline.convert(
                        box, chosen, "apply" if how == "apply" else "dry_run", key
                    ),
                    run,
                    stop,
                    remember,
                )
            except Exception as failure:  # noqa: BLE001 - the page must hear it ended
                last = self._convert_runs.get(sandbox_id, run)
                self._convert_runs[sandbox_id] = last.model_copy(
                    update={"status": "failed", "error": type(failure).__name__, "current": None}
                )
                raise
            finally:
                self._convert_stops.pop(sandbox_id, None)
                if run.mode == "apply":
                    self._capture_repo(sandbox_id)  # converted Raw, even when stopped
            results: dict[str, int] = {}
            for item in done.items:
                results[item.status] = results.get(item.status, 0) + 1
            return (
                "succeeded" if done.status == "finished" else "stopped",
                f"{len(done.items)} of {len(done.paths)} originals: "
                + ", ".join(f"{n} {status}" for status, n in sorted(results.items())),
            )

        title = (
            "Convert " if run.mode == "apply" else "Preview convert "
        ) + f"{len(paths)} original(s)"
        threading.Thread(
            target=self.tasks().tracked(
                "convert" if run.mode == "apply" else "preview", title, sandbox_id, work
            ),
            name="knowledge-convert",
            daemon=True,
        ).start()
        return {"ok": True, "run_id": run.run_id}

    def stop_convert(self, sandbox_id: str) -> dict[str, Any]:
        stop = getattr(self, "_convert_stops", {}).get(sandbox_id)
        if stop is None:
            return {"ok": False, "code": "convert_not_running"}
        stop.set()
        return {"ok": True}

    def convert_status(self, sandbox_id: str) -> dict[str, Any]:
        run = getattr(self, "_convert_runs", {}).get(sandbox_id)
        if run is None:
            return {"ok": True, "run": None}
        shown = run.model_dump(mode="json")
        stop = getattr(self, "_convert_stops", {}).get(sandbox_id)
        if shown["status"] == "running" and stop is not None and stop.is_set():
            shown["status"] = "stopping"
        shown["progress"] = knowledge_progress(run.progress_key)
        return {"ok": True, "run": shown}

    def start_reingest(self, sandbox_id: str, raw_refs: list[str]) -> dict[str, Any]:
        """Ingest the chosen Raw documents again with the sandbox's current
        rules, one after another in the background (owner 2026-10-13)."""
        boxes = self._sandboxes()
        if boxes is None or self.runtime.config.knowledge_pipeline is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        try:
            _, sandbox = boxes.open(sandbox_id)
        except SandboxError as error:
            return {"ok": False, "code": error.code}
        chosen = tuple(
            dict.fromkeys(
                ref for ref in raw_refs if isinstance(ref, str) and ref.startswith("raw/")
            )
        )
        if not chosen or len(chosen) > MAX_REINGEST:
            return {"ok": False, "code": "no_raw_documents"}
        self._reingest_stops: dict[str, threading.Event] = getattr(self, "_reingest_stops", {})
        self._reingest_live: dict[str, ReingestRun] = getattr(self, "_reingest_live", {})
        if sandbox_id in self._reingest_stops:
            return {"ok": False, "code": "reingest_running"}
        stop = threading.Event()
        self._reingest_stops[sandbox_id] = stop
        run = ReingestRun(
            run_id=f"reingest-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:4]}",
            sandbox_id=sandbox_id,
            actor=self.runtime.actor,
            raw_refs=chosen,
            started=datetime.now(UTC).isoformat(timespec="seconds"),
        )

        def live(current: ReingestRun) -> None:
            self._reingest_live[sandbox_id] = current

        def work() -> tuple[TaskStatus, str]:
            try:
                done = run_reingest(
                    self.pipeline_call, run, sandbox.root / REINGEST_RUNS, stop, on_change=live
                )
            finally:
                self._reingest_stops.pop(sandbox_id, None)
                self._reingest_live.pop(sandbox_id, None)
            results: dict[str, int] = {}
            for item in done.items:
                results[item.status] = results.get(item.status, 0) + 1
            return (
                "succeeded" if done.status == "finished" else "stopped",
                f"{len(done.items)} of {len(done.raw_refs)} Raw: "
                + ", ".join(f"{n} {status}" for status, n in sorted(results.items())),
            )

        threading.Thread(
            target=self.tasks().tracked(
                "reingest", f"Re-ingest {len(chosen)} Raw document(s)", sandbox_id, work
            ),
            name="knowledge-reingest",
            daemon=True,
        ).start()
        return {"ok": True, "run_id": run.run_id}

    def stop_reingest(self, sandbox_id: str) -> dict[str, Any]:
        """Stop after the document in progress; what is left can be continued."""
        stop = getattr(self, "_reingest_stops", {}).get(sandbox_id)
        if stop is None:
            return {"ok": False, "code": "reingest_not_running"}
        stop.set()
        return {"ok": True}

    def reingest_status(self, sandbox_id: str) -> dict[str, Any]:
        boxes = self._sandboxes()
        if boxes is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        try:
            _, sandbox = boxes.open(sandbox_id)
        except SandboxError as error:
            return {"ok": False, "code": error.code}
        current = getattr(self, "_reingest_live", {}).get(sandbox_id)
        stop = getattr(self, "_reingest_stops", {}).get(sandbox_id)
        if current is not None:
            live = reingest_report(current)
            if stop is not None and stop.is_set() and live["status"] == "running":
                live["status"] = "stopping"
            return {"ok": True, "run": live}
        saved = latest_reingest(sandbox.root / REINGEST_RUNS)
        if saved is not None and saved["status"] in ("running", "stopping") and stop is None:
            saved["status"] = "interrupted"  # the Agent restarted while it ran
        return {"ok": True, "run": saved}

    def refresh_knowledge(self, base: str) -> dict[str, Any]:
        """Stage the project vault as the Agent's next Knowledge version."""
        if self.config_path is None:
            return {"ok": False, "code": "refresh_unavailable"}
        with self._one_at_a_time:
            try:
                result = refresh_from_project(
                    self.config_path, self.runtime.layout, base, self.runtime.actor
                )
            except PublishError as error:
                return {"ok": False, "code": error.code}
        return {"ok": True, "restart_required": True, "data": result.model_dump(mode="json")}

    def skill_assist_start(
        self, sandbox_id: str, path: str, current: str, turns: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Start one reply in the background; the page follows its state:
        collecting -> asking -> checking -> done | failed."""
        job_id = uuid.uuid4().hex[:12]
        job: dict[str, Any] = {
            "ok": True,
            "job_id": job_id,
            "state": "collecting",
            "started": time.monotonic(),
            "history": ["collecting"],
        }
        self._assist_jobs = getattr(self, "_assist_jobs", {})
        self._assist_jobs[job_id] = job

        def state(name: str) -> None:
            job["state"] = name
            job["history"].append(name)

        def run() -> None:
            result = self.skill_assist(sandbox_id, path, current, turns, on_state=state)
            job["result"] = result
            state("done" if result.get("ok") else "failed")

        threading.Thread(target=run, name="skill-assist", daemon=True).start()
        return {"ok": True, "job_id": job_id}

    def skill_assist_status(self, job_id: str) -> dict[str, Any]:
        job = getattr(self, "_assist_jobs", {}).get(job_id)
        if job is None:
            return {"ok": False, "code": "unknown_job"}
        return {
            "ok": True,
            "state": job["state"],
            "history": job["history"],
            "elapsed_s": round(time.monotonic() - job["started"], 1),
            "result": job.get("result"),
        }

    def skill_assist(
        self,
        sandbox_id: str,
        path: str,
        current: str,
        turns: list[dict[str, Any]],
        on_state: Any = None,
    ) -> dict[str, Any]:
        """One reply of the Skill assistant; it proposes, the person saves."""
        pipeline = self._pipeline()
        if pipeline is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        if not (
            path == "CLAUDE.md"
            or re.fullmatch(r"skills/[A-Za-z0-9][A-Za-z0-9._-]*/SKILL\.md", path)
        ):
            return {"ok": False, "code": "not_a_rule_file"}
        try:
            _, vault = pipeline.sandboxes.open(sandbox_id)
            chat = [Turn.model_validate(turn) for turn in turns]
        except (SandboxError, ValueError):
            return {"ok": False, "code": "skill_assist_request_invalid"}
        installed = self.runtime.agent.gateway.bridge.installed.get(KNOWLEDGE_QUERY_SPEC.identity)
        model = getattr(getattr(installed, "handler", None), "model", None)
        alias = getattr(getattr(installed, "handler", None), "alias", None)
        if model is None or alias is None:
            return {"ok": False, "code": "skill_assist_unavailable"}
        guide = pipeline.skill_guide()
        answering = "mode: answer" in current or path.startswith("skills/ask-")
        scope = re.search(r"^applies_to:\s*(raw/\S+)", current, re.MULTILINE)
        sample = None
        if scope and not answering:
            folder = vault.root / scope.group(1)
            first = next(iter(sorted(folder.rglob("*.md"))), None) if folder.is_dir() else None
            if first is not None:
                sample = first.read_text(encoding="utf-8", errors="ignore")
        try:
            reply = assist(
                model,
                alias,
                guide=guide.guide,
                template=guide.answer_template if answering else guide.ingest_template,
                path=path,
                current=current,
                sample=sample,
                turns=chat,
                trace=_trace(),
                on_state=on_state,
            )
        except (RuntimeError, ValueError) as error:
            return {"ok": False, "code": f"skill_assist_failed:{error}"[:80]}
        return {"ok": True, **reply.model_dump(mode="json")}

    def benchmark_status(self, sandbox_id: str) -> dict[str, Any]:
        boxes = self._sandboxes()
        if boxes is None:
            return {"ok": False, "code": "knowledge_pipeline_disabled"}
        try:
            _, sandbox = boxes.open(sandbox_id)
        except SandboxError as error:
            return {"ok": False, "code": error.code}
        return {"ok": True, "report": latest_benchmark(sandbox)}


def handle(handler: Any, method: str, parsed: Any) -> bool:
    """Answer a maintenance route on the web handler (already token-checked);
    True when answered. The wiki repositories' routes come first, as before."""
    if knowledge_repos_api.handle(handler, method, parsed):  # wiki repositories (R4a)
        return True
    wiki: WikiWeb | None = getattr(handler.server.web, "wiki", None)
    if wiki is None:
        return False
    if method == "GET":
        return _get(handler, wiki, parsed)
    if method == "POST" and parsed.path in POST_ROUTES:
        _post(handler, wiki, parsed.path)
        return True
    return False


def _get(handler: Any, web: WikiWeb, parsed: Any) -> bool:
    if parsed.path not in GET_ROUTES:
        return False
    query = parse_qs(parsed.query)
    if parsed.path == "/api/knowledge/pipeline":
        handler._json(200, web.knowledge_pipeline())
    elif parsed.path == "/api/knowledge/skill-assist":
        handler._json(200, web.skill_assist_status((query.get("job") or [""])[0]))
    elif parsed.path == "/api/knowledge/push":
        handler._json(200, web.push_status((query.get("sandbox_id") or [""])[0]))
    elif parsed.path == "/api/knowledge/review-proposal":
        handler._json(200, web.review_proposal((query.get("sandbox_id") or [""])[0]))
    elif parsed.path == "/api/knowledge/convert":
        handler._json(200, web.convert_status((query.get("sandbox_id") or [""])[0]))
    elif parsed.path == "/api/knowledge/progress":
        key = (query.get("key") or [""])[0]
        handler._json(200, {"ok": True, "progress": knowledge_progress(key)})
    elif parsed.path == "/api/knowledge/reingest":
        handler._json(200, web.reingest_status((query.get("sandbox_id") or [""])[0]))
    else:  # /api/knowledge/benchmark
        handler._json(200, web.benchmark_status((query.get("sandbox_id") or [""])[0]))
    return True


def _post(handler: Any, web: WikiWeb, path: str) -> None:
    # Agent Web's own request limits: an original travels in a step call.
    from host_runtime.web import MAX_ATTACHMENT_REQUEST_BYTES, MAX_BODY_BYTES

    try:
        length = int(handler.headers.get("Content-Length") or "0")
    except ValueError:
        handler._json(400, {"error": "the request did not say how long it was"})
        return
    limit = (
        MAX_ATTACHMENT_REQUEST_BYTES if path == "/api/knowledge/pipeline/call" else MAX_BODY_BYTES
    )
    if length > limit:
        handler._json(413, {"error": "that is larger than a request to an Agent"})
        return
    try:
        body = json.loads(handler.rfile.read(length) or b"{}")
    except (ValueError, TypeError):
        handler._json(400, {"error": "the request was not valid JSON"})
        return
    if path == "/api/knowledge/pipeline/call":
        if not isinstance(body, dict) or not isinstance(body.get("arguments", {}), dict):
            handler._json(400, {"ok": False, "code": "pipeline_request_invalid"})
            return
        try:
            result = web.pipeline_call(
                str(body.get("step") or ""), dict(body.get("arguments") or {})
            )
        except Exception as failure:  # noqa: BLE001 - a page shows everything
            result = {"ok": False, "code": f"pipeline_error:{type(failure).__name__}"}
        handler._json(200, result)
        return
    if path == "/api/knowledge/push/start":
        if (
            not isinstance(body, dict)
            or not isinstance(body.get("sets"), list)
            or not isinstance(body.get("resolutions", {}), dict)
        ):
            handler._json(400, {"ok": False, "code": "push_request_invalid"})
            return
        handler._json(
            200,
            web.start_push(
                str(body.get("sandbox_id") or ""),
                [str(x) for x in body["sets"]],
                {str(k): str(v) for k, v in dict(body.get("resolutions") or {}).items()},
            ),
        )
        return
    if path in ("/api/knowledge/convert/start", "/api/knowledge/convert/stop"):
        chosen = body if isinstance(body, dict) else {}
        sandbox_id = str(chosen.get("sandbox_id") or "")
        handler._json(
            200,
            web.start_convert(sandbox_id, str(chosen.get("mode") or ""))
            if path.endswith("/start")
            else web.stop_convert(sandbox_id),
        )
        return
    if path == "/api/knowledge/reingest/start":
        if not isinstance(body, dict) or not isinstance(body.get("raw_refs"), list):
            handler._json(400, {"ok": False, "code": "reingest_request_invalid"})
            return
        handler._json(
            200,
            web.start_reingest(str(body.get("sandbox_id") or ""), list(body["raw_refs"])),
        )
        return
    if path == "/api/knowledge/reingest/stop":
        sandbox_id = str(body.get("sandbox_id") or "") if isinstance(body, dict) else ""
        handler._json(200, web.stop_reingest(sandbox_id))
        return
    if path == "/api/knowledge/skill-assist":
        if not isinstance(body, dict) or not isinstance(body.get("turns"), list):
            handler._json(400, {"ok": False, "code": "skill_assist_request_invalid"})
            return
        handler._json(
            200,
            web.skill_assist_start(
                str(body.get("sandbox_id") or ""),
                str(body.get("path") or ""),
                str(body.get("current") or ""),
                list(body["turns"]),
            ),
        )
        return
    if path == "/api/knowledge/refresh":
        if not isinstance(body, dict):
            handler._json(400, {"ok": False, "code": "refresh_request_invalid"})
            return
        handler._json(200, web.refresh_knowledge(str(body.get("base") or "")))
        return
    if path == "/api/knowledge/benchmark/start":
        if not isinstance(body, dict) or not isinstance(body.get("sets"), list):
            handler._json(400, {"ok": False, "code": "benchmark_request_invalid"})
            return
        handler._json(
            200,
            web.start_benchmark(str(body.get("sandbox_id") or ""), list(body["sets"])),
        )
        return
    # /api/knowledge/pipeline/publish
    if not isinstance(body, dict):
        handler._json(400, {"ok": False, "code": "publish_request_invalid"})
        return
    handler._json(
        200,
        web.publish_knowledge(str(body.get("base") or ""), str(body.get("candidate_root") or "")),
    )
