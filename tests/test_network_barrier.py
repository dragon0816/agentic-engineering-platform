"""A fresh scoped request must finish; old/background traffic is not freshness."""

import json
from typing import Any

import pytest

from integrations.network_barrier import NetworkBarrier, sanitize_network_event

ORIGIN = "https://example.test"
FRAME = "main-frame"


def start(barrier: NetworkBarrier, ident: str, stamp: float, now: float, **fields: Any) -> None:
    barrier.event(
        "Network.requestWillBeSent",
        {
            "requestId": ident,
            "frameId": FRAME,
            "type": "XHR",
            "timestamp": stamp,
            "origin": ORIGIN,
            **fields,
        },
        now,
    )


def finish(barrier: NetworkBarrier, ident: str, now: float, status: int = 200) -> None:
    barrier.event(
        "Network.responseReceived",
        {
            "requestId": ident,
            "timestamp": 100 + now,
            "status": status,
        },
        now,
    )
    barrier.event(
        "Network.loadingFinished",
        {
            "requestId": ident,
            "timestamp": 100 + now + 0.01,
        },
        now + 0.01,
    )


def armed() -> NetworkBarrier:
    tracker = NetworkBarrier((ORIGIN,))
    tracker.arm(FRAME, ORIGIN, 100.0, 0.0)
    return tracker


def test_requires_actual_fresh_success_then_quiet() -> None:
    tracker = armed()
    assert not tracker.ready(10.0, 0.2)
    start(tracker, "fresh", 100.1, 0.1)
    assert not tracker.ready(10.0, 0.2)
    finish(tracker, "fresh", 0.2)
    assert not tracker.ready(0.3, 0.2)
    assert tracker.ready(0.5, 0.2)
    assert tracker.evidence()["fresh_finished"] == 1


def test_prearm_observation_cannot_be_promoted_by_late_delivery() -> None:
    tracker = armed()
    start(tracker, "delayed", 100.1, -0.1)
    finish(tracker, "delayed", 0.2)
    assert not tracker.ready(1.0, 0.2)
    assert tracker.evidence()["fresh_finished"] == 0


def test_not_modified_is_transport_success_without_business_data_claim() -> None:
    tracker = armed()
    start(tracker, "fresh", 100.1, 0.1)
    finish(tracker, "fresh", 0.2, 304)
    assert tracker.ready(1.0, 0.2)


def test_arm_preserves_old_pending_until_it_finishes_without_making_it_fresh() -> None:
    tracker = NetworkBarrier((ORIGIN,))
    start(tracker, "old", 99.0, -0.1)
    tracker.arm(FRAME, ORIGIN, 100.0, 0.0)
    start(tracker, "fresh", 100.1, 0.1)
    finish(tracker, "fresh", 0.2)
    assert not tracker.ready(1.0, 0.2)
    finish(tracker, "old", 1.0)
    assert not tracker.ready(1.1, 0.2)
    assert tracker.ready(1.3, 0.2)
    assert tracker.evidence()["fresh_finished"] == 1


@pytest.mark.parametrize("failure", ["request", "http"])
@pytest.mark.parametrize("timing", ["before_arm", "after_arm", "late_old"])
def test_old_failure_terminates_pending_without_poisoning_new_success(
    failure: str, timing: str
) -> None:
    tracker = NetworkBarrier((ORIGIN,))
    if timing != "late_old":
        start(tracker, "old", 99.0, -0.3)
    if timing == "before_arm":
        if failure == "request":
            tracker.event("Network.loadingFailed", {"requestId": "old", "timestamp": 99.1}, -0.2)
        else:
            tracker.event(
                "Network.responseReceived",
                {"requestId": "old", "timestamp": 99.1, "status": 503},
                -0.2,
            )
            tracker.event("Network.loadingFinished", {"requestId": "old", "timestamp": 99.2}, -0.1)
    tracker.arm(FRAME, ORIGIN, 100.0, 0.0)
    if timing == "late_old":
        start(tracker, "old", 99.0, 0.05)
    start(tracker, "fresh", 100.1, 0.1)
    finish(tracker, "fresh", 0.2)
    if timing != "before_arm":
        if failure == "request":
            tracker.event("Network.loadingFailed", {"requestId": "old", "timestamp": 100.3}, 0.3)
        else:
            finish(tracker, "old", 0.3, 503)
        assert not tracker.ready(0.4, 0.2)
    assert tracker.ready(1.0, 0.2)
    assert tracker.evidence()["fresh_finished"] == 1
    assert tracker.evidence()["failed_reason"] == ""


def test_old_cancellation_alone_cannot_certify_freshness() -> None:
    tracker = NetworkBarrier((ORIGIN,))
    start(tracker, "old", 99.0, -0.1)
    tracker.arm(FRAME, ORIGIN, 100.0, 0.0)
    tracker.event("Network.loadingFailed", {"requestId": "old", "timestamp": 100.2}, 0.2)
    assert not tracker.ready(1.0, 0.2)
    assert tracker.evidence()["fresh_finished"] == 0


@pytest.mark.parametrize("kind", ["pre_arm", "late_old", "old_redirect"])
def test_old_requests_never_supply_freshness(kind: str) -> None:
    tracker = NetworkBarrier((ORIGIN,))
    if kind != "late_old":
        start(tracker, "old", 100.05 if kind == "pre_arm" else 99.0, -0.1)
    tracker.arm(FRAME, ORIGIN, 100.0, 0.0)
    if kind == "late_old":
        start(tracker, "old", 99.0, 0.1)
    elif kind == "old_redirect":
        start(tracker, "old", 100.1, 0.1, redirectOrigin=ORIGIN, redirectStatus=302)
    finish(tracker, "old", 0.2)
    assert not tracker.ready(1.0, 0.2)
    assert tracker.evidence()["fresh_finished"] == 0


@pytest.mark.parametrize("fields", [{"frameId": "iframe"}, {"origin": "https://other.test"}])
def test_background_scope_never_satisfies_freshness(fields: dict[str, Any]) -> None:
    tracker = armed()
    start(tracker, "background", 100.1, 0.1, **fields)
    finish(tracker, "background", 0.2)
    assert not tracker.ready(1.0, 0.2)
    start(tracker, "fresh", 100.3, 0.3)
    finish(tracker, "fresh", 0.4)
    assert tracker.ready(1.0, 0.2)


def test_new_unallowed_origin_is_not_retained_before_arm() -> None:
    tracker = NetworkBarrier((ORIGIN,))
    start(tracker, "unrelated", 99.0, -0.1, origin="https://unapproved.private")
    assert tracker.evidence()["observed"] == 0
    assert "unapproved.private" not in repr(tracker.__dict__)
    tracker.arm(FRAME, ORIGIN, 100.0, 0.0)
    finish(tracker, "unrelated", 0.2)
    assert not tracker.ready(1.0, 0.2)


def test_wildcard_policy_still_allows_origin_to_be_observed() -> None:
    tracker = NetworkBarrier(("*",))
    tracker.arm(FRAME, "https://another.test", 100.0, 0.0)
    start(tracker, "fresh", 100.1, 0.1, origin="https://another.test")
    finish(tracker, "fresh", 0.2)
    assert tracker.ready(1.0, 0.2)


@pytest.mark.parametrize("status", [400, 401, 500, 503])
def test_http_errors_refuse_even_when_loading_finished(status: int) -> None:
    tracker = armed()
    start(tracker, "fresh", 100.1, 0.1)
    finish(tracker, "fresh", 0.2, status)
    assert not tracker.ready(1.0, 0.2)
    assert tracker.evidence()["failed_reason"] == "http_error"


@pytest.mark.parametrize("stamp", [99.0, 100.1], ids=["old", "fresh"])
def test_scoped_redirect_outside_origin_refuses(stamp: float) -> None:
    tracker = armed()
    start(tracker, "fresh", stamp, 0.1)
    start(
        tracker,
        "fresh",
        100.2,
        0.2,
        origin="https://other.test",
        redirectOrigin=ORIGIN,
        redirectStatus=302,
    )
    finish(tracker, "fresh", 0.3)
    assert not tracker.ready(1.0, 0.2)
    assert tracker.evidence()["failed_reason"] == "redirect_out_of_scope"


def test_malformed_old_metadata_stays_fatal_despite_later_fresh_success() -> None:
    tracker = NetworkBarrier((ORIGIN,))
    start(tracker, "old", 99.0, -0.1)
    tracker.arm(FRAME, ORIGIN, 100.0, 0.0)
    start(tracker, "fresh", 100.1, 0.1)
    finish(tracker, "fresh", 0.2)
    safe = sanitize_network_event(
        "Network.responseReceived",
        {
            "requestId": "old",
            "type": "XHR",
            "timestamp": 100.3,
            "response": {"status": "unknown"},
        },
    )
    assert safe is not None
    tracker.event("Network.responseReceived", safe, 0.3)
    assert not tracker.ready(1.0, 0.2)
    assert tracker.evidence()["failed_reason"] == "metadata_invalid"


@pytest.mark.parametrize("failure", ["request", "lost", "overflow", "malformed"])
def test_needed_failure_is_latched(failure: str) -> None:
    tracker = NetworkBarrier((ORIGIN,), max_pending=1)
    tracker.arm(FRAME, ORIGIN, 100.0, 0.0)
    start(tracker, "fresh", 100.1, 0.1)
    if failure == "request":
        tracker.event("Network.loadingFailed", {"requestId": "fresh", "timestamp": 100.2}, 0.2)
    elif failure == "lost":
        tracker.mark_lost()
    elif failure == "overflow":
        start(tracker, "another", 100.2, 0.2)
    else:
        tracker.event("Network.responseReceived", {"malformed": True}, 0.2)
    finish(tracker, "fresh", 0.3)
    assert not tracker.ready(1.0, 0.2)
    assert tracker.evidence()["failed_reason"]


def test_terminal_bookkeeping_is_bounded_too() -> None:
    tracker = NetworkBarrier((ORIGIN,), max_pending=2)
    tracker.arm(FRAME, ORIGIN, 100.0, 0.0)
    for number in range(3):
        start(tracker, str(number), 100.0 + number, float(number))
        finish(tracker, str(number), float(number) + 0.1)
    assert not tracker.ready(10.0, 0.2)
    assert tracker.evidence()["failed_reason"] == "overflow"


def test_unseen_asset_terminals_cannot_fill_bookkeeping_or_supply_freshness() -> None:
    tracker = armed()
    for number in range(300):
        tracker.event(
            "Network.loadingFinished",
            {
                "requestId": f"asset-{number}",
                "timestamp": 100.1,
            },
            0.1,
        )
    assert not tracker.ready(1.0, 0.2)
    start(tracker, "fresh", 100.2, 0.2)
    finish(tracker, "fresh", 0.3)
    assert tracker.ready(1.0, 0.2)


def test_large_raw_headers_and_query_are_discarded_before_size_limits() -> None:
    raw = {
        "requestId": "fresh",
        "frameId": FRAME,
        "type": "Fetch",
        "timestamp": 100.1,
        "request": {
            "url": ORIGIN + "/orders?token=SECRET-QUERY" + "q" * 10000,
            "headers": {"Authorization": "SECRET-HEADER" * 10000},
        },
    }
    safe = sanitize_network_event("Network.requestWillBeSent", raw)
    assert safe == {
        "requestId": "fresh",
        "frameId": FRAME,
        "type": "Fetch",
        "timestamp": 100.1,
        "origin": ORIGIN,
    }
    tracker = armed()
    assert safe is not None
    tracker.event("Network.requestWillBeSent", safe, 0.1)
    finish(tracker, "fresh", 0.2)
    assert tracker.ready(1.0, 0.2)
    assert "SECRET" not in json.dumps(safe) + json.dumps(tracker.evidence())


def test_large_response_headers_do_not_hide_required_http_error_status() -> None:
    safe = sanitize_network_event(
        "Network.responseReceived",
        {
            "requestId": "fresh",
            "type": "XHR",
            "timestamp": 100.2,
            "response": {
                "status": 503,
                "headers": {"secret": "PRIVATE" * 10000},
                "url": ORIGIN + "/?secret=PRIVATE",
            },
        },
    )
    assert safe == {"requestId": "fresh", "timestamp": 100.2, "status": 503}
    tracker = armed()
    start(tracker, "fresh", 100.1, 0.1)
    assert safe is not None
    tracker.event("Network.responseReceived", safe, 0.2)
    assert tracker.evidence()["failed_reason"] == "http_error"
    assert "PRIVATE" not in repr(tracker.__dict__)


def test_redirect_sanitization_keeps_only_bounded_origin_and_status() -> None:
    safe = sanitize_network_event(
        "Network.requestWillBeSent",
        {
            "requestId": "fresh",
            "frameId": FRAME,
            "type": "XHR",
            "timestamp": 100.2,
            "request": {"url": ORIGIN + "/next?secret=PRIVATE"},
            "redirectResponse": {
                "status": 302,
                "url": ORIGIN + "/old?secret=PRIVATE",
                "headers": {"secret": "PRIVATE" * 10000},
            },
        },
    )
    assert safe == {
        "requestId": "fresh",
        "timestamp": 100.2,
        "frameId": FRAME,
        "type": "XHR",
        "origin": ORIGIN,
        "redirectOrigin": ORIGIN,
        "redirectStatus": 302,
    }
    tracker = armed()
    start(tracker, "fresh", 100.1, 0.1)
    assert safe is not None
    tracker.event("Network.requestWillBeSent", safe, 0.2)
    finish(tracker, "fresh", 0.3)
    assert tracker.ready(1.0, 0.2)
    assert "PRIVATE" not in repr(tracker.__dict__)


def test_missing_frame_redirect_cannot_hide_a_tracked_scope_change() -> None:
    tracker = armed()
    start(tracker, "fresh", 100.1, 0.1)
    safe = sanitize_network_event(
        "Network.requestWillBeSent",
        {
            "requestId": "fresh",
            "type": "XHR",
            "timestamp": 100.2,
            "request": {"url": "https://other.test/orders"},
            "redirectResponse": {"status": 302, "url": ORIGIN + "/orders"},
        },
    )
    if safe is not None:
        tracker.event("Network.requestWillBeSent", safe, 0.2)
    finish(tracker, "fresh", 0.3)
    assert not tracker.ready(1.0, 0.2)


def test_worker_and_unrelated_type_are_dropped_without_raw_retention() -> None:
    assert (
        sanitize_network_event(
            "Network.requestWillBeSent",
            {
                "requestId": "worker",
                "type": "Fetch",
                "timestamp": 100.1,
                "request": {"url": ORIGIN + "/?secret=PRIVATE"},
            },
        )
        is None
    )
    assert (
        sanitize_network_event(
            "Network.responseReceived",
            {
                "requestId": "image",
                "type": "Image",
                "timestamp": 100.1,
                "response": {"status": 404},
            },
        )
        is None
    )


def test_loss_before_arm_and_reused_completed_id_never_recover() -> None:
    tracker = NetworkBarrier((ORIGIN,))
    tracker.mark_lost()
    tracker.arm(FRAME, ORIGIN, 100.0, 0.0)
    start(tracker, "fresh", 100.1, 0.1)
    finish(tracker, "fresh", 0.2)
    assert not tracker.ready(1.0, 0.2)
    tracker = armed()
    start(tracker, "same", 100.1, 0.1)
    finish(tracker, "same", 0.2)
    start(tracker, "same", 100.3, 0.3)
    assert not tracker.ready(1.0, 0.2)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "100"])
def test_malformed_needed_timestamp_refuses(bad: Any) -> None:
    safe = sanitize_network_event(
        "Network.requestWillBeSent",
        {
            "requestId": "fresh",
            "frameId": FRAME,
            "type": "XHR",
            "timestamp": bad,
            "request": {"url": ORIGIN + "/orders"},
        },
    )
    assert safe == {"malformed": True}


def test_only_bounded_needed_metadata_is_retained() -> None:
    assert sanitize_network_event("Network.dataReceived", {"data": "SECRET"}) is None
    assert (
        sanitize_network_event(
            "Network.requestWillBeSent",
            {
                "type": "Image",
                "request": {"url": "SECRET"},
            },
        )
        is None
    )
    assert sanitize_network_event(
        "Network.requestWillBeSent",
        {
            "type": "XHR",
            "timestamp": 100.0,
            "requestId": "x" * 10000,
            "frameId": FRAME,
            "request": {"url": ORIGIN},
        },
    ) == {"malformed": True}
    tracker = armed()
    start(tracker, "SECRET-ID", 100.1, 0.1)
    assert "SECRET-ID" not in json.dumps(tracker.evidence())


@pytest.mark.parametrize("origin", ["https://forbidden.test", "file://local", "not-origin"])
def test_arm_outside_allowed_http_origin_fails_closed(origin: str) -> None:
    tracker = NetworkBarrier((ORIGIN,))
    tracker.arm(FRAME, origin, 100.0, 0.0)
    assert not tracker.ready(1.0, 0.2)
    assert tracker.evidence()["failed_reason"]
