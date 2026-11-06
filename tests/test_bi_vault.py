"""BI vaults on knowledge repositories (R2; `docs/phases/KNOWLEDGE_REPO.md`).

Every PC is its own temporary workspace with its own copy of the vault folder;
`_Drive.deliver` plays OneDrive, copying the files a PC has not got yet, so a
test decides exactly what each PC has seen when it pushes. The cards of two
PCs with the same commits must be identical, table by table. All data is
fictional.
"""

from __future__ import annotations

import copy
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from capabilities.bi_cards import catalog, source_markdown, vault
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore, PlannedRow, datasets
from host_runtime.bi_cards_api import route

EXAMPLE = "example/product-spec@1.0.0"


class _Drive:
    """Per-PC copies of one shared vault folder and a manual OneDrive."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def workspace(self, pc: str) -> Path:
        path = self.root / pc / "workspace"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def parent(self, pc: str) -> Path:
        path = self.root / pc / "OneDrive - Fictional Co"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def clone(self, source_pc: str, pc: str, vault_id: str) -> Path:
        """A new PC receives the whole folder."""
        target = self.parent(pc) / vault_id
        shutil.copytree(self.parent(source_pc) / vault_id, target)
        return target

    def deliver(self, source_pc: str, pc: str, vault_id: str) -> None:
        """Copy every file `pc` has not got yet (files are never changed)."""
        source = self.parent(source_pc) / vault_id
        target = self.parent(pc) / vault_id
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if path.is_file() and relative.name != "REPO.md" and not (target / relative).exists():
                (target / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target / relative)


def _call(
    ws: Path, method: str, path: str, body: Any = None, actor: str = "tester", **q: str
) -> Any:
    return route(ws, actor, method, path, q, body)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _refused(answer: Any, status: int, code: str) -> dict[str, Any]:
    assert (answer[0], answer[1].get("code")) == (status, code), answer
    return dict(answer[1])


def _tables(ws: Path, dataset: str) -> dict[str, list[tuple[Any, ...]]]:
    """Every card table of a PC, to compare PCs exactly."""
    path = BiStore(ws, dataset).path
    with sqlite3.connect(path) as db:
        return {
            table: sorted(tuple(r) for r in db.execute(f"SELECT * FROM {table}"))
            for table in (
                "cards",
                "fields",
                "history",
                "proposals",
                "evidence",
                "imports",
                "meta",
                "vault_keys",
            )
        }


def _row(key: str, **values: Any) -> PlannedRow:
    return PlannedRow(
        row=1,
        entity_type="Technology",
        canonical_key=key,
        name=key,
        values={"name": key, **values},
        synthetic=False,
    )


def _two_pcs(tmp_path: Path) -> tuple[_Drive, str, str, Path, Path]:
    """PC a creates a vault (author alice); PC b joins it (author bob)."""
    drive = _Drive(tmp_path)
    a, b = drive.workspace("a"), drive.workspace("b")
    made = _ok(
        _call(
            a,
            "POST",
            "/api/bi/vaults",
            {
                "path": str(drive.parent("a")),
                "title": "Market Signals",
                "purpose": "虛構測試：市場訊號與產品對應",
                "schema": "bi.schema/v1.1",
                "author": "alice",
                "default_pack": False,  # these tests are about the vault, not its analyses
            },
        )
    )
    vault_id = made["vault"]["id"]
    folder = drive.clone("a", "b", vault_id)
    _ok(_call(b, "POST", "/api/bi/vaults/join", {"path": str(folder), "author": "bob"}))
    return drive, vault_id, vault.dataset_name(vault_id), a, b


def _sync(ws: Path, vault_id: str) -> dict[str, Any]:
    return dict(_ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/sync", {}))["sync"])


def _status(ws: Path, vault_id: str) -> dict[str, Any]:
    return _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/status"))


def _use_homes(ws: Path, vault_id: str, *names: str) -> None:
    """Domains a test works in, taken up from the vault's default list and pushed: only the
    homes something is in are listed (acceptance F22)."""
    for name in names:
        _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/homes", {"name": name}))
    _commit(ws, vault_id, "領域")
    _push(ws, vault_id)


def _commit(ws: Path, vault_id: str, purpose: str) -> dict[str, Any]:
    return _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/commit", {"purpose": purpose}))


def _push(ws: Path, vault_id: str) -> dict[str, Any]:
    return _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/push", {}))


def _card(ws: Path, dataset: str, key: str, entity_type: str = "Technology") -> dict[str, Any]:
    store = BiStore(ws, dataset)
    found = store.find(entity_type, key)
    assert found is not None
    return {"id": found["id"], "version": found["version"], "fields": store.fields(found["id"])}


def _edit(ws: Path, dataset: str, key: str, field: str, value: Any, actor: str) -> Any:
    """A person's value staged in the working copy, for testing commit, push and
    conflict. Set-up only: a person changes a value with a correction note."""
    card = _card(ws, dataset, key)
    version = BiStore(ws, dataset).set_field(
        card["id"], field, value, base_version=card["version"], actor=f"{actor} via web"
    )
    return 200, {"ok": True, "version": version}


def _note(ws: Path, dataset: str, key: str, field: str, value: Any, actor: str) -> dict[str, Any]:
    """A correction note, previewed and confirmed; a vault commits it at once."""
    card = _card(ws, dataset, key)
    note = _ok(
        _call(
            ws,
            "POST",
            "/api/bi/corrections/preview",
            {
                "dataset": dataset,
                "card": card["id"],
                "field": field,
                "value": value,
                "base_version": card["version"],
                "reason": f"{actor} 的更正",
            },
            actor=actor,
        )
    )
    return _ok(
        _call(
            ws,
            "POST",
            "/api/bi/corrections/apply",
            {"dataset": dataset, "text": note["text"], "base_version": note["base_version"]},
            actor=actor,
        )
    )


def _commits(drive: _Drive, pc: str, vault_id: str) -> list[str]:
    root = drive.parent(pc) / vault_id / "commits"
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*.json"))


def _import(ws: Path, dataset: str, *rows: PlannedRow, filename: str = "t.csv") -> None:
    BiStore(ws, dataset).apply(
        list(rows), filename=filename, entity_type="Technology", actor="x via web"
    )


def test_create_lays_out_the_folder_and_join_checks_it(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    folder = drive.parent("a") / vault_id
    document = json.loads((folder / "repo.json").read_text(encoding="utf-8"))
    assert (document["format"], document["id"], document["type"]) == (
        "aep.knowledge.repo/v1",
        vault_id,
        "bi",
    )
    assert (folder / "REPO.md").read_text(encoding="utf-8").startswith("# Market Signals")
    for name in (
        "applications/robotics/sources",
        "library/competitors/sources",
        "library/skills",
        "tags",
    ):
        assert (folder / name).is_dir()
    # The vault holds the schema it uses, built in or not (decision 1).
    assert (folder / "schemas" / "bi.schema__v1.1@5.0.0.json").is_file()
    assert _commits(drive, "a", vault_id) == ["alice/1.json"]
    first = json.loads((folder / "commits/alice/1.json").read_text(encoding="utf-8"))
    assert first["kind"] == "schema" and "bi.schema/v1.1@5.0.0" in first["purpose"]
    # No database is ever in the shared folder.
    assert not [p for p in folder.rglob("*") if p.suffix in (".sqlite", ".db")]
    assert dataset in datasets(a) and dataset in datasets(b)
    assert BiStore(b, dataset).schema_ref() == "bi.schema/v1.1@5.0.0"
    listed = _ok(_call(b, "GET", "/api/bi/vaults"))["vaults"]
    assert [(v["id"], v["author"], v["title"]) for v in listed] == [
        (vault_id, "bob", "Market Signals")
    ]
    _refused(_call(b, "POST", "/api/bi/vaults/join", {"path": str(tmp_path)}), 400, "repo_invalid")
    c = drive.workspace("c")
    other = drive.clone("a", "c", vault_id)
    body = {"path": str(other), "author": "alice"}
    _refused(_call(c, "POST", "/api/bi/vaults/join", body), 409, "author_taken")
    _ok(_call(c, "POST", "/api/bi/vaults/join", {**body, "resume": True}))
    again = {
        "path": str(drive.parent("a")),
        "title": "x",
        "id": vault_id,
        "schema": "bi.schema/v1.1",
    }
    _refused(_call(a, "POST", "/api/bi/vaults", again), 409, "vault_exists")
    _refused(
        _call(a, "POST", "/api/bi/datasets", {"name": "vault-x", "schema": "bi.schema/v1.1"}),
        400,
        "dataset_invalid",
    )


def test_an_import_commits_at_once_and_reaches_others_by_push(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"), _row("EtherCAT"), filename="tech.csv")
    status = _status(a, vault_id)
    assert (status["ahead"], status["uncommitted"]) == (1, 0)
    assert _commits(drive, "a", vault_id) == ["alice/1.json"]  # local until pushed
    assert _push(a, vault_id)["status"] == "pushed"
    written = json.loads(
        (drive.parent("a") / vault_id / "commits/alice/2.json").read_text(encoding="utf-8")
    )
    assert written["purpose"].startswith("匯入 tech.csv")
    unit = next(o for o in written["ops"] if o["unit"].endswith(":standard_body"))
    assert unit["base"] is None and unit["value"]["value"] == "IEEE"
    assert unit["value"]["source"]["ref"] == "tech.csv#row1"
    drive.deliver("a", "b", vault_id)
    assert _sync(b, vault_id)["applied"] == 1
    assert _tables(a, dataset) == _tables(b, dataset)
    # A person's edit waits in b's working copy until b commits and pushes.
    _ok(_edit(b, dataset, "TSN", "standard_body", "IEEE 802.1", "bob"))
    assert _status(b, vault_id)["uncommitted"] == 1
    pending = _ok(_call(b, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    assert [c["after"]["value"] for c in pending["uncommitted"]] == ["IEEE 802.1"]
    _refused(
        _call(b, "POST", f"/api/bi/vaults/{vault_id}/commit", {"purpose": " "}),
        400,
        "purpose_missing",
    )
    _commit(b, vault_id, "標準組織寫成 IEEE 802.1")
    assert _push(b, vault_id)["status"] == "pushed"
    drive.deliver("b", "a", vault_id)
    assert _sync(a, vault_id)["applied"] == 1
    field = _card(a, dataset, "TSN")["fields"]["standard_body"]
    assert (field["value"], field["kind"]) == ("IEEE 802.1", "human")
    assert _tables(a, dataset) == _tables(b, dataset)
    history = BiStore(a, dataset).history(_card(a, dataset, "TSN")["id"])
    assert [h["new"] for h in history if h["field"] == "standard_body"] == ["IEEE", "IEEE 802.1"]
    assert _sync(a, vault_id)["applied"] == 0


def test_a_push_after_another_on_the_same_field_is_a_conflict_until_resolved(
    tmp_path: Path,
) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"))
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    _ok(_edit(a, dataset, "TSN", "standard_body", "IEEE 802.1", "alice"))
    _commit(a, vault_id, "a 的修改")
    _push(a, vault_id)
    _ok(_edit(b, dataset, "TSN", "standard_body", "IETF", "bob"))
    _commit(b, vault_id, "b 的修改")
    drive.deliver("a", "b", vault_id)
    result = _push(b, vault_id)
    assert result["status"] == "conflicts"
    (conflict,) = result["conflicts"]
    assert (conflict["mine"]["value"], conflict["theirs"]["value"]) == ("IETF", "IEEE 802.1")
    assert _commits(drive, "b", vault_id) == ["alice/1.json", "alice/2.json", "alice/3.json"]
    _ok(
        _call(
            b,
            "POST",
            f"/api/bi/vaults/{vault_id}/resolve",
            {"unit": conflict["unit"], "choice": "mine"},
        )
    )
    assert _push(b, vault_id)["status"] == "pushed"
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    assert _card(a, dataset, "TSN")["fields"]["standard_body"]["value"] == "IETF"
    assert _tables(a, dataset) == _tables(b, dataset)


def test_different_fields_merge_on_push(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"))
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    _ok(_edit(a, dataset, "TSN", "standard_body", "IEEE 802.1", "alice"))
    _commit(a, vault_id, "a")
    _push(a, vault_id)
    _ok(_edit(b, dataset, "TSN", "body", "時間敏感網路", "bob"))
    _commit(b, vault_id, "b")
    drive.deliver("a", "b", vault_id)
    assert _push(b, vault_id)["status"] == "pushed"
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    fields = _card(a, dataset, "TSN")["fields"]
    assert (fields["standard_body"]["value"], fields["body"]["value"]) == (
        "IEEE 802.1",
        "時間敏感網路",
    )
    assert _tables(a, dataset) == _tables(b, dataset)


def test_a_race_on_replay_is_a_pending_proposal_on_every_pc(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"))
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    # Both push before OneDrive brings the other's commit.
    for ws, value, actor in ((a, "IEEE 802.1", "alice"), (b, "IETF", "bob")):
        _ok(_edit(ws, dataset, "TSN", "standard_body", value, actor))
        _commit(ws, vault_id, f"{actor} edits")
        assert _push(ws, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    _sync(b, vault_id)
    assert _tables(a, dataset) == _tables(b, dataset)
    card = _card(a, dataset, "TSN")
    winner = card["fields"]["standard_body"]["value"]
    (proposal,) = BiStore(a, dataset).proposals(card["id"])
    assert proposal["source"]["kind"] == "conflict" and {winner, proposal["value"]} == {
        "IEEE 802.1",
        "IETF",
    }
    assert [c["open"] for c in _status(a, vault_id)["conflicts"]] == [True]
    # A person accepts the other value on a: committed, pushed, closed everywhere.
    _ok(
        _call(
            a,
            "POST",
            f"/api/bi/cards/{card['id']}/proposals/{proposal['id']}",
            {"dataset": dataset, "action": "accept", "base_version": card["version"]},
            actor="alice",
        )
    )
    _commit(a, vault_id, "決定衝突")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _card(b, dataset, "TSN")["fields"]["standard_body"]["value"] == proposal["value"]
    assert BiStore(b, dataset).proposals(card["id"]) == []
    assert _tables(a, dataset) == _tables(b, dataset)


def test_a_reviewed_run_commits_once_with_its_evidence(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    csv = "技術,標準組織\nTSN,IEEE\nPTP,IEEE\n"
    source = _ok(
        _call(a, "POST", "/api/bi/sources", {"dataset": dataset, "name": "t.csv", "text": csv})
    )["source"]
    run = _ok(
        _call(
            a,
            "POST",
            "/api/bi/runs",
            {
                "dataset": dataset,
                "kind": "ingest",
                "source_id": source["id"],
                "entity_type": "Technology",
            },
        )
    )["run"]
    detail = _ok(_call(a, "GET", f"/api/bi/runs/{run['id']}", dataset=dataset))
    for candidate in detail["candidates"]:
        _ok(
            _call(
                a,
                "POST",
                f"/api/bi/runs/{run['id']}/candidates/{candidate['id']}",
                {"dataset": dataset, "review": "accepted"},
            )
        )
    committed = _ok(_call(a, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": dataset}))
    assert committed["applied"]["created"] == 2
    again = _ok(_call(a, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": dataset}))
    assert again.get("already") is True
    # The source travels in a commit of its own, the run in exactly one more.
    local = vault.Vault(a, vault_id).repo.local_commits()
    assert [item["purpose"] for item in local][0] == "加入來源：t.csv"
    assert _status(a, vault_id)["ahead"] == 2
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _tables(a, dataset) == _tables(b, dataset)
    card = _card(b, dataset, "TSN")
    assert BiStore(b, dataset).evidence(card["id"])[0]["excerpt"]


def test_a_commit_waiting_for_onedrive_and_a_tampered_one(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"))
    _push(a, vault_id)
    source = drive.parent("a") / vault_id / "commits/alice/2.json"
    target = drive.parent("b") / vault_id / "commits/alice/2.json"
    content = source.read_bytes()
    target.write_bytes(content[: len(content) // 2])  # OneDrive still downloading
    report = _sync(b, vault_id)
    assert report["applied"] == 0 and [i["file"] for i in report["incomplete"]] == [
        "commits/alice/2.json"
    ]
    target.write_bytes(content)
    assert _sync(b, vault_id)["applied"] == 1
    assert _tables(a, dataset) == _tables(b, dataset)
    forged = json.loads(content)
    forged["ops"][0]["value"] = "forged"
    target.write_text(json.dumps(forged), encoding="utf-8")
    report = _sync(b, vault_id)
    assert report["bad"] == [
        {"file": "commits/alice/2.json", "reason": "id does not match the content"}
    ]
    assert BiStore(b, dataset).find("Technology", "TSN") is None


def test_undo_and_a_schema_upgrade_travel_as_commits(tmp_path: Path) -> None:
    drive = _Drive(tmp_path)
    a, b = drive.workspace("a"), drive.workspace("b")
    example = catalog.example()
    _ok(_call(a, "POST", "/api/bi/schemas/install", example["schema"]))
    made = _ok(
        _call(
            a,
            "POST",
            "/api/bi/vaults",
            {
                "path": str(drive.parent("a")),
                "title": "Specs",
                "schema": EXAMPLE,
                "author": "alice",
            },
        )
    )
    vault_id = made["vault"]["id"]
    dataset = vault.dataset_name(vault_id)
    assert (drive.parent("a") / vault_id / "schemas" / "example__product-spec@1.0.0.json").is_file()
    store = BiStore(a, dataset)

    def supplier(key: str, country: str, filename: str) -> Any:
        row = PlannedRow(
            row=1,
            entity_type="Supplier",
            canonical_key=key,
            name=key,
            values={"name": key, "country": country},
            synthetic=True,
        )
        return store.apply([row], filename=filename, entity_type="Supplier", actor="alice via web")

    supplier("虛構電子", "TW", "s.csv")
    second = supplier("範例零件", "JP", "s2.csv")
    _ok(
        _call(a, "POST", "/api/bi/import/undo", {"dataset": dataset, "import_id": second.import_id})
    )
    assert store.find("Supplier", "範例零件") is None
    _commit(a, vault_id, "撤銷 s2.csv")
    draft = _ok(_call(a, "POST", "/api/bi/schema-drafts", {"base": EXAMPLE, "title": "v2"}))
    document = copy.deepcopy(draft["document"])
    entity = next(t for t in document["types"] if t["name"] == "Supplier")
    entity["fields"] = [f for f in entity["fields"] if f["name"] != "country"]
    entity["fields"].append({"name": "region", "label": "地區", "kind": "str", "class": "sourced"})
    document["migrations"] = {"renames": {"Supplier.country": "region"}}
    draft_id = draft["draft"]["id"]
    _ok(_call(a, "POST", f"/api/bi/schema-drafts/{draft_id}/revisions", {"document": document}))
    target = _ok(_call(a, "POST", f"/api/bi/schema-drafts/{draft_id}/publish", {}))["ref"]
    preview = _ok(_call(a, "POST", f"/api/bi/datasets/{dataset}/schema/preview", {"to": target}))
    body = {"to": target, "preview_token": preview["preview_token"]}
    applied = _ok(_call(a, "POST", f"/api/bi/datasets/{dataset}/schema/apply", body))["to"]
    # A vault's new version is numbered from its content, so two can never share a number.
    assert applied.startswith("example/product-spec@1.1.") and applied != target
    target = applied
    _commit(a, vault_id, "升級 schema：country 改名 region")
    assert _push(a, vault_id)["status"] == "pushed"
    purposes = [
        c["purpose"]
        for c in reversed(_ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/history"))["commits"])
    ]
    assert purposes[0].startswith("建立知識庫") and purposes[-2:] == [
        "撤銷 s2.csv",
        "升級 schema：country 改名 region",
    ]
    # A PC without either schema joins: it installs them from the folder.
    folder = drive.clone("a", "b", vault_id)
    _ok(_call(b, "POST", "/api/bi/vaults/join", {"path": str(folder), "author": "bob"}))
    assert BiStore(b, dataset).schema_ref() == target
    assert catalog.for_store(BiStore(b, dataset)).ref == target
    card = _card(b, dataset, "虛構電子", "Supplier")
    assert card["fields"]["region"]["value"] == "TW" and "country" not in card["fields"]
    assert BiStore(b, dataset).find("Supplier", "範例零件") is None
    assert _tables(a, dataset) == _tables(b, dataset)


def test_the_vaults_schema_file_is_authoritative(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    path = drive.parent("b") / vault_id / "schemas" / "bi.schema__v1.1@5.0.0.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["title"] = "changed elsewhere"
    path.write_text(json.dumps(document), encoding="utf-8")
    refused = _refused(
        _call(b, "POST", f"/api/bi/vaults/{vault_id}/sync", {}), 409, "schema_mismatch"
    )
    assert refused["file"] == "schemas/bi.schema__v1.1@5.0.0.json"


def test_revert_tag_and_publish(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"))
    _push(a, vault_id)
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": "v1", "purpose": "第一版"}))
    _refused(
        _call(a, "POST", f"/api/bi/vaults/{vault_id}/publish", {"tag": "v1"}),
        400,
        "confirm_required",
    )
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/publish", {"tag": "v1", "confirm": True}))
    _ok(_edit(a, dataset, "TSN", "standard_body", "wrong", "alice"))
    _commit(a, vault_id, "錯的修改")
    _push(a, vault_id)
    _refused(
        _call(a, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": "v1", "purpose": "again"}),
        409,
        "tag_exists",
    )
    _ok(
        _call(
            a,
            "POST",
            f"/api/bi/vaults/{vault_id}/revert",
            {"version": "v1", "purpose": "改錯了，回到 v1"},
        )
    )
    _push(a, vault_id)
    assert _card(a, dataset, "TSN")["fields"]["standard_body"]["value"] == "IEEE"
    history = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/history"))
    assert history["commits"][0]["kind"] == "revert" and history["published"]["tag"] == "v1"
    changed = _ok(
        _call(a, "GET", f"/api/bi/vaults/{vault_id}/diff", commit=history["commits"][0]["id"])
    )
    assert [c["after"]["value"] for c in changed["changes"]] == ["IEEE"]
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _status(b, vault_id)["published"]["tag"] == "v1"
    assert _tables(a, dataset) == _tables(b, dataset)


def test_a_dataset_converts_to_a_vault(tmp_path: Path) -> None:
    drive = _Drive(tmp_path)
    a, b = drive.workspace("a"), drive.workspace("b")
    _ok(_call(a, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    store = BiStore(a, "lab")
    store.apply(
        [_row("TSN", standard_body="IEEE")], filename="t.csv", entity_type="Technology", actor="x"
    )
    card = _card(a, "lab", "TSN")
    store.set_field(
        card["id"], "standard_body", "IEEE 802.1", base_version=card["version"], actor="p"
    )
    store.apply(
        [_row("TSN", standard_body="IETF")], filename="u.csv", entity_type="Technology", actor="x"
    )
    lab_bytes = store.path.read_bytes()
    made = _ok(
        _call(
            a,
            "POST",
            "/api/bi/vaults/convert",
            {
                "dataset": "lab",
                "path": str(drive.parent("a")),
                "author": "alice",
                "purpose": "虛構",
            },
        )
    )
    assert store.path.read_bytes() == lab_bytes  # the dataset itself is left as it was
    vault_id = made["vault"]["id"]
    dataset = vault.dataset_name(vault_id)
    assert _commits(drive, "a", vault_id) == ["alice/1.json"]
    converted = BiStore(a, dataset)
    assert converted.schema_ref() == store.schema_ref()
    original = store.find("Technology", "TSN")
    copied = converted.find("Technology", "TSN")
    assert original is not None and copied is not None
    assert converted.fields(copied["id"]) == store.fields(original["id"])
    assert [p["value"] for p in converted.proposals(copied["id"])] == ["IETF"]
    folder = drive.clone("a", "b", vault_id)
    _ok(_call(b, "POST", "/api/bi/vaults/join", {"path": str(folder), "author": "bob"}))
    assert _tables(a, dataset) == _tables(b, dataset)
    # The proposal kept from the dataset is decided in the vault like any other.
    proposal = BiStore(b, dataset).proposals(copied["id"])[0]
    _ok(
        _call(
            b,
            "POST",
            f"/api/bi/cards/{copied['id']}/proposals/{proposal['id']}",
            {"dataset": dataset, "action": "reject"},
        )
    )
    _commit(b, vault_id, "拒絕 IETF")
    _push(b, vault_id)
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    assert converted.proposals(copied["id"]) == []
    assert _tables(a, dataset) == _tables(b, dataset)


def test_converting_a_dataset_takes_its_sources_along(tmp_path: Path) -> None:
    drive = _Drive(tmp_path)
    a = drive.workspace("a")
    _ok(_call(a, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    staging = Staging(a, "lab")
    kept = staging.add_source(
        "visit.md", text="# 拜訪\nA 公司評估 TSN", actor="alice", classification="UNCLASSIFIED"
    )
    gone = staging.add_source("gone.md", text="消失的檔案", actor="alice")
    source_markdown.save(
        a,
        "lab",
        kept["id"],
        markdown="# 拜訪（改過）\nA 公司評估 TSN",
        base_rev=1,
        note="校對",
        actor="alice",
    )
    # The file is gone from disk (the row's stored path is not in the public view).
    with staging._db() as db:
        stored = db.execute("SELECT stored FROM sources WHERE id = ?", (gone["id"],)).fetchone()[0]
    (staging.dir / stored).unlink()
    before = {r["rev"]: r for r in staging.markdown_revisions(kept["id"])}
    given = {"dataset": "lab", "path": str(drive.parent("a")), "author": "alice", "purpose": "虛構"}
    made = _ok(_call(a, "POST", "/api/bi/vaults/convert", given))
    assert made["sources"] == {"copied": 1, "skipped": 1, "staged": 1}
    target = Staging(a, made["vault"]["dataset"])
    copied = target.source(kept["id"])
    assert copied is not None
    assert copied["name"] == "visit.md" and copied["classification"] == "UNCLASSIFIED"
    assert target.source(gone["id"]) is None
    # The original bytes and every Markdown revision come along, the latest still current.
    assert target.source_bytes(kept["id"]) == staging.source_bytes(kept["id"])
    assert {r["rev"]: r for r in target.markdown_revisions(kept["id"])} == before
    assert source_markdown.current(target, kept["id"]) == source_markdown.current(
        staging, kept["id"]
    )
    # A copy on this PC: the dataset keeps them and nothing reaches the shared folder.
    assert staging.source(kept["id"]) is not None
    folder = drive.parent("a") / made["vault"]["id"]
    shared = [p.name for p in folder.rglob("*") if p.is_file()]
    assert "visit.md" not in shared and not any(kept["sha256"] in name for name in shared)


def test_a_plain_dataset_is_written_as_before(tmp_path: Path) -> None:
    _ok(_call(tmp_path, "POST", "/api/bi/demo/load", {"dataset": "demo"}))
    assert not (tmp_path / "bi" / "vaults").exists()
    assert BiStore(tmp_path, "demo").vault_id is None
    assert datasets(tmp_path) == ["demo"]
    with sqlite3.connect(BiStore(tmp_path, "demo").path) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not any(t.startswith("vault_") for t in tables)


def test_an_unreachable_folder_refuses_writes(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    shutil.rmtree(drive.parent("b") / vault_id)
    with pytest.raises(Exception) as caught:
        BiStore(b, dataset).apply(
            [_row("TSN")], filename="t.csv", entity_type="Technology", actor="b"
        )
    assert getattr(caught.value, "code", "") == "vault_unreachable"
    _refused(_call(b, "POST", f"/api/bi/vaults/{vault_id}/sync", {}), 409, "vault_unreachable")
    assert _status(b, vault_id)["reachable"] is False
    _refused(_call(b, "GET", "/api/bi/vaults/nope/status"), 404, "vault_unknown")
