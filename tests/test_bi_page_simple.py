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
    return any(tag == "details" and name.startswith("bi-b-adv-")
               for tag, name in PANE.around[ident])  # fmt: skip


def _in_manage(ident: str) -> bool:
    """In the top row's 管理 menu, or a panel only that menu opens (owner 2026-11-19, B1)."""
    return any((tag, name) in (("details", "bi-b-v-menu"), ("div", "bi-advanced"))
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
    # One 匯入 for schema, rules and programs (owner 2026-11-20).
    "bi-b-pkg-import",
    # Step 2a's schema (acceptance F8): the draft as a table. 建議 schema is under 進階
    # (owner 2026-11-20).
    "bi-b-draft-table",
    "bi-b-draft-use",
    "bi-b-upgrade",
    "bi-ai",
    "bi-b-start",
    "bi-b-cands",
    "bi-b-commit-go",
    # Step 3: dashboard, questions, the test run, its result, and what follows it.
    "bi-b-bench-run",
    "bi-b-bench-report",
    # 分享: one step for commit, push, tag and publish (acceptance F13).
    "bi-b-share-list",
    "bi-b-share-tests",
    "bi-b-ver-purpose",
    "bi-b-share-tag",
    "bi-b-share-go",
    "bi-b-share-progress",
    "bi-b-ver-history",
)

#: The former 進階：資料集與發佈, now in the 管理 menu (owner 2026-11-19, B1 and S3), with
#: 新增知識庫 and 加入.
MANAGE = (
    "bi-b-v-new",
    "bi-b-v-join",
    "bi-b-v-sync",
    "bi-publish",
    "bi-publish-panel",
    "bi-subs-open",
    "bi-subs",
    "bi-new",
    "bi-new-panel",
    "bi-install",
    "bi-install-panel",
    "bi-demo",
    "bi-schema-note",
)

#: Not named by the owner: under 進階, and still there.
ADVANCED = (
    "bi-b-v-convert",
    "bi-b-askable",
    "bi-b-pages",
    "bi-b-rerun",
    "bi-b-sk-form",
    "bi-b-tl-save",
    "bi-b-draft-new",
    "bi-b-draft-text",
    "bi-b-versions",
    # 「建議 schema」 only on a press, under 進階：Schema (owner 2026-11-20).
    "bi-b-sg-run",
    "bi-b-sg-table",
    "bi-b-fresh",
    "bi-b-recipe",
    "bi-b-instr",
    "bi-b-trial",
    "bi-b-cmp-go",
    "bi-b-sb-open",
    "bi-b-an-pack",
    "bi-b-atl",
    "bi-b-bc-list",
    "bi-b-ver-commit",
    "bi-b-ver-push",
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


@pytest.mark.parametrize("ident", MANAGE)
def test_the_former_datasets_section_and_create_join_are_in_the_manage_menu(ident: str) -> None:
    assert ident in PANE.around, ident
    assert _in_manage(ident), ident


def test_there_is_no_folded_section_at_the_foot_of_the_page() -> None:
    assert "進階：資料集與發佈" not in PAGE
    assert PANE.tags["bi-advanced"] == "div"
    # The panels open under the top row, where the menu is.
    assert (
        PAGE.index('id="bi-b-v-menu"')
        < PAGE.index('id="bi-advanced"')
        < PAGE.index('id="bi-views"')
    )


@pytest.mark.parametrize(
    "ident",
    [
        "bi-ask",
        "bi-hint",
        "bi-refresh",
        "bi-b-ds",
        "bi-b-src-shared",
        # Owner 2026-11-19 first batch: the step bar and the tabs already do these.
        "bi-b-to-cards",
        "bi-b-ro-cards",
        "bi-b-ro-dash",
        "bi-b-ro-links",
        "bi-b-md-close",
        "bi-b-fit",
        "bi-b-atl-port",
        # Owner 2026-11-20: the profile is assembled by the program, never shown, and
        # 建議 schema reads the working domain's sources with no choice to make.
        "bi-b-profile",
        "bi-b-pf-home",
        "bi-b-pf-json",
        "bi-b-pf-save",
        "bi-b-sg-scope",
        # No AI collaboration in step 2 (owner 2026-11-20): import instead.
        "bi-b-sk-new",
        "bi-b-sa-open",
        "bi-b-tl-ai",
    ],
)
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
        'id="bi-b-v-menu"',
        'id="bi-b-src-folder"',
        'id="bi-b-home-new"',
        'id="bi-views"',
        'id="bi-stepper"',
        'id="bi-b-class"',
    ]
    at = [PAGE.index(mark, PAGE.index('<div id="kn-pane-bi"')) for mark in order]
    assert at == sorted(at), order
    assert "bi-bar" not in PAGE[PAGE.index('<div id="kn-pane-bi"') :].split("<section")[0]


def test_create_and_join_are_in_the_manage_menu_and_in_sight_with_no_knowledge_base() -> None:
    # Owner 2026-11-19 (S3) moved them from beside the selection into 管理.
    for ident in ("bi-b-v-new", "bi-b-v-join", "bi-b-v-sync"):
        assert ("details", "bi-b-v-menu") in PANE.around[ident], ident
    # Their form is not in the menu, or closing the menu would hide it.
    assert not any(tag == "details" for tag, _name in PANE.around["bi-b-v-form"])
    # With nothing on this PC the guide shows both, not folded.
    for ident in ("bi-empty-new", "bi-empty-join"):
        assert ("div", "bi-empty-state") in PANE.around[ident], ident
        assert not any(tag == "details" for tag, _name in PANE.around[ident]), ident


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
        # A panel only the 管理 menu opens is as folded as 進階.
        and ("div", "bi-advanced") not in around
    ]
    assert long == []


def test_a_read_only_dataset_keeps_a_way_to_another_one() -> None:
    assert 'data-bi-view=build]").hidden = readOnly' not in PAGE
    assert 'if (name === "build" && biReadOnly()) name = "dashboard";' not in PAGE
    # Step 1 hides only what cannot be done there.
    assert 'el("bi-b-src-input").hidden = readOnly' in PAGE
    # The 卡片 and Dashboard tabs above are the way there (C9: no buttons repeating them).
    assert "bi-b-ro-links" not in PAGE


def test_the_other_tabs_sentence_does_not_show_on_this_one() -> None:
    assert 'el("kn-note").hidden = knPane !== "pipeline";' in PAGE


def test_a_panel_opened_from_the_manage_menu_closes_it_and_comes_into_view() -> None:
    panel = PAGE[PAGE.index("function biPanel(") :]
    panel = panel[: panel.index("\n}\n")]
    assert 'el("bi-b-v-menu").open = false;' in panel
    assert "panel.scrollIntoView(" in panel


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
    # With no wiki pipeline, or nothing in it, there is nothing else to open on (F1).
    assert 'call("/api/knowledge/pipeline")' in opening and "!info.enabled" in opening
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


def test_the_two_sections_are_tabs_with_the_run_above_the_questions() -> None:
    # Owner 2026-11-20: Benchmark and Dashboard are tabs of the main area; the numbers, then
    # 跑測試 with its bar, sit above the questions so the button is in sight.
    for section in ("bi-b-bench", "bi-b-an"):
        assert f'<details id="{section}" class="card bi-sec" hidden>' in PAGE
    assert (
        PAGE.index('id="bi-b-tabs"')
        < PAGE.index('id="bi-b-bench-sum"')
        < PAGE.index('id="bi-b-bench-run"')
        < PAGE.index('id="bi-b-run-progress"')
        < PAGE.index('id="bi-b-bench"')
        < PAGE.index('id="bi-b-an"')
    )


def test_every_jump_to_another_tab_has_a_way_back() -> None:
    script = PAGE[PAGE.index("function biBackHide") :]
    jumps = [line for line in script.splitlines() if 'biShowView("' in line]
    assert jumps == []


def test_the_schema_suggestion_sits_under_advanced_after_the_skills() -> None:
    # Owner 2026-11-20: the main path of step 2 is the schema summary and the skills; 建議
    # schema runs only on a press, under 進階：Schema.
    start = PAGE.index('data-stage="schema"')
    at = [PAGE.index(f'id="{i}"', start) for i in ("bi-b-skills", "bi-b-adv-schema", "bi-b-sg-run")]
    assert at == sorted(at)


def test_every_bi_function_the_page_calls_is_defined() -> None:
    # A helper removed while another branch still calls it fails only at run time, where the
    # parse check cannot see it (biRowMenu, 2026-11-06).
    called = set(re.findall(r"(?<![\w.])(bi[A-Z]\w*)\(", PAGE))
    defined = set(re.findall(r"(?:function\s+|(?:const|let|var)\s+)(bi[A-Z]\w*)", PAGE))
    assert called - defined == set()


def test_controls_with_nothing_to_choose_stay_out_of_sight() -> None:
    """Owner 2026-11-19 first batch: shown only when there is a choice to make."""
    # H1: 含 SAMPLE 示範卡 only where the Dashboard has sample cards.
    assert '<div id="bi-sample-box" hidden>' in PAGE
    assert 'el("bi-sample-box").hidden = !reply.has_sample' in PAGE
    # C1: the revision choice with two or more; C3: the source search past ten.
    assert '<div id="bi-b-md-rev-box" hidden>' in PAGE
    assert '<div id="bi-b-src-q-box" hidden>' in PAGE
    # E2: the run's folder follows the source under a working domain.
    assert 'el("bi-b-folder-box").hidden = !pick.options.length || Boolean(biScope());' in PAGE
    # G4: a new question is the working domain's.
    assert ("div", "bi-b-bq-home-box") in PANE.around["bi-b-bq-home"]


def test_the_wording_names_what_is_on_the_page() -> None:
    # S1, F3: step 3 has 分享, no 版本 block and no separate Push.
    assert "到「版本」" not in PAGE and "測試與 Push" not in PAGE
    assert ' 個：到「分享」")' in PAGE
    # J1: the step bar is the way back.
    pane = PAGE[PAGE.index('<div id="kn-pane-bi"') : PAGE.index('<section id="panel-reviews"')]
    assert "上一步" not in pane
