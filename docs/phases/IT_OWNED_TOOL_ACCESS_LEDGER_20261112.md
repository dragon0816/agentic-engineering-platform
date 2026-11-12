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
