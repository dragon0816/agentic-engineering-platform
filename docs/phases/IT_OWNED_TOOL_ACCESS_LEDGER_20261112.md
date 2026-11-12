# IT-owned tool access execution ledger

Base:394ca4d2ccb271a88d45bdaf3978a43f24079a58.
Branch:it-owned-tool-access-20261112.
Worktree:C:/Users/Chi_L/.paseo/worktrees/2qnenase/it-owned-tools-20261112.

Owner scoped harness approval,2026-11-12:
「同意上述 harness 範圍並開始實作」, replying to the four-scope question
recorded in the design and DECISIONS. No additional consent is needed for tasks
inside that stated scope; expansion still requires new consent.

Plan self-review: requirements mapped to8 tasks; internal Knowledge helper
contracts/model eligibility preserved; actual IT decisions never fabricated.
No implementation yet. No process is active. Next: Task1 red tests.

## Evidence and rulings

- New managed worktree wks_9e3f85169bdceb9b created from the design commit;
  original main/accepted package/resident are untouched. No editable install or
  dependency rebind is performed in the shared virtual environment.

## Task1 — environment execution

Red: corrected task1-red.log has35fail/1pass; calls were blocked by legacy
permission/approval checks and Outlook was absent. The initial test fixture
omitted required central_required; that first run is preserved separately and
is not the causal red proof. Correcting the fixture changed no assertion.
Green: task1-green.log/xml64passed5.47s; Ruff check/format passed, mypy runtime.py
passed. Updated old default-deny/review-as-admission assertions to the owner's
new contract, retaining real handler count/output/error/context checks.
LocalPolicy is a legacy-compatible identity facade; no fake IT grant/approval
is created. Unknown targets, bad arguments and real OS errors remain failures.
Global lint/type/full/build remain for final source freeze; this is a verified
slice, not whole-feature completion. No resident/config/install change.

Task2 red: isolated no-reference Outlook discovery fails as expected2.27s;
no COM/mail access occurred. Test is in test_it_tool_discovery.py, outside the
Task1 commit, ready for the registration slice.

Ruling: retain LocalPolicy's constructor/add/confirm_writes interfaces only as
compatibility metadata while migrating callers; no method may gate execution.
This avoids breaking integrations before their registration/install migration.

## Task2 — portable registration and local assets

Red: task2-red.log1failed proves missing Outlook; expanded discovery red2failed/
1passed proves Skill-gated BI/contacts and member-selected local assets.
Green: task2-affected.log/xml52passed22.22s, including zero-COM discovery,
no-reference data/Outlook/BI/contacts and local assets independent of legacy tool
selections. Ruff passed; host.py mypy passed. Registration Knowledge isolation
and pipeline host checks46passed25.86s. Full445/full build remain final gates.

Removed13 asset-usage guards/setup assignments from portable registration and
unused policy imports/helpers. Removed grant/profile-capability admission and
fake runtime grant synthesis; preserved authenticated device checks and existing
Knowledge selections/model data approval. Old grants can coexist or be malformed
without becoming startup permission input. Diagnostics report actual installed
assets. Existing assertions were updated only for the explicit changed policy;
foreign-device and invalid-asset/secret-redaction assertions remain.

Ruling: profile procedure selection still controls which instructions fit a
role, not common tool access. Internal Knowledge query helpers retain their
query/check contracts. Configured-only integration descriptors/setup statuses
belong to Task3's common catalog, not a second registry policy. The new system
command block is also Task3; Task2 covers existing portable built-ins.

Next: commit Task2 and implement Task3 common catalog/description/invocation.
No test/build process remains; no resident or shared configuration was touched.

## Task3 — common execution contracts (implementation in progress)

Added common paginated catalog, schema description and Bridge invocation tools
to Gateway, authoring MCP and assistant MCP. External authoring returns status
metadata only; its pre-existing model/data boundary remains. Known integrations
without handlers are shown as needs_setup, independently of permission metadata.
system/run-command runs argv under the OS account, preserves actual exit code,
bounded/redacted output and real timeout/start failures. Windows timeout cleanup
terminates the command tree because a venv launcher can leave child pipe handles.

Red/green: common alias tests initially exposed duplicate writes and incorrectly
memoized reads. Gateway now resolves the actual capability effect identity and
classification, shared across generic/Skill aliases. Corrected fixture errors
(Skill namespace and result field name) are not treated as causal evidence.
Legacy approval callback does not block execution; actual environment refusals
remain unrecorded and are tested on repeat. Pending Host outcomes retain their
existing separate regression coverage.

task3-green.log/xml:112passed10.70s, covering common tools, command, effects,
host discovery, dispatch/contracts and authoring/assistant adapters. Ruff passes;
focused source mypy7files passed before the final offered-descriptor addition.
Interim whole-tree mypy is still running; do not claim it passed. A legacy test
still accesses removed LocalPolicy._grants, to migrate in Task5 with its original
technical-refusal assertion preserved. Whole-feature verification is pending.

Ruling: binding-specific execution timeout is runtime metadata, not permission;
the command handler owns its requested timeout with a bounded cleanup margin.
CapabilitySpec accepts side-effect descriptions without fabricated approval refs;
shared publishing governance is separate and unchanged by this contract removal.

Task3 checkpoint:112 focused passed plus the migrated legacy-grant assertion
1passed; whole-tree mypy1101files passed, Ruff check/format src/tests passed.
This is not full-suite/build acceptance. The interim whole-tree mypy first found
one stale private-grant assertion; it now asserts no grant admission/no fake
approval, rather than reaching into a removed implementation dictionary.
Task4 red:4failed confirms agent MCP installation interface is absent; tests
are deliberately not included in the Task3 execution-contract commit.

## Task4 — agent MCP connection and live catalog

Agent ToolAccess.install_mcp saves through existing McpHub with background
connection disabled, then connects synchronously in a worker thread. Gateway,
assistant and authoring MCP expose this operation. Credentials stay environment
references. No approval record, synthetic grant or restart. Catalog/invoke read
the live registry, so the static generic tools work in the SAME bounded model
conversation after installation. Skill selection is not involved.

MCP replacement/disable/delete disconnects its stale bindings; current schema is
registered on reconnect. Explicit MCP isError now yields a failed execution with
typed diagnostics, rather than success. Direct MCP aliases declare their effect
and resolve the same capability identity. A reconnect cannot reset a successful
effect receipt for the same logical target/arguments within the turn.

Evidence: task4-red.log4failed (missing interface); task4-green.xml/log22passed;
task4-conversation.xml/log27passed; task4-final.xml/log34passed7.07s (including
single-conversation install/catalog/invoke, stdio+HTTP fixtures, schema refresh,
disable, invalid transport/executable, real MCP error, effect regressions).
Whole-tree mypy1102files passed; Ruff check/format passed before final HTTP test,
which was formatted/import-sorted. Final source freeze still owes full checks.
No real install/network/mail was used; HTTP fixture listens only on loopback.

Next Task5: direct local asset install with honest unverified quality/provenance,
no approval cards; preserve central publishing rules and historical cards.

## Task5 — direct local asset installation and truthful receipts

Normal Gateway/authoring MCP run/install paths execute directly. Added Gateway
Skill draft/install tools and live procedure refresh. Local installations retain
pending business review, actual candidate/digest provenance and draft/validated
quality; an Install press or reference string is not business acceptance. No new
grant file or approval card. Old explicit request/decision APIs remain readable
and tested as history; no pending historical action is automatically decided.
Contract/dependency/name/version checks remain; unverified quality is visible,
not fabricated and not a local-install admission gate. Completion/coverage still
requires actual verification; dropping pagination is never verified by installing.

New direct execution exposed two real duplication gaps. Added run receipts shared
with Gateway (installation metadata does not repeat the procedure), plus Bridge
success-only normalized capability receipts shared across wrappers of the same
registry. Actual handler invocation is false on replay, warnings identify it;
failures/read calls are not memoized. Shared registry write lock protects receipt
check/execution/record across Bridge wrappers. No caller may reset a successful
receipt by reconnecting or installing in the same turn.

Evidence: task5-red4failed (missing direct semantics), live Skill refresh red,
repeat-run and generic-then-Workflow-write reds (actual duplicate handler calls),
invented-review-reference red (false approved metadata). New local tests passed;
task5-final.xml/log435passed133.90s across authoring/repair/input continuity/
pagination/preflight/history/revision/Knowledge isolation/effects/dispatch.
That broad run preceded the final metadata tightening; final provenance/related
tests task5-review-provenance.xml/log50passed33.17s. Earlier diagnostic run had
7 stale policy expectations/428passed; migrated only approval-as-admission
assertions, preserving stronger input, original-file, coverage and no-egress
checks. That diagnostic overlapped later edits and is not final acceptance.
Task5 focused mypy541files and Ruff passed before final metadata tightening;
final whole-feature static/full/build checks remain mandatory in Task8.

Task6 red (uncommitted test_it_tool_boundaries.py):4fail confirms legacy folder/
sender/date hiding, missing body continuation metadata, mode switches/cards and
generic file folder restriction. This red file is excluded from the Task5 commit.


## Task6 in progress — mailbox/native execution and cross-endpoint receipts

Uncommitted implementation removes application mail folder/sender/date admission,
read cards and native backend switches/permission relays; adds bounded mail body
continuations and explicit send-draft capability. Draft remains draft. Production
legacy mail aliases use the same Bridge target/turn receipts. Native HTTP turn
tokens now scope assistant and authoring endpoints to one TurnEffects record;
a loopback cross-endpoint test proves one handler invocation and token expiry.
No external provider guards/settings are bypassed. Codex uses native HTTP MCP
config with bearer token references in child environment, never token argv.
Model/data-routing requirements are unchanged.

General commands/Python validation use actual IT/OS identity. The EnvironmentRunner
shares typed subprocess execution with command capability, retains timeout,
redacted bounded output, real exit statuses and fresh-artifact evidence. Purpose-
specific coding/change writable/test contracts and Knowledge helper isolation
remain. Default Python execution no longer needs host coding roots, low-token
setup or a firewall rule. Desktop/browser output paths accept absolute accessible
paths; overwrite intent and actual path kinds remain validated.

Actual checks so far: task6-mail-native.xml85passed/1failed/2deselected34.70s;
sole remaining failure was new test importing SPEC as SEND_SPEC, corrected.
Initial Python adapter9failures/20passed exposed CRLF output and killed-process
exit compatibility; normalized text newlines and preserved timeout exit=None at
the Python adapter, without weakening failed-run/output JSON assertions. The
85pass run includes those corrected Python tests. task6-boundaries.xml17passed
5.38s includes direct preflight without cards or false verification and replay.
task6-mcp-lifecycle.xml22passed25.92s. New EOF/log redaction test first failed
because close killed the launcher without reaching child EOF; fixed by EOF-first
shutdown, owned-tree fallback and redacted stderr drain. No real mailbox/send.
Static review found native Knowledge read steps could be memoized by the new
wrapper; corrected classification and added fresh-read regression before final
verification. Final whole-tree lint/type/full/build are still pending.

Old decision/request APIs remain explicit compatibility paths. Preflight's old
request builder is private and tested as historical behavior; the normal model
tool directly returns the actual Bridge result. No historical pending cards are
auto-approved or replayed. Broad affected test run is in progress; no full suite,
build, resident deployment, push or shared Gateway change has occurred.


## Task6/7 focused acceptance and current verification boundary

Latest focused checks: task6-final-focused.xml118passed61.74s; task6-tail.xml
61passed/2live-Outlook-skipped84.50s. These cover direct read/draft/send, native
fake adapters, actual local Python, legacy SOP install, real trial-input reuse,
normal direct browser preflight, old-card compatibility and MCP connect/cleanup.
The updated one-conversation fixture now discovers/uses an existing validator,
installs a missing MCP fixture, discovers it and invokes it in the SAME turn:
five actual successful tool calls, one existing handler call, no approval files.
Earlier task6-affected3 had187passed/3failed/3skipped121.72s; those3 required old
approval records for actual input continuity. They now assert the same QA values
are replayed from actual trial history independently of removed/foreign/stale
legacy cards, and are included in the latest118passing focused tests. Stronger
same-actor/session/digest/run-history conflict checks remain unchanged.

Legacy SOP Studio had an additional preview-as-install-admission/fake-review
path. A new red proved direct installation was refused. It now accepts a valid
local draft, never fabricates business review or a successful full trial from a
preview, writes no grant, and the authenticated Web endpoint refreshes the live
workflow registry. Invalid/missing draft, missing capability and version conflict
remain real failures. The changed draft cannot inherit old preview evidence.
This is within the approved local-install scope, not new shared publishing policy.

Ruff check and format check passed (1158 files). Whole-tree mypy passed1112files
before the final small legacy-Studio/comment/test edits; final freeze recheck is
mandatory. Real native-provider tests now opt in with AEP_NATIVE_CLI_TESTS=1,
analogous to existing live Outlook/GUI checks: inheriting IT environment must not
silently use a developer's live credentials in routine tests. Fake CLI/ACP/MCP
protocol/error/data-policy assertions remain and have run. Actual provider help
was inspected read-only; no live provider model prompt, mailbox/send or C4C run.

Task7 Knowledge: exact baseline445 node IDs executed,445passed162.21s,0skipped.
knowledge-comparison.json proves identical445 identities AND outcomes, not merely
a count. Initial runner hit Windows argv length before pytest started; switched
to pytest.main in one Python process with the same exact node IDs (no dropped
cases). Raw log/JUnit retained. This measures deterministic regressions, not all
possible live model answers. Final frozen full-suite must compare the same445
again. No query ranking/evidence/model-data eligibility implementation was edited.
Knowledge helper scope and shared publication remain purpose-specific contracts.

Updated application Settings copy, backend tool exposure, MCP tool descriptions,
creator/Knowledge guides and AGENTS/CLAUDE/requirements/architecture/contracts to
avoid instructions to wait for removed local approval gates. AGENTS22, IT/OS
permissions, actual outcomes, dry-run intent and model/data policy remain intact.
No resident, delivered package, shared Gateway, remote branch or main changes.
Task8 whole-branch independent review, frozen full suite, build and pipcheck are
still pending. This is NOT final feature completion or deployment acceptance.


## Review repair checkpoint —2026-11-12 (UNCOMMITTED)

Whole-branch read-only reviewer it_tools_final_review (base394ca4d2..f490ebb1)
returned Critical0/Important4. All findings reproduced with causal tests:
1. RLock over await allowed duplicate/concurrent writes: review-concurrency-red
   2failed/1passed. Added common/async_lock.py ExecutionLock with cross-loop Future
   signaling, no thread mutex held over await, nested workflow leases and separate
   per-receipt coordination. Gateway run receipts are checked/recorded inside the
   execution lease. Existing registry/shared-wrapper serialization retained.
2. MCP normalized/truncated names could dispatch another tool: collision-red had
   2targets for5tools. Stable disambiguated identities/model aliases preserve
   ordinary unambiguous IDs; constructed suffix collision fallback uses full hashes.
   Followup ownership red proved a preexisting target was silently claimed/removed;
   connect now rejects binding conflict, rolls back/unregisters only bindings it
   installed. Duplicate raw names report a technical protocol failure, not success.
   This final hardening is pending its rerun.
3. Schedule live grant/effect/per-run gates survived Bridge removal: schedule-red
   2failed. Worker/resolver now use actual authenticated stored owner/Bridge and
   installed target/task contracts. Historical grant/callbacks do not admit tools;
   no old pending occurrence is auto-approved or replayed. Atomic claims, pauses,
   uncertain work and task model/data validation remain.
4. Exited command root could leave child pipes/orphans past deadline: process-red
   2failed including real orphan marker. Deadline now covers root exit AND pipe
   draining. Windows supervisor joins an unnamed kill-on-close Job before starting
   requested executable; no token/network/memory/process-count restrictions. POSIX
   uses owned process group. No PID guessing/other-process termination. Microsoft
   Job Objects documentation checked. No new dependencies. Initial repair36passed
   100.92s across commands/Python/fresh-artifact tests. Supervisor argv now uses an
   owned temporary UTF-8 JSON file to avoid command-line inflation; retest pending.

New schedule/MCP/concurrency focused run40passed12.36s before final MCP ownership/
constructed-alias hardening. No live company Outlook, model prompt, C4C or send.
A separate old-admission scan selected95cases:32failed/63passed37.73s. Migrate only
withdrawn permission expectations. Grounded Knowledge tests now assert the same
answer/raw citations; BI tests retain published tag/evidence and model/data toggle.
Resume/retry tests simulate actual unavailable binding dependencies with new
 tests/execution_fixtures.py, retaining pre-handler no-effect and uncertain evidence
instead of recreating an application permission gate. Retained-contracts run:
171passed/1actual status mismatch69.71s (missing resource is unavailable, corrected).
Broader business-contracts run194passed/12failed/1skipped161.42s:8 caused old fake
MailSummary conversion including newly added MailMessage body metadata;4 are old
push/approval expectations or newly isolated fixture setup/assertions. Diagnose
and correct without weakening source/output/side-effect guarantees. Logs/JUnit
under .scratch/it-owned-verification. No full pytest/build for feature yet.
Whole-tree mypy1117passed and Ruff/format passed before latest small refinements;
final frozen checks still mandatory. Source repair diff is UNCOMMITTED.


## Final review repair checkpoint (2026-11-12)

The required same whole-branch reviewer rechecked the repair diff: Critical0,
Important0 remaining (source review only; no claim of live validation).
Five Important findings were repaired: concurrent effect serialization, MCP
collision/foreign-binding rollback, residual schedule admission, owned process
lifetime/deadline, and generic native result-data eligibility. Native HTTP,
AgentMode and unscoped generic invocation now executes and returns honest status
with `result_eligibility_not_established`; unknown tool result data is never
implicitly PUBLIC. Gateway content routing and authoring metadata-only contracts
remain separate. This is not an end-to-end guarantee for legacy native content
paths or a provider's independent filesystem tools.

A stale historical pending card also suppressed the persistent completion check.
A corrected fixture explicitly creates the saved task; the original exception
fails that test (`review-historical-card-red.log`). Removing only that exception
preserves factual inquiry and genuine business-question isolation. Historical
cards are never auto-approved or counted as execution proof.

Review repairs targeted acceptance:89passed28.00s (`review-final-green.xml`),
including all three native result boundaries, same-turn receipt reuse, concurrent
native threads, MCP constructed aliases/foreign ownership, Windows command tree
cleanup/deadline, schedules and authoring Knowledge isolation. Earlier focused
runs and their real failures remain recorded, including the initial completion
fixture that had not created a task; it was corrected before causal red/green.
Business fixtures now distinguish real query filters from withdrawn mail scope
ceilings; their MailSummary projections explicitly omit body-pagination metadata.
Recovery fixtures use actual unavailable dependencies instead of revoked grants,
retaining no-handler/no-effect and uncertain-run assertions. No output or source
provenance assertion was weakened. Final full-suite/build acceptance pending.


## First full-suite results and final source freeze (2026-11-13)

Initial full source:6682passed/37failed/15skipped8390.40s (2:19:50), raw
full-initial.xml/log retained. The identical445baseline Knowledge case IDs and
outcomes all match, with no missing or changed cases (knowledge-full-comparison).
The earlier small prefix probes were not the actual first failing test; the
actual first failure was addon exact Skill upgrade/rollback, not an Outlook
sender. Do not treat those unrelated probe passes as resolving the first failure.

Most failures encoded canceled grant/approval/roots/push-field restrictions or
old UI copy. Migrated assertions retain actual handler results, no side effect in
preview, proper actor/HTTP401/409, historical cards not replayed, published
Knowledge source tags and citations, voice/text normalized arguments and once
per turn, exact installed capability advertisement and mock-only benchmark
execution. No real instrument, Outlook, native provider or C4C run was used.
BI pending-body UI check now awaits its same quiet invariant while keeping the
first response body held; exact POST count/order/state assertions remain.
First affected-module run:383passed/1fixture failure/1IPv6skip578.33s. That one
fixture misread external run codes; corrected to the real run payload. Subsequent
checks exposed a real missing UI last-run record, repaired below rather than
removing the output assertion.

Actual source regressions and causal evidence:
- All retained Skill versions collided in alias registry. Preserve explicit
  member procedure-version preference when no profile; otherwise exact profile
  versions, and retain ambiguous-profile registry rejection. No tool grants.
  Default local families use existing semantic-version ordering. Original addon
  test reproduced red. Two-member/profile red proved silent version omission;
  a second parameter proved a surviving capability-selection activation gate.
  Removed only that tool gate; Skill/Knowledge/model checks remain. Final profile
  cases include alias conflicts and exact registry identity, not merely no crash.
- Direct runs lacked approval-backed display history. Typed AuthoringRunReceipt
  stores actual run ID/status/digest/time only (no inputs/output content or fake
  approval). It is not verification evidence, and revised drafts clear it.
- Nonblocking candidate-lock contention after success could replace the actual
  outcome with an error. Success is recorded first; metadata busy/stale/unreadable
  records a warning with verified=false. Busy regression and same-turn retry
  pass without another side effect.
- Concurrent direct authoring ran two workflow IDs despite capability dedupe.
  Receipt-concurrency-red proved2IDs. Direct execution now uses the same async
  registry lease as Gateway workflows, covering lookup/run/success recording.
  No thread mutex is held across await. Two native threads return one run ID,
  one replay, one handler call.
- A replayed old prototype incorrectly borrowed a newer revision's verified
  readiness. replay-proof-red reproduced verified=True. Replay now requires exact
  current digest for readiness; otherwise actual prior outcome remains replayed
  but verified/coverage=false. Actor identity check retained at entry.

Final focused proof:161passed50.86s (final-proof-green.xml); additional
atomic/profile pass34cases14.76s. The same whole-branch reviewer rechecked all
Important repairs and reports no remaining Critical/Important (source review;
not a live test). Ruff/format/mypy final checks recorded separately. Final source
freeze uses source-freeze-final.json. A second full run is justified by the
concrete host/profile/execution source fixes; do not repeat without further
changes or unresolved failures. Build waits for full completion.


## BI-local tool gate addendum (2026-11-13)

A supplemental admission-path check found a real omitted gate, within the same
owner-approved tool-approval-removal scope: `bi_cards.tool_runs` required local
per-PC code-hash approval before run/try_draft. A Skill cannot remove that runtime
branch or the disabled UI button; calling approve automatically would fabricate
review. Three desired-behavior cases reproduced HTTP409/tool_needs_approval
(bi-tool-policy-red.log,3failed15.61s). Removed only this local execution gate,
retained historical review metadata/API (never fabricated approved), exposed
requires_approval=false, enabled normal Run and removed the helper's stop-for-
approval instruction. Data-transformer source/output/readonly/format/timeout
contracts, classifications, derived_from, withdrawal and Knowledge curation
review remain. A general OS command tool remains distinct from this purpose-
specific source transformer.

Dedicated BI acceptance:55passed242.52s across runtime, cross-PC sync, unreviewed
revision/draft actual outputs, UI, skill agent, confidentiality and guard attacks.
Updated same whole-branch reviewer:Critical0/Important0 for this delta, source-only
review. A first command named a nonexistent withdrawal test file and ran no tests;
actual withdrawal regression is in test_bi_tool_runs and passed in the55.

Important evidence boundary: this BI-only delta was made while the frozen CORE
full-final run was already beyond those tests, so that full is not evidence for
the new BI implementation. The3 BI runtime/UI modules and3 changed test modules
are an explicit separately verified component delta. All common execution,
registration, receipt, native/model/Knowledge core source remains at the final
full source snapshot. Preserve source-freeze-final.json and a separate final
component hash map; do not report an unchanged global source hash or pretend the
old full exercised this new BI gate behavior. Rerun exact445comparison and all
static/build checks on the completed combined tree. Do not repeat unrelated
hours of UI tests solely for the narrowly scoped component change.

## Final verification closeout (2026-11-13)

Second core full actually ended6724passed2failed15skipped7933.08s. Both raw
failures retained in full-final.xml/log. Long Knowledge source fixture failed
before import at deep pytest root: short control passed; deep control failed.
First attempted long_path(root) fixture change was insufficient and still failed
deep; final isolated short TemporaryDirectory source passes both short and deep
roots (longpath-*-isolated.xml,1pass4.01s each), destination>260 assertions intact.
The remaining conversation failure was RemoteDisconnected caused by a session
atomic-write FileNotFoundError, NOT a timeout/load inference. Baseline and current
workspace writers both reproduce on the same long path; workspace.py and
authoring_task.py are unchanged. Whole current conversation module at short root:
6passed24.51s. Existing long-workspace persistence limitation remains.

Current BI final55passed166.55s. final_evidence.py reconciles6740collected cases
plus1collection-level skip, replacing only the named supplemental cases and3BI
renamed IDs. Three JWT cases embed collection-time expiry timestamps and match
parameterized family counts; all other IDs exact. Combined6726passed15skipped,
zero missing cases, NOT one green full. Exact445Knowledge comparison: raw final
has1fixture failure, supplemented comparison zero changed/missing outcomes.

Final Ruff check/format1481 pass; configured mypy1117 pass; pipcheck passes.
python -m build --no-isolation succeeds. Isolated --target installation plus4
module imports succeeds; all571wheel Python sources match current source after
newline normalization, no extra/missing files. Source delta vs full freeze is
exactly6BI files and1test fixture; no other core changes. No shared editable
install rebinding, resident/Gateway/main update, feature push or live company
execution. See final acceptance Markdown and VERIFICATION JSON for hashes,
case-level provenance, limits and known long-path baseline issue.
