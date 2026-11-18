"""A wiki knowledge repository on the Knowledge page, in a real browser (R4b).

The real Agent Web server in a temporary workspace: a copy of a fictional wiki
folder is imported as a repository from the page, this PC's intake and
question folders are set, an original is pulled, and step 3's 「版本」 area
commits, pushes (with the untested note), tags and publishes after the
person's confirmation. The sandbox-only push and candidate cards are hidden for
a repository. Screenshots in `.scratch/knowledge-repo/`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from test_knowledge_repo_pipeline import QUESTION, served  # noqa: F401 - the fixture
from test_knowledge_repos_api import _wiki_folder

from host_runtime.web import AgentWebServer
from knowledge import wiki_repos, wiki_repos_write

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "knowledge-repo"


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_a_repository_on_the_knowledge_page(served: AgentWebServer, tmp_path: Path) -> None:  # noqa: F811
    from integrations.browser import Browser, BrowserError

    server = served
    workspace = server.web.runtime.layout.workspace_root
    source = _wiki_folder(tmp_path / "src")
    drive, intake, questions = tmp_path / "drive", tmp_path / "intake", tmp_path / "questions"
    drive.mkdir()
    (intake / "Products").mkdir(parents=True)
    (intake / "Products" / "tester-z.txt").write_bytes(b"Tester Z has K3.\n")
    (questions / "products").mkdir(parents=True)
    (questions / "products" / "q1.md").write_bytes(QUESTION.encode("utf-8"))
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def run(expression: str) -> Any:
        return browser._evaluate(expression)

    def wait(expression: str, seconds: float = 60) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                value = run(expression)
            except BrowserError:
                value = None
            if value:
                return value
            time.sleep(0.1)
        raise AssertionError(expression)

    def click(selector: str) -> None:
        run(f"document.querySelector({json.dumps(selector)}).click()")

    def text_of(element_id: str) -> str:
        return str(run(f"document.getElementById('{element_id}').textContent"))

    def has(element_id: str, words: str) -> str:
        return f"document.getElementById('{element_id}').textContent.includes({json.dumps(words)})"

    def hidden(element_id: str) -> bool:
        return bool(run(f"document.getElementById('{element_id}').hidden"))

    def set_value(element_id: str, value: str) -> None:
        run(f"document.getElementById('{element_id}').value = {json.dumps(value)}")

    def button(box: str, label: str) -> str:
        """A button in `box` by its words."""
        return (
            f"[...document.querySelectorAll('#{box} button')]"
            f".find((b) => b.textContent.trim() === {json.dumps(label)})"
        )

    def size(width: int, height: int, mobile: bool) -> None:
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=height,
            deviceScaleFactor=1,
            mobile=mobile,
        )

    def shoot(name: str) -> None:
        time.sleep(0.25)
        browser.screenshot(shots / f"{name}.png")

    try:
        size(1366, 1000, False)
        browser.navigate(server.address)
        wait("!!document.getElementById('nav-knowledge')")
        click("#nav-knowledge")
        wait(has("kp-repos", "還沒有知識庫"))

        # -- import a copy of a wiki folder from the page ------------------------------------
        run("document.querySelector('.kp-repo-new').open = true")
        assert run("document.getElementById('kp-repo-mode').value") == "import"
        set_value("kp-repo-source", str(source))
        set_value("kp-repo-path", str(drive))
        set_value("kp-repo-title", "Tester wiki")
        click("#kp-repo-form button[type=submit]")
        wait(has("kp-title", "知識庫"))
        (listed,) = wiki_repos.listing(workspace)
        assert listed["title"] == "Tester wiki"
        assert not hidden("kp-repo-settings") and hidden("kp-discard")
        wait(has("kp-scope-name", "整個知識庫"))
        wait(has("kp-pull-folders", "還沒設定收件資料夾"))
        shoot("repo-pull-unset")

        # -- this PC's folders, then pull an original ----------------------------------------
        set_value("kp-intake", str(intake))
        set_value("kp-questions", str(questions))
        click("#kp-repo-save")
        wait(has("kp-repo-saved", "已儲存"))
        wait(has("kp-pull-folders", "Products"))
        click("#kp-pull-folders input[type=checkbox]")
        click("#kp-pull")
        wait(has("kp-pull-result", "1 new original"))
        shoot("repo-pull")

        # -- step 3: the 「版本」 area replaces the sandbox push -------------------------------
        click("#kp-stepper [data-stage=test]")
        wait("!document.getElementById('kp-ver').hidden")
        assert hidden("kp-push-card") and hidden("kp-candidate")
        wait(has("kp-bench-sets", "products"))
        wait(has("kp-ver-pending", "還沒 commit 的檔案 1 個"))
        assert "tester-z.txt" in text_of("kp-ver-pending")
        assert "還沒有發佈過" in text_of("kp-ver-reads")
        set_value("kp-ver-purpose", "加入 Tester Z 原始檔")
        click("#kp-ver-commit")
        wait(has("kp-ver-result", "已 commit"))
        wait("!document.getElementById('kp-ver-push').disabled")
        click("#kp-ver-push")
        wait(has("kp-ver-result", "已 push 1 個 commit"))
        assert "沒有跑過測試" in text_of("kp-ver-result")
        wait(has("kp-ver-history", "加入 Tester Z 原始檔"))
        shoot("repo-versions")

        # -- tag and publish (the person confirms) -------------------------------------------
        run(f"{button('kp-ver-history', '加 tag')}.click()")
        wait("!!document.querySelector('#kp-ver-history .kp-ver-ask input')")
        run("document.querySelector('#kp-ver-history .kp-ver-ask input').value = 'v1'")
        run(f"{button('kp-ver-history', '建立 tag')}.click()")
        wait(has("kp-ver-result", "已建立 tag「v1」"))
        wait("!!" + button("kp-ver-history", "發佈 v1"))
        run("window.confirm = () => true")
        run(f"{button('kp-ver-history', '發佈 v1')}.click()")
        wait(has("kp-ver-result", "已發佈「v1」"))
        wait(has("kp-ver-history", "發佈中"))
        wait(has("kp-ver-reads", "發佈版本「v1」"))
        assert wiki_repos_write.history(workspace, listed["id"])["published"]["tag"] == "v1"
        shoot("repo-published")

        # -- phone width ---------------------------------------------------------------------
        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("repo-versions-phone")
    finally:
        browser.close()
