"""The BI page's first row: the vault, then the working domain, above every tab.

Owner, 2026-11-05: 「第一件事情是選擇vault，或者是新增一個vault，接著再選domain」. The working
domain sets what the Dashboard and the card tab read. A real browser on fictional data.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok
from test_vault_asking_e2e import _bi_host, _Model, _served

from aep_bi.cards import vault
from aep_bi.cards.store import BiStore

AIDC = "applications/aidc/sources"
QUIET = "window.__aepWatch.open.length === 0"
VISIBLE = (
    "(id) => { const e = document.getElementById(id); return !!e && e.offsetParent !== null; }"
)


def _tops(page: BiPage, *selectors: str) -> list[float]:
    found = page.run(
        f"JSON.stringify({json.dumps(selectors)}.map((s) =>"
        " document.querySelector(s).getBoundingClientRect().top))"
    )
    return [float(x) for x in json.loads(str(found))]


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_someone_with_no_vault_starts_at_creating_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    # A fictional OneDrive, so that nothing of this PC's own shows (acceptance F3).
    profile = tmp_path / "profile"
    onedrive = profile / "OneDrive - Fake Co"
    onedrive.mkdir(parents=True)
    # The variables are read in `test_bi_vault_folder_check`; the browser needs the real profile.
    monkeypatch.setattr(vault, "onedrive_folders", lambda: [str(onedrive)])
    # A colleague's vault holding only 海事, for this PC to join (second-PC finding F22).
    _other_config, other_layout = _bi_host(tmp_path / "other")
    other, shared = other_layout.workspace_root, tmp_path / "shared"
    shared.mkdir()
    made = _ok(
        _call(
            other,
            "POST",
            "/api/bi/vaults",
            {"path": str(shared), "title": "Marine", "schema": "bi.schema/v1.1",
             "author": "bob", "default_pack": False},
        )
    )  # fmt: skip
    theirs = str(made["vault"]["id"])
    home = {"name": "海事", "folder": "marine"}
    _ok(_call(other, "POST", f"/api/bi/vaults/{theirs}/homes", home))
    _ok(_call(other, "POST", f"/api/bi/vaults/{theirs}/commit", {"purpose": "新增領域"}))
    _ok(_call(other, "POST", f"/api/bi/vaults/{theirs}/push", {}))
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "top" if shots else None
        ) as page:
            page.wait(QUIET, 60)
            # Knowledge opens here by itself on a PC with no wiki pipeline (acceptance F1).
            page.run(
                "localStorage.removeItem('kn-pane-chosen'); knChosen = false;"
                " knShow('pipeline', false); loadKnowledgeTab()"
            )
            page.wait(
                "!document.getElementById('kn-pane-bi').hidden"
                " && document.getElementById('kn-pane-pipeline').hidden",
                60,
            )
            page.wait(QUIET, 60)
            # The guide shows 新增知識庫; they live in 管理 since 2026-11-19 (S3).
            assert "go" in str(page.run("document.getElementById('bi-empty-new').className"))
            # Joining is as much a first step as creating (F21).
            assert "go" in str(page.run("document.getElementById('bi-empty-join').className"))
            assert page.run("document.getElementById('bi-b-src-folder-box').hidden")
            assert page.run(f"({VISIBLE})('bi-empty-new') && ({VISIBLE})('bi-empty-join')")
            page.shoot("first-time")

            # -- the form: the schema under 進階 on the newest, the folder checked ------------
            page.click("#bi-empty-new")
            page.wait("!document.getElementById('bi-b-v-form').hidden")
            assert page.run(
                "(() => { const d = document.getElementById('bi-b-v-schema').closest('details');"
                " return !!d && !d.open && d.textContent.includes('進階'); })()"
            )
            assert page.run(
                "document.getElementById('bi-b-v-schema').value"
                " === bi.schemas.filter((s) => s.source === 'shipped').pop().ref"
            )
            page.wait(
                "[...document.querySelectorAll('#bi-b-v-path-suggest button')]"
                ".some((b) => b.textContent.includes('OneDrive - Fake Co'))",
                60,
            )
            typed = json.dumps(str(tmp_path / "nowhere"))
            page.run(
                f"{{ const p = document.getElementById('bi-b-v-path'); p.value = {typed};"
                " p.dispatchEvent(new Event('input')); }"
            )
            page.see("bi-b-v-path-check", "找不到資料夾")
            page.run("document.querySelector('#bi-b-v-path-suggest button').click()")
            page.see("bi-b-v-path-check", "可以用")
            assert page.run("document.getElementById('bi-b-v-path').value") == str(onedrive)
            page.shoot("new-vault-form")

            # -- a Chinese name asks for an id instead of making vault-xxxxxx (F4) -----------
            page.set_value("bi-b-v-title", "海事市場")
            page.click("#bi-b-v-go")
            page.see("bi-b-v-err", "請填知識庫 id")
            assert page.run("document.activeElement.id") == "bi-b-v-id"
            page.set_value("bi-b-v-id", "marine-intel")
            page.click("#bi-b-v-go")
            page.see("bi-notice", "已建立")
            assert (onedrive / "marine-intel" / "repo.json").is_file()
            # A new vault has no domain in use: it says so and points at 新增領域 (F22).
            page.see("bi-notice", "還沒有領域")
            page.wait("document.activeElement.id === 'bi-b-home-new'", 60)
            assert (
                page.run("bi.build.homes.filter((h) => !h.home.startsWith('library/')).length") == 0
            )

            # -- joining a vault of one domain starts in it (F22), from 管理 ------------------
            page.click("#bi-b-v-menu > summary")
            page.wait(f"({VISIBLE})('bi-b-v-join')")
            page.click("#bi-b-v-join")
            assert not page.run("document.getElementById('bi-b-v-menu').open")
            page.wait("!document.getElementById('bi-b-v-form').hidden")
            page.set_value("bi-b-v-path", str(shared / theirs))
            page.set_value("bi-b-v-author", "carol")
            # The button waits until the page has loaded the vault just created.
            page.wait("!document.getElementById('bi-b-v-go').disabled", 120)
            page.click("#bi-b-v-go")
            page.wait(
                "document.getElementById('bi-b-src-folder').value"
                " === 'applications/marine/sources'"
                " || document.getElementById('bi-b-v-err').textContent !== ''",
                60,
            )
            assert page.text_of("bi-b-v-err") == ""
            assert page.run("biVaultOf(biDataset()).id") == theirs
            labels = page.run(
                "[...document.getElementById('bi-b-src-folder').options]"
                ".map((o) => o.textContent).join('|')"
            )
            assert str(labels).split("|")[:2] == ["全部領域", "海事"]
            assert page.run(
                "document.querySelector('#bi-b-src-folder optgroup').label.includes('不是領域')"
            )
            page.shoot("joined")

            # -- withdrawing a colleague's source says whose and for whom (F23) --------------
            page.run("biWithdrawForm({id: 'x', name: 'fake.md', added_by: 'bob'})")
            withdraw = page.text_of("bi-b-src-withdraw")
            assert "bob" in withdraw and "不是你的" in withdraw and "所有人" in withdraw
            page.run("biWithdrawForm({id: 'y', name: 'own.md', added_by: 'carol'})")
            assert "不是你的" not in page.text_of("bi-b-src-withdraw")
            assert "所有人" in page.text_of("bi-b-src-withdraw")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_row_is_first_on_every_tab_and_the_tabs_read_under_it(tmp_path: Path) -> None:
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
             "author": "alice", "default_pack": False},
        )
    )  # fmt: skip
    dataset, vault_id = str(made["vault"]["dataset"]), str(made["vault"]["id"])
    # Domains are listed when something is in them (F22): a question each.
    for slug, home in (("aidc-q", "aidc"), ("wl-q", "wireless")):
        body = {"question": f"虛構題 {slug}？", "must": ["好"], "slug": slug, "home": home}
        _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/checks", body))
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "top" if shots else None
        ) as page:
            page.choose("bi-dataset", dataset)
            page.wait("document.getElementById('bi-b-src-folder').options.length > 1", 60)
            page.wait(QUIET, 60)
            assert page.run("document.getElementById('bi-empty-state').hidden")

            # -- on the one row, vault then domain, above the tabs, above the stepper ---------
            page.click("#bi-views [data-bi-view=build]")
            vault_y, domain_y, tabs_y, steps_y = _tops(
                page, "#bi-dataset", "#bi-b-src-folder", "#bi-views", "#bi-stepper"
            )
            assert abs(vault_y - domain_y) < 4, (vault_y, domain_y)
            assert domain_y < tabs_y < steps_y
            lefts = page.run(
                "document.getElementById('bi-dataset').getBoundingClientRect().left"
                " < document.getElementById('bi-b-src-folder').getBoundingClientRect().left"
            )
            assert lefts
            # New and join are in the folded 管理 menu (owner 2026-11-19, S3), with the former
            # 進階：資料集與發佈 (B1); there is no folded section at the foot any more.
            assert not page.run("document.getElementById('bi-b-v-menu').open")
            folded = "(id) => !!document.getElementById(id).closest('details:not([open])')"
            assert page.run(f"({folded})('bi-b-v-new') && ({folded})('bi-b-v-join')")
            page.click("#bi-b-v-menu > summary")
            for item in ("bi-b-v-new", "bi-b-v-join", "bi-new", "bi-install", "bi-demo"):
                assert page.run(f"({VISIBLE})('{item}')"), item
            page.click("#bi-b-v-menu > summary")
            assert page.run("document.getElementById('bi-advanced').tagName") == "DIV"
            # Step 1 starts at the files.
            assert page.run(
                "document.querySelector('.kp-stage[data-stage=source] #bi-b-class') !== null"
                " && document.querySelector('.kp-stage[data-stage=source] #bi-dataset') === null"
            )
            page.shoot("build")

            # -- scrolled, the step bar stays whole under the row (acceptance F4) ------------
            page.run("biScroller().scrollTop = 900")
            assert float(page.run("biScroller().scrollTop")) > 100
            assert page.run(
                "(() => { const r = document.getElementById('bi-top-row').getBoundingClientRect(),"
                " s = document.getElementById('bi-stepper').getBoundingClientRect();"
                " return s.top >= r.bottom - 1 && s.bottom < r.bottom + 120; })()"
            )
            page.shoot("build-scrolled")
            page.run("biScroller().scrollTop = 0")

            # -- the status line goes with the vault, on every tab ----------------------------
            page.wait("document.getElementById('bi-b-v-state').textContent.includes('張卡片')", 60)

            # -- the Dashboard: the working domain decides, so there is nothing to choose -----
            page.choose("bi-b-src-folder", "sources")
            page.click("#bi-views [data-bi-view=dashboard]")
            page.wait(QUIET, 60)
            assert page.run(f"({VISIBLE})('bi-dataset') && ({VISIBLE})('bi-b-src-folder')")
            assert page.run(f"({VISIBLE})('bi-domain')"), "全部領域 still chooses a domain here"
            page.shoot("dashboard-all")
            page.choose("bi-b-src-folder", AIDC)
            page.wait(QUIET, 60)
            assert not page.run(f"({VISIBLE})('bi-domain')")
            assert str(page.run("document.getElementById('bi-domain').value")).lower() == "aidc"
            page.shoot("dashboard-aidc")

            # -- the card tab: its filter starts on the working domain, and stays changeable --
            page.click("#bi-views [data-bi-view=cards]")
            page.wait(QUIET, 60)
            assert (
                str(page.run("document.getElementById('bi-card-domain').value")).lower() == "aidc"
            )
            assert page.run(f"({VISIBLE})('bi-card-domain')")
            page.shoot("cards-aidc")
            page.choose("bi-card-domain", "")
            page.wait(QUIET, 60)
            assert page.run("document.getElementById('bi-card-domain').value") == ""
            # The next choice of domain sets it again; back to 全部領域, every domain.
            page.choose("bi-b-src-folder", "applications/wireless/sources")
            page.wait(QUIET, 60)
            assert (
                str(page.run("document.getElementById('bi-card-domain').value")).lower()
                == "wireless"
            )
            page.choose("bi-b-src-folder", "sources")
            page.wait(QUIET, 60)
            assert page.run("document.getElementById('bi-card-domain').value") == ""

            # -- a plain dataset has no domain part, and the vault part stays ----------------
            page.choose("bi-dataset", "demo")
            page.wait("document.getElementById('bi-b-src-folder-box').hidden", 60)
            assert page.run(f"({VISIBLE})('bi-dataset') && ({VISIBLE})('bi-b-v-menu')")

            # -- sticky: both stay when the page scrolls --------------------------------------
            page.choose("bi-dataset", dataset)
            page.wait("!document.getElementById('bi-b-src-folder-box').hidden", 60)
            page.click("#bi-views [data-bi-view=build]")
            page.wait(QUIET, 60)
            page.run(
                "document.querySelector('.kp-stage[data-stage=source]')"
                ".scrollIntoView({block: 'end'})"
            )
            assert page.run(
                "(() => { const r = document.getElementById('bi-dataset').getBoundingClientRect();"
                " return r.top >= 0 && r.bottom <= innerHeight; })()"
            )

            # -- a phone: stacked, nothing pushes the page sideways ---------------------------
            page.browser.page().call(
                "Emulation.setDeviceMetricsOverride",
                width=390,
                height=844,
                deviceScaleFactor=1,
                mobile=True,
            )
            page.wait(
                "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
            )
            vault_y, domain_y = _tops(page, "#bi-dataset", "#bi-b-src-folder")
            assert domain_y > vault_y
            page.run("window.scrollTo(0, 0)")
            page.shoot("phone")
