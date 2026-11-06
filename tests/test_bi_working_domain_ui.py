"""The working domain in the page (`docs/phases/BI_PAGE_SIMPLE.md` §9), in a real browser on
fictional data (owner, 2026-11-05: 「依選擇的domain來做後續的ingest和testing」).

One combobox above the stepper; steps 1, 2 and 3 follow it; other domains' runs stay reachable,
and a regression in another domain is in sight before a push.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok
from test_vault_asking_e2e import _bi_host, _Model, _served

from capabilities.bi_cards import vault
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore
from host_runtime import bi_bench

AIDC = "applications/aidc/sources"
WIRELESS = "applications/wireless/sources"
# 虛構範例: fictional rows.
TECH_CSV = "技術,領域,成熟度\nEtherCAT,robotics,mature\n"


def _skill(workspace: Path, vault_id: str, name: str, folder: str) -> None:
    _ok(
        _call(
            workspace,
            "POST",
            f"/api/bi/vaults/{vault_id}/skills",
            {"name": name, "role": "extract", "applies_to": [folder], "card_types": [],
             "body": "虛構規則"},
        )
    )  # fmt: skip


def _question(workspace: Path, vault_id: str, slug: str, home: str | None) -> None:
    body = {"question": f"虛構題 {slug}？", "must": ["好"], "slug": slug, "home": home}
    _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/checks", body))


def _q_row(slug: str) -> str:
    return f"document.querySelector('#bi-b-bq-list tr[data-unit=\"check:question:main/{slug}\"]')"


def _rows(page: BiPage) -> str:
    return page.text_of("bi-b-sources")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_one_working_domain_carries_through_the_three_steps(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    BiStore(workspace, "demo").create("bi.schema/v1.1")
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(
        _call(
            workspace,
            "POST",
            "/api/bi/vaults",
            {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
             "author": "alice"},
        )
    )  # fmt: skip
    dataset, vault_id = str(made["vault"]["dataset"]), str(made["vault"]["id"])
    staging = Staging(workspace, dataset)
    theirs = staging.add_source("wl.csv", text=TECH_CSV, actor="alice", folder=WIRELESS)
    staging.add_source("aidc.md", text="# AIDC\n", actor="alice", folder=AIDC)
    staging.add_source("root.md", text="# 根\n", actor="alice", folder="sources")
    _skill(workspace, vault_id, "aidc-rule", AIDC)
    _skill(workspace, vault_id, "wl-rule", WIRELESS)
    _question(workspace, vault_id, "mine", "aidc")
    _question(workspace, vault_id, "theirs", "wireless")
    _question(workspace, vault_id, "whole", None)

    # A whole-vault run finds a wireless regression; a newer run of aidc on the same content is
    # all green. Asked by this test: the point here is what the page shows of the reports.
    def ask(question: str, side: bi_bench.Side) -> dict[str, Any]:
        wrong = side == "working" and "theirs" in question
        return {"ok": True, "answer": "不知道" if wrong else "好"}

    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "scope" if shots else None
        ) as page:
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            page.wait("document.querySelectorAll('#bi-b-sources tbody tr').length === 3")
            page.wait(f"[...bi.build.homes].some((h) => h.folder === {json.dumps(AIDC)})")

            # -- first visit: everything shows, and nothing can be added to no domain ------
            assert page.text_of("bi-b-src-count").startswith("顯示 3／3 份・已選 ")
            assert page.run("document.getElementById('bi-b-src-folder').value") == "sources"
            assert (
                page.run(
                    "document.getElementById('bi-b-src-folder').selectedOptions[0].textContent"
                )
                == "全部領域"
            )
            page.attach("later.md", "# 之後\n", "text/markdown")
            assert page.run("document.getElementById('bi-b-upload').disabled")
            assert not page.run("document.getElementById('bi-b-scope-need').hidden")
            page.shoot("first-visit")

            # -- 全部領域 is an overview: everything shows, nothing is added, no source ingested --
            page.choose_row_source("aidc.md")
            assert page.run("document.getElementById('bi-b-next1').disabled")
            shut = page.run(
                "[...document.querySelectorAll('#bi-substeps [data-stage=method]')]"
                ".every((b) => b.disabled)"
            )
            assert shut
            page.stage("test")
            page.wait("document.querySelectorAll('#bi-b-bq-list tbody tr').length === 3")
            for ident in ("bi-b-bq-add", "bi-b-qa-open", "bi-b-an-new", "bi-b-bq-pane"):
                assert page.run(f"document.getElementById({ident!r}).hidden"), ident
            assert not page.run("document.getElementById('bi-b-overview').hidden")
            assert "這次跑全部 3 題" in page.text_of("bi-b-run-why")
            page.run("document.querySelector('#bi-b-bq-list tbody tr').click()")
            assert page.run("!bi.bqSel")
            # The table can be seen: with no editor beside it, it once had no height at all.
            page.run("document.getElementById('bi-b-bench').open = true")
            assert page.run(
                "document.querySelector('#bi-b-bq-list tbody tr').offsetHeight > 0"
                " && document.getElementById('bi-b-bq-list').getBoundingClientRect().height > 60"
            )
            page.run("document.getElementById('bi-b-bench').open = false")
            page.shoot("overview-step3")
            page.stage("source")

            # -- a domain: step 1 follows, the file goes to it -----------------------------
            page.choose("bi-b-src-folder", AIDC)
            page.wait(
                "document.getElementById('bi-b-src-count').textContent"
                ".startsWith('顯示 1／3 份・已選 ')"
            )
            assert "aidc.md" in _rows(page) and "wl.csv" not in _rows(page)
            assert not page.run("document.getElementById('bi-b-upload').disabled")
            assert page.run("document.getElementById('bi-b-scope-need').hidden")
            page.click("#bi-b-upload")
            page.see("bi-b-sources", "later.md")
            assert page.run("bi.build.sources.find((s) => s.name === 'later.md').folder") == AIDC
            page.shoot("step1")

            # -- kept across a reload, per dataset ----------------------------------------
            page.reload()
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            page.wait(f"document.getElementById('bi-b-src-folder').value === {json.dumps(AIDC)}")
            page.wait(
                "document.getElementById('bi-b-src-count').textContent"
                ".startsWith('顯示 2／4 份・已選 ')"
            )

            # -- in sight on every step -----------------------------------------------------
            page.choose_row_source("aidc.md")
            for stage in ("method", "test"):
                page.stage(stage)
                assert not page.run("document.getElementById('bi-b-src-folder-box').hidden")
                top = page.run(
                    "document.getElementById('bi-b-src-folder-box').getBoundingClientRect().height"
                )
                assert float(top) > 0
                # Scrolled to the end of a long step, it is still there.
                page.run("[...document.querySelectorAll('#bi-view-build .kp-stage')]"
                         ".find((s) => !s.hidden).scrollIntoView({block: 'end'})")  # fmt: skip
                assert page.run(
                    "(() => { const r = document.getElementById('bi-b-src-folder')"
                    ".getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; })()"
                ), f"out of sight on {stage}"

            # -- step 2: skills and tools of this domain ------------------------------------
            page.wait("document.getElementById('bi-b-sk-list').textContent.includes('aidc-rule')")
            skills = page.text_of("bi-b-sk-list")
            assert "wl-rule" not in skills and "其他領域還有 1 條" in skills
            assert "classify" in skills  # applies to every source

            # -- step 3: this domain's questions, and the regression elsewhere stays in sight
            # (Run here: the file added above changed the content, so an earlier run no longer
            # counts, and the page says that too.)
            page.stage("test")
            page.wait("document.getElementById('bi-b-bench').hidden === false")
            bi_bench.run(workspace, vault_id, ask=ask, extract=lambda c: [], actor="alice")
            bi_bench.run(
                workspace, vault_id, ask=ask, extract=lambda c: [], actor="alice", home="aidc"
            )
            page.run("biBench(bi.verVault)")
            page.wait("document.getElementById('bi-b-bench-report').textContent.includes('涵蓋')")
            page.wait("document.getElementById('bi-b-bq-list').textContent.includes('虛構題 mine')")
            questions = page.text_of("bi-b-bq-list")
            assert "虛構題 theirs" not in questions
            # What has no domain yet shows apart, closed, and is not this domain's.
            assert page.run(
                "!document.getElementById('bi-b-bq-waiting').open"
                " && document.getElementById('bi-b-bq-waiting').textContent"
                ".includes('虛構題 whole')"
            )
            assert page.text_of("bi-b-bench-state").startswith("1 題")
            assert "這次跑 aidc 的 1 題" in page.text_of("bi-b-run-why")
            report = page.text_of("bi-b-bench-report")
            assert "涵蓋 aidc 1 題" in report
            assert "Push 會被擋" in report and "（wireless）" in report
            assert "虛構題 theirs" in report
            page.shoot("step3")

            # -- commit says what it carries ------------------------------------------------
            # By the names people know them by (the list showed the folder's key before).
            label = "bi.build.homes.find((h) => h.home === %r).label"
            wireless, aidc = page.run(label % "wireless"), page.run(label % "aidc")
            page.wait(
                "document.getElementById('bi-b-ver-pending').textContent"
                f".includes({json.dumps(wireless)})"
            )
            pending = page.text_of("bi-b-ver-pending")
            assert str(aidc) in pending and "這次 commit 也會帶上其他領域的改動" in pending

            # -- a question's domain is a combobox: 全庫 and the vault's homes ---------------
            homes = page.run(
                "[...document.getElementById('bi-b-bq-home').options]"
                ".map((o) => o.textContent).join('/')"
            )
            assert str(homes).startswith("全庫/") and "aidc" in str(homes)
            # A new one starts on the working domain.
            page.click("#bi-b-bq-add")
            assert page.run("document.getElementById('bi-b-bq-home').value") == "aidc"

            def edit(slug: str) -> None:
                page.run(
                    "document.querySelector("
                    f"'#bi-b-bq-list tr[data-unit=\"check:question:main/{slug}\"]').click()"
                )
                page.see("bi-b-bq-title", "修改題目")

            def home_of(unit: str) -> Any:
                return vault.Vault(workspace, vault_id).repo.working_units()[unit].get("home")

            # An old question shows 全庫, and gaining a domain keeps its set and slug.
            edit("whole")
            assert page.run("document.getElementById('bi-b-bq-home').value") == ""
            assert "全庫" in page.text_of("bi-b-bq-list")
            page.choose("bi-b-bq-home", "aidc")
            page.click("#bi-b-bq-save")
            page.wait(_q_row("whole") + ".textContent.includes('aidc')")
            assert home_of("check:question:main/whole") == "aidc"

            # Saved again without touching it, it keeps its domain; back to 全庫, the field goes.
            page.wait("document.getElementById('bi-b-bq-home').value === 'aidc'")
            page.set_value("bi-b-bq-must", "好, 再好")
            page.click("#bi-b-bq-save")
            page.wait("document.getElementById('bi-b-bq-must').value === '好, 再好'")
            page.wait(_q_row("whole") + ".textContent.includes('再好')")
            assert home_of("check:question:main/whole") == "aidc"
            page.choose("bi-b-bq-home", "")
            page.click("#bi-b-bq-save")
            page.wait(_q_row("whole") + ".textContent.includes('全庫')")
            assert home_of("check:question:main/whole") is None

            # Given to another domain, it leaves this list, and the editor starts afresh.
            edit("mine")
            page.choose("bi-b-bq-home", "wireless")
            page.click("#bi-b-bq-save")
            page.wait("!" + _q_row("mine"))
            page.see("bi-b-bq-title", "新增題目")
            assert home_of("check:question:main/mine") == "wireless"
            page.shoot("step3-editor")

            # -- the AI panel knows, and closes on a change ---------------------------------
            page.click("#bi-b-qa-open")
            page.wait("!document.getElementById('bi-ai').hidden")
            page.see("bi-ai-target", "工作領域 aidc")
            assert page.run("bi.ai.scope") == "aidc"
            page.choose("bi-b-src-folder", WIRELESS)
            page.wait("document.getElementById('bi-ai').hidden")
            page.wait(
                "document.getElementById('bi-b-bq-list').textContent.includes('虛構題 theirs')"
            )

            # -- a run in another domain is never opened by itself, and is one choice away --
            source_id = theirs["id"]
            page.run(
                f"biCall('/api/bi/runs', {{dataset: {json.dumps(dataset)}, kind: 'ingest',"
                f" source_id: {json.dumps(source_id)}, path: 'rules'}})"
                ".then((r) => window.__run = r.run.id)"
            )
            page.wait("window.__run")
            page.wait(
                "biCall('/api/bi/runs?dataset=' + encodeURIComponent(biDataset()))"
                ".then((r) => window.__runs = r.runs) && (window.__runs || [])"
                ".some((r) => r.id === window.__run && r.status === 'review')"
            )
            page.choose("bi-b-src-folder", AIDC)
            page.run("biBuildRuns()")
            page.wait("(bi.build.waiting || []).length === 1")
            page.stage("review")
            page.wait("!!document.querySelector('#bi-b-run-pick optgroup[label=其他領域] option')")
            assert page.run("document.getElementById('bi-b-run-pick').value") == ""
            assert not page.run("bi.build.run")
            page.shoot("review-other-domain")
            page.choose("bi-b-run-pick", str(page.run("window.__run")))
            page.wait("bi.build.run && bi.build.run.id === window.__run")
            page.choose("bi-b-src-folder", WIRELESS)
            page.wait(
                "!document.querySelector('#bi-b-run-pick optgroup[label=其他領域]')"
                " && document.getElementById('bi-b-run-pick').value === window.__run"
            )

            # -- a plain dataset has no choice to make --------------------------------------
            page.stage("source")
            page.choose("bi-dataset", "demo")
            page.wait("document.getElementById('bi-b-src-folder-box').hidden")
            page.attach("plain.md", "# 平\n", "text/markdown")
            assert not page.run("document.getElementById('bi-b-upload').disabled")
            assert page.run("document.getElementById('bi-b-scope-need').hidden")
