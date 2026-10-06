# fix-run-001 is invalid (kept as evidence)

Stopped after T10 on 2026-10-06. Do not use its results for scores.

- T01-T08 ran while the coding runner interpreter could not start under
  restricted execution: every `coding__run` returned exit code
  `0xC0000135` (STATUS_DLL_NOT_FOUND), so no script ran.
- Cause (D4, evaluator-side environment, not AEP code): an access-control
  entry for an AppContainer SID was left on the runner's folder by an earlier
  AppContainer feasibility probe (2026-10-06). With it, the low-integrity
  test process could not read the runner's own files. The probe's profile
  had been deleted, but this entry had not.
- The entry was removed while the run was in progress, so T09-T10 ran under a
  different environment from T01-T08. The run is therefore inconsistent.
- Prevention: the coding doctor check now starts the runner the way a coding
  run does (restricted) and imports pytest and openpyxl.

Rerun: `fix-run-002`, all 20 tasks, same fixtures and validator version.
