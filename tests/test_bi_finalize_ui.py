"""定案 on a card, and step 3 saying a regression elsewhere does not stop this push.

Owner, 2026-11-05: after a meeting, the person responsible settles a field. A real browser on
fictional data. `docs/phases/BI_PAGE_SIMPLE.md` §14.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _import, _ok, _row
from test_vault_asking_e2e import _bi_host, _Model, _served

from capabilities.bi_cards.store import BiStore
from host_runtime import bi_bench

QUIET = "window.__aepWatch.open.length === 0"


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_field_is_settled_on_its_card_and_a_failure_elsewhere_is_only_a_note(
    tmp_path: Path,
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
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
    _import(workspace, dataset, _row("TSN", standard_body="IEEE"), filename="seed.csv")
    for slug, home in (("wl-q", "wireless"),):
        body = {"question": f"虛構題 {slug}？", "must": ["好"], "slug": slug, "home": home}
        _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/checks", body))
    _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/commit", {"purpose": "題目"}))
    _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/push", {}))

    def ask(_question: str, side: bi_bench.Side) -> dict[str, Any]:
        return {"ok": True, "answer": "不知道" if side == "working" else "好"}

    bi_bench.run(workspace, vault_id, ask=ask, extract=lambda c: [], actor="alice")
    body = {"question": "虛構題 新？", "must": ["好"], "slug": "aidc-q", "home": "aidc"}
    _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/checks", body))

    store = BiStore(workspace, dataset)
    card = next(r for r in store.card_rows() if r["canonical_key"] == "TSN")["id"]
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "final" if shots else None
        ) as page:
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            page.wait("(bi.build.homes || []).length > 0")
            page.choose("bi-b-src-folder", "applications/aidc/sources")
            page.stage("test")
            page.wait(QUIET, 60)

            # -- step 3: the change is in aidc, and the failure in wireless does not stop it ---
            page.wait(
                "document.getElementById('bi-b-bench-report').textContent.includes('其他領域')", 60
            )
            report = page.text_of("bi-b-bench-report")
            assert "不擋這次 push" in report and "（wireless）" in report
            assert "Push 會被擋" not in report
            page.shoot("step3")

            # -- 定案 on a card: value, reason, and it says what is next --------------------
            page.click("#bi-views [data-bi-view=cards]")
            page.wait(QUIET, 60)
            page.choose("bi-card-domain", "")
            page.wait(QUIET, 60)
            page.run(f"biOpenCard({card!r})")
            page.wait(
                "[...document.querySelectorAll('#bi-detail-body button')]"
                ".some((b) => (b.getAttribute('aria-label') || '').startsWith('定案'))",
                60,
            )
            page.run(
                "[...document.querySelectorAll('#bi-detail-body button')]"
                ".find((b) => (b.getAttribute('aria-label') || '').startsWith('定案')"
                " && b.parentElement.parentElement.textContent.includes('IEEE')).click()"
            )
            form = "document.querySelector('#bi-detail-body .bi-final')"
            page.wait(f"!!{form}", 30)
            # With no reason it does not settle.
            page.run(f"{form}.querySelector('input').value = 'ETSI'; {form}.requestSubmit()")
            page.wait(f"{form}.textContent.includes('沒有定案')", 30)
            assert store.fields(card)["standard_body"]["value"] == "IEEE"
            page.run(
                f"{form}.querySelectorAll('input')[1].value = '11-05 會議決定';"
                f" {form}.requestSubmit()"
            )
            page.see("bi-notice", "已定案")
            assert "commit 並 push" in page.text_of("bi-notice")
            assert store.fields(card)["standard_body"]["value"] == "ETSI"
            page.wait("document.getElementById('bi-detail-body').textContent.includes('ETSI')", 60)
            page.shoot("settled")
