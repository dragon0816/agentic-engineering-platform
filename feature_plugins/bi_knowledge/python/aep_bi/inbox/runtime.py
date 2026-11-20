"""The inbox's process-wide parts: the workspace, the Telegram messenger and Agent Web.

`BiFeature.startup` gives the workspace; `telegram_ready` gives the messenger and the
host when Agent Web attaches Telegram, and starts the schedule once. The browser
fallback for login-walled Threads/Instagram posts is off until the owner turns it on
(`options.json` beside the inbox file: `{"browser_fallback": true}`), after testing
real links (assessment §8).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from aep_bi.inbox import fetch
from aep_bi.inbox.bot import Bot
from aep_bi.inbox.process import Processor
from aep_bi.inbox.scheduler import Scheduler
from aep_bi.inbox.store import Inbox
from host_runtime.features import Messenger

OPTIONS_FILE = "options.json"


class InboxRuntime:
    def __init__(self) -> None:
        self.workspace: Path | None = None
        self.messenger: Messenger | None = None
        self.host: Any = None
        self.scheduler: Scheduler | None = None
        self._lock = threading.Lock()

    def bot(self, host: Any) -> Bot | None:
        if self.workspace is None:
            return None
        return Bot(self.workspace)

    def options(self) -> dict[str, Any]:
        if self.workspace is None:
            return {}
        path = Inbox(self.workspace).dir / OPTIONS_FILE
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    def processor(self, host: Any = None) -> Processor | None:
        if self.workspace is None:
            return None
        chosen = host if host is not None else self.host
        ai = None
        if chosen is not None:
            from aep_bi.host.bi_cards_api import web_ai_runtime

            ai = web_ai_runtime(chosen)
        browser = None
        if self.options().get("browser_fallback") is True:
            profile = Inbox(self.workspace).dir / "browser-profile"
            browser = lambda url: fetch.browser_fetch(url, profile)  # noqa: E731
        return Processor(self.workspace, ai, self.messenger, browser=browser)

    def ready(self, messenger: Messenger, host: Any) -> None:
        with self._lock:
            self.messenger, self.host = messenger, host
            if self.workspace is None or self.scheduler is not None:
                return
            self.scheduler = Scheduler(self.workspace, self._job, self._run)
            self.scheduler.start()

    def _job(self, kind: str, key: str) -> Any:
        def work() -> None:
            processor = self.processor()
            if processor is None:
                return
            if kind == "collect":
                processor.collect(key)
            else:
                processor.remind(key)

        return work

    def _run(self, title: str, work: Any) -> None:
        host = self.host
        tasks = getattr(host, "tasks", None)
        if callable(tasks):

            def tracked() -> tuple[str, str]:
                work()
                return "succeeded", title

            target = tasks().tracked("bi-inbox", title, "", tracked)
        else:
            target = work
        threading.Thread(target=target, name="bi-inbox", daemon=True).start()


RUNTIME = InboxRuntime()
