"""Shared test setup: no test reaches Telegram's getMe over the network."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NoReturn

import pytest

from host_runtime import bot_identity


class _Offline:
    def send(self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float) -> NoReturn:
        raise OSError("tests are offline")


@pytest.fixture(autouse=True)
def _bot_identity_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot_identity, "TRANSPORT_FACTORY", _Offline)
