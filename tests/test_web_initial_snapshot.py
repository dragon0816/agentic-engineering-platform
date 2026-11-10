"""A first-page snapshot must not combine old rows with newly reset pagination."""

import time
from typing import Any

import pytest

from integrations.web_script import (
    ScriptRunner,
    WebAction,
    WebPagination,
    WebScript,
    WebScriptError,
)


class ObservationPage:
    clicks = 0
    url = "https://example.test/orders"

    def navigate(self, url: str) -> None:
        raise AssertionError("no navigation is needed")

    def reload(self, **options: Any) -> None:
        raise AssertionError("no reload is needed")

    def evaluate(self, expression: str) -> Any:
        if expression == "document.location.href":
            return self.url
        raise AssertionError("observations are controlled by the fixture")

    def click_at(self, x: float, y: float) -> None:
        self.clicks += 1


def paginated_action(max_pages: int = 200) -> WebAction:
    return WebAction.model_validate(
        {
            "do": "read_table",
            "table": "#orders",
            "save_as": "orders",
            "pagination": {
                "current": {"css": "#current"},
                "total": {"css": "#total"},
                "next": {"css": "#next"},
                "key_columns": ["ID"],
                "max_pages": max_pages,
            },
        }
    )


class ObservedRunner(ScriptRunner):
    numbers = (1, 1)
    rows = [{"ID": "fresh-first-page"}]
    truncated = False
    row_reads = 0

    def _table_rows(self, action: WebAction, **options: Any) -> dict[str, Any]:
        self.row_reads += 1
        return {"rows": self.rows, "truncated": self.truncated}

    def _page_numbers(self, paging: WebPagination) -> tuple[int, int]:
        return self.numbers


def test_initial_rows_are_reread_when_pagination_changes_during_capture() -> None:
    class TransitioningRunner(ObservedRunner):
        numbers = (26, 26)
        row_reads = 0

        def _table_rows(self, action: WebAction, **options: Any) -> dict[str, Any]:
            self.row_reads += 1
            if self.row_reads == 1:
                # The table was sampled before the pending query reset its paginator.
                self.numbers = (1, 1)
                return {"rows": [{"ID": "old-final-page"}], "truncated": False}
            return {"rows": [{"ID": "fresh-first-page"}], "truncated": False}

    page = ObservationPage()
    runner = TransitioningRunner(page, ("https://example.test",), settle_s=0, timeout_s=1)
    action = WebAction.model_validate(
        {
            "do": "read_table",
            "table": "#orders",
            "save_as": "orders",
            "pagination": {
                "current": {"css": "#current"},
                "total": {"css": "#total"},
                "next": {"css": "#next"},
                "key_columns": ["ID"],
            },
        }
    )

    result = runner.run(WebScript(actions=(action,)), "read")

    assert result.data["orders"] == [{"ID": "fresh-first-page"}]
    assert runner.row_reads >= 2
    assert page.clicks == 0


def test_consistent_nonfirst_page_is_refused_without_settling_or_clicking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_sleep(seconds: float) -> None:
        raise AssertionError("a consistent nonfirst page must fail immediately")

    monkeypatch.setattr(time, "sleep", unexpected_sleep)
    page = ObservationPage()
    runner = ObservedRunner(page, ("https://example.test",), settle_s=0.5)
    runner.numbers = (26, 26)
    with pytest.raises(WebScriptError, match="web_pagination_not_at_start"):
        runner.run(WebScript(actions=(paginated_action(),)), "read")
    assert runner.row_reads == 1 and page.clicks == 0


@pytest.mark.parametrize("changing", ["numbers", "rows"])
def test_unstable_initial_snapshot_stops_with_one_bounded_deadline(
    monkeypatch: pytest.MonkeyPatch, changing: str
) -> None:
    now = 0.0

    def clock() -> float:
        nonlocal now
        now += 0.02
        return now

    monkeypatch.setattr(time, "monotonic", clock)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)

    class ChangingRunner(ObservedRunner):
        page_reads = 0

        def _table_rows(self, action: WebAction, **options: Any) -> dict[str, Any]:
            result = super()._table_rows(action, **options)
            if changing == "rows":
                result["rows"] = [{"ID": str(self.row_reads)}]
            return result

        def _page_numbers(self, paging: WebPagination) -> tuple[int, int]:
            self.page_reads += 1
            return (1, 1 + self.page_reads % 2) if changing == "numbers" else (1, 1)

    page = ObservationPage()
    runner = ChangingRunner(page, ("https://example.test",), settle_s=0.2, timeout_s=1)
    with pytest.raises(WebScriptError, match="web_wait_timeout"):
        runner.run(WebScript(actions=(paginated_action(),)), "read")
    assert now < 1.2 and 1 < runner.row_reads < 50 and page.clicks == 0


@pytest.mark.parametrize("failure", ["origin", "max_pages", "keys", "truncated"])
def test_initial_capture_keeps_existing_origin_and_completeness_guards(failure: str) -> None:
    page = ObservationPage()
    runner = ObservedRunner(page, ("https://example.test",), settle_s=0, timeout_s=1)
    code = "web_origin_not_allowed"
    if failure == "origin":
        page.url = "https://denied.test/orders"
    elif failure == "max_pages":
        runner.numbers = (1, 3)
        code = "web_pagination_limit_exceeded"
    elif failure == "keys":
        runner.rows = [{"ID": "same"}, {"ID": "same"}]
        code = "web_pagination_duplicate_keys"
    else:
        runner.truncated = True
        code = "web_table_limit_exceeded"
    with pytest.raises(WebScriptError, match=code):
        runner.run(WebScript(actions=(paginated_action(max_pages=2),)), "read")
    assert page.clicks == 0


def test_consistent_single_page_returns_the_actual_rows() -> None:
    page = ObservationPage()
    runner = ObservedRunner(page, ("https://example.test",), settle_s=0)
    result = runner.run(WebScript(actions=(paginated_action(),)), "read")
    assert result.data["orders"] == [{"ID": "fresh-first-page"}]
    assert page.clicks == 0


def test_missing_table_cannot_reset_the_initial_capture_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 0.0

    class MissingPage(ObservationPage):
        table_reads = 0

        def evaluate(self, expression: str) -> Any:
            nonlocal now
            if expression == "document.location.href":
                return self.url
            self.table_reads += 1
            now += 0.3
            return '{"error": "web_table_missing"}'

    class SlowNumbersRunner(ScriptRunner):
        def _page_numbers(self, paging: WebPagination) -> tuple[int, int]:
            nonlocal now
            now += 0.8
            return 1, 1

    def sleep(seconds: float) -> None:
        nonlocal now
        now += seconds

    monkeypatch.setattr(time, "monotonic", lambda: now)
    monkeypatch.setattr(time, "sleep", sleep)
    page = MissingPage()
    runner = SlowNumbersRunner(page, ("https://example.test",), settle_s=0.2, timeout_s=1)
    with pytest.raises(WebScriptError, match="web_table_missing"):
        runner.run(WebScript(actions=(paginated_action(),)), "read")
    assert page.table_reads == 1 and now < 1.2 and page.clicks == 0
