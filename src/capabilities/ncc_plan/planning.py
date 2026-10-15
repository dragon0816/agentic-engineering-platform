"""Resolve one plan from the catalogue: Workflow 14's `prepare` step.

Ported from rs_workflow_system@896046e `host-bridge/jobs/ncc_improvement_plan.py`
(`stations_from_config`, `find_station` and the `load`/`price` part of `run`).
The content decisions stay in `rules`, which is the source module unchanged.

The catalogue is the source's `config/workflow-14.json`, read as data: only its
content sections are used. Its `paths`, `params` and `ops` sections are not
read; AEP's per-install Workflow settings replace them, and `ops` may carry
the old dashboard's token.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from capabilities.ncc_plan import rules
from capabilities.ncc_plan.contracts import (
    NccDocument,
    NccMail,
    NccPlan,
    NccPlanRequest,
    ServiceLine,
    Verdict,
)
from capabilities.ncc_plan.rules import JobError

CATALOGUE_SECTIONS = (
    "document",
    "prices",
    "systems",
    "outcomes",
    "faultLines",
    "channelNames",
    "planLines",
    "displayNames",
    "stationSystems",
    "faultIntro",
    "stations",
    "delivery",
)
PHOTO_SUFFIXES = (".jpg", ".jpeg", ".png", ".JPG", ".PNG")


def load_catalogue(path: Path) -> dict[str, Any]:
    """The catalogue's content sections; anything else in the file is ignored."""
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise JobError("the catalogue is not a JSON object")
    return {key: data.get(key) for key in CATALOGUE_SECTIONS}


def stations_from_config(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The station list as the catalogue holds it (source `stations_from_config`)."""
    out: list[dict[str, Any]] = []
    for row in rows or []:
        name = str(row.get("station") or "").strip()
        if not name:
            continue
        out.append(
            {
                "station": name,
                "location": str(row.get("location") or "").strip(),
                "authority": str(row.get("authority") or "").strip(),
                "builtYear": str(row.get("builtYear") or "").strip(),
                "area": str(row.get("area") or "").strip(),
                "population": row.get("population"),
                "coverageIsOwn": bool(str(row.get("area") or "").strip()),
                "equipmentModel": str(row.get("equipmentModel") or "").strip(),
                "power": str(row.get("power") or "").strip(),
                "channels": list(row.get("channels") or []),
                "serviceChannels": list(row.get("serviceChannels") or []),
                "systems": list(row.get("systems") or []),
            }
        )
    return out


def find_station(stations: Sequence[dict[str, Any]], wanted: str) -> dict[str, Any]:
    want = (wanted or "").strip()
    if not want:
        raise JobError("params.station is empty; choose which station this plan is for")
    for row in stations:
        if row["station"] == want or row["station"] == f"{want}站":
            return row
    close = [s["station"] for s in stations if want.rstrip("站") in s["station"]]
    hint = f" Did you mean: {', '.join(close[:5])}?" if close else ""
    raise JobError(f"{want!r} is not in the station table.{hint}")


def station_choices(catalogue_file: str) -> list[tuple[str, str]]:
    """`(value, label)` for the station menu, sorted as the source published it."""
    rows = stations_from_config(load_catalogue(Path(catalogue_file)).get("stations") or [])
    rows.sort(key=lambda row: f"{row['location']:<12}{row['station']}")
    return [
        (
            row["station"],
            f"{row['station']}（{row['location']}）" if row["location"] else row["station"],
        )
        for row in rows
    ]


def _split(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,\s]+", text or "") if item.strip()]


def _missing_photos(photo_dir: str, station: str, expected: Sequence[str]) -> list[str]:
    if not photo_dir.strip():
        return list(expected)
    folder = Path(photo_dir) / station
    return [
        name
        for name in expected
        if not any((folder / f"{name}{ext}").is_file() for ext in PHOTO_SUFFIXES)
    ]


def _mail(
    request: NccPlanRequest,
    catalogue: Mapping[str, Any],
    station: Mapping[str, Any],
    output_path: Path,
    total: int,
    missing_photos: Sequence[str],
) -> NccMail:
    """The covering draft (source `create_draft`): a draft, never a send."""
    delivery = catalogue.get("delivery") or {}
    recipients = [item for item in request.draft_to if item.strip()]
    if not recipients and str(delivery.get("to") or "").strip():
        recipients = [str(delivery["to"]).strip()]
    if request.dry_run or not recipients:
        return NccMail(skip=True)
    subject = str(delivery.get("subjectTemplate") or "{station}改善服務規劃").format(
        station=station.get("station", ""), total=f"{total:,}"
    )
    lines = [
        f"<p>{station.get('station', '')}的改善服務規劃已產出。</p>",
        f"<p>總計 {total:,} 元（未稅）。</p>",
    ]
    if missing_photos:
        lines.append(
            "<p>還需要補上這幾張照片：" + "、".join(str(x) for x in missing_photos) + "</p>"
        )
    lines.append("<p>這封是草稿，不會自動寄出。</p>")
    return NccMail(
        skip=False,
        subject=subject,
        html_body="<html><body>" + "".join(lines) + "</body></html>",
        to=tuple(recipients),
        cc=tuple(str(item) for item in (delivery.get("cc") or []) if str(item).strip()),
        attachments=(str(output_path),),
    )


def prepare_plan(request: NccPlanRequest) -> NccPlan:
    """Everything the document will say, resolved; nothing is written."""
    request = NccPlanRequest.model_validate(request)
    catalogue = load_catalogue(Path(request.catalogue_file))
    document = catalogue.get("document") or {}
    prices = catalogue.get("prices") or []
    station_systems = catalogue.get("stationSystems") or {}
    catalog = catalogue.get("systems") or []
    outcomes = catalogue.get("outcomes") or {}
    channel_names = catalogue.get("channelNames") or {}

    stations = stations_from_config(catalogue.get("stations") or [])
    if not stations:
        raise JobError("the catalogue carries no `stations` list, so there is nothing to choose")
    template = Path(request.template_file)
    if not template.is_file():
        raise JobError("the example plan used as the template was not found")
    station = find_station(stations, request.station)

    # The station's own equipment wins over the shared default.
    if station.get("systems"):
        catalog = [{"system": name} for name in station["systems"]]
    elif station["station"] in station_systems:
        catalog = [{"system": name} for name in station_systems[station["station"]]]

    channels = _split(request.channels)
    if not channels:
        channels = [str(c) for c in (station.get("channels") or [])]
    if not channels:
        channels = [str(c) for c in (document.get("defaultChannels") or [])]
    if not channels:
        raise JobError("no channels given and document.defaultChannels is empty")

    service_channels = (
        [str(c) for c in (station.get("serviceChannels") or [])]
        or [str(c) for c in (document.get("serviceChannels") or [])]
        or channels
    )
    model = str(station.get("equipmentModel") or document.get("equipmentModel") or "").strip()
    power = str(station.get("power") or document.get("power") or "").strip()
    ticks = request.ticks()
    selection = rules.selection_from_ticks(catalog, ticks, len(channels), power)

    spelling = document.get("spelling") or {}
    completion = rules.date_in_slashes(
        str(request.completion_date or document.get("completionDate") or "")
    )
    contractor = str(document.get("contractor") or "")
    plan_year = str(document.get("planYear") or "")
    confirm_date = rules.date_in_words(request.confirm_date)
    service_table, total = rules.service_rows(
        selection, prices, outcomes, completion, names=catalogue.get("displayNames") or {}
    )

    expected_photos = rules.photo_names(channels)
    missing_photos = _missing_photos(request.photo_dir, station["station"], expected_photos)
    out_name = f"{plan_year} {station['station']}改善服務規劃 {model} {power}{len(channels)}台.docx"
    output_dir = Path(request.output_dir)
    if not output_dir.is_dir():
        # Named, not created: an absent folder is usually a typo or a share
        # that is not mounted, and making one hides both.
        raise JobError("output_dir is not a folder; fix it in this Workflow's settings")
    output_path = output_dir / out_name

    area = rules.prefer_spelling(rules.service_area(station["location"], station["area"]), spelling)
    authority = rules.prefer_spelling(
        rules.authority_line(station["location"], station["authority"]), spelling
    )
    population = f"{station['population']:,}" if station["population"] is not None else "＿＿"
    intro = ""
    intro_templates = catalogue.get("faultIntro") or {}
    for item, _qty in selection:
        found = intro_templates.get(rules.normalise_item(item))
        if found:
            intro = "（一）" + found.format(channels=len(channels))
            break
    doc = NccDocument(
        authority_line=f"標的區域所在機關：{authority}",
        title_line=f"標的區域\t{station['authority']}{station['station']}",
        contractor_line=f"履約廠商：{contractor}" if contractor else "",
        channel_sentence=rules.channel_sentence(
            service_channels, channel_names, int(document.get("programmeCount") or 0)
        ),
        start_year_line=f"1、數位無線電視服務提供起始年度：{station['builtYear']}年度。",
        area_line=f"2、服務區域：{area or '＿＿'}，可服務人口數約{population}人。",
        confirm_line=(
            "（一）標的區域仍有機關或民眾有接收數位無線電視訊號需求，且標的區域所轄權責機關"
            f"{authority}{confirm_date}確認有改善需求，爰本案即規畫辦理改善服務。"
            if confirm_date
            else ""
        ),
        system_rows=tuple(tuple(row) for row in rules.system_rows_from_ticks(catalog, ticks)),
        service_rows=tuple(tuple(row) for row in service_table),
        plan_lines=tuple(
            rules.plan_lines(
                selection,
                catalogue.get("planLines") or {},
                len(channels),
                str(document.get("closingLine") or ""),
            )
        ),
        fault_intro=intro,
        fault_captions=tuple(
            rules.fault_lines(selection, channels, catalogue.get("faultLines") or {})
        ),
    )
    preview: list[str] = []
    if request.dry_run:
        preview = rules.preview(
            station=station,
            area=area,
            out_name=out_name,
            selection=selection,
            rows=service_table,
            total=total,
            channels=channels,
            service_channels=service_channels,
            systems=catalog,
            unmatched=[],
            missing_photos=missing_photos,
        )
    summary = f"{station['station']} {len(selection)} 項，總計 {total:,} 元"
    return NccPlan(
        station=station["station"],
        authority=station["authority"],
        built_year=station["builtYear"],
        area=station["area"],
        population=station["population"],
        coverage_is_own=station["coverageIsOwn"],
        channels=tuple(channels),
        service_channels=tuple(service_channels),
        services=tuple(ServiceLine(item=n, quantity=q) for n, q in selection),
        total=total,
        expected_photos=tuple(expected_photos),
        missing_photos=tuple(missing_photos),
        output_name=out_name,
        output_path=str(output_path),
        template_file=str(template),
        dry_run=request.dry_run,
        preview=tuple(preview),
        verdict=(
            Verdict(ok=None, summary=summary + "，試跑，未寫檔")
            if request.dry_run
            else Verdict(ok=True, summary=summary + "，待寫檔")
        ),
        document=doc,
        mail=_mail(request, catalogue, station, output_path, total, missing_photos),
    )
