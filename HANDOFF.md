# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/web-workflow-launch`
Base: `origin/main` at merge commit `49dc7da` (PR #149)
PR: pending creation

## Goal

Complete Productization 1 slice 4: let a member launch any exact installed
Workflow from Personal Agent Web through the normal local Agent, Gateway,
Workflow engine and Bridge policy, with result and trace evidence.

## Completed

- Added `WorkflowLaunchRequest`, a closed exact-identity, JSON-arguments and
  idempotency contract that cannot claim actor, Bridge, route or authorization.
- Added `LocalWorkflowRequest` and `LocalAgent.execute_workflow` for exact local
  Workflow execution after normal device/member admission. It bypasses model
  routing but not Workflow preflight or Bridge capability policy.
- Personal Agent Web now projects each installed Workflow's input/output
  contract names and provides a generic exact-version selector plus JSON object
  editor. There is no workflow-specific form or command in the page.
- Added authenticated loopback `POST /api/workflows/run`. The host supplies its
  trusted actor/Bridge identity and a fresh trace; the response uses the
  existing `LocalAgentOutcome` and readable rendering.
- The page shows request, trace and run identifiers and refreshes durable recent
  runs after completion. Reusing the same idempotency key joins the same run.
- Added real-socket tests for success, idempotency, durable run recording,
  bearer protection, identity-claim rejection and secret-shaped argument
  rejection.
- Updated Architecture, Contracts, Roadmap, Tasks and the active Productization
  specification after implementation verification.

## In Progress

- Documentation and handoff are ready to commit. The branch needs push, PR
  creation and exact-head Platform verification.

## Remaining

1. Push, open the PR and wait for exact-head CI; merge automatically when green
   under the owner's 2026-10-01 instruction.
2. Productization 1 slice 5: browse exact installed Knowledge versions and ask
   one grounded question with citations in Personal Agent Web.
3. Productization 1 slice 6: replace the in-memory shared catalog references
   with the smallest persistent implementation that preserves current APIs.
4. After all Personal Agent Web slices merge, use the repository roadmap to
   define and begin the second and third productization stages.

## Architecture decisions made

- **ADAPT** the existing `Gateway.execute_workflow`, `WorkflowEngine` and
  `LocalAgent` admission/run-recording path. No source repository has a
  competing generic Web launch path to migrate.
- Exact user selection is deterministic and never passes through model intent
  routing. It adds no authority: admission and every Bridge policy check remain.
- Current Workflow manifests name an `input_contract` but carry no JSON Schema.
  The generic UI therefore labels the contract and accepts one JSON object
  instead of guessing fields.
- The browser creates the idempotency key; the server supplies actor, Bridge and
  trace identity. Neither the page nor request may claim authorization.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu run was performed.
Browser automation was not run per owner direction; the HTTP boundary was
exercised over real loopback sockets.

```text
Focused Web/Agent/contracts suite:
python -m pytest tests/test_agent_web.py tests/test_local_agent.py
  tests/test_contracts.py -q --basetemp=<repo>/.scratch/...
72 passed

Full suite (browser test excluded):
python -m pytest --ignore=tests/test_browser.py -q --basetemp=<repo>/.scratch/...
1387 passed, 4 skipped in 51.29s

python -m ruff check .
All checks passed!

python -m ruff format --check .
302 files already formatted

python -m mypy src tests
Success: no issues found in 236 source files

python -m pip check
No broken requirements found.

python -m build --outdir <repo>/.scratch/dist-workflow-launch
Successfully built sdist and wheel.

git diff --check
PASS
```

The four skips are existing Windows environment conditions: symlink/link
privileges, IPv6 loopback and directory links.

## Known issues

- Symbolic input-contract names are not field schemas; users enter JSON until a
  later governed schema contract is approved.
- The launch request waits for the existing configured Workflow wait period.
  The page shows a running state but does not stream step events yet.
- Installed and selected still do not imply executable; missing Bridge policy
  grants produce the existing Workflow failure.
- The shared catalog is still in memory until Productization 1 slice 6.

## Next Recommended Action

After this PR merges, implement grounded Knowledge asking as a separate exact
installed-Knowledge action. Reuse the existing knowledge-query capability and
model binding, return its citations unchanged, and do not put retrieval or
answer-generation logic in the Web layer.
