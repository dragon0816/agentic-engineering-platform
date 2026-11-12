# C4C low-risk integration and Windows package

Date: 2026-11-12. Working branch c4c-low-risk-20261112 in
C:/Users/Chi_L/.paseo/worktrees/2qnenase/c4c-low-risk-20261112.
Runtime source e69371e62ec2a01d31eead91f67ff9e4404a4254, based on 097b2521.
Original checkout/main, origin/main and running resident remain untouched.

## Owner scope

Integrate only safe numeric Outlook diagnostics, opt-in live Outlook tests and
queued-message feedback. Knowledge asking must not regress. Package this AEP
with the accepted Sales Order Workflow and related Skills plus Traditional
Chinese instructions. No new harness scope is authorized. Remote e564e1ad is
excluded: its text-only legacy projection can infer success without execution
provenance; assessment only in CHAT_WORKFLOW_PERSISTENCE_MERGE_REVIEW.md.

## Actual verification

- Baseline affected tests: 13 passed; baseline Knowledge: 445 passed.
- Integrated affected tests: 21 passed, 2 skipped; live Outlook/GUI disabled.
- Initial complete local run: 6619 passed, 13 skipped, 0 failures/errors,
  8453.20 seconds. Both failing CI BI cases passed locally.
- All 445 baseline Knowledge test identities and outcomes matched full.xml;
  eight Knowledge/model/evaluation source paths unchanged. This does not prove
  every stochastic real-model answer. No test/assertion/timeout was weakened.
- Ruff check/format, mypy, pip check and fresh platform wheel build passed.
- Read-only source review: no Critical/Important, two Minor diagnostic/test-cwd
  caveats recorded in LOW_RISK_REMOTE_INTEGRATION.md.
- Original CI43102812296 is red: 6556 passed,74 skipped,2 BI UI failures.
  Static/build and Windows/Shared offline installs passed. Artifact quota
  blocked uploads; do not call it green.
- Diagnostic CI43114604977 ran original assertions twice on base097/head e693:
  version-link fails twice on BOTH refs; create-domain passes twice on BOTH.
  No only-head failure; the full-run domain failure is unreproduced, cause unknown.
  Diagnostic-only workflow is excluded from delivery.

Evidence: .scratch/low-risk-verification/full.log/full.xml,
knowledge-baseline.xml, knowledge-after-full.json, and source-equivalence JSON.
Use original repository .venv/Scripts/python.exe, this worktree src on PYTHONPATH;
do not repoint the shared editable environment or start another full test run.

## Local package

Requested ZIP is under original repository
 dist/releases/20261112-c4c-e69371e6/.
ZIP aep-windows-preview-0.1.0-e69371e62ec2.zip,193516554 bytes,
SHA256 33963cf8e1fc0442c24ca8af38b64d9dd0453bff70ff14fa6ca6365a04c5cd49.
588 archived payload hashes verified by the official builder and independent read.
Runtime comes from git archive e693; only the release template receives the
approved asset/document overlay. Source/business scripts remain unchanged.

Included exact published asset exports:
- engineering/sap-sales-orders-report@1.0.9, accepted candidate digest
  dae0b636346fb8bc5ce22fff6d6d1ec560500b880c46989b4d0a139c4e6f3d4d;
- engineering/sop-workflow-development@1.0.0;
- engineering/sap-c4c-workflow-navigation@1.0.5.
The original installation card was owner-approved; Workflow is installed on the
resident. Candidate/published metadata linkage retained in provenance.json.
The three exports are schema-valid and have identical steps/parameters/checks.
Existing installer adds them through normal bundled-assets rules, without
execution grants or overrides of user edits/disabled/removed assets.
No source orders, employee mapping contents, reports or Host/browser secrets.
Original fixed user paths, SOP dates and rates remain explicit portability
limits: cross-PC use requires normal AEP revision, trial and approval.
Sales_Order/ contains the standalone asset exports and dedicated Chinese guide;
START-HERE/INSTALL/USER_GUIDE/RELEASE.zh-TW.md cover installation and operation.
Prior live C4C acceptance is documented in C4C_ROUND7_ACCEPTANCE.md; packaging
checks do not rerun production C4C.

## Package completion and known procedural incident

Isolated install exited0; doctor ready, platform/Gateway pip checks passed.
562 installed Python files and three Sales Order assets match exported bytes.
Explicit isolated Gateway home config/managed/version checks passed, no Gateway
was started. Final package only added the current-PC update guide after the
installation; every existing payload hash stayed identical. Final588payload
hashes and installed source/assets were checked again. Claude review had no
Critical/Important; Minor caveats are in the package report. No production C4C
rerun or new harness edit occurred.

Important: GatewayInstallOnly still initializes the shared user Gateway home.
The test initially omitted AEP_GATEWAY_HOME and changed the shared python path
to the canary interpreter, regenerating YAML. No pre-test backup existed. This
was a test-isolation error; do not claim exact previous bytes/value were restored.
Normal CLI subsequently normalized python to the verified live external Gateway
interpreter. The repair changed only python relative to the post-canary backup,
kept managed=false/11models/all other fields, and left YAML bytes unchanged.
The external service PID5468/starttime stayed unchanged. No restart, token refresh
or user-env export occurred. Claude independently found no exact original value.
See C4C_WINDOWS_PACKAGE_20261112.md and private gateway-repair-proof.json.

For this PC, the new Chinese update guide says update.cmd -NoGateway. Future
canaries must explicitly isolate AEP_GATEWAY_HOME (without user-env export) or
use -NoGateway; GatewayInstallOnly is not a settings-isolation flag. Existing
flags solve this procedure issue; no installer/harness change was made.

## Delivery and next action

Local deliverables: original repository dist/releases/20261112-c4c-e69371e6/,
including ZIP, SHA256SUMS, current-PC update guide, full guides, Sales_Order/
standalone exports and CANARY-VERIFICATION.json. No build/test/driver is active.
Temporary evidence is under C:/TEMP/aep-package-20261112; private shared-setting
backup is outside the distributable. Keep the canary evidence until delivery
review is complete; do not remove live Gateway files/processes.

Delivery receipt: dfd73c1a9fe2efcede8266dfaa2dd40aafefd67e was normally
fast-forward pushed to c4c-verified-20261112 and matched git ls-remote.
Origin/main remained267c75e4c917e523ad72a52d93890d8d7837bbb5. This follow-up
receipt changes documentation only; runtime/package source remains e69371e6.
Original resident/source checkout remain untouched. Do not merge e564e1ad.
No full-test rerun is needed for this documentation-only receipt.

Next action belongs to the owner: use the delivered Chinese current-PC guide
and update.cmd -NoGateway when ready to update the installed AEP. Packaging did
not deploy the integrated runtime. Any later portability revision must use normal
AEP authoring/trial/approval; any harness change needs separate scoped consent.
