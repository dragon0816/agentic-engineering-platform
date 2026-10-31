"""The AI session panels of 「建立與匯入」 in a real (headless) browser.

BI ingest phases 5 and 6 (`docs/phases/BI_INGEST.md` §9, §10): the real Agent
Web server, which has no Knowledge model here. Step 3: the Session B panel says
plainly that no model is available and a turn is refused with
`model_unavailable`; a rule-path method is created from the recipe box, tried,
saved as a second revision, tried again, the two trials compared, and the
first revision brought back. Step 2: a draft is tried on the sample without a
model. Then the AI runtime is swapped for a scripted model (the page and the
routes are real): Session A suggests a new field, shows the diff and what was
sent, 「套用到草稿」 writes revision 2 and the sample trial shows the new field;
Session B suggests a check that 「套用為新版次」 saves. Nothing reaches the
cards. At phone width the steps have no horizontal scroll. Screenshots in
`.scratch/bi-sessions/`.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from test_bi_methods import Model
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from capabilities.bi_cards.ai_runs import AiRuntime
from host_runtime import bi_cards_api
from models.contracts import ModelRequest

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "bi-sessions"
TECH_CSV = "技術,領域,成熟度\nEtherCAT,robotics,mature\nTSN,robotics,growth\nOPC UA,robotics,成熟\n"
RECIPE = {
    "passes": [
        {
            "id": "tech",
            "entity_type": "Technology",
            "mapping": {"columns": {"技術": "name", "領域": "domain", "成熟度": "maturity"}},
        }
    ]
}


PRICE_FIELD = {
    "name": "price_band",
    "label": "價格帶",
    "kind": "str",
    "class": "sourced",
    "aliases": ["價格帶"],
}


def _answer(request: ModelRequest) -> dict[str, Any]:
    if request.output_contract == "aep.bi.schema_suggestion.v1":
        return {
            "reply": "在技術卡加一個價格帶欄位。",
            "verdict": "extend",
            "reasons": ["樣本沒有價格欄位"],
            "assumptions": ["價格帶是文字"],
            "missing_information": ["價格帶的分級"],
            "changes": [{"op": "add_field", "type": "Technology", "field": PRICE_FIELD}],
            "examples": [],
        }
    return {
        "reply": "加一條檢查：技術卡要有標準組織。",
        "changes": {"checks": [{"entity_type": "Technology", "require": ["standard_body"]}]},
        "reasons": ["方便追蹤標準"],
        "limits": [],
        "needs_engineering": ["讀掃描 PDF 需要 OCR"],
    }


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_session_panels_in_a_browser(
    served: Any,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from integrations.browser import Browser, BrowserError

    # The served Agent Web has no Knowledge model; the test decides when one exists.
    model: dict[str, Any] = {"pair": None}

    def background(_title: str, work: Any) -> None:
        threading.Thread(target=work, daemon=True).start()

    monkeypatch.setattr(
        bi_cards_api,
        "web_ai_runtime",
        lambda _web: AiRuntime(model=lambda: model["pair"], background=background),
    )
    web, server, _recorder, _ = served
    workspace = web.runtime.layout.workspace_root
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

    def click_text(scope: str, label: str) -> None:
        run(
            f"[...document.querySelectorAll({json.dumps(scope + ' button')})]"
            f".find(b => b.textContent.includes({json.dumps(label)})).click()"
        )

    def text_of(element_id: str) -> str:
        return str(run(f"document.getElementById('{element_id}').textContent"))

    def set_value(element_id: str, value: str) -> None:
        run(f"document.getElementById('{element_id}').value = {json.dumps(value)}")

    def stage_shown(name: str) -> str:
        return f"!document.querySelector('#bi-view-build .kp-stage[data-stage={name}]').hidden"

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

    cards_db = workspace / "bi" / "demo" / "bi.sqlite"
    try:
        size(1366, 1000, False)
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        run("window.confirm = () => true;")
        click("#nav-knowledge")
        click("#kn-tabs [data-kn=bi]")
        wait("document.getElementById('bi-status-bar').hidden")
        click("#bi-views [data-bi-view=build]")
        wait(stage_shown("source"))
        run(
            "(() => { const dt = new DataTransfer();"
            f" dt.items.add(new File([{json.dumps(TECH_CSV)}], 'tech.csv', {{type: 'text/csv'}}));"
            " const f = document.getElementById('bi-b-file'); f.files = dt.files;"
            " f.dispatchEvent(new Event('change')); })()"
        )
        click("#bi-b-upload")
        wait("document.querySelectorAll('#bi-b-sources tbody input:checked').length === 1")

        # -- step 3: no model → the panel says so; a rules method with revisions ------------
        click("#bi-build-steps [data-stage=method]")
        wait(stage_shown("method"))
        wait("document.getElementById('bi-b-sb-model').textContent.includes('model_unavailable')")
        # The built-ins are always listed; a table source starts on 「表格規則」, and
        # Session B is shown before any Skill is saved (owner, 2026-10-28).
        pick = "document.getElementById('bi-b-m-pick')"
        assert run(f"[...{pick}.options].slice(0, 2).map(o => o.value).join()") == (
            "builtin:llm,builtin:rules"
        )
        assert run(f"{pick}.value") == "builtin:rules"
        assert "表格規則" in text_of("bi-b-sb-target")
        assert run("document.getElementById('bi-b-sb-send').offsetHeight > 0")
        set_value("bi-b-recipe", json.dumps(RECIPE, ensure_ascii=False))
        set_value("bi-b-m-name", "技術表")
        click("#bi-b-m-new")
        wait("document.getElementById('bi-b-m-info').textContent.includes('第 1 版')")
        assert "規則轉換" in text_of("bi-b-m-info")
        assert run(
            "document.getElementById('bi-b-m-pick').selectedOptions[0].textContent"
        ).startswith("技術表")
        set_value("bi-b-sb-msg", "沒有文件依據的需求標成推測")
        click("#bi-b-sb-send")
        wait("document.getElementById('bi-b-sb-status').textContent.includes('沒有可用的模型')")
        assert run("document.getElementById('bi-b-sb-status').getAttribute('role')") == "status"
        assert run("document.getElementById('bi-b-sb-send').offsetHeight > 0")  # visible
        assert "沒有對話" in text_of("bi-b-sb-log")  # nothing was stored

        click("#bi-b-trial")
        wait("document.getElementById('bi-b-trial-result').textContent.includes('試跑完成')")
        assert "@1" in text_of("bi-b-trial-result")
        fixed = json.loads(json.dumps(RECIPE))
        fixed["passes"][0]["mapping"]["enum_aliases"] = {"maturity": {"成熟": "mature"}}
        set_value("bi-b-recipe", json.dumps(fixed, ensure_ascii=False))
        click("#bi-b-m-save")
        wait("document.getElementById('bi-b-m-info').textContent.includes('第 2 版')")
        click("#bi-b-trial")
        wait("document.getElementById('bi-b-trial-result').textContent.includes('@2')")
        wait("!document.getElementById('bi-b-cmp-go').disabled")
        click("#bi-b-cmp-go")
        wait("document.getElementById('bi-b-cmp').textContent.includes('錯誤')")
        compared = text_of("bi-b-cmp")
        assert "@1" in compared and "@2" in compared and "相同" in compared
        run("document.getElementById('bi-b-cmp').scrollIntoView()")
        shoot("3-compare")

        click_text("#bi-b-m-info", "回復到這一版")
        wait("document.getElementById('bi-b-m-info').textContent.includes('第 3 版')")
        assert "回復到第 1 版" in text_of("bi-b-m-info")
        assert "enum_aliases" not in run("document.getElementById('bi-b-recipe').value")
        assert not cards_db.exists()

        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("3-method-phone")
        size(1366, 1000, False)

        # -- step 2: a draft tried on the sample, no model yet ------------------------------
        click("#bi-build-steps [data-stage=schema]")
        wait(stage_shown("schema"))
        # Session A is shown without a draft; with no model, sending makes nothing.
        wait("document.getElementById('bi-b-sa-model').textContent.includes('model_unavailable')")
        assert run("document.getElementById('bi-b-sa-send').offsetHeight > 0")
        assert "還沒有開啟草稿" in text_of("bi-b-sa-target")
        set_value("bi-b-sa-msg", "幫技術卡加一個價格帶欄位")
        click("#bi-b-sa-send")
        wait("document.getElementById('bi-b-sa-status').textContent.includes('沒有可用的模型')")
        assert not (workspace / "bi" / "schema-drafts").exists()
        set_value("bi-b-sa-msg", "")
        click("#bi-b-draft-new")
        wait("!document.getElementById('bi-b-draft').hidden")
        wait("document.getElementById('bi-b-sa-target').textContent.includes('第 1 版')")
        assert run("document.querySelector('#bi-b-sa-sources input').checked")
        assert run("document.getElementById('bi-b-sa-send').offsetHeight > 0")  # visible
        click("#bi-b-draft-trial")
        wait("document.getElementById('bi-b-draft-trial-result').textContent.includes('試跑完成')")
        assert "draft:" in text_of("bi-b-draft-trial-result")

        # -- Session A with a (scripted) model -------------------------------------------
        scripted = Model(_answer)
        model["pair"] = (scripted, "test-model")
        set_value("bi-b-sa-goal", "追蹤機器人技術的價格")
        set_value("bi-b-sa-msg", "幫技術卡加一個價格帶欄位")
        click("#bi-b-sa-send")
        wait("document.getElementById('bi-b-sa-log').textContent.includes('擴充這份 schema')")
        log = text_of("bi-b-sa-log")
        assert "price_band" in log and "價格帶的分級" in log
        assert "tech.csv" in log and "INTERNAL" in log and "test-model" in log
        assert scripted.requests[-1].tools == ()
        run("document.getElementById('bi-b-sa-log').scrollIntoView()")
        shoot("2-session-a")
        click_text("#bi-b-sa-log", "套用到草稿")
        wait("document.getElementById('bi-b-draft-info').textContent.includes('第 2 版')")
        wait("document.getElementById('bi-b-sa-log').textContent.includes('已套用為草稿第 2 版')")
        click("#bi-b-draft-trial")
        wait("document.getElementById('bi-b-draft-trial-result').textContent.includes('第 2 版')")
        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("2-session-a-phone")
        size(1366, 1000, False)

        # -- Session B with the model: a suggested check saved as a revision ----------------
        click("#bi-build-steps [data-stage=method]")
        wait(stage_shown("method"))
        wait("document.getElementById('bi-b-sb-model').textContent.includes('test-model')")
        set_value("bi-b-sb-msg", "技術卡一定要有標準組織")
        click("#bi-b-sb-send")
        wait("document.getElementById('bi-b-sb-log').textContent.includes('需要工程開發')")
        click_text("#bi-b-sb-log", "套用為新版次")
        wait("document.getElementById('bi-b-m-info').textContent.includes('第 4 版')")
        assert "必要欄位檢查 1 條" in text_of("bi-b-m-info")
        run("document.getElementById('bi-b-sb-log').scrollIntoView()")
        shoot("3-session-b")
        # A built-in is never changed: the first message saves a copy and talks about it.
        run(
            "{ const s = document.getElementById('bi-b-m-pick'); s.value = 'builtin:llm';"
            " s.dispatchEvent(new Event('change')); }"
        )
        wait("document.getElementById('bi-b-sb-target').textContent.includes('AI 擷取')")
        assert "沒有對話" in text_of("bi-b-sb-log")
        set_value("bi-b-sb-msg", "技術卡一定要有標準組織")
        click("#bi-b-sb-send")
        wait("document.getElementById('bi-notice').textContent.includes('另存為你的 Skill')")
        wait("document.getElementById('bi-b-sb-log').textContent.includes('需要工程開發')")
        assert not str(run("document.getElementById('bi-b-m-pick').value")).startswith("builtin:")
        assert "AI 擷取（我的版本" in text_of("bi-b-m-info")
        assert not cards_db.exists()
        assert not (workspace / "bi" / "schemas").exists()
    finally:
        browser.close()
