"""Feature mount points: core without the LLM Wiki maintenance, and the Wiki through them.

docs/phases/FEATURE_PLUGIN_WIKI_PROPOSAL_DRAFT_20261118.md (owner consent
2026-11-18): the Host reaches the Wiki maintenance only through
`host_runtime.features`, so a feature set without it is a working AEP whose
Knowledge asking, BI, Reviews and memory are unchanged, and its page parts go
where they were (`page_order`, the core stand-in table).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from bi_page_driver import _WATCH, browser_missing
from test_agent_web import base, fetch, knowledge_runtime
from test_host_wiring import membership_record, workspace
from test_knowledge_pipeline_host import _grants
from test_knowledge_sandbox import _base
from test_product_e2e_05 import V1
from test_review_proposals import _finding, _report

from aep_bi import feature as features_bi
from aep_wiki import feature as features_wiki
from host_runtime import features, web_page
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from integrations.browser import Browser

ROOT = Path(__file__).resolve().parents[1]
BI_PLUGIN = ROOT / "feature_plugins" / "bi_knowledge" / "python"
WIKI = features_wiki.FEATURE
BI = features_bi.FEATURE
ONLY_BI = features.FeatureSet((BI,))
ONLY_WIKI = features.FeatureSet((WIKI,))
NEITHER = features.FeatureSet(())
COMBINATIONS = {"only BI": ONLY_BI, "only Wiki": ONLY_WIKI, "neither": NEITHER}
#: The Wiki maintenance's package (the plugin's `python/`); without the feature no
#: core module imports any of it.
WIKI_PLUGIN = ROOT / "feature_plugins" / "llm_wiki" / "python"


def test_the_running_features_are_the_wiki_and_bi_and_the_wiki_page_comes_first() -> None:
    assert [feature.name for feature in features.active()] == ["bi-knowledge", "llm-wiki"]
    both = features.FeatureSet((WIKI, BI)).page_fragments()
    # Whatever order the features load in, the Wiki's parts are placed before BI's.
    assert features.FeatureSet((BI, WIKI)).page_fragments() == both
    assert web_page.page(features.FeatureSet((BI, WIKI))) == web_page.page()
    page = web_page.page()
    assert page.index('id="kn-pane-pipeline"') < page.index('id="kn-pane-bi"')
    assert "LLM Wiki is not installed" not in page and "BI Knowledge is not installed" not in page


def test_without_the_wiki_the_page_keeps_the_shell_and_offers_no_maintenance_tab() -> None:
    page = web_page.page(ONLY_BI)
    assert "LLM Wiki is not installed" in page
    assert '#kn-tabs [data-kn="pipeline"] { display: none; }' in page
    for mount in (
        'id="kn-pane-pipeline"',
        'id="kp-status"',
        'id="kp-status-text"',
        'id="kp-status-time"',
        'id="kp-progress"',
        'id="kp-askable"',
        'id="kn-pane-bi"',
        'id="bi-dataset"',
    ):
        assert page.count(mount) == 1, mount
    assert 'id="kp-stepper"' not in page and "function kpStage(" not in page
    # Every Wiki name the shell itself calls has a stand-in; the shared helpers stay.
    for name in ("pipeline", "kpOpen", "loadKnowledge"):
        assert page.count(f"function {name}(") == 1, name
    for name in ("kpRun", "kpStatus", "kpWithProgress", "kpButton", "askableLoad", "stepperSet"):
        assert page.count(f"function {name}(") == 1, name
    # Neither feature: both stand-ins, each once.
    bare = web_page.page(NEITHER)
    assert "LLM Wiki is not installed" in bare and "BI Knowledge is not installed" in bare
    for mount in ('id="kn-pane-pipeline"', 'id="kn-pane-bi"', 'id="kp-askable"'):
        assert bare.count(mount) == 1, mount


def test_an_in_process_plugin_places_its_page_parts_by_its_manifest() -> None:
    class Late(features.Feature):
        name = "late"

        def page_fragments(self) -> dict[str, str]:
            return {"feature_js": "/* late */"}

    class Early(Late):
        name = "early"
        page_order = 10

        def page_fragments(self) -> dict[str, str]:
            return {"feature_js": "/* early */"}

    joined = features.FeatureSet((Late(), Early())).page_fragments()
    assert joined["feature_js"] == "/* early *//* late */"


def test_core_modules_import_no_wiki_maintenance_code_without_the_feature() -> None:
    script = (
        "import sys\n"
        "import host_runtime.host, host_runtime.web, host_runtime.sync, channels.telegram\n"
        "import host_runtime.change_proposals, host_runtime.assistant_tools\n"
        "import host_runtime.knowledge_binding, host_runtime.assets, host_runtime.web_page\n"
        "import host_runtime.agent_mode, knowledge.wiki_repos, knowledge.query\n"
        "host_runtime.web_page.page()\n"
        "print('\\n'.join(sorted(n for n in sys.modules"
        " if n == 'aep_wiki' or n.startswith('aep_wiki.'))))\n"
    )
    found = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env={
            **os.environ,
            # The Wiki stays importable, so a core module that reached it would be listed.
            "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(BI_PLUGIN), str(WIKI_PLUGIN)]),
            "AEP_BUNDLED_PLUGINS": "",
        },
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert found.returncode == 0, found.stderr
    assert found.stdout.split() == []


def test_without_the_wiki_the_host_offers_no_pipeline_capability_or_route(tmp_path: Path) -> None:
    with features.use(ONLY_BI), _served(tmp_path) as (web, server):
        assert web.wiki is None
        assert _pipeline_capabilities(web) == 0
        for path in ("/api/knowledge/pipeline", "/api/knowledge/repos", "/api/knowledge/push"):
            assert fetch(base(server) + path, token=server.token).status == 404, path
        for path in ("/api/knowledge/pipeline/call", "/api/knowledge/repos/create"):
            assert fetch(base(server) + path, token=server.token, body={}).status == 404, path
        # BI and asking-side routes are still served.
        assert fetch(base(server) + "/api/bi/datasets", token=server.token).status == 200
        assert fetch(base(server) + "/api/knowledge/askable", token=server.token).status == 200
        # An agent's Knowledge tools say the pipeline is off, as without host.json's.
        assert web.agent_mode.knowledge is None
        # Reviews: an accepted rule edit is followed up by hand; a sandbox route
        # shows no outcome.
        assert web._outcome("sandbox:sb-x") == ""
        workspace_root = web.runtime.layout.workspace_root
        _report(workspace_root, _finding("rule_edit", "skills/ingest-notes/SKILL.md"))
        listed = web.reviews()["proposals"]
        decided = web.review_decide(listed[0]["proposal_id"], "accept", None, None)
        routed = next(p for p in decided["proposals"] if p["kind"] == "rule_edit")
        assert routed["route"] == "manual"


def test_with_the_wiki_the_same_host_serves_the_pipeline(tmp_path: Path) -> None:
    with features.use(ONLY_WIKI), _served(tmp_path) as (web, server):
        assert web.wiki is not None and web.agent_mode.knowledge is web.wiki
        assert _pipeline_capabilities(web) == 21
        reply = fetch(base(server) + "/api/knowledge/pipeline", token=server.token)
        assert reply.status == 200 and json.loads(reply.body)["enabled"] is True
        assert fetch(base(server) + "/api/bi/datasets", token=server.token).status == 404


@pytest.mark.parametrize("chosen", list(COMBINATIONS))
def test_knowledge_asking_works_with_or_without_either_feature(tmp_path: Path, chosen: str) -> None:
    with features.use(COMBINATIONS[chosen]), knowledge_runtime(tmp_path) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            answered = fetch(
                base(server) + "/api/knowledge/ask",
                token=server.token,
                body={
                    "asset": V1.model_dump(mode="json"),
                    "question": "What firmware does Safe mode require?",
                },
            ).json()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    assert answered["ok"] is True
    assert answered["answer"] == "Safe mode requires firmware 2.0 [1]."
    assert answered["record"]["cited_passages"]


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
@pytest.mark.parametrize("chosen", list(COMBINATIONS))
def test_the_page_loads_and_knowledge_opens_with_no_script_error(
    tmp_path: Path, chosen: str
) -> None:
    with features.use(COMBINATIONS[chosen]), _served(tmp_path) as (_web, server):
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()
        try:
            browser.page().call("Page.enable")
            browser.page().call("Page.addScriptToEvaluateOnNewDocument", source=_WATCH)
            browser.navigate(server.address)
            _wait(browser, '!document.getElementById("send").disabled')
            for tab in ("knowledge", "reviews", "memory", "knowledge"):
                browser.evaluate(f"document.getElementById('nav-{tab}').click()")
                _wait(browser, f"!document.getElementById('panel-{tab}').hidden")
                _wait(browser, "window.__aepWatch.open.length === 0")
            shown = {
                name: browser.evaluate(
                    f"getComputedStyle(document.querySelector('#kn-tabs [data-kn=\"{name}\"]'))"
                    ".display"
                )
                for name in ("pipeline", "bi")
            }
            assert (shown["pipeline"] != "none") == (chosen == "only Wiki")
            assert (shown["bi"] != "none") == (chosen == "only BI")
            assert browser.evaluate("window.__aepWatch.errors") == []
        finally:
            browser.close()


def _pipeline_capabilities(web: AgentWeb) -> int:
    installed = web.runtime.agent.gateway.bridge.installed
    return sum(
        binding.spec.identity.namespace == "knowledge-pipeline"
        for binding in installed._bindings.values()
    )


def _wait(browser: Browser, expression: str, seconds: float = 60) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if browser.evaluate(expression):
            return
        time.sleep(0.2)
    raise AssertionError(expression)


@contextmanager
def _served(tmp_path: Path) -> Iterator[tuple[AgentWeb, AgentWebServer]]:
    vault = _base(tmp_path)
    config, _ = workspace(
        tmp_path,
        membership=membership_record(),
        grants=_grants(),
        config_changes={"knowledge_pipeline": {"vaults": [{"name": "k-test", "root": str(vault)}]}},
    )
    with build_runtime(config) as runtime:
        web = AgentWeb(runtime)
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield web, server
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
