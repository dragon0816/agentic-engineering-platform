"""The domains' collect and review times, run by the resident host while it is up.

Each enabled domain has two local times (BI 「管理」). A poll every `interval_s`
seconds finds, for each time, its latest occurrence that is not older than a day and
not before the setting was saved; that occurrence is claimed once in the inbox's file
(so a restart, a second poll or a second process never runs it again: AGENTS rule 21)
and run as a tracked background task, which Agent Web's restart check sees (AGENTS
rule 19). A PC that was off at 07:30 and starts at 09:00 runs that morning's collect
once; an older one is not replayed. No n8n (AGENTS rule 3).

Why not the Host schedule store: its targets are installed Workflows and Agent Tasks,
neither of which reaches Agent Web's model that an AI ingest needs (assessment §4); a
new target kind would be a core change outside the owner's consent of 2026-11-19.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aep_bi.inbox import domains as dom
from aep_bi.inbox.store import Inbox

POLL_SECONDS = 30.0
#: An occurrence older than this when first seen is not run.
CATCH_UP = timedelta(hours=20)

#: (kind, domain key) -> the work to run in the background for it.
Job = Callable[[str, str], Callable[[], None]]
#: (title, work) -> run `work` in the background.
Runner = Callable[[str, Callable[[], None]], None]


class Scheduler:
    def __init__(
        self,
        workspace: Path,
        job: Job,
        run: Runner,
        *,
        interval_s: float = POLL_SECONDS,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.workspace = workspace
        self.job = job
        self.run = run
        self.interval_s = interval_s
        self.clock = clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def tick(self) -> list[tuple[str, str]]:
        """Start what is due now; the (kind, domain) pairs started."""
        inbox = Inbox(self.workspace)
        now = self.clock()
        started: list[tuple[str, str]] = []
        for setting in inbox.settings().values():
            if not setting.enabled:
                continue
            saved = datetime.fromisoformat(setting.saved_at)
            for kind, clock in (("collect", setting.collect_at), ("review", setting.review_at)):
                if not clock:
                    continue
                due = dom.last_at(clock, now)
                if due < saved or now - due > CATCH_UP:
                    continue
                key = f"{kind}:{setting.domain}:{due.astimezone(UTC).isoformat()}"
                if inbox.claim_occurrence(key):
                    label = "收集" if kind == "collect" else "審核提醒"
                    self.run(f"BI 收集箱{label}：{setting.domain}", self.job(kind, setting.domain))
                    started.append((kind, setting.domain))
        return started

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="bi-inbox-schedule", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:  # noqa: BLE001 - one failed poll never ends the loop
                pass
            self._stop.wait(self.interval_s)
