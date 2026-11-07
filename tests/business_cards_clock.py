"""A fixed contact-edit day, independent of collection time and host timezone."""

from datetime import UTC, date, datetime
from typing import Self

import pytest

from capabilities.business_cards import store


@pytest.fixture(name="contact_today")
def fixed_contact_day(monkeypatch: pytest.MonkeyPatch) -> date:
    today = date(2026, 11, 6)

    class StatementDay(date):
        @classmethod
        def today(cls) -> Self:
            return cls(2026, 11, 6)

    monkeypatch.setattr(store, "date", StatementDay)
    monkeypatch.setattr(store, "_clock", lambda: datetime(2026, 11, 6, 12, tzinfo=UTC))
    return today
