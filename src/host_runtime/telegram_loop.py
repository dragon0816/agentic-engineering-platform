"""Poll Telegram inside the Agent Web process, on a thread of its own.

`aep-host telegram` remains for a host without Agent Web. Here the loop starts
when the host has a Telegram configuration and is replaced when the settings
page saves a new one, so configuring the bot needs no restart.
"""

from __future__ import annotations

import asyncio
import threading

from channels.telegram import TelegramIngress


class ResidentTelegram:
    def __init__(self, ingress: TelegramIngress) -> None:
        self.ingress = ingress
        self.failure: str | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._ready = threading.Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="telegram-poll", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._stop = asyncio.Event()
        self._ready.set()
        try:
            failure = loop.run_until_complete(self.ingress.run(self._stop))
            self.failure = None if failure is None else failure.code
        except Exception:  # pragma: no cover - reported as a stopped loop, never raised
            self.failure = "telegram_loop_crashed"
        finally:
            loop.close()

    def stop(self, timeout: float = 60.0) -> None:
        if self._loop is not None and self._stop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
