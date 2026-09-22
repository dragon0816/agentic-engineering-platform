# Handoff — Phase 6 closed; Phase 7 awaits owner decisions

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-6/closure`, based on `main` after PR #45 merged.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

Record Phase 6 as complete against its Roadmap exit criterion ("evaluation
suite runs in CI without production side effects and blocks known
regressions") and leave the repository ready for Phase 7 to be specified.

## Owner decisions in force

Listed with their dates in `docs/TASKS.md`. The ones that shaped Phases 5 and
6: Codex and Claude Code are excluded as model providers (2026-09-21) and out
of scope for Phase 6 entirely (2026-09-22); provider adapters are in-process
code and the platform never starts a provider process (2026-09-21).

## Completed

- Phase 6, five slices, PRs #39, #41, #42, #43 and #45 (`docs/TASKS.md`).
  Each was reviewed and every finding applied before merge.
- This closure: the Roadmap status line and a dated "Met" paragraph under
  Phase 6, the Architecture status line, a Phase 6 paragraph in the README,
  the "Met" note in `docs/phases/PHASE_6_EVALUATION.md`, and the Phase 6
  section of `docs/TASKS.md` marked complete with the open items carried
  forward.
- `CLAUDE.md` says no phase specification is active and that
  `docs/phases/PHASE_7_*.md` is not to be written until the pending owner
  decisions in `docs/TASKS.md` are answered. Those decisions live in
  `docs/TASKS.md`, not here, because this file is rewritten on every handoff.

## In Progress

- PR #46 (this closure) open for review. Nothing else uncommitted.

## Remaining

Phase 7, "End-to-end migration and deprecation", has no specification yet,
and writing it waits on the four questions under "Pending owner decisions" in
`docs/TASKS.md`: which source components are deprecated and in what order,
what parity means for each, where production-like scenarios may run and with
whose credentials, and rollback and retention for the source repositories.

The one live request against each model adapter that would confirm the
provider field names (`docs/TASKS.md`, "Never exercised against a live
endpoint") waits on the third of those: nothing in this repository may talk
to a real endpoint until the owner says where that is allowed to happen.

## Architecture decisions made

None in this closure. Phase 6's are in `docs/PHASE_6_MIGRATION.md`.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed.
This branch changes documentation only; the suite was run to confirm nothing
reads the changed files:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 677 passed, 3 skipped (link privileges)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS
git diff --check
# PASS
```

No model, gateway, network, real vault, job or n8n instance was invoked.

## Known issues / limitations

Carried forward in `docs/TASKS.md` under "Open items carried forward". For
Phase 6 specifically: nothing persists an `ExecutionTrace` yet; the
repository's single credential pattern is deliberately narrow; and
`stayed_in_namespace` has no allowance for a capability legitimately shared
across namespaces.

## Next Recommended Action

Merge PR #46 on green CI and flip its row in `docs/TASKS.md` to `done`. Then
put the four pending owner decisions in `docs/TASKS.md` to the owner; do not
write `docs/phases/PHASE_7_*.md` until they are answered.
