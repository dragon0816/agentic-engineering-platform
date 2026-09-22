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
- `CLAUDE.md` and `AGENTS.md` still name `docs/phases/PHASE_6_EVALUATION.md`
  as the active specification, as they named Phase 5's until Phase 6 began.
  That specification now says the phase is met, so a reader is not misled;
  the pointer moves when a Phase 7 specification exists.

## In Progress

- PR #46 (this closure) open for review. Nothing else uncommitted.

## Remaining

Phase 7, "End-to-end migration and deprecation", has no specification yet.
The Roadmap says: run representative production-like scenarios against old
and new paths; deprecate source components only after parity and acceptance
criteria are met; keep rollback documentation during the transition. Writing
that specification needs decisions only the owner can make:

1. **Which source components are candidates for deprecation**, and in what
   order. The source inventory in `docs/ARCHITECTURE.md` names five
   repositories; Phases 2 to 6 migrated or deliberately declined pieces of
   each, and `docs/PHASE_N_MIGRATION.md` records what was declined and why.
2. **What "parity" means for each**, in terms this platform can measure. The
   evaluation harness can express a parity check as a case, but somebody who
   uses the source tools has to say which behaviours matter.
3. **What production-like means here.** Every test in the repository is
   inert by design. A Phase 7 scenario that talks to a real Ollama, the real
   company gateway, a real vault or a real n8n needs a host, credentials and
   a place to run that is not CI, and the owner decides where that is.
4. **Rollback and retention** for source repositories: archived, frozen or
   deleted, and who owns them during the transition.

A smaller piece of work that needs no decision: neither model adapter has
been run against a live endpoint (`docs/TASKS.md`, "Never exercised against a
live endpoint"). One real request against each would confirm the field names
before Phase 7 relies on them.

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
put the four Phase 7 questions above to the owner; do not write
`docs/phases/PHASE_7_*.md` until they are answered.
