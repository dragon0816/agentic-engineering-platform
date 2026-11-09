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
