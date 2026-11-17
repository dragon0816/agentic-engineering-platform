"""The first reading stays; later readings keep their evidence as proposals."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _row, _two_pcs

from aep_bi.cards import extract, importer
from aep_bi.cards.store import BiStore


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("visible", [False, True])
@pytest.mark.parametrize("scenario", ["reading", "evidence", "updated"])
def test_two_pcs_replay_same_card(
    tmp_path: Path, reverse: bool, visible: bool, scenario: str
) -> None:
    from test_bi_vault import _commit, _import, _push, _sync, _tables

    from aep_bi.cards import vault

    drive, vid, dataset, a, b = _two_pcs(tmp_path)
    _import(a, dataset, _row("Fictional", body="Shared"))
    _push(a, vid)
    drive.deliver("a", "b", vid)
    _sync(b, vid)
    card = BiStore(a, dataset).find("Technology", "Fictional")
    assert card is not None
    cid = card["id"]
    value: Any
    for ws, who, date in ((a, "alice", "2026-11-05"), (b, "bob", "2026-11-06")):
        repo = vault.Vault(ws, vid).repo
        if scenario == "reading":
            key, value = (
                f"field:{cid}:summary",
                {
                    "value": who,
                    "source": {"kind": "import", "ref": who, "by": who, "at": date},
                    "history": None,
                },
            )
        elif scenario == "updated":
            key, value = (
                f"field:{cid}:updated",
                {
                    "value": date,
                    "source": {"kind": "import", "ref": who, "by": who, "at": date},
                    "history": None,
                },
            )
        else:
            key, value = (
                f"evidence:{cid}:body",
                [
                    {
                        "source_id": who,
                        "source_name": who,
                        "run_id": who,
                        "locator": {},
                        "excerpt": who,
                        "basis": "fact",
                        "at": date,
                    }
                ],
            )
        repo.stage_many({key: value})
        _commit(ws, vid, who)
    for ws in (b, a) if reverse else (a, b):
        _push(ws, vid)
        if visible:
            drive.deliver("b" if ws == b else "a", "a" if ws == b else "b", vid)
    drive.deliver("a", "b", vid)
    drive.deliver("b", "a", vid)
    _sync(a, vid)
    _sync(b, vid)
    assert _tables(a, dataset) == _tables(b, dataset)

    def contents(ws: Path) -> bytes:
        with sqlite3.connect(BiStore(ws, dataset).path) as db:
            return "\n".join(db.iterdump()).encode("utf-8")

    # SQLite headers count local transactions; the complete SQL content must agree.
    assert contents(a) == contents(b)
    store = BiStore(a, dataset)
    if scenario == "reading":
        first, other = ("bob", "alice") if visible and reverse else ("alice", "bob")
        assert store.fields(cid)["summary"]["value"] == first
        assert any(p["value"] == other for p in store.proposals(cid))
    elif scenario == "updated":
        assert store.fields(cid)["updated"]["value"] == "2026-11-06"
    else:
        assert sorted(e["source_name"] for e in store.evidence(cid)) == ["alice", "bob"]
    assert not vault.Vault(a, vid).repo.conflicts()
    for ws in (a, b):
        target = vault.Vault(ws, vid)
        head = target.repo.head()
        assert head is not None
        assert target.repo.state_at(head) == target.repo.units()
        target.rebuild()
    assert _tables(a, dataset) == _tables(b, dataset)
    assert contents(a) == contents(b)


def test_evidence_context_does_not_resurrect_replaced_value() -> None:
    import copy

    from aep_bi.cards import same_card, vault
    from knowledge.repo.repository import apply_ops, value_hash

    key, field = "evidence:fiction:summary", "field:fiction:summary"
    old = {field: {"value": "Old"}, key: [{"source_id": "old"}]}
    incoming = [
        {"unit": key, "value": [*old[key], {"source_id": "append"}], "base": value_hash(old[key])}
    ]
    annotated = same_card.annotate(old, incoming)
    frozen = copy.deepcopy(annotated)
    replaced = {field: {"value": "New"}, key: [{"source_id": "replacement"}]}
    assert apply_ops(replaced, annotated, kind=vault.BiType())
    assert replaced[key] == [{"source_id": "replacement"}]
    assert annotated == frozen


def test_old_ambiguous_evidence_still_conflicts() -> None:
    from aep_bi.cards import vault
    from knowledge.repo.repository import apply_ops, value_hash

    key = "evidence:fiction:body"
    units = {key: [{"source_id": "first"}]}
    ops = [{"unit": key, "value": [{"source_id": "second"}], "base": value_hash([])}]
    assert apply_ops(units, ops, kind=vault.BiType()) == apply_ops(dict(units), ops)
    assert units[key] == [{"source_id": "first"}]


def test_old_sequential_replacement_replays_without_new_semantics() -> None:
    import copy

    from aep_bi.cards import vault
    from knowledge.repo.repository import apply_ops, value_hash

    key = "field:fiction:summary"
    old = {"value": "Old", "source": {"kind": "import"}, "history": None}
    new = {
        "value": "New",
        "source": {"kind": "import"},
        "history": {"old_evidence": [{"source_id": "old"}]},
    }
    units = {key: old, "evidence:fiction:summary": [{"source_id": "old"}]}
    ops: list[dict[str, Any]] = [
        {"unit": key, "value": new, "base": value_hash(old)},
        {
            "unit": "evidence:fiction:summary",
            "value": [{"source_id": "new"}],
            "base": value_hash(units["evidence:fiction:summary"]),
        },
    ]
    expected = copy.deepcopy(units)
    assert apply_ops(expected, ops) == apply_ops(units, ops, kind=vault.BiType()) == []
    assert units == expected


def test_replay_policy_upgrade_rebuilds_once(tmp_path: Path) -> None:
    import json

    from aep_bi.cards import vault

    _, vid, _, a, _ = _two_pcs(tmp_path)
    repo = vault.Vault(a, vid).repo
    before = repo.units()
    stamp = repo._stamp_path()
    cached = json.loads(stamp.read_text(encoding="utf-8"))
    cached.pop("policy", None)
    stamp.write_text(json.dumps(cached), encoding="utf-8")
    with repo._connect() as db:
        db.execute("PRAGMA user_version = 0")
    assert repo.sync()["rebuilt"]
    assert repo.units() == before
    assert not repo.sync()["rebuilt"]


def test_opening_an_old_materialization_replays_the_old_repository_cache(tmp_path: Path) -> None:
    import json
    from contextlib import closing

    from aep_bi.cards import card_model, vault

    _, vid, dataset, a, _ = _two_pcs(tmp_path)
    store = BiStore(a, dataset)
    repo = vault.Vault(a, vid).repo
    expected = repo.units()
    key = next(k for k in expected if k.startswith("meta:"))
    with closing(repo._connect()) as db:
        db.execute("UPDATE units SET value = ? WHERE key = ?", (json.dumps("stale cache"), key))
        db.execute("PRAGMA user_version = 0")
    with closing(sqlite3.connect(store.path)) as db:
        db.execute(f"PRAGMA user_version = {card_model.MODEL_VERSION - 1}")
    vault.ensure_current(store)
    assert repo.units() == expected


def test_evidence_operation_context_is_validated_and_bi_only() -> None:
    import copy

    from aep_bi.cards import vault
    from knowledge.repo.repository import COMMIT_FORMAT, commit_id, commit_problem

    record: dict[str, Any] = {
        "format": COMMIT_FORMAT,
        "repo": "fiction",
        "author": "alice",
        "seq": 1,
        "clock": 1,
        "purpose": "Fictional evidence",
        "kind": "change",
        "created": "2026-11-06",
        "files": [],
        "ops": [
            {
                "unit": "evidence:fiction:summary",
                "value": [],
                "base": None,
                "bi_evidence": {"before": None, "field": None, "after_field": None},
            }
        ],
    }
    record["id"] = commit_id(record)
    assert (
        commit_problem(record, repo="fiction", author="alice", seq=1, kind=vault.BiType()) is None
    )
    assert commit_problem(record, repo="fiction", author="alice", seq=1, kind=None) is not None
    bad = copy.deepcopy(record)
    bad["ops"][0]["bi_evidence"]["before"] = []
    bad["id"] = commit_id(bad)
    assert (
        commit_problem(bad, repo="fiction", author="alice", seq=1, kind=vault.BiType()) is not None
    )


@pytest.mark.parametrize("field", ["summary", "usage", "scope"])
def test_import_keeps_first_reading(tmp_path: Path, field: str) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    store = BiStore(a, dataset)
    for value in ("First reading", "Other reading"):
        prepared = importer.preview(
            store,
            entity_type="Technology",
            filename="fictional.csv",
            csv_text=f"name,{field}\nFictional,{value}\n",
        )
        importer.apply(store, prepared, None, actor="alice")
    card = store.find("Technology", "Fictional")
    assert card is not None
    assert store.fields(card["id"])[field]["value"] == "First reading"
    assert any(p["value"] == "Other reading" for p in store.proposals(card["id"]))


def test_chunk_reading_keeps_alternative_evidence() -> None:
    def candidate(value: str) -> dict[str, Any]:
        return {
            "fields": [
                {
                    "field": "summary",
                    "value": value,
                    "basis": "inference",
                    "evidence": [{"excerpt": value}],
                }
            ],
            "warnings": [],
            "value_errors": [],
        }

    first = candidate("First")
    extract.merge(first, candidate("Other"))
    field = first["fields"][0]
    assert field["value"] == "First"
    assert field["alternatives"][0]["evidence"] == [{"excerpt": "Other"}]


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    "dates",
    [
        ("2026-11-05", "2026-11-06"),
        ("2026-11-06T10:00:00+08:00", "2026-11-06T03:00:00+00:00"),
    ],
)
def test_same_reference_is_one_row_with_the_later_fallback_time(
    reverse: bool, dates: tuple[str, str]
) -> None:
    from aep_bi.cards import same_card, vault
    from knowledge.repo.repository import apply_ops

    field, key = "field:fiction:summary", "evidence:fiction:summary"
    base = {field: {"value": "Shared"}}
    rows = [
        {
            "reference_id": "same",
            "source_id": "fiction",
            "locator": {"page": 1},
            "run_id": run,
            "reference_at": date,
            "reference_time_basis": "submission_fallback",
        }
        for run, date in zip(("alice", "bob"), dates, strict=True)
    ]
    ops = [same_card.annotate(base, [{"unit": key, "value": [row], "base": None}]) for row in rows]
    units: dict[str, Any] = dict(base)
    for batch in reversed(ops) if reverse else ops:
        assert not apply_ops(units, batch, kind=vault.BiType())
    assert units[key] == [rows[1]]


def test_an_append_does_not_reapply_a_stale_review_of_an_existing_reference() -> None:
    from aep_bi.cards import same_card, vault
    from knowledge.repo.repository import apply_ops, value_hash

    field, key = "field:fiction:summary", "evidence:fiction:summary"
    original = {"reference_id": "first", "stance": "supports"}
    reviewed = {"reference_id": "first", "stance": "refutes"}
    addition = {"reference_id": "second", "stance": "supports"}
    base = {field: {"value": "Shared"}, key: [original]}
    ops = same_card.annotate(
        base, [{"unit": key, "value": [original, addition], "base": value_hash([original])}]
    )
    current = {field: base[field], key: [reviewed]}
    assert not apply_ops(current, ops, kind=vault.BiType())
    assert current[key] == [reviewed, addition]


@pytest.mark.parametrize("reverse", [False, True])
def test_updated_uses_chronological_time_across_offsets(reverse: bool) -> None:
    from aep_bi.cards import vault
    from knowledge.repo.repository import apply_ops

    key = "field:fiction:updated"
    values = ["2026-11-06T10:00:00+08:00", "2026-11-06T03:00:00+00:00"]
    units: dict[str, Any] = {}
    for value in reversed(values) if reverse else values:
        assert not apply_ops(
            units, [{"unit": key, "value": {"value": value}, "base": None}], kind=vault.BiType()
        )
    assert units[key]["value"] == values[1]


@pytest.mark.parametrize("at", ["2026-11-06T02:00:00+00:00", "2026-11-06T03:00:00+00:00"])
def test_card_updated_uses_chronological_time_and_history_format(at: str) -> None:
    from aep_bi.cards.vault import _field_history

    entry = {
        "at": "2026-11-06T10:00:00+08:00",
        "group": "one",
        "ref": "one",
        "author": "alice",
        "changes": [
            {
                "unit": "field:fiction:summary",
                "applied": True,
                "before": None,
                "after": {"value": "Fictional", "history": {"at": at}},
            }
        ],
    }
    _, cards = _field_history([entry])
    assert cards["fiction"]["updated"] == at
