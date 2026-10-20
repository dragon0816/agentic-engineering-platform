"""The interactive HTML org chart (owner 2026-10-20; docs/phases/BUSINESS_CARDS.md §6).

One self-contained page from the same data as the PNG: valid structure,
every contact value as text (a contact named `<script>` stays text), no
external address, people who left behind a toggle, search data, a reporting
tree only where lines exist, and the fields still to confirm. A real
headless browser opens it, switches views, searches a name (the card opens),
toggles people who left, and checks dark mode and 390 px; screenshots go to
`.scratch/org-chart-html/`. Synthetic people, no network.
"""

from __future__ import annotations

import json
import os
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from test_business_cards_capabilities import _bridge, _people, _run

from capabilities.business_cards import chart
from capabilities.business_cards.chart_html import TEMPLATE

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "org-chart-html"
XSS = "<script>alert(1)</script>"


class _Tags(HTMLParser):
    """Collects start tags with their ids and checks that every opened
    element that must close does close."""

    VOID = {"meta", "input", "br", "img", "link", "hr"}

    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.tags: list[str] = []
        self.stack: list[str] = []
        self.data_json = ""
        self._in_data = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        found = dict(attrs)
        if found.get("id"):
            self.ids.add(str(found["id"]))
        self._in_data = found.get("id") == "chart-data"
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        assert self.stack and self.stack[-1] == tag, (tag, self.stack[-3:])
        self.stack.pop()
        self._in_data = False

    def handle_data(self, data: str) -> None:
        if self._in_data:
            self.data_json += data


def _parsed(page: str) -> _Tags:
    tags = _Tags()
    tags.feed(page)
    tags.close()
    assert tags.stack == [], tags.stack
    return tags


def _chart(tmp_path: Path, **arguments: Any) -> tuple[dict[str, Any], str, dict[str, Any]]:
    bridge = _bridge(tmp_path)
    _people(bridge)
    _setup(bridge)
    drawn = _run(bridge, "org-chart", {"company": "範例科技", **arguments})
    assert drawn.status == "succeeded", drawn.failure
    data = drawn.data
    assert data is not None
    page = Path(data["html_path"]).read_text(encoding="utf-8")
    return data, page, json.loads(_parsed(page).data_json)


def _setup(bridge: Any) -> None:
    """A contact whose fields hold markup, a reporting line with evidence,
    a departure and a field still to confirm."""
    assert (
        _run(
            bridge,
            "add-card",
            {
                "name": XSS,
                "company": "範例科技",
                "division": "研發處",
                "title": "\"工程師\" & <b>'x'</b>",
                "email": "x@example.com",
                "uncertain": ["email"],
            },
        ).status
        == "succeeded"
    )
    assert (
        _run(
            bridge,
            "set-reporting-line",
            {
                "person": {"name": "李大華"},
                "manager": {"name": "王小明"},
                "evidence_kind": "signature",
                "evidence_ref": "<msg-9>",
            },
        ).status
        == "succeeded"
    )
    assert (
        _run(
            bridge,
            "set-status",
            {"person": {"name": "林離"}, "status": "left", "reason": "left in September"},
        ).status
        == "succeeded"
    )


def test_png_stays_the_default_and_html_or_both_add_the_page(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    _people(bridge)
    plain = _run(bridge, "org-chart", {"company": "範例科技"}).data
    assert plain is not None and plain["format"] == "png" and plain["html_path"] == ""
    assert [item["media_type"] for item in plain["attach"]] == ["image/png", "text/markdown"]
    page = _run(bridge, "org-chart", {"company": "範例科技", "format": "html"}).data
    assert page is not None and page["png_path"] == ""
    assert [item["media_type"] for item in page["attach"]] == ["text/html", "text/markdown"]
    assert Path(page["html_path"]).parent == Path(plain["png_path"]).parent  # charts/
    both = _run(bridge, "org-chart", {"company": "範例科技", "format": "both"}).data
    assert both is not None
    assert [item["media_type"] for item in both["attach"]] == [
        "image/png",
        "text/html",
        "text/markdown",
    ]
    assert Path(both["png_path"]).is_file() and Path(both["html_path"]).is_file()
    refused = _run(bridge, "org-chart", {"company": "範例科技", "format": "svg"})
    assert refused.status != "succeeded"


def test_the_page_is_one_valid_self_contained_document(tmp_path: Path) -> None:
    _, page, data = _chart(tmp_path, format="html")
    assert page.startswith("<!DOCTYPE html>")
    tags = _parsed(page)
    for wanted in ("title", "tab-tree", "tab-grouped", "tree", "grouped", "search", "results"):
        assert wanted in tags.ids, wanted
    assert {"show-left", "card", "card-close", "chart-data"} <= tags.ids
    assert tags.tags.count("style") == 1 and tags.tags.count("script") == 2
    assert "<title>範例科技 組織圖</title>" in page
    assert data["title"] == "範例科技 組織圖" and data["company"] == "範例科技"
    # No network: no address, no external script, stylesheet or font.
    assert not re.search(r"https?://|//[a-z0-9.-]+\.[a-z]{2,}/", page, re.IGNORECASE)
    assert "<link" not in page and " src=" not in page and "@import" not in page
    assert "default-src 'none'" in page
    # General: nothing about one company is built into the page itself.
    assert "範例" not in TEMPLATE and "WNC" not in TEMPLATE


def test_contact_markup_is_shown_as_text_never_as_markup(tmp_path: Path) -> None:
    _, page, data = _chart(tmp_path, format="html")
    assert XSS not in page and "<b>'x'</b>" not in page
    assert "\\u003cscript\\u003ealert(1)\\u003c/script\\u003e" in page
    person = next(p for p in data["people"] if p["name"] == XSS)
    assert person["title"] == "\"工程師\" & <b>'x'</b>"
    # The script builds elements with text only.
    for unsafe in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert unsafe not in TEMPLATE, unsafe
    assert "createTextNode" in TEMPLATE and "textContent" in TEMPLATE


def test_people_who_left_are_in_the_data_behind_a_toggle_hidden_by_default(
    tmp_path: Path,
) -> None:
    result, page, data = _chart(tmp_path, format="html")
    assert data["show_left"] is False
    left = [p for p in data["people"] if p["left"]]
    assert [p["name"] for p in left] == ["林離"] and left[0]["status_label"] == "已離職"
    assert 'id="show-left"' in page and "顯示已離職" in page
    # The PNG/legend counts follow include_left as before.
    assert result["left_omitted"] == 1
    _, _, shown = _chart(tmp_path / "again", format="html", include_left=True)
    assert shown["show_left"] is True


def test_the_search_data_and_the_person_card_fields_are_there(tmp_path: Path) -> None:
    _, _, data = _chart(tmp_path, format="html")
    wang = next(p for p in data["people"] if p["name"] == "王小明")
    for key in ("romanised", "title", "business_group", "division", "department", "email"):
        assert key in wang
    assert wang["email"] == "hm.wang@example.com" and wang["department"] == "射頻部"
    assert wang["path"] == ["網通事業群", "研發處", "射頻部"]
    assert wang["sources"] and wang["sources"][0]["label"] == "名片"
    assert re.match(r"\d{4}-\d{2}-\d{2}", wang["sources"][0]["date"])
    assert "p.romanised" in TEMPLATE and "p.email" in TEMPLATE and "p.department" in TEMPLATE


def test_a_reporting_tree_only_where_lines_exist_otherwise_grouping_only(
    tmp_path: Path,
) -> None:
    _, _, data = _chart(tmp_path, format="html")
    assert data["has_lines"] is True and data["no_lines_note"] == ""
    lee = next(p for p in data["people"] if p["name"] == "李大華")
    assert lee["manager"] == {
        "id": lee["manager"]["id"],
        "name": "王小明",
        "evidence": "簽名檔（<msg-9>）",
        "inferred": False,
    }
    wang = next(p for p in data["people"] if p["name"] == "王小明")
    assert [r["name"] for r in wang["reports"]] == ["李大華"]
    bare = _bridge(tmp_path / "bare")
    _people(bare)
    page = _run(bare, "org-chart", {"company": "範例科技", "format": "html"}).data
    assert page is not None
    grouped = json.loads(_parsed(Path(page["html_path"]).read_text("utf-8")).data_json)
    assert grouped["has_lines"] is False and grouped["no_lines_note"] == chart.NO_LINES_NOTE
    assert all(p["manager"] is None and p["reports"] == [] for p in grouped["people"])


def test_fields_to_confirm_are_named_in_chinese(tmp_path: Path) -> None:
    _, _, data = _chart(tmp_path, format="html")
    person = next(p for p in data["people"] if p["name"] == XSS)
    assert person["needs"] == ["Email"]
    assert '"需確認：" + p.needs.join("、")' in TEMPLATE


# -- in a real browser --------------------------------------------------------------


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_page_works_in_a_real_browser(tmp_path: Path) -> None:
    from integrations.browser import Browser

    _, page, _ = _chart(tmp_path, format="html")
    html_path = next((tmp_path / "workspace").rglob("*.html"))
    assert html_path.read_text(encoding="utf-8") == page
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def run(expression: str) -> Any:
        return browser._evaluate(expression)

    def wait(expression: str, seconds: float = 20) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = run(expression)
            if value:
                return value
            time.sleep(0.1)
        raise AssertionError(expression)

    def size(selector: str) -> list[int]:
        found: list[int] = json.loads(
            str(
                run(
                    "JSON.stringify((() => { const r = document.querySelector("
                    + json.dumps(selector)
                    + ").getBoundingClientRect(); return [r.width, r.height]; })())"
                )
            )
        )
        return found

    def no_side_scroll() -> None:
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )

    try:
        browser.navigate(html_path.as_uri())
        wait("document.querySelectorAll('#tree .person').length > 0")
        assert run("document.getElementById('title').textContent") == "範例科技 組織圖"
        # The markup in a contact is text: no injected element ran or exists.
        assert run("document.querySelectorAll('main script, main b').length") == 0
        assert run(f"document.body.innerText.includes({json.dumps(XSS)})")
        # Reporting tree with the evidenced (solid) line, then grouping.
        assert "回報關係" in str(run("document.getElementById('tree').innerText"))
        assert run("document.querySelectorAll('#tree .edge:not(.inferred)').length") >= 1
        # People who left are hidden by default.
        assert not run("document.body.innerText.includes('林離')")
        for selector in ("#tab-tree", "#tab-grouped", "#search", ".person", "summary"):
            assert size(selector)[1] >= 44, selector
        no_side_scroll()
        browser.screenshot(shots / "org-chart-tree-light.png")
        # Grouped view (by keyboard: ArrowRight on the tabs).
        run("document.getElementById('tab-tree').focus()")
        run(
            "document.getElementById('tab-tree').dispatchEvent("
            "new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}))"
        )
        assert run("document.getElementById('grouped').hidden") is False
        assert run("document.getElementById('tree').hidden") is True
        assert run("document.activeElement.id") == "tab-grouped"
        assert run("document.querySelectorAll('#grouped .box').length") >= 2
        browser.screenshot(shots / "org-chart-grouped-light.png")
        # Search a name: the result list, Enter opens the person card.
        run(
            "(() => { const s = document.getElementById('search'); s.value = '王小';"
            " s.dispatchEvent(new Event('input')); })()"
        )
        wait("document.querySelectorAll('#results .result').length === 1")
        run(
            "document.getElementById('search').dispatchEvent("
            "new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}))"
        )
        wait("!document.getElementById('card').hidden")
        card = str(run("document.getElementById('card').innerText"))
        for words in ("王小明", "網通事業群", "研發處", "射頻部", "協理", "hm.wang@example.com"):
            assert words in card, (words, card)
        assert "在職" in card and "名片" in card and "李大華 向他報告：簽名檔（<msg-9>）" in card
        assert size("#card-close")[0] >= 44
        browser.screenshot(shots / "org-chart-card-light.png")
        run("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
        assert run("document.getElementById('card').hidden") is True
        # Search by email finds the markup-named contact; its card shows 需確認.
        run(
            "(() => { const s = document.getElementById('search'); s.value = 'x@example';"
            " s.dispatchEvent(new Event('input')); })()"
        )
        wait("document.querySelectorAll('#results .result').length === 1")
        run("document.querySelector('#results .result').click()")
        wait("!document.getElementById('card').hidden")
        card = str(run("document.getElementById('card').innerText"))
        assert XSS in card and "Email" in card and "需確認" in card
        run("document.getElementById('card-close').click()")
        # The toggle shows people who left, greyed.
        run("document.getElementById('show-left').click()")
        wait("document.body.innerText.includes('林離')")
        assert run("document.querySelectorAll('.person.left').length") >= 1
        light = run("getComputedStyle(document.body).backgroundColor")
        browser.screenshot(shots / "org-chart-left-shown.png")
        # Dark mode follows the system.
        browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "dark"}],
        )
        dark = run("getComputedStyle(document.body).backgroundColor")
        assert light != dark, (light, dark)
        browser.screenshot(shots / "org-chart-grouped-dark.png")
        # 390 px: no horizontal page scroll; the card fills the screen.
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=390,
            height=844,
            deviceScaleFactor=1,
            mobile=True,
        )
        time.sleep(0.3)
        no_side_scroll()
        browser.screenshot(shots / "org-chart-narrow-dark.png")
        run("document.getElementById('tab-tree').click()")
        no_side_scroll()
        run("document.querySelector('#tree .person').click()")
        wait("!document.getElementById('card').hidden")
        assert size("#card")[0] <= 390
        no_side_scroll()
        browser.screenshot(shots / "org-chart-card-narrow-dark.png")
    finally:
        browser.close()
        browser.discard_profile()
