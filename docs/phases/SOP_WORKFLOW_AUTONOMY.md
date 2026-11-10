# SOP Workflow autonomy implementation — 2026-11-09

Owner approved resolving the five diagnosed gaps after reviewing
SOP_WORKFLOW_AUTONOMY_DIAGNOSIS_2026-11-09.md. Scope is the resident Agent's
authoring path, not another externally authored C4C manifest. Existing business,
installation and external-write approvals remain mandatory.

## Architecture and slices

1. Execution truth: distinguish a completed invocation from an unsuccessful
   program. A typed execution failure may carry validated capability output
   locally, so the Agent can diagnose it. Return only files created/changed by
   this invocation as outputs; old files cannot satisfy output checks. Preserve
   direct coding diagnostics and existing external MCP data withholding.
2. Browser observation: expose the actual typed action schema and a bounded,
   origin-scoped DOM inspection action. Include action index/kind and fresh
   page evidence on execution failure. No arbitrary JavaScript, HTTP clients,
   credential values or SAP-specific core code.
3. Inputs: preserve supplied parameter values/file origins with authoring state;
   prefill declarations/forms and reject directory/missing file inputs before
   browser dispatch. Keep upload ownership/root authorization unchanged.
4. Authoring state and gates: persist requirement IDs and evidence/check
   coverage with a candidate. A change invalidates validation for the previous
   digest. A verified reusable candidate must pass the current manifest's actual
   trial and declared coverage; an untested/incomplete candidate stays a draft.
   Installation approval is independent of this technical verification.
5. Repair continuation: a failed authoring trial is returned to the Agent with
   the same task context, inside a bounded continuation. Respect pending
   approvals, existing side-effect deduplication and actor/session ownership;
   never auto-repeat a successful side effect or silently reduce requirements.

## Tests before implementation

- Nonzero/timed-out Python remains failed through Bridge/Workflow/result summary,
  retains useful validated diagnostics, and cannot pass with a leftover XLSX.
- Output listing recognizes changed/new files, excludes unchanged prior files.
- Real-browser inspection exposes a scoped control/table beyond the initial
  observation cap, redacts secrets, honors origins and gives precise failure
  location/evidence. Existing read-mode restrictions remain.
- A supplied lookup path survives authoring/short history, becomes a form value,
  and folder/missing/unsupported-file errors stop before any browser call.
- Requirement omission/current-digest failed trial prevents verified readiness;
  revision invalidates old proof. Owner approval does not bypass verification.
- Failed trial resumes diagnosis with bounded attempts; pending authorization
  stops safely; replay never repeats a successful side effect.

## Acceptance and verification

Use an isolated resident Agent Web entry point with the original SOP/workbook
and approved internal Gateway. No injected selectors, scripts or known-good
Workflow. The Agent must discover, draft, trial, repair and offer its result via
AEP tools. Verify all rows/pages/current count, supplied dates, mappings,
currencies and fresh artifacts independently. Explicitly record any unmet item;
a mocked or externally repaired run cannot establish this acceptance.

Run focused regressions, full pytest for shared-runtime changes, Ruff,
typecheck and build. Record initial failures and actual reruns. Update TASKS,
DECISIONS and HANDOFF; commit verified slices on local main per owner repository
policy, never push. Resident Host deployment/restart requires the active-work
check and is separate from source verification.

## Execution ledger

- Architecture review: use existing Bridge/Workflow/authoring boundaries. Add
  typed bounded contracts; no provider-specific or C4C-specific routing.
- Ruling: the owner's request approves the preceding five-part diagnosis and
  proposed implementation direction. Do not repeat a design-approval question.
- Ruling: repository policy explicitly selects local main commits; use that
  existing workspace, with disjoint file ownership and root-controlled commits.
- Plan: execution truth, browser diagnostics and file validation can be developed
  independently; candidate state/continuation integrates them afterward.
- Status: planning complete; implementation and regressions in progress.

### Acceptance-driven data composition slice

The actual Agent prototype prepares run-specific dates, mapping path and rates,
then reads Browser data, but the reporting step receives only the latter and
hardcodes configuration. Add one atomic read-only `data/merge` capability with
two separately bound object inputs and an explicit merged output. This uses
existing Workflow input contracts; do not refactor their union or inject hidden
context into Python. Conflicting unequal keys fail rather than silently replace
owner input. Bounds/schema and a real multi-source Workflow regression precede
implementation. Teach authoring the general composition pattern; the Agent
still writes and verifies its own business Workflow.

### Acceptance-driven observation and repair follow-ups (2026-11-10)

The real candidate's failure revealed missing accessible names for SAP's
aria-labelledby fields, lost original attachment context after long discovery,
and generic recovery treating a CSS scope failure as an authorization scope.
Use shared DOM accessible-name resolution, scoped attachment-reference reuse
and an exact technical failure allowlist. Preserve actual authorization stops.

Actual trial diagnostics must survive generic preview truncation: persist
redacted bounded metadata before bulk page/rows, and include it explicitly in
the same candidate's repair request. Existing actor/digest/token checks remain.
The candidate also reused one input for current and total pages. Reject both
identical declarations and different locators resolving the same DOM element;
equal numbers from distinct last-page controls remain valid. These changes
prevent false success; they do not certify business completeness by themselves.

Repeated live revisions also revisited previously failed navigation after
history eviction. Extend the existing task with bounded actual trial history
(ten entries/12 KB, metadata and declared Browser target prefixes only), and
surface it before bulk repair context. Do not fabricate historical records,
change approvals/repair limits or forbid legitimate transient-failure repairs.

### Idempotent disclosure action (acceptance-driven, 2026-11-10)

Actual revision20 reached its date fill after blindly clicking Advanced Search;
the retained actual failure showed pressed=false and only the paginator input.
The click closed an already-open panel. A reusable linear procedure therefore
needs a conditional reveal primitive, not another guessed field selector.

Add `ensure_visible` to the existing Browser action contract, with `target`
(desired content) and `trigger` (the disclosure control). Probe only unique
CSS-visible presence using the existing finder; never read field values. If
already visible, return without clicking. Otherwise native-click the trigger
once under the existing origin/read policy, then poll target within one shared
deadline. Ambiguity/invalid selectors/origin errors fail immediately; only a
genuinely missing target permits the trigger. Tag failures as
`ensure_visible.target` or `ensure_visible.trigger`, preserving existing codes.
Only this action accepts `trigger`; ordinary click behavior remains unchanged.

This stays in deterministic local execution. No Workflow engine condition,
recording subsystem, new permission or dependency is added. Existing owner
authorization for the five repairs covers this necessary repeatability fix.
Architecture review found no boundary conflict. A broad recorder is deferred;
blind toggle retries were rejected because they can close desired content.

Before implementation, regressions cover hidden/visible initial state, repeated
replay, a single click followed by timeout, target ambiguity with zero clicks,
read-mode refusal when a click is needed, origin checks and invalid trigger
placement. Generic schema/authoring guidance must expose the operation without
C4C selectors. Presence does not establish business success or reusable proof.

Reuse the value-free presence probe for `wait_for` when `value` is omitted.
Provided regular expressions retain their existing full-text semantics. This
avoids treating an icon caption or a multiline table as text matching `.*`;
presence waits do not need to read field values. Keep existing origin/read
boundaries and a bounded timeout. Add actual Edge coverage for both forms.

### Preserve declared collection completeness (2026-11-10)

Native revision27 removed read_table.pagination after pagination-limit errors,
while weak model-written present(actions) assertions still reported complete
coverage. This can certify a first-page workbook; do not approve it as complete.
Add a narrow sticky obligation in the existing actor/session AuthoringTask,
derived from a real declared paginated Browser collection and identified by
capability/output save_as plus source digest. Ordinary draft/plan replacement,
output rename/removal or candidate-id replacement cannot erase the obligation.
Only the matching collection's complete read strategy satisfies coverage; an
unrelated dummy pagination does not. Prototypes remain draftable/runnable but
cannot become verified or install-ready while completeness is unproven.

Architecture review approves this minimal readiness boundary. A genuine
alternative full export can be prototyped, but file existence or a model's
complete=true is not full-collection evidence. Supporting that alternative's
verified proof requires a future deterministic count/provenance contract; do
not add a guessed bypass now. Legacy tasks have a compatible empty default;
capture only real declarations, without invented historical backfill. This
guard prevents observed regression, not every weak initial requirement plan.
Regression tests precede implementation: dropped paging despite weak coverage,
dummy/renamed/removed collections, task/candidate continuity, stale proof and
restored matching pagination. Existing approval and repair budgets remain.

### Explicit fresh-document reload (2026-11-10)

Actual failed trial32 retained the Document Date condition widget and two popup
date fields at the Home Nav/0 URL, after a preceding failure left the dialog
open. Native revision33 attempted about:blank as a reset; root held that trial
because the origin policy does not authorize it. A local real Edge experiment
confirmed hash navigation keeps loader ID/modal/JS sentinel and old complete
state; Page.reload changes loader, clears the fixture modal/sentinel and keeps
the viewport. This supports an explicit reload primitive, not changing open.

Add no-argument WebAction.reload using the same Browser/tab/profile. Require
act mode (conservative for possible form resubmission); never accept a
confirmation dialog or restart the browser. Before reload obtain main loader,
send Page.reload once, then require a different nonempty main loader and that
new document's complete state within one shared monotonic deadline including
CDP commands. Origin is checked before/during/after. Do not use _await_load,
which can return after an event timeout without establishing a new document.
No URL/script/new permissions or app-specific selectors. Existing open/click
semantics remain. Architecture review approves this necessary repeatability
repair within the owner's five-gap scope. Regressions precede implementation:
real SPA modal reset, old-complete refusal, new-loader timeout, redirect origin
stop, read-mode refusal, argument validation and preserved viewport.
After readiness is read, recheck the same main frame and loader before success;
an intervening B-to-C document change resumes observation under the original
deadline without sending another reload. Independent adversarial CDP review
proved the missing post-readiness check could pair B's complete with C/loading.

### Native hover before activation (2026-11-10)

A local trusted-event experiment disproved a missing-buttons hypothesis: raw
click_at already sends buttons=1 on press. It proved a separate fidelity gap:
without mouseMoved, pointer entry first occurs while pressed, so a hover-gated
control can refuse activation. This is not proof of the C4C failure's cause.
Architecture review approved an internal optional hover helper, retaining raw
click_at semantics. ScriptRunner hovers only after act authorization, uniqueness
and hit testing, then rechecks origin, deadline and the same target. Moving
targets are observed again within the original deadline; ambiguity, overlays
and origin changes stop before press. Press/release occur once without replay.
No public action, permission, app selector or forced JavaScript click is added.
Causal tests cover trusted events, moving targets, obscured and ambiguous targets,
read refusal, origin, socket failure and shared deadlines. Independent review
found no blocking issue and eight synthetic boundaries passed.

### Long-session automatic repair persistence (2026-11-10)

Actual native trial35 failed at wait_for actions8; its automatic repair saved
revision36 and a new trial approval, then crashed at web.py save_conversation
with conversation_update_stale. The full100-message window only permits a
two-message rollover; automatic continuation truthfully adds one assistant.
A99-message window receiving an ordinary owner/result pair also overflows
by one. Add causal storage and real-repair regressions before implementation.
Allow only one- or two-message appends with the corresponding retained old
suffix and unchanged timestamp/actor/monotonic protections; reject rewrites,
shrinks, stale snapshots and three-message rollover. Do not invent user input,
restart/replay the trial or recreate the already persisted candidate/approval.
This is a narrow gap4 continuation fix; no new capability or side effect.
