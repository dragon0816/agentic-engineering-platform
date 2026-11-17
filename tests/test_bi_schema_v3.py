"""BI schema 3.0.0: technology areas, value chains and card aliases as fields (BI D1).

`docs/phases/BI_ANALYSIS_DASHBOARD.md` §3: `tech_areas` (allowed values = the
coverage matrix's areas, labels as aliases) on the types placed by `segment`,
`chain` on Node (the AIDC chains) and `aliases` on every type named by `name`
(read by name matching, D2). 3.0.0 only adds fields, so a 2.0.0
dataset upgrades without moving a value; a bare `bi.schema/v1.1` now means 3.0.0.
All data is fictional.
"""

from __future__ import annotations

import json
from pathlib import Path

from test_bi_schema_v2 import _call, _ok

from aep_bi.cards import catalog, schema_versions
from aep_bi.cards.store import BiStore, PlannedRow
from scripts.build_bi_schema_v3 import OUT, build

V2, V3 = "bi.schema/v1.1@2.0.0", "bi.schema/v1.1@3.0.0"


def test_the_shipped_3_0_0_is_generated_and_only_adds_fields(tmp_path: Path) -> None:
    assert json.loads(OUT.read_text(encoding="utf-8")) == build()
    old, new = catalog.resolve(tmp_path, V2), catalog.resolve(tmp_path, V3)
    changes = schema_versions.diff(old.document, new.document)
    assert {c["change"] for c in changes} == {"field_added"}
    added = sorted((c["type"], c["field"]) for c in changes)
    assert ("Node", "chain") in added and ("Account", "aliases") in added
    assert ("Signal", "aliases") not in added  # named by date and title, not by a name
    assert {t for t, f in added if f == "tech_areas"} == {
        "Account", "CustomerProduct", "Ecosystem", "SupplyLink"}  # fmt: skip
    # Later versions came after, so a bare id no longer means this one (`test_bi_card_model_shape`
    # pins the newest).
    assert catalog.resolve(tmp_path, "bi.schema/v1.1").version != "3.0.0"


def test_labels_are_aliases_of_the_allowed_values(tmp_path: Path) -> None:
    reg = catalog.resolve(tmp_path, V3)
    areas = reg.types["Account"].get("tech_areas")
    chain = reg.types["Node"].get("chain")
    assert areas is not None and chain is not None
    assert reg.normalize(areas, "RF；EMC；Moon")[0] == ["rf", "emc"]
    assert reg.normalize(areas, "Wireless & Comm.")[0] == ["wireless-comm"]
    assert reg.normalize(chain, "運算鏈；PWR")[0] == ["CMP", "PWR"]


def test_a_2_0_0_dataset_upgrades_without_moving_a_value(tmp_path: Path) -> None:
    _ok(_call(tmp_path, "POST", "/api/bi/datasets", {"name": "market", "schema": V2}))
    store = BiStore(tmp_path, "market")
    values = {"name": "L1-CMP-GPU", "domain": ["AIDC"]}
    row = PlannedRow(row=1, entity_type="Node", canonical_key="l1-cmp-gpu", name="L1-CMP-GPU",
                     values=values, synthetic=False)  # fmt: skip
    store.apply([row], filename="n.csv", entity_type="Node", actor="tester")
    path = "/api/bi/datasets/market/schema"
    preview = _ok(_call(tmp_path, "POST", f"{path}/preview", {"to": V3}))
    assert preview["blocked"] == [] and preview["totals"]["widened"] == 0
    _ok(_call(tmp_path, "POST", f"{path}/apply",
              {"to": V3, "preview_token": preview["preview_token"]}))  # fmt: skip
    assert store.schema_ref() == V3
    card = store.find("Node", "l1-cmp-gpu")
    assert card is not None and store.fields(card["id"])["domain"]["value"] == ["AIDC"]
