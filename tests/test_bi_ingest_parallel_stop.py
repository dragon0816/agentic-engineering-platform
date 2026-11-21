"""BI Ingest reads parts at once, stops for real and survives a restart (owner 2026-11-21).

A 28-part PDF took 42 minutes one part at a time, 停止 only flipped the run's status,
the total was unknown until part 1 ended, and a killed Host left the run `extracting`
forever. Here: up to `extract.PARALLEL_PARTS` parts at once with the same candidates,
ids and merges as one after another; the first progress is (0, N); a stopped run starts
no further part, writes nothing, ends `cancelled` and its task says `stopped`; a run
left `extracting` with no worker becomes `partial` with `interrupted` parts, and 重試
asks only those (parts read before answer from the cache). The models are fakes.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from test_bi_ai_runs import Jobs, _call, _detail, _ok, _runtime, _start

from aep_bi.cards import extract, runs
from aep_bi.cards.schema import registry
from aep_bi.cards.staging import Staging
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

PARTS = 6


def _text(parts: int = PARTS) -> str:
    # Each part names a technology; names repeat across parts, so merging order shows.
    return "\n".join(
        f"## 第 {i} 節\n\n技術 T{i % 3} 用在產線 {i}。\n" + "說明。" * 30 + "\n"
        for i in range(parts)
    )


class Reader:
    """Answers by the part it is shown, after a delay that differs per part, from any
    thread; counts calls under a lock and remembers which parts it was asked."""

    def __init__(self, delay: Callable[[int], float] = lambda part: 0.0) -> None:
        self.delay = delay
        self.lock = threading.Lock()
        self.asked: list[int] = []
        self.running = 0
        self.most = 0
        self.gate: threading.Event | None = None

    def generate(self, request: ModelRequest) -> ModelResponse:
        shown = request.messages[1].text
        part = int(re.search(r"第 (\d+) 節", shown).group(1))  # type: ignore[union-attr]
        with self.lock:
            self.asked.append(part)
            self.running += 1
            self.most = max(self.most, self.running)
        try:
            if self.gate is not None:
                self.gate.wait(5)
            time.sleep(self.delay(part))
            name = f"T{part % 3}"
            answer = {
                "candidates": [
                    {
                        "entity_type": "Technology",
                        "name": name,
                        "fields": {
                            "domain": {
                                "value": f"產線 {part}",
                                "basis": "fact",
                                "quote": f"技術 {name} 用在產線 {part}",
                            }
                        },
                    }
                ]
            }
            return ModelResponse(
                trace=request.trace, model_alias=request.model_alias, structured_output=answer
            )
        finally:
            with self.lock:
                self.running -= 1

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def _extract(model: Any, **extra: Any) -> extract.Extraction:
    return extract.extract(
        model,
        "test-model",
        registry(),
        text=_text(),
        source_id="src1",
        source_name="parts.md",
        types=("Technology",),
        instructions="",
        known={},
        chunk_chars=200,
        **extra,
    )


def test_parts_read_at_once_give_the_same_result_as_one_after_another() -> None:
    progress: list[tuple[int, int]] = []
    one = _extract(Reader(), workers=1)
    # Later parts finish first: the merge still follows the document.
    many_model = Reader(lambda part: 0.02 * (PARTS - part))
    many = _extract(many_model, workers=4, on_chunk=lambda d, t: progress.append((d, t)))
    assert one.chunks == many.chunks == PARTS
    assert many.candidates == one.candidates
    assert [c["id"] for c in many.candidates] == ["c1", "c2", "c3"]
    assert many.warnings == one.warnings and many.failures == one.failures == []
    assert many_model.most > 1  # really at once
    assert many_model.most <= 4
    assert progress[0] == (0, PARTS)  # the total before any call
    assert progress[-1] == (PARTS, PARTS) and len(progress) == PARTS + 1


def test_the_first_progress_names_the_total_before_any_model_call() -> None:
    seen: list[tuple[int, int, int]] = []
    model = Reader()
    _extract(model, workers=4, on_chunk=lambda d, t: seen.append((d, t, len(model.asked))))
    assert seen[0] == (0, PARTS, 0)


def test_a_retry_counts_the_parts_it_skips_as_done() -> None:
    seen: list[tuple[int, int]] = []
    _extract(Reader(), workers=4, only=[2, 4], on_chunk=lambda d, t: seen.append((d, t)))
    assert seen[0] == (PARTS - 2, PARTS) and seen[-1] == (PARTS, PARTS)


def test_a_stop_starts_no_further_part_and_marks_the_result() -> None:
    model = Reader()
    model.gate = threading.Event()
    stopped = threading.Event()

    gate = model.gate

    def stop_and_release() -> None:
        stopped.set()
        gate.set()

    def progress(done: int, total: int) -> None:
        if done == 0:
            # Four parts are under way when the person stops; let them end.
            threading.Timer(0.2, stop_and_release).start()

    result = _extract(model, workers=4, on_chunk=progress, cancelled=stopped.is_set)
    assert result.cancelled
    assert sorted(model.asked) == [0, 1, 2, 3]  # the ones under way only


def test_a_stop_before_a_format_retry_asks_no_more() -> None:
    calls: list[int] = []

    class Bad:
        def generate(self, request: ModelRequest) -> ModelResponse:
            calls.append(1)
            return ModelResponse(
                trace=request.trace, model_alias=request.model_alias, text="not json"
            )

    piece = extract.chunks(_text(1), 200)[0]
    found, _, failure = extract.extract_chunk(
        Bad(),  # type: ignore[arg-type]
        "m",
        registry(),
        types=("Technology",),
        instructions="",
        known={},
        chunk=piece,
        source_id="s",
        source_name="n",
        cancelled=lambda: bool(calls),
    )
    assert calls == [1] and found == []
    assert failure is not None and failure["code"] == extract.CANCELLED


# -- the run --------------------------------------------------------------------------


def _source(tmp_path: Path, parts: int = PARTS) -> str:
    body = {"dataset": "demo", "name": "parts.md", "text": _text(parts)}
    return str(_ok(_call(tmp_path, "POST", "/api/bi/sources", body))["source"]["id"])


@pytest.fixture
def small_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extract, "CHUNK_CHARS", 200)
    monkeypatch.setattr(extract, "PARALLEL_PARTS", 4)
    original = extract.extract

    def cut_small(*args: Any, **kwargs: Any) -> extract.Extraction:
        kwargs.setdefault("chunk_chars", 200)
        return original(*args, **kwargs)

    monkeypatch.setattr(extract, "extract", cut_small)


def test_a_stopped_run_writes_nothing_and_its_task_says_stopped(
    tmp_path: Path, small_parts: None
) -> None:
    jobs = Jobs()
    model = Reader()
    model.gate = threading.Event()
    run = _start(tmp_path, _runtime(model, jobs), _source(tmp_path))
    work = jobs.pending.pop(0)[1]
    ended: list[Any] = []
    worker = threading.Thread(target=lambda: ended.append(work()))
    worker.start()
    deadline = time.time() + 5
    while len(model.asked) < 4 and time.time() < deadline:
        time.sleep(0.01)
    shown = _detail(tmp_path, run["id"])["run"]
    assert shown["status"] == "extracting" and shown["progress"]["chunks"] == PARTS
    assert shown["working"] is True
    _ok(_call(tmp_path, "POST", f"/api/bi/runs/{run['id']}/cancel", {"dataset": "demo"}))
    stopping = _detail(tmp_path, run["id"])["run"]
    assert stopping["status"] == "cancelled" and stopping["working"] is True  # 停止中…
    model.gate.set()
    worker.join(5)
    assert ended == ["stopped"]
    after = _detail(tmp_path, run["id"])
    assert after["run"]["status"] == "cancelled" and after["run"]["working"] is False
    assert after["candidates"] == []
    assert sorted(model.asked) == [0, 1, 2, 3]


def test_the_task_reports_how_the_run_ended(tmp_path: Path, small_parts: None) -> None:
    jobs = Jobs()
    run = _start(tmp_path, _runtime(Reader(), jobs), _source(tmp_path))
    assert jobs.pending.pop(0)[1]() == "succeeded"
    assert _detail(tmp_path, run["id"])["run"]["status"] == "review"


def test_the_host_task_records_a_stopped_run_as_stopped() -> None:
    from aep_bi.host.bi_cards_api import web_ai_runtime

    finished: list[tuple[str, str]] = []

    class Tasks:
        def tracked(self, kind: str, title: str, where: str, work: Any) -> Any:
            return lambda: finished.append(work())

    class Web:
        def tasks(self) -> Tasks:
            return Tasks()

    runtime = web_ai_runtime(Web())
    for ended in ("stopped", "failed", None):
        runtime.background("t", lambda e=ended: e)  # type: ignore[misc]
    deadline = time.time() + 5
    while len(finished) < 3 and time.time() < deadline:
        time.sleep(0.01)
    assert sorted(finished) == sorted([("stopped", "t"), ("failed", "t"), ("succeeded", "t")])


def test_a_run_left_extracting_becomes_partial_and_retry_reads_only_what_is_missing(
    tmp_path: Path, small_parts: None
) -> None:
    jobs = Jobs()
    first = Reader()
    run = _start(tmp_path, _runtime(first, jobs), _source(tmp_path))
    jobs.run_all()  # read once: every part's answer is in the cache
    staging = Staging(tmp_path, "demo")
    reference = _detail(tmp_path, run["id"])["candidates"]
    # As if the Host was killed during a retry of parts 1 and 4: the run stays
    # `extracting`, its layout says which parts that attempt read, no thread works on it.
    layout = staging.layout(run["id"]) or {}
    layout.update(attempt=[1, 4], done=2)
    staging.put_layout(run["id"], layout)
    staging.set_status(run["id"], "extracting")
    shown = _detail(tmp_path, run["id"])["run"]
    assert shown["status"] == "partial" and shown["interrupted"] is True
    assert [(f["chunk"], f["code"]) for f in shown["failures"]] == [
        (1, runs.INTERRUPTED),
        (4, runs.INTERRUPTED),
    ]
    again = Reader()
    _ok(
        _call(
            tmp_path,
            "POST",
            f"/api/bi/runs/{run['id']}/retry",
            {"dataset": "demo"},
            _runtime(again, jobs),
        )
    )
    jobs.run_all()
    after = _detail(tmp_path, run["id"])
    assert again.asked == []  # parts 1 and 4 answered from the cache
    assert after["run"]["status"] == "review" and after["run"]["failures"] == []
    assert after["run"]["interrupted"] is False
    assert [c["name"] for c in after["candidates"]] == [c["name"] for c in reference]


def test_an_orphan_run_with_nothing_read_retries_every_part(
    tmp_path: Path, small_parts: None
) -> None:
    jobs = Jobs()
    run = _start(tmp_path, _runtime(Reader(), jobs), _source(tmp_path))
    jobs.pending.clear()  # the Host stopped before the work began
    runs.release_worker(Staging(tmp_path, "demo"), run["id"])
    shown = _detail(tmp_path, run["id"])["run"]
    assert shown["status"] == "partial" and shown["interrupted"] is True
    again = Reader()
    path = f"/api/bi/runs/{run['id']}/retry"
    _ok(_call(tmp_path, "POST", path, {"dataset": "demo"}, _runtime(again, jobs)))
    jobs.run_all()
    assert sorted(again.asked) == list(range(PARTS))
    assert _detail(tmp_path, run["id"])["run"]["status"] == "review"


def test_a_run_with_a_worker_is_never_taken_for_an_orphan(
    tmp_path: Path, small_parts: None
) -> None:
    jobs = Jobs()
    run = _start(tmp_path, _runtime(Reader(), jobs), _source(tmp_path))
    assert _detail(tmp_path, run["id"])["run"]["status"] == "extracting"
    assert not runs.recover_interrupted(Staging(tmp_path, "demo"), run["id"])
    jobs.run_all()
    assert _detail(tmp_path, run["id"])["run"]["status"] == "review"
    assert extract.PARALLEL_PARTS == 4


def test_a_run_that_ends_while_it_is_looked_at_is_not_taken_for_an_orphan(
    tmp_path: Path, small_parts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The page reads the run while its worker is finishing: the worker sets `review` and is
    # released between the read of the status and the check for a worker. That run ended
    # well; it must not become `partial` with an `interrupted` part.
    jobs = Jobs()
    run = _start(tmp_path, _runtime(Reader(), jobs), _source(tmp_path))
    finisher = threading.Thread(target=jobs.run_all)
    real = Staging.run_row
    first: list[bool] = []

    def run_row(self: Staging, run_id: str) -> Any:
        row = real(self, run_id)
        if not first:
            first.append(True)
            finisher.start()
            finisher.join(timeout=5)  # the worker ends meanwhile, if it can
        return row

    monkeypatch.setattr(Staging, "run_row", run_row)
    runs.recover_interrupted(Staging(tmp_path, "demo"), run["id"])
    monkeypatch.setattr(Staging, "run_row", real)
    if first:
        finisher.join()
    else:
        jobs.run_all()
    shown = _detail(tmp_path, run["id"])["run"]
    assert shown["status"] == "review" and shown["interrupted"] is False, shown
    assert shown["failures"] == []
