"""A working domain's skills and tools as a package (`aep.bi.package/v1`).

Design: `docs/phases/BI_SKILL_TOOL_PACKAGE_IMPORT_DESIGN_20261119.md`; owner choices in
`docs/DECISIONS.md` (2026-11-19): command-line scripts import as 「需改寫」, a package without a
manifest is inferred, import goes only into the current working domain. Preview first, then
batches staged as uncommitted vault changes; nothing in a package runs. All fictional.
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_vault import _call, _commit, _ok, _refused, _two_pcs

from aep_bi.cards import packages, tool_session, vault
from aep_bi.host import bi_cards_api

FIXTURES = Path(__file__).parent / "fixtures"
SKILL_BODY = "供應商表格：每列一個 Technology，名稱在第一欄。"
TOOL = '''"""Turn a vendor sheet into one CSV.

Each row of the sheet becomes one row of rows.csv.
"""
import os

text = open(INPUT, encoding="utf-8").read()
with open(os.path.join(OUTPUT, "rows.csv"), "w", encoding="utf-8") as out:
    out.write("line" + chr(10) + text)
'''
CLI = '''"""A command-line ingest script."""
import argparse
import yaml
import bi_schema

parser = argparse.ArgumentParser()
parser.add_argument("source")
args = parser.parse_args()
print(yaml, bi_schema, args)
'''


def _post(ws: Path, vault_id: str, body: Any) -> Any:
    return _call(ws, "POST", f"/api/bi/vaults/{vault_id}/package", body)


def _zip(files: Mapping[str, str | bytes], top: str = "") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(top + name, data)
    return buffer.getvalue()


def _manifest(*contents: dict[str, Any], name: str = "vendor-pack") -> str:
    return json.dumps({"format": packages.FORMAT, "name": name, "contents": list(contents)})


def _skill_text(name: str, body: str = SKILL_BODY, role: str = "extract", **extra: Any) -> str:
    head = {
        "name": name,
        "revision": 1,
        "schema": "bi.schema/v1.1@1.0.0",
        "role": role,
        "applies_to": ["sources/vendor"],
        "card_types": ["Technology"],
        **extra,
    }
    lines = [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in head.items()]
    return "---\n" + "\n".join(lines) + "\n---\n\n" + body + "\n"


def _skill_entry(name: str) -> dict[str, Any]:
    return {"kind": "skill", "name": name, "file": f"skills/{name}.md"}


def _tool_entry(name: str) -> dict[str, Any]:
    return {"kind": "tool", "name": name, "file": f"tools/{name}.py"}


def _preview(ws: Path, vault_id: str, home: str, data: bytes) -> dict[str, Any]:
    return packages.preview_zip(ws, vault_id, home, data, "vendor.zip")


def _apply(ws: Path, vault_id: str, preview: dict[str, Any], **actions: str) -> list[Any]:
    """Apply every default item (and the ones given an action) in batches, as the page does."""
    chosen = [
        {"id": i["id"], **({"as": actions[i["id"]]} if i["id"] in actions else {})}
        for i in preview["items"]
        if i["default"] or i["id"] in actions
    ]
    results = []
    for at in range(0, len(chosen), packages.BATCH):
        batch = {"token": preview["token"], "items": chosen[at : at + packages.BATCH]}
        results += _ok(_post(ws, vault_id, {"apply": batch}))["results"]
    return results


def _items(preview: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {i["id"]: i for i in preview["items"]}


def _units(ws: Path, vault_id: str) -> dict[str, Any]:
    return dict(vault.Vault(ws, vault_id).repo.working_units())


def _domain_with_rule_and_tool(ws: Path, vault_id: str) -> None:
    rule = {
        "home": "aidc",
        "name": "vendor-extract",
        "role": "extract",
        "body": SKILL_BODY,
        "applies_to": ["applications/aidc/sources/vendor"],
        "card_types": ["Technology"],
    }
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/skills", rule))
    tool = {"home": "aidc", "name": "vendor-rows", "suffix": ".py", "text": TOOL}
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/tools", tool))
    _commit(ws, vault_id, "規則與工具")


def test_export_then_import_into_another_domain_round_trips(tmp_path: Path) -> None:
    _, vault_id, _dataset, a, _ = _two_pcs(tmp_path)
    _domain_with_rule_and_tool(a, vault_id)
    listed = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/package", home="aidc"))["items"]
    assert [i["id"] for i in listed] == ["skill:vendor-extract", "tool:vendor-rows"]
    data = packages.export_zip(a, vault_id, "aidc")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read(packages.MANIFEST))
        names = sorted(archive.namelist())
        tool_bytes = archive.read("tools/vendor-rows.py")
    assert names == [packages.MANIFEST, "skills/vendor-extract.md", "tools/vendor-rows.py"]
    assert manifest["format"] == packages.FORMAT
    assert manifest["exported_from"]["home"] == "aidc" and manifest["exported_from"]["commit"]
    skill, tool = manifest["contents"]
    assert skill["applies_to"] == ["sources/vendor"], "applies_to leaves the home out"
    assert skill["from_revision"] == 1 and skill["role"] == "extract"
    assert tool["description"] == "Turn a vendor sheet into one CSV.", "from the docstring"
    import hashlib

    assert tool["sha256"] == hashlib.sha256(tool_bytes).hexdigest()

    # Into another working domain: both new, then staged as that domain's.
    preview = _preview(a, vault_id, "wireless", data)
    assert preview["package"]["inferred"] is False and preview["home"] == "wireless"
    assert {i["id"]: i["status"] for i in preview["items"]} == {
        "skill:vendor-extract": "new",
        "tool:vendor-rows": "new",
    }
    assert preview["guard"] == packages.GUARD
    before = _units(a, vault_id)
    results = _apply(a, vault_id, preview)
    assert [r["result"] for r in results] == ["staged", "staged"]
    units = _units(a, vault_id)
    rule = units["skill:wireless/vendor-extract"]
    assert rule["applies_to"] == ["applications/wireless/sources/vendor"]
    assert rule["revision"] == 1
    tool_unit = units["tool:wireless/vendor-rows"]
    assert tool_unit["sha256"] == units["tool:aidc/vendor-rows"]["sha256"]
    assert tool_unit["description"] == "Turn a vendor sheet into one CSV."
    assert "needs_rewrite" not in tool_unit
    assert units["skill:aidc/vendor-extract"] == before["skill:aidc/vendor-extract"]

    # At most once: the same batch again, and the same package again, change nothing.
    again = _apply(a, vault_id, preview)
    assert [r["result"] for r in again] == ["already", "already"]
    second = _preview(a, vault_id, "wireless", data)
    assert {i["status"] for i in second["items"]} == {"same"}
    assert not any(i["default"] for i in second["items"])
    forced = _ok(
        _post(a, vault_id, {"apply": {"token": second["token"],
                                      "items": [{"id": "tool:vendor-rows"}]}})
    )["results"]  # fmt: skip
    assert forced[0]["result"] == "same"
    assert _units(a, vault_id) == units

    # Exported again from the new domain: the same files.
    _commit(a, vault_id, "匯入")
    with zipfile.ZipFile(io.BytesIO(packages.export_zip(a, vault_id, "wireless"))) as archive:
        assert archive.read("tools/vendor-rows.py") == tool_bytes
        assert json.loads(archive.read(packages.MANIFEST))["contents"][0]["applies_to"] == [
            "sources/vendor"
        ]


def test_a_zip_and_its_folder_preview_the_same_and_one_wrapper_folder_is_taken_off(
    tmp_path: Path,
) -> None:
    _, vault_id, _dataset, a, _ = _two_pcs(tmp_path)
    files = {
        packages.MANIFEST: _manifest(_skill_entry("vendor-extract"), _tool_entry("vendor-rows")),
        "skills/vendor-extract.md": _skill_text("vendor-extract"),
        "tools/vendor-rows.py": TOOL,
        "README.md": "說明",
    }
    zipped = _preview(a, vault_id, "aidc", _zip(files, top="vendor-pack/"))
    folder = _ok(
        _post(a, vault_id, {"preview": {"home": "aidc", "files": [
            {"path": "vendor-pack/" + k, "text": v} for k, v in files.items()]}})
    )  # fmt: skip
    strip = ("token",)
    assert {k: v for k, v in zipped.items() if k not in strip} == {
        k: v for k, v in folder.items() if k not in strip + ("ok",)
    }
    assert zipped["package"]["readme"] == "說明"


def test_without_a_manifest_the_contents_are_inferred(tmp_path: Path) -> None:
    _, vault_id, _dataset, a, _ = _two_pcs(tmp_path)
    data = _zip(
        {
            "rules/vendor-extract.md": _skill_text("vendor-extract"),
            "notes.md": "# 只是筆記",
            "Vendor_Rows.py": TOOL,
            "data.csv": "a,b",
        }
    )
    preview = _preview(a, vault_id, "aidc", data)
    assert preview["package"]["inferred"] is True
    assert preview["package"]["name"] == "vendor", "named after the zip for a rename"
    found = _items(preview)
    assert set(found) == {"skill:vendor-extract", "tool:vendor-rows"}
    assert all(i["status"] == "new" for i in found.values())
    assert {s["file"]: s["reason"] for s in preview["skipped"]} == {
        "notes.md": "不是判讀規則或工具",
        "data.csv": "不支援的檔案類型",
    }


def test_an_update_is_the_next_revision_and_the_old_one_stays(tmp_path: Path) -> None:
    _, vault_id, _dataset, a, _ = _two_pcs(tmp_path)
    _domain_with_rule_and_tool(a, vault_id)
    old = _units(a, vault_id)["skill:aidc/vendor-extract"]
    data = _zip(
        {
            packages.MANIFEST: _manifest(_skill_entry("vendor-extract")),
            "skills/vendor-extract.md": _skill_text("vendor-extract", body="新的判讀方式。"),
        }
    )
    preview = _preview(a, vault_id, "aidc", data)
    item = _items(preview)["skill:vendor-extract"]
    assert (item["status"], item["default"], item["revision"]) == ("update", True, 1)
    assert _apply(a, vault_id, preview)[0]["revision"] == 2
    target = vault.Vault(a, vault_id)
    now = target.repo.working_units()["skill:aidc/vendor-extract"]
    assert now["revision"] == 2 and now["path"] != old["path"]
    for path in (old["path"], now["path"]):
        assert (target.folder / path).is_file() or (target.repo.work / "files" / path).is_file()
    skills = {s["name"]: s for s in vault.skills(a, vault_id)["skills"]}
    assert skills["aidc/vendor-extract"]["body"] == "新的判讀方式。"


def test_conflicts_follow_the_role_rule_and_are_not_ticked(tmp_path: Path) -> None:
    _, vault_id, _dataset, a, _ = _two_pcs(tmp_path)
    _domain_with_rule_and_tool(a, vault_id)
    # A classify rule of this domain with the name the package's extract rule has.
    classify = {"home": "aidc", "name": "sorter", "role": "classify", "body": "分類。"}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/skills", classify))
    # The tool changed on this PC and not committed.
    edited = {"home": "aidc", "name": "vendor-rows", "suffix": ".py", "text": TOOL + "# local\n"}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/tools", edited))
    data = _zip(
        {
            packages.MANIFEST: _manifest(_skill_entry("sorter"), _tool_entry("vendor-rows")),
            "skills/sorter.md": _skill_text("sorter"),
            "tools/vendor-rows.py": TOOL + "# from the package\n",
        }
    )
    preview = _preview(a, vault_id, "aidc", data)
    found = _items(preview)
    sorter, rows = found["skill:sorter"], found["tool:vendor-rows"]
    assert (sorter["status"], sorter["action"], sorter["rename_to"]) == (
        "conflict",
        "rename",
        "sorter-vendor-pack",
    ), "a different role is imported under a new name"
    assert (rows["status"], rows["action"]) == ("conflict", "new_revision"), "same role"
    assert not sorter["default"] and not rows["default"], "a conflict is never ticked"
    assert _apply(a, vault_id, preview) == [], "nothing chosen, nothing staged"
    refused = _ok(
        _post(a, vault_id, {"apply": {"token": preview["token"],
                                      "items": [{"id": "tool:vendor-rows"}]}})
    )["results"]  # fmt: skip
    assert refused[0]["result"] == "failed" and "改名匯入" in refused[0]["message"]
    results = _apply(
        a, vault_id, preview, **{"skill:sorter": "rename", "tool:vendor-rows": "new_revision"}
    )
    assert [(r["name"], r["revision"]) for r in results] == [
        ("aidc/sorter-vendor-pack", 1),
        ("aidc/vendor-rows", 3),
    ]
    units = _units(a, vault_id)
    assert units["skill:aidc/sorter"]["role"] == "classify", "the existing rule is untouched"
    assert units["skill:aidc/sorter-vendor-pack"]["role"] == "extract"


def test_invalid_items_say_every_reason_and_cannot_be_applied(tmp_path: Path) -> None:
    _, vault_id, _dataset, a, _ = _two_pcs(tmp_path)
    data = _zip(
        {
            packages.MANIFEST: _manifest(
                _skill_entry("unknown-type"),
                _skill_entry("other-domain"),
                _skill_entry("classifier"),
                _skill_entry("no-head"),
                _skill_entry("missing-file"),
                _tool_entry("broken"),
                {"kind": "tool", "name": "Bad_Name", "file": "tools/bad.py"},
                {"kind": "workflow", "name": "flow", "file": "flows/flow.json"},
            ),
            "skills/unknown-type.md": _skill_text("unknown-type", card_types=["Spaceship"]),
            "skills/other-domain.md": _skill_text(
                "other-domain", applies_to=["applications/wireless/sources"]
            ),
            "skills/classifier.md": _skill_text("classifier", role="classify"),
            "skills/no-head.md": "只是一段文字。",
            "tools/broken.py": "def (:\n",
            "tools/bad.py": TOOL,
            "tools/unlisted.py": TOOL,
        }
    )
    preview = _preview(a, vault_id, "aidc", data)
    found = _items(preview)
    assert all(i["status"] == "invalid" and not i["default"] for i in found.values())
    reasons = {k: "；".join(v["reasons"]) for k, v in found.items()}
    assert "Spaceship" in reasons["skill:unknown-type"]
    assert "不在這個工作領域" in reasons["skill:other-domain"]
    assert "classify" in reasons["skill:classifier"]
    assert "frontmatter" in reasons["skill:no-head"]
    assert "包裡沒有 skills/missing-file.md" in reasons["skill:missing-file"]
    assert "無法編譯" in reasons["tool:broken"]
    assert "名稱只能用小寫英數字" in reasons["tool:Bad_Name"]
    assert "kind 必須是 skill 或 tool" in reasons["workflow:flow"]
    assert {"file": "tools/unlisted.py", "reason": f"沒有列在 {packages.MANIFEST}"} in preview[
        "skipped"
    ]
    before = _units(a, vault_id)
    results = _ok(
        _post(a, vault_id, {"apply": {"token": preview["token"],
                                      "items": [{"id": "tool:broken"}]}})
    )["results"]  # fmt: skip
    assert results[0]["result"] == "failed" and "無法編譯" in results[0]["message"]
    assert _units(a, vault_id) == before
    # A manifest of another format is refused as a whole.
    status, refused = _post(a, vault_id, {"preview": {"home": "aidc", "files": [
        {"path": packages.MANIFEST, "text": json.dumps({"format": "other"})}]}})  # fmt: skip
    assert (status, refused["code"]) == (400, "package_invalid")
    # Only into a working domain.
    status, refused = _post(a, vault_id, {"preview": {"home": "", "files": [
        {"path": "tools/x.py", "text": TOOL}]}})  # fmt: skip
    assert (status, refused["code"]) == (400, "home_invalid")


@pytest.mark.parametrize(
    "folder", ["robotics_kb_sample/tools", "bi_vault_example/tools"], ids=["robotics", "example"]
)
def test_the_owners_command_line_scripts_import_as_needing_a_rewrite(
    tmp_path: Path, folder: str
) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    root = FIXTURES / folder
    files = [
        {"path": "tools/" + p.relative_to(root).as_posix(), "text": p.read_text(encoding="utf-8")}
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix in (".py", ".md", ".json", ".txt")
    ]
    preview = _ok(_post(a, vault_id, {"preview": {"home": "aidc", "files": files}}))
    assert preview["package"]["inferred"] is True
    found = _items(preview)
    assert "tool:bi-ingest" in found and "tool:bi-schema" in found
    ingest = found["tool:bi-ingest"]
    assert (ingest["status"], ingest["needs_rewrite"], ingest["default"]) == ("new", True, True)
    said = "；".join(ingest["warnings"])
    assert "命令列腳本" in said and "INPUT" in said
    assert "bi_schema" in said and "單檔" in said, "a sibling module is named"
    assert "yaml" in said, "pyyaml is not in the sandbox"
    assert ingest["description"].startswith("BI vault ingest"), "from the docstring"
    assert found["tool:bi-schema"]["needs_rewrite"] is True

    results = _apply(a, vault_id, preview)
    assert {r["result"] for r in results} == {"staged"}
    unit = _units(a, vault_id)["tool:aidc/bi-ingest"]
    assert unit["needs_rewrite"] is True and unit["description"].startswith("BI vault ingest")
    listed = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/tools"))["tools"]
    assert next(t for t in listed if t["name"] == "aidc/bi-ingest")["needs_rewrite"] is True
    # Kept, not runnable until rewritten.
    body = {
        "dataset": dataset,
        "name": "raw.md",
        "text": "# raw\n",
        "folder": "applications/aidc/sources",
    }
    source = _ok(_call(a, "POST", "/api/bi/sources", body))["source"]["id"]
    _refused(
        _call(a, "POST", f"/api/bi/vaults/{vault_id}/tool-run",
              {"name": "aidc/bi-ingest", "source_id": source}),
        400,
        "tool_needs_rewrite",
    )  # fmt: skip

    # One click: the existing tool AI gets the script and is told to rewrite it.
    session = _ok(
        _call(a, "POST", "/api/bi/sessions", {"dataset": dataset, "kind": "tool", "target": "aidc"})
    )["session"]
    model = Scripted({"reply": "改寫好了。", "needs": [], "code": TOOL, "notes": []})
    code = next(t for t in listed if t["name"] == "aidc/bi-ingest")["code"]
    turn = _ok(
        bi_cards_api.route(
            a, "alice", "POST", f"/api/bi/sessions/{session['id']}/turns", {},
            {"dataset": dataset, "message": "請把這個命令列腳本改寫成工具", "scope": "aidc",
             "code": code, "source_ids": [source]},
            None, _runtime(model, Jobs()),
        )
    )["session"]["turns"][-1]  # fmt: skip
    assert turn["suggestion"]["code"] == TOOL
    assert tool_session.REWRITE_HINT in model.requests[0].messages[1].text
    # Saving the rewritten code is a new revision that runs.
    saved = _ok(
        _call(a, "POST", f"/api/bi/vaults/{vault_id}/tools",
              {"home": "aidc", "name": "bi-ingest", "suffix": ".py", "text": TOOL})
    )["tool"]  # fmt: skip
    assert saved["revision"] == 2 and "needs_rewrite" not in saved
    ran = _ok(
        _call(a, "POST", f"/api/bi/vaults/{vault_id}/tool-run",
              {"name": "aidc/bi-ingest", "source_id": source})
    )  # fmt: skip
    assert [s["name"] for s in ran["sources"]] == ["rows.csv"]


def _symlink_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        info = zipfile.ZipInfo("tools/link.py")
        info.external_attr = 0o120777 << 16
        archive.writestr(info, "/etc/passwd")
    return buffer.getvalue()


def _backslash_zip() -> bytes:
    # zipfile writes `/` on Windows; the bytes are changed to what another tool may write.
    return _zip({"tools/evil.py": TOOL}).replace(b"tools/evil.py", b"tools\\evil.py")


def _bomb() -> bytes:
    return _zip({"tools/big.py": b"#" + b"0" * (2 * 1024 * 1024)})


@pytest.mark.parametrize(
    ("data", "said"),
    [
        (_zip({"../evil.py": TOOL}), ".."),
        (_zip({"tools/../../evil.py": TOOL}), ".."),
        (_zip({"/abs/evil.py": TOOL}), "絕對路徑"),
        (_zip({"C:/evil.py": TOOL}), "磁碟代號"),
        (_backslash_zip(), "反斜線"),
        (_zip({"tools/con.py": TOOL}), "Windows 保留"),
        (_zip({"tools/a.py": TOOL, "tools/A.py": TOOL}), "大小寫"),
        (_symlink_zip(), "symlink"),
        (_bomb(), "zip bomb"),
        (b"not a zip", "不是 zip"),
    ],
    ids=["slip", "slip-deep", "absolute", "drive", "backslash", "reserved", "case", "symlink",
         "bomb", "garbage"],
)  # fmt: skip
def test_an_unsafe_zip_is_refused_whole_and_nothing_is_kept(
    tmp_path: Path, data: bytes, said: str
) -> None:
    _, vault_id, _dataset, a, _ = _two_pcs(tmp_path)
    with pytest.raises(Exception) as caught:
        _preview(a, vault_id, "aidc", data)
    assert getattr(caught.value, "code", None) == "package_invalid", caught.value
    assert said in str(getattr(caught.value, "message", caught.value))
    kept = vault.local_dir(a, vault_id) / packages.IMPORTS_DIR
    assert not kept.exists() or not any(kept.iterdir())


def test_size_and_count_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, vault_id, _dataset, a, _ = _two_pcs(tmp_path)
    many = _zip({f"tools/t{n}.py": TOOL for n in range(packages.MAX_FILES + 1)})
    with pytest.raises(Exception, match="上限"):
        _preview(a, vault_id, "aidc", many)
    monkeypatch.setattr(packages, "MAX_ZIP_BYTES", 1000)
    with pytest.raises(Exception, match="zip 太大"):
        _preview(a, vault_id, "aidc", _zip({"tools/big.py": TOOL * 50}, top="x/") + b" " * 1000)
    monkeypatch.setattr(packages, "MAX_ZIP_BYTES", 20 * 1024 * 1024)
    monkeypatch.setattr(packages, "MAX_TOTAL_BYTES", 2000)
    with pytest.raises(Exception, match="解壓後超過"):
        _preview(a, vault_id, "aidc", _zip({"tools/a.py": TOOL * 20}))
    many_files = [{"path": f"tools/t{n}.py", "text": TOOL} for n in range(packages.MAX_FILES + 1)]
    status, refused = _post(a, vault_id, {"preview": {"home": "aidc", "files": many_files}})
    assert (status, refused["code"]) == (400, "package_invalid")


def test_batches_are_at_most_ten_and_a_token_expires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, vault_id, _dataset, a, _ = _two_pcs(tmp_path)
    files = {f"tools/t{n}.py": TOOL.replace("rows.csv", f"rows{n}.csv") for n in range(12)}
    preview = _preview(a, vault_id, "aidc", _zip(files))
    assert len(preview["items"]) == 12 and preview["batch"] == packages.BATCH
    status, refused = _post(
        a, vault_id, {"apply": {"token": preview["token"],
                                "items": [{"id": i["id"]} for i in preview["items"]]}}
    )  # fmt: skip
    assert (status, refused["code"]) == (400, "package_invalid") and "10" in refused["message"]
    assert len(_apply(a, vault_id, preview)) == 12
    _ok(_post(a, vault_id, {"discard": preview["token"]}))
    status, gone = _post(
        a, vault_id, {"apply": {"token": preview["token"], "items": [{"id": "tool:t1"}]}}
    )
    assert (status, gone["code"]) == (400, "package_expired")
    later = _preview(a, vault_id, "aidc", _zip({"tools/x.py": TOOL}))
    monkeypatch.setattr(packages, "TOKEN_SECONDS", -1)
    status, gone = _post(a, vault_id, {"apply": {"token": later["token"],
                                                 "items": [{"id": "tool:x"}]}})  # fmt: skip
    assert (status, gone["code"]) == (400, "package_expired")


class _Handler:
    """Just enough of Agent Web's request handler for the raw-body routes."""

    def __init__(self, workspace: Path, body: bytes = b"") -> None:
        self.headers = {"Content-Length": str(len(body))}
        self.rfile = io.BytesIO(body)
        runtime = type("R", (), {"layout": type("L", (), {"workspace_root": workspace})()})()
        self.server = type("S", (), {"web": type("W", (), {"runtime": runtime})()})()
        self.sent: list[tuple[int, Any, str]] = []

    def _json(self, status: int, payload: Any) -> None:
        self.sent.append((status, payload, "json"))

    def _refuse_unread(self, status: int, payload: Any) -> None:
        self.sent.append((status, payload, "refused"))

    def _send(self, status: int, body: bytes, kind: str) -> None:
        self.sent.append((status, body, kind))


def test_the_upload_and_export_routes_carry_raw_bytes(tmp_path: Path) -> None:
    from urllib.parse import urlparse

    _, vault_id, _dataset, a, _ = _two_pcs(tmp_path)
    _domain_with_rule_and_tool(a, vault_id)
    export = _Handler(a)
    url = urlparse(f"/api/bi/vaults/{vault_id}/package-export?home=aidc&items=tool:vendor-rows")
    assert bi_cards_api.handle(export, "GET", url)
    status, data, kind = export.sent[0]
    assert (status, kind) == (200, "application/zip")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert sorted(archive.namelist()) == [packages.MANIFEST, "tools/vendor-rows.py"]
    upload = _Handler(a, data)
    url = urlparse(f"/api/bi/vaults/{vault_id}/package-upload?home=wireless&name=x.zip")
    assert bi_cards_api.handle(upload, "POST", url)
    status, payload, _ = upload.sent[0]
    assert status == 200 and payload["items"][0]["status"] == "new"
    big = _Handler(a, b"")
    big.headers["Content-Length"] = str(packages.MAX_ZIP_BYTES + 1)
    url = urlparse(f"/api/bi/vaults/{vault_id}/package-upload?home=aidc")
    assert bi_cards_api.handle(big, "POST", url)
    assert big.sent[0][0] == 413 and big.sent[0][2] == "refused"
    empty = _Handler(a)
    url = urlparse(f"/api/bi/vaults/{vault_id}/package-export?home=wireless")
    bi_cards_api.handle(empty, "GET", url)
    assert empty.sent[0][0] == 400 and empty.sent[0][1]["code"] == "package_empty"
