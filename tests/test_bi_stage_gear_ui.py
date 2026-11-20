"""The BI build page's stages, their gear settings and 自動執行 (owner 2026-11-20).

Each stage is named as the owner named it (Data input, Ingest, Benchmark testing); what it needs
set once opens from its gear as a tab of the side area, and the main view keeps its run and its
results. 自動執行 runs 轉檔, Ingest, accepting every pending row with 匯入, and 跑測試 with no
stop, its progress beside it; a second press while it runs, or a reload in the middle, never
starts a second run or imports twice. The real Agent Web server in a temporary workspace,
joined to a copy of the fixture vault, with a scripted model. All data is fictional.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_extract import Scripted
from test_bi_vault import _call, _ok
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from aep_bi.cards.ai_runs import AiRuntime
from aep_bi.host import bi_bench, bi_cards_api
from scripts import bi_feed_fixtures as fixtures

VAULT = fixtures.VAULT_ID
DATASET = f"vault-{VAULT}"
NOTE = "# 會議\n\n日期：2026-10-01\n客戶 FAKE-7 表示正在評估 TSN。\n"
QUOTE = "客戶 FAKE-7 表示正在評估 TSN"
CARD = "FAKE-7 評估 TSN"


def _answer(_text: str) -> Any:
    # Slow enough to watch the stage it is in, and to reload the page in the middle.
    time.sleep(2.5)
    return {
        "candidates": [
            {
                "entity_type": "Signal",
                "name": CARD,
                "fields": {
                    # A Signal is named by its date and title.
                    "date": {"value": "2026-10-01", "basis": "fact", "quote": "日期：2026-10-01"},
                    "title": {"value": CARD, "basis": "fact", "quote": QUOTE},
                    "summary": {"value": QUOTE, "basis": "fact", "quote": QUOTE},
                    # A judgement field, required: accepted with no reason (owner 2026-11-20).
                    "so_what": {"value": "可能需要 TSN 方案", "basis": "inference"},
                },
            }
        ]
    }


def _setup(
    served: Any,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, Path, list[str]]:
    web, server, _recorder, _ = served
    workspace = web.runtime.layout.workspace_root
    copy = tmp_path / "shared" / "vault"
    shutil.copytree(fixtures.VAULT_DIR, copy)
    fixtures.join(workspace, copy)
    benches: list[str] = []

    def background(title: str, work: Any) -> None:
        benches.append(title)
        work()

    monkeypatch.setattr(
        bi_cards_api,
        "web_bench_runtime",
        lambda _web: bi_bench.BenchRuntime(
            ask_for=lambda _v, _a: lambda q, s: {"ok": True, "answer": QUOTE},
            extract_for=lambda _v, _a: lambda case: [],
            background=background,
        ),
    )
    model = Scripted(_answer)
    monkeypatch.setattr(
        bi_cards_api,
        "web_ai_runtime",
        lambda _web: AiRuntime(
            model=lambda: (model, "test-model"), background=lambda _title, work: work()
        ),
    )
    return server, workspace, benches


def _open(page: BiPage) -> str:
    page.run(f"bi.want = {DATASET!r}; biLoad()")
    page.wait(f"document.getElementById('bi-dataset').value === {DATASET!r}")
    page.click("#bi-views [data-bi-view=build]")
    page.wait("(bi.build.homes || []).length > 0")
    folder = str(page.run("bi.build.homes[0].folder"))
    page.choose("bi-b-src-folder", folder)
    return folder


def _ingests(workspace: Path) -> list[dict[str, Any]]:
    found = _ok(_call(workspace, "GET", "/api/bi/runs", dataset=DATASET))["runs"]
    return [run for run in found if run["kind"] == "ingest"]


def _shown(ident: str) -> str:
    return f"document.getElementById({ident!r}).getClientRects().length > 0"


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_each_gear_opens_its_stages_settings_beside_and_the_main_view_has_none(
    served: Any,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, _workspace, _benches = _setup(served, tmp_path, monkeypatch)
    with BiPage(tmp_path / "browser", server.address) as page:
        _open(page)
        names = page.run(
            "[...document.querySelectorAll('#bi-stepper [data-stage] strong')]"
            ".map((s) => s.textContent)"
        )
        assert names == ["Data input", "Ingest", "Benchmark testing"]
        page.stage("source")
        assert "Data input" in page.text_of("bi-b-source")

        settings = {
            "source": ("bi-b-class", "bi-b-v-info"),
            "ingest": ("bi-b-schema-now", "bi-b-m-pick", "bi-b-sk-list", "bi-b-adv-schema"),
            "test": ("bi-b-bq-form", "bi-b-qa-open", "bi-b-an-list", "bi-b-an-new"),
        }
        stage_of = {"source": "source", "ingest": "method", "test": "test"}
        titles = {"source": "Data input 設定", "ingest": "Ingest 設定",
                  "test": "Benchmark testing 設定"}  # fmt: skip
        for gear, idents in settings.items():
            page.stage(stage_of[gear])
            # The main view shows none of the stage's settings.
            for ident in idents:
                assert not page.run(_shown(ident)), ident
            assert (
                page.run(f"document.getElementById('bi-b-gear-{gear}').ariaLabel") == titles[gear]
            )
            page.gear(gear)
            tab = (
                "[...document.querySelectorAll('.extra-tab-label')]"
                f".filter((t) => t.textContent === {titles[gear]!r})"
            )
            assert page.run(f"{tab}.length") == 1
            for ident in idents:
                assert page.run(
                    f"document.getElementById({ident!r}).closest('.extra-panel') !== null"
                ), ident
            assert page.run(f"document.getElementById('bi-b-gear-{gear}').ariaExpanded") == "true"
            # Pressed again: the same tab comes to the front, not a second one.
            page.click(f"#bi-b-gear-{gear}")
            assert page.run(f"{tab}.length") == 1
            # Closed: the settings go back home, hidden, ids and all.
            page.run(f"{tab}[0].parentNode.querySelector('.extra-tab-close').click()")
            page.wait(f"document.getElementById('bi-b-set-{gear}').hidden")
            assert page.run(
                f"document.getElementById('bi-b-set-{gear}').closest('.kp-stage') !== null"
            )
            assert page.run(f"document.getElementById('bi-b-gear-{gear}').ariaExpanded") == "false"

        # The source file location is in Data input's settings.
        page.gear("source")
        page.see("bi-b-v-info", "共用資料夾")
