"""Shared test setup: no test reaches Telegram's getMe over the network, and BI
extraction reads one chunk at a time unless a test asks for more."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NoReturn

import pytest

from aep_bi.cards import extract
from host_runtime import bot_identity


class _Offline:
    def send(self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float) -> NoReturn:
        raise OSError("tests are offline")


@pytest.fixture(autouse=True)
def _bot_identity_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot_identity, "TRANSPORT_FACTORY", _Offline)


@pytest.fixture(autouse=True)
def _bi_chunks_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    # Scripted test models answer in call order; parallel chunks are tested on purpose
    # (tests/test_bi_ingest_parallel_stop.py).
    monkeypatch.setattr(extract, "PARALLEL_PARTS", 1)
