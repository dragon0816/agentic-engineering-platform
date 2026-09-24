# Handoff — E2E-03 bounded Coding Harness

Updated: 2026-09-25 (Asia/Taipei).
Branch: `codex/e2e-03-coding-harness`.
Base: merged E2E-02 on `main` (`5428774`).
Implementation commit: `273cde3`.
Pull request: #99, open against `main`.

Progress across all phases remains in `docs/TASKS.md`. This file records the
current stopping point and the evidence needed to continue without chat history.

## Completed

- Merged E2E-02 to `main` after its exact head and 4/4 previous CI jobs were
  verified.
- Added provider-neutral Coding Harness contracts for pinned workspace state,
  bounded plan, candidate and actual patches, validation cases, repair/command
  budgets, exact command outcomes, ordered events, artifact digest, Skill
  versions and trace.
- Added `BoundedWorkspace`: every read/write is allowlisted and resolved beneath
  the explicit root; traversal and resolved escapes are refused. The initial
  content revision is verified before mutation.
- Added `DeclaredCommands` and `CodingHarness`: no shell/subprocess path exists;
  only injected installed validators may decide completion. A structured
  failure feeds a bounded repair; budget exhaustion is a typed failure.
- Added `coding-harness.run` as a Bridge-installed `write` capability with
  required permission, policy ref and execution approval.
- Added the deterministic JSON transformation proof and committed new/regression
  fixtures. The wrong first candidate is rejected; one repair passes both.
- Added negative tests for traversal/credential content, undeclared validation,
  repair exhaustion and an old regression failing after the new case passes.
- Kept commit/push/publication outside the Harness contract.
- Narrowed GitHub Actions to the owner-requested Windows/Python 3.12 target. The
  package compatibility declaration remains Python 3.11+.
- Updated Architecture, Contracts, Roadmap, Tasks, README and the E2E-03 gate
  record only after the implementation passed locally.

## In progress

- Obtain the single Windows/Python 3.12 CI result for PR #99.

## Remaining

- Merge E2E-03 only after its exact PR head passes CI.
- Start E2E-05 only after that merge. E2E-05 must demonstrate question with Raw
  citations -> feedback -> standardized improvement request -> Knowledge
  candidate -> new plus existing evaluation -> separate domain approval ->
  versioned republish -> corrected cited answer, while Raw remains byte-identical.
- E2E-04 and E2E-01 remain blocked by the approved order.

## Architecture decisions made

- **REUSE** resident `LocalAgent`, `Gateway`, `BridgeExecutor`, installed Skills
  and `LocalPolicy`; there is no second agent or execution path.
- **ADD** the Harness at the Personal Engineering execution boundary and expose
  it through one normally authorized Bridge capability.
- **ADAPT** the source benchmark invariant that every grader must reject a known
  wrong output.
- **DO NOT MIGRATE** the source live-model/arbitrary-subprocess runner. It is not
  a sandbox and conflicts with inert CI and the declared-command boundary.
- Use a typed JSON transformation program for the first safe vertical. General
  generated-code execution requires a later isolation adapter behind the same
  command contract.
- A plan grants no access. Runtime path/command allowlists and Bridge policy are
  independently authoritative.
- Validation creates a candidate only. Git writes, publishing, business review
  and technical/execution authorization remain separate transitions.

## Exact verification commands and results

```text
.venv\Scripts\python.exe -m pytest tests\test_product_e2e_03.py -q -p no:cacheprovider --basetemp .scratch\pytest-e2e03-final
4 passed in 0.26s

.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .scratch\pytest-e2e03-full-final
1291 passed, 4 skipped in 67.95s

.venv\Scripts\python.exe -m ruff check .
All checks passed

.venv\Scripts\python.exe -m ruff format --check .
231 files already formatted

.venv\Scripts\python.exe -m mypy
Success: no issues found in 190 source files

.venv\Scripts\python.exe -m build --no-isolation --outdir .scratch\build-e2e03
Successfully built sdist and wheel

.venv\Scripts\python.exe -m pip check
No broken requirements found

git diff --check
passed
```

The four skips are existing host-dependent cases: two Windows link privilege
checks, IPv6 loopback availability and a directory-link privilege check. No
Ubuntu or Python 3.11 validation was run, per owner instruction.

## Known issues

- The author and routing model in the gate are scripted, so CI is deterministic
  and inert. A real model/provider is not acceptance evidence for E2E-03.
- The first transformation artifact is declarative JSON. Arbitrary Python or
  shell execution is deliberately absent until an isolation boundary exists.
- The Harness mutates its allowed temporary workspace during validation but
  never commits, pushes or publishes it.
- `.claude/` is untracked user-owned state and must not be committed, modified
  or removed.

## Next recommended action

Wait for PR #99's Windows/Python 3.12 job and merge only its verified head. Then
branch from updated `main` and implement E2E-05 from
`docs/PRODUCT_ACCEPTANCE_TESTS.md` without returning to Phase 7 backlog work.
