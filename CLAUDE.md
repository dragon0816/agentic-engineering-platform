# Claude Code Instructions

Claude Code is a replaceable coding worker in this repository. GitHub and committed repository artifacts are the persistent project state; conversation history is not.

## Required startup sequence

Before modifying code:
1. Read `docs/ARCHITECTURE.md`.
2. Read `AGENTS.md` for shared repository engineering rules.
3. Read `docs/ROADMAP.md`.
4. Read `docs/TASKS.md` for what is done and what is next.
5. Read the most recent phase specification, `docs/phases/PHASE_6_EVALUATION.md`. Phase 6 is complete and no phase is active; Phase 7 waits on the pending owner decisions in `docs/TASKS.md`.
6. Read `HANDOFF.md`.
7. Inspect `git status`, recent commits and the current diff.
8. Use the applicable procedures under `.agents/skills/`.

## Source of truth

`docs/ARCHITECTURE.md` is the architectural source of truth. Do not redesign the architecture during an implementation task unless the task explicitly requests an architecture change.

No phase specification is active: Phase 6 is met (`docs/phases/PHASE_6_EVALUATION.md`) and Phase 7 is not specified. Do not write `docs/phases/PHASE_7_*.md` until the pending owner decisions in `docs/TASKS.md` are answered; until then the scope of any task is what the owner asks for, plus the open items carried forward in `docs/TASKS.md`. `docs/TASKS.md` is the progress record: completed slices are kept there, never deleted, and every slice adds a row rather than replacing one. `HANDOFF.md` records resumable execution state, not architecture and not progress; it is rewritten each time and carries only where the current work stopped.

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
