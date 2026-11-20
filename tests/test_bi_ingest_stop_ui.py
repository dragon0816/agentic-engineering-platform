"""自動執行's 停止 and the part total from the start (owner 2026-11-21).

The Ingest progress says 第 1／N 段 before the first part is answered; 停止 shows beside
自動執行 only while it runs, the row says 停止中…（等目前這段完成） until the part under way
ends, and 自動執行 ends in place with 已停止 and its stage; the run is cancelled with no
candidates. The real Agent Web server, a gated scripted model and a background thread as
the Host runs it. All data is fictional.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_extract import Scripted
from test_bi_stage_gear_ui import DATASET, NOTE, _answer, _ingests, _open, _setup
from test_bi_vault import _call, _ok
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from aep_bi.cards.ai_runs import AiRuntime
from aep_bi.host import bi_cards_api

TEXT = "document.getElementById('bi-b-progress-text').textContent"


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_auto_run_stops_in_place_after_the_part_under_way(
    served: Any,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, workspace, _benches = _setup(served, tmp_path, monkeypatch)
    gate = threading.Event()

    def held(text: str) -> Any:
        gate.wait(60)
        return _answer(text)

    model = Scripted(held)
    monkeypatch.setattr(
        bi_cards_api,
        "web_ai_runtime",
        lambda _web: AiRuntime(
            model=lambda: (model, "test-model"),
            background=lambda _title, work: threading.Thread(target=work, daemon=True).start(),
        ),
    )
    try:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open(page)
            page.stage("source")
            assert page.run("document.getElementById('bi-b-auto-stop').hidden")
            page.attach("會議.md", NOTE, "text/markdown")
            page.click("#bi-b-auto")
            # The total before the first part is answered.
            page.wait(f"{TEXT}.includes('第 1／1 段')", 60)
            assert page.run("!document.getElementById('bi-b-auto-stop').hidden")
            page.click("#bi-b-auto-stop")
            page.wait(f"{TEXT}.includes('停止中…（等目前這段完成）')", 30)
            assert page.run("document.getElementById('bi-b-auto').disabled")
            gate.set()
            page.wait(f"{TEXT}.includes('自動執行已停止在第 2/4 步（Ingest）')", 60)
            assert page.run("document.getElementById('bi-b-auto-stop').hidden")
            assert not page.run("document.getElementById('bi-b-auto').disabled")
    finally:
        gate.set()
    (run,) = _ingests(workspace)
    assert run["status"] == "cancelled" and run["working"] is False
    detail = _ok(_call(workspace, "GET", f"/api/bi/runs/{run['id']}", dataset=DATASET))
    assert detail["candidates"] == []
