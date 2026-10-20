"""Workflows 06 and 06b (rs_workflow_system loan_scan / loan_process) as two
AEP Workflows, their capabilities and a Skill.

- `engineering/rs-loan-customer-block-scan` (06, `/run 6`): read the inbox
  for 簽核通知 with a FastView `DR…` link and queue one item per borrow number.
- `engineering/rs-loan-queue-reply` (06b): for each queued form read the
  customer off the loan portal, check C4C's delivery blocks, and save the
  reply (or an internal notice) as an Outlook **draft**. Optionally, one send
  card per draft: each send is its own press in Agent Web.

They ship **switched off** (`host_runtime.assets.shipped_off`): they serve one
team's loan desk, need that team's portal and C4C access, and write
customer-facing drafts. No schedule is created; the person may add one in
Agent Web > Schedules (docs/phases/RS_WORKFLOW_MIGRATION.md).
"""

from agent.skills import SkillManifest
from capabilities.contracts import CapabilitySpec
from capabilities.loan_reply.handlers import CONSUMER
from common.assets import AssetIdentity, WorkflowManifest

SCAN_WORKFLOW = AssetIdentity(
    namespace="engineering", name="rs-loan-customer-block-scan", version="1.0.0"
)
REPLY_WORKFLOW = AssetIdentity.model_validate(CONSUMER)
SKILL = AssetIdentity(namespace="engineering", name="rs-loan-reply", version="1.0.0")

_POLICY = ["loan-reply-policy"]


def _spec(name: str, description: str, side_effect: str, **policy: object) -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": {"namespace": "loan", "name": name, "version": "1.0.0"},
            "name": f"loan.{name}",
            "description": description,
            "input_contract": f"loan.{name}.input.v1",
            "output_contract": f"loan.{name}.output.v1",
            "side_effect": side_effect,
            "policy": {
                "required_permissions": [f"loan.{name}"],
                "policy_refs": _POLICY,
                **policy,
            },
        }
    )


#: Producer, read: the Outlook folder, parsed; nothing is written.
SCAN_SPEC = _spec(
    "scan-mail",
    "Read loan approval notices from one Outlook folder and decide which borrow "
    "numbers to queue; writes nothing",
    "read",
)
#: Producer, write: the local queue in this host's workspace.
ENQUEUE_SPEC = _spec(
    "enqueue",
    "Add the decided borrow numbers to this computer's loan queue (one item per "
    "borrow number; a known number is never added twice)",
    "write",
    risk="low",
    approval_required=True,
)
#: Consumer, read: the loan portal and C4C in this computer's Edge profiles.
LOOK_UP_SPEC = _spec(
    "look-up",
    "Open each queued loan form in the loan portal and read the customer's "
    "delivery blocks in C4C; claims nothing and writes no mail",
    "read",
)
#: Consumer, write: Outlook drafts (never sent) and the queue's state.
DRAFT_SPEC = _spec(
    "draft-replies",
    "Save each form's reply or internal notice as an Outlook draft (never sent) "
    "and mark the queue item done or failed",
    "write",
    risk="medium",
    approval_required=True,
)
#: Consumer, write: one send card per draft, in this host's card store.
OFFER_SPEC = _spec(
    "offer-send",
    "When asked, show one send card per saved draft; sends nothing",
    "write",
    risk="low",
    approval_required=True,
)
#: The send itself. Declared for policy and review, and deliberately never
#: installed as a capability: no Workflow step, tool or model can call it. It
#: runs only from a person's Send press on one card
#: (`host_runtime.loan_reply_cards.LoanReplyCards.decide`).
SEND_SPEC = _spec(
    "send-reply",
    "Send one reviewed loan reply draft from Outlook after the person pressed Send on its card",
    "external_side_effect",
    risk="high",
    approval_required=True,
)

_METADATA = {
    "owner": {"type": "team", "id": "engineering"},
    "visibility": "organization",
    "lifecycle": "published",
}


def _step(spec: CapabilitySpec, inputs: dict[str, object]) -> dict[str, object]:
    return {"capability": spec.identity.model_dump(), "inputs": inputs}


def scan_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": SCAN_WORKFLOW.model_dump(), **_METADATA},
            "kind": "workflow",
            "run_alias": 6,
            "description": (
                "Workflow 06: read the inbox for loan approval notices (簽核通知 with a "
                "FastView DR… link) and queue one item per borrow number for "
                "rs-loan-queue-reply. Rejections (否決), excluded categories and known "
                "numbers are skipped; a dry run lists what would be queued and writes nothing."
            ),
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": [SCAN_SPEC.name, ENQUEUE_SPEC.name],
            },
            "parameters": [
                {
                    "name": "mail_folder",
                    "label": "要掃描的 Outlook 資料夾",
                    "kind": "text",
                    "scope": "static",
                    "default": "Inbox",
                    "order": 1,
                    "help": "例如 Inbox 或 Inbox/借用單；預設收件匣。",
                },
                {
                    "name": "max_messages",
                    "label": "一次最多看幾封信",
                    "kind": "integer",
                    "scope": "static",
                    "default": 200,
                    "minimum": 1,
                    "maximum": 2000,
                    "order": 2,
                },
                {
                    "name": "process_from",
                    "label": "只處理這個時間之後收到的信",
                    "kind": "text",
                    "scope": "static",
                    "order": 3,
                    "help": "例如 2026-08-11 09:00。留空＝第一次正式執行的時間（之前的信"
                    "可能已人工回覆過，不再處理）。",
                },
                {
                    "name": "require_sender",
                    "label": "只接受指定寄件者的簽核通知",
                    "kind": "boolean",
                    "scope": "static",
                    "default": False,
                    "order": 4,
                },
                {
                    "name": "sender_smtp",
                    "label": "指定的寄件者信箱",
                    "kind": "text",
                    "scope": "static",
                    "order": 5,
                    "help": "上一項打開才用；HQ 與本地系統的寄件信箱不同，不確定就留空。",
                },
                {
                    "name": "exclude_categories",
                    "label": "不處理的借用單類別代碼",
                    "kind": "text_list",
                    "scope": "static",
                    "order": 6,
                    "help": "例如 S；留空＝所有類別（一般、HQ、L 專用、S 及新類別）。",
                },
                {
                    "name": "dry_run",
                    "label": "只試跑，先看會排入哪些借用單？",
                    "kind": "boolean",
                    "default": False,
                    "order": 10,
                    "help": "列出會排入佇列的借用單，不寫入佇列。",
                },
                {
                    "name": "process_from_once",
                    "label": "這次從什麼時間收到的信開始？（只影響這一次）",
                    "kind": "text",
                    "order": 20,
                    "help": "例如 2026-08-11 09:00；留空用設定或第一次執行的時間。",
                },
            ],
            "progress_steps": [
                {"id": "scan", "title": "讀收件匣找簽核通知"},
                {"id": "enqueue", "title": "排入佇列"},
            ],
            "input_contract": "engineering.rs-loan-customer-block-scan.input.v1",
            "output_contract": "loan.enqueue.output.v1",
            "steps": [
                _step(SCAN_SPEC, {"request": {"source": "run"}}),
                _step(ENQUEUE_SPEC, {"scan": {"source": "step", "step_index": 0}}),
            ],
        }
    )


def reply_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {"identity": REPLY_WORKFLOW.model_dump(), **_METADATA},
            "kind": "workflow",
            "description": (
                "Workflow 06b: for each queued loan form, read the customer off the loan "
                "portal, check C4C's delivery blocks and save the reply on the approval "
                "notice (or an internal notice) as an Outlook draft; never sends. "
                "Optionally one send card per draft, each sent only by its own press."
            ),
            "execution": {"mode": "local"},
            "dependencies": {
                "central_required": False,
                "local_capabilities": [LOOK_UP_SPEC.name, DRAFT_SPEC.name, OFFER_SPEC.name],
            },
            # Two Edge profiles and Outlook: not alongside another such run.
            "occupies_machine": True,
            "parameters": [
                {
                    "name": "alert_recipient",
                    "label": "內部通知寄給誰",
                    "kind": "emails",
                    "scope": "static",
                    "order": 1,
                    "help": "C4C 查不到客戶或流程失敗時，內部通知草稿的收件者。",
                },
                {
                    "name": "template_dir",
                    "label": "回信範本資料夾",
                    "kind": "folder",
                    "scope": "static",
                    "order": 2,
                    "help": "放 blocked-reply.txt 等檔案即可改信件文字；留空用內建文字。",
                },
                {
                    "name": "portal_origin",
                    "label": "出借系統網址",
                    "kind": "text",
                    "scope": "static",
                    "default": "https://rstw-portal.rsint.net",
                    "order": 3,
                    "help": "信裡的連結只有指向這個網站才會開啟。",
                },
                {
                    "name": "c4c_home_url",
                    "label": "C4C 首頁網址",
                    "kind": "text",
                    "scope": "static",
                    "order": 4,
                    "help": "留空用 SAP C4C 的預設首頁。",
                },
                {
                    "name": "loan_account",
                    "label": "出借系統登入時要選的公司帳號",
                    "kind": "text",
                    "scope": "static",
                    "order": 5,
                    "help": "Microsoft 帳號選擇畫面上的 email；留空選第一個。不需要密碼。",
                },
                {
                    "name": "close_browsers_after",
                    "label": "做完關閉瀏覽器",
                    "kind": "boolean",
                    "scope": "static",
                    "default": True,
                    "order": 6,
                },
                {
                    "name": "show_browser",
                    "label": "顯示瀏覽器視窗",
                    "kind": "boolean",
                    "scope": "static",
                    "default": True,
                    "order": 7,
                    "help": "第一次登入時請保持打開。",
                },
                {
                    "name": "settle_ms",
                    "label": "每個畫面等待（毫秒）",
                    "kind": "integer",
                    "scope": "static",
                    "default": 2500,
                    "minimum": 0,
                    "maximum": 60000,
                    "order": 8,
                },
                {
                    "name": "busy_timeout_ms",
                    "label": "C4C 忙碌最多等（毫秒）",
                    "kind": "integer",
                    "scope": "static",
                    "default": 25000,
                    "minimum": 1000,
                    "maximum": 300000,
                    "order": 9,
                },
                {
                    "name": "nav_timeout_ms",
                    "label": "開網頁最多等（毫秒）",
                    "kind": "integer",
                    "scope": "static",
                    "default": 90000,
                    "minimum": 5000,
                    "maximum": 600000,
                    "order": 10,
                },
                {
                    "name": "dry_run",
                    "label": "只試跑？",
                    "kind": "boolean",
                    "default": False,
                    "order": 20,
                    "help": "會讀出借系統與 C4C，但不建草稿、不動佇列。",
                },
                {
                    "name": "max_items",
                    "label": "這次處理幾筆？",
                    "kind": "integer",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 20,
                    "order": 30,
                },
                {
                    "name": "offer_send",
                    "label": "草稿建好後，每封各給一張「寄出」確認卡？",
                    "kind": "boolean",
                    "default": False,
                    "order": 40,
                    "help": "每封都要你在 Agent Web 親自按一次「寄出」才會寄；不按就留在草稿匣。",
                },
            ],
            "progress_steps": [
                {"id": "look-up", "title": "讀出借系統與 C4C"},
                {"id": "draft", "title": "建 Outlook 草稿"},
                {"id": "offer", "title": "寄出確認卡", "optional": True},
            ],
            "input_contract": "engineering.rs-loan-queue-reply.input.v1",
            "output_contract": "loan.offer-send.output.v1",
            "steps": [
                _step(LOOK_UP_SPEC, {"request": {"source": "run"}}),
                _step(DRAFT_SPEC, {"lookups": {"source": "step", "step_index": 0}}),
                _step(OFFER_SPEC, {"drafts": {"source": "step", "step_index": 1}}),
            ],
        }
    )


def loan_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {"identity": SKILL.model_dump(), **_METADATA},
            "alias": "loan",
            "selector_hint": (
                "展示機出借 借用單 DR 簽核通知 delivery block 配送限制 回信草稿 loan reply"
            ),
            "instructions": (
                "Answer demo-unit loan approvals with two Workflows. `scan` runs "
                "engineering/rs-loan-customer-block-scan: it queues one item per borrow "
                "number from the inbox. `reply` runs engineering/rs-loan-queue-reply: it "
                "reads each queued form and C4C and saves Outlook drafts; never sends. "
                "Offer a dry run first. Sending is only the person's own press on each "
                "send card in Agent Web; never say a mail was sent unless a card says so."
            ),
            "commands": [
                {"name": "scan", "kind": "workflow", "target": SCAN_WORKFLOW.model_dump()},
                {"name": "reply", "kind": "workflow", "target": REPLY_WORKFLOW.model_dump()},
            ],
            "default_command": "scan",
        }
    )
