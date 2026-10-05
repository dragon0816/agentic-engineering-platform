# Coding on the Bridge

Owner request 2026-10-06: start coding-feature development and check that the
harness process can meet coding needs, with the tools installed on the Bridge.
E2E-03 (`docs/phases/E2E_03_CODING_HARNESS.md`) proved the bounded loop in CI
with a scripted author and an in-process JSON validator; nothing registers it
on a live host, no real author exists and no generated code is executed.

## Owner decisions (2026-10-06)

1. Author: the internal Gateway model first; native Claude Code later, for
   PUBLIC-only tasks, under the existing data rule (`docs/DECISIONS.md`).
2. Validation: pytest only, run as declared commands. No general shell.
3. First repository: a new practice repository, not a real project.
4. Isolation: restricted Windows execution, practice repository only.

## Isolation of generated code

pytest imports the code the model wrote, so this phase lifts the E2E-03
deferral of generated-code execution for this one path, behind these limits:

| Limit | How |
|---|---|
| No write outside the run | the test process runs at low integrity; only the run folder (worktree and temp) is labelled low |
| No network | an outbound firewall block on a dedicated runner interpreter; the host refuses to run when the rule is missing |
| No second process | a Job object allows one active process, so the code cannot start an unblocked interpreter |
| Bounded resources | the Job object caps memory and kills the process tree at the timeout |
| No credentials | the environment is rebuilt from an allowlist; no `AEP_*`, tokens or keys |
| Golden tests stay golden | the author may write only the declared file; `tests/` and `test_*.py` are never writable |
| Nothing leaves the worktree | the change lives in a detached git worktree; never committed, pushed or merged |

Residual risk accepted by the owner: the process can still read files the
Windows account can read.

## Slices

| Id | Slice | Verification |
|---|---|---|
| C1 | This plan and the decision record | docs |
| C2 | Restricted runner: low integrity, Job object, scrubbed environment, timeout, JUnit result | Windows tests: env, timeout, child refused, outside write refused |
| C3 | Git worktree workspace and the two pytest commands (`pytest-new`, `pytest-suite`) | tests against a temporary git repository |
| C4 | Gateway change author (plan, change, repair as JSON over the model client) | scripted model tests |
| C5 | `coding/change@1.0.0` capability, `coding` host binding, `coding` Skill, doctor checks | host wiring tests |
| C6 | Install: runner interpreter + pytest, firewall rule (owner, elevated), practice repository, live config and grant | live doctor |
| C7 | Live run on the practice repository through Agent Web and Telegram | plan -> change -> failing test -> repair -> suite passes, worktree left for review |
| C8 | Later: native Claude Code author for PUBLIC tasks | separate decision |
