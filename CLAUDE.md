# Claude Code Instructions

Claude Code is a replaceable coding worker in this repository. GitHub and committed repository artifacts are the persistent project state; conversation history is not.

## Required startup sequence

Before modifying code:
1. Read `docs/ARCHITECTURE.md`.
2. Read `docs/PRODUCT_VISION.md` for product direction.
3. Read `docs/PRODUCT_ACCEPTANCE_TESTS.md` for the mandatory E2E order and gates.
4. Read `AGENTS.md` for shared repository engineering rules.
5. Read `docs/ROADMAP.md`.
6. Read `docs/TASKS.md` for what is done and what is next.
7. Read the relevant active specification. Phase 7 source migration is under
   `docs/phases/PHASE_7_MIGRATION.md`; product E2E work uses the gate document
   named by `docs/TASKS.md` and `HANDOFF.md`.
8. Read `HANDOFF.md`.
9. Inspect `git status`, recent commits and the current diff.
10. Use the applicable procedures under `.agents/skills/`.

## Source of truth

`docs/PRODUCT_VISION.md` defines product direction,
`docs/PRODUCT_ACCEPTANCE_TESTS.md` defines the required E2E sequence and gate,
and `docs/ARCHITECTURE.md` defines the implementation architecture. Do not
redesign the architecture during an implementation task unless the task
explicitly requests an architecture change.

Phase 7 is active under `docs/phases/PHASE_7_MIGRATION.md`; source decisions are
in `docs/PHASE_7_MIGRATION.md`. Follow its migration order and never claim live
parity from inert CI. `docs/TASKS.md` is the progress record: completed slices are
kept there, never deleted, and every slice adds a row rather than replacing one.
`HANDOFF.md` records resumable execution state, not architecture and not progress;
it is rewritten each time and carries only where the current work stopped.

Phase 7 and the product E2E sequence can both be active. Continue the work named
in `HANDOFF.md`; do not substitute a Phase 7 backlog item for an active product
gate. Never begin the next E2E gate until the preceding gate meets the exact
completion condition in `docs/PRODUCT_ACCEPTANCE_TESTS.md` and `docs/TASKS.md`.

## Required workflow

Architecture -> Requirements -> Contracts -> Tests -> Implementation -> Verification -> Commit -> Handoff

Before implementation, apply `.agents/skills/architecture-guard/SKILL.md`.
For planning, apply `.agents/skills/implementation-planning/SKILL.md`.
For shared contracts, apply `.agents/skills/contract-development/SKILL.md`.
Before completion or transfer, apply `.agents/skills/code-change-verification/SKILL.md` and `.agents/skills/handoff/SKILL.md`.
When migrating existing behavior, apply `.agents/skills/migration/SKILL.md`.

## Handoff

Codex, Claude Code and humans may alternate on the same branch. Never depend on another coding agent's chat history.

When taking over: read the committed state, run verification, reconcile `HANDOFF.md` with the repository, then continue from the next recommended action.

When stopping: leave a reproducible state, commit completed coherent work, clearly document incomplete work, verification results and the next action in `HANDOFF.md`, and add the finished work to `docs/TASKS.md`.

Do not claim tests passed unless they were actually run.
