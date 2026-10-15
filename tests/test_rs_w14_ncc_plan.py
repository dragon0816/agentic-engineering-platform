"""rs_workflow_system Workflow 14 (ncc_improvement_plan) as an AEP Workflow.

Strategy ADAPT: the content rules are the source module (oracle:
tests/test_ncc_rules_source.py); the docx edit and the run are ported; the
Outlook draft is the shared `outlook.draft` building block. These tests cover
the job-body behaviour the source pinned (dry run, verdict, files, absent
output folder, Word lock, draft never fatal and never sent) through the real
Workflow, Bridge policy and generated forms. A last test compares the output
with the source job itself on the real template when the source clone and its
(uncommitted) documents are on this machine.
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import pytest
from test_host_wiring import membership_record, workspace

from capabilities.ncc_plan.contracts import NccPlanRequest
from capabilities.ncc_plan.handlers import render_plan
from capabilities.ncc_plan.manifest import WORKFLOW, plan_workflow
from capabilities.ncc_plan.planning import prepare_plan, station_choices
from channels import telegram_flow as flow
from common.execution import TraceIdentifiers
from common.local_agent import LocalWorkflowRequest
from common.workflow_forms import agent_tool_schema, form_fields, settings_fields
from host_runtime.host import build_runtime
from host_runtime.workflow_settings import SETTINGS_FILE, WorkflowSettingsStore
from integrations.outlook_draft import DraftError, MailDraft, RecordingDraftWriter

docx = pytest.importorskip("docx")

SOURCE_ROOT = Path(r"C:\Users\Chi_L\Documents\claude\n8n_workflow_system")

CATALOGUE: dict[str, Any] = {
    "paths": {"template": "ignored.docx"},
    "ops": {"baseUrl": "https://ops.invalid", "token": "never-read"},
    "document": {
        "contractor": "台灣羅德史瓦茲有限公司",
        "planYear": "2026",
        "completionDate": "115/09/30",
        "programmeCount": 23,
        "defaultChannels": ["CH24", "CH26"],
        "closingLine": "提供1年內故障維修服務。",
        "spelling": {"臺東縣": "台東縣"},
        "serviceChannels": ["CH24", "CH26", "CH28"],
        "equipmentModel": "TLX9",
        "power": "5W",
    },
    "channelNames": {"CH24": "中視", "CH26": "公視", "CH28": "民視"},
    "systems": [
        {
            "system": "發射/補隙系統",
            "field": "transmitter",
            "perChannel": True,
            "serviceByPower": {"5W": "5瓦發射系統改善服務", "25W": "25瓦發射系統改善服務"},
        },
        {"system": "訊號放大器系統", "field": "amplifier", "service": "放大器增益改善服務"},
        {"system": "空調系統", "field": "aircon", "service": "空調恆溫改善服務"},
    ],
    "prices": [
        {"item": "5瓦發射系統改善服務", "unitPrice": 299000},
        {"item": "25瓦發射系統改善服務", "unitPrice": 338500},
        {"item": "放大器增益改善服務", "unitPrice": 50000},
        {"item": "空調恆溫改善服務", "unitPrice": 30000},
    ],
    "outcomes": {"5瓦發射系統改善服務": "MER改善"},
    "displayNames": {"5瓦發射系統改善服務": "5W補隙系統調變錯誤比改善服務"},
    "planLines": {
        "5瓦發射系統改善服務": "改善{channels}台發射機。",
        "空調恆溫改善服務": "改善空調。",
    },
    "faultLines": {"5瓦發射系統改善服務": "{channel} 發射機調變錯誤比不佳"},
    "faultIntro": {"5瓦發射系統改善服務": "5W發射機共{channels}台調變錯誤比不佳。"},
    "stations": [
        {
            "station": "公館站",
            "location": "臺東縣綠島鄉",
            "authority": "綠島鄉公所",
            "builtYear": "98",
            "area": "綠島鄉公館村",
            "population": 1331,
        },
        {
            "station": "四條溝站",
            "location": "新北市平溪區",
            "authority": "平溪區公所",
            "builtYear": "99",
            "area": "",
            "population": None,
            "power": "25W",
            "channels": ["CH30"],
        },
    ],
    "delivery": {"to": "", "cc": ["lead@example.com"], "subjectTemplate": "{station}改善服務規劃"},
}


def _template(path: Path) -> Path:
    document = docx.Document()
    for text in (
        "標的區域\t舊機關舊站",
        "標的區域所在機關：舊機關",
        "履約廠商：舊廠商",
        "（一）數位無線電視為民眾提供舊頻道",
        "1、數位無線電視服務提供起始年度：90年度。",
        "2、服務區域：舊區域",
        "二、現況",
        "（一）5W舊說明",
    ):
        document.add_paragraph(text)
    systems = document.add_table(rows=2, cols=3)
    for cell, text in zip(systems.rows[0].cells, ("項次", "系統", "狀態"), strict=True):
        cell.text = text
    for _ in range(2):
        block = document.add_table(rows=2, cols=1)
        block.rows[1].cells[0].text = "舊照片說明"
    for text in (
        "三、改善服務規劃",
        "（一）標的區域仍有機關舊句",
        "（二）舊行",
        "（三）舊行",
        "四、經費",
    ):
        document.add_paragraph(text)
    services = document.add_table(rows=2, cols=6)
    for cell, text in zip(
        services.rows[0].cells, ("項次", "項目", "數量", "金額", "完成", "成效"), strict=True
    ):
        cell.text = text
    document.save(str(path))
    return path


def _files(tmp_path: Path) -> dict[str, str]:
    catalogue = tmp_path / "workflow-14.json"
    catalogue.write_text(json.dumps(CATALOGUE, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()
    photos = tmp_path / "photos" / "公館站"
    photos.mkdir(parents=True)
    (photos / "外觀.jpg").write_bytes(b"\xff\xd8")
    return {
        "catalogue_file": str(catalogue),
        "template_file": str(_template(tmp_path / "template.docx")),
        "output_dir": str(output),
        "photo_dir": str(tmp_path / "photos"),
    }


def _texts(path: Path) -> tuple[list[str], list[list[list[str]]]]:
    document = docx.Document(str(path))
    return (
        [paragraph.text for paragraph in document.paragraphs],
        [[[cell.text for cell in row.cells] for row in table.rows] for table in document.tables],
    )


def test_prepare_resolves_the_document_and_render_writes_it(tmp_path: Path) -> None:
    settings = _files(tmp_path)
    plan = prepare_plan(
        NccPlanRequest.model_validate(
            {
                **settings,
                "station": "公館",
                "channels": "CH24,CH26",
                "confirm_date": "115/6/7",
                "transmitter": True,
                "aircon": True,
            }
        )
    )
    assert plan.station == "公館站" and plan.total == 299000 * 2 + 30000
    assert plan.missing_photos == ("CH24", "CH26")  # 外觀.jpg is there
    assert plan.output_name == "2026 公館站改善服務規劃 TLX9 5W2台.docx"
    assert plan.document.authority_line == "標的區域所在機關：台東縣政府綠島鄉公所"
    assert plan.mail.skip is True  # nobody to send it to
    rendered = render_plan(plan)
    assert rendered.written and rendered.verdict.ok is True
    assert rendered.verdict.summary == "公館站 2 項，總計 628,000 元，已寫檔"
    assert rendered.files[0].name == plan.output_name
    paragraphs, tables = _texts(Path(plan.output_path))
    assert "標的區域\t綠島鄉公所公館站" in paragraphs
    assert "2、服務區域：台東縣綠島鄉公館村，可服務人口數約1,331人。" in paragraphs
    assert "（一）5W發射機共2台調變錯誤比不佳。" in paragraphs
    assert any(
        text.startswith("（一）標的區域仍有機關") and "115年6月7日" in text for text in paragraphs
    )
    # 三、 follows the selection: one line per service with a sentence, then the closing.
    assert ["（二）改善2台發射機。", "（三）改善空調。", "（四）提供1年內故障維修服務。"] == [
        text for text in paragraphs if text[:3] in ("（二）", "（三）", "（四）")
    ]
    systems, *blocks, services = tables
    assert [row[2] for row in systems[1:]] == ["□正常■待改善", "■正常□待改善", "□正常■待改善"]
    assert [block[-1][0] for block in blocks] == [
        "CH24 發射機調變錯誤比不佳",
        "CH26 發射機調變錯誤比不佳",
    ]
    assert services[1][:4] == ["1", "5W補隙系統調變錯誤比改善服務", "2", "598,000"]
    assert services[-1][1] == "總計" and services[-1][3] == "628,000"


def test_the_stations_menu_comes_from_the_catalogue(tmp_path: Path) -> None:
    settings = _files(tmp_path)
    assert station_choices(settings["catalogue_file"]) == [
        ("四條溝站", "四條溝站（新北市平溪區）"),
        ("公館站", "公館站（臺東縣綠島鄉）"),
    ]


def _grants() -> list[dict[str, Any]]:
    def grant(namespace: str, name: str, permission: str) -> dict[str, Any]:
        return {
            "actor": "engineer",
            "asset": {"namespace": namespace, "name": name, "version": "1.0.0"},
            "permissions": [permission],
            "policy_refs": [f"{namespace}-policy"]
            if namespace != "outlook"
            else ["outlook-draft-policy"],
            "approval_ref": "w14-approval",
        }

    return [
        grant("ncc-plan", "prepare", "ncc-plan.prepare"),
        grant("ncc-plan", "render", "ncc-plan.render"),
        grant("outlook", "draft", "outlook.draft"),
    ]


def _runtime(tmp_path: Path, drafter: Any, settings: dict[str, str] | None) -> Any:
    config, layout = workspace(tmp_path / "host", membership=membership_record(), grants=_grants())
    (layout.workflows / "rs-ncc.json").write_text(
        plan_workflow().model_dump_json(), encoding="utf-8"
    )
    if settings is not None:
        WorkflowSettingsStore(layout.workspace_root / SETTINGS_FILE).save(WORKFLOW, settings)
    return config, build_runtime(config, drafter=drafter)


def _run(runtime: Any, config: Any, arguments: dict[str, Any], key: str) -> Any:
    request = LocalWorkflowRequest(
        actor="engineer",
        bridge_id=config.device.bridge_id,
        workflow=WORKFLOW,
        arguments=arguments,
        idempotency_key=key,
        trace=TraceIdentifiers(trace_id=f"w14-{key}", request_id="w14", span_id="test"),
    )
    result = asyncio.run(runtime.agent.execute_workflow(request)).workflow
    assert result is not None
    return result


def test_the_workflow_previews_writes_and_drafts_through_bridge_policy(tmp_path: Path) -> None:
    settings = _files(tmp_path)
    writer = RecordingDraftWriter()
    config, runtime = _runtime(tmp_path, lambda: writer, settings)
    with runtime:
        preview = _run(
            runtime,
            config,
            {
                "station": "公館站",
                "transmitter": True,
                "dry_run": True,
                "draft_to": ["a@example.com"],
            },
            "dry",
        )
        assert preview.run.status == "succeeded", preview.run.failure
        prepared, rendered, drafted = (step.data for step in preview.step_results)
        assert prepared["verdict"] == {
            "ok": None,
            "summary": "公館站 1 項，總計 598,000 元，試跑，未寫檔",
        }
        assert any("試跑" in line for line in prepared["preview"])
        assert rendered["written"] is False and drafted["skipped"] is True
        assert list(Path(settings["output_dir"]).iterdir()) == [] and writer.drafts == []

        real = _run(
            runtime,
            config,
            {"station": "公館站", "transmitter": True, "draft_to": ["reviewer@example.com"]},
            "real",
        )
        assert real.run.status == "succeeded", real.run.failure
        _, rendered, drafted = (step.data for step in real.step_results)
        assert rendered["written"] is True and Path(rendered["output"]).is_file()
        assert drafted["drafted"] is True and drafted["attachments"] == 1
        [mail] = writer.drafts
        assert mail.to == ("reviewer@example.com",) and mail.cc == ("lead@example.com",)
        assert mail.subject == "公館站改善服務規劃"
        assert mail.attachments == (rendered["output"],)
        assert "不會自動寄出" in mail.html_body

        nothing = _run(runtime, config, {"station": "公館站"}, "nothing")
        assert nothing.run.failure is not None
        assert nothing.run.failure.code == "ncc_nothing_ticked"
        unknown = _run(runtime, config, {"station": "不存在站", "transmitter": True}, "unknown")
        assert unknown.run.failure is not None
        assert unknown.run.failure.code == "workflow_choice_unavailable"


def test_a_failed_draft_does_not_fail_the_run(tmp_path: Path) -> None:
    class Broken:
        def save(self, draft: MailDraft) -> object:
            raise DraftError("outlook_missing")

    config, runtime = _runtime(tmp_path, Broken, _files(tmp_path))
    with runtime:
        result = _run(
            runtime,
            config,
            {"station": "公館站", "transmitter": True, "draft_to": ["a@example.com"]},
            "broken",
        )
        assert result.run.status == "succeeded", result.run.failure
        _, rendered, drafted = (step.data for step in result.step_results)
        assert rendered["written"] is True
        assert drafted == {**drafted, "drafted": False, "error": "outlook_missing"}


def test_missing_settings_an_absent_folder_and_a_word_lock_are_refused(tmp_path: Path) -> None:
    config, runtime = _runtime(tmp_path / "unset", None, None)
    with runtime:
        unset = _run(runtime, config, {"station": "公館站", "transmitter": True}, "unset")
        assert unset.run.failure is not None
        assert unset.run.failure.code == "workflow_settings_incomplete"

    settings = _files(tmp_path)
    absent = {**settings, "output_dir": str(tmp_path / "not-there")}
    config, runtime = _runtime(tmp_path / "absent", None, absent)
    with runtime:
        refused = _run(runtime, config, {"station": "公館站", "transmitter": True}, "absent")
        assert refused.run.failure is not None
        assert refused.run.failure.code == "ncc_output_dir_missing"
    assert not (tmp_path / "not-there").exists()  # named, not created

    plan = prepare_plan(
        NccPlanRequest.model_validate({**settings, "station": "公館站", "transmitter": True})
    )
    locked = Path(plan.output_path)
    locked.write_bytes(b"open in Word")
    os.chmod(locked, stat.S_IREAD)
    try:
        from capabilities.ncc_plan.document import DocumentError

        with pytest.raises(DocumentError, match="document_open_in_word"):
            render_plan(plan)
    finally:
        os.chmod(locked, stat.S_IWRITE | stat.S_IREAD)
    assert locked.read_bytes() == b"open in Word"  # nothing was changed


def test_one_declaration_generates_every_form() -> None:
    manifest = plan_workflow()
    web = {field["name"]: field for field in form_fields(manifest, "web")}
    assert web["dry_run"]["order"] < web["station"]["order"]  # deciding to preview comes first
    assert "catalogue_file" not in web
    assert [field["name"] for field in settings_fields(manifest)] == [
        "catalogue_file",
        "template_file",
        "output_dir",
        "photo_dir",
    ]
    schema = agent_tool_schema(manifest)
    assert "catalogue_file" not in schema["properties"]
    assert schema["required"] == ["station"]
    state = flow.start(manifest, "write", lambda _m, _s, _a: ["公館站", "四條溝站"])
    assert isinstance(state, flow.FlowState)
    station = flow.begin(state)  # Telegram asks the required field first
    assert station.prompt is not None
    assert station.prompt.buttons == [[("公館站", "公館站"), ("四條溝站", "四條溝站")]]
    following = flow.answer(state, "公館站")
    assert following.prompt is not None
    assert following.prompt.buttons == [[("Yes", "yes"), ("No", "no")]]  # dry run


@pytest.mark.skipif(
    not (SOURCE_ROOT / "ncc_paper").is_dir()
    or not (SOURCE_ROOT / "config/workflow-14.json").is_file(),
    reason="the source clone and its uncommitted NCC documents are not on this machine",
)
def test_parity_with_the_source_job_on_the_real_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same catalogue and template through the source job and through AEP
    give the same document text. Writes only under tmp_path."""
    monkeypatch.syspath_prepend(str(SOURCE_ROOT / "host-bridge"))
    for name in [key for key in sys.modules if key == "jobs" or key.startswith("jobs.")]:
        monkeypatch.delitem(sys.modules, name)
    import jobs.ncc_improvement_plan as job  # type: ignore[import-not-found]
    from jobs import _steps  # type: ignore[import-not-found]

    catalogue_file = SOURCE_ROOT / "config/workflow-14.json"
    catalogue = json.loads(catalogue_file.read_text(encoding="utf-8-sig"))
    template = SOURCE_ROOT / catalogue["paths"]["template"]
    station = catalogue["stations"][0]["station"]
    source_out, aep_out = tmp_path / "source", tmp_path / "aep"
    source_out.mkdir()
    aep_out.mkdir()

    def defaults(_log: Any = None) -> dict[str, Any]:
        out = {
            f"_{key}": catalogue.get(key)
            for key in (
                "document",
                "prices",
                "systems",
                "serviceSystems",
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
        }
        out["_paths"] = {"template": str(template), "outputDir": str(source_out)}
        return out

    monkeypatch.setattr(job, "load_file_defaults", defaults)
    monkeypatch.setattr(job, "publish_reference_sets", lambda *args, **kwargs: {})
    ticks = {"transmitter": True, "aircon": True, "ups": True}
    token = _steps.attach(lambda _m: None, job.STEPS)
    try:
        source = job.run(
            {"station": station, "confirmDate": "115/06/07", **ticks}, log=lambda _m: None
        )
    finally:
        _steps.detach(token)

    plan = prepare_plan(
        NccPlanRequest.model_validate(
            {
                "catalogue_file": str(catalogue_file),
                "template_file": str(template),
                "output_dir": str(aep_out),
                "station": station,
                "confirm_date": "115/06/07",
                **ticks,
            }
        )
    )
    rendered = render_plan(plan)
    assert plan.output_name == Path(source["output"]).name
    assert plan.total == source["total"]
    assert _texts(Path(rendered.output or "")) == _texts(Path(source["output"]))


@pytest.mark.skipif(
    not (SOURCE_ROOT / "host-bridge/jobs/_ncc_rules.py").is_file(),
    reason="the source clone is not on this machine",
)
def test_the_rules_are_the_source_module_with_only_its_imports_modernised() -> None:
    source = (SOURCE_ROOT / "host-bridge/jobs/_ncc_rules.py").read_text(encoding="utf-8")
    ported = (Path(__file__).resolve().parents[1] / "src/capabilities/ncc_plan/rules.py").read_text(
        encoding="utf-8"
    )
    expected = source.replace("\r\n", "\n").replace(
        "from typing import Any, Iterable, Mapping, Sequence\n",
        "from collections.abc import Mapping, Sequence\nfrom typing import Any\n",
    )
    assert ported == expected
