# Development Handoff

This file is the durable handoff state between Codex, Claude Code and human contributors. Update it when ownership changes or a meaningful implementation slice completes.

## Current phase

Phase 1 — Foundation

## Current branch

`phase-1/foundation`

## Goal

Implement the minimal provider-neutral, side-effect-free foundation defined in `docs/phases/PHASE_1_FOUNDATION.md`.

## Completed

- Phase 0 architecture and migration plan.
- Multi-user contribution-driven platform requirements.
- Team Platform Plane vs Personal Engineering / Execution Plane.
- Personal Engineering Agent and Bridge responsibility split.
- Engineering Capability Flywheel and contribution lifecycle.
- Coding-agent-neutral development workflow and handoff design.
- Scoped asset identity (`namespace`/owner/visibility) and cross-server-safe naming baseline.
- Agent-assisted contribution model with department business review plus technical/policy risk checks.
- Explicit local-vs-central execution dependency contract.
- Provider-neutral secret-reference boundary; no secret values in Registry assets.

## In progress

- Phase 1 implementation has not started yet.

## Remaining

Follow `docs/phases/PHASE_1_FOUNDATION.md` in small verified slices.

## Architecture invariants

- Registry is control plane; Bridge is execution plane.
- Personal Engineering Agent owns reasoning/planning/capability selection.
- Bridge owns deterministic local execution/resource access.
- Deterministic routing precedes LLM reasoning.
- Publishing does not grant execution permission.
- Contributions evolve without normal core-runtime changes.
- Model/provider and coding-agent implementations are replaceable.
- Namespace, owner and visibility are separate concepts.
- Business approval does not replace technical/policy authorization.
- Local-first execution depends on declared dependencies and available authorization.
- Secret values remain in the execution environment.
- n8n is optional integration infrastructure.

## Verification

No Phase 1 implementation exists yet; implementation verification is not applicable.

## Known issues

None recorded for the foundation implementation yet.

## Next recommended action

Create the Phase 1 repository skeleton and shared contract package, starting with contract tests before implementation.
