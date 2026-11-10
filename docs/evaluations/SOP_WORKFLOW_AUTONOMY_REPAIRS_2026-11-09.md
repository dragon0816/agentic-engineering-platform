# SOP Workflow autonomy repairs — verification in progress

This continues the owner's five-gap diagnosis. Source implementation and
deterministic regression tests are distinct from live Agent-only acceptance.
No resident rollout or successful autonomous C4C completion is claimed here.

## Five repairs

| Gap | Source behavior | Evidence boundary |
|---|---|---|
| Failed Python reported successful / stale Excel accepted | Validated execution failure; bounded fresh-output scan; failed steps cannot pass output checks | Focused execution/Bridge/harness regressions passed |
| Full SOP reduced to a smaller installable Workflow | Persistent requirement IDs, descriptions/check bindings; exact-current-trial proof; installation gate | Version/scope/coverage regressions; independent live business completeness still required |
| Agent lacks usable Browser evidence | Full typed schema, scoped DOM, fresh failure/action evidence, safe semantic overview | Synthetic and actual Edge regressions; overview follow-up under verification |
| Failure ends at a technical handoff | Bounded same-task continuation after approved/form/card trials, including unfinished prototypes | Public entry-point regressions; no self-approval or install |
| Already supplied workbook asked again | Actual user/attachment provenance, durable prefill, pre-dispatch validation | File/input/form and question-before-first-draft regressions |

## Actual Agent-only run: initial authorization configuration

The private harness creates an isolated Agent Web/runtime with the owner's
original PDF and XLSX and configured approved internal Gateway. It provides
the original task, confirmed dates/rates and an empty working directory. It
does not provide selectors, scripts or a known-good manifest. Local-only
query/filter/export/report actions are authorized; order edits and mail are not.

First run read the attachments and saved eight requirements. It stopped with
`web_origin_not_allowed` while automatic SSO visited a transient origin. The
test's C4C-only whitelist was corrected to the resident Host's existing web
configuration. No candidate or success claim resulted from that run.

## Actual Agent-only continuation: failed acceptance

The continuation exhausted the existing 30-minute turn budget after 140 tool
calls: 78 inspections, 53 Browser operations, four draft attempts, three run
attempts, and two authoring reads. It reached the Sales Orders view and worked
on the date controls, but produced no saved candidate or Excel. It returned
`turn_time_limit`; this is a failed acceptance, not autonomous completion.

Two concrete implementation problems were exposed:

1. The new coverage gate rejected intermediate navigation-only drafts before
   they could be saved/tested. The model then used nonexistent candidate IDs.
   The corrected contract allows explicitly incomplete prototypes to be saved
   and tried, returns their missing coverage, and preserves all requirements.
   Only successful execution with full current coverage grants verified proof
   and installation readiness. A successful partial trial continues authoring
   within the same bounded budget; it does not mean the SOP is complete.
2. The safe page observation showed the first raw DOM nodes, often hidden
   wrappers/header markup. Tool preview truncation compounded the problem.
   A bounded semantic overview must precede raw nodes so useful visible text,
   controls and table hints survive the preview. Deep DOM remains available
   for scoped diagnosis; no application-specific selectors are embedded.

A read-only audit also found CDP's receive loop could exceed its socket idle
timeout under continuous unrelated events. Absolute per-command deadlines and
bounded event buffering were added with actual loopback transport tests. New
Gateway connections during the live run show that its entire delay was not a
single proven stuck model request. HTTP idle timeouts were not redesigned in
this slice.

## Verification ledger (not final)

- Focused overlapping groups: execution113 passed; Agent checks/delegation130;
  Browser41 plus optional skip; initial root/legacy92; file validation12;
  provenance14; task24. Do not sum overlapping runs as unique coverage.
- Latest partial-draft/proof/completion group:49 passed in29.02s.
- CDP deadline/browser integration:75 passed, including continuous event,
  partial fragment and ping traffic limits. Semantic overview follow-up pending.
- Full normal collection:6162 cases/532 modules, four disjoint file shards,
  still running. Initial outcomes and logs are preserved privately.
- Completed shard2:1531 passed/4 skipped/2 failed. The attachment fixture needs
  the new actual-plan/trial contract; a Browser layout check passed unchanged
  in an isolated module rerun. Neither initial failure is erased.
- Initial global test environment has incompatible Matplotlib3.7.3/NumPy2.2.6.
  A separate test venv follows existing project numpy<2/Matplotlib>=3.11
  requirements; weekly-report module16 passed, and Browser/library/BI modules8
  passed unchanged. The owner's global Python environment was not modified.
- Ruff and mypy1062 files passed before final follow-ups. Sdist/wheel build
  passed. Repeat affected checks after final source changes.

Fresh final-code Agent-only acceptance, complete test outcomes, local commits
and a safe resident deployment remain outstanding. Private documents, raw
tool results and workbooks are excluded from the repository.

## Second fresh run: responsive layout defect

The fresh semantic-overview run made28 tool calls and no saved candidate,
then ended with the configured180-second `model_timeout`. Twelve Browser
operations failed; final targets included Select View and Advanced Search.
Independent read-only observation of this isolated target found a500x320
viewport, a completed page with no accessibility dialog, and14 controls whose
centers were covered by the same fixed full-viewport phone-layout navigation
shade. This confirms a concrete reason for the observed obscured-target errors;
it does not establish that every earlier failure had the same cause.

The optional generic Browser viewport contract is being tested. AEP Browser
execution opts into1440x900 desktop dimensions on every attached/re-attached
target, including popups; generic callers retain their existing sizing when
they do not opt in. Preserve pointer hit-testing and the actual page: do not
remove the shade or replace native pointer events with JavaScript clicks.
The acceptance harness will keep its Host alive across approval/continuation
requests, matching resident Agent Web lifetime, and record private tool
observations without modifying model responses or supplying implementation.

## Follow-up verification and actual trials (2026-11-10)

Source fixes are committed locally through797a63ee. Initial full-suite shards
finished with6142 passed,10 failed and10 skipped (6162 total), plus an optional
missing-av collection skip. Initial results are retained. Passing reruns cover
every failure: plotting dependencies in an isolated test environment, unchanged
Browser/library/BI reruns, the interpreter-launcher fixture, the actual
plan/trial attachment fixture and the current in-flight proof token. No test
was weakened to accept stale output or an incomplete candidate.

Final affected run:505 passed,1 optional desktop skip,37 modules,554.40s.
Ruff check and format passed globally (1419 files at that check); configured
mypy passed1069 files. Sdist/wheel build passed. These source checks do not
establish C4C business acceptance. The system-site-packages test venv has
unrelated global OpenCV/tifffile/streamlit dependency conflicts under pip check;
a separate clean environment successfully installed the current wheel with
the declared office/weekly-mail extras and passed pip check (no broken
requirements), without changing the owner's Python environment.

The desktop acceptance uses the same Agent-created candidate, now revision7.
Its first three approved trials failed truthfully and automatically resumed
the same candidate through revisions3/4; the existing three-unfinished-trial
bound then stopped repair. Subsequent explicit business continuation requests
preserved that candidate and original attachments. A later30-minute discovery
turn also failed to produce a usable revision. These interventions and failed
attempts are not omitted or described as single-prompt autonomous completion.

Live evidence exposed four additional generic platform weaknesses, now fixed:

- Shared accessible-name resolution handles aria-labelledby/HTML labels
  consistently; actual field naming improved from0 to30 of32 visible inputs.
- Original source references/images survive long authoring and repair turns,
  without fabricating new human uploads or answers.
- Known technical failures now carry bounded self-repair guidance. CSS scope
  errors are distinct from authorization scope; policy boundaries still stop.
- Actual trial failure/action diagnostics survive bulk page preview truncation.
  A false1/1 pagination candidate is refused, including different locators
  resolving the same element; distinct final-page25/25 controls remain valid.

The actual Agent selected the new read-only data/merge building block to keep
prepared run parameters together with Browser rows. Its revision5 had an
identical current/total locator; approving that concrete safe query trial with
the corrected platform rejected it. AEP independently revised it to distinct
controls (revision6), then repaired a missing target (revision7). Reopening C4C
changed generated page IDs, so revision7 still failed at navigation. It has
not produced a verified Excel and has not been installed. The current business
continuation requires repeatability from a reopened page and complete original
date/page/report requirements; no selectors or scripts were supplied to AEP.

Independent review found and closed the runtime locator-alias pagination
bypass. Targeted regression groups passed114 recovery/turn cases,58 diagnostic/
authoring cases and42 Browser/script cases (overlap with the505 affected run;
do not sum them). Actual current filtered count, complete unique IDs/pages,
both date bounds, source mapping, currency conversion, monthly sums, changed
parameters and fresh workbook still require successful live acceptance.
No resident Host update/restart, production Workflow replacement or push has
occurred. Private source documents, traces and business outputs stay ignored.

## Continued current-source verification (2026-11-10 04:30 Taipei)

The subsequent full run collected6294 cases in537 modules:6281 passed,
3 failed and10 skipped, plus the optional missing-av collection skip. Original
shard logs/XML remain under .scratch/autonomy-current-20261110-*; do not describe
this full run as all green. Each failure was corrected without removing its
assertions: capability sync now checks all four advertised identities, desktop
geometry explicitly selects the desktop viewport, and the BI demo waits for
its own final refresh before checking layout. Corresponding complete modules
passed19/16/2 cases respectively (one IPv6 skip in the transport module).
Combined affected verification passed188 cases with one IPv6 skip. These
counts overlap and must not be summed. Global Ruff/format (1420 files), mypy
(1070 files), and sdist/wheel build passed before the conditional disclosure
follow-up. Source is committed locally through a115557e; no push occurred.

Same-candidate native acceptance reached revision21. Repeated attempts still
have not produced a workbook; root supplied business continuation requests and
normal trial approvals, never candidate code/selectors. Bounded actual trial
history now survives normal-turn context truncation as well as automatic
repair. Pagination failures identify the actual current/total/next/control
field while preserving existing error codes and authorization boundaries.

An actual revision20 trial failed at date fill with Advanced Search pressed
false and only the paginator input visible after its unconditional disclosure
click. This is concrete evidence for a repeatability repair, distinct from
earlier unproven field-label hypotheses. The narrow ensure_visible action
probes unique visible presence without field values, skips an already visible
target, or native-clicks its disclosure once within a shared deadline. Omitted
wait_for value means presence; supplied regex behavior is unchanged. Final
regressions/review and AEP's own revised candidate are still in progress.
Resident rollout and C4C business acceptance remain incomplete.

Conditional disclosure source committed4fd706fc after105 affected cases,
global Ruff/format1420 files, mypy1070 files and build passed. Independent
implementation review found no blockers. Native AEP independently adopted
ensure_visible/presence waits inrevision22, but trials22/23 failed earlier at
All selection (actions3), not the new disclosure action. Subsequent real
exploration successfully used layout-toggle then variant-trigger and menu-item
click. Savedrevision24 omitted the first operation. A generic business QA
continuation now requires AEP to compare successful discovery with the saved
sequence and prove repeatability from a reopened page before another trial.
No Codex selectors/code were supplied. This observed remaining planning issue
means native autonomy acceptance stays open despite verified platform source.

## Resident rollout and additional live findings (2026-11-10)

Source4fd706fc was deployed after a fresh canary install/doctor/pip check and
an immediate resident activity guard (busy=false/items=[]). Root stopped only
the verified old Host process, backed up config privately, used the official
installer without Gateway/agent-skill changes, and restarted it hidden with
its original port/schedules. Post-start activity, empty stderr, pip check,
unchanged config/device/workspace, installed-source SHA and fresh live Host
authoring catalog passed; old c4c-sales-order-report@1.0.1 remains installed.
External cached MCP tool processes still expose their old catalog; they were
not killed and are not evidence of the freshly restarted Agent Web's version.

Native trials25/26 failed at wait/readiness/pagination checks. Revision27 then
removed pagination while its original weak present(actions) assertions still
claimed complete coverage. Root held that incomplete trial approval. This is
an additional observed verification gap, not a successful workaround. A sticky
task obligation now retains real declared complete collections; an unrelated
pagination or later same-output writer cannot discharge it. Review found and
closed the cross-action overwrite bypass and pre-input-binding source-digest
error with causal red/green regressions. Final affected108 passed (overlaps
focused23); full current6358-case/538-module verification is running. Ruff/
format1421files and mypy1071files pass. Build still running at this checkpoint.

A real pending-approval reply also showed a generated task summary labelled
完成 because its model turn was answered. It now renders 已回覆; an actual
pending-trial multi-tool turn regression was red before the correction, and
the full summary/artifact modules passed13 cases afterward. No workflow success
status or approval semantics changed.

Date-fill exploration exposed a C4C invalid-date warning and a single-day query
of11 records. Root sent business QA referencing the original SOP's Between,
Value and Value To, without selectors/code. Native AEP independently opened the
condition dialog and filled both fields. At21:25:25UTC an actual paginated
Browser observation returned751 records with UI All(751). Independent read-only
QA confirmed751 distinct nonempty IDs and all dates2026-07-01..2026-11-09 within
the requested range. That ignored original source snapshot is retained for
later workbook comparison; it is not a generated workbook or final candidate
proof. Native candidate reachedrevision29; cold navigation/repeatability still
needs successful final run. No new Sales Order workflow is installed yet.

## Active verification checkpoint (2026-11-10, supersedes running counts above)

The6358 full suite completed6345 passed/3 failed/10 skipped; optional av
collection skipped. Two BI failures were causally reproduced as stale layout
writes and stale overview handlers, fixed without relaxing assertions; the
BI group passed57. The unchanged PowerShell startup module passed6 on recheck.
A later6384-case partial suite was aborted: concurrent build briefly removed
its sdist path during collection; failed collection shards were retried, then
all owned test workers stopped before a further evidenced hover repair. Neither
partial run is counted as passing. Build must finish before the next full suite.

Local trusted-event experiments prove a hover-gated-control gap, not the cause
of C4C navigation failure. Internal hover now precedes native activation, with
post-hover origin/unique-target/hit-test revalidation and a shared deadline.
Independent review found no blocker; eight synthetic boundaries passed. Raw
click_at is unchanged. Global Ruff/format1423 files and mypy1073 files passed.

Native AEP revision34 still has no successful whole run. Result51 was a180s
model timeout; root polled it late, an avoidable monitoring delay. The private
Host was cleanly restarted at READY to load frozen hover source and restored
without a new task. A normal business continuation is running; no candidate
script or selector was edited by root. No new workbook or installation yet.

## Five-gap delivery matrix (current checkpoint)

| Observed gap | Implemented platform behavior | Remaining acceptance |
|---|---|---|
| False success and stale outputs | Nonzero/timeout outcomes fail; outputs must be fresh; answered summary says replied | Full native report must actually succeed |
| Tested SOP lost during revisions | Durable requirements, exact-digest trial/install gate, sticky declared paginated collection | Business identity/filter correctness still needs independent report QA |
| Insufficient Browser contract/evidence | Typed actions, scoped DOM/controls, action/target failure, bounded diagnostics, pagination separation, ensure-visible/reload/native hover | No evidence yet identifying the latest specific obscuring control |
| No automatic continuation | Failed approved/form trials enter bounded repair with durable history and existing approvals | Real original workflow has not yet completed a full repair/run |
| Re-asked/invalid supplied files | Actor/session input provenance, prefilled file defaults, file preflight, original attachment retention | Changed mapping/date/FX end-to-end test pending |

PDF/XLSX/DOCX ingestion and ordered-list rendering were separately implemented
and committed earlier. Historical Codex-authored C4C success is not counted as
AEP autonomous authoring success. The new candidate is authored only by AEP.

## Additional actual-boundary repairs (2026-11-10)

Native35 failed waitactions8; automatic repair produced36 and its approval
but crashed saving its response at the100-message cap. Native36 reproduced
the same crash after producing37. Storage only admitted a two-message rollover,
while truthful Host repair adds one assistant. It also refused99+ordinary pair.
Three causal reds preceded the narrow one/two rollover fix. Eleven causal and
negative safeguards passed; expanded whole groups194 passed; independent review
no blocker. No user input was fabricated and no completed side effect replayed.
The6397-case in-progress suite was explicitly aborted before changing storage;
its partial results are not reported as passing.

Native37 exhausted its three-trial allowance with a real Document Date view
wait failure; still no workbook. Root sent an actual business QA continuation
restating Document Date/Between/All and original dates/FX, recorded as test
operator intervention. The same candidate/task persists, not a one-prompt claim.

Repeated actual inline inspect_dom calls omitted save_as and received generic
validation errors. The actual exported schema did not explain this conditional
requirement. A causal HostTool-schema regression now checks exposed guidance;
metadata and authoring guidance explain required aliases and prefer dedicated
browser__inspect for ad-hoc inspection. Runtime validators/defaults/actions are
unchanged. This improves discoverability; native acceptance remains pending.

Actual native trial38 on the rollover fix failed a Browser wait, then normal
automatic continuation saved revision39 and new trial approval without the
previous history-window exception. Result60 is retained. This verifies actual
repair persistence/continuation, not success of the requested sales report.
Root read-only review also evaluated only the candidate's pure amount parser
on USD1,234.56/TWD1.234,56/EUR123.45; amounts/currency were preserved. It did
not modify the candidate or create business output outside AEP.

## Actual native output acceptance (2026-11-10)

Revision42/version1.0.41 completed the actual whole workflow and produced a
fresh report at08:44. Independent read-only oracle compared all751 unique IDs
and copied raw values to the earlier complete Browser source; source amounts,
currencies, date bounds,29-row owner mapping, EUR conversions and106 monthly
groups reconciled with zero issues.173 unmatched owner orders remain present
with blank Sub-Dept. Proof stays private:autonomy-native-report-qa.json. This
is a new AEP-authored workflow, not the earlier Codex-authored installed asset.

Changed runtime input trial exposed starting from an old page index. AEP revised
its own browser procedure, then revision45/version1.0.44 successfully queried
Nov1..8 with alternate mapping, USD0.9/TWD0.03 and QA-only filename prefix.
Independent oracle matched28 unique source IDs, all amounts/currencies/new FX,
new mapping and11 monthly groups, zero issues. One actual output row carries
the changed QA mapping tag, proving the override was used. Original mapping
was not changed. QA rates are not official defaults.

Interim revisions43/44 drifted dates into saved defaults; root held these trial
approvals and repeated a plain-language date-range/default correction. Stored
revision45 was read back with original official dates/rates/file/prefix. These
operator QA interventions are recorded; this is not one-prompt authoring.
A cold Browser official-default replay and resident-owner transfer/trial remain.
Final source6409-case/541-module suite is running; one possible known UI failure
awaits its full traceback. Source is frozen and the verified wheel matches all
556 included Python files. No new resident workflow installation yet.

## Final platform verification and cold-query diagnosis

Runtime repairs committed locally in six narrow commits throughf872ca76, no
push. Normal full suite6409 cases/541 modules completed6397 passed,2 failed,
10 skipped. Both failed full modules reran unchanged together:14 passed387.11s.
Proposal confirmation failed at the known baseline703; viewport reattachment
failed its initial DOM read88, cause not proven. No assertions/timeouts were
weakened. Final Ruff1424files, mypy1074files, wheelbuild and clean-package pip
check passed. Final architecture review found no boundary/approval/provenance
violation. These are qualified exact results, not a single all-green full run.

Later native warm revision46 again reconciled751 unique orders/106 groups
with zero issues. Cold start remains unverified: passive observers logged real
current1,total529,max200 and30 visible rows, then later AEP read visible/26 and
correct original Date filter. AEP misattributed this to stalearia-label; source
audit proves _PAGE_NUMBERS reads innerText/value, not aria-label. Do not change
the correct parser on that explanation. Query/result readiness is the remaining
diagnostic focus; not a PDF/Excel read error. AEP-generated revision46 is retained
unchanged as a reference because subsequent UI repair unnecessarily rewrote the
verified report. No Codex business code/selector replacement was supplied.
Resident update, final owner draft/trial/install and cold acceptance remain.
