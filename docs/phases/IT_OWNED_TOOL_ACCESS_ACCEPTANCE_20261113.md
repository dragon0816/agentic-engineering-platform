# IT-owned tool access: implementation acceptance

Date: 2026-11-13. Branch: `it-owned-tool-access-20261112`.
Later clarification: no IT approval/identity/managed allowlist is required. This
historical phase filename is retained as an identifier, not a permission system.
Authorization: the owner's explicit consent to the four harness changes in
`IT_OWNED_TOOL_ACCESS_DESIGN_20261112.md`, recorded in DECISIONS. This report
covers local implementation and verification, not deployment to the resident.

## Resulting behavior

- Installed tools are discovered independently of per-tool grants or profile
  capability selections. Skill/Knowledge selection still selects guidance and
  grounded sources. Exact profile versions and model eligibility remain valid.
- Bridge, MCP and conversation backends share typed discovery/invocation.
  Installation/connection refreshes tools in the current session. Missing
  software, credentials, unsupported resources and source-service errors remain
  actual failures, not fabricated success or AEP approval requests.
- AEP no longer requires tool installation/execution cards, mail sender/folder
  allowlists, command/folder admission lists, schedule grants, or local BI code
  hash approval. Legacy approval/review records remain historical; they are not
  silently approved or replayed. Local draft installation does not assert
  business correctness or shared publication approval.
- Successful effects have receipts and a common async execution lease, including
  native threads and delegated calls. Repeated calls return the earlier result.
  Failed/pending calls are not marked successful. Workflow verification remains
  tied to the tested digest; display receipts never establish verification.
- Generic native tool invocation preserves the existing model-data boundary:
  unknown result eligibility returns execution metadata and an explicit withheld
  data diagnostic, not arbitrary raw company content. This is separate from
  tool execution permission. No new model-data classification exemption exists.
- Outlook draft and send remain distinct actions. Search/body pagination is
  explicit, so a partial search is not presented as a complete mail thread.

## Verification and first-result history

Machine-readable case reconciliation, source hashes, raw-report hashes and wheel
provenance are in `IT_OWNED_TOOL_ACCESS_VERIFICATION_20261113.json`. Raw logs/XML
remain locally in `.scratch/it-owned-verification/`; they are not company data
exports and are not part of the source delivery.

| Check | Actual result |
| --- | --- |
| Initial full suite | 6682 passed, 37 failed, 15 skipped; 8390.40 seconds |
| Final core full suite | 6724 passed, 2 failed, 15 skipped; 7933.08 seconds |
| Current BI-local component | 55 passed; 166.55 seconds |
| Corrected long-destination-path fixture | 1 passed at short root and 1 passed at deep root; 4.01 seconds each |
| Knowledge conversation module at short root | 6 passed; 24.51 seconds |
| Current collection reconciled against named reports | 6726 passed, 15 skipped, no unresolved failed case; **combined evidence, not one green full run** |
| Exact Knowledge baseline comparison | Same 445 case IDs/outcomes after the named fixture rerun; no missing cases |
| Ruff check / format | Passed / 1481 files formatted |
| Mypy, configured src and tests | 1117 source files passed |
| Build / pip check | sdist and wheel built; no broken requirements |
| Isolated wheel installation/import | Passed; 571 Python files match current source after newline normalization |
| Required independent source review | No remaining Critical or Important findings, including focused BI delta review |

The first 37 failures were investigated, not erased. Obsolete admission assertions
were replaced with actual output, side-effect count, authentication, history,
source/citation and real-dependency failure assertions. Real Skill-version,
profile activation, receipt, concurrent execution and replay-digest defects were
fixed with causal failing/passing cases. The ledger preserves the sequence.

The final two failures came from the deliberately deep pytest temporary root:

1. The long-path Knowledge test failed while creating its source fixture, before
   AEP import. Its source now uses a normal short temporary directory; the
   destination still exceeds 260 characters and all Raw, publication, read and
   digest assertions remain. Both deep and short root reruns pass.
2. The conversation test reached the existing generic atomic session writer at a
   Win32 path exceeding 260 characters and disconnected. Both baseline and
   current atomic writers reproduce the same FileNotFoundError at that path;
   `workspace.py` and `authoring_task.py` are unchanged from base394ca4d2, and the
   same pre-existing conversation observation invokes them. No session-state
   harness expansion was made. All six current conversation cases pass at a
   normal short root. **The long workspace persistence limitation remains.**

Three BI runtime/UI modules and their three test modules changed after the core
full snapshot, plus the Knowledge test fixture above. Hash reconciliation proves
all other frozen code/fixtures unchanged, and web-page code outside the BI tools
rendering function unchanged. The dedicated 55-case BI run validates that
component; the older full run is not claimed as its proof. All current collected
cases are accounted for; three JWT fixture IDs contain collection-time expiry
timestamps and are matched by their parameterized family/count. The exact 445
Knowledge baseline comparison does not use this normalization.

## 使用方式與邊界

更新到本分支實作後，使用者可直接在對話說明工作，例如「找出這封郵件的
往來內容並整理待辦」或「安裝並連接這個 MCP，再用它處理附件」。Agent 可
探索已安裝工具、連接工具並在同一 session 呼叫，AEP 不再要求工具授權卡。
工具在執行環境能實際執行就可使用，AEP 不要求 IT 核准、IT 身分或管理名單；
缺少軟體、登入失敗或來源系統拒絕時，回報實際錯誤。
資料是否能交給所選模型，仍依既有資料規則判斷；原生後端若只收到執行摘要，
應呈現資料未放行的原因，不能宣稱已讀取或分析完整內容。

Tests use fake mailboxes/providers/MCP services and inert subprocesses. They do
not prove live Outlook COM behavior, live mail-thread completeness, actual mail
sending, arbitrary third-party installation, C4C operation, or stochastic model
answer quality. Native provider/IT permission guards are not bypassed. Existing
legacy native content paths and independent provider tools are not a newly
certified end-to-end data-egress isolation boundary.

Main, resident AEP, shared Gateway configuration, and the previously accepted
C4C distribution were not updated. This branch is locally committed; deployment
and a replacement end-user package are separate delivery steps.

## Wording clarification follow-up

Owner:「不用保留IT，在電腦上可以執行，就可以用」. No IT gate existed; the
follow-up aligns UI, prompt/Skill/audit wording and current requirements. All11
changed Python ASTs are identical except string literals; no execution branch,
Knowledge or model-data rule changed. The preceding full-suite evidence describes
the accepted pre-clarification tree; no new full run is claimed for this copy edit.

Follow-up focused run:92passed1failed2skipped107.65s. The unchanged subprocess
deadline case took2.062s against its<2s assertion; its entire7-case module passed
on rerun9.39s without changing assertions. The timing cause was not independently
proved. Combined focused evidence93passed2skipped. Ruff/format1482/mypy1117,
pipcheck and rebuilt sdist/wheel pass; all571wheel Python sources match the new
tree after newline normalization. Details/hashes:
`DIRECT_TOOL_USE_CLARIFICATION_20261113.json`. Resident remains unchanged.
