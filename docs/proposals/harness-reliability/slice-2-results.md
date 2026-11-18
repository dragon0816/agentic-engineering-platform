# Slice 2 — operation ownership results

The selected direction is implemented locally on harness/reliability-141. No
running host, production database, BI checkout or vault was modified.

## Behavior

- The existing host state database atomically owns a resource before a Python or
  Coding Harness task worker starts. Both adapters use the same workspace key.
- Bridge timeout/cancellation leaves the claim unknown and blocks another task
  for that workspace with non-retryable operation_in_progress. The operation ID
  remains in the existing CapabilityResult.warnings and local/channel rendering.
- The actual worker acknowledges completed/failed status and releases the claim.
  An unknown process result keeps the claim even after its worker returned.
- Host restart does not expire claims. Separate connections using the same state
  database coordinate atomically. Different resource keys can proceed.
- Claim acknowledgment failure prevents dispatch. Finish acknowledgment failure
  leaves an unresolved claim when the final write was not persisted; an ambiguous
  commit may already contain the worker's terminal observation, which must be
  inspected rather than assumed absent. Completion cannot be downgraded by a late
  timeout, or overwrite an operator reconciliation.
- Schema 6 migrates additively to 7, preserving existing rows. Older binaries
  reject 7 rather than ignoring active claims. See slice-2-design.md for rollback.

## Operator inspection and recovery

These commands print metadata only. Run against the intended host configuration;
development tests use disposable configuration/state. List includes the latest
50 records; an older known ID can be inspected directly.

```powershell
aep-host operations --config <host.json>
aep-host operations --config <host.json> --operation-id <operation-id>
```

Do not infer stopped execution from timeout, elapsed time, missing PID or a
restarted host. First establish that the original worker/process and downstream
effects stopped; reconcile their outcome as necessary. Only then:

```powershell
aep-host reconcile-operation --config <host.json> --operation-id <operation-id> --confirm-stopped
```

This reuses the journal's existing SuspensionConfirmation, records the configured
operator and marks the operation failed/operation_reconciled. It never claims
successful output and does not retry. The command has no model-exposed tool.

## Verification

- Before schema assertion update: 48 passed, 1 failed because an existing migration
  test still expected version 6. Updated that assertion to 7.
- Focused runtime/Workflow/host/restricted group: 105 passed, 1 skipped (installed
  live coding runner absent). An overly short 30 ms normal-call deadline in the
  new fixture was corrected after one load-sensitive failure; only its intended
  blocked worker now uses the short deadline.
- Final ownership + reporting regressions: 22 passed in 2.52 seconds. Includes an
  actual Windows restricted Python process: first call timed out, conflicting
  replay was rejected, the real worker later acknowledged completion, and its
  scratch effect file contained exactly one line.
- Caller cancellation, reopen/reconciliation, two SQLite connections, independent
  workspace, unknown result, persistence failures, migration preservation and
  real CLI inspection/reconciliation are covered.
- A live gpt-5.6 native-loop controlled Excel trial passed: real injected exit 1,
  failed operation retained, second worker completed, independently verified
  workbook values; 3 model turns/2 workers. See controlled-excel-benchmark.md.
- Final Ruff check passed; format check: 1319 files already formatted; mypy:
  success for 980 source files; wheel/sdist build succeeded; pip check passed.
- Final full run exposed a second obsolete migration assertion in
  test_portable_task.py (expected 6 instead of 7). Updated the test expectation;
  fresh migration/ownership/reporting/host group: **56 passed in 5.47 seconds**.
  Ruff and mypy passed again. No production behavior changed during this full run.
- First S1 full suite: 5298 passed, 35 skipped, 10 BI failures. Baseline and
  short-path reproduction are documented in baseline-regression-notes.md.
  Final S2 full run completed on 2026-11-19: **5315 passed, 35 skipped, 4 failed
  in 1723.74 seconds**. Three failures are the separately reproduced baseline BI
  cases. The fourth is the obsolete portable-task migration assertion, corrected
  and covered by the fresh 56-pass group above. No entire-suite rerun after that
  test-only correction is claimed. Raw log/XML: `.scratch/pytest-final-s2.log`
  and `.scratch/pytest-final-s2.xml`.

  Full command (PYTHONDONTWRITEBYTECODE=1, AEP_GUI_TESTS=0):

  ```powershell
  .\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp C:/tmp/aep-reliability-141/final-s2-1 --junitxml=.scratch/pytest-final-s2.xml
  ```

  Final correction check:

  ```powershell
  .\.venv\Scripts\python.exe -B -m pytest tests/test_portable_task.py tests/test_operation_ownership.py tests/test_harness_reliability.py tests/test_host_wiring.py -q -p no:cacheprovider --basetemp C:/tmp/aep-reliability-141/migration-final-1 --tb=short
  ```

Architecture guard: Bridge retains deterministic execution ownership, the Agent
retains planning/repair, existing Workflow/Skill/result/permission mechanisms are
reused, and no framework/database/RBAC replacement was introduced. Only the
owner-selected operation lifecycle is added. Known private gateway credential and
delivery reference were checked absent from the staged diff. Original worktrees
remained clean. Final work is local only, with no running-host migration.

## Boundaries

This does not kill a worker, prove external effects rolled back, or cover every
Office/MCP/thread handler. Exact workspace identity does not detect overlapping
parent/child roots. Separate state databases do not coordinate. Low-level direct
library calls without Bridge context remain outside the claim mechanism.
No lease expiry, automatic reconciliation or blind side-effect retry was added.
The original SOP/PDF incident still needs its actual inputs/runtime evidence.
