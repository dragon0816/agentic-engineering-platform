# Claude Code Instructions

Claude Code is a replaceable coding worker in this repository. GitHub and committed repository artifacts are the persistent project state; conversation history is not.

## Required startup sequence

Before modifying code:
1. Read `ARCHITECTURE.md`.
2. Read `AGENTS.md` for shared repository engineering rules.
3. Read `docs/MIGRATION_PLAN.md`.
4. Read the active phase specification, currently `docs/PHASE_1_FOUNDATION.md`.
5. Read `HANDOFF.md`.
6. Inspect `git status`, recent commits and the current diff.
7. Use the applicable procedures under `.agents/skills/`.

## Source of truth

`ARCHITECTURE.md` is the architectural source of truth. Do not redesign the architecture during an implementation task unless the task explicitly requests an architecture change.

`docs/PHASE_1_FOUNDATION.md` defines the current implementation scope. `HANDOFF.md` records resumable execution state, not architecture.

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

When stopping: leave a reproducible state, commit completed coherent work, clearly document incomplete work, verification results and the next action in `HANDOFF.md`.

Do not claim tests passed unless they were actually run.
