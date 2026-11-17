# C4C Windows package, 2026-11-12

## Authorized scope

The owner requested this AEP version, the accepted Sales Order Workflow, related
Skills, and operator instructions. This is local artifact packaging using the
existing Windows builder and `assets install-bundled` mechanism. It introduces
no runtime, harness, permissions, or business-script changes. Distribution does
not grant execution permission. The running resident and origin/main stay intact.

## Contents and provenance

- Runtime source: e69371e62ec2a01d31eead91f67ff9e4404a4254, the staged low-risk
  integration; excluded remote harness commit e564e1ad is not included.
- engineering/sap-sales-orders-report@1.0.9, accepted candidate digest
  dae0b636346fb8bc5ce22fff6d6d1ec560500b880c46989b4d0a139c4e6f3d4d.
  Exported installed manifest SHA256:
  7375afd299dff32ea7b82e05f1743c32d8b51bd7f0d76efbc29e07686e5a3004.
- engineering/sop-workflow-development@1.0.0.
- engineering/sap-c4c-workflow-navigation@1.0.5.
- Existing Traditional Chinese installer/operator/BI guides and a Sales Order
  guide covering execution, exceptions, and simple-dialogue SOP authoring.

The three published assets are byte-identical exports of the installed assets.
Their approved draft/published metadata relationship and original approval
references are retained in the private package's provenance.json. The approved
Workflow steps, parameters and checks are unchanged. Company order data, report
workbooks, employee mapping contents, Host configuration, credentials and browser
profiles are excluded. Tenant navigation and original paths remain in the private
Workflow; do not publish this asset payload as generic public example data.

## Portability limitation

The accepted Workflow has no parameters and embeds the original workstation's
workspace and Downloads mapping path, SOP dates and exchange rates. Packaging
does not make it portable. Other workstations or reporting periods require normal
AEP revision, a new complete trial/output reconciliation, and installation approval.
The operator guide states this explicitly; no untested script substitutions are
presented as the accepted version.

## Verification sequence

1. Finish the active full suite; compare the same 445 baseline Knowledge cases
   and all eight Knowledge/model source paths. Preserve original CI failures and
   baseline/control evidence (LOW_RISK_REMOTE_INTEGRATION.md).
2. Export committed runtime source and build a fresh platform wheel. Reuse the
   previously downloaded binary dependency cache; the stale platform wheel is
   excluded. The official builder verifies gateway lock hashes, credentials,
   Windows path lengths and every payload hash.
3. Overlay the three approved manifests in existing aep-skills folders, with
   provenance and instructions. Verify each archived payload digest.
4. Install into a fresh isolated local directory, with no shortcuts/coding-agent
   setup and no Gateway start. Check doctor, dependency consistency, source
   identity and installed asset identities/hashes. Do not run production C4C.
5. Record actual outcomes, final ZIP hash and delivery path before reporting done.

## Built artifact and independent review

Archive: original repository dist/releases/20261112-c4c-e69371e6/
aep-windows-preview-0.1.0-e69371e62ec2.zip (193516554 bytes).
SHA256: 33963cf8e1fc0442c24ca8af38b64d9dd0453bff70ff14fa6ca6365a04c5cd49.
All 588 payload entries match manifest.json. The ZIP has 589 members including
the manifest itself. The external SHA256SUMS covers the ZIP; the internal
SHA256SUMS covers the Sales Order assets/documents, with complete platform
coverage in manifest.json.

Claude's final read-only package review found no Critical/Important issue. All
three assets and seven standalone attachment files match the reviewed exports.
All 562 wheel Python files match the pinned Git source after CRLF/LF
normalization; line-ending differences are not source behavior changes.
No company workbook, Host config or credential payload was found. Incidental
short common-word/name hits in third-party Hermes font/icon data were reviewed
as unrelated to company source rows. This is not a claim that arbitrary strings
in third-party dependency wheels were comprehensively audited.

Minor documentation caveats retained: the standalone attachment guide's statement
that it does not auto-install applies to that attachment; the main installer does
install its bundled assets through the existing mechanism, as explained in the
main release guide. Internal SHA256SUMS has the narrower asset scope above.
No runtime/business/test changes were introduced to address these wording issues.

## Completed isolated installation and procedural correction

Install exited 0 in C:/TEMP/aep-sales-canary-e69371e6. Doctor reported resident
ready; platform and Gateway pip check both passed. All 562 installed Python
files match the committed-source export byte-for-byte, and all three installed
Sales Order assets match the exported bytes and typed JSON. No production C4C
trial was run during packaging.

The initial Gateway status probe incorrectly assumed a clean managed Gateway;
this PC deliberately uses an external unmanaged service. More importantly,
GatewayInstallOnly still invokes gateway init against the shared user home.
The test did not set AEP_GATEWAY_HOME, so it changed the shared python reference
to the canary interpreter and regenerated the rendered YAML. This was a test
isolation error, not a new source change. There was no pre-test backup of these
two files, so exact previous bytes/previous python cannot be claimed restored.
The existing unmanaged service was not stopped/restarted, nor were tokens
refreshed or user environment credentials exported (unmanaged init returns early).

Correction used the normal CLI to point the unmanaged Gateway at the verified
interpreter of the already-running external Gateway. Post-canary files were
backed up privately before this correction; only the python setting changed,
all other settings including managed=false and 11 models matched, and rendered
YAML bytes stayed identical during correction. PID5468 and its pre-test start
time were unchanged. Claude independently found no original backup/value and
confirmed this is functional normalization, not evidence of an exact restore.
The original resident installation and origin/main remain unchanged.

A separate explicit Gateway --home under the canary was initialized without
user-env/start. Its config/managed/version checks passed; ours=false confirmed
it had not started a process on the externally served port. Existing flags and
an isolated home solve this procedure problem without installer/harness edits.

The final ZIP only adds the Chinese current-PC update guide recommending the
existing update.cmd -NoGateway option; all 587 existing payload records are
identical to the installed/reviewed archive (initial SHA025e4ab3...5956).
The final source/asset comparison and all 588 final payload hashes passed again;
there was no reason to repeat the full suite or reinstall identical runtime bits
for this documentation-only addition. CANARY-VERIFICATION.json beside the ZIP
records the exact outcomes, original probe failure and shared-setting incident.

Status: package, installation, payload comparisons and documented procedural
correction complete. No pending test/build/driver process remains.
