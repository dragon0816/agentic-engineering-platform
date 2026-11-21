"""Creating a domain in the page, and switching with no stale rows.

`docs/phases/BI_PAGE_SIMPLE.md` §9, §10. Owner, 2026-11-05: 「需要讓使用者可以create domain」;
「切到ingest, testing時，也要帶出這個domain相關的skill, tool, benchmark question, dashboard」.
A real browser on fictional data.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok
from test_vault_asking_e2e import _bi_host, _Model, _served

from aep_bi.cards.store import BiStore

AIDC = "applications/aidc/sources"
WIRELESS = "applications/wireless/sources"
NEW = "applications/automotive/sources"
# 虛構範例.
QUESTIONS = {"aidc-q": "aidc", "wl-q": "wireless"}
TIMES_OUT = 60
QUIET_READS = "window.__aepWatch.open.length === 0"


def _labels(page: BiPage) -> list[str]:
    found = page.run(
        "[...document.getElementById('bi-b-src-folder').options].map((o) => o.textContent)"
        ".join('|')"
    )
    return str(found).split("|")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_domain_is_created_in_the_row_and_becomes_the_working_domain(tmp_path: Path) -> None:
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
    for slug, home in QUESTIONS.items():
        body = {"question": f"虛構題 {slug}？", "must": ["好"], "slug": slug, "home": home}
        _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/checks", body))
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "create" if shots else None
        ) as page:
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            page.wait("(bi.build.homes || []).length > 0")
            page.wait("document.getElementById('bi-b-src-folder').options.length > 1")

            # -- readable names, the values stay ------------------------------------------
            labels = _labels(page)
            assert labels[:2] == ["全部領域", "AIDC"]
            assert not any("/" in label or "（" in label for label in labels)
            assert page.run(
                f"[...document.getElementById('bi-b-src-folder').options]"
                f".find((o) => o.textContent === 'AIDC').value === '{AIDC}'"
            )

            # -- a name that exists says so; nothing is made ------------------------------
            page.click("#bi-b-home-new")
            assert not page.run("document.getElementById('bi-b-home-form').hidden")
            page.set_value("bi-b-home-name", "aidc")
            page.click("#bi-b-home-go")
            page.see("bi-b-home-err", "已經有領域")
            assert len(_labels(page)) == len(labels)
            page.shoot("exists")

            # -- a Chinese name needs a folder, and then shows ----------------------------
            page.set_value("bi-b-home-name", "車用電子")
            page.click("#bi-b-home-go")
            page.see("bi-b-home-err", "資料夾名稱")
            page.set_value("bi-b-home-folder", "automotive")
            page.click("#bi-b-home-go")
            page.wait(f"document.getElementById('bi-b-src-folder').value === '{NEW}'")
            assert "車用電子" in _labels(page)
            assert page.run("document.getElementById('bi-b-home-form').hidden")
            assert not page.run("document.getElementById('bi-b-home-new').hidden")
            assert page.run("biScope()") == "automotive"
            page.see("bi-notice", "還沒 commit")
            assert "applications/automotive/" in page.text_of("bi-notice")

            # -- it is empty, and says what that means ------------------------------------
            page.wait("!document.getElementById('bi-b-scope-empty').hidden")
            empty = page.text_of("bi-b-scope-empty")
            # One line and a 新增規則 link (S5); the folder of examples is in the guide.
            assert "Signal" in empty and "library/skill-review" not in empty
            assert page.run(
                "[...document.querySelectorAll('#bi-b-scope-empty button')]"
                ".map((b) => b.textContent).join() === '新增規則'"
            )
            page.shoot("created")

            # -- a new rule applies to it, unpushed (acceptance F9) --------------------------
            # The step-2 AI session is gone (owner 2026-11-20): 新增規則 opens the rule form,
            # prefilled with the new domain's folder.
            page.wait("(bi.skills && bi.skills.folders || []).length > 0", TIMES_OUT)
            page.click_text("#bi-b-scope-empty", "新增規則")
            page.wait("!document.getElementById('bi-b-sk-form').hidden")
            assert page.run("document.getElementById('bi-b-sk-applies').value") == NEW
            assert page.run("document.getElementById('bi-b-sk-name').readOnly") is False
            page.shoot("new-rule-folder")
            page.set_value("bi-b-sk-name", "automotive-extract")
            page.set_value("bi-b-sk-body", "虛構電源廠是 Account。")
            page.click("#bi-b-sk-form button[type=submit]")
            page.see("bi-notice", "存成第 1 版")
            assert "push 後大家才會用到" in page.text_of("bi-notice")
            page.wait("document.getElementById('bi-b-sk-form').hidden")

            # -- a file goes to it at once -------------------------------------------------
            page.upload("car.md", "# 虛構\n", "text/markdown")
            assert page.run("bi.build.sources.find((s) => s.name === 'car.md').folder") == NEW

            # -- kept across a reload ------------------------------------------------------
            page.reload()
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            page.wait(f"document.getElementById('bi-b-src-folder').value === '{NEW}'", TIMES_OUT)

            # -- switching: at once, and an old reply cannot bring old rows back ------------
            page.choose("bi-b-src-folder", AIDC)
            page.stage("test")
            page.see("bi-b-bq-list", "虛構題 aidc-q")
            page.wait("!!bi.benchReply")
            page.wait("window.__aepWatch.open.length === 0", TIMES_OUT)
            # The next read of the questions answers only when told, after the switch.
            page.run(
                "(() => { const was = window.fetch; window.__hold = [];"
                " window.fetch = async (...args) => { const reply = await was(...args);"
                " if (String(args[0]).includes('/checks')) {"
                " await new Promise((go) => window.__hold.push(go)); }"
                " return reply; }; })()"
            )
            page.run("biBench(bi.verVault)")
            page.wait("window.__hold.length === 1", TIMES_OUT)
            page.choose("bi-b-src-folder", WIRELESS)
            # No wait: it was drawn inside the change.
            rows = page.text_of("bi-b-bq-list")
            assert "虛構題 wl-q" in rows and "虛構題 aidc-q" not in rows
            assert page.text_of("bi-b-bench-state").startswith("1 題")
            assert "wireless" in page.text_of("bi-b-run-why")
            page.wait("window.__hold.length === 2", TIMES_OUT)
            page.run("window.__hold.splice(0).forEach((go) => go())")
            page.wait("window.__aepWatch.open.length === 0", TIMES_OUT)
            rows = page.text_of("bi-b-bq-list")
            assert "虛構題 wl-q" in rows and "虛構題 aidc-q" not in rows
            assert page.text_of("bi-b-bench-state").startswith("1 題")

            # -- a read from before a save does not close the question being edited ------------
            # It used to clear the editor, so that saving next made a second question.
            page.run("window.__hold = { push: (go) => go(), length: 0, splice: () => [] }")
            page.wait(QUIET_READS, TIMES_OUT)
            page.run(
                "(() => { const was = call; call = async (path, body) => {"
                " const reply = await was(path, body);"
                " if (!body && path.includes('/checks') && !window.__oldRead) {"
                " await new Promise((go) => { window.__oldRead = go; }); }"
                " if (path.endsWith('/status') && !window.__status) {"
                " await new Promise((go) => { window.__status = go; }); }"
                " return reply; }; })()"
            )
            page.run("biBench(bi.verVault)")
            page.wait("!!window.__oldRead", TIMES_OUT)
            page.run(
                "biBenchSave({question: '虛構題 剛存的？', must: '好', home: 'wireless',"
                " slug: 'fresh'}).then((reply) => { window.__saved = reply.unit; })"
            )
            # Saved, and its own read of the list has not started yet.
            page.wait("!!window.__status", TIMES_OUT)
            page.run(
                "biBqPick({unit: 'check:question:main/fresh', slug: 'fresh', set: 'main',"
                " question: '虛構題 剛存的？', must: ['好'], must_not: [], home: 'wireless'})"
            )
            # The read from before the save answers now: it is read again, not drawn.
            page.run("window.__oldRead()")
            page.wait(
                "document.getElementById('bi-b-bq-list').textContent.includes('虛構題 剛存的')",
                TIMES_OUT,
            )
            assert page.run("bi.bqSel && bi.bqSel.slug === 'fresh'")
            page.run("window.__status()")
            page.wait("!!window.__saved", TIMES_OUT)
            page.wait(QUIET_READS, TIMES_OUT)
            assert page.run("bi.bqSel && bi.bqSel.slug === 'fresh'")

            # -- a new domain has no questions: nothing is borrowed from another ------------
            page.choose("bi-b-src-folder", NEW)
            rows = page.text_of("bi-b-bq-list")
            assert "虛構題" not in rows
            assert page.text_of("bi-b-bench-state").startswith("0 題")
            assert page.run("document.getElementById('bi-b-bench-run').disabled")
            page.shoot("empty-step3")

            # -- under 全部領域 no folder is chosen for the person: no 新增規則 is offered ------
            # (the rule form is reached from a domain's own empty notice, owner 2026-11-20)
            page.choose("bi-b-src-folder", "sources")
            page.wait(QUIET_READS, TIMES_OUT)
            assert not page.run("biScope()")
            assert page.run("document.getElementById('bi-b-scope-empty').hidden")
            assert not page.run("[...document.querySelectorAll('#bi-b-scope-empty button')].length")
            assert page.run("!document.getElementById('bi-b-sk-new')")
