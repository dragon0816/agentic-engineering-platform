# IT-owned tool access — local implementation and verification complete

Updated 2026-11-13. Worktree:
C:/Users/Chi_L/.paseo/worktrees/2qnenase/it-owned-tools-20261112
Branch: it-owned-tool-access-20261112. Implementation commit d1653a45;
long-path fixture commit 6a1488ed; earlier feature slices through f490ebb1.
This handoff and final acceptance evidence are committed after those changes.
No feature push, main update, resident restart, shared Gateway edit or previous
C4C package replacement. Do not imply the running resident uses this branch.

## Goal and scope

Owner explicitly approved four harness changes: unified tool registration across
Bridge/MCP/conversation backends; no AEP grants, install/execute approval cards or
extra command/folder/mail admission; same-session install/connect/use; preserve
real outcomes, successful-effect deduplication and Knowledge evidence/citations.
No change to model/data classification. Skill-first causal evidence and explicit
scope consent are in DECISIONS and IT_OWNED_TOOL_ACCESS_DESIGN_20261112.md.
AGENTS22 still applies to expansions. Do not ask again for already covered work.

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
