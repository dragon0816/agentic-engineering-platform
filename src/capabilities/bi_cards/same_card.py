"""BI's deterministic unit merge policy, shared by push and every replay."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from knowledge.repo.repository import canonical, value_hash

from .card_model import reference_id

VERSION = 2
READINGS = ("summary", "usage", "scope")


def time_key(value: str) -> tuple[int, datetime]:
    """Compare ISO dates/instants in UTC; legacy undated strings sort before dates."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return 0, datetime.min.replace(tzinfo=UTC)
    return 1, parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _union(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_reference: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = str(
            row.get("reference_id")
            or reference_id(str(row.get("source_id") or ""), row.get("locator") or {})
        )
        previous = by_reference.get(identity)

        def order(item: dict[str, Any]) -> tuple[tuple[int, datetime], str]:
            return time_key(str(item.get("reference_at") or item.get("at") or "")), canonical(item)

        if previous is None or order(row) > order(previous):
            by_reference[identity] = row
    return [by_reference[key] for key in sorted(by_reference)]


def annotate(units: Mapping[str, Any], ops: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    incoming = {str(op["unit"]): op["value"] for op in ops}
    for op in ops:
        item = dict(op)
        key = str(op["unit"])
        if key.startswith("evidence:"):
            field = "field:" + key.removeprefix("evidence:")
            old = units.get(field) or {}
            new = incoming.get(field, old) or {}
            item["bi_evidence"] = {
                "before": units.get(key),
                "field": value_hash(old.get("value")),
                "after_field": value_hash(new.get("value")),
            }
        result.append(item)
    return result


def prepare(units: Mapping[str, Any], ops: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Project immutable operations; never change the commit or guess an old append."""
    output: list[dict[str, Any]] = []
    skipped: set[str] = set()
    incoming = {str(op["unit"]): op["value"] for op in ops}
    fields = {str(o["unit"]): o["value"] for o in ops if str(o["unit"]).startswith("field:")}
    for op in ops:
        key, value = str(op["unit"]), op["value"]
        current = units.get(key)
        if not key.startswith("field:") or not isinstance(value, dict):
            continue
        name = key.split(":", 2)[-1]
        source = value.get("source") or {}
        if (
            name in READINGS
            and isinstance(current, dict)
            and current.get("value") == value.get("value")
            and value_hash(current) != op["base"]
            and source.get("kind") != "human"
        ):
            skipped.add(key)
            continue
        if (
            name in READINGS
            and isinstance(current, dict)
            and current.get("value")
            and value.get("value") is not None
            and current["value"] != value["value"]
            and source.get("kind") != "human"
            and value_hash(current) != op["base"]
        ):
            _, cid, name = key.split(":", 2)
            evidence_key = f"evidence:{cid}:{name}"
            evidence = incoming.get(evidence_key, [])
            proposal = {
                "card": cid,
                "field": name,
                "value": value["value"],
                "kind": source.get("kind", "import"),
                "ref": source.get("ref", ""),
                "at": source.get("at", ""),
                "status": "pending",
                "evidence": evidence,
            }
            identity = hashlib.sha256(canonical(op).encode()).hexdigest()[:12]
            output.append({"unit": f"proposal:{identity}", "value": proposal, "base": None})
            skipped.update((key, evidence_key))
    for op in ops:
        key, value = str(op["unit"]), op["value"]
        if key in skipped:
            continue
        item = dict(op)
        current = units.get(key)
        if key.endswith(":updated") and key.startswith("field:"):
            if isinstance(current, dict) and isinstance(value, dict):
                if isinstance(current.get("value"), str) and isinstance(value.get("value"), str):
                    item["value"] = max(
                        (current, value), key=lambda v: (time_key(v["value"]), canonical(v))
                    )
                    item["base"] = value_hash(current)
        if key.startswith("evidence:") and isinstance(value, list):
            field_key = "field:" + key.removeprefix("evidence:")
            field = units.get(field_key) or {}
            context = op.get("bi_evidence")
            if context is not None:
                before = context["before"] or []
                adds = all(canonical(row) in {canonical(r) for r in value} for row in before)
                same = context["after_field"] == value_hash(field.get("value")) and (
                    context["field"] == context["after_field"]
                    or (fields.get(field_key) or {}).get("value") == field.get("value")
                )
                if adds and context["field"] == context["after_field"] and not same:
                    item["base"] = "bi_field_changed"
                if adds and same and (current is None or isinstance(current, list)):
                    baseline = {canonical(row) for row in before}
                    additions = [row for row in value if canonical(row) not in baseline]
                    item["value"] = _union([*(current or []), *additions])
                    item["base"] = value_hash(current)
            elif ((fields.get(field_key) or {}).get("history") or {}).get(
                "old_evidence"
            ) is not None:
                pass  # Old replacement: keep the existing base check, never union it.
        output.append(item)
    return output
