"""Re-ingest Raw documents with a sandbox's current rules (owner 2026-10-13)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from host_runtime.knowledge_reingest import ReingestRun, latest, one, run_reingest
from host_runtime.web_page import PAGE


class _Steps:
    """The page's two pipeline steps; each Raw ref picks its own outcome."""

    def __init__(self, stop: threading.Event | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.stop = stop

    def __call__(self, step: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((step, arguments))
        if step == "ingest-apply":
            if arguments["plan_id"] == "plan-stale":
                return {"ok": True, "data": {"status": "rejected", "problems": ["stale_plan"]}}
            return {"ok": True, "data": {"status": "applied", "written": ["wiki/a.md"]}}
        ref = arguments["raw_ref"]
        if self.stop is not None:
            self.stop.set()  # a person presses Stop while the first document runs
        if ref == "raw/Market/broken.md":
            return {"ok": False, "code": "model_http_error"}
        if ref == "raw/Market/empty.md":
            return {"ok": True, "data": {"status": "invalid_plan", "failure_code": None}}
        plan = {
            "status": "planned",
            "plan_id": "plan-1",
            "pages": [{"path": "wiki/a.md"}],
            "problems": [],
            "contradictions": [],
        }
        if ref == "raw/Market/flagged.md":
            plan.update(problems=["drops_sourced_line"], contradictions=["5G date differs"])
        if ref == "raw/Market/stale.md":
            plan["plan_id"] = "plan-stale"
        return {"ok": True, "data": plan}


def test_a_clean_plan_is_applied_and_a_flagged_one_waits_for_the_person() -> None:
    steps = _Steps()
    assert one(steps, "sb-1", "raw/Market/ok.md").status == "applied"
    assert [name for name, _ in steps.calls] == ["ingest-plan", "ingest-apply"]
    steps.calls.clear()
    flagged = one(steps, "sb-1", "raw/Market/flagged.md")
    assert flagged.status == "needs_review" and flagged.plan_id == "plan-1"
    assert flagged.pages == ("wiki/a.md",) and flagged.contradictions == ("5G date differs",)
    assert flagged.detail == "drops_sourced_line, contradiction"
    assert [name for name, _ in steps.calls] == ["ingest-plan"]  # never applied by itself
    assert one(steps, "sb-1", "raw/Market/broken.md").detail == "model_http_error"
    assert one(steps, "sb-1", "raw/Market/empty.md").status == "failed"
    assert one(steps, "sb-1", "raw/Market/stale.md").detail == "stale_plan"


def _run(*refs: str) -> ReingestRun:
    return ReingestRun(
        run_id="reingest-20261013T000000-abcd",
        sandbox_id="sb-1",
        actor="leo.chi",
        raw_refs=refs,
        started="2026-10-13T00:00:00+00:00",
    )


def test_a_run_records_every_document_and_can_continue_after_a_stop(tmp_path: Path) -> None:
    refs = ("raw/Market/ok.md", "raw/Market/flagged.md", "raw/Market/broken.md")
    stop = threading.Event()
    stopped = run_reingest(_Steps(stop), _run(*refs), tmp_path, stop)
    assert stopped.status == "stopped" and len(stopped.items) == 1
    saved = latest(tmp_path)
    assert saved is not None and saved["remaining"] == list(refs[1:])
    finished = run_reingest(
        _Steps(), stopped.model_copy(update={"status": "running"}), tmp_path, threading.Event()
    )
    assert finished.status == "finished" and finished.remaining == ()
    assert [i.status for i in finished.items] == ["applied", "needs_review", "failed"]
    assert latest(tmp_path)["remaining"] == []  # type: ignore[index]


def test_an_error_in_one_document_does_not_end_the_run(tmp_path: Path) -> None:
    def step(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise OSError("disk")

    done = run_reingest(step, _run("raw/a.md", "raw/b.md"), tmp_path, threading.Event())
    assert [i.detail for i in done.items] == ["error:OSError", "error:OSError"]


def test_the_page_offers_re_ingest_and_explains_pull() -> None:
    for hook in (
        'id="kp-reingest"',
        'id="kp-reingest-stop"',
        'id="kp-raw-folder"',
        "/api/knowledge/reingest/start",
        "already_raw",
        "Tick them in step 3",
    ):
        assert hook in PAGE


def test_the_ingest_list_previews_on_click_and_ticks_with_keys() -> None:
    # Owner 2026-10-13: the document shows beside the list (no Preview button, no jump),
    # new Raw from a convert is ticked and green, keys move and tick, one box ticks all.
    for hook in (
        'id="kp-doc"',
        'id="kp-plan-one"',
        'id="kp-raw-all"',
        'class="kp-filelist"',
        '"ArrowDown"',
        "event.shiftKey",
        "kpNewRaw",
        ".kp-file.kp-new span",
        "Ingest ticked",
    ):
        assert hook in PAGE
    assert 'id="kp-raw-tick"' not in PAGE and 'id="kp-raw-clear"' not in PAGE
