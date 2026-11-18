"""The LLM Wiki maintenance as a feature: its parts of the Host, asked through `features`.

The Knowledge tab's `知識庫維護` (intake, convert and curation in a sandbox or a
wiki repository, and the repositories' versions)
(docs/phases/FEATURE_PLUGIN_WIKI_PROPOSAL_DRAFT_20261118.md, owner consent
2026-11-18). Each hook calls the code that was called from core before; nothing
here decides anything of its own. Asking a vault or a published wiki repository
(`knowledge_binding`, the Knowledge harness and the formats it reads) is core's.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from pathlib import Path
from typing import Any

from host_runtime import wiki_bench, wiki_host, wiki_page, wiki_web
from host_runtime.features import Feature
from knowledge.repo import wiki

#: Its page fragments go before BI's (`DEFAULT_PAGE_ORDER`), where they were.
PAGE_ORDER = 50


class WikiFeature(Feature):
    name = "llm-wiki"
    page_order = PAGE_ORDER

    def startup(self, workspace_root: Path) -> None:
        # A wiki repository's push is checked against its recorded test runs (R4a).
        wiki.set_benchmark(partial(wiki_bench.gate, workspace_root))

    def handle(self, handler: Any, method: str, parsed: Any) -> bool:
        # The wiki repositories (R4a) and the Knowledge tab's maintenance routes.
        return wiki_web.handle(handler, method, parsed)

    def page_fragments(self) -> Mapping[str, str]:
        return {
            "feature_css": wiki_page.WIKI_CSS,
            "knowledge_pane": wiki_page.WIKI_PANE_HTML,
            "feature_js": wiki_page.WIKI_JS,
        }

    def service(self, name: str) -> Any | None:
        # `knowledge_pipeline_bindings`: the pipeline's 21 capabilities, built from
        # host.json at the Host's place for them; `wiki_web`: Agent Web's
        # maintenance part (the steps, and the sandboxes Reviews opens).
        if name == "knowledge_pipeline_bindings":
            return wiki_host.pipeline_bindings
        if name == "wiki_web":
            return wiki_web.WikiWeb
        return None


FEATURE = WikiFeature()
