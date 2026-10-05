"""Content rules for the NCC improvement-plan job.

Copied from rs_workflow_system@896046e host-bridge/tests/test_ncc_rules.py as
the parity oracle for `capabilities.ncc_plan.rules`; only the import path
changed. Seven tests about the job body (draft, verdict, output folder, Word
lock, dry-run switch, upload control) are re-expressed against the AEP
Workflow in tests/test_rs_w14_ncc_plan.py.

Pure functions, so none of this needs Word, a docx, or the Bridge. The numbers
are taken from the two real example plans: if a change here breaks one of these,
the document it produces stops matching the ones the customer has already seen.
"""

from __future__ import annotations

import pytest

from capabilities.ncc_plan.rules import (
    JobError,
    authority_line,
    channel_sentence,
    display_name,
    fault_lines,
    normalise_item,
    parse_selection,
    photo_names,
    plan_lines,
    prefer_spelling,
    price_of,
    selection_from_ticks,
    service_area,
    service_for,
    service_rows,
    split_coverage,
    system_rows_from_ticks,
)

# The four services and prices 公館站's plan actually lists.
PRICES = [
    {"item": "5瓦(含以上及以下)(各頻道)發射/補隙系統變調變錯誤比改善服", "unitPrice": 299000},
    {"item": "訊號放大器系統增益改善服務", "unitPrice": 125000},
    {"item": "混頻系統(6頻道)調變錯誤比改善服務", "unitPrice": 99450},
    {"item": "DVB-T接收/發射天線(單一方向)性能改善服務", "unitPrice": 95000},
    {"item": "25瓦(含以上)(各頻道)發射/補隙系統調變錯誤比改善服務", "unitPrice": 338500},
]


# --------------------------------------------------------------------------
# split_coverage: the population is buried in the area text
# --------------------------------------------------------------------------


def test_the_population_comes_out_of_the_coverage_text() -> None:
    area, population = split_coverage("平溪區十分里、望古里等【約1,331人】")
    assert population == 1331
    assert "【" not in area and "人】" not in area


def test_the_thousands_separator_does_not_reach_the_number() -> None:
    _, population = split_coverage("新竹縣市地區【約980,112人】")
    assert population == 980112


def test_a_blank_coverage_yields_no_population_rather_than_zero() -> None:
    """Zero people would be a claim; None is the absence of one."""
    area, population = split_coverage("")
    assert area == "" and population is None


# --------------------------------------------------------------------------
# authority_line: the two columns overlap
# --------------------------------------------------------------------------


def test_the_township_is_not_repeated() -> None:
    """位置 already contains it, so joining the columns says it twice."""
    assert authority_line("臺東縣綠島鄉", "綠島鄉公所") == "臺東縣政府綠島鄉公所"


def test_a_county_government_is_left_alone() -> None:
    """Prefixing would give 連江縣政府連江縣政府."""
    assert authority_line("連江縣北竿鄉", "連江縣政府") == "連江縣政府"


def test_a_municipality_works_the_same_way() -> None:
    assert authority_line("新北市平溪區", "平溪區公所") == "新北市政府平溪區公所"


# --------------------------------------------------------------------------
# service_area and spelling
# --------------------------------------------------------------------------


def test_the_county_is_prepended_to_the_area() -> None:
    assert service_area("臺東縣綠島鄉", "綠島鄉公館村") == "臺東縣綠島鄉公館村"


def test_an_area_that_already_names_the_county_is_not_doubled() -> None:
    assert service_area("花蓮縣壽豐鄉", "花蓮縣壽豐鄉鹽寮村") == "花蓮縣壽豐鄉鹽寮村"


def test_the_two_spellings_of_tai_are_reconciled() -> None:
    """The station table writes 臺東縣; every example plan writes 台東縣."""
    assert prefer_spelling("臺東縣政府綠島鄉公所", {"臺東縣": "台東縣"}) == "台東縣政府綠島鄉公所"


# --------------------------------------------------------------------------
# parse_selection
# --------------------------------------------------------------------------


def test_a_selection_parses_into_names_and_quantities() -> None:
    assert parse_selection("甲:6,乙:1") == [("甲", 6), ("乙", 1)]


def test_a_service_with_no_quantity_means_one() -> None:
    assert parse_selection("訊號放大器系統增益改善服務") == [("訊號放大器系統增益改善服務", 1)]


def test_a_name_containing_a_colon_keeps_it() -> None:
    """The quantity is after the *last* colon, and these names carry brackets
    and slashes already."""
    assert parse_selection("GPS接收天線(供3頻道以上使用):2") == [("GPS接收天線(供3頻道以上使用)", 2)]  # noqa: E501 - oracle text kept as the source wrote it


def test_zero_is_dropped_rather_than_written_as_a_zero_row() -> None:
    assert parse_selection("甲:0,乙:2") == [("乙", 2)]


def test_choosing_nothing_is_refused() -> None:
    with pytest.raises(JobError):
        parse_selection("")


def test_a_quantity_that_is_not_a_number_is_named() -> None:
    with pytest.raises(JobError) as excinfo:
        parse_selection("甲:many")
    assert "many" in str(excinfo.value)


# --------------------------------------------------------------------------
# money: these totals are on documents the customer has seen
# --------------------------------------------------------------------------


def test_the_gongguan_total_matches_the_real_plan() -> None:
    selection = parse_selection(
        "5瓦(含以上及以下)(各頻道)發射/補隙系統變調變錯誤比改善服:6,"
        "訊號放大器系統增益改善服務:1,"
        "混頻系統(6頻道)調變錯誤比改善服務:1,"
        "DVB-T接收/發射天線(單一方向)性能改善服務:1")
    rows, total = service_rows(selection, PRICES, {}, "115/09/30")
    assert total == 2113450          # the figure printed in 公館站's plan
    assert rows[0][3] == "1,794,000"  # 299,000 x 6
    assert rows[-1][1] == "總計"


def test_the_sitiaogou_total_matches_too() -> None:
    selection = parse_selection("25瓦(含以上)(各頻道)發射/補隙系統調變錯誤比改善服務:2")
    _, total = service_rows(selection, PRICES, {}, "115/09/30")
    assert total == 677000


def test_a_service_with_no_price_is_refused_not_counted_as_zero() -> None:
    """A total silently short by one line is worse than no document."""
    with pytest.raises(JobError) as excinfo:
        price_of("不存在的服務", PRICES)
    assert "不存在的服務" in str(excinfo.value)


def test_the_price_list_wording_is_matched_through_the_pdf_line_wrapping() -> None:
    """The PDF wraps names mid-word, so the same service is spelled two ways."""
    assert price_of("混頻系統 (6頻道) 調變錯誤比改善服務", PRICES) == 99450
    assert normalise_item("混頻系統（6頻道）") == "混頻系統(6頻道)"


def test_the_schedule_shows_the_document_name_not_the_contract_name() -> None:
    selection = parse_selection("25瓦(含以上)(各頻道)發射/補隙系統調變錯誤比改善服務:2")
    names = {"25瓦(含以上)(各頻道)發射/補隙系統調變錯誤比改善服務": "25W發射系統調變錯誤比改善服務"}
    rows, _ = service_rows(selection, PRICES, {}, "115/09/30", names=names)
    assert rows[0][1] == "25W發射系統調變錯誤比改善服務"


# --------------------------------------------------------------------------
# the two tables have to agree
# --------------------------------------------------------------------------


SYSTEMS = [
    {"n": 1, "system": "發射/補隙系統", "field": "transmitter", "perChannel": True,
     "serviceByPower": {"5W": "5瓦(含以上及以下)(各頻道)發射/補隙系統變調變錯誤比改善服",
                        "25W": "25瓦(含以上)(各頻道)發射/補隙系統調變錯誤比改善服務"}},
    {"n": 2, "system": "訊號放大器系統", "field": "amplifier",
     "service": "訊號放大器系統增益改善服務"},
    {"n": 3, "system": "空調系統", "field": "aircon", "service": "空調系統恆溫品質改善服務"},
]


def test_the_table_lists_every_system_whether_ticked_or_not() -> None:
    """表一 is the same rows on every plan; only the box changes."""
    rows = system_rows_from_ticks(SYSTEMS, {"amplifier": True})
    assert [r[1] for r in rows] == ["發射/補隙系統", "訊號放大器系統", "空調系統"]
    assert rows[0][2] == "■正常□待改善"
    assert rows[1][2] == "□正常■待改善"


def test_a_tick_selects_its_priced_service() -> None:
    picked = selection_from_ticks(SYSTEMS, {"amplifier": True}, 6, "5W")
    assert picked == [("訊號放大器系統增益改善服務", 1)]


def test_per_channel_services_take_the_channel_count() -> None:
    """公館站: 5W x 6 channels. 四條溝站: 25W x 2. Measured, not assumed."""
    picked = selection_from_ticks(SYSTEMS, {"transmitter": True}, 6, "5W")
    assert picked[0][1] == 6
    picked = selection_from_ticks(SYSTEMS, {"transmitter": True}, 2, "25W")
    assert picked[0][1] == 2


def test_the_wattage_decides_which_transmitter_service_is_billed() -> None:
    """One tick, two prices -- the station's power is what separates them."""
    assert "5瓦" in selection_from_ticks(SYSTEMS, {"transmitter": True}, 6, "5W")[0][0]
    assert "25瓦" in selection_from_ticks(SYSTEMS, {"transmitter": True}, 2, "25W")[0][0]


def test_an_unpriced_wattage_is_refused_by_name() -> None:
    with pytest.raises(JobError) as excinfo:
        selection_from_ticks(SYSTEMS, {"transmitter": True}, 6, "7W")
    assert "7W" in str(excinfo.value)


def test_ticking_nothing_is_refused() -> None:
    with pytest.raises(JobError):
        selection_from_ticks(SYSTEMS, {}, 6, "5W")


def test_the_ticks_keep_the_table_order() -> None:
    picked = selection_from_ticks(SYSTEMS, {"aircon": True, "transmitter": True}, 2, "25W")
    assert "25瓦" in picked[0][0] and picked[1][0] == "空調系統恆溫品質改善服務"


def test_service_for_names_the_system_when_nothing_is_configured() -> None:
    with pytest.raises(JobError) as excinfo:
        service_for({"system": "穩壓系統"}, "5W")
    assert "穩壓系統" in str(excinfo.value)


# --------------------------------------------------------------------------
# the numbered sections follow the selection
# --------------------------------------------------------------------------


def test_the_plan_section_is_numbered_in_full_width_and_continues_from_one() -> None:
    selection = parse_selection("甲:2,乙:1")
    lines = plan_lines(selection, {"甲": "甲壞了({channels}頻道)。", "乙": "乙壞了。"},
                       6, "保固說明。")
    assert lines[0].startswith("（二）") and "6頻道" in lines[0]
    assert lines[1].startswith("（三）")
    assert lines[2] == "（四）保固說明。"


def test_a_service_with_no_template_does_not_leave_a_gap_in_the_numbering() -> None:
    selection = parse_selection("甲:1,無範本:1,乙:1")
    lines = plan_lines(selection, {"甲": "A。", "乙": "B。"}, 2, "")
    assert [l[:3] for l in lines] == ["（二）", "（三）"]  # noqa: E741 - as the source wrote it


def test_one_fault_caption_per_channel() -> None:
    selection = parse_selection("甲:2")
    captions = fault_lines(selection, ["CH26", "CH28"], {"甲": "甲({channel})故障。"})
    assert captions == ["甲(CH26)故障。", "甲(CH28)故障。"]


def test_the_channel_sentence_counts_what_the_station_broadcasts() -> None:
    text = channel_sentence(["CH24", "CH26"], {"CH24": "中視", "CH26": "公視"}, 23)
    assert "CH24中視、CH26公視" in text
    assert "共2頻道23個" in text


def test_the_expected_photos_are_the_exterior_plus_one_per_channel() -> None:
    assert photo_names(["CH24", "CH26"]) == ["外觀", "CH24", "CH26"]


def test_display_name_falls_back_to_the_contract_wording() -> None:
    assert display_name("未對應的服務", {}) == "未對應的服務"


# --------------------------------------------------------------------------
# preview: what a dry run shows somebody who cannot read the code
# --------------------------------------------------------------------------


STATION = {"station": "東清站", "authority": "蘭嶼鄉公所",
           "builtYear": "100", "population": 1654}


def _preview(**over):
    from capabilities.ncc_plan.rules import preview
    selection = parse_selection("25瓦(含以上)(各頻道)發射/補隙系統調變錯誤比改善服務:2")
    rows, total = service_rows(selection, PRICES, {}, "115/09/30")
    kw = dict(station=STATION, area="台東縣蘭嶼鄉東清村", out_name="x.docx",
              selection=selection, rows=rows, total=total,
              channels=["CH26"], service_channels=["CH24", "CH26"],
              systems=[{"system": "發射系統"}], unmatched=[], missing_photos=[])
    kw.update(over)
    return "\n".join(preview(**kw))


def test_the_preview_survives_a_big5_console() -> None:
    """The CLI prints this on a cp950 console, and an unencodable character
    kills the job at the moment it has something to say -- which is how the
    warning sign was found."""
    _preview().encode("cp950")


def test_it_states_the_station_the_money_and_the_filename() -> None:
    text = _preview()
    assert "東清站" in text and "1,654" in text
    assert "677,000" in text
    assert "x.docx" in text


def test_it_separates_the_channels_broadcast_from_the_ones_improved() -> None:
    """Conflating them understated 四條溝站, which carries six and fixes two."""
    text = _preview()
    assert "涵蓋 2 個頻道" in text and "這次改善 1 個" in text


def test_a_mismatch_between_the_two_tables_is_spelled_out() -> None:
    text = _preview(unmatched=["訊號放大器系統增益改善服務"])
    assert "【注意】" in text
    assert "兩張表會對不上" in text
    assert "訊號放大器系統增益改善服務" in text


def test_no_warning_block_when_the_tables_agree() -> None:
    assert "【注意】" not in _preview(unmatched=[])


def test_it_says_plainly_that_nothing_was_written() -> None:
    assert "還沒寫任何檔案" in _preview()


def test_missing_photos_are_listed_rather_than_counted_only() -> None:
    text = _preview(missing_photos=["外觀", "CH26"])
    assert "缺 2 張" in text and "外觀" in text


def test_a_station_with_no_population_says_so_instead_of_zero() -> None:
    text = _preview(station={**STATION, "population": None})
    assert "人口數不詳" in text


# --------------------------------------------------------------------------
# delivery: how the finished document reaches a person
# --------------------------------------------------------------------------




# --------------------------------------------------------------------------
# dates: one format to type, two to print
# --------------------------------------------------------------------------


@pytest.mark.parametrize("typed", ["115/06/07", "115-06-07", "115.6.7", "115年6月7日"])
def test_the_same_date_is_accepted_however_it_is_typed(typed: str) -> None:
    """The form asked for 115年6月7日 in one box and 115/09/30 in the other,
    which is the document's two formats leaking onto the person filling it in."""
    from capabilities.ncc_plan.rules import date_in_words
    assert date_in_words(typed) == "115年6月7日"


def test_the_sentence_gets_words_and_the_table_gets_slashes() -> None:
    """三、（一） reads 「…115年9月30日確認…」; 表四's column reads 115/09/30."""
    from capabilities.ncc_plan.rules import date_in_slashes, date_in_words
    assert date_in_words("115/09/30") == "115年9月30日"
    assert date_in_slashes("115年9月30日") == "115/09/30"


def test_the_table_column_is_zero_padded() -> None:
    from capabilities.ncc_plan.rules import date_in_slashes
    assert date_in_slashes("115/6/7") == "115/06/07"


def test_text_that_is_not_a_date_is_left_alone() -> None:
    """Somebody writing 「115年6月上旬」 means it; rewriting it would be worse."""
    from capabilities.ncc_plan.rules import date_in_slashes, date_in_words
    assert date_in_words("115年6月上旬") == "115年6月上旬"
    assert date_in_slashes("待確認") == "待確認"


def test_an_impossible_date_is_not_reformatted_into_looking_valid() -> None:
    from capabilities.ncc_plan.rules import date_in_words
    assert date_in_words("115/13/40") == "115/13/40"


def test_an_empty_date_stays_empty() -> None:
    from capabilities.ncc_plan.rules import date_in_slashes, date_in_words
    assert date_in_words("") == "" and date_in_slashes("") == ""
