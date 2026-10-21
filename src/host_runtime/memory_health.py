"""The nightly memory health check on this Host (accumulated memory M5, §8.4).

Runs `memory.health.run_check` for every actor's memory database on the Host
(nightly, with the experience review, and from the memory page's 「立即檢查」
for the signed-in actor), and turns the person's presses on its findings into
the fixes: merge two contacts, 仍在職 / 已離職, stop a preference, keep one.
The check itself never changes the memory. The contradiction question goes
to the internal model the experience review uses (structured, bounded: one
call per scope with at least two preferences, at most `MAX_SCOPES`); with no
internal model it is skipped. Telemetry and the nightly report get counts,
never content.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import Field

import telemetry.recorder as telemetry
from capabilities.business_cards.contracts import PersonRef
from capabilities.business_cards.space import CONTACTS_ORG, PEOPLE
from capabilities.business_cards.store import CardStore, CardStoreError
from common.base import Contract
from common.execution import TraceIdentifiers
from memory.health import (
    KIND_LABELS,
    ContradictionAsker,
    EntitySource,
    HealthError,
    HealthFindings,
    HealthReport,
    last_run,
    load_settings,
    run_check,
    save_settings,
)
from memory.preferences import Preference, PreferenceError
from memory.service import DB_FILE, MEMORY_FOLDER, MemoryService, MemoryServiceError

LOCAL_ZONE = ZoneInfo("Asia/Taipei")
HOST_MANAGER = "host/memory"
OUTPUT_CONTRACT = "memory_health_contradictions"
MAX_PAIRS = 5
PROMPT = (
    "You check one person's saved rules for one assistant Skill. Two rules contradict "
    "when following one means breaking the other. Reply with one JSON object: "
    '{"pairs": [{"a": <rule number>, "b": <rule number>, "why": "<one short sentence '
    'in Traditional Chinese>"}]}. List only real contradictions, at most 5; reply '
    '{"pairs": []} when there are none. Rules about different things never contradict.'
)
#: The actions a finding of each kind offers, the decision each records.
ACTIONS: dict[str, dict[str, str]] = {
    "duplicate": {"merge": "resolved", "dismiss": "dismissed"},
    "stale": {"still_active": "resolved", "left": "resolved"},
    "contradiction": {"remove_a": "resolved", "remove_b": "resolved", "keep_both": "dismissed"},
    "unused": {"remove": "resolved", "keep": "dismissed"},
    "orphan": {"keep": "dismissed"},
    "stale_sync": {"dismiss": "dismissed"},
}
MESSAGES = {
    "finding_unknown": "找不到這個項目",
    "finding_closed": "這個項目已經處理過了",
    "finding_action_unknown": "這個項目沒有這個做法",
    "change_unknown": "找不到這次變更",
    "health_settings_invalid": "設定的值不對：月數 0–120、天數 1–3650",
    "health_off": "健康檢查已關閉（在「紀錄」可以打開）",
    "person_unknown": "找不到這位聯絡人（可能已合併或刪除）",
    "preference_unknown": "這條偏好已經不在使用中",
    "merge_same_person": "不能和自己合併",
}


def _refused(code: str) -> dict[str, Any]:
    return {"ok": False, "code": code, "message": MESSAGES.get(code, code)}


def _local(value: str) -> str:
    if not value:
        return ""
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if moment.tzinfo is None:
        return moment.strftime("%Y-%m-%d")
    return moment.astimezone(LOCAL_ZONE).strftime("%Y-%m-%d %H:%M")


class HealthSummary(Contract):
    """One night's check over every actor: counts only (the nightly report)."""

    at: str
    actors: int = 0
    checked: int = 0
    switched_off: int = 0
    found: dict[str, int] = Field(default_factory=dict)
    opened: int = 0
    open: int = 0
    gone: int = 0
    model_calls: int = 0
    model: dict[str, int] = Field(default_factory=dict)
    failed: int = 0

    def markdown(self) -> str:
        found = ", ".join(f"{kind} {count}" for kind, count in sorted(self.found.items()))
        model = ", ".join(f"{use} {count}" for use, count in sorted(self.model.items()))
        return (
            "## Memory health\n\n"
            f"- Actors: {self.actors} ({self.checked} checked, {self.switched_off} switched off"
            + (f", {self.failed} failed" if self.failed else "")
            + ")\n"
            f"- Found: {found or 'nothing'}\n"
            f"- To decide: {self.open} open ({self.opened} new), {self.gone} no longer found\n"
            f"- Contradiction question: {self.model_calls} model calls"
            + (f" ({model})" if model else "")
            + "\n"
        )


def ask_with(model: Any, alias: str, check_id: str) -> ContradictionAsker:
    """The contradiction question through the internal model: one structured
    call per scope, the rules numbered, only their text sent."""
    from host_runtime.experience_review import structured_call

    counter = [0]

    def ask(scope: str, rules: Sequence[Preference]) -> list[tuple[str, str, str]]:
        counter[0] += 1
        shown = "\n".join(f"{number}. {item.text}" for number, item in enumerate(rules, 1))
        data = structured_call(
            model,
            alias,
            system=PROMPT,
            user=f"Rules of one Skill:\n{shown}",
            trace=TraceIdentifiers(
                trace_id=check_id, request_id=f"{check_id}-{counter[0]}", span_id="memory-health"
            ),
            output_contract=OUTPUT_CONTRACT,
            max_output_tokens=500,
        )
        pairs = data.get("pairs") if isinstance(data, dict) else None
        found: list[tuple[str, str, str]] = []
        for item in pairs if isinstance(pairs, list) else ():
            if not isinstance(item, dict):
                continue
            first, second = item.get("a"), item.get("b")
            if not all(
                isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= len(rules)
                for n in (first, second)
            ):
                continue
            assert isinstance(first, int) and isinstance(second, int)
            found.append(
                (
                    rules[first - 1].preference_id,
                    rules[second - 1].preference_id,
                    str(item.get("why") or "")[:200],
                )
            )
        return found[:MAX_PAIRS]

    return ask


class MemoryHealth:
    """The health check for one Agent Web's Host."""

    def __init__(
        self, web: Any, *, model_source: Callable[[], tuple[Any, str] | None] | None = None
    ) -> None:
        self.web = web
        self.model_source = model_source or self._review_model
        self.last_summary: HealthSummary | None = None

    def _review_model(self) -> tuple[Any, str] | None:
        from host_runtime.experience_review import review_model

        try:
            return review_model(self.web.runtime)
        except AttributeError:
            return None

    @property
    def layout(self) -> Any:
        return self.web.runtime.layout

    def service(self, actor: str) -> MemoryService:
        service: MemoryService = self.web.personal_memory.service(actor)
        return service

    def _manager_state(self) -> Callable[[str], str]:
        from host_runtime.memory_spaces import manager_states

        states = manager_states(self.layout)
        return lambda manager: "host" if manager == HOST_MANAGER else states.get(manager, "missing")

    def _cards(self, actor: str, service: MemoryService) -> CardStore | None:
        """The actor's contacts, only when the store was already opened the
        normal way (its table exists): the check never starts a migration."""
        from host_runtime.memory_spaces import registry

        with service.connect() as con:
            known = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (PEOPLE,)
            ).fetchone()
        if known is None:
            return None
        try:
            return CardStore.for_actor(self.layout.workspace_root, actor, registry(self.layout))
        except CardStoreError:
            return None

    def _last_used(self, actor: str, recorded: Mapping[str, str]) -> dict[str, str]:
        """When an answer last carried each preference: the uses recorded
        since M5, and the `preferences_used` of the actor's stored answers."""
        used = dict(recorded)
        try:
            records = self.web.runtime.state.conversations(actor, limit=200)
        except (AttributeError, ValueError):
            records = []
        for record in records:
            for message in record.messages:
                stamp = message.created_at.astimezone(UTC).isoformat(timespec="seconds")
                for preference_id in getattr(message, "preferences_used", ()) or ():
                    if stamp > used.get(str(preference_id), ""):
                        used[str(preference_id)] = stamp
        return used

    # -- running ---------------------------------------------------------------

    def run(self, actor: str, *, now: datetime | None = None) -> HealthReport:
        """One actor's check (the button, or one actor of the night)."""
        service = self.service(actor)
        settings = load_settings(service)
        prefs = self.web.personal_memory.preferences(actor)
        active = prefs.listed() if settings.enabled else []
        cards = self._cards(actor, service) if settings.enabled else None
        entities: dict[str, EntitySource] = {} if cards is None else {CONTACTS_ORG: cards}
        asker: ContradictionAsker | None = None
        stamp = f"health-{(now or datetime.now(UTC)):%Y%m%dT%H%M%S}"
        if settings.enabled and self._needs_model(active):
            found = self.model_source()
            asker = None if found is None else ask_with(found[0], found[1], stamp)
        report = run_check(
            service,
            preferences=active,
            last_used=self._last_used(actor, prefs.last_used()) if settings.enabled else {},
            entities=entities,
            manager_state=self._manager_state(),
            ask=asker,
            now=now,
            settings=settings,
        )
        self._telemetry(report)
        return report

    @staticmethod
    def _needs_model(preferences: Sequence[Preference]) -> bool:
        scopes: dict[str, int] = {}
        for item in preferences:
            scopes[item.scope] = scopes.get(item.scope, 0) + 1
        return any(count >= 2 for count in scopes.values())

    @staticmethod
    def _telemetry(report: HealthReport) -> None:
        """Counts only, never content."""
        attributes = {
            "enabled": report.enabled,
            "opened": report.opened,
            "open": report.still_open,
            "gone": report.gone,
            "model": report.model,
            "model_calls": report.model_calls,
            **{f"found_{kind}": count for kind, count in sorted(report.found.items())},
        }
        with telemetry.run("memory_health", attributes={"run_label": "memory health check"}):
            telemetry.emit("memory.health_checked", state="checking", attributes=attributes)

    def actors(self) -> list[str]:
        """Whose memory databases this Host has (each one names its actor)."""
        folder = Path(self.layout.workspace_root) / MEMORY_FOLDER
        found: list[str] = []
        for path in sorted(folder.glob(f"*/{DB_FILE}")) if folder.is_dir() else ():
            try:
                with closing(sqlite3.connect(path, timeout=10)) as con:
                    row = con.execute("SELECT value FROM meta WHERE key = 'actor'").fetchone()
            except Exception:  # noqa: BLE001 - an unreadable database is skipped
                continue
            if row is not None and row[0] and row[0] not in found:
                found.append(str(row[0]))
        actor = str(self.web.runtime.actor)
        if actor not in found:
            found.insert(0, actor)
        return found

    def run_all(self, *, now: datetime | None = None) -> HealthSummary:
        """The nightly pass: every actor of this Host, each in their own
        database; a failure of one does not stop the others."""
        counts = {"actors": 0, "checked": 0, "switched_off": 0, "failed": 0}
        totals = {"opened": 0, "open": 0, "gone": 0, "model_calls": 0}
        found: dict[str, int] = {}
        model: dict[str, int] = {}
        for actor in self.actors():
            counts["actors"] += 1
            try:
                report = self.run(actor, now=now)
            except Exception:  # noqa: BLE001 - counted; the next night tries again
                counts["failed"] += 1
                continue
            if not report.enabled:
                counts["switched_off"] += 1
                continue
            counts["checked"] += 1
            for kind, count in report.found.items():
                found[kind] = found.get(kind, 0) + count
            model[report.model] = model.get(report.model, 0) + 1
            totals["opened"] += report.opened
            totals["open"] += report.still_open
            totals["gone"] += report.gone
            totals["model_calls"] += report.model_calls
        summary = HealthSummary(
            at=(now or datetime.now(UTC)).isoformat(timespec="seconds"),
            found=found,
            model=model,
            **counts,
            **totals,
        )
        self.last_summary = summary
        return summary

    # -- the page -----------------------------------------------------------------

    def overview(self, actor: str) -> dict[str, Any]:
        service = self.service(actor)
        settings = load_settings(service)
        rules_months = sorted(
            {
                rule.after
                for summary in service.spaces()
                for rule in summary.rules.freshness
                if rule.kind == "entities"
            }
        )
        run = last_run(service)
        return {
            "settings": settings.as_dict(),
            "rule_periods": rules_months,
            "last_run": None if run is None else {**run, "at_local": _local(str(run.get("at")))},
            "findings": [self._shown(item) for item in HealthFindings(service).listed()],
            "kind_labels": KIND_LABELS,
        }

    def _shown(self, item: Mapping[str, Any]) -> dict[str, Any]:
        """A finding as the page draws it: a title, label/value pairs, the
        actions and the memory-page links."""
        kind = str(item["kind"])
        subject = dict(item["subject"])
        pairs: list[list[str]] = []
        title = ""
        links: list[dict[str, str]] = []
        actions: list[dict[str, str]] = []
        if kind == "duplicate":
            people = subject.get("people") or []
            title = "可能是同一個人：" + "、".join(str(p.get("name")) for p in people)
            reason = {
                "same_email": "Email 相同",
                "same_name_company": "同公司同名，但 Email 或部門不同，所以沒有自動合併",
            }.get(str(subject.get("reason")), str(subject.get("reason")))
            for number, person in enumerate(people, 1):
                pairs.append(
                    [
                        f"第 {number} 筆",
                        " · ".join(
                            str(person.get(key))
                            for key in ("name", "company", "department", "title", "email")
                            if person.get(key)
                        ),
                    ]
                )
                links.append(
                    {"label": f"開啟第 {number} 筆", "person_id": str(person["person_id"])}
                )
            pairs.append(["為什麼", reason])
            actions = [
                {"action": "merge", "label": "合併（保留第 1 筆）", "style": "primary"},
                {"action": "dismiss", "label": "不是同一人", "style": ""},
            ]
        elif kind == "stale":
            title = str(subject.get("question"))
            pairs = [
                ["公司", str(subject.get("company") or "—")],
                ["最後一次出現", str(subject.get("last_seen") or "—")],
                ["期限", _period(str(subject.get("period")))],
            ]
            links.append({"label": "開啟該聯絡人", "person_id": str(subject.get("person_id"))})
            actions = [
                {"action": "still_active", "label": "仍在職", "style": "primary"},
                {"action": "left", "label": "已離職", "style": "danger"},
            ]
        elif kind == "contradiction":
            label = str(subject.get("scope_label") or subject.get("scope"))
            title = f"『{label}』的兩條偏好可能矛盾"
            a, b = subject.get("a") or {}, subject.get("b") or {}
            pairs = [
                ["第 1 條", str(a.get("text"))],
                ["第 2 條", str(b.get("text"))],
                ["為什麼", str(subject.get("why") or "—")],
            ]
            links.append(
                {"label": "到偏好", "tab": "preferences", "id": str(a.get("preference_id"))}
            )
            actions = [
                {"action": "remove_a", "label": "停用第 1 條", "style": ""},
                {"action": "remove_b", "label": "停用第 2 條", "style": ""},
                {"action": "keep_both", "label": "兩條都留", "style": ""},
            ]
        elif kind == "unused":
            title = f"很久沒用的偏好：「{subject.get('text')}」"
            used = str(subject.get("last_used") or "")
            pairs = [
                ["Skill", str(subject.get("scope_label") or subject.get("scope"))],
                ["最後一次用到", _local(used) if used else "存下後沒用過"],
                ["存下", _local(str(subject.get("created_at")))],
            ]
            links.append(
                {"label": "到偏好", "tab": "preferences", "id": str(subject.get("preference_id"))}
            )
            actions = [
                {"action": "remove", "label": "刪除", "style": "danger"},
                {"action": "keep", "label": "保留", "style": ""},
            ]
        elif kind == "orphan":
            title = f"『{subject.get('space')}』沒有管理的 Skill"
            pairs = [["原本的管理者", str(subject.get("manager"))]]
            links.append({"label": "到紀錄匯出或刪除", "tab": "records", "id": str(item["space"])})
            actions = [{"action": "keep", "label": "保留", "style": ""}]
        elif kind == "stale_sync":
            title = f"整理進度停住：{subject.get('key')}"
            pairs = [
                ["來源", str(subject.get("source"))],
                ["最後前進", _local(str(subject.get("updated_at")))],
                ["期限", _period(str(subject.get("period")))],
            ]
            links.append({"label": "到同步進度", "tab": "sync", "id": str(subject.get("key"))})
            actions = [{"action": "dismiss", "label": "知道了", "style": ""}]
        return {
            "finding_id": item["finding_id"],
            "kind": kind,
            "kind_label": KIND_LABELS.get(kind, kind),
            "space": item["space"],
            "title": title,
            "pairs": pairs,
            "links": links,
            "actions": actions,
            "created_at_local": _local(str(item["created_at"])),
        }

    def check_now(self, actor: str) -> dict[str, Any]:
        """「立即檢查」: the signed-in actor's check, now."""
        if not load_settings(self.service(actor)).enabled:
            return _refused("health_off")
        report = self.run(actor)
        opened = report.opened
        skipped = "（矛盾檢查略過：沒有可用的內部模型）" if report.model == "unavailable" else ""
        return {
            "ok": True,
            "counts": report.counts(),
            "message": (f"檢查完成：{opened} 個新項目，" if opened else "檢查完成：沒有新項目，")
            + f"共 {report.still_open} 個待確認。{skipped}",
        }

    def update_settings(self, actor: str, body: Mapping[str, Any]) -> dict[str, Any]:
        wanted = {
            key: body[key] for key in ("enabled", "freshness_months", "unused_days") if key in body
        }
        try:
            saved = save_settings(self.service(actor), wanted)
        except HealthError as error:
            return _refused(error.code)
        return {"ok": True, "settings": saved.as_dict(), "message": "已儲存健康檢查設定。"}

    def decide(self, actor: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """The person's press on a finding: the fix, then the finding closed.
        Fixes go through the stores' own undoable changes."""
        who = f"{actor} via web"
        service = self.service(actor)
        findings = HealthFindings(service)
        finding = findings.get(str(body.get("finding_id") or ""))
        if finding is None:
            return _refused("finding_unknown")
        if finding["state"] != "open":
            return _refused("finding_closed")
        kind, action = str(finding["kind"]), str(body.get("action") or "")
        state = ACTIONS.get(kind, {}).get(action)
        if state is None:
            return _refused("finding_action_unknown")
        subject = finding["subject"]
        reply: dict[str, Any] = {"ok": True, "message": "已處理。"}
        try:
            if kind == "duplicate" and action == "merge":
                people = subject.get("people") or []
                change = self._store(actor).merge_people(
                    str(people[0]["person_id"]),
                    str(people[1]["person_id"]),
                    actor=who,
                    reason="merged on the memory page (health check)",
                )
                reply = {"ok": True, "message": "已合併，可以復原。", "undo": _cards_undo(change)}
            elif kind == "stale" and action == "still_active":
                self._store(actor).confirm_active(
                    PersonRef(person_id=str(subject.get("person_id"))),
                    actor=who,
                    reason="still at work, said on the memory page (health check)",
                )
                reply = {"ok": True, "message": f"已記下：{subject.get('name')} 仍在職。"}
            elif kind == "stale" and action == "left":
                _, _, _, left = self._store(actor).set_status(
                    PersonRef(person_id=str(subject.get("person_id"))),
                    "left",
                    actor=who,
                    reason="left, said on the memory page (health check)",
                    effective=None,
                )
                reply = {
                    "ok": True,
                    "message": f"已記下：{subject.get('name')} 已離職，可以復原。",
                    "undo": _cards_undo(left),
                }
            elif kind in ("contradiction", "unused") and action in (
                "remove_a",
                "remove_b",
                "remove",
            ):
                target = (
                    subject.get("a" if action == "remove_a" else "b", {}).get("preference_id")
                    if kind == "contradiction"
                    else subject.get("preference_id")
                )
                change = self.web.personal_memory.preferences(actor).remove(
                    str(target), actor=who, reason=f"{kind} on the memory page (health check)"
                )
                reply = {
                    "ok": True,
                    "message": "已停用這條偏好，可以復原。",
                    "undo": {"kind": "preference", "change_id": change},
                }
            elif state == "dismissed":
                reply = {"ok": True, "message": "好，保留不動。"}
        except CardStoreError as error:
            return _refused(error.code)
        except PreferenceError as error:
            return _refused(error.code)
        except MemoryServiceError as error:
            return _refused(error.code)
        findings.close(str(finding["finding_id"]), state, action=action, actor=who)
        if isinstance(reply.get("undo"), dict):
            reply["undo"]["finding_id"] = str(finding["finding_id"])
        return reply

    def undo(self, actor: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """復原 under a finding's fix: the store's own undo of that change,
        then the finding open again (its state returns to `open`, #233), so the
        card shows at once instead of after the next check. A store refusal
        (`undo_conflict`, `change_unknown`) propagates and leaves it closed."""
        who = f"{actor} via web"
        findings = HealthFindings(self.service(actor))
        finding = findings.get(str(body.get("finding_id") or ""))
        if finding is None:
            return _refused("finding_unknown")
        kind, change = str(body.get("kind") or ""), str(body.get("change_id") or "")
        if not change:
            return _refused("change_unknown")
        if kind == "preference":
            reverted, _ = self.web.personal_memory.preferences(actor).undo(change, actor=who)
        elif kind == "contacts":
            reverted = len(self._store(actor).undo(change, actor=who)[0])
        else:
            return _refused("change_unknown")
        reopened = findings.reopen(str(finding["finding_id"]))
        return {"ok": True, "reverted": reverted, "reopened": reopened, "message": "已復原。"}

    def _store(self, actor: str) -> CardStore:
        from host_runtime.memory_spaces import registry

        return CardStore.for_actor(self.layout.workspace_root, actor, registry(self.layout))


def _cards_undo(change: str | None) -> dict[str, str] | None:
    return None if not change else {"kind": "contacts", "change_id": change}


def _period(value: str) -> str:
    if not value.startswith("P") or len(value) < 3:
        return value
    number, unit = value[1:-1], value[-1]
    return f"{number} {'個月' if unit == 'M' else '天'}沒有新的證據"
