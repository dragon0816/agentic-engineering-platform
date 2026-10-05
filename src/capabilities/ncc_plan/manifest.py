"""Workflow 14 (rs_workflow_system ncc_improvement_plan): capabilities, Workflow, Skill.

One parameter declaration generates the Agent Web form, the settings page,
the Telegram questions and the Agent tool schema. Per-install settings name
the catalogue (the source's `config/workflow-14.json`), the template, the
output folder and the photo folder; a run picks the station, the channels,
the ticked systems, the dates and who gets the draft.
"""

from agent.skills import SkillManifest
from capabilities.contracts import CapabilitySpec
from capabilities.mail_draft.handlers import DRAFT_SPEC
from common.assets import AssetIdentity, WorkflowManifest

WORKFLOW = AssetIdentity(namespace="engineering", name="rs-ncc-improvement-plan", version="1.0.0")
SKILL = AssetIdentity(namespace="engineering", name="rs-ncc-improvement-plan-skill",
                      version="1.0.0")
STATIONS_FUNCTION = "ncc_plan.stations"

PREPARE_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "ncc-plan", "name": "prepare", "version": "1.0.0"},
        "name": "ncc_plan.prepare",
        "description": "Resolve one NCC improvement plan from the catalogue; writes nothing",
        "input_contract": "ncc-plan.prepare.input.v1",
        "output_contract": "ncc-plan.prepare.output.v1",
        "side_effect": "read",
        "policy": {
            "required_permissions": ["ncc-plan.prepare"],
            "policy_refs": ["ncc-plan-policy"],
        },
    }
)

RENDER_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "ncc-plan", "name": "render", "version": "1.0.0"},
        "name": "ncc_plan.render",
        "description": "Write the resolved NCC improvement plan as a .docx in the output folder",
        "input_contract": "ncc-plan.render.input.v1",
        "output_contract": "ncc-plan.render.output.v1",
        "side_effect": "write",
        "policy": {
            "risk": "low",
            "approval_required": True,
            "required_permissions": ["ncc-plan.render"],
            "policy_refs": ["ncc-plan-policy"],
        },
    }
)

#: 表一's eleven systems, in the source's order and wording.
_SYSTEMS = (
    ("transmitter", "1. 發射/補隙系統"),
    ("amplifier", "2. 訊號放大器系統"),
    ("mixer", "3. 混頻系統"),
    ("satDecoder", "4. 衛星解碼系統"),
    ("satAntenna", "5. 衛星天線"),
    ("gpsAntenna", "6. GPS接收天線"),
    ("dvbtAntenna", "7. DVB-T接收/發射天線"),
    ("aircon", "8. 空調系統"),
    ("voltageStabiliser", "9. 穩壓系統"),
    ("ups", "10. 不斷電系統"),
    ("isolationTransformer", "11. 隔離變壓系統"),
)

_SETTINGS = [
    {"name": "catalogue_file", "label": "目錄檔（workflow-14.json）", "kind": "file",
     "scope": "static", "required": True, "accept": [".json"], "order": 1,
     "help": "站台、價目、系統與文句的 JSON 檔，格式同 rs_workflow_system 的 "
             "config/workflow-14.json；只讀內容區段，不讀 paths/ops。"},
    {"name": "template_file", "label": "範本 .docx", "kind": "file", "scope": "static",
     "required": True, "accept": [".docx"], "order": 2,
     "help": "當作範本的範例改善服務規劃。"},
    {"name": "output_dir", "label": "輸出資料夾", "kind": "folder", "scope": "static",
     "required": True, "order": 3,
     "help": "產出的 .docx 放這裡；資料夾必須已存在，不會自動建立。"},
    {"name": "photo_dir", "label": "站台照片根目錄", "kind": "folder", "scope": "static",
     "order": 4,
     "help": "底下一站一個資料夾，檔名用頻道代號（外觀.jpg、CH24.jpg）。留空就不檢查。"},
]

_RUN = [
    {"name": "dry_run", "label": "只試跑，先看內容？", "kind": "boolean", "default": False,
     "order": 8, "help": "列出這份文件會寫什麼，不產生檔案、不建草稿。"},
    {"name": "station", "label": "要做哪一個改善站？", "kind": "select", "required": True,
     "choices_source": f"fn:{STATIONS_FUNCTION}", "group": "identity", "order": 10},
    {"name": "channels", "label": "這次要改善哪些頻道？", "kind": "text", "order": 40,
     "help": "用逗號分隔，例如 CH26,CH28。留空就用這一站的設定。"},
    {"name": "confirm_date", "label": "權責機關哪一天確認有改善需求？", "kind": "text",
     "order": 60, "help": "民國年，例如 115/06/07。"},
    {"name": "completion_date", "label": "預計完成日期？", "kind": "text", "order": 70,
     "help": "民國年，例如 115/09/30；留空用目錄檔的設定。"},
    {"name": "draft_to", "label": "要把文件寄到哪個信箱？", "kind": "emails", "order": 75,
     "help": "只建 Outlook 草稿，不會寄出；留空就不建。"},
    *[
        {"name": name, "label": label, "kind": "boolean", "default": False,
         "group": "systems", "order": 200 + 10 * index}
        for index, (name, label) in enumerate(_SYSTEMS)
    ],
]

_METADATA = {
    "owner": {"type": "team", "id": "engineering"},
    "visibility": "organization",
    "lifecycle": "published",
}


def _mail_input(field: str) -> dict[str, object]:
    return {"source": "step", "step_index": 0, "path": ["mail", field]}


def plan_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": WORKFLOW.model_dump(), **_METADATA},
            "kind": "workflow",
            "run_alias": 14,
            "description": (
                "Workflow 14: write one station's 改善服務規劃 .docx from the template and "
                "the catalogue, and optionally save an Outlook draft with it attached "
                "(never sent). A dry run lists what the document will say and writes nothing."
            ),
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": [PREPARE_SPEC.name, RENDER_SPEC.name, DRAFT_SPEC.name],
            },
            "parameters": [*_SETTINGS, *_RUN],
            "progress_steps": [
                {"id": "prepare", "title": "讀目錄並依勾選算金額"},
                {"id": "render", "title": "寫 .docx"},
                {"id": "draft", "title": "建 Outlook 草稿", "optional": True},
            ],
            "input_contract": "engineering.rs-ncc-improvement-plan.input.v1",
            "output_contract": "outlook.draft.output.v1",
            "steps": [
                {"capability": PREPARE_SPEC.identity.model_dump(),
                 "inputs": {"request": {"source": "run"}}},
                {"capability": RENDER_SPEC.identity.model_dump(),
                 "inputs": {"plan": {"source": "step", "step_index": 0}}},
                {"capability": DRAFT_SPEC.identity.model_dump(),
                 "inputs": {
                     field: _mail_input(field)
                     for field in ("skip", "subject", "html_body", "to", "cc",
                                   "attachments", "best_effort")
                 }},
            ],
        }
    )


def plan_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {"identity": SKILL.model_dump(), **_METADATA},
            "alias": "ncc",
            "instructions": (
                "Write an NCC 改善服務規劃 for one station with Workflow 14. Ask which station, "
                "which systems need work and who should get the draft; offer a dry run first."
            ),
            "commands": [{"name": "plan", "kind": "workflow", "target": WORKFLOW.model_dump()}],
            "default_command": "plan",
        }
    )
