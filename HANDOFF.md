# SOP Workflow autonomy — source verified; C4C acceptance incomplete

Checkpoint: 2026-11-10 01:31 Asia/Taipei. Branch main. Owner asked to resolve
five diagnosed platform gaps and verify that AEP itself can author the supplied
C4C SOP Workflow. Do not claim end-to-end success. No resident Host rollout,
restart, production Workflow replacement, installation or push has occurred.

## Read next

- docs/phases/SOP_WORKFLOW_AUTONOMY.md: scope and acceptance boundary.
- docs/evaluations/SOP_WORKFLOW_AUTONOMY_REPAIRS_2026-11-09.md: failed attempts,
  actual source verification and live acceptance evidence.
- docs/CONTRACTS.md and docs/DECISIONS.md: new contracts and rationale.
- docs/TASKS.md: five-gap task deliberately remains open.

## Committed implementation

- 296de745: execution failures retain validated local diagnostics; failed Python
  and unchanged old files cannot satisfy output checks.
- 98e7fc9e: supplied file inputs persist/prefill and validate before dispatch.
- 6be7371b: bounded origin-scoped Browser evidence, semantic overview, CDP
  deadlines and stable desktop viewport on attachment/reattachment/popups.
- d90e75bf: durable actor/session SOP task, immutable requirements, editable
  technical assertions, exact-current proof, partial prototypes, bounded repair,
  pending approvals and current draft-card installation gates.
- 6d71bb87: new real owner input can reopen exhausted allowance; automatic
  repair cannot. Input event identity preserves later repeated replies.
- fe1d0187: pure read-only data/merge composes prepared parameters and Browser
  rows through existing bindings; conflicts refuse, no hidden runner context.
- b0bee30b: shared accessible names from aria-labelledby/HTML labels/fallbacks.
- a6115825: original same-session SOP source notes/images survive long discovery
  and repair turns with existing ownership/root/preview limits.
- ee3ab23a,797a63ee: exact technical error recovery allowlist distinguishes CSS
  scope from authorization scope and preserves all existing limits/approvals.
- 0d3c5562: at most12KB redacted actual trial/action diagnostics precede bulk
  previews in repair; Python tail/invalid controls retained, raw rows omitted.
- 13b99445: current and total page controls must differ in declaration AND
  actual resolved DOM identity on every poll; safe boolean invalid state.

Independent reviews closed the pagination locator-alias bypass and found no
remaining blockers in the final recovery/diagnostic/browser slices. No candidate
code or selectors were edited by Codex in this live acceptance.

## Verification

Initial full suite:6162 cases in532 modules;6142 passed,10 failed,10 skipped,
plus missing optional av collection skip. Original shard logs/XML retained.
Every initial failure has a passing affected rerun (environment, unchanged
Browser/BI/library cases, actual-trial fixtures and in-flight proof token).
Do not rewrite this as an initially all-green full run.

Final affected verification:505 passed,1 optional desktop GUI skip,37 modules,
554.40s. Logs .scratch/autonomy-verified-tests.log/.xml. Earlier389 and434 runs
are overlapping evidence; do not add counts. Focused final groups114 recovery,
58 authoring diagnostics and42 Browser/script cases also overlap.

Configured global Ruff/format pass (1419 files at check); configured mypy1069
files pass. Logs .scratch/autonomy-final-{ruff,mypy}.log. Current sdist/wheel
build passed (.scratch/autonomy-current-build.log). Separate clean wheel install
with existing office/weekly-mail extras passed pip check and CLI --help. The
system-site-packages test venv has unrelated global OpenCV/tifffile/streamlit
pip-check conflicts; the owner's global interpreter was not changed.

## Actual private AEP-only acceptance

Root: .scratch/autonomy-acceptance-desktop-20261109 (ignored business material).
Uses actual AgentWeb/LocalAgent/Bridge and configured approved internal Gateway;
original owner PDF/XLSX, automatic SSO, query/filter/export/local Excel only.
No SAP HTTP/Python retrieval, order edits, mail, known-good manifest injection
or manual selector/script repairs. General business continuation requests and
operator approval of reviewed safe trial revisions ARE recorded interventions.

Candidate wf-20261109-151306-c1b4f6,
engineering/c4c-sales-orders-monthly-eur, revision10/version1.0.9.
Same candidate throughout. No verified workbook or installation yet. Previous
manual750-row report is NOT autonomous acceptance evidence.

Current isolated Host process: exec session23279, private harness
.scratch/accept_autonomy.py --restore-loop. Its latest approved trial
ap-20261109-172854-14a22f is running. Revision9 failed navigation, and AEP
independently restored its discovered navigation procedure in revision10.
Poll before commands; never send commands mid-turn. Last saved result12 is
revision10 awaiting that now-approved trial; next result13 expected.
Telemetry SQLite and tool-observations.jsonl show actual progress. No result
should be treated as proof unless current revision complete actual trial passes.

At READY_FOR_NEXT_REQUEST:
- approve <approval_id>: normal approval only after reviewing candidate diff.
- install <draft-card-id>: only after independent business acceptance.
- quit: stops ONLY this private isolated Host.
- Plain text sends a real business continuation, resets exhausted repair budget
  as real owner input; record it honestly, never describe as zero intervention.

--restore-loop restores without adding a new turn; --resume-loop sends the
existing general business continuation. To restart this isolated fixture only:
$env:AEP_ACCEPTANCE_ROOT='autonomy-acceptance-desktop-20261109'
python .scratch/accept_autonomy.py --restore-loop

Live failures exposed responsive overlay, missing accessible names, lost source
references, inadequate composition, recovery misclassification and diagnostics
truncation. Candidate5's same-input paging was blocked; AEP fixed it in6, then
repaired navigation in7/8 and date targeting/localized amount parsing in9.
Generated page IDs change after reopening; repeatable navigation/date filtering
and full report are still unproven. Do not mark all five problems complete.

## Next actions

1. Poll current23279; inspect actual next candidate diff for safe authorized
   operations, approve normally, let AEP repair its own candidate.
2. Verify full filtered UI count vs all exported uniqueIDs/pages, both date
   bounds2026-07-01..2027-06-30, mapping and unmapped exceptions, amounts,
   monthly sums, fresh workbook and changed-parameter propagation.
3. Latest owner confirmed1TWD=.02712085EUR; USD=.87. Do not reask known inputs.
4. Do not fix the business manifest externally to make acceptance green.
5. Keep docs current and commit docs locally. Any further source change needs
   corresponding tests/verification before claim/commit.
6. Before resident deployment/restart inspect ALL active runs/turns/forms;
   refuse or wait while interactions exist (AGENTS19). Isolated source checks
   are distinct from actual resident rollout. Never push without instruction.
