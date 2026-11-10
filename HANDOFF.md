# Active handoff: delivered runtime and C4C novice evaluation

Date: 2026-11-11. Branch: main. Local commits only; no push.

## Goal and owner constraints

The owner wants a novice to give the original short C4C sales-order request,
Sales_order.pdf and Downloads/Sales name and Dept.xlsx, then have AEP clarify
only missing business decisions, develop and trial a reusable workflow, and
independently reconcile its Excel with the source. A successful engine status or
nonempty workbook is insufficient. Do not supply business scripts, selectors or
an old graph to force the novice test to pass.

AGENTS rule22 requires Skill-first evidence and explicit scoped owner consent
BEFORE every harness change. A general feature request is not that consent.
Only the Knowledge intake/state/completion isolation correction received scoped
consent; no further C4C harness changes, retry expansion or business branches are
authorized. Query/export and local Excel are authorized, no C4C order mutations
or mail. Final Workflow installation still requires owner approval.

## Delivered runtime

- b0cded20: Skill-first harness governance in repository instructions/skills.
- 8cde171f: bounded metadata-only Claude Code/Codex model catalogs, backend-scoped
  selection/persistence and actual model forwarding. No native inference/login
  during catalog discovery; Codex agent mode and data permissions unchanged.
- 47f28a6b3764fe1ffde9c9ff69bd4ebbb91fb657: Knowledge queries preserve pending
  workflow questions/budget/proof, while actual authoring still enforces trials
  and approvals. Existing Knowledge retrieval/citations/routes are unchanged.
  Attachment data does not become user intent, but metadata/bytes/history remain.

Runtime source is frozen and delivered. Only documentation changed afterward.
Official offline bundle:
.scratch/knowledge-isolation-offline-bundle/aep-windows-preview-0.1.0-47f28a6b3764.zip
SHA256 c5b2660b410f80c9906f8d5ba2162fe52b8e50213878fca95604abd94b218aa7.
Build, clean canary install/doctor/pipcheck/Agg, installed source paths and all559
Python-file bytes passed independent checks. Resident official updater preserved
semantic config and installed this revision; port53583, actor leo.chi,
Bridge bridge-tp401555. Read fresh agent-web.json privately for auth/PID; never
print token/address. A later guarded restart loaded the approved C4C Skill.
Proofs: knowledge-isolation-canary-proof.json,
knowledge-isolation-resident-update-proof.json,
knowledge-isolation-resident-verification.json under .scratch.

Always use .venv/Scripts/python.exe for project checks (system Python has an ABI
mismatch). Launch the resident with its INSTALLED .venv/Scripts/aep-host.exe,
hidden; never the development launcher. Before any restart freshly check active
turns/tasks/questions/forms/approvals and actual PID ownership. Do not interrupt
the active C4C conversation or kill unrelated browser/gateway/CLI processes.

## Verification evidence and limits

Native focused167 and legacy UI/model20 passed. Knowledge focused171 passed
(44new+127existing), final independent review clear. Ruff,1438 format files,
mypy1087 files, pipcheck, build and diff checks passed.

Final normal full suite collected6587 items/551 modules in4 shards:
6572 passed,5 failed,10 skipped. All559 source files remained unchanged.
All4 initially failing whole modules rechecked unchanged:78 passed total
(NetworkClick11,WebScript60,MemberPortalTabs2,ChatWorkflowFormsWeb5).
This is NOT an initially clean full-suite result. Original causes remain partly
unproven: browser startup without published port, observation-lost refusal instead
of expected origin error, trigger consuming a .3s target budget, portal DOM
navigation_failed and chat Send not enabled within30s. Later assertions not
reached in failed tests are not claimed to have passed. One invalid long-path
forms diagnostic is retained separately; short C:/Temp recheck passed5/5.
Rollup: .scratch/knowledge-isolation-verification-rollup.json; raw final suite
logs/XML/result use knowledge-isolation-verified-20261110 prefix. No weakened
assertions, fixture changes or production patches were used for these failures.

Live installed Agent Web, own empty PUBLIC test session: Claude Code14 and
Codex8 model IDs visible/enabled with provider default, Send enabled; no inference
messages. Own conversation deleted and own named browser closed. Proof:
.scratch/knowledge-native-ui-proof.json.

Live Gateway synthetic workflow question followed by unrelated factual query:
actual pending report_currency task remained byteexact, no erroneous unfinished
trial warning, no authoring calls. Initial helper used a wrong task path and is
explicitly inconclusive; corrected proof uses authoring/chat/tasks. Own synthetic
session deleted. Proof: .scratch/knowledge-live-smoke/proof.json.

Graphify AST-only update completed without semantic/API labeling;46144 nodes,
137066 edges,2195 communities. Warnings were3 intentionally invalid generated
benchmark scripts, not production syntax. No new dependency.

## C4C evaluation history

Old engineering/c4c-sales-order-report1.0.1/1.0.2 was recoverably removed through
normal APIs; original files, previous reports/history retained. The older correct
report was heavily assisted and does not prove novice autonomy.

Round1: conversation-ee31cddf67774a1080b72c6bfcdc52df, exact original prompt/files.
AEP independently authored wf-20261110-134814-547e6d, self-repaired2 failed
trials, then run-206c751b36254547aea846ddd192f230 produced only11 orders and
claimed completeness without independent source totals. NOT accepted. Install
ap-20261110-145156-28e5a2 withdrawn/rejected; draft/report preserved.

Owner approved generic SOP Skill engineering/sop-workflow-development1.0.0,
alias sop_workflow, candidate sk-20261110-145833-7cd3e7, install card
ap-20261110-145903-047b14. Round2 conversation-942a6f8a767148869969e4640550afb7
actually selected it (telemetry proof). AEP independently authored
wf-20261110-153208-59d583 and repaired navigation, but all3 trials failed:
run-7a08aa6c830e444485fec61fb5f82bc2 and run-4b5bf77bb0cb4d4485e952398dc1c1d6
ensure_visible.trigger timeout; run-da3cbf0e7b7b4dfc92820baae7bf840b wait_for
timeout. Bounded evaluation stopped; no accepted Excel, no workflow install.
Evidence: .scratch/novice-sop-20261110 and novice-skill-sop-20261110.

## Approved domain Skill and current clean round3

The owner explicitly approved card ap-20261110-184948-7b7722 in this conversation.
Normal approval API installed engineering/sap-c4c-workflow-navigation1.0.1,
alias c4c_navigation, candidate sk-20261110-155444-ab60a7 revision2,
digest 8b8439bbbd3dc5d102d36cdda71490f6e524046a1c3e12811908379807ed1b48.
Version1.0.0/old digest is superseded. Fresh guarded installed-service restart
loaded it alongside generic SOP1.0.0. No harness changes. Proofs:
.scratch/c4c-domain-skill-owner-approval.json and c4c-domain-skill-loaded.json.
The Skill teaches layered menu/Sales/Sales Orders discovery, start-state checks,
actual schemas/roles and source-to-output validation; no company records/scripts.

Round3 FINISHED in conversation-e49586c9aec040aeacb0fe28ce720396.
Driver: .scratch/c4c_domain_sop_client.py; PTY55035 explicitly closed after3trials.
Evidence: .scratch/c4c-domain-sop-20261111/session.json,
latest-progress.json and result-*.json. Exact original simple prompt/files sent
ONCE; do not resend. Previous generated .aep-run code privately archived before
prompt, existing Excel outputs preserved. Telemetry trace
trace-6922085063b54ee8ab5b63a4b0fac2c8 confirms both c4c_navigation and
sop_workflow selected. AEP independently authored
engineering/sap-c4c-sales-orders-report1.0.0, candidate
wf-20261110-191957-9353bc, and self-repaired2failed trials without root hints.
All3 full trials FAILED, before the Excel step:
- run-425c7d12015040deaf15341574390b8a, digest352747f3...: actions[5]
  wait_for Sales Orders timed out, although actual list/search controls existed.
- run-1419db70f1824d14b324d24170e708cb, digestcf78a63d...: actions[8]
  wait_for bare All timed out with a decorated All(count) view control present.
- run-c66326871bc54d919200ad809d2a8473, digestb545a423...: actions[4]
  click refused as web_target_obscured. The specific occluder is not established.
No final Excel was produced/accepted and no Workflow was installed. Trial
approvals used the existing query/export/local-file grant only. Bounded repair
stopped; do not silently renew it. Authoritative safe rollup:
.scratch/c4c-domain-sop-20261111/evaluation.json, raw result-0..3.json retained.

## Approved Skill1.0.2 and completed round4 evaluation

Prepared through normal MCP creator APIs, check passed, submitted SAME candidate
sk-20261110-155444-ab60a7 revision3 as
engineering/sap-c4c-workflow-navigation1.0.2, digest
e99b639afcc8af2c572e781e20f5b7ea87b85e442641098615c271c2c11029f9.
The owner explicitly instructed「現在是測試，請直接同意使用」for this card.
Normal approval API approved ap-20261110-193334-b00427. Fresh idle/PID/config
guard preceded restart of the INSTALLED service; source/config unchanged.
Inventory confirmed1.0.2 and generic SOP1.0.0 loaded. No harness changes.

The revision requires discovery to test wait predicates with the same browser
action semantics as the graph, handles decorated/variable-count view labels,
and inspects actual occlusion/actionability before safe recovery. It forbids
force clicks, arbitrary JS/coordinates, guessing the occluder, borrowed generated
IDs, budget renewal or claiming an untested Excel. Previous domain/QA guidance
and capability commands are retained; no new grants/data/scripts/dependencies.
Proposal, check, submission, install request and behavioral evaluation cases:
.scratch/c4c-domain-sop-20261111/skill-1.0.2-*.json.
Format validation passed. Authentication recovered after the disclosed environment intervention; all3full navigation trials subsequently failed, before Excel acceptance.

## Round4 finished after owner login confirmation

Conversation-999662143d234cabb77786ee68b17c3e retained original prompt/PDF/Excel.
Driver .scratch/c4c_preflight_sop_client.py; PTY60833 and resumed57261 both closed.
Previous failed candidates/source were recoverably archived/removed, reports
retained. Skill1.0.2/generic SOP1.0.0 actually selected; no new Skill approval needed.
Evidence .scratch/c4c-preflight-sop-20261111, result-0..8.json and evaluation.json.

Owner confirmed「可以登入」. AEP still saw SAML assertion-consumed errors; readonly
metadata established an independent HEADLESS browser-profile versus normal Edge.
One open-without-reload contrast retained the same assertion ID. Root freshly
checked idle and exactly one SAML-error tab, then gracefully closed ONLY that
owned browser with the existing Browser API. Profile/login files preserved; no
cookies read/copied/deleted, no config/harness changes. auth-browser-reset.json.
AEP's next normal capability relaunched the browser and reached Home/Sales Orders.
Access recovered, server-side cause unproven. Disclose this environment intervention;
do not describe the full evaluation as zero-intervention. Root gave authentication
recovery instructions, but no business graph, selectors or processing scripts.

AEP independently selected All/prescribed dates, observed765records/26pages,
and authored engineering/c4c-sales-orders-export-excel1.0.0,
candidate wf-20261110-201153-ff4b99; currentrevision3,
digest4275da4378c38ef637f5d2d19a5b662e106598a4209d2a5ae6c1ca7c1e1613d4.
All3approved FULL TRIALS FAILED before Excel:
- run-cb7b32190da9402bb950e9583c031808: actions[2] ensure_visible target timeout.
- run-7cb2bf783a3542909df5687a1b3886c4: actions[4] click target missing.
- run-a64cebe6af7846789fe40864b1489517: actions[3] wait timeout.
AEP self-patched the first2 failures. Downstream merge/Python stayed byteexact;
only navigation changed. No accepted Excel or Workflow installation. Bounded
repair stopped, own driver closed. Trial cards approved under standing test grant.
One root snapshot-audit helper initially hit cp950 decoding; corrective UTF8 audit
confirmed downstream unchanged. Do not mistake that helper error for a product
failure or claim its failed check had passed before approval.

## Causal finding and next owner decision (NO implementation consent)

Automatic repair in src/host_runtime/web.py:1269 permits only browser inspection
and authoring tools, excluding browser__operate/coding__run. agent/gateway.py:990
filters tool schemas, bindings and hints before the model sees them. Therefore
Skill1.0.2 cannot grant live incremental browser preflight in that phase; full
approved Workflow trial validation remains possible. Existing capturing-model
regression explicitly asserts the absence and passed unchanged:1test/11.27s.
Command: .venv/Scripts/python.exe -m pytest
 tests/test_authoring_repair.py::test_failed_authoring_resumes_once_with_only_safe_tools_and_retests -q
Evidence repair-preflight-causal-proof.json (AST extraction/current sourcehash),
navigation-compilation-analysis.json (initial successful path not preserved;
third revision reused an earlier failed pair), evaluation.json. Initial drafting
also needs Skill improvement; preflight availability alone is no correctness proof.

Next concrete action: obtain owner's EXPLICIT scoped harness consent on
[proposal](docs/phases/AUTHORING_BROWSER_PREFLIGHT_PROPOSAL.md), then plan/contracts/
tests/implementation/verification. Proposed scope: govern browser preflight for
active matching candidate/digest/failed-step/origin, explicit model provenance,
normal Bridge approval, bounded requests and unchanged3full-trial limit; keep
coding/desktop/mail/install absent, no Knowledge or global permission changes.
Simply adding browser__operate to the allowlist is rejected: its current host
adapter defaults Bridge origin to person, so safe approval/provenance must be
preserved explicitly. If further continuation/state scope becomes necessary,
return with the concrete expansion for consent. No code/tests/policy edited.

Do not renew repair budgets or install the failed workflow to make the test pass.
SOP business facts remain: fixed2026-07-01..2027-06-30; ultimately confirmed
1TWD=0.02712085EUR (earlier no superseded), USD0.87EUR, EUR1. Original mapping
workbook is read-only. Future acceptance requires independent source-to-Excel
reconciliation, not nonempty output or writer input counts. No evaluation remains
running; never promise background continuation after a final reply.
