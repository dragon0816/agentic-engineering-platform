# Handoff — Phase 6 evaluation, slice 5 (trace capture with redaction)

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-6/trace-capture`, based on `main` after PR #44 merged.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Goal

The Roadmap asks for one record of a request's journey: route, plan, tool and
workflow calls, approvals, duration, model usage and final status, with
secrets redacted. Requirements: `docs/phases/PHASE_6_EVALUATION.md` (slice 5);
contracts: `docs/CONTRACTS.md` ("Trace capture with redaction"); decisions:
`docs/PHASE_6_MIGRATION.md` ("Slice 5 decisions").

## Owner decisions in force

Listed with their dates in `docs/TASKS.md`. The one that shapes this phase:
**Codex and Claude Code are out of scope for Phase 6 entirely** (2026-09-22).

## Completed

- `src/common/trace.py`: `redact`, `carries_credential`, `TraceEvent` and
  `ExecutionTrace`, with `ExecutionTrace.build(trace, observed, dispatches,
  approved=)` reading the routing outcome and the Bridge's events. The record
  is redacted by construction and its validator refuses one that still
  carries credential material, is out of order, or does not open with the
  route and close with the outcome. Bridge events are read through a
  `DispatchRecord` protocol so `common` does not import `workflow`.
- `common.evaluation.labelled` (was `_labelled`) is shared, so redaction and
  the `no_credential_in_evidence` grader use one definition of a credential;
  a label that names a secret is inherited by everything beneath it.
- `common.assets.SECRET_PATTERN` spans whole secrets (quoted values, private
  key blocks to their `END` line) and refuses to match `REDACTED`, which is
  defined beside it with `SECRET_FIELD`. The model adapters and the registry
  redact and reject with the same pattern, so they gained the same reach.
- PR #45 review (9 findings) applied. Three were real leaks with one root
  cause: the pattern located the start of a secret and matched its own
  marker, so a private key kept its body, a quoted password kept its tail,
  and a mapping under `password` was never scanned. The validator now also
  holds a stored trace to internal consistency (dispatch events match
  `dispatched`; `ran`, `approved`, `unapproved` are subsets of it).
- `tests/evaluation_runner.py`: `GatewayRunner.trace(case, observed)` and
  `RepositoryRunner.observe(case)`, which returns the observation and its
  trace and files every trace in `RepositoryRunner.traces`.
- `tests/test_trace.py`, 16 tests: every repository trace joins its case's
  request, is ordered and scans clean; the scenario trace shows both
  dispatches in Bridge order under approval; a refused request traces as
  `unresolved` with its code; the agent trace records model usage; a bearer
  token in a failure arrives redacted and counted; a private key is removed
  whole; a quoted credential with a space is removed whole; a JSON-shaped
  credential is redacted; a secret under a credential key goes whatever its
  shape; redaction is idempotent; the marker is not itself a credential; a
  trace cannot be built around credential material; a stored trace cannot
  claim more than its dispatches; a foreign event cannot join; out-of-order
  or out-of-shape events are refused.
- Slice 5 requirements and the "Phase 6 exit criteria" section in
  `docs/phases/PHASE_6_EVALUATION.md`; PR #43 flipped to `done` and PR #44
  recorded in `docs/TASKS.md`.

## In Progress

- PR #45 open for review. Nothing else uncommitted.

## Remaining

Close Phase 6 against its exit criteria once PR #45 merges: mark the phase met
in `docs/ROADMAP.md` (dated, with a paragraph like Phase 5's), update the
status lines of `docs/ARCHITECTURE.md` and the README, flip the slice 5 row
and add a closure row in `docs/TASKS.md`, and decide with the owner what the
active phase pointer in `CLAUDE.md` and `AGENTS.md` should name, since no
Phase 7 specification exists yet and writing one needs owner decisions about
which source components are deprecated and what parity means.

## Architecture decisions made

- The trace is built from evidence the platform already records, never from
  a new logging path, so it cannot disagree with what the graders read.
- Redaction and the credential grader share one rule (`labelled` over
  `SECRET_PATTERN`), and the pattern is the repository's single definition
  of a credential: it spans the whole secret and refuses its own marker, so
  there is no special case for the marker anywhere. A string is replaced
  whole when it still scans as a credential beside its field name.
- `approved` is recorded beside `unapproved`: the Roadmap asks for approvals,
  and "who allowed that" needs the allowed dispatches too.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 677 passed, 3 skipped (link privileges)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

No model, gateway, network, real vault, job or n8n instance was invoked.

## Known issues / limitations

- Nothing persists a trace yet. `ExecutionTrace` is safe to store and
  round-trips through JSON, but no store, file or journal entry writes one;
  the test runners keep them in memory for the suite. A host that wants
  durable traces writes them beside its checkpoints.
- `SECRET_PATTERN` is the repository's one definition of a credential and is
  deliberately narrow (password, API key, access token, secret value, bearer
  token, private key block). A provider-specific token shape it does not
  name is not redacted; extending the pattern extends redaction, the grader
  and the registry's rejection together.
- The trace does not carry the plan beyond `declared_steps` and the route's
  target. The workflow manifest that names the steps is the plan, and the
  target identity is enough to find it.
- The Bridge's events carry the request's own `TraceIdentifiers` because the
  workflow engine does not open child spans. If it ever does, the join rule
  in `ExecutionTrace.build` (strict equality) needs to compare `trace_id` and
  `request_id` instead.

## Next Recommended Action

Merge PR #45 on green CI and flip its row in `docs/TASKS.md` to `done`. Then
close Phase 6 as described under "Remaining".
