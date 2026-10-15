"""Pure helpers for the NCC improvement-plan job. No I/O, so they are testable.

Everything here is a decision about *content* -- which systems a chosen service
touches, what a row costs, how a station's coverage text splits into an area and
a population. The docx handling lives in the job beside it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


class JobError(RuntimeError):
    """Something the operator can fix. The message names the cause."""


#: "…等【約1,331人】" -> the number, on its own.
_POPULATION_RE = re.compile(r"【約\s*([\d,]+)\s*人】")


def split_coverage(text: str) -> tuple[str, int | None]:
    """`(area, population)` from a coverage cell.

    The population is inside the text rather than in its own column, and the
    document needs the two separately: one goes in "服務區域：…" and the other
    in "可服務人口數約…人".
    """
    raw = (text or "").strip()
    match = _POPULATION_RE.search(raw)
    population = int(match.group(1).replace(",", "")) if match else None
    area = _POPULATION_RE.sub("", raw).strip()
    area = area.rstrip("等").strip().rstrip("、").strip()
    return area, population


def normalise_item(name: str) -> str:
    """A price-list item name with spacing and full-width brackets levelled.

    The PDF wraps names mid-word, so the same service appears as
    "混頻系統 (6頻道) 調變錯誤比改 善服務" in one place and without the spaces
    in another. Matching on a normalised form keeps the config readable.
    """
    text = re.sub(r"\s+", "", name or "")
    return text.replace("（", "(").replace("）", ")").replace("：", ":").replace("，", ",")


def price_of(item: str, prices: Sequence[Mapping[str, Any]]) -> int:
    """The unit price for a service, or a refusal naming what was not found.

    Refuses rather than defaulting to zero: a plan whose total is silently short
    by one line is worse than one that did not get written.
    """
    wanted = normalise_item(item)
    for row in prices:
        if normalise_item(str(row.get("item", ""))) == wanted:
            return int(row["unitPrice"])
    known = ", ".join(sorted({str(r.get("item", ""))[:24] for r in prices})[:6])
    raise JobError(
        f"no unit price for {item!r} in the configured price list. Known items start with: {known}…"
    )


def parse_selection(raw: str | Sequence[str]) -> list[tuple[str, int]]:
    """`"5瓦…:6, 訊號放大器…:1"` -> `[(name, quantity), …]`.

    Accepts a list as well, because the workflow may send one. A quantity of
    zero is dropped: choosing a service and then asking for none of it is a
    contradiction the document cannot render.
    """
    if isinstance(raw, str):
        parts = [p for p in re.split(r"[,\n;]", raw) if p.strip()]
    else:
        parts = [str(p) for p in (raw or []) if str(p).strip()]

    out: list[tuple[str, int]] = []
    for part in parts:
        name, sep, qty = part.rpartition(":")
        if not sep:
            name, qty = part, "1"
        name = name.strip()
        if not name:
            raise JobError(f"service entry {part!r} has no name; expected 名稱:數量")
        try:
            quantity = int(str(qty).strip())
        except ValueError as exc:
            raise JobError(
                f"service {name!r} has quantity {qty!r}, which is not a whole number"
            ) from exc
        if quantity < 0:
            raise JobError(f"service {name!r} has a negative quantity ({quantity})")
        if quantity == 0:
            continue
        out.append((name, quantity))
    if not out:
        raise JobError("no service items were chosen, so there is nothing to plan")
    return out


def service_rows(
    selection: Sequence[tuple[str, int]],
    prices: Sequence[Mapping[str, Any]],
    outcomes: Mapping[str, str],
    completion_date: str,
    names: Mapping[str, str] | None = None,
) -> tuple[list[list[str]], int]:
    """The rows of 表四, plus the total.

    Returns strings because that is what goes in the cells, and the money is
    formatted once here rather than at each call site.
    """
    rows: list[list[str]] = []
    total = 0
    for i, (name, quantity) in enumerate(selection, 1):
        unit = price_of(name, prices)
        amount = unit * quantity
        total += amount
        rows.append(
            [
                str(i),
                display_name(name, names or {}),
                str(quantity),
                f"{amount:,}",
                completion_date,
                outcomes.get(normalise_item(name), ""),
            ]
        )
    rows.append(["", "總計", "", f"{total:,}", "", ""])
    return rows, total


def system_rows(
    catalog: Sequence[Mapping[str, Any]],
    selection: Sequence[tuple[str, int]],
    mapping: Mapping[str, str],
) -> list[list[str]]:
    """The rows of 表一: every system, ticked 正常 or 待改善.

    A system is 待改善 exactly when a chosen service improves it -- which is the
    rule the examples follow, and the reason the two tables cannot disagree.
    """
    improving = {mapping.get(normalise_item(name), normalise_item(name)) for name, _ in selection}
    rows: list[list[str]] = []
    for i, entry in enumerate(catalog, 1):
        system = str(entry.get("system", "")).strip()
        needs_work = normalise_item(system) in improving
        rows.append(
            [
                str(i),
                system,
                "□正常■待改善" if needs_work else "■正常□待改善",
            ]
        )
    return rows


def unmatched_systems(
    catalog: Sequence[Mapping[str, Any]],
    selection: Sequence[tuple[str, int]],
    mapping: Mapping[str, str],
) -> list[str]:
    """Chosen services whose system is not in the catalogue.

    Worth reporting rather than ignoring: it means 表一 will not mark anything
    for that service, so the two tables would tell different stories.
    """
    known = {normalise_item(str(e.get("system", ""))) for e in catalog}
    missing = []
    for name, _ in selection:
        target = mapping.get(normalise_item(name), normalise_item(name))
        if target not in known:
            missing.append(name)
    return missing


#: 臺東縣綠島鄉 -> 臺東縣, 新北市平溪區 -> 新北市, 連江縣北竿鄉 -> 連江縣
_COUNTY_RE = re.compile(r"^(.+?[縣市])")


def prefer_spelling(text: str, swaps: Mapping[str, str] | None = None) -> str:
    """Apply the document's spelling of characters the sources disagree on.

    The station table writes 臺東縣; every example plan writes 台東縣. Both are
    correct and a document that mixes them looks careless, so one wins and it is
    configurable rather than decided here.
    """
    out = text or ""
    for source, target in (swaps or {}).items():
        out = out.replace(source, target)
    return out


def authority_line(location: str, authority: str) -> str:
    """「臺東縣政府綠島鄉公所」from the table's 位置 and 管轄單位.

    Concatenating the two columns gives 「臺東縣綠島鄉綠島鄉公所」 -- the
    township appears twice, because 位置 already contains it. The examples名
    the county government, so only the 縣/市 part is kept.

    An authority that is itself a county government (連江縣政府) is returned
    unchanged: prefixing it would give 「連江縣政府連江縣政府」.
    """
    auth = (authority or "").strip()
    loc = (location or "").strip()
    if not auth:
        return loc
    if auth.endswith("政府"):
        return auth
    match = _COUNTY_RE.match(loc)
    county = match.group(1) if match else loc
    return f"{county}政府{auth}" if county else auth


def service_area(location: str, area: str) -> str:
    """「台東縣綠島鄉公館村」-- the county, then the area as the table has it.

    The table's 涵蓋區域 starts at the township, and the document names the
    county first. Skipped when the area already carries it, which some rows do.
    """
    area = (area or "").strip()
    if not area:
        return ""
    match = _COUNTY_RE.match((location or "").strip())
    county = match.group(1) if match else ""
    if not county or area.startswith(county):
        return area
    # 臺 and 台 are the same county spelled two ways; both appear in these files.
    if county.startswith("臺") and area.startswith("台" + county[1:]):
        return area
    return f"{county}{area}"


def display_name(item: str, names: Mapping[str, str]) -> str:
    """The short name the document uses, or the price-list name unchanged.

    The price list writes 「5瓦(含以上及以下)(各頻道)發射/補隙系統變調變錯誤比
    改善服」 -- wrapped mid-word by the PDF -- while the plan writes
    「5W補隙系統調變錯誤比改善服務」. The contract needs the first; the reader
    needs the second.
    """
    return names.get(normalise_item(item), item)


def plan_lines(
    selection: Sequence[tuple[str, int]],
    templates: Mapping[str, str],
    channel_count: int,
    closing: str,
) -> list[str]:
    """三、改善服務規劃 -- one numbered line per chosen service, then the closing.

    Numbered in 全形 because that is what the document uses, and the numbering
    has to continue from （一）, which the caller writes.
    """
    marks = "一二三四五六七八九十"
    lines: list[str] = []
    for item, _qty in selection:
        template = templates.get(normalise_item(item))
        if not template:
            # No sentence for this service, so it contributes no paragraph --
            # and must not consume a number either, or the list reads
            # （二）（四） and looks like something was deleted.
            continue
        index = len(lines) + 1
        mark = marks[index] if index < len(marks) else str(index + 1)
        lines.append(f"（{mark}）" + template.format(channels=channel_count))
    if closing:
        mark = marks[len(lines) + 1] if len(lines) + 1 < len(marks) else str(len(lines) + 2)
        lines.append(f"（{mark}）{closing}")
    return lines


def fault_lines(
    selection: Sequence[tuple[str, int]], channels: Sequence[str], templates: Mapping[str, str]
) -> list[str]:
    """二、 -- one caption per channel, for the service that drives the faults.

    The first chosen service with a caption template wins: the examples caption
    每 channel once, naming the transmitter, not once per service.
    """
    for item, _qty in selection:
        template = templates.get(normalise_item(item))
        if template:
            return [template.format(channel=c) for c in channels]
    return []


def preview(
    *,
    station: Mapping[str, Any],
    area: str,
    out_name: str,
    selection: Sequence[tuple[str, int]],
    rows: Sequence[Sequence[str]],
    total: int,
    channels: Sequence[str],
    service_channels: Sequence[str],
    systems: Sequence[Mapping[str, Any]],
    unmatched: Sequence[str],
    missing_photos: Sequence[str],
) -> list[str]:
    """What the document will say, for somebody who cannot read the code.

    Returned as lines rather than printed so it can be tested, and written in
    Chinese because every value in it is -- a Chinese station name inside an
    English sentence is harder to read than either alone.
    """
    population = station.get("population")
    people = f"約{population:,}人" if isinstance(population, int) else "人口數不詳"

    out = [
        "",
        "── 這份文件會長這樣（試跑，還沒寫檔）" + "─" * 26,
        f"  站台      {station.get('station', '')}"
        f"（{station.get('authority', '')} · 建置{station.get('builtYear', '')}年）",
        f"  服務區域  {area or '（未填）'} · {people}",
        f"  檔名      {out_name}",
        "",
        f"  現況說明涵蓋 {len(service_channels)} 個頻道，這次改善 {len(channels)} 個："
        f"{'、'.join(channels)}",
        "",
        f"  改善項目（{len(selection)} 項，總計 {total:,} 元未稅）",
    ]
    for row in rows[:-1]:  # the last row is the total
        out.append(f"    {row[1]:<34}×{row[2]:>3}   {row[3]:>12}")

    matched = len(selection) - len(unmatched)
    out += [
        "",
        f"  表一會列這一站的 {len(systems)} 個系統，其中 {matched} 個標成待改善，其餘標正常",
    ]

    if unmatched:
        out += [
            "",
            "  【注意】這幾項服務在表一找不到對應的系統：",
            *[f"      {name}" for name in unmatched],
            "    表四會列出它們，表一不會標記 —— 兩張表會對不上。",
            "    多半是這一站的系統清單或選的服務項目不對。",
        ]

    if missing_photos:
        out += ["", f"  照片還缺 {len(missing_photos)} 張：{'、'.join(missing_photos)}"]

    out += [
        "",
        "  還沒寫任何檔案，也沒有動到任何來源文件。",
        "  確認以上內容無誤，拿掉試跑就會真的產出。",
        "─" * 62,
        "",
    ]
    return out


def service_for(entry: Mapping[str, Any], power: str) -> str:
    """The priced service a ticked system selects.

    The transmitter row is priced by wattage, so which line of the contract it
    is depends on the station -- 公館站's 5W and 四條溝站's 25W are different
    prices for the same tick.
    """
    by_power = entry.get("serviceByPower") or {}
    if by_power:
        key = (power or "").strip().upper()
        service = by_power.get(key)
        if not service:
            raise JobError(
                f"{entry.get('system')} is priced per wattage and this station's "
                f"power is {power!r}, which is not one of "
                f"{', '.join(sorted(by_power))}. Set it in the station's settings."
            )
        return str(service)
    service = str(entry.get("service") or "").strip()
    if not service:
        raise JobError(f"{entry.get('system')} has no service configured")
    return service


def selection_from_ticks(
    systems: Sequence[Mapping[str, Any]], ticked: Mapping[str, Any], channel_count: int, power: str
) -> list[tuple[str, int]]:
    """`[(service, quantity), …]` for the systems somebody ticked, in table order.

    Quantity is the channel count for the three services the contract prices per
    channel, and one for the rest -- measured from the examples rather than
    assumed: 公館站 5W x 6 channels, 四條溝站 25W x 2, 衛星解碼 x 2, GPS x 2.
    """
    out: list[tuple[str, int]] = []
    for entry in systems:
        field = str(entry.get("field") or "")
        if not field or not ticked.get(field):
            continue
        quantity = channel_count if entry.get("perChannel") else 1
        if quantity < 1:
            raise JobError(
                f"{entry.get('system')} is priced per channel but no channel was "
                "chosen, so there is no quantity to bill"
            )
        out.append((service_for(entry, power), quantity))
    if not out:
        raise JobError(
            "no system was ticked, so there is nothing to improve. Tick the ones "
            "that need work in 表一."
        )
    return out


def system_rows_from_ticks(
    systems: Sequence[Mapping[str, Any]], ticked: Mapping[str, Any]
) -> list[list[str]]:
    """表一: every system in order, ticked 正常 or 待改善.

    Same eleven rows on every plan -- what varies is only the box.
    """
    rows: list[list[str]] = []
    for i, entry in enumerate(systems, 1):
        needs_work = bool(ticked.get(str(entry.get("field") or "")))
        rows.append(
            [
                str(i),
                str(entry.get("system") or ""),
                "□正常■待改善" if needs_work else "■正常□待改善",
            ]
        )
    return rows


#: 115/09/30, 115-09-30, 115.9.30 or 115年9月30日 -- people type all four, and
#: the form should not care which.
_ROC_DATE_RE = re.compile(r"^\s*(\d{2,3})\s*[/\-.年]\s*(\d{1,2})\s*[/\-.月]\s*(\d{1,2})\s*日?\s*$")


def parse_roc_date(text: str) -> tuple[int, int, int] | None:
    """`(year, month, day)` from a ROC date, or None if it is not one."""
    match = _ROC_DATE_RE.match(text or "")
    if not match:
        return None
    year, month, day = (int(g) for g in match.groups())
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return year, month, day


def date_in_words(text: str) -> str:
    """`115/09/30` -> `115年9月30日`, for the sentence in 三、（一）.

    Unrecognised text is returned unchanged: somebody writing 「115年6月上旬」
    means it, and rewriting it would be worse than leaving it.
    """
    parsed = parse_roc_date(text)
    if not parsed:
        return (text or "").strip()
    year, month, day = parsed
    return f"{year}年{month}月{day}日"


def date_in_slashes(text: str) -> str:
    """`115年9月30日` -> `115/09/30`, for the 完成日期 column of 表四."""
    parsed = parse_roc_date(text)
    if not parsed:
        return (text or "").strip()
    year, month, day = parsed
    return f"{year}/{month:02d}/{day:02d}"


def photo_names(channels: Sequence[str]) -> list[str]:
    """Which image files a plan expects, in document order.

    The convention: one exterior shot, then one per channel, named after the
    channel exactly as the document writes it.
    """
    return ["外觀"] + [str(c).strip() for c in channels if str(c).strip()]


def channel_sentence(
    channels: Sequence[str], names: Mapping[str, str], programme_count: int
) -> str:
    """「數位無線電視為民眾提供CH24中視、…共N頻道M個數位無線節目的收視。」"""
    parts = []
    for channel in channels:
        key = str(channel).strip()
        parts.append(f"{key}{names.get(key, '')}")
    joined = "、".join(parts)
    return (
        f"（一）數位無線電視為民眾提供{joined}，共{len(parts)}頻道"
        f"{programme_count}個數位無線節目的收視。"
    )
