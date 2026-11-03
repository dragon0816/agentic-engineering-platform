"""Knowledge repositories R3, BI part (`docs/phases/KNOWLEDGE_REPO.md` §8).

A vault holds a generated classify skill; a domain's notes move into its
extract skill; an AI run reads the classify skill and the extract skill of the
source's folder after the fixed evidence rules; a skill written for another
schema version is not run until it is updated. Two PCs as in
`test_bi_vault.py`. All data is fictional.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_vault import _call, _commit, _ok, _push, _refused, _sync, _two_pcs

from capabilities.bi_cards import vault, vault_skills
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore
from host_runtime.bi_cards_api import route

V1 = "bi.schema/v1.1@1.1.0"
V2 = "bi.schema/v1.1@2.0.0"
NEWEST = "bi.schema/v1.1@5.0.0"  # a new vault's (the newest shipped)
NOTES = "ODM 是 Account；晶片廠是 Ecosystem。"
CONFIG: dict[str, Any] = {
    "domains": [
        {
            "id": "aidc",
            "label": "AI 資料中心",
            "segments": [
                {"id": "aidc-computing", "label": "AIDC Computing"},
                {"id": "aidc-power", "label": "AIDC Power"},
            ],
            "notes": NOTES,
        },
        {"id": "aerospace", "label": "航太", "notes": "衛星營運商是 Account。"},
    ],
    "areas": [{"id": "chipset", "label": "晶片"}],
    "segment_field": "segment",
    "area_field": "role",
}
NOTE = "虛構電力公司宣布液冷方案，與虛構 ODM 合作。"


def _skills(ws: Path, vault_id: str) -> dict[str, dict[str, Any]]:
    listed = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/skills"))
    return {s["name"]: s for s in listed["skills"]}


def _save_domains(ws: Path, dataset: str) -> dict[str, Any]:
    """An old domain configuration (written as 「領域設定」 did before BI D4)."""
    store = BiStore(ws, dataset)
    store.set_meta_value("domains", json.dumps(CONFIG, ensure_ascii=False), base=None)
    return {"config": json.loads(store.meta_value("domains") or "{}")}


def _ai_run(ws: Path, dataset: str, folder: str, model: Scripted) -> tuple[Any, Jobs]:
    jobs = Jobs()
    ai = _runtime(model, jobs)
    body = {"dataset": dataset, "name": "note.md", "text": NOTE}
    source = _ok(route(ws, "alice", "POST", "/api/bi/sources", {}, body))["source"]["id"]
    start = {"dataset": dataset, "kind": "ingest", "source_id": source, "folder": folder}
    return route(ws, "alice", "POST", "/api/bi/runs", {}, start, None, ai), jobs


def test_a_new_vault_holds_a_generated_classify_skill(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    found = _skills(a, vault_id)
    classify = found["classify"]
    assert classify["role"] == "classify" and classify["schema"] == NEWEST
    assert classify["generated"] and not classify["needs_update"]
    assert "- SupplyLink：" in classify["body"] and "- aidc：AIDC" in classify["body"]
    # It is a file in the shared folder, listed in REPO.md, and on the other PC.
    folder = drive.parent("a") / vault_id
    assert (folder / classify["path"]).is_file()
    assert "classify" in (folder / "REPO.md").read_text(encoding="utf-8")
    assert _skills(b, vault_id)["classify"]["revision"] == 1


def test_domain_notes_move_into_extract_skills(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    saved = _save_domains(a, dataset)
    # The configuration keeps everything but the notes.
    assert [d["notes"] for d in saved["config"]["domains"]] == ["", ""]
    assert [s["id"] for s in saved["config"]["domains"][0]["segments"]] == [
        "aidc-computing",
        "aidc-power",
    ]
    found = _skills(a, vault_id)
    aidc, aerospace = found["aidc-extract"], found["aerospace-extract"]
    assert aidc["body"] == NOTES and aidc["role"] == "extract"
    # A domain whose segments are no application gets an application of its own
    # (a domain whose segments are: `test_bi_vault_homes`).
    assert aidc["applies_to"] == ["applications/aidc/sources"]
    assert aerospace["applies_to"] == ["applications/aerospace/sources"]
    pending = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    labels = {c["label"] for c in pending["uncommitted"]}
    assert {"領域設定", "skill「aidc-extract」", "skill「aerospace-extract」"} <= labels
    _commit(a, vault_id, "領域設定與判讀規則")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _skills(b, vault_id)["aidc-extract"]["body"] == NOTES


def test_an_ai_run_reads_the_skills_of_its_folder(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _save_domains(a, dataset)
    model = Scripted({"candidates": []})
    answer, jobs = _ai_run(a, dataset, "applications/aidc/sources", model)
    run = _ok(answer)["run"]
    jobs.run_all()
    system = model.requests[0].messages[0].text
    assert system.index("Evidence rules (always apply)") < system.index("skill classify")
    assert "Extraction (skill aidc-extract, revision 1):\n" + NOTES in system
    assert "衛星營運商" not in system  # another domain's skill
    used = Staging(a, dataset).layout(run["id"]) or {}  # the run keeps the revisions it read
    assert [(u["name"], u["revision"]) for u in used["skills"]["skills"]] == [
        ("classify", 1),
        ("aidc-extract", 1),
    ]
    detail = _ok(_call(a, "GET", f"/api/bi/runs/{run['id']}", dataset=dataset))
    assert detail["run"]["status"] == "review"
    # A library source reads the classify skill only.
    model = Scripted({"candidates": []})
    answer, jobs = _ai_run(a, dataset, "library/products/sources", model)
    jobs.run_all()
    system = model.requests[0].messages[0].text
    assert "skill classify" in system and "Extraction (skill" not in system
    _refused(_ai_run(a, dataset, "../elsewhere", Scripted())[0], 400, "folder_invalid")


def test_a_skill_for_an_older_schema_is_not_run_until_updated(tmp_path: Path) -> None:
    a, parent = tmp_path / "ws", tmp_path / "drive"
    a.mkdir()
    parent.mkdir()
    made = _ok(
        _call(
            a,
            "POST",
            "/api/bi/vaults",
            {"path": str(parent), "title": "Old", "purpose": "虛構測試", "schema": V1,
             "author": "alice"},
        )
    )  # fmt: skip
    vault_id = made["vault"]["id"]
    dataset = vault.dataset_name(vault_id)
    rule = {"name": "power-extract", "role": "extract", "body": "電源廠是 Account。",
            "applies_to": ["sources/applications/aidc-power"]}  # fmt: skip
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/skills", rule))
    _commit(a, vault_id, "電源判讀規則")
    path = f"/api/bi/datasets/{dataset}/schema"
    preview = _ok(_call(a, "POST", f"{path}/preview", {"to": V2}))
    _ok(_call(a, "POST", f"{path}/apply", {"to": V2, "preview_token": preview["preview_token"]}))
    found = _skills(a, vault_id)
    # The generated classify skill follows the schema; the written one waits.
    assert found["classify"]["schema"] == V2 and found["classify"]["revision"] == 2
    assert found["power-extract"]["needs_update"]
    answer, _ = _ai_run(a, dataset, "sources/applications/aidc-power", Scripted())
    refused = _refused(answer, 409, "skill_needs_update")
    assert "power-extract" in refused["message"]
    # Saving it again binds it to the vault's schema; the run then starts.
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/skills", rule))
    assert not _skills(a, vault_id)["power-extract"]["needs_update"]
    model = Scripted({"candidates": []})
    answer, jobs = _ai_run(a, dataset, "sources/applications/aidc-power", model)
    _ok(answer)
    jobs.run_all()
    assert "skill power-extract, revision 2" in model.requests[0].messages[0].text


def test_an_edited_classify_skill_is_kept_on_a_schema_change(tmp_path: Path) -> None:
    a, parent = tmp_path / "ws", tmp_path / "drive"
    a.mkdir()
    parent.mkdir()
    made = _ok(
        _call(a, "POST", "/api/bi/vaults", {"path": str(parent), "title": "Old",
                                            "purpose": "虛構測試", "schema": V1})
    )  # fmt: skip
    vault_id = made["vault"]["id"]
    dataset = vault.dataset_name(vault_id)
    edit = {"name": "classify", "role": "classify", "body": "只做 Signal 卡。"}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/skills", edit))
    _commit(a, vault_id, "只收訊號")
    path = f"/api/bi/datasets/{dataset}/schema"
    preview = _ok(_call(a, "POST", f"{path}/preview", {"to": V2}))
    _ok(_call(a, "POST", f"{path}/apply", {"to": V2, "preview_token": preview["preview_token"]}))
    classify = _skills(a, vault_id)["classify"]
    assert classify["body"] == "只做 Signal 卡。" and classify["needs_update"]
    assert not classify["generated"]


def test_a_skill_save_is_checked(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    path = f"/api/bi/vaults/{vault_id}/skills"
    base = {"name": "x-extract", "role": "extract", "body": "規則"}
    _refused(_call(a, "POST", path, {**base, "role": "ingest"}), 400, "skill_invalid")
    _refused(_call(a, "POST", path, {**base, "card_types": ["Moon"]}), 400, "skill_invalid")
    _refused(_call(a, "POST", path, {**base, "applies_to": ["raw"]}), 400, "skill_invalid")
    _refused(_call(a, "POST", path, {**base, "body": " "}), 400, "skill_invalid")
    _refused(_call(a, "POST", path, {**base, "name": "X Y"}), 400, "skill_invalid")
    saved = _ok(_call(a, "POST", path, {**base, "card_types": ["Account"]}))
    assert saved["skill"]["revision"] == 1 and saved["status"]["uncommitted"] >= 2


def test_converting_a_dataset_moves_its_notes(tmp_path: Path) -> None:
    ws, parent = tmp_path / "ws", tmp_path / "drive"
    ws.mkdir()
    parent.mkdir()
    _ok(_call(ws, "POST", "/api/bi/datasets", {"name": "market", "schema": V2}))
    _save_domains(ws, "market")
    made = _ok(_call(ws, "POST", "/api/bi/vaults/convert",
                     {"dataset": "market", "path": str(parent), "author": "alice"}))  # fmt: skip
    vault_id = made["vault"]["id"]
    found = _skills(ws, vault_id)
    assert found["aidc-extract"]["body"] == NOTES and "classify" in found
    document = json.loads(BiStore(ws, vault.dataset_name(vault_id)).meta_value("domains") or "{}")
    assert [d.get("notes") for d in document["domains"]] == ["", ""]
    # The dataset itself is left as it was.
    kept = json.loads(BiStore(ws, "market").meta_value("domains") or "{}")
    assert kept["domains"][0]["notes"] == NOTES
    assert vault_skills.notes_skill_name("AIDC") == "aidc-extract"
    shutil.rmtree(parent)
