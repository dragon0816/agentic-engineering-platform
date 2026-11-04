"""A home's tools in ingest (`BI_CARD_MODEL.md` P2-a). All data is fictional."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _commit, _ok, _push, _refused, _two_pcs

from capabilities.bi_cards import tool_runs, vault
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore, BiStoreError
from host_runtime.bi_cards_api import route

FOLDER = "applications/aidc/sources"
TOOL = """
import csv, os
rows = open(INPUT, encoding="utf-8").read().split()
with open(os.path.join(OUTPUT, "normalized.csv"), "w", newline="", encoding="utf-8") as out:
    writer = csv.writer(out)
    writer.writerow(["name"])
    writer.writerows([r] for r in rows)
print("rows", len(rows))
"""


def _source(ws: Path, dataset: str, text: str = "虛構甲 虛構乙", **more: Any) -> dict[str, Any]:
    body = {"dataset": dataset, "name": "raw.txt", "text": text, "folder": FOLDER, **more}
    found: dict[str, Any] = _ok(route(ws, "alice", "POST", "/api/bi/sources", {}, body))["source"]
    return found


def _save(ws: Path, vault_id: str, code: str = TOOL, name: str = "normalize") -> dict[str, Any]:
    body = {"home": "aidc", "name": name, "suffix": ".py", "text": code}
    found: dict[str, Any] = _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/tools", body))["tool"]
    return found


def _approve(ws: Path, vault_id: str, sha256: str) -> None:
    body = {"sha256": sha256, "confirm": True}
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/tool-approve", body))


def _run(ws: Path, vault_id: str, source_id: str, name: str = "aidc/normalize") -> Any:
    body = {"name": name, "source_id": source_id}
    return _call(ws, "POST", f"/api/bi/vaults/{vault_id}/tool-run", body)


def _execute(code: str, tmp_path: Path) -> Any:
    raw = tmp_path / "raw.txt"
    raw.write_text("虛構", encoding="utf-8")
    return tool_runs.execute(code.encode(), raw, "raw.txt", seconds=120)


def test_a_new_revision_needs_a_persons_approval_with_the_code_visible(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    source = _source(a, dataset)
    first = _save(a, vault_id)
    refused = _refused(_run(a, vault_id, source["id"]), 409, "tool_needs_approval")
    assert refused["code_text"] == TOOL and refused["sha256"] == first["sha256"]
    listed = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/tools"))
    assert listed["tools"][0]["code"] == TOOL and listed["tools"][0]["approved"] is False
    assert "不是" in listed["guard"]
    body = {"sha256": first["sha256"]}
    path = f"/api/bi/vaults/{vault_id}/tool-approve"
    _refused(_call(a, "POST", path, body), 400, "confirm_required")
    _refused(_call(a, "POST", path, {"sha256": "0" * 64, "confirm": True}), 404, "tool_unknown")
    _approve(a, vault_id, first["sha256"])
    assert _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/tools"))["tools"][0]["approved"] is True
    _ok(_run(a, vault_id, source["id"]))
    # Another revision is other code: it asks again.
    second = _save(a, vault_id, TOOL + "\nprint('more')\n")
    assert second["path"] == "applications/aidc/tools/normalize/rev-2-alice.py"
    _refused(_run(a, vault_id, source["id"]), 409, "tool_needs_approval")


def test_the_approval_is_per_pc(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    source = _source(a, dataset)
    saved = _save(a, vault_id)
    _approve(a, vault_id, saved["sha256"])
    _ok(_run(a, vault_id, source["id"]))
    _commit(a, vault_id, "工具與來源")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _ok(_call(b, "POST", f"/api/bi/vaults/{vault_id}/sync", {}))
    _refused(_run(b, vault_id, source["id"]), 409, "tool_needs_approval")
    _approve(b, vault_id, saved["sha256"])
    _ok(_run(b, vault_id, source["id"]))


def test_the_output_is_a_new_source_and_never_a_card(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    source = _source(a, dataset, classification="CONFIDENTIAL")
    saved = _save(a, vault_id)
    _approve(a, vault_id, saved["sha256"])
    cards = len(BiStore(a, dataset).card_rows())
    done = _ok(_run(a, vault_id, source["id"]))
    assert "rows 2" in done["printed"]
    assert done["tool"] == {"name": "aidc/normalize", "revision": 1}
    assert [s["name"] for s in done["sources"]] == ["normalized.csv"]
    assert len(BiStore(a, dataset).card_rows()) == cards
    staging = Staging(a, dataset)
    kept = staging.source(done["sources"][0]["id"])
    assert kept is not None and kept["classification"] == "CONFIDENTIAL"
    assert "虛構甲" in staging.source_bytes(kept["id"]).decode("utf-8")
    unit = vault.Vault(a, vault_id).repo.working_units()[f"source:{kept['sha256']}"]
    assert unit["folder"] == FOLDER and unit["file"].startswith(FOLDER + "/")
    assert unit["derived_from"] == {
        "source": source["id"],
        "sha256": source["sha256"],
        "tool": "aidc/normalize",
        "revision": 1,
        "tool_sha256": saved["sha256"],
    }
    # The same output again is the same source.
    assert _ok(_run(a, vault_id, source["id"]))["sources"][0]["already"] is True


def test_withdrawing_a_source_takes_what_a_tool_made_from_it(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    source = _source(a, dataset)
    saved = _save(a, vault_id)
    _approve(a, vault_id, saved["sha256"])
    made = _ok(_run(a, vault_id, source["id"]))["sources"][0]
    _commit(a, vault_id, "工具與來源")
    _push(a, vault_id)
    target = vault.Vault(a, vault_id)
    units = target.repo.units()
    derived = units[f"source:{Staging(a, dataset).source(made['id'])['sha256']}"]  # type: ignore[index]
    assert (target.folder / derived["file"]).is_file()
    body = {"source_id": source["id"], "reason": "虛構", "confirm": True}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/withdraw-source", body))
    assert not (target.folder / derived["file"]).exists()
    assert Staging(a, dataset).source(made["id"]) is None


@pytest.mark.parametrize(
    ("code", "said"),
    [
        ("import socket", "socket"),
        ("import subprocess", "subprocess"),
        ("import os\nos.system('echo x')", "os.system"),
        ("import ctypes", "ctypes"),
        ("import sqlite3\nsqlite3.connect('x.sqlite')", "sqlite3.connect"),
        ("open('outside.txt', 'w').write('x')", "outside"),
        ("import os\nos.mkdir('elsewhere')", "outside"),
        ("raise ValueError('虛構的錯誤')", "虛構的錯誤"),
    ],
)
def test_the_guard_refuses(tmp_path: Path, code: str, said: str) -> None:
    with pytest.raises(BiStoreError) as failure:
        _execute(code, tmp_path)
    assert failure.value.code == "tool_failed" and said in failure.value.message


def test_shutil_cannot_copy_out_of_the_output_folder(tmp_path: Path) -> None:
    target = tmp_path / "escaped.txt"
    code = f"import shutil\nshutil.copy(INPUT, {str(target)!r})"
    with pytest.raises(BiStoreError):
        _execute(code, tmp_path)
    assert not target.exists()


def test_a_tool_may_write_into_its_output_folder_only(tmp_path: Path) -> None:
    code = (
        "import os\nos.makedirs(OUTPUT, exist_ok=True)\n"
        "open(os.path.join(OUTPUT, 'a.md'), 'w').write('# x')"
    )
    outputs, _ = _execute(code, tmp_path)
    assert [(o.name, o.data) for o in outputs] == [("a.md", b"# x")]


@pytest.mark.parametrize(
    "code",
    [
        "print('nothing written')",
        "import os\nopen(os.path.join(OUTPUT, 'a.exe'), 'w').write('x')",
        "import os\nopen(os.path.join(OUTPUT, 'a.csv'), 'w').close()",
    ],
)
def test_output_that_is_not_a_csv_or_markdown_is_refused(tmp_path: Path, code: str) -> None:
    with pytest.raises(BiStoreError) as failure:
        _execute(code, tmp_path)
    assert failure.value.code == "tool_output_invalid"


def test_a_tool_that_runs_too_long_is_stopped(tmp_path: Path) -> None:
    raw = tmp_path / "raw.txt"
    raw.write_text("x", encoding="utf-8")
    with pytest.raises(BiStoreError) as failure:
        tool_runs.execute(b"while True: pass", raw, "raw.txt", seconds=8)
    assert failure.value.code == "tool_failed"


def test_only_python_runs(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    source = _source(a, dataset)
    body = {"home": "aidc", "name": "macro", "suffix": ".js", "text": "x"}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/tools", body))
    _refused(_run(a, vault_id, source["id"], "aidc/macro"), 400, "tool_not_python")
    _refused(_run(a, vault_id, source["id"], "aidc/none"), 404, "tool_unknown")


def test_an_ai_draft_waits_for_the_person_and_stages_nothing(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    source = _source(a, dataset)
    before = vault.Vault(a, vault_id).repo.working_units()
    given = {"home": "aidc", "name": "normalize", "code": TOOL}
    made = tool_runs.draft(a, vault_id, given, "alice via web")
    assert made["approved"] is False
    assert vault.Vault(a, vault_id).repo.working_units() == before
    with pytest.raises(BiStoreError) as failure:
        tool_runs.try_draft(a, vault_id, made["sha256"], source["id"])
    assert failure.value.code == "tool_needs_approval"
    listed = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/tools"))
    assert listed["drafts"][0]["code"] == TOOL
    _approve(a, vault_id, made["sha256"])
    tried = tool_runs.try_draft(a, vault_id, made["sha256"], source["id"])
    assert tried["files"][0]["name"] == "normalized.csv" and "虛構甲" in tried["files"][0]["text"]
    # Only shown: no source was kept and nothing was staged.
    assert len(Staging(a, dataset).sources()) == 1
    assert vault.Vault(a, vault_id).repo.working_units() == before
    # Saved as a revision it is the same code, already read and approved here.
    saved = _save(a, vault_id)
    assert saved["sha256"] == made["sha256"]
    _ok(_run(a, vault_id, source["id"]))
    assert _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/tools"))["drafts"] == []
