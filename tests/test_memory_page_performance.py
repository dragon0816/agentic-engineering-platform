"""The memory page's cost (live check B3, 2026-10-21).

On the owner's PC, with 9 people, 13 observations and a few preferences and
notes, `GET /api/memory/overview` took 17-18 s and every action 8-14 s: each
call re-opened the Memory Service, rebuilt the memory registry (parsing
every installed Skill and Workflow manifest) and set up the schema again,
several times per call. These tests count what one overview does, on a
fixture shaped like that installation (about 70 installed manifests, 200
conversations, the same memory sizes; synthetic content), so they do not
depend on the machine's speed; one generous wall-clock budget guards
against a regression the counts would miss.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_business_cards_conversation import Conversation
from test_business_cards_conversation import web as web  # noqa: F401 - the fixture

from agent.skills import SkillManifest
from capabilities.business_cards.contracts import PersonRef
from capabilities.business_cards.space import CONTACTS_ORG
from capabilities.business_cards.store import CardStore
from host_runtime import memory_spaces
from host_runtime.assets import shipped, shipped_off
from host_runtime.conversations import ConversationMessage, ConversationRecord
from host_runtime.web import AgentWeb
from memory import service as memory_service

Web = tuple[AgentWeb, Conversation]
SCOPE = "skill:engineering/business-cards"
COMPANIES = ("範例科技股份有限公司", "示範電子股份有限公司", "測試通訊股份有限公司")
#: Installed manifests on the owner's PC: 14 Skills and 56 Workflows.
SKILLS, WORKFLOWS = 14, 56
CONVERSATIONS = 200


def _install(agent_web: AgentWeb) -> None:
    """About as many installed Skill and Workflow files as the owner has:
    the shipped ones plus synthetic copies under other names."""
    layout = agent_web.runtime.layout
    layout.skills.mkdir(parents=True, exist_ok=True)
    layout.workflows.mkdir(parents=True, exist_ok=True)
    manifests = [*shipped(), *shipped_off()]
    skills = [item for item in manifests if isinstance(item, SkillManifest)]
    workflows = [item for item in manifests if not isinstance(item, SkillManifest)]
    for folder, items, wanted in (
        (layout.skills, skills, SKILLS),
        (layout.workflows, workflows, WORKFLOWS),
    ):
        written = len(list(folder.glob("*__*__*.json")))
        number = 0
        while written < wanted:
            item = items[number % len(items)]
            data = json.loads(item.model_dump_json())
            identity = data["metadata"]["identity"]
            if number >= len(items):
                identity["name"] = f"{identity['name']}-copy{number}"
            path = (
                folder / f"{identity['namespace']}__{identity['name']}__{identity['version']}.json"
            )
            number += 1
            if path.exists():
                continue
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            written += 1


def seed(agent_web: AgentWeb) -> None:
    """The owner's sizes with synthetic content: 9 people (13 sightings, one
    open proposal), a sync state, 3 preferences, 3 notes, 200 conversations."""
    from host_runtime.memory_spaces import registry

    _install(agent_web)
    actor = agent_web.runtime.actor
    layout = agent_web.runtime.layout
    store = CardStore.for_actor(layout.workspace_root, actor, registry(layout))
    people = []
    for number in range(9):
        added = store.add(
            {
                "name": f"測試人{number}",
                "romanised_name": f"Test Person {number}",
                "company": COMPANIES[number % 3],
                "department": "射頻部",
                "title": "經理",
                "email": f"person{number}@example.com",
            },
            source="card",
            source_date=date(2026, 1, 1 + number),
            source_ref="sha256:" + f"{number:02x}" * 32,
            uncertain=(),
            actor="seed",
        )
        people.append(added.person_id)
    store.edit(PersonRef(person_id=people[0]), {}, actor="seed", reason="", confirm=["email"])
    # A second card of the first person reads the confirmed email differently:
    # the one open proposal.
    store.add(
        {
            "name": "測試人0",
            "romanised_name": "Test Person 0",
            "company": COMPANIES[0],
            "department": "射頻部",
            "title": "經理",
            "email": "person0x@example.com",
        },
        source="card",
        source_date=date(2026, 2, 1),
        source_ref="sha256:" + "ff" * 32,
        uncertain=("email",),
        actor="seed",
    )
    for number in range(1, 4):
        store.add(
            {
                "name": f"測試人{number}",
                "company": COMPANIES[number % 3],
                "email": f"person{number}@example.com",
            },
            source="email_signature",
            source_date=date(2026, 3, 1 + number),
            source_ref=f"mail-{number}",
            uncertain=(),
            actor="seed",
        )
    service = agent_web.personal_memory.service(actor)
    service.owned(CONTACTS_ORG).advance_sync(
        "mail:Inbox",
        "example.com",
        last_message_date="2026-10-19T08:00:00+00:00",
        message_ids=["m-1"],
        extractor_version="sig-3",
        actor="seed",
    )
    prefs = agent_web.personal_memory.preferences(actor)
    saved = [
        prefs.save(SCOPE, text, actor="seed", scope_label="名片／組織圖")[0]
        for text in ("組織圖用英文名", "執行時不需要問是否包含在職人員", "部門用全名")
    ]
    notes = agent_web.personal_memory.notes(actor)
    for number in range(3):
        notes.save(
            f"# 筆記 {number}\n\n會議紀錄……" * 5,
            actor="seed",
            source_kind="answer",
            tags=["會議", f"t{number}"],
            entities=[f"{CONTACTS_ORG}:person:{people[number]}"],
        )
    now = datetime.now(UTC) - timedelta(days=30)
    text = "這是一段比較長的回答內容，" * 120
    for number in range(CONVERSATIONS):
        start = now + timedelta(minutes=number)
        agent_web.runtime.state.create_conversation(
            ConversationRecord(
                session_id=f"s-{number}",
                actor=actor,
                title=f"對話 {number}",
                created_at=start,
                updated_at=start + timedelta(seconds=2),
                messages=(
                    ConversationMessage(
                        message_id=f"m-{number}-q",
                        role="user",
                        text="問題",
                        created_at=start,
                        status="submitted",
                    ),
                    ConversationMessage(
                        message_id=f"m-{number}-a",
                        role="assistant",
                        text=text,
                        created_at=start + timedelta(seconds=1),
                        status="answered",
                        preferences_used=(saved[number % 3].preference_id,),
                    ),
                ),
            )
        )


class Counts:
    """How often one call opens a SQLite database, sets up the memory schema
    and reads the installed manifests."""

    def __init__(self) -> None:
        self.opens: dict[str, int] = {}
        self.schema = 0
        self.scans = 0

    def opened(self, path: object) -> None:
        name = Path(str(path)).name
        self.opens[name] = self.opens.get(name, 0) + 1


@contextmanager
def counting(monkeypatch: pytest.MonkeyPatch) -> Iterator[Counts]:
    counts = Counts()
    real_connect = sqlite3.connect
    real_schema = memory_service.MemoryService._setup
    real_installed = memory_spaces._scan

    def connect(database: Any, *args: Any, **kwargs: Any) -> sqlite3.Connection:
        counts.opened(database)
        con: sqlite3.Connection = real_connect(database, *args, **kwargs)
        return con

    def setup(self: memory_service.MemoryService, actor: str) -> None:
        counts.schema += 1
        real_schema(self, actor)

    def installed(*args: Any, **kwargs: Any) -> Any:
        counts.scans += 1
        return real_installed(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", connect)
        patch.setattr(memory_service.MemoryService, "_setup", setup)
        patch.setattr(memory_spaces, "_scan", installed)
        yield counts


def test_one_overview_opens_each_database_once_and_scans_the_manifests_once(
    web: Web,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_web, _ = web
    seed(agent_web)
    first = agent_web.memory_page.get("/api/memory/overview", {})
    assert first["ok"] and len(first["proposals"]) == 1
    with counting(monkeypatch) as counts:
        overview = agent_web.memory_page.get("/api/memory/overview", {})
    assert overview == first
    assert counts.opens.get("memory.sqlite", 0) <= 1, counts.opens
    assert counts.opens.get("state.sqlite", 0) <= 1, counts.opens
    # The legacy cards.db was migrated on the first open; not opened again.
    assert counts.opens.get("cards.db", 0) == 0, counts.opens
    # Nothing on the disk changed since the first call: no manifest is read
    # again and the schema is not set up again.
    assert counts.scans <= 1 and counts.schema == 0, (counts.scans, counts.schema)


def test_a_single_route_opens_the_memory_database_once(
    web: Web,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_web, _ = web
    seed(agent_web)
    full = agent_web.memory_page.get("/api/memory/overview", {})
    for section in ("proposals", "preferences", "notes", "spaces", "sync", "records", "health"):
        with counting(monkeypatch) as counts:
            answer = agent_web.memory_page.get("/api/memory/overview", {"only": section})
        assert answer["ok"] and answer[section] == full[section], section
        assert set(answer) == {"ok", "actor", section}, section
        assert counts.opens.get("memory.sqlite", 0) <= 1, (section, counts.opens)
        assert counts.schema == 0 and counts.scans <= 1, (section, counts.schema, counts.scans)


def test_a_changed_manifest_is_read_again(web: Web) -> None:  # noqa: F811
    """The cache of parsed manifests follows the files: switching a Skill off
    (moving its file) shows at once, without a restart."""
    agent_web, _ = web
    seed(agent_web)
    layout = agent_web.runtime.layout
    before = {item["space"]: item for item in agent_web.memory_page.overview()["spaces"]}
    assert before[CONTACTS_ORG]["manager_state"] == "on"
    (layout.skills / "disabled").mkdir(exist_ok=True)
    source = layout.skills / "engineering__business-cards__1.0.0.json"
    source.replace(layout.skills / "disabled" / source.name)
    after = {item["space"]: item for item in agent_web.memory_page.overview()["spaces"]}
    assert after[CONTACTS_ORG]["manager_state"] == "off"


def test_the_overview_stays_within_a_generous_time_budget(web: Web) -> None:  # noqa: F811
    agent_web, _ = web
    seed(agent_web)
    agent_web.memory_page.get("/api/memory/overview", {})
    started = time.perf_counter()
    for _ in range(3):
        assert agent_web.memory_page.get("/api/memory/overview", {})["ok"]
    assert (time.perf_counter() - started) / 3 < 3.0


def test_a_database_changed_elsewhere_is_set_up_again(web: Web) -> None:  # noqa: F811
    """The setup is skipped only while the file is as this process left it:
    a change from elsewhere (here: an older rules row) is put right on the
    next open, as before."""
    agent_web, _ = web
    seed(agent_web)
    actor = agent_web.runtime.actor
    service = agent_web.personal_memory.service(actor)
    with sqlite3.connect(service.path) as con:
        (wanted,) = con.execute(
            "SELECT rules_json FROM spaces WHERE space = ?", (CONTACTS_ORG,)
        ).fetchone()
        con.execute("UPDATE spaces SET rules_json = '{}' WHERE space = ?", (CONTACTS_ORG,))
    con.close()
    reopened = agent_web.personal_memory.service(actor)
    with sqlite3.connect(reopened.path) as con:
        (now,) = con.execute(
            "SELECT rules_json FROM spaces WHERE space = ?", (CONTACTS_ORG,)
        ).fetchone()
    con.close()
    assert now == wanted
