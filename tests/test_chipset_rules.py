"""The chipset report's rules, against the source's own tests.

Every case in sections 1 to 9 and 11 is the pinned source's, ported case for
case: they are the oracle this migration is measured against, and each was
taken from a real row of the project lists or of the `Chipset_requirement`
sheet. Section 12 is new and covers what this port fixed, each test naming
the defect it would catch coming back.

They need neither Excel nor a workbook. They do need a ruleset, and the one
they use is the shipped default, so several of them are as much assertions
about that file as about the code: the suggested owner for Qualcomm, the four
fill colours, the vendor order, the corrections for `SoftBand` and
`Infenion`. That is the source's arrangement too, and it is honest as long as
it is said out loud.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

import pytest

from capabilities.chipset_report import rules as R
from capabilities.chipset_report.ruleset import ChipsetRuleset, Rules, compile_rules, load_ruleset

WHEN = _dt.date(2026, 7, 28)
HEADERS = list(R.FALLBACK_TARGET_HEADERS)


@pytest.fixture(scope="module")
def rules() -> Rules:
    return compile_rules(load_ruleset())


def altered(ruleset: ChipsetRuleset, **sections: Any) -> Rules:
    """The shipped ruleset with one section replaced. The source's tests
    reached into a mutable dictionary; a ruleset is frozen, so a variant is
    made rather than the original damaged for whatever runs next."""
    return compile_rules(ruleset.model_copy(update=sections))


def names(tokens: list[R.ChipsetToken]) -> list[str]:
    return [token.display for token in tokens]


def row(**fields: Any) -> R.SourceRow:
    base: dict[str, Any] = {
        "fiscal_year": "FY2627",
        "sheet": "Project List",
        "row_number": 2,
        "status": "On-going",
    }
    base.update(fields)
    return R.SourceRow(**base)


# ---------------------------------------------------------------------------
# 1. Splitting the chipset cell
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("QCA6688", ["QCA6688"]),
        ("RTL8852BE", ["RTL8852BE"]),
        ("MT7925", ["MT7925"]),
        ("IPQ9720", ["IPQ9720"]),
        ("MT7996", ["MT7996"]),
        ("MTK7921/7925", ["MT7921", "MT7925"]),
        ("Qualcomm\nWi-Fi 7 QFW7114/7124", ["QFW7114", "QFW7124"]),
        ("QCN-6515,QCN-6563", ["QCN6515", "QCN6563"]),
        ("WiFi: mtk7921+mtk7922, BT: IW416", ["MT7921+MT7922", "IW416"]),
        ("5G: SDX82, Wi-Fi: QFW7114, BT: IW416", ["SDX82", "QFW7114", "IW416"]),
        ("SDX35 (Cellular, NR)", ["SDX35"]),
        ("MT7977+MT7996+MT7988", ["MT7977+MT7996+MT7988"]),
        (
            "QCA: IPQ5322 SoC + QCN6412 RADIO + QCA8384 SWITCH",
            ["IPQ5322 SoC + QCN6412 RADIO + QCA8384 SWITCH"],
        ),
        ("QCN62xx Wakiki \n+ IPQ53xx Miami", ["QCN62xx Wakiki + IPQ53xx Miami"]),
        (
            "MT7987A(SoC)\nMT7992B(BBIC)\nMT7975N(2.4G RFIC)\nMT7979N(5G RFIC)\n",
            ["MT7987A(SoC) + MT7992B(BBIC) + MT7975N(2.4G RFIC) + MT7979N(5G RFIC)"],
        ),
        ("QCA JUHU\nQCA Hermosa", ["QCA JUHU + QCA Hermosa"]),
        ("QCA JUHU solution\n IPQ9620+QCN9575 *3", ["QCA JUHU + IPQ9620+QCN9575"]),
        (
            "Nordique 54L\nMT8371LV +MT6637(Radio front end)",
            ["Nordic54L", "MT8371LV +MT6637(Radio front end)"],
        ),
        ("Qualcomm\nIPQ5424", ["IPQ5424"]),
        (
            "5G/LTE:Qualcomm SDX82\nWi-Fi: Qualcomm QFW7114 \nBT:NXP IW416\nGNSS: STLIV4F",
            ["Qualcomm SDX82", "Qualcomm QFW7114", "NXP IW416", "STLIV4F"],
        ),
        ("QCA IPQ96XX+TRESTLE\n(BBIC+RFIC)", ["QCA IPQ96XX+TRESTLE (BBIC+RFIC)"]),
    ],
)
def test_split_chipsets(rules: Rules, raw: str, expected: list[str]) -> None:
    assert names(R.split_chipsets(raw, rules)) == expected


def test_split_the_big_research_cell(rules: Rules) -> None:
    """One real cell with alternatives separated by `or`, blank lines and a
    sentence of prose in the middle of it."""
    raw = (
        "BRCM4916+6718x3\n or\nQCA IPQ96XX+TRESTLE\n(BBIC+RFIC)\n\nMTK MT7999\n\n"
        "under discussion either all\n\nQM35825\n\nQualcomm SDX35\n"
        "(Wi-Fi 8/ UWB/BLE/NR/LTE/Zigbee)"
    )
    tokens = R.split_chipsets(raw, rules)
    assert names(tokens) == [
        "BCM4916+6718x3",
        "QCA IPQ96XX+TRESTLE (BBIC+RFIC)",
        "MTK MT7999",
        "QM35825",
        "Qualcomm SDX35",
    ]
    assert set(tokens[-1].tech_hint) == {"wifi", "uwb", "bt", "cellular", "zigbee"}


@pytest.mark.parametrize(
    "raw, fragment",
    [("TBC", "placeholder"), ("N/A", "placeholder"), (None, "empty"), ("", "empty")],
)
def test_noise_never_disappears_silently(rules: Rules, raw: Any, fragment: str) -> None:
    tokens = R.split_chipsets(raw, rules)
    assert len(tokens) == 1
    assert tokens[0].unresolved is True
    assert tokens[0].display == "TBD"
    assert fragment in " ".join(tokens[0].warnings)


@pytest.mark.parametrize(
    "raw, display",
    [
        ("Quectel", "Quectel (model TBD)"),
        ("Qualcomm", "Qualcomm (model TBD)"),
        ("Infenion", "Infineon (model TBD)"),
        ("Qualcomm\nWi-Fi 7", "Qualcomm (model TBD)"),
    ],
)
def test_vendor_only_cells_become_flagged_placeholders(
    rules: Rules, raw: str, display: str
) -> None:
    tokens = R.split_chipsets(raw, rules)
    assert len(tokens) == 1
    assert tokens[0].display == display
    assert tokens[0].unresolved is True
    assert any("only a vendor name" in warning for warning in tokens[0].warnings)


def test_multiplicity_suffix_does_not_eat_model_numbers(rules: Rules) -> None:
    """`SDX35` must not be read as `SD` times 35."""
    assert names(R.split_chipsets("Qualcomm SDX35", rules)) == ["Qualcomm SDX35"]
    assert names(R.split_chipsets("IPQ9620+QCN9575 *3", rules)) == ["IPQ9620+QCN9575"]


# ---------------------------------------------------------------------------
# 2. Vendor
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "chipset, vendor",
    [
        ("QCA6688", "Qualcomm"),
        ("QCN6515", "Qualcomm"),
        ("IPQ9720", "Qualcomm"),
        ("QM35825", "Qualcomm"),
        ("Qualcomm SDX35", "Qualcomm"),
        ("QCA JUHU + QCA Hermosa", "Qualcomm"),
        ("QCN62xx Wakiki + IPQ53xx Miami", "Qualcomm"),
        ("MT7925", "MediaTek"),
        ("MTK MT7999", "MediaTek"),
        ("MT8371LV +MT6637(Radio front end)", "MediaTek"),
        ("BCM47722", "Broadcom"),
        ("BCM4916+6718x3", "Broadcom"),
        ("RTL8852BE", "Realtek"),
        ("NXP IW416", "NXP"),
        ("STLIV4F", "STMicroelectronics"),
        ("Nordic54L", "Nordic"),
        ("Intel BE211", "Intel"),
        ("TBD", ""),
    ],
)
def test_infer_vendor(rules: Rules, chipset: str, vendor: str) -> None:
    assert R.infer_vendor(chipset, rules) == vendor


# ---------------------------------------------------------------------------
# 3. Technology
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "chipset, end_products, purpose, expected",
    [
        ("QCA6688", "IVI/TCU", "R&D", ["wifi", "bt"]),
        ("QM35825", "Mobile CPE\nAP", "R&D", ["uwb"]),
        ("Qualcomm SDX82", "FR1 router", "Production", ["cellular"]),
        ("RTL8852BE", "Wi-Fi 6e module", "Production", ["wifi"]),
        ("STLIV4F", "FR1 router", "Production", ["gnss"]),
        ("Nordic54L", "RF board for sports equipment\nBT function", "Prodcution", ["bt"]),
        ("QCA JUHU + QCA Hermosa", "Router", "Production", ["wifi"]),
        (
            "Quectel (model TBD)",
            "FWA:5G+WIFI+BT+thread",
            "R&D",
            ["wifi", "bt", "cellular", "thread"],
        ),
        (
            "Qualcomm (model TBD)",
            "Lora\nupgrade BT+WIFI in Q3",
            "Porduction",
            ["wifi", "bt", "lora"],
        ),
        ("Qualcomm (model TBD)", "industry AP", "R&D", ["TBD"]),
    ],
)
def test_resolve_technologies(
    rules: Rules, chipset: str, end_products: str, purpose: str, expected: list[str]
) -> None:
    token = R.ChipsetToken(display=chipset)
    source = row(chipset_models=chipset, end_products=end_products, purpose=purpose)
    techs, _details, _warnings = R.resolve_technologies(token, source, rules)
    assert techs == R.order_technologies(expected, rules)


def test_an_explicit_label_beats_the_chipset_table(rules: Rules) -> None:
    """`BT:NXP IW416` is bt only, although IW416 also does wifi."""
    raw = "5G/LTE:Qualcomm SDX82\nWi-Fi: Qualcomm QFW7114 \nBT:NXP IW416\nGNSS: STLIV4F"
    source = row(chipset_models=raw, end_products="FR1 router", purpose="Production")
    resolved = {}
    for token in R.split_chipsets(raw, rules):
        techs, _details, _warnings = R.resolve_technologies(token, source, rules)
        resolved[token.display] = techs
    assert resolved == {
        "Qualcomm SDX82": ["cellular"],
        "Qualcomm QFW7114": ["wifi"],
        "NXP IW416": ["bt"],
        "STLIV4F": ["gnss"],
    }


def test_unresolved_technology_is_flagged_not_dropped(rules: Rules) -> None:
    token = R.ChipsetToken(display="QCA Foo")
    source = row(chipset_models="QCA Foo", end_products="Industry AP", purpose="R&D")
    techs, _details, warnings = R.resolve_technologies(token, source, rules)
    assert techs == ["TBD"]
    assert any("could not be resolved" in warning for warning in warnings)


# ---------------------------------------------------------------------------
# 4. Identity and what the sheet already tracks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source_chipset, existing_chipset",
    [
        ("QCA6688", "QCA6688"),
        ("MTK7925", "MT7925"),
        ("BRCM 47722", "BCM47722"),
        ("Nordique 54L", "Nordic54L"),
        ("Qualcomm SDX35", "Qualcomm SDX35"),
        ("Qualcomm SDX82", "SDX82"),
        ("Qualcomm QFW7114", "QFW7114"),
        ("NXP IW416", "IW416"),
        ("Qualcomm IPQ5424", "IPQ5424"),
        ("QCN62xx Wakiki + IPQ53xx Miami", "QCN62xx Wakiki + IPQ53xx Miami"),
        ("QCA IPQ96XX+TRESTLE (BBIC+RFIC)", "QCA IPQ96XX + Trestle (BBIC+RFIC)"),
        (
            "IPQ5322 SoC + QCN6412 RADIO + QCA8384 SWITCH",
            "IPQ5322 SoC + QCN6412 (Pebble) + QCA8384 Switch",
        ),
        (
            "MT7987A(SoC) + MT7992B(BBIC) + MT7975N(2.4G RFIC) + MT7979N(5G RFIC)",
            "MT7987A(SoC) + MT7992B(BBIC) + MT7975N(2.4G) + MT7979N(5G)",
        ),
        ("QCA JUHU + QCA Hermosa", "QCA JUHU + QCA Hermosa (codename)"),
    ],
)
def test_match_key_equal(rules: Rules, source_chipset: str, existing_chipset: str) -> None:
    assert R.match_key(source_chipset, rules) == R.match_key(existing_chipset, rules)


@pytest.mark.parametrize(
    "first, second",
    [
        ("MT7921", "MT7925"),
        ("IPQ9620+QCN9575", "IPQ9670 + QCN9575 (JUHU)"),
        ("QCN6515", "QCN6563"),
        ("IPQ9720", "IPQ9670"),
    ],
)
def test_match_key_differs(rules: Rules, first: str, second: str) -> None:
    assert R.match_key(first, rules) != R.match_key(second, rules)


EXISTING: list[dict[str, Any]] = [
    {
        "chipset": "QM35825",
        "Technology": "uwb",
        "DRI": "Jundong",
        "Status": "Completed",
        "Comments": "3/02:\nWill release at middle of March",
    },
    {
        "chipset": "QCA6688",
        "Technology": "WiFi / BT",
        "DRI": "Kevin Fang",
        "Status": "Not Start",
        "Comments": "2026/7/17:\nWait for DUT",
    },
    {
        "chipset": "Qualcomm SDX35",
        "Technology": "Cellular(RedCap/NTN)",
        "DRI": "Kevin Fang",
        "Status": "Ready for Launch",
        "Comments": "",
    },
    {
        "chipset": "MT7977+MT7996+MT7988",
        "Technology": "wifi",
        "DRI": "Jenny Chen",
        "Status": "Completed",
        "Comments": "",
    },
]


def test_the_matched_row_follows_the_target_header_row(rules: Rules) -> None:
    """The row number has to be one a person can go to.

    The target sheet gained a blank first row for a sort button, so its
    headers moved to row 2 and its data starts at row 3. The records handed
    in look identical either way, because the header is already stripped, so
    nothing downstream notices the shift by itself. Off by one, the number
    still lands on a real row, which is exactly why nobody would report it.
    """
    rows = [row(row_number=3, project_name="V3TA", chipset_models="QCA6688", opp_id="553641")]
    at_one = R.transform(rows, EXISTING, HEADERS, rules, today=WHEN)
    at_two = R.transform(rows, EXISTING, HEADERS, rules, today=WHEN, target_header_row=2)

    first = [r["_MatchedRow"] for r in at_one.records if r["_Match"] == "tracked"]
    second = [r["_MatchedRow"] for r in at_two.records if r["_Match"] == "tracked"]
    assert first, "the fixture must produce a tracked row for this to mean anything"
    assert second == [number + 1 for number in first]


def test_index_existing_splits_combined_technology_cells(rules: Rules) -> None:
    indexed = {entry.chipset: entry for entry in R.index_existing(EXISTING, rules)}
    assert indexed["QCA6688"].technologies == ("wifi", "bt")
    assert indexed["Qualcomm SDX35"].technologies == ("cellular",)
    assert indexed["QM35825"].row_number == 2
    assert indexed["MT7977+MT7996+MT7988"].row_number == 5


@pytest.mark.parametrize(
    "chipset, technology, level, row_number",
    [
        ("QCA6688", "wifi", "tracked", 3),
        ("QCA6688", "bt", "tracked", 3),
        ("Qualcomm SDX35", "cellular", "tracked", 4),
        ("Qualcomm SDX35", "uwb", "tracked-other-tech", 4),
        ("MT7996", "wifi", "partial", 5),
        ("IPQ9720", "wifi", "new", None),
    ],
)
def test_match_against_existing(
    rules: Rules, chipset: str, technology: str, level: str, row_number: int | None
) -> None:
    indexed = R.index_existing(EXISTING, rules)
    agg = R.Aggregate(
        key=(R.match_key(chipset, rules), technology), chipset=chipset, technology=technology
    )
    got_level, got_row = R.match_against_existing(agg, indexed, rules)
    assert got_level == level
    assert (got_row.row_number if got_row else None) == row_number


# ---------------------------------------------------------------------------
# 5. The scalar columns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (7, 7.0),
        ("2\n", 2.0),
        (None, None),
        ("UG", None),
        ("CMP180", None),
        ("N/A", None),
        ("CMP180 x 5", 5.0),
        (2.0, 2.0),
    ],
)
def test_parse_units(value: Any, expected: float | None) -> None:
    assert R.parse_units(value) == expected


@pytest.mark.parametrize(
    "value, iso",
    [
        ("July. 2026", "2026-07-01"),
        ("Jan. 2027", "2027-01-01"),
        ("Dec,2026", "2026-12-01"),
        ("May-2027", "2027-05-01"),
        ("Oct,2026", "2026-10-01"),
        ("Dec , 2026", "2026-12-01"),
        ("Q4-26", "2026-10-01"),
        ("2026/4", "2026-04-01"),
        ("End of Oct.", None),
        ("TBC", None),
        (None, None),
        (_dt.datetime(2026, 5, 1), "2026-05-01"),
    ],
)
def test_parse_schedule(value: Any, iso: str | None) -> None:
    when, _text = R.parse_schedule(value)
    assert (when.isoformat() if when else None) == iso


def test_format_schedule_matches_the_target_convention(rules: Rules) -> None:
    assert R.format_schedule(_dt.date(2026, 7, 1), rules) == "Jul. 2026"
    assert R.format_schedule(None, rules) == ""


@pytest.mark.parametrize(
    "raw, expected", [("H", "High"), ("M", "Moderate"), ("L", "Low"), ("", "")]
)
def test_map_priority(rules: Rules, raw: str, expected: str) -> None:
    assert R.map_priority(raw, rules) == expected


def test_merge_priority_keeps_the_highest(rules: Rules) -> None:
    assert R.merge_priority("Moderate", "High", rules) == "High"
    assert R.merge_priority("High", "Low", rules) == "High"
    assert R.merge_priority("", "Low", rules) == "Low"


# ---------------------------------------------------------------------------
# 6. Companies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("American\nBrand", ["American Brand"]),
        ("SpaceX\nand\nAmazon", ["SpaceX", "Amazon"]),
        (
            "SoftBand\nSagemcom\nNokia\nSpaceX\nDell",
            ["SoftBank", "Sagemcom", "Nokia", "SpaceX", "Dell"],
        ),
        ("N/A\nprimarily target Charter", ["Charter"]),
        ("Orcale", ["Oracle"]),
        ("Cadillac, Jeep, ALFA ROMEO", ["Cadillac", "Jeep", "ALFA ROMEO"]),
        ("N/A", []),
        (None, []),
    ],
)
def test_split_companies_brand(rules: Rules, raw: Any, expected: list[str]) -> None:
    assert R.split_companies(raw, rules, "brand") == expected


def test_split_companies_mfg(rules: Rules) -> None:
    assert R.split_companies("Foxconn-FIH", rules, "mfg") == ["Foxconn"]
    assert R.split_companies("Quanta", rules, "mfg") == ["Quanta"]


def test_join_companies_uses_newlines_like_the_target(rules: Rules) -> None:
    assert R.join_companies(["Eero", "Netgear", "Eero"], rules) == "Eero\nNetgear"


# ---------------------------------------------------------------------------
# 7. Aggregation
# ---------------------------------------------------------------------------


def test_aggregate_merges_projects_on_chipset_and_technology(rules: Rules) -> None:
    rows = [
        row(
            row_number=4,
            brand="Waymo",
            mfg="Quanta",
            chipset_models="MTK7921/7925",
            end_products="IVI",
            purpose="Prodcution",
            units=3,
            schedule="Jan. 2027",
            opp_id="519452",
            priority="M",
        ),
        row(
            row_number=21,
            brand="HP",
            mfg="WNC",
            project_name="7925",
            chipset_models="MT7925",
            end_products="Wi-Fi 6e module",
            purpose="Production",
            units=2,
            schedule="Dec, 2026",
            opp_id="517782",
            priority="H",
        ),
    ]
    aggregates, _dropped = R.aggregate(rows, rules)
    by_key = {(agg.chipset, agg.technology): agg for agg in aggregates}
    merged = by_key[("MT7925", "wifi")]
    assert merged.brands == ["Waymo", "HP"]
    assert merged.mfgs == ["Quanta", "WNC"]
    assert merged.units_total == 5
    assert merged.priority == "High"
    assert merged.schedule_date == _dt.date(2026, 12, 1), "the earliest date wins"
    assert merged.opp_ids == ["519452", "517782"]
    assert ("MT7921", "wifi") in by_key, "the alternative is kept"


def test_units_are_not_double_counted_across_fiscal_years(rules: Rules) -> None:
    """Both fiscal years list the same project, so it is two units and not
    four."""
    rows = [
        row(
            fiscal_year=year,
            row_number=3,
            brand="RVT",
            mfg="Quanta",
            project_name="V3TA",
            chipset_models="QCA6688",
            units=2,
            schedule="Jan. 2027",
            opp_id="553641",
            priority="M",
        )
        for year in ("FY2627", "FY2526")
    ]
    aggregates, _dropped = R.aggregate(rows, rules)
    by_key = {(agg.chipset, agg.technology): agg for agg in aggregates}
    assert by_key[("QCA6688", "wifi")].units_total == 2
    assert by_key[("QCA6688", "bt")].units_total == 2
    assert by_key[("QCA6688", "wifi")].fiscal_years == ["FY2627", "FY2526"]


def undecided_rows() -> list[R.SourceRow]:
    return [
        row(
            row_number=2,
            brand="BMW",
            mfg="Quanta",
            project_name="V28 / V28A",
            chipset_models="TBC",
            end_products=" BMW-IVI",
            units=7,
            opp_id="1085846",
        ),
        row(
            row_number=13,
            brand="SoftBand\nNokia",
            mfg="Foxconn",
            project_name="Rental Business",
            chipset_models="N/A",
            units=20,
            opp_id="566155",
        ),
    ]


def test_undecided_chipsets_are_left_out_of_the_report(rules: Rules) -> None:
    """A chipset nobody has chosen does not belong in a report about chipset
    requirements. `TBC`, `N/A` and a bare vendor name all mean not decided,
    so they produce no row rather than one somebody filters out by hand."""
    aggregates, _dropped = R.aggregate(undecided_rows(), rules)
    assert aggregates == []
    vendor_only = [
        row(chipset_models="Qualcomm", opp_id="1"),
        row(chipset_models="Quectel", opp_id="2"),
    ]
    named_only, _ = R.aggregate(vendor_only, rules)
    assert named_only == []


def test_dropped_chipsets_are_reported_not_silently_lost(rules: Rules) -> None:
    """A missing project needs a reason."""
    result = R.transform(undecided_rows(), [], HEADERS, rules, today=WHEN)
    assert result.records == ()
    assert len(result.dropped) == 2
    assert {item.reason for item in result.dropped} == {R.PLACEHOLDER_REASON}
    assert {item.raw for item in result.dropped} == {"TBC", "N/A"}
    assert all(item.row_number for item in result.dropped)


def test_unresolved_rows_do_not_merge_across_projects(rules: Rules) -> None:
    """The no-merge guarantee holds even when dropping is switched off: one
    project's undecided chipset is not another's."""
    keeping = altered(
        rules.ruleset,
        split=rules.ruleset.split.model_copy(
            update={"drop_placeholders": False, "drop_vendor_only": False}
        ),
    )
    aggregates, _dropped = R.aggregate(undecided_rows(), keeping)
    assert len(aggregates) == 2
    assert {agg.units_total for agg in aggregates} == {7.0, 20.0}


def test_status_filter_excludes_lost_by_default(rules: Rules) -> None:
    assert R.row_is_included(row(status="On-going"), None, ["Lost"]) is True
    assert R.row_is_included(row(status="WON"), None, ["Lost"]) is True
    assert R.row_is_included(row(status=""), None, ["Lost"]) is True
    assert R.row_is_included(row(status="Lost"), None, ["Lost"]) is False
    assert R.row_is_included(row(status="WON"), ["On-going"], ["Lost"]) is False


# ---------------------------------------------------------------------------
# 8. Rendering
# ---------------------------------------------------------------------------


def test_render_row_shape_and_traceability(rules: Rules) -> None:
    rows = [
        row(
            row_number=3,
            brand="RVT",
            mfg="Quanta",
            project_name="V3TA",
            chipset_models="QCA6688",
            end_products="IVI/TCU",
            units=2,
            schedule="Jan. 2027",
            opp_id="553641",
            priority="M",
        )
    ]
    result = R.transform(rows, EXISTING, HEADERS, rules, today=WHEN)
    assert result.rows_generated == 2, "wifi and bt"
    record = next(r for r in result.records if r["Technology"] == "wifi")
    assert list(record)[: len(HEADERS)] == HEADERS, "the sheet's own headers, in its own order"
    assert record["Chipset Vendor"] == "Qualcomm"
    assert record["chipset"] == "QCA6688"
    assert record["Brand"] == "RVT"
    assert record["MFG"] == "Quanta"
    assert record["Protential Biz"] == 2
    assert record["Purchased Schedule"] == "Jan. 2027"
    assert record["Piority "] == "Moderate"
    # What people keep by hand is never overwritten.
    assert record["DRI"] == "Kevin Fang"
    assert record["Status"] == "Not Start"
    assert "2026/7/17:\nWait for DUT" in record["Comments"]
    assert record["Comments"].startswith("[W1-TRACE 2026-07-28]")
    assert "FY2627!Project List!R3" in record["Comments"]
    assert "opp=553641" in record["Comments"]
    assert record["_Match"] == "tracked"
    assert record["_MatchedRow"] == 3
    assert record["_SourceFY"] == "FY2627"
    assert record["_SourceProjects"] == "V3TA"
    assert record["_SourceOPPIDs"] == "553641"
    assert record["_RawChipsetText"] == "QCA6688"


def test_the_trace_block_is_line_parseable_even_with_multiline_names(rules: Rules) -> None:
    rows = [
        row(
            row_number=15,
            brand="R&D Use",
            mfg="Foxconn",
            project_name="TBD\n(WiFi 8 project)",
            chipset_models="MTK MT7999\n",
            end_products="Mobile CPE\nAP",
            purpose="R&D",
            units=1,
            opp_id="531243",
        ),
        row(
            fiscal_year="FY2526",
            sheet="Project List_Sales update",
            row_number=15,
            brand="R&D Use",
            mfg="Foxconn",
            project_name="TBD\n(WiFi 8 project)",
            chipset_models="MTK MT7999",
            end_products="Mobile CPE\nAP",
            purpose="R&D",
            units=1,
            opp_id="",
        ),
    ]
    result = R.transform(rows, [], HEADERS, rules, today=WHEN)
    lines = result.records[0]["Comments"].split("\n")
    assert lines == [
        "[W1-TRACE 2026-07-28]",
        "FY2627!Project List!R15 | project=TBD / (WiFi 8 project) | opp=531243",
        "FY2526!Project List_Sales update!R15 | project=TBD / (WiFi 8 project) | opp=-",
        "raw=MTK MT7999",
    ]
    for line in lines[1:-1]:
        assert line.count(" | ") == 2, "three fields, so the block stays parseable"


def test_new_rows_get_a_suggested_owner_and_a_default_status(rules: Rules) -> None:
    rows = [
        row(
            brand="CISCO",
            mfg="Foxconn",
            project_name="TBC",
            chipset_models="IPQ9720",
            end_products="Industry AP",
            units=4,
            schedule="May-2027",
            priority="H",
        )
    ]
    record = R.transform(rows, EXISTING, HEADERS, rules, today=WHEN).records[0]
    assert record["_Match"] == "new"
    assert record["Status"] == "Not Start"
    assert record["DRI"] == "Kevin Fang", "suggested by vendor"
    assert record["Purchased Schedule"] == "May. 2027"


def test_the_unknown_business_marker(rules: Rules) -> None:
    rows = [
        row(
            brand="Eero",
            mfg="Pegatron",
            chipset_models="QCN-6515",
            end_products="WIFI8",
            units="UG",
        )
    ]
    assert R.transform(rows, [], HEADERS, rules, today=WHEN).records[0]["Protential Biz"] == "UG"
    rows = [
        row(
            brand="Eero",
            mfg="Pegatron",
            chipset_models="QCN-6515",
            end_products="WIFI8",
            units=None,
        )
    ]
    assert R.transform(rows, [], HEADERS, rules, today=WHEN).records[0]["Protential Biz"] == "?"


def test_row_colours(rules: Rules) -> None:
    assert R.row_colour({"_Match": "tracked", "_Warnings": ""}, rules) == "#E2EFDA"
    assert R.row_colour({"_Match": "partial", "_Warnings": ""}, rules) == "#DDEBF7"
    assert R.row_colour({"_Match": "new", "_Warnings": ""}, rules) == "#FFF2CC"
    assert (
        R.row_colour({"_Match": "new", "_Warnings": R.UNRESOLVED_TECHNOLOGY}, rules) == "#FCE4D6"
    ), "a technology nobody could work out is the more useful thing to say"


def test_vendor_display_group_first(rules: Rules) -> None:
    records = [
        {"Chipset Vendor": "Qualcomm"},
        {"Chipset Vendor": "Qualcomm"},
        {"Chipset Vendor": "MediaTek"},
    ]
    grouped = altered(
        rules.ruleset,
        output=rules.ruleset.output.model_copy(update={"vendor_display": "groupFirst"}),
    )
    R.apply_vendor_display(records, ["Chipset Vendor"], grouped)
    assert [record["Chipset Vendor"] for record in records] == ["Qualcomm", "", "MediaTek"]


def test_transform_output_is_sorted_by_vendor_then_chipset(rules: Rules) -> None:
    rows = [
        row(row_number=2, chipset_models="RTL8852BE", end_products="Wi-Fi 6e module"),
        row(row_number=3, chipset_models="MT7996", end_products="IF board"),
        row(row_number=4, chipset_models="IPQ9720", end_products="Industry AP"),
    ]
    result = R.transform(rows, [], HEADERS, rules, today=WHEN)
    assert [record["Chipset Vendor"] for record in result.records] == [
        "Qualcomm",
        "MediaTek",
        "Realtek",
    ], "the ruleset's order, not the alphabet's and not the input's"


# ---------------------------------------------------------------------------
# 9. Reading a row whatever the workbook calls its columns
# ---------------------------------------------------------------------------


def test_source_row_reads_the_real_multiline_headers() -> None:
    record = {
        "Brand": "RVT",
        "MFG": "Quanta",
        "Project Name": "V3TA",
        "Chipset models": "QCA6688",
        "End-Products": "IVI/TCU",
        "Purpose": "R&D ",
        "Project stage\n(RD/EVT/DVT/MP)": "EVT",
        "Potential Biz\n(Units)": 2,
        "\nOI (EUR K)": 100,
        "Purchased \nSchedule\n(M/Y)": "Jan. 2027",
        "OPP ID": 553641,
        "Prority": "M",
        "Status\n(Won/On-going/Lost)": "On-going",
    }
    parsed = R.SourceRow.from_record(record, "FY2526", "Project List_Sales update", 3)
    assert parsed.brand == "RVT"
    assert parsed.chipset_models == "QCA6688"
    assert parsed.units == 2, "kept as the number the cell held"
    assert parsed.schedule == "Jan. 2027"
    assert parsed.opp_id == "553641"
    assert parsed.priority == "M"
    assert parsed.status == "On-going"
    assert parsed.purpose == "R&D"


def test_the_other_fiscal_years_header_variant_also_works() -> None:
    """One year drops the suffixes the other carries."""
    record = {
        "Brand": "BMW",
        "MFG": "Quanta",
        "Chipset models": "TBC",
        "Potential Biz\n(Units)": 7,
        "Purchased \nSchedule": "July. 2026",
        "Prority": "H",
        "Status\n(Won/On-going/Lost)": "On-going",
    }
    parsed = R.SourceRow.from_record(record, "FY2627", "Project List", 2)
    assert parsed.units == 7
    assert parsed.schedule == "July. 2026"


# ---------------------------------------------------------------------------
# 11. The cells this run would change
# ---------------------------------------------------------------------------


def test_a_watched_field_that_moved_is_named(rules: Rules) -> None:
    """The question each week is not whether a row is known. It is: this row
    is tracked, so what is different this time."""
    assert R.watched_but_missing(["Purchased Schedule", "Protential Biz"], rules) == []


def test_a_watch_that_covers_no_column_is_reported(rules: Rules) -> None:
    """A misspelt watch field produces no error and no highlight, which reads
    exactly like a week in which nothing changed."""
    assert R.watched_but_missing(["Chipset Vendor", "chipset"], rules) == [
        "Purchased Schedule",
        "Protential Biz",
    ]


def test_the_spelling_in_the_workbook_is_the_one_that_matches() -> None:
    """Case and spacing fold; spelling does not. The sheet says `Protential
    Biz`, so a rule saying `Potential Biz` watches nothing at all."""
    assert R.match_header(["Protential Biz"], "protential  biz") == "Protential Biz"
    assert R.match_header(["Protential Biz"], "Potential Biz") == ""


def test_watch_fields_are_configurable(rules: Rules) -> None:
    """Sales adding a third column they edit by hand is not a code change."""
    watching = altered(
        rules.ruleset, output=rules.ruleset.output.model_copy(update={"watch_fields": ("Status",)})
    )
    assert watching.watch_fields == ("Status",)
    assert rules.watch_fields == ("Purchased Schedule", "Protential Biz")


def test_a_new_row_marks_nothing_as_changed(rules: Rules) -> None:
    """Every value on a new row differs from nothing, so marking them all
    would say nothing at all."""
    headers = ["chipset", "Purchased Schedule", "Protential Biz"]
    agg = R.Aggregate(key=("x", "wifi"), chipset="X", technology="WiFi", vendor="V")
    record = R.render_row(agg, "new", None, headers, rules, WHEN)
    assert record["_Changed"] == ""


def test_changed_travels_with_the_other_trace_columns() -> None:
    """It is written to the sheet, so it has to be one of its headers."""
    assert "_Changed" in R.TRACE_HEADERS


# ---------------------------------------------------------------------------
# 12. What this port fixed
# ---------------------------------------------------------------------------


def test_technology_order_is_the_same_in_every_process(rules: Rules) -> None:
    """The source ordered anything outside the canonical list by iterating a
    set, so its output moved between processes. A plan that differs run to
    run is not evidence of anything."""
    assert R.order_technologies(["zz", "wifi", "aa", "bt"], rules) == ["wifi", "bt", "zz", "aa"]
    assert R.order_technologies(["aa", "zz"], rules) == ["aa", "zz"]


def test_two_runs_in_one_process_do_not_share_their_dropped_rows(rules: Rules) -> None:
    """The source hung the dropped rows on the function object, so a second
    run read back whatever the first had left there."""
    first, first_dropped = R.aggregate(undecided_rows(), rules)
    second, second_dropped = R.aggregate([row(chipset_models="QCA6688")], rules)
    assert first == [] and len(first_dropped) == 2
    assert second and second_dropped == []


def test_an_impossible_month_is_text_rather_than_a_crash() -> None:
    """The source handed month 13 straight to the calendar, which raised. On
    this platform that is a step that failed with nothing to say, where every
    other unparseable schedule is simply text."""
    when, text = R.parse_schedule("2026/13")
    assert when is None
    assert text == "2026/13"
    assert R.parse_schedule("2026/0")[0] is None
    assert R.parse_schedule("2026/12")[0] == _dt.date(2026, 12, 1)


def test_the_month_name_does_not_follow_the_machines_language(rules: Rules) -> None:
    """`%b` is the host's locale. On a non-English Windows the whole column
    would change language and stop matching what is already in the sheet."""
    import locale

    try:
        locale.setlocale(locale.LC_TIME, "German_Germany.1252")
    except locale.Error:  # pragma: no cover - the locale is not installed here
        pytest.skip("no German locale on this machine")
    try:
        assert R.format_schedule(_dt.date(2026, 3, 1), rules) == "Mar. 2026"
    finally:
        locale.setlocale(locale.LC_TIME, "C")


def test_a_keyword_written_with_a_space_matches_only_what_it_means(rules: Rules) -> None:
    """The source built this pattern with two chained replacements, the
    second rewriting what the first inserted, which left a character class
    that also matched `wi[fi`."""
    assert R.find_technologies("wi fi module", rules) == ["wifi"]
    assert R.find_technologies("wi-fi module", rules) == ["wifi"]
    assert R.find_technologies("wifi module", rules) == ["wifi"]
    assert R.find_technologies("wi[fi module", rules) == []
    assert R.find_technologies("wi]fi module", rules) == []
