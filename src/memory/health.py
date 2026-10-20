"""The memory health check (accumulated memory M5, docs/phases/ACCUMULATED_MEMORY.md §7–§8).

One actor's memory database, checked for what goes wrong when memory is not
looked after: duplicates (people who look like one person), stale facts
(the space's freshness rules, as data), contradictory preferences the
deterministic M3 check missed (asked of the internal model by the caller,
bounded), preferences not used for a while, orphan spaces and sync states
that stopped moving. Each finding is a row of `health_findings` in the
actor's own database, shown on the memory page's 待確認 for the person to
decide. The check never changes the memory itself: every fix is a person's
press, made by the Host's routes (`host_runtime.memory_health`).

Findings are keyed (`space`, `kind`, `key`) so a second run updates rather
than repeats them: a finding the person dismissed stays dismissed (an unused
preference is asked about again after another `unused_days`), one whose fix
was undone opens again, and an open one no longer found goes (`gone`).
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, Protocol

from common.memory import FreshnessRule
from memory.personal import PREFERENCES_SPACE
from memory.preferences import Preference, polarity, same_subject, subject
from memory.service import MemoryService, MemoryServiceError, now_iso

FindingKind = Literal["duplicate", "stale", "contradiction", "unused", "orphan", "stale_sync"]
KINDS: tuple[FindingKind, ...] = (
    "duplicate",
    "stale",
    "contradiction",
    "unused",
    "orphan",
    "stale_sync",
)
#: What the page calls each kind (a distinct 待確認 type).
KIND_LABELS: dict[str, str] = {
    "duplicate": "可能重複",
    "stale": "很久沒出現",
    "contradiction": "偏好可能矛盾",
    "unused": "很久沒用的偏好",
    "orphan": "無主的資料",
    "stale_sync": "整理進度停住",
}
SETTINGS_KEY = "health_settings"
LAST_RUN_KEY = "health_last_run"
#: Bounds of the one model question per scope (contradictions).
MAX_SCOPES = 5
MAX_RULES_PER_SCOPE = 12
#: The newest findings a page shows.
MAX_FINDINGS = 300

#: Whether the contradiction question was asked: `used`; not needed (fewer
#: than two preferences in every scope), the internal model unavailable, or
#: the check switched off.
ModelUse = Literal["used", "not_needed", "unavailable", "failed", "off"]


class HealthError(MemoryServiceError):
    """A refusal by code (`finding_unknown`, `finding_closed`,
    `health_settings_invalid`)."""


@dataclass(frozen=True)
class HealthSettings:
    """The person's settings (the memory page, 紀錄), kept in their own
    database. `freshness_months` overrides the spaces' entity freshness
    period when set (0 keeps each rule's own)."""

    enabled: bool = True
    freshness_months: int = 0
    unused_days: int = 90

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "freshness_months": self.freshness_months,
            "unused_days": self.unused_days,
        }


def load_settings(service: MemoryService) -> HealthSettings:
    try:
        saved = json.loads(service.get_meta(SETTINGS_KEY) or "{}")
    except ValueError:
        saved = {}
    defaults = HealthSettings()
    if not isinstance(saved, dict):
        saved = {}
    enabled = saved.get("enabled", defaults.enabled)
    months = saved.get("freshness_months", defaults.freshness_months)
    days = saved.get("unused_days", defaults.unused_days)
    return HealthSettings(
        enabled=enabled if isinstance(enabled, bool) else defaults.enabled,
        freshness_months=months if _whole(months, 0, 120) else defaults.freshness_months,
        unused_days=days if _whole(days, 1, 3650) else defaults.unused_days,
    )


def _whole(value: Any, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def save_settings(service: MemoryService, changes: Mapping[str, Any]) -> HealthSettings:
    """Only the keys sent change; other saved keys (a later version's) stay."""
    try:
        saved = json.loads(service.get_meta(SETTINGS_KEY) or "{}")
    except ValueError:
        saved = {}
    if not isinstance(saved, dict):
        saved = {}
    checks = {
        "enabled": lambda value: isinstance(value, bool),
        "freshness_months": lambda value: _whole(value, 0, 120),
        "unused_days": lambda value: _whole(value, 1, 3650),
    }
    for key, value in changes.items():
        check = checks.get(key)
        if check is None or not check(value):
            raise HealthError("health_settings_invalid")
        saved[key] = value
    service.set_meta(SETTINGS_KEY, json.dumps(saved, sort_keys=True))
    return load_settings(service)


# -- periods ------------------------------------------------------------------


def months_before(moment: date, months: int) -> date:
    """The same day `months` calendar months earlier (the month's last day
    when that day does not exist)."""
    year, month = divmod(moment.year * 12 + moment.month - 1 - months, 12)
    month += 1
    for day in range(moment.day, 27, -1):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return date(year, month, min(moment.day, 28))


def cutoff(period: str, today: date) -> date:
    """The day before which something is stale, for `P12M` or `P30D`."""
    number, unit = int(period[1:-1]), period[-1]
    return months_before(today, number) if unit == "M" else today - timedelta(days=number)


def _day(value: str) -> str:
    return (value or "")[:10]


# -- what the check reads -----------------------------------------------------


class EntitySource(Protocol):
    """A space manager's own view, for the checks that need its entities
    (`contacts/org`: the business-cards store)."""

    def last_seen(self, statuses: Sequence[str] = ()) -> list[dict[str, str]]: ...

    def duplicates(self) -> list[dict[str, Any]]: ...


#: (scope, its preferences) -> contradictory pairs (id, id, why), or raises.
ContradictionAsker = Callable[[str, Sequence[Preference]], list[tuple[str, str, str]]]


@dataclass
class Found:
    space: str
    kind: FindingKind
    key: str
    subject: dict[str, Any]


@dataclass
class HealthReport:
    """One run for one actor: counts only leave it (telemetry, the nightly
    report); the findings are in the actor's database."""

    check_id: str
    at: str
    enabled: bool = True
    found: dict[str, int] = field(default_factory=dict)
    opened: int = 0
    still_open: int = 0
    gone: int = 0
    model: ModelUse = "not_needed"
    model_calls: int = 0
    skipped: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "at": self.at,
            "enabled": self.enabled,
            "found": dict(self.found),
            "opened": self.opened,
            "open": self.still_open,
            "gone": self.gone,
            "model": self.model,
            "model_calls": self.model_calls,
            "skipped": list(self.skipped),
        }


# -- the findings table --------------------------------------------------------


def _row(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["subject"] = json.loads(item.pop("subject_json") or "{}")
    return item


class HealthFindings:
    """The `health_findings` rows of one actor's database."""

    def __init__(self, service: MemoryService) -> None:
        self.service = service

    def listed(self, *, state: str | None = "open") -> list[dict[str, Any]]:
        where, args = "", ()  # type: tuple[str, tuple[str, ...]]
        if state is not None:
            where, args = "WHERE state = ?", (state,)
        with self.service.connect() as con:
            rows = con.execute(
                f"SELECT * FROM health_findings {where} ORDER BY created_at, finding_id LIMIT ?",
                (*args, MAX_FINDINGS),
            ).fetchall()
        return [_row(row) for row in rows]

    def get(self, finding_id: str) -> dict[str, Any] | None:
        with self.service.connect() as con:
            row = con.execute(
                "SELECT * FROM health_findings WHERE finding_id = ?", (finding_id,)
            ).fetchone()
        return None if row is None else _row(row)

    def close(
        self, finding_id: str, state: str, *, action: str, actor: str, at: str | None = None
    ) -> None:
        """The person's decision (`resolved` by a fix, `dismissed`)."""
        stamp = at or now_iso()
        with self.service.connect(immediate=True) as con:
            done = con.execute(
                "UPDATE health_findings SET state = ?, action = ?, decided_at = ?, "
                "decided_by = ?, updated_at = ? WHERE finding_id = ? AND state = 'open'",
                (state, action, stamp, actor, stamp, finding_id),
            ).rowcount
        if not done:
            raise HealthError("finding_closed")

    def record(
        self,
        found: Iterable[Found],
        checked: Iterable[str],
        *,
        check_id: str,
        today: date,
        unused_days: int,
    ) -> tuple[int, int, int]:
        """Store one run's findings for the kinds `checked`: new ones open,
        known ones are updated, open ones not found any more go. Returns
        (opened, open now, gone)."""
        stamp = now_iso()
        kinds = set(checked)
        seen: set[str] = set()
        opened = 0
        with self.service.connect(immediate=True) as con:
            for item in found:
                row = con.execute(
                    "SELECT * FROM health_findings WHERE space = ? AND kind = ? AND key = ?",
                    (item.space, item.kind, item.key),
                ).fetchone()
                body = json.dumps(item.subject, ensure_ascii=False, sort_keys=True)
                if row is None:
                    finding_id = f"h-{secrets.token_hex(5)}"
                    con.execute(
                        "INSERT INTO health_findings (finding_id, space, kind, key, subject_json, "
                        "state, check_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            finding_id,
                            item.space,
                            item.kind,
                            item.key,
                            body,
                            "open",
                            check_id,
                            stamp,
                            stamp,
                        ),
                    )
                    opened += 1
                    seen.add(finding_id)
                    continue
                seen.add(str(row["finding_id"]))
                state = str(row["state"])
                again = state in ("gone", "resolved") or (
                    state == "dismissed"
                    and item.kind == "unused"
                    and _day(str(row["decided_at"]))
                    < (today - timedelta(days=unused_days)).isoformat()
                )
                if again:
                    opened += 1
                con.execute(
                    "UPDATE health_findings SET subject_json = ?, check_id = ?, updated_at = ?, "
                    "state = ?, action = CASE WHEN ? THEN '' ELSE action END, "
                    "decided_at = CASE WHEN ? THEN '' ELSE decided_at END, "
                    "decided_by = CASE WHEN ? THEN '' ELSE decided_by END WHERE finding_id = ?",
                    (
                        body,
                        check_id,
                        stamp,
                        "open" if again else state,
                        again,
                        again,
                        again,
                        row["finding_id"],
                    ),
                )
            gone = 0
            for row in con.execute(
                "SELECT finding_id, kind FROM health_findings WHERE state = 'open'"
            ).fetchall():
                if row["kind"] in kinds and row["finding_id"] not in seen:
                    con.execute(
                        "UPDATE health_findings SET state = 'gone', updated_at = ? "
                        "WHERE finding_id = ?",
                        (stamp, row["finding_id"]),
                    )
                    gone += 1
            still = int(
                con.execute("SELECT COUNT(*) FROM health_findings WHERE state = 'open'").fetchone()[
                    0
                ]
            )
        return opened, still, gone


# -- the checks -------------------------------------------------------------------


def _duplicates(space: str, source: EntitySource) -> list[Found]:
    found = []
    for pair in source.duplicates():
        ids = sorted(str(person["person_id"]) for person in pair["people"])
        found.append(Found(space, "duplicate", "|".join(ids), dict(pair)))
    return found


def _stale_entities(
    space: str, rule: FreshnessRule, source: EntitySource, today: date, months: int
) -> list[Found]:
    period = f"P{months}M" if months else rule.after
    limit = cutoff(period, today).isoformat()
    found = []
    for person in source.last_seen(rule.status):
        seen = _day(person["last_seen"])
        if not seen or seen >= limit:
            continue
        found.append(
            Found(
                space,
                "stale",
                f"{person['person_id']}@{seen}",
                {
                    **person,
                    "entity": rule.entity,
                    "question": rule.question.replace("{name}", person["name"] or "這位聯絡人"),
                    "period": period,
                },
            )
        )
    return found


def _stale_sync(
    space: str, rule: FreshnessRule, service: MemoryService, today: date
) -> list[Found]:
    limit = cutoff(rule.after, today).isoformat()
    found = []
    for item in service.sync_overview():
        state = item["state"]
        if item["space"] != space or state is None:
            continue
        moved = _day(state.updated_at)
        if moved >= limit:
            continue
        found.append(
            Found(
                space,
                "stale_sync",
                f"{item['source']}|{item['key']}@{moved}",
                {
                    "source": item["source"],
                    "key": item["key"],
                    "updated_at": state.updated_at,
                    "last_message_date": state.last_message_date,
                    "period": rule.after,
                },
            )
        )
    return found


def _unused(
    preferences: Sequence[Preference], last_used: Mapping[str, str], today: date, days: int
) -> list[Found]:
    limit = (today - timedelta(days=days)).isoformat()
    found = []
    for item in preferences:
        used = last_used.get(item.preference_id, "")
        latest = max(_day(used), _day(item.created_at), _day(item.updated_at))
        if latest >= limit:
            continue
        found.append(
            Found(
                PREFERENCES_SPACE,
                "unused",
                item.preference_id,
                {
                    "preference_id": item.preference_id,
                    "text": item.text,
                    "scope": item.scope,
                    "scope_label": item.scope_label,
                    "last_used": used,
                    "created_at": item.created_at,
                    "days": days,
                },
            )
        )
    return found


def known_conflict(left: Preference, right: Preference) -> bool:
    """What the deterministic M3 check already finds (the same subject, the
    opposite polarity): kept on purpose when both are active."""
    return same_subject(subject(left.text), subject(right.text)) and polarity(
        left.text
    ) != polarity(right.text)


def _contradictions(
    preferences: Sequence[Preference], ask: ContradictionAsker | None, report: HealthReport
) -> list[Found] | None:
    """One bounded question per scope with at least two preferences; None
    when the question could not be asked (nothing to update then)."""
    scopes: dict[str, list[Preference]] = {}
    for item in preferences:
        scopes.setdefault(item.scope, []).append(item)
    asked = [(scope, items) for scope, items in sorted(scopes.items()) if len(items) >= 2]
    if not asked:
        report.model = "not_needed"
        return []
    if ask is None:
        report.model = "unavailable"
        report.skipped.append("contradiction")
        return None
    found: list[Found] = []
    for scope, items in asked[:MAX_SCOPES]:
        shown = list(items[:MAX_RULES_PER_SCOPE])
        by_id = {item.preference_id: item for item in shown}
        report.model_calls += 1
        try:
            pairs = ask(scope, shown)
        except Exception:  # noqa: BLE001 - a failed question leaves the findings as they were
            report.model = "failed"
            report.skipped.append("contradiction")
            return None
        for first, second, why in pairs:
            left, right = by_id.get(first), by_id.get(second)
            if left is None or right is None or left is right or known_conflict(left, right):
                continue
            a, b = sorted((left, right), key=lambda item: item.preference_id)
            found.append(
                Found(
                    PREFERENCES_SPACE,
                    "contradiction",
                    f"{a.preference_id}|{b.preference_id}",
                    {
                        "scope": scope,
                        "scope_label": a.scope_label or b.scope_label,
                        "a": {"preference_id": a.preference_id, "text": a.text},
                        "b": {"preference_id": b.preference_id, "text": b.text},
                        "why": why[:200],
                    },
                )
            )
    report.model = "used"
    return found


def run_check(
    service: MemoryService,
    *,
    preferences: Sequence[Preference],
    last_used: Mapping[str, str] | None,
    entities: Mapping[str, EntitySource],
    manager_state: Callable[[str], str],
    ask: ContradictionAsker | None,
    now: datetime | None = None,
    settings: HealthSettings | None = None,
) -> HealthReport:
    """One run of the health check over one actor's database. Reads only;
    the findings table is its sole output. `preferences` are the active
    ones; `last_used` maps a preference id to when an answer last carried it
    (None: unknown, so no unused check); `entities` are the managers' views
    by space; `manager_state(manager)` says `host`, `on`, `off` or `missing`
    (an orphan); `ask` is the bounded contradiction question (None when the
    internal model is unavailable)."""
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    today = moment.date()
    chosen = settings or load_settings(service)
    report = HealthReport(
        check_id=f"health-{moment:%Y%m%dT%H%M%S}-{secrets.token_hex(2)}",
        at=moment.isoformat(timespec="seconds"),
        enabled=chosen.enabled,
    )
    if not chosen.enabled:
        report.model = "off"
        return report
    found: list[Found] = []
    checked: set[str] = {"orphan", "unused" if last_used is not None else "", "stale_sync"}
    for summary in service.spaces():
        space = summary.space
        if manager_state(summary.manager) == "missing":
            found.append(
                Found(space, "orphan", space, {"space": space, "manager": summary.manager})
            )
        source = entities.get(space)
        if source is not None:
            checked.add("duplicate")
            found.extend(_duplicates(space, source))
        for rule in summary.rules.freshness:
            if rule.kind == "sync_state":
                found.extend(_stale_sync(space, rule, service, today))
            elif source is not None:
                checked.add("stale")
                found.extend(_stale_entities(space, rule, source, today, chosen.freshness_months))
    if last_used is not None:
        found.extend(_unused(preferences, last_used, today, chosen.unused_days))
    else:
        report.skipped.append("unused")
    contradictions = _contradictions(preferences, ask, report)
    if contradictions is not None:
        checked.add("contradiction")
        found.extend(contradictions)
    for item in found:
        report.found[item.kind] = report.found.get(item.kind, 0) + 1
    report.opened, report.still_open, report.gone = HealthFindings(service).record(
        found,
        checked - {""},
        check_id=report.check_id,
        today=today,
        unused_days=chosen.unused_days,
    )
    service.set_meta(LAST_RUN_KEY, json.dumps(report.counts(), sort_keys=True))
    return report


def last_run(service: MemoryService) -> dict[str, Any] | None:
    try:
        found = json.loads(service.get_meta(LAST_RUN_KEY) or "null")
    except ValueError:
        return None
    return found if isinstance(found, dict) else None
