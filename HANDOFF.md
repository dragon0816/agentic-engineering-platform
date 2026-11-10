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

## Approved Skill1.0.2 and round4 authentication blockage

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
Format validation passed; navigation/workbook acceptance is inconclusive because round4 could not authenticate.

Round4 STOPPED: conversation-999662143d234cabb77786ee68b17c3e.
Driver .scratch/c4c_preflight_sop_client.py, PTY60833 explicitly closed.
Exact original prompt/PDF/Downloads workbook path sent ONCE. Previous3failed
candidates archived then removed through normal APIs; prior .aep-run source
archived, reports retained. No root business code or selector coaching.
Evidence .scratch/c4c-preflight-sop-20261111:
- clean-start-proof.json / restart-proof.json / skill-loaded.json
- skill-selection-proof.json confirms c4c_navigation and sop_workflow selected
- sso-entry-comparison.json proves URL byteexact same as earlier successful entry
- result-0..2.json retains actual model/tool evidence; evaluation.json safe rollup

AEP read the mapping workbook but opening the original SOP entry reached SAP
OpenID then SAML2 errors. Two natural followups supplied the known automatic SSO
fact and requested one actual fresh reopen (first recheck only inspected).
Final operation really called open+inspect_dom; still reported
CX_SAML20_ASSERTION: The assertion has already been consumed.
Initial OpenID correlation ID60280999-A0FE-40EF-840F-47B02F97B15E.
This is evidence of the current browser's authentication blockage, not proof of
the server-side cause. No login settings changed, no forced click/auth bypass,
no harness edits or repair-budget renewal. AEP preserved original SOP plan and
needs_input/authentication_required/c4c_sso_access. Zero full Workflow trials,
no new accepted Excel or installed Workflow. Resident activity idle after stop.

Next concrete action: ask owner to restore/confirm C4C login in AEP's Edge, then
resume THIS preserved conversation via the normal API with that new fact.1.0.2
already approved/loaded; do not ask to approve it again. Let AEP build/repair within
existing limits and approve exact trial cards under standing export/local-file
test grant. Final Workflow installation is separate and only after accepted
business output. Respond only to genuine business gaps: automatic SSO, fixed SOP
2026-07-01..2027-06-30; owner ultimately confirmed1TWD=0.02712085EUR (earlier no
superseded), USD0.87EUR, EUR1. Independently reconcile source and Excel. No
background evaluation remains running; do not promise background continuation.
