"""BI vault V10 (owner 2026-10-29; `docs/phases/BI_VAULT.md` §12): per-domain
configuration of one market vault.

The configuration is checked against the dataset's schema, saved with a
revision (a stale save is refused), shared through a vault's change files,
and used: chains are read from node names or lists, the coverage matrix comes
from the domains' segments, and imports take its enum and name aliases. All
data is fictional.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from capabilities.bi_cards import domains, vault
from capabilities.bi_cards.schema import shipped
from capabilities.bi_cards.store import BiStore
from host_runtime.bi_cards_api import route

V2 = "bi.schema/v1.1@2.0.0"


def _call(ws: Path, method: str, path: str, body: Any = None, **query: str) -> Any:
    return route(ws, "tester", method, path, query, body)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _refused(answer: Any, status: int, code: str) -> dict[str, Any]:
    assert (answer[0], answer[1].get("code")) == (status, code), answer
    return dict(answer[1])


CONFIG: dict[str, Any] = {
    "domains": [
        {
            "id": "aidc",  # matched to the schema's spelling, AIDC
            "label": "AI 資料中心",
            "segments": [
                {"id": "aidc-computing", "label": "AIDC Computing", "priority": True},
                {"id": "aidc-power", "label": "AIDC Power"},
            ],
            "chains": [
                {"id": "CMP", "label": "運算鏈", "node_pattern": r"^L\d-CMP-"},
                {"id": "PWR", "label": "電力鏈", "node_pattern": r"^L\d-PWR-"},
                {"id": "THM", "label": "散熱鏈", "nodes": ["L3-PWR-Liquid-Cooling"]},
            ],
            "nodes": ["L1-CMP-Accelerator", "L3-PWR-Liquid-Cooling"],
        },
        {"id": "aerospace", "label": "航太", "segments": [{"id": "space", "label": "Space"}]},
    ],
    "areas": [{"id": "chipset", "label": "晶片"}, {"id": "power-system", "label": "電力系統"}],
    "segment_field": "segment",
    "area_field": "role",
    "name_aliases": {"聯發科": "MediaTek", "L1 加速器": "L1-CMP-Accelerator"},
    "enum_aliases": {"role": {"雲端業者": "hyperscaler"}},
}


def _dataset(ws: Path) -> None:
    _ok(_call(ws, "POST", "/api/bi/datasets", {"name": "market", "schema": V2}))


def _save(ws: Path, config: Any, base: int, dataset: str = "market") -> Any:
    body = {"dataset": dataset, "config": config, "base_revision": base}
    return _call(ws, "POST", "/api/bi/domains", body)


def test_a_configuration_is_checked_saved_with_a_revision_and_read(tmp_path: Path) -> None:
    _dataset(tmp_path)
    empty = _ok(_call(tmp_path, "GET", "/api/bi/domains", dataset="market"))
    assert empty == {
        "dataset": "market", "configured": False, "revision": 0, "config": None, "warnings": [],
    }  # fmt: skip
    saved = _ok(_save(tmp_path, CONFIG, 0))
    assert saved["configured"] is True and saved["revision"] == 1
    assert saved["warnings"] == []  # every segment is an allowed value of 2.0.0's `segment`
    config = saved["config"]
    assert [d["id"] for d in config["domains"]] == ["AIDC", "aerospace"]
    assert config["format"] == domains.FORMAT and config["updated_by"] == "tester via web"
    read = _ok(_call(tmp_path, "GET", "/api/bi/domains", dataset="market"))
    assert read["config"] == config
    _refused(_save(tmp_path, CONFIG, 0), 409, "domains_stale")
    assert _ok(_save(tmp_path, CONFIG, 1))["revision"] == 2
    # A segment the schema cannot hold is saved with a warning, not refused.
    odd = {**CONFIG, "domains": [{"id": "AIDC", "segments": [{"id": "aidc-cooling"}]}]}
    flagged = _ok(_save(tmp_path, odd, 2))["warnings"]
    assert [w["code"] for w in flagged] == ["value_not_allowed"]
    assert "aidc-cooling" in flagged[0]["message"]


def test_an_invalid_configuration_names_what_is_wrong(tmp_path: Path) -> None:
    _dataset(tmp_path)

    def refused(change: Any) -> str:
        config = {**CONFIG, **change}
        return str(_refused(_save(tmp_path, config, 0), 400, "domains_invalid")["message"])

    assert "不在 schema 的 domains" in refused({"domains": [{"id": "marine"}]})
    twice = [
        {"id": "AIDC", "segments": [{"id": "s"}]},
        {"id": "aerospace", "segments": [{"id": "s"}]},
    ]
    assert "出現在兩個領域" in refused({"domains": twice})
    bad_chain = [{"id": "AIDC", "chains": [{"id": "X", "node_pattern": "("}]}]
    assert "不是有效的規則" in refused({"domains": bad_chain})
    empty_chain = [{"id": "AIDC", "chains": [{"id": "X"}]}]
    assert "node_pattern 或 nodes" in refused({"domains": empty_chain})
    assert "不是允許值" in refused({"enum_aliases": {"role": {"雲": "cloud"}}})
    assert "沒有叫" in refused({"enum_aliases": {"colour": {}}})
    assert "areas" in refused({"areas": []})
    _refused(_save(tmp_path, CONFIG, None), 400, "base_revision_missing")  # type: ignore[arg-type]
    assert not _ok(_call(tmp_path, "GET", "/api/bi/domains", dataset="market"))["configured"]


def test_chains_come_from_node_names_or_lists() -> None:
    config = domains.Config(domains.validate(CONFIG, shipped()[1]))
    assert config.chains_of("L2-CMP-Server") == ["CMP"]
    assert config.chains_of("L3-PWR-Liquid-Cooling") == ["PWR", "THM"]  # a shared node
    assert config.chains_of("L2-Antenna-Module") == []
    assert config.chains_of("L2-CMP-Server", "aerospace") == []
    assert config.canon("聯發科") == "MediaTek" and config.canon(" Keysight ") == "Keysight"


def test_the_coverage_matrix_comes_from_the_domains(tmp_path: Path) -> None:
    _dataset(tmp_path)
    before = _ok(_call(tmp_path, "GET", "/api/bi/coverage", dataset="market"))
    assert before["matrix_source"] == "shipped"
    _ok(_save(tmp_path, CONFIG, 0))
    store = BiStore(tmp_path, "market")
    csv = (
        "name,role,segment\n"
        "Fictional Power Co,power-system,aidc-power\n"
        "Fictional Chip Co,chipset,\n"
    )
    preview = _ok(_call(tmp_path, "POST", "/api/bi/import/preview",
                        {"dataset": "market", "entity_type": "Ecosystem", "filename": "e.csv",
                         "csv_text": csv}))  # fmt: skip
    # 2.0.0's `segment` takes the market chart's segments (aidc-power) beside aerospace's.
    assert not any(w["code"] == "type_mismatch" for r in preview["rows"] for w in r["warnings"])
    _ok(_call(tmp_path, "POST", "/api/bi/import/apply", {"preview_id": preview["preview_id"]}))
    report = _ok(_call(tmp_path, "GET", "/api/bi/coverage", dataset="market"))
    assert report["matrix_source"] == "domains"
    assert [m["id"] for m in report["matrix"]["markets"]] == ["AIDC", "aerospace"]
    assert len(report["cells"]) == 3 * 2
    assert report["totals"]["cards"] == 2 and report["totals"]["no_segment"] == 1
    cells = {(c["segment"], c["area"]): c["cards"] for c in report["cells"]}
    assert cells[("aidc-power", "power-system")] == 1  # area_field is role
    assert sum(cells.values()) == 1
    assert store.card_rows()


def test_imports_take_the_configured_name_and_enum_aliases(tmp_path: Path) -> None:
    _dataset(tmp_path)
    _ok(_save(tmp_path, CONFIG, 0))
    csv = "name,role,node\n聯發科,雲端業者,L1 加速器\n"
    preview = _ok(_call(tmp_path, "POST", "/api/bi/import/preview",
                        {"dataset": "market", "entity_type": "Ecosystem", "filename": "e.csv",
                         "csv_text": csv}))  # fmt: skip
    (row,) = preview["rows"]
    assert row["canonical_key"] == "MediaTek"
    values = {f["field"]: f["normalized"] for f in row["fields"]}
    assert values["role"] == "hyperscaler" and values["node"] == "L1-CMP-Accelerator"


def test_a_vault_shares_the_configuration_with_every_pc(tmp_path: Path) -> None:
    a, b = tmp_path / "a" / "ws", tmp_path / "b" / "ws"
    drive_a, drive_b = tmp_path / "a" / "drive", tmp_path / "b" / "drive"
    for folder in (a, b, drive_a, drive_b):
        folder.mkdir(parents=True)
    made = _ok(
        _call(a, "POST", "/api/bi/vaults",
              {"path": str(drive_a), "title": "Market", "purpose": "虛構測試", "schema": V2,
               "author": "alice"})
    )  # fmt: skip
    vault_id = made["vault"]["id"]
    dataset = vault.dataset_name(vault_id)
    _ok(_save(a, CONFIG, 0, dataset))
    # Saved is staged on this PC; a commit with a purpose and a push share it.
    shared_commits = drive_a / vault_id / "commits" / "alice"
    before = len(list(shared_commits.glob("*.json")))
    committed = _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/commit",
                          {"purpose": "Add the AIDC domain"}))  # fmt: skip
    assert committed["commit"]["purpose"] == "Add the AIDC domain"
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/push", {}))
    assert len(list(shared_commits.glob("*.json"))) == before + 1
    shutil.copytree(drive_a / vault_id, drive_b / vault_id)
    _ok(_call(b, "POST", "/api/bi/vaults/join",
              {"path": str(drive_b / vault_id), "author": "bob"}))  # fmt: skip
    shared = _ok(_call(b, "GET", "/api/bi/domains", dataset=dataset))
    assert shared["revision"] == 1 and shared["config"]["domains"][0]["id"] == "AIDC"
    assert _ok(_call(b, "GET", "/api/bi/coverage", dataset=dataset))["matrix_source"] == "domains"
