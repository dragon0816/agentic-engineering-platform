# Handoff — E2E-02 SOP to deterministic Workflow

Updated: 2026-09-25 (Asia/Taipei).
Branch: `codex/e2e-02-sop-workflow`.
Base: `main` at `d2bee6291345bb91b04bc9b772e3097e269a2e1d` (PR #97 merge).
Pull request: #98, open against `main`.
Implementation commit: `e4f15446b8fb49eb459a3c6aaad3265254aaed89`.
Documentation commit: `831f03d`.
Verified PR head: `f129aa4`.

Progress across all phases remains in `docs/TASKS.md`. This file records the
current stopping point and the evidence needed to continue without chat history.

## Completed

- Implemented product gate E2E-02 over the existing resident `LocalAgent`,
  `Gateway`, `WorkflowEngine` and `BridgeExecutor`; no second agent/runtime path
  was introduced.
- Extended `DraftWorkflowRequest` with unique exact capability identities and
  made every `WorkflowDraft` echo the request that reached the drafter.
- Made deterministic review reject a structurally valid draft that silently
  omits a capability required by the SOP acceptance criteria.
- Added typed fixture, validation evidence and acceptance outcome contracts.
  Secret values are rejected; a pass must identify its run, match expected and
  observed output, be deterministic and belong to the same trace.
- Added `PersonalWorkflowAuthor`: the user request enters through resident Agent
  admission and normal Gateway routing; a candidate runs only in a throwaway
  Workflow inventory through a Gateway, Workflow engine and the host's existing
  Bridge policy. Validation does not install or publish the draft.
- Added a pure human business-approval transition bound to the exact validated
  manifest digest. It leaves technical policy, installation and execution
  authorization separate.
- Added the inert normalize-then-count fixture and E2E tests for the green path,
  semantic omission, ambiguous/secret acceptance input, wrong output,
  publication without permission and identical no-model replay.
- Updated Architecture, Contracts, Roadmap, Tasks, README and the E2E-02 product
  gate record only after the implementation had a reproducible local green path.
- Updated `CLAUDE.md` so a fresh Claude Code session must read Product Vision,
  Product Acceptance Tests and the active product-gate specification instead of
  defaulting to the independent Phase 7 backlog.
- Opened PR #98 and attached it to this task. GitHub Actions run `36023283160`
  passed 4/4 on head `f129aa4`: Ubuntu and Windows with Python 3.11 and 3.12.

## In progress

- PR #98 owner review and merge decision.

## Remaining

- Merge only when the owner explicitly asks. Do not begin E2E-03 before PR #98
  has a reproducible passing path and merges.
- Phase 7 production-like work remains independent: company-host workflow 11
  parity, workflow 10 remaining slices, workflow 13 and Knowledge-copy parity.

## Architecture decisions made

- **REUSE** the current resident Agent, Gateway, Workflow engine, Bridge policy
  and `WorkflowManifest`; E2E-02 is a bounded application service around them.
- Required capabilities are explicit executable acceptance criteria. The model
  may propose structure but cannot silently remove a required outcome.
- Candidate validation uses an ephemeral Workflow inventory with the same Bridge
  and grants as normal execution. The host inventory and Registry stay unchanged.
- Expected output is supplied independently and graded outside the model.
- Business approval may publish the validated manifest; technical policy,
  installation, distribution and execution grants remain separate.
- General workspace editing, code generation and repair remain E2E-03 scope.

## Guardrails for the next worker

- The current task is PR #98 review and, only after explicit owner approval,
  merge. Do not add another feature to this PR.
- Do not start E2E-03 on this branch or before PR #98 merges. The mandatory
  order remains E2E-02 → E2E-03 → E2E-05 → E2E-04 → E2E-01.
- Do not return to a Phase 7 backlog item merely because Phase 7 is also active;
  the product-gate work named in this handoff has priority.
- Do not replace the current Agent/Gateway/Workflow/Bridge path with a new agent
  framework or redesign the approved architecture.
- Do not treat a model-generated manifest as completion evidence. The external
  fixture comparison is the validator.
- Do not combine draft validation, business approval, technical policy,
  publication, installation or execution authorization. They are separate
  transitions and the tests deliberately prove that publication grants no
  permission.
- Do not require a live model or company workstation for E2E-02. This gate is
  intentionally inert; live endpoint and physical-resource evidence belongs to
  later gates.
- Preserve the untracked user-owned `.claude/` directory.

The implementation evidence map is:

- acceptance source: `docs/PRODUCT_ACCEPTANCE_TESTS.md`, E2E-02;
- approved boundary: `docs/ARCHITECTURE.md`, “E2E-02 bounded Workflow authoring
  and validation”;
- gate record: `docs/phases/E2E_02_SOP_WORKFLOW.md`;
- contracts: `src/capabilities/workflow_author/contracts.py`;
- semantic review: `src/capabilities/workflow_author/review.py`;
- use-case orchestration: `src/host_runtime/workflow_author.py`;
- committed input: `tests/fixtures/e2e_02/sop-workflow.json`; and
- executable proof and negative cases: `tests/test_product_e2e_02.py`.

## Exact verification commands and results

```text
.venv\Scripts\python.exe -m pytest tests\test_workflow_author.py tests\test_product_e2e_02.py -q -p no:cacheprovider --basetemp=.scratch\pytest-e2e02-contract-3
30 passed in 0.29s

.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --ignore=tests\test_browser.py --basetemp=.scratch\pytest-e2e02-nobrowser
1266 passed, 4 skipped in 32.31s

.venv\Scripts\python.exe -m pytest tests\test_browser.py -q -p no:cacheprovider --basetemp=.scratch\pytest-e2e02-browser
21 passed in 285.53s (run outside the command sandbox because installed Chromium closes its debugging socket inside it)

Combined unique suite result: 1287 passed, 4 skipped

GitHub Actions run 36023283160 on f129aa4
4/4 passed: Ubuntu/Windows x Python 3.11/3.12

.venv\Scripts\python.exe -m ruff check .
All checks passed

.venv\Scripts\python.exe -m ruff format --check .
222 files already formatted

.venv\Scripts\python.exe -m mypy
Success: no issues found in 182 source files

.venv\Scripts\python.exe -m pip check
No broken requirements found

.venv\Scripts\python.exe -m build --no-isolation --outdir .scratch\build-e2e02
Successfully built agentic_engineering_platform-0.1.0.tar.gz and agentic_engineering_platform-0.1.0-py3-none-any.whl

.scratch\wheel-env\Scripts\python.exe -m pip install --no-deps --force-reinstall .scratch\build-e2e02\agentic_engineering_platform-0.1.0-py3-none-any.whl
.scratch\wheel-env\Scripts\python.exe -I -c "from capabilities.workflow_author.contracts import WorkflowAcceptanceRequest; from host_runtime.workflow_author import PersonalWorkflowAuthor; print(WorkflowAcceptanceRequest.__name__, PersonalWorkflowAuthor.__name__)"
WorkflowAcceptanceRequest PersonalWorkflowAuthor

git diff --check
passed
```

The first isolated build attempt could not download `setuptools>=75` because the
sandbox blocks package-index access. After installing the declared build
dependency with approved network access, the default `dist/` path was locked by
an existing artifact. Building to `.scratch/build-e2e02` succeeded; this is an
environment/path issue, not a source or package-content failure.

## Known issues

- The scripted model makes the E2E path deterministic and inert. A live model is
  intentionally not acceptance evidence for this gate.
- This slice is not a general Coding Harness and does not edit a workspace or
  repair generated code; those are E2E-03 concerns.
- `.claude/` is untracked user-owned state and must not be committed, modified or
  removed.

## Next recommended action

Review PR #98. Once the owner approves a merge, merge it. Start E2E-03 only
after that merge; do not expand this PR into the Coding Harness.
