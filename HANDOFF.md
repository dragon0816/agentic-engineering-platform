# Feature-plugin assessment — proposal complete, no implementation

Updated 2026-11-13. Worktree:
C:/Users/Chi_L/.paseo/worktrees/2qnenase/it-owned-tools-20261112
Branch: it-owned-tool-access-20261112. Implementation commit d1653a45;
long-path fixture commit 6a1488ed; earlier feature slices through f490ebb1.
Tool feature and verification were pushed with owner consent: remote branch
it-owned-tool-access-20261112 was checked at a902df0f58650afc360ee4f6ed59b5ebda9e3f57.
No main update, resident restart, shared Gateway edit or previous C4C package
replacement. Do not imply the running resident uses this branch.

## Latest task: feature plugin assessment

Owner requests LLM Wiki, BI Knowledge and future feature GUI/API/processing/data/
Skills/tools/Workflows as separately installable plugins. Assessment completed:
docs/phases/FEATURE_PLUGIN_ASSESSMENT_20261113.md. Source inspection only; changes
are docs. No runtime edits/new packages/company processing/full tests needed or
performed. git diff --check and source reference existence checked separately.
Proposed first common Plugin API upgrade, then compatible plugin-only updates;
reuse assets/extension process/repo primitives, add generic Web/API/provider/
data-lifecycle registration, stage BI then Wiki, preserve Knowledge asking.
Existing ExtensionManager.activate still requires ExtensionActivationApproval;
new installer must align with no-tool/IT-approval owner policy, not copy that gate.
This is a proposal only; obtain scoped AGENTS22 consent before harness edits.

Previous merge assessment: fetched main267c75e4 and dry merge found3doc conflicts
(HANDOFF/DECISIONS/TASKS), no source text conflicts. Main adds e564e1ad's unchanged
workflow_form_runs.py legacy success inference; its blob is identical in that
commit, current main and dry merged tree. Existing synthetic false-success
finding remains relevant. Do not merge unchanged; no actual merge was performed.
Branch currently has no matching CI run (push branch filter excludes its name).
Do not conflate old branch validation with the untested combined merge result.

Assessment docs are a separate local commit after the pushed feature; they are
not silently pushed or treated as owner implementation approval.

## Goal and scope

Owner explicitly approved four harness changes: unified tool registration across
Bridge/MCP/conversation backends; no AEP grants, install/execute approval cards or
extra command/folder/mail admission; same-session install/connect/use; preserve
real outcomes, successful-effect deduplication and Knowledge evidence/citations.
No change to model/data classification. Skill-first causal evidence and explicit
scope consent are in DECISIONS and IT_OWNED_TOOL_ACCESS_DESIGN_20261112.md.
AGENTS22 still applies to expansions. Do not ask again for already covered work.

Latest owner clarification2026-11-13: no IT prerequisite; if tools can execute in
the environment, they can be used. No IT approval branch existed. Follow-up edits
are only UI/prompt/Skill/audit wording and current requirements, not control flow.
Historic IT-owned phase filenames are identifiers, not an authorization system.
Follow-up verification: focused first92pass1timing-failure2skip (2.062s vs<2s),
unchanged command module rerun7pass9.39s; combined93pass2skip, not first-run green.
Ruff/format1482/mypy1117/build/pipcheck pass;571wheel Python files match source.
Python ASTs unchanged except string literals in11files, no new full run needed.
See docs/phases/DIRECT_TOOL_USE_CLARIFICATION_20261113.json for exact provenance.

## Completed

Tasks1–8 complete. Typed ToolAccess discovery/invoke/install; current-session MCP
refresh; builtins independent of grants/profile tool selections; direct local
asset install without fake business review; schedule and BI-local admission
removed; Outlook read/query pagination and separate draft/send; native adapters
add no AEP tool-disable/sandbox/approval relay and bypass no external guard.
Shared async execution lease and successful receipts cover gateway/native/direct
workflow calls. MCP collision/ownership rollback, process-tree deadlines, exact
Skill-version rollback/profile references, actual run display receipts and
replay-digest verification are covered. Generic native unknown-eligibility tool
results return status only with an explicit data-route diagnostic. Existing
Knowledge/model/source rules remain. No third-party dependency was added.

## Verification: actual results and limits

Read docs/phases/IT_OWNED_TOOL_ACCESS_ACCEPTANCE_20261113.md and corresponding
VERIFICATION JSON for source/report/wheel hashes and case-level provenance.
- Initial full:6682passed37failed15skipped8390.40s; raw reports retained. Old
  admission expectations migrated; real version/profile/receipt defects fixed
  with causal reds/greens. Same445Knowledge baseline cases all passed then.
- Final core full:6724passed2failed15skipped7933.08s. NOT one green full run.
- Long-path fixture: input setup failed before import at deep temp root. Final
  test-only source uses short TemporaryDirectory; destination still>260 and
  Raw/publication/read/digest assertions unchanged. Short/deep reruns each1pass.
- Conversation failure: RemoteDisconnected from pre-existing Win32 long session
  atomic-write path, not timeout. Baseline and current writers both reproduce;
  workspace.py and authoring_task.py unchanged. Whole module at short root6pass.
- BI delta55pass after the full snapshot; it is separately validated, not claimed
  covered by the old full. Exactly6BI files plus1fixture differ from frozen core;
  web_page outside BI tools rendering unchanged.
- Combined current-case evidence6726passed15skipped; zero missing collected cases.
  This reconciles6740collected cases+1collection-level skip;3JWT time-generated
  parameter IDs match by family/count, all others exact. Same445Knowledge cases
  match baseline outcomes after the named fixture rerun, without normalization.
- Ruff check/format1481 pass; configured mypy src+tests1117 pass; build sdist/wheel
  and pipcheck pass. Isolated --target wheel install/import passes. All571Python
  wheel sources match current source after newline normalization, no extras.
- Required fresh source reviewer: no remaining Critical/Important findings,
  including focused BI delta review. This is not live system proof.

## Known remaining limitations

Generic session persistence at Win32 workspace paths beyond260 remains a known
baseline limitation. No unrelated state-storage harness expansion was made.
No live Outlook/mail send/thread, C4C, real provider, arbitrary third-party tool
or company instrument test. Deterministic Knowledge tests do not prove stochastic
model answer quality. Native unknown eligibility may withhold raw tool content;
execution permission is not model-data authorization. Existing legacy native
content/provider paths are not certified end-to-end egress isolation by this work.

## Continuing safely

Do not repeat hours of full tests without a concrete change/failure. Local code
is verified; deployment/replacement end-user package is a separate next step.
Use original repo .venv/Scripts/python.exe with this worktree/src;tests first on
PYTHONPATH. NEVER rebind the shared editable installation. For checks use
AEP_OUTLOOK_TESTS=0,AEP_GUI_TESTS=0,AEP_NATIVE_CLI_TESTS=0 and a fresh SHORT owned
C:/TEMP basetemp. Raw evidence and build live in .scratch/it-owned-verification/.
No full-suite watcher remains. TASKS and DECISIONS contain the closeout/boundary.
