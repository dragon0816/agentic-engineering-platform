"""The Member Portal page: tabs, one card size, and an asset's content.

Requirements: owner feedback of 2026-10-15 (`docs/phases/PLATFORM_OVERVIEW.md`):
the portal is in tabs kept in the URL hash, administrators land on the
Overview; every asset card has the same size; opening a card shows the
version's published content (`assets/manifest`) inside the tab, with
Markdown rendered safely.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from test_asset_access import _browser_missing
from test_asset_ownership import NOW, artifact_for, identity_of, package
from test_member_publish import skill_manifest
from test_platform_overview import _app, _seed
from test_shared_platform_app import request

from common.assets import AssetIdentity
from common.enrollment import Invitation
from control_plane.member_page import PAGE

ADMIN_TABS = ["overview", "marketplace", "published", "submissions", "applications", "review",
              "registrations", "assets", "members"]
MEMBER_TABS = ["marketplace", "published", "submissions", "applications"]
SKILL_TEXT = ("## How\n\nRun **the weekly check** with `run`.\n\n- first\n- second\n\n"
              "<img src=x onerror=window.__pwned=1> [docs](https://example.invalid/docs)")


def test_the_page_is_in_tabs_with_uniform_cards_and_asset_content() -> None:
    for hook in ('role="tablist"', 'id="portal-tabs"', 'role="tabpanel"', "#tab=",
                 "aria-selected", "ArrowRight", "ArrowLeft", '"Home"', '"End"', "hashchange",
                 "history.pushState", *(f'id="panel-{key}"' for key in ADMIN_TABS),
                 '"Overview"', '"Marketplace"', '"My published assets"', '"My submissions"',
                 '"Applications"', '"Review queue"', '"Registrations (Bridges)"',
                 '"All published assets"', '"Members & invitations"', 'id:"review-badge"',
                 # One card size: equal rows, clamped description, footer at the bottom.
                 "grid-auto-rows:1fr", "-webkit-line-clamp:3", "card-foot{margin-top:auto",
                 "text-overflow:ellipsis", "card-open",
                 # The content of a version, inside the tab.
                 "/v1/member/assets/manifest", 'id="asset-detail"', "detail-slot",
                 "Run parameters", "Keyword rules", "Script tools", "Selector hint",
                 "Side effects and permissions", "Instructions", "Full manifest (JSON)",
                 # Administrators manage any asset from the asset tab.
                 'id="asset-kinds"', 'id="view-cards"', 'id="view-table"',
                 "Who can use it", "Owner and co-editors", "Deprecate"):
        assert hook in PAGE, hook
    # The overview, member administration and owner tools.
    for hook in ('id="overview-tiles"', "/v1/member/admin/overview",
                 "/v1/member/admin/members/update", 'id="member-editor"', 'id="member-role"',
                 'id="member-groups"', 'id="owner-editor"', 'id="coeditor-add"',
                 'id="coeditor-list"', 'id="transfer-type"', 'id="transfer-save"',
                 "/v1/member/assets/co-editors/", "/v1/member/assets/transfer",
                 "/v1/member/assets/deprecate", "May publish new versions", "co_editor_unknown",
                 "co_editor_exists", "not_name_owner", "last_administrator", "Last seen",
                 'id="bridge-filter"', 'id="member-filter"', 'id="asset-filter"'):
        assert hook in PAGE, hook
    # A transfer names the new owner before it happens.
    assert "confirm(`Transfer ${owning.namespace}/${owning.name} to ${target}?" in PAGE
    # Markdown is escaped before any tag is added, and links are http(s) only.
    assert "function markdown(" in PAGE and "esc(text).replace(" in PAGE
    assert 'rel="noopener noreferrer"' in PAGE and "(https?:\\/\\/" in PAGE
    # Administrators land on the Overview, members on the Marketplace.
    assert '(admin?"overview":"marketplace")' in PAGE


def _publish_more(app: Any, seeded: dict[str, Any]) -> None:
    """A Skill with Markdown instructions for weekly-check, and two Knowledge
    names whose descriptions differ greatly in length."""
    url = seeded["url"]
    target = AssetIdentity(namespace="lab", name="weekly-check", version=seeded["version"])
    skill = skill_manifest(target)
    skill["instructions"] = SKILL_TEXT
    skill["selector_hint"] = "weekly numbers check"
    status, submitted = request(url + "assets/submit", authorization=seeded["leo"], body={
        "kind": "skill", "change": "minor", "manifest": skill})
    assert status == 200, submitted
    assert request(url + "admin/submissions/approve", authorization=seeded["root"], body={
        "submission_id": submitted["submission"]["submission_id"], "evidence": "read"})[0] == 200
    for name, text in (("short-notes", "Short."), ("long-notes", "Long description. " * 40)):
        identity = identity_of(name)
        item = package(identity, kind="knowledge", visibility="organization").model_copy(
            update={"description": text})
        app.state.packages.publish(item, artifact=artifact_for(identity))


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_tabbed_portal_in_a_real_browser(tmp_path: Path) -> None:
    from integrations.browser import Browser

    with _app(tmp_path, [NOW]) as app:
        seeded = _seed(app)
        _publish_more(app, seeded)
        proof = app.issue_invitation(
            Invitation(invitation_id="invite-admin2", actor="admin2",
                       issued_by="platform-admin", role="platform_admin"),
            expires_at=NOW.replace(year=2027)).bearer
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()

        def js(code: str) -> Any:
            return browser._evaluate(code)

        def text(element: str) -> str:
            return str(js(f'document.getElementById("{element}").textContent'))

        def until(check: Any, seconds: float = 20) -> None:
            deadline = time.monotonic() + seconds
            while not check() and time.monotonic() < deadline:
                time.sleep(0.2)
            assert check()

        def visible_panels() -> list[str]:
            return list(json.loads(str(js(
                'JSON.stringify([...document.querySelectorAll("[role=tabpanel]")]'
                '.filter(p => !p.hidden).map(p => p.id))'))))

        def box(selector: str) -> list[float]:
            return list(json.loads(str(js(
                f'JSON.stringify((r => [r.width, r.height])(document.querySelector('
                f'{json.dumps(selector)}).getBoundingClientRect()))'))))

        def card_heights(container: str) -> list[float]:
            return list(json.loads(str(js(
                f'JSON.stringify([...document.querySelectorAll("#{container} .card")]'
                '.map(c => Math.round(c.getBoundingClientRect().height)))'))))

        try:
            browser.navigate(app.member_base_url + f"/#invitation={proof}")
            # First sign-in sets a password (owner 2026-10-15).
            until(lambda: bool(browser._evaluate(
                'document.getElementById("set-password-form").getClientRects().length')))
            browser._evaluate('document.getElementById("new-password").value='
                              '"lantern orchard pebble 42";'
                              'document.getElementById("new-password-again").value='
                              '"lantern orchard pebble 42";'
                              'document.getElementById("set-password").click(); 0')
            until(lambda: "Registered computers" in text("overview-tiles"))
            assert js('document.getElementById("ptab-overview").getAttribute("aria-selected")'
                      ) == "true"
            tabs = json.loads(str(js('JSON.stringify(tabKeys)')))
            assert tabs == ADMIN_TABS
            until(lambda: text("review-badge") == "1")  # one submission waiting

            # Each tab: its panel alone is shown, has a size, and is in the hash.
            for key in ADMIN_TABS:
                js(f'showTab("{key}"); 0')
                assert visible_panels() == [f"panel-{key}"], key
                width, height = box(f"#panel-{key}")
                assert width > 300 and height > 100, (key, width, height)
                assert js("location.hash") == f"#tab={key}"
            assert js('document.documentElement.scrollWidth <= window.innerWidth + 1') is True

            # Keyboard on the tab bar.
            js('showTab("overview", {focus: true}); 0')
            js('document.getElementById("portal-tabs").dispatchEvent(new KeyboardEvent("keydown",'
               ' {key: "ArrowRight", bubbles: true})); 0')
            assert js("document.activeElement.id") == "ptab-marketplace"
            js('document.getElementById("portal-tabs").dispatchEvent(new KeyboardEvent("keydown",'
               ' {key: "End", bubbles: true})); 0')
            assert visible_panels() == ["panel-members"]

            # Reload and back keep the tab.
            js('showTab("registrations"); 0')
            js("location.reload(); 0")
            until(lambda: "bridge-leo-pc" in text("bridge-rows"))
            assert visible_panels() == ["panel-registrations"]
            assert "probe" in text("bridge-rows")
            js('showTab("members"); 0')
            until(lambda: "newbie" in text("member-rows"))
            js("history.back(); 0")
            until(lambda: visible_panels() == ["panel-registrations"])

            # A tile opens All published assets on its kind; every card one size.
            js('showTab("overview"); 0')
            js('[...document.querySelectorAll("#overview-tiles .tile")].find(t =>'
               ' t.textContent.startsWith("Knowledge")).click(); 0')
            until(lambda: "long-notes" in text("asset-cards"))
            assert visible_panels() == ["panel-assets"]
            assert js('document.querySelector("#asset-kinds [aria-pressed=true]").textContent'
                      ).startswith("Knowledge")
            heights = card_heights("asset-cards")
            assert len(heights) == 3 and max(heights) - min(heights) <= 1, heights
            js('[...document.querySelectorAll("#asset-kinds button")][0].click(); 0')
            heights = card_heights("asset-cards")
            assert len(heights) == 8 and max(heights) - min(heights) <= 1, heights

            # The content of a Workflow opens inside the tab.
            js('[...document.querySelectorAll("#asset-cards .card-open")].find(b =>'
               ' b.textContent === "weekly-check").click(); 0')
            until(lambda: "Steps" in text("detail-content"))
            assert js('document.getElementById("panel-assets").contains('
                      'document.getElementById("asset-detail"))') is True
            assert "read" in text("detail-content") and "Side effects" in text("detail-content")
            assert "Everyone in the organization" in text("detail-facts")
            assert "Owner and co-editors" in text("detail-actions")
            js('document.getElementById("detail-close").click(); 0')
            assert js('document.getElementById("asset-detail").hidden') is True

            # Co-editors and owner of any name, from the asset tab.
            js('[...document.querySelectorAll("#asset-cards .card")].find(c =>'
               ' c.querySelector(".card-open").textContent === "weekly-check")'
               '.querySelector(".card-open").click(); 0')
            until(lambda: "Owner and co-editors" in text("detail-actions"))
            js('[...document.querySelectorAll("#detail-actions button")].find(b =>'
               ' b.textContent === "Owner and co-editors").click(); 0')
            until(lambda: "weekly-check" in text("owner-title"))
            assert "members of team engineering (owner)" in text("owner-publishers")
            js('document.getElementById("coeditor-account").value = "nobody";'
               ' document.getElementById("coeditor-add").click(); 0')
            until(lambda: "not an active member" in text("owner-status"))
            js('document.getElementById("coeditor-account").value = "visitor";'
               ' document.getElementById("coeditor-add").click(); 0')
            until(lambda: "may now publish" in text("owner-status"))
            record = app.state.packages.ownership("lab", "weekly-check")
            assert record is not None and record.co_editors == ("visitor",)
            js('document.getElementById("owner-close").click(); 0')

            # Markdown is escaped before any tag is added.
            rendered = str(js('markdown("<img src=x onerror=alert(1)> **b** '
                              '[x](javascript:alert(1)) [y](https://e.invalid)")'))
            assert "<img" not in rendered and "&lt;img" in rendered
            assert "<strong>b</strong>" in rendered and 'href="javascript' not in rendered
            assert 'href="https://e.invalid"' in rendered

            # A member: four tabs, the Marketplace, cards one size, a Skill's content.
            leo = seeded["leo"].removeprefix("Bearer ")
            js("localStorage.clear(); 0")
            browser.navigate(app.member_base_url + f"/#session={leo}&bridge=bridge-leo-pc")
            until(lambda: "weekly-skill" in text("addon-cards"))
            assert json.loads(str(js('JSON.stringify(tabKeys)'))) == MEMBER_TABS
            assert visible_panels() == ["panel-marketplace"]
            assert js('document.getElementById("ptab-overview")') is None
            heights = card_heights("addon-cards")
            assert len(heights) >= 3 and max(heights) - min(heights) <= 1, heights
            assert "Selected for Bridge" in text("addon-cards")
            js('[...document.querySelectorAll("#addon-cards .card-open")].find(b =>'
               ' b.textContent === "weekly-skill").click(); 0')
            until(lambda: "Keyword rules" in text("detail-content"))
            assert js('document.querySelector("#detail-content .md strong").textContent'
                      ) == "the weekly check"
            assert js('document.querySelector("#detail-content img")') is None
            assert js("window.__pwned === undefined") is True
            assert "lab/weekly-check@" in text("detail-content")
            assert "weekly numbers check" in text("detail-content")
            js('[...document.querySelectorAll("#detail-actions button")].find(b =>'
               ' b.textContent === "Select for install").click(); 0')
            until(lambda: "Selected for this Bridge" in text("detail-status"))
            chosen = {item.asset.name for item in app.state.authorization.selections()}
            assert chosen == {"weekly-check", "weekly-skill"}
        finally:
            browser.close()
            browser.discard_profile()
