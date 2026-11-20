"""BI Knowledge as a feature: its parts of the Host, asked through `features`.

Each hook calls the BI code that was called from core before (proposal r3,
stage A); nothing here decides anything of its own.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from functools import partial
from pathlib import Path
from typing import Any

from aep_bi.cards import vault as bi_vault
from aep_bi.cards.capability import bindings as bi_cards_bindings
from aep_bi.cards.manifest import bi_knowledge_skill
from aep_bi.host import (
    bi_assistant_query,
    bi_bench,
    bi_cards_api,
    bi_chat_save,
    bi_feed_api,
    bi_page,
    bi_subscriptions,
    bi_vaults_api,
)
from aep_bi.host.bi_cards_tools import (
    ATLAS_PORT,
    atlas_embeds,
    bi_cards_tools,
    bi_chart_files,
    bi_question,
    bi_skill_on,
    with_bi_sources,
)
from aep_bi.inbox.runtime import RUNTIME as INBOX
from host_runtime.features import (
    Feature,
    Messenger,
    PackageInstaller,
    PackageRefused,
    PreparedPackage,
    TelegramAnswer,
    TelegramItem,
    TelegramQuestion,
)

FEED_POST_REFUSAL = "the feed answers GET only"


class BiFeature(Feature):
    name = "bi-knowledge"

    def startup(self, workspace_root: Path) -> None:
        # A BI vault's push is checked against its recorded test runs (BI T1).
        bi_vault.set_benchmark(partial(bi_bench.gate, workspace_root))
        # The Telegram inbox's workspace (owner 2026-11-19).
        INBOX.workspace = workspace_root

    def capability_bindings(
        self, workspace_root: Path, approved: Sequence[str]
    ) -> Iterable[tuple[Any, Any, Any, Any]]:
        # `approved` is not a BI gate: BI reads every data class (owner 2026-11-17).
        return bi_cards_bindings(workspace_root)

    def host_tools(self, gateway: Any) -> Iterable[Any]:
        return bi_cards_tools(gateway)

    def shipped_skills(self) -> Iterable[Any]:
        # BI knowledge cards (owner 2026-10-21, Case A): switched on in every install.
        return (bi_knowledge_skill(),)

    def public_get(self, handler: Any, path: str, query: str, workspace_root: Path) -> bool:
        # The BI analysis feed, read by Atlas without the page token (owner 2026-11-01).
        return bi_feed_api.handle(handler, "GET", path, query, workspace_root)

    def refuses_post(self, path: str) -> str | None:
        return FEED_POST_REFUSAL if bi_feed_api.is_feed(path) else None

    def handle(self, handler: Any, method: str, parsed: Any) -> bool:
        return bi_cards_api.handle(handler, method, parsed)  # BI cards (Case A)

    def turn_context(self, item: Any) -> AbstractContextManager[None]:
        return _atlas_port(getattr(item, "atlas_port", None))

    def answer_files(self, result: Any) -> list[dict[str, Any]]:
        # A BI query's chart page (BI C2) shows in a sandboxed frame.
        return list(bi_chart_files(result))

    def answer_embeds(self, result: Any) -> list[dict[str, Any]]:
        return list(atlas_embeds(result))

    def finish_answer(self, text: str, result: Any) -> str:
        # A subscribed BI dataset's source line, when the model left it out.
        return with_bi_sources(text, result)

    def bypasses_knowledge(self, message: str, gateway: Any) -> bool:
        # A BI cards question goes to the model and bi__query, not the vault.
        return bool(bi_question(message) and bi_skill_on(gateway))

    def assistant_tool(self, name: str) -> Callable[..., dict[str, Any]] | None:
        return bi_assistant_query.answer if name == "aep_bi_query" else None

    def askable_vaults(self, web: Any, granted: Any, entry: Any) -> list[dict[str, Any]]:
        return bi_vaults_api.askable_vaults(web, granted, entry)

    def observe_catalog(self, workspace_root: Path, platform: Any, discovered: Any) -> None:
        # Subscribed BI datasets: the update badge, stopped (no access) or offline.
        bi_subscriptions.observe_catalog(workspace_root, platform, discovered)

    def page_fragments(self) -> Mapping[str, str]:
        return {
            "feature_css": bi_page.BI_CSS,
            "knowledge_pane": bi_page.BI_PANE_HTML,
            "feature_js": bi_page.BI_JS,
        }

    def package_installer(self, kind: str) -> PackageInstaller | None:
        # A subscribed, read-only BI dataset copy from the Shared Platform.
        return _BI_DATASETS if kind == bi_subscriptions.KIND else None

    def service(self, name: str) -> Any | None:
        # The chat's saved-analysis proposals (BI C3) plan and apply here.
        return bi_chat_save if name == "bi_chat_save" else None

    def telegram_item(self, item: TelegramItem, host: Any) -> TelegramAnswer | None:
        # What a domain's collection bot receives goes to that domain's inbox.
        bot = INBOX.bot(host)
        return None if bot is None else bot.handle(item)

    def telegram_question(
        self, item: TelegramItem, host: Any, gateway: Any
    ) -> TelegramQuestion | TelegramAnswer | None:
        # A plain question to a domain's bot: bi__query on that domain (owner 2026-11-21).
        bot = INBOX.bot(host)
        return None if bot is None else bot.question(item, bi_cards_tools(gateway))

    def telegram_ready(self, messenger: Messenger, host: Any) -> None:
        # Reminders and results go out through Telegram; the inbox schedule starts.
        INBOX.ready(messenger, host)


class _Prepared:
    def __init__(self, held: bi_subscriptions.PreparedInstall) -> None:
        self.held = held

    def commit(self) -> None:
        try:
            self.held.commit()
        except bi_subscriptions.SubscriptionError as error:
            raise PackageRefused(error.code) from None

    def rollback(self) -> None:
        self.held.rollback()


class _BiDatasets:
    def prepare(
        self,
        workspace_root: Path,
        namespace: str,
        name: str,
        version: str,
        content: bytes,
        sha256: str,
    ) -> PreparedPackage:
        try:
            held = bi_subscriptions.prepare(
                workspace_root, namespace, name, version, content, sha256
            )
        except bi_subscriptions.SubscriptionError as error:
            raise PackageRefused(error.code) from None
        return _Prepared(held)


_BI_DATASETS = _BiDatasets()


@contextmanager
def _atlas_port(port: int | None) -> Iterator[None]:
    token = ATLAS_PORT.set(port)
    try:
        yield
    finally:
        ATLAS_PORT.reset(token)


FEATURE = BiFeature()
