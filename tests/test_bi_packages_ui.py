"""A skill/tool package in a browser (owner 2026-11-19: 「GUI和操作，請盡量減化」): 更多 → 匯出
downloads the working domain's zip; 更多 → 匯入 → zip → preview → 匯入到 <工作領域>, with its
progress beside the button, stages it; a command-line script shows 「需改寫」 and its one-press
AI rewrite. All fictional.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_extract import Scripted
from test_bi_packages import CLI, SKILL_BODY, TOOL, _zip
from test_bi_vault import _call, _commit, _ok, _use_homes
from test_vault_asking_e2e import _bi_host, _Model, _served

from aep_bi.cards import packages, vault
from aep_bi.cards.ai_runs import AiRuntime
from aep_bi.host import bi_cards_api

AIDC = "applications/aidc/sources"
WIRELESS = "applications/wireless/sources"


def _attach_zip(page: BiPage, data: bytes, name: str) -> None:
    encoded = base64.b64encode(data).decode("ascii")
    page.run(
        "(() => { const dt = new DataTransfer();"
        f" const bytes = Uint8Array.from(atob({json.dumps(encoded)}), (c) => c.charCodeAt(0));"
        f" dt.items.add(new File([bytes], {json.dumps(name)}, {{type: 'application/zip'}}));"
        " const f = document.getElementById('bi-b-pkg-zip'); f.files = dt.files;"
        " f.dispatchEvent(new Event('change')); })()"
    )


def _open_menu(page: BiPage, button: str) -> None:
    page.run("document.getElementById('bi-b-pkg-menu').open = true")
    page.click(f"#{button}")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_export_and_import_a_package_from_more(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    shared = tmp_path / "sharepoint"
    shared.mkdir()
    made: dict[str, Any] = _ok(
        _call(workspace, "POST", "/api/bi/vaults",
              {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
               "author": "alice"})
    )  # fmt: skip
    vault_id, dataset = str(made["vault"]["id"]), str(made["vault"]["dataset"])
    _use_homes(workspace, vault_id, "AIDC", "Wireless")
    rule = {"home": "aidc", "name": "vendor-extract", "role": "extract", "body": SKILL_BODY,
            "card_types": ["Technology"]}  # fmt: skip
    _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/skills", rule))
    tool = {"home": "aidc", "name": "vendor-rows", "suffix": ".py", "text": TOOL}
    _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/tools", tool))
    _commit(workspace, vault_id, "規則與工具")
    rewriter = Scripted({"reply": "改寫好了。", "needs": [], "code": TOOL, "notes": []})
    monkeypatch.setattr(
        bi_cards_api,
        "web_ai_runtime",
        lambda _web: AiRuntime(
            model=lambda: (rewriter, "test-model"), background=lambda _t, work: work()
        ),
    )
    exported = packages.export_zip(workspace, vault_id, "aidc")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.wait(
                "[...document.getElementById('bi-dataset').options]"
                f".some((o) => o.value === {json.dumps(dataset)})"
            )
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            page.wait("!document.getElementById('bi-b-src-folder-box').hidden")
            page.choose("bi-b-src-folder", AIDC)
            page.stage("schema")
            page.wait("!document.getElementById('bi-b-skills').hidden")
            # Nothing new in sight: 匯入 and 匯出 wait in 更多.
            assert page.run("document.getElementById('bi-b-pkg').hidden") is True
            assert page.run("document.getElementById('bi-b-pkg-menu').open") is False

            # 匯出: the domain's rule and tool, all ticked, downloaded as one zip.
            _open_menu(page, "bi-b-pkg-export")
            page.wait("!!document.getElementById('bi-b-pkg-download')")
            items = page.text_of("bi-b-pkg-items")
            assert "vendor-extract" in items and "vendor-rows" in items
            page.click("#bi-b-pkg-download")
            page.see("bi-b-pkg-export-status", "已下載 aep-bi-aidc.zip")
            download = page.run("bi.pkg.lastDownload")
            assert download["items"] == 2 and download["bytes"] > 200

            # 匯入 into Wireless: preview, then staged with its progress beside the button.
            page.choose("bi-b-src-folder", WIRELESS)
            _open_menu(page, "bi-b-pkg-import")
            page.see("bi-b-pkg", "匯入判讀規則和工具到")
            _attach_zip(page, exported, "aep-bi-aidc.zip")
            page.wait("!!document.getElementById('bi-b-pkg-apply')")
            preview = page.text_of("bi-b-pkg-preview")
            assert "新增" in preview and "vendor-extract" in preview and "vendor-rows" in preview
            assert "防止失誤" in preview, "the sandbox is described truthfully"
            assert (
                page.run(
                    "document.getElementById('bi-b-pkg-apply').closest('.bi-actions')"
                    ".nextElementSibling.id"
                )
                == "bi-b-pkg-apply-status"
            ), "the progress line is beside the button"
            assert "匯入到 " in page.text_of("bi-b-pkg-apply")
            page.click("#bi-b-pkg-apply")
            page.see("bi-b-pkg-apply-status", "已加入 2 項待提交改動")
            units = vault.Vault(workspace, vault_id).repo.working_units()
            assert units["skill:wireless/vendor-extract"]["applies_to"] == [WIRELESS]
            assert "tool:wireless/vendor-rows" in units

            # A command-line script: 「需改寫」, and 用 AI 改寫 asks the tool AI in one press.
            _open_menu(page, "bi-b-pkg-import")
            _attach_zip(page, _zip({"tools/bi_ingest.py": CLI}), "scripts.zip")
            page.wait("!!document.getElementById('bi-b-pkg-apply')")
            page.see("bi-b-pkg-preview", "需改寫")
            page.see("bi-b-pkg-preview", "沒有 aep-bi-package.json")
            page.click("#bi-b-pkg-apply")
            page.see("bi-b-pkg-apply-status", "已加入 1 項")
            page.see("bi-b-tl-list", "需改寫")
            assert "對選取的來源執行" not in page.run(
                "[...document.querySelectorAll('#bi-b-tl-list tr')]"
                ".find((r) => r.textContent.includes('bi-ingest')).textContent"
            )
            page.click_text("#bi-b-tl-list", "用 AI 改寫")
            page.wait("bi.ai && bi.ai.kind === 'tool'")
            page.see("bi-ai-log", "改寫好了")
            sent = " ".join(m.text for m in rewriter.requests[0].messages)
            assert "改寫成讀 INPUT" in sent and "argparse" in sent, "the script and the ask"
            assert "argparse" in page.run("document.getElementById('bi-b-tl-code').value")
