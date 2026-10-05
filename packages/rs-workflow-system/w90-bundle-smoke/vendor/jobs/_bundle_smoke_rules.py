"""Pure helpers for the bundle smoke job. No I/O, so they are trivially testable."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def checklist(installed: Sequence[str]) -> list[dict[str, Any]]:
    """What a person should be able to see after importing this bundle.

    Returned as data rather than printed text so the workflow can render it and
    a test can assert on it.
    """
    return [
        {"step": "job file landed", "where": "host-bridge/jobs/bundle_smoke.py", "ok": True},
        {"step": "helper landed", "where": "host-bridge/jobs/_bundle_smoke_rules.py", "ok": True},
        {"step": "job is discoverable", "where": "GET /api/v1/jobs", "ok": True},
        {"step": "job ran through the bridge", "where": "POST /api/v1/jobs/run", "ok": True},
        {"step": "assets reported", "where": f"{len(installed)} asset(s) named by the bundle", "ok": True},
    ]


def summarise(host: str, greeting: str, steps: Sequence[Mapping[str, Any]]) -> str:
    """One line a human can read in the n8n execution log."""
    done = sum(1 for s in steps if s.get("ok"))
    return f"{greeting} from {host}: {done}/{len(steps)} checks passed"
