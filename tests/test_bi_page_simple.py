"""The BI page's main path holds only the owner's flow (`docs/phases/BI_PAGE_SIMPLE.md`).

The owner's rule: 「ui請以簡單為主，善用table，menu/comobox」. These read the page's own
markup. What a person reaches in a real browser is `test_bi_share_ui` and the flow tests.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

import pytest

from host_runtime.web_page import PAGE

VOID = {"input", "br", "img", "meta", "link", "hr"}


class _Pane(HTMLParser):
    """Each element's id with the ids and tags around it, and the paragraphs' text."""

    def __init__(self) -> None:
        super().__init__()
        self.open: list[tuple[str, str]] = []
        self.around: dict[str, list[tuple[str, str]]] = {}
        self.tags: dict[str, str] = {}
        self.paragraphs: list[tuple[str, list[tuple[str, str]]]] = []
        self.reading: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        given = dict(attrs)
        ident = given.get("id") or ""
        if ident:
            assert ident not in self.around, f"two elements are {ident}"
            self.around[ident] = list(self.open)
            self.tags[ident] = tag
        if tag == "p":
            self.reading = ""
        if tag not in VOID:
            self.open.append((tag, ident))

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self.reading is not None:
            self.paragraphs.append((self.reading.strip(), list(self.open)))
            self.reading = None
        if self.open and self.open[-1][0] == tag:
            self.open.pop()

    def handle_data(self, data: str) -> None:
        if self.reading is not None:
            self.reading += data


def _pane() -> _Pane:
    start = PAGE.index('<div id="kn-pane-bi"')
    end = PAGE.index('<section id="panel-reviews"')
    parsed = _Pane()
    parsed.feed(PAGE[start:end])
    return parsed


PANE = _pane()


def _in_advanced(ident: str) -> bool:
    return any(tag == "details" and name.startswith(("bi-b-adv-", "bi-advanced"))
               for tag, name in PANE.around[ident])  # fmt: skip


#: The owner's flow, in the steps they named. Nothing here may be folded away.
MAIN_PATH = (
    # Step 1: vault, market field, files, convert, the converted result.
    "bi-dataset",
    "bi-b-src-folder",
    "bi-b-file",
    "bi-b-upload",
    "bi-b-sources",
    # Step 2: skills and tools, ingest, the cards.
    "bi-b-sk-list",
    "bi-b-tl-list",
    "bi-b-sk-new",
    "bi-ai",
    "bi-b-start",
    "bi-b-cands",
    "bi-b-commit-go",
    # Step 3: dashboard, questions, the test run, its result, and what follows it.
    "bi-b-bench-run",
    "bi-b-bench-report",
    "bi-b-ver-commit",
    "bi-b-ver-push",
    "bi-b-ver-history",
)

#: Not named by the owner: under 進階, and still there.
ADVANCED = (
    "bi-publish",
    "bi-publish-panel",
    "bi-subs",
    "bi-new",
    "bi-new-panel",
    "bi-install",
    "bi-install-panel",
    "bi-demo",
    "bi-schema-note",
    "bi-b-v-convert",
    "bi-b-askable",
    "bi-b-pages",
    "bi-b-profile",
    "bi-b-rerun",
    "bi-b-sk-form",
    "bi-b-tl-save",
    "bi-b-sa-open",
    "bi-b-draft-new",
    "bi-b-versions",
    "bi-b-upgrade",
    "bi-b-fit",
    "bi-b-fresh",
    "bi-b-recipe",
    "bi-b-instr",
    "bi-b-trial",
    "bi-b-cmp-go",
    "bi-b-sb-open",
    "bi-b-an-pack",
    "bi-b-atl",
    "bi-b-bc-list",
    "bi-b-ver-discard",
)


@pytest.mark.parametrize("ident", MAIN_PATH)
def test_the_owners_flow_is_not_folded_away(ident: str) -> None:
    assert ident in PANE.around, ident
    assert not any(tag == "details" for tag, _name in PANE.around[ident]), ident


@pytest.mark.parametrize("ident", ADVANCED)
def test_what_the_owner_did_not_name_is_under_advanced_and_still_there(ident: str) -> None:
    assert ident in PANE.around, ident
    assert _in_advanced(ident), ident


@pytest.mark.parametrize("ident", ["bi-ask", "bi-hint", "bi-refresh", "bi-b-ds", "bi-b-src-shared"])
def test_the_removed_controls_are_gone_from_markup_and_script(ident: str) -> None:
    assert ident not in PANE.around
    assert f'"{ident}"' not in PAGE


def test_there_is_one_selection_above_every_tab_vault_then_domain() -> None:
    # Owner: 「第一件事情是選擇vault，或者是新增一個vault，接著再選domain」.
    assert PANE.tags["bi-dataset"] == "select"
    assert ("div", "bi-view-build") not in PANE.around["bi-dataset"]
    assert ("div", "bi-view-build") not in PANE.around["bi-b-src-folder"]
    assert ("div", "bi-top-row") in PANE.around["bi-dataset"]
    assert ("div", "bi-top-row") in PANE.around["bi-b-src-folder"]
    order = [
        'id="bi-dataset"',
        'id="bi-b-v-new"',
        'id="bi-b-v-join"',
        'id="bi-b-src-folder"',
        'id="bi-b-home-new"',
        'id="bi-views"',
        'id="bi-stepper"',
        'id="bi-b-class"',
    ]
    at = [PAGE.index(mark, PAGE.index('<div id="kn-pane-bi"')) for mark in order]
    assert at == sorted(at), order
    assert "bi-bar" not in PAGE[PAGE.index('<div id="kn-pane-bi"') :].split("<section")[0]


def test_create_and_join_sit_beside_the_selection_and_the_rest_is_folded() -> None:
    for ident in ("bi-b-v-new", "bi-b-v-join"):
        assert ("details", "bi-b-v-menu") not in PANE.around[ident], ident
        assert ("div", "bi-top-row") in PANE.around[ident], ident
    assert ("details", "bi-b-v-menu") in PANE.around["bi-b-v-sync"]
    # Their form is not in the menu, or closing the menu would hide it.
    assert not any(tag == "details" for tag, _name in PANE.around["bi-b-v-form"])


def test_the_market_field_is_named_and_the_button_is_convert() -> None:
    assert '<label class="bi-label" for="bi-b-src-folder">工作領域</label>' in PAGE
    assert 'id="bi-b-upload" type="button" disabled>轉檔</button>' in PAGE


def test_the_stepper_has_three_steps_and_three_parts_of_step_2() -> None:
    nav = PAGE[PAGE.index('id="bi-substeps"') :]
    nav = nav[: nav.index("</nav>")]
    shown = [line for line in nav.splitlines() if "<strong>" in line]
    assert [s.strip() for s in shown] == [
        "<span><strong>類別與規則</strong></span></button></li>",
        "<span><strong>Ingest</strong></span></button></li>",
        "<span><strong>審核</strong></span></button></li>",
    ]


def test_the_main_path_has_no_explanatory_paragraphs() -> None:
    """Anything longer than a line belongs under 進階, or nowhere."""
    long = [
        text
        for text, around in PANE.paragraphs
        if len(text) > 40
        and not any(tag == "details" for tag, _name in around)
        # A warning or an error says something happened; it is not an explanation.
        and ("div", "bi-b-bench-report") not in around
    ]
    assert long == []


def test_a_read_only_dataset_keeps_a_way_to_another_one() -> None:
    assert 'data-bi-view=build]").hidden = readOnly' not in PAGE
    assert 'if (name === "build" && biReadOnly()) name = "dashboard";' not in PAGE
    # Step 1 hides only what cannot be done there.
    assert 'el("bi-b-src-input").hidden = readOnly' in PAGE
    assert 'el("bi-b-ro-links").hidden = !readOnly' in PAGE
    assert not any(tag == "details" for tag, _name in PANE.around["bi-b-ro-links"])


def test_the_other_tabs_sentence_does_not_show_on_this_one() -> None:
    assert 'el("kn-note").hidden = knPane !== "pipeline";' in PAGE


def test_a_panel_opened_from_elsewhere_opens_advanced_first() -> None:
    assert 'el("bi-advanced").open = true;' in PAGE


def test_every_element_the_script_names_is_in_the_page() -> None:
    named = set(re.findall(r'el\("(bi-[a-z0-9-]+)"\)', PAGE))
    # Some are drawn by the script itself, with their id set there.
    drawn = set(re.findall(r'\.id = "(bi-[a-z0-9-]+)"', PAGE))
    missing = sorted(name for name in named - drawn if f'id="{name}"' not in PAGE)
    assert missing == []


def test_no_function_of_the_page_is_declared_twice() -> None:
    """The later one silently wins, for every caller of the earlier one."""
    names = re.findall(r"^(?:async )?function (\w+)\(", PAGE, flags=re.MULTILINE)
    assert sorted({name for name in names if names.count(name) > 1}) == []


def test_the_knowledge_page_opens_on_bi_unless_another_tab_was_chosen() -> None:
    opening = PAGE[PAGE.index("async function loadKnowledgeTab()") :]
    opening = opening[: opening.index("function knShow")]
    assert 'call("/api/bi/datasets")' in opening and 'knShow("bi")' in opening
    # Only a person's click on a tab counts as a choice.
    assert 'localStorage.setItem("kn-pane-chosen"' in PAGE


def test_a_read_filter_sits_beside_what_it_filters() -> None:
    """Under 進階 they filtered the Dashboard and cards with nothing showing it."""
    for ident in ("bi-domain", "bi-sample"):
        assert ("div", "bi-view-dashboard") in PANE.around[ident], ident
    assert ("div", "bi-view-cards") in PANE.around["bi-card-domain"]
    assert '"&domain=" + encodeURIComponent(el("bi-card-domain").value)' in PAGE


def test_one_ai_panel_and_none_of_the_five() -> None:
    assert PAGE.count('<aside id="bi-ai" class="bi-ai-panel"') == 1
    for gone in ("bi-b-sa-log", "bi-b-sb-log", "bi-b-ska-log", "bi-b-ana-log", "bi-b-qa-log"):
        assert gone not in PAGE
    for word in ("（Session A）", "（Session B）", "和對話同一套 harness"):
        assert word not in PAGE


@pytest.mark.parametrize(
    ("ident", "section"),
    [
        ("bi-b-bq-list", "bi-b-bench"),
        ("bi-b-bq-form", "bi-b-bench"),
        ("bi-b-qa-open", "bi-b-bench"),
        ("bi-b-an-list", "bi-b-an"),
        ("bi-b-an-new", "bi-b-an"),
    ],
)
def test_step_3_edits_in_its_two_sections(ident: str, section: str) -> None:
    """Owner, 2026-11-05: collapsed by default, not under 進階, with 跑測試 below them."""
    assert ("details", section) in PANE.around[ident]
    assert not _in_advanced(ident)


def test_the_two_sections_are_collapsed_by_default() -> None:
    for section in ("bi-b-bench", "bi-b-an"):
        assert f'<details id="{section}" class="card bi-sec" hidden>' in PAGE
    assert (
        PAGE.index('id="bi-b-bench"')
        < PAGE.index('id="bi-b-an"')
        < PAGE.index('id="bi-b-bench-run"')
    )


def test_every_jump_to_another_tab_has_a_way_back() -> None:
    script = PAGE[PAGE.index("function biBackHide") :]
    jumps = [line for line in script.splitlines() if 'biShowView("' in line]
    assert jumps == []
