# Development Handoff

## Current phase and branch

Phase 2 — Agent and capability layer, first reviewable implementation slice.
Branch: `phase-2/implementation`, based on Phase 1 commit `006e5b6`.
Phase 1 PR #4 remains open and unmerged. Phase 2 is a stacked PR against
`phase-1/implementation`; retarget after the Phase 1 merge is handled by a human.
Do not merge either PR automatically.

## Goal

Implement the Roadmap's provider-neutral routing/capability layer while preserving
characterized source behavior. Scope and acceptance are recorded in
`docs/phases/PHASE_2_AGENT_CAPABILITIES.md`; source decisions are in
`docs/PHASE_2_MIGRATION.md`.

## Completed

- Reconciled repository/PR state; Phase 1 baseline: 52 passing tests.
- Pinned `telegram-local-agent` commit `4b40a215909e4fdd4b65519d70669a84e9abd43d`;
  inspected routing, Skill/Tool registries, MCP and file manager. Source unchanged.
- Committed a checksum-verified, test-only routing excerpt and 13 source
  characterization tests before adding the adapted runtime.
- Added opaque attachments to the existing channel-neutral RequestContext.
- Added governed Skill procedures, exact version/namespace alias installation,
  command mappings, ordered keyword routes and direct Skill/default selection.
- Deterministic routing precedes one optional provider-neutral model selection.
  Model targets must be installed; invalid/unknown routes return typed needs-input.
  Workflow selection remains intent; no workflow engine is implemented.
- Explicit local capability bindings with typed async handlers/input/output models.
- Default-deny trusted local policy: exact actor/asset match, required permissions,
  technical policy references and separate execution approval reference.
- Bridge dispatch checks authorization, local/central dependencies, inputs, outputs
  and cooperative timeouts. Secret-dependent calls fail unavailable without a resolver.
- MCP discovery/call adapter uses an injected client and reviewed host bindings;
  discovery never grants execution authority. MCP calls use the same Bridge checks.
- Trace events contain identity/status/error codes, never payloads or raw exceptions.
- Added regression/evaluation cases, end-to-end inert dispatch tests and documentation.
- Expanded CI to Phase 2 branches; all six Python packages ship typing markers;
  source distributions include regression fixtures and Skill sample data.

## In Progress

Final branch publication, GitHub CI observation and stacked PR creation.
No production service, transport, model or capability has been invoked.

## Remaining

- Review this slice and resolve its Phase 1 PR dependency before merging.
- Concrete MCP transport/session/auth adapters and model providers remain external;
  only injected fakes are exercised. No live integration/parity is claimed.
- Upload/persistence/file resolution, production source tools, full workflow engine,
  channel/UI servers, secret resolution, production identity/RBAC and specialist
  agents remain separate work. No source capability is deprecated by this slice.
- Characterize the specific production source tool selected for the next adapter;
  do not treat command routing parity as end-to-end production parity.

## Architecture decisions made

- ADAPT source command precedence, aliases and raw args into typed route intent;
  WRAP MCP list/call behind a client protocol; retain source production implementations.
- Unknown explicit commands fail closed. No implicit function-name execution, fuzzy
  cross-scope selection, auto-import, guessed path/url/query arguments or silent kwargs
  dropping. These intentional differences are documented in the migration record.
- Skill manifests are procedures and bindings; executable handlers are installed
  explicitly in the Personal Engineering/Bridge plane. Team Registry stays metadata-only.
- Namespace, owner, visibility, publication, review and runtime permission stay separate.
  Neither technical approval metadata nor discovery authorizes execution.
- LocalPolicy grants are trusted host configuration, never request/model/asset data.
  Host code must authenticate the actor. This is not a production authentication server
  or a security boundary against hostile in-process Python code.
- Regex rules are trusted reviewed installation configuration, not untrusted user/model
  input. No regex sandbox is provided. Model prompts include installed Skill guidance,
  but no attachment names/refs/content automatically.
- Model routing makes at most one call; the synchronous provider owns its I/O timeout.
  Async execution timeouts require cooperative cancellation and cannot undo side effects.
- No automatic retry of handlers. Availability is a host-provided snapshot, not a probe.

## Exact verification commands and results

Run from repository root with the existing .venv (Windows, Python 3.12.14).

```powershell
.venv/Scripts/python.exe -m pytest tests/test_source_routing.py -q
# PASS: 13 source characterization tests
.venv/Scripts/python.exe -m pytest -q
# PASS: 112 tests, including all 52 Phase 1 tests
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 29 source/test files
.venv/Scripts/python.exe -m pip check
# PASS: no broken requirements
.venv/Scripts/python.exe -m build
# PASS: source distribution and wheel
.scratch/wheel-env/Scripts/python.exe -m pip install --no-deps --force-reinstall dist/agentic_engineering_platform-0.1.0-py3-none-any.whl
# PASS: non-editable wheel installed
.scratch/wheel-env/Scripts/python.exe -I -c "import agent.routing, agent.skills, capabilities.runtime, capabilities.mcp, workflow.dispatch; print(agent.routing.__file__)"
# PASS: imports resolve from wheel-env/Lib/site-packages
git diff --check
# PASS
```

The new routing and dispatch tests were first run before implementation and failed
on missing modules as expected. Subsequent lint/type findings were fixed; no check
failure was waived. GitHub CI status will be recorded before PR delivery.
The first Phase 2 CI run exposed a Windows locale-dependent JSON read in the
source-characterization harness (three Chinese cases failed). The read now explicitly
uses UTF-8; the existing multilingual cases are the regression coverage.

## Known issues / limitations

- Cooperative deadlines are not hard process isolation; do not install blocking or
  cancellation-suppressing production handlers without a stronger execution boundary.
- Runtime approval references are preconfigured policy evidence, not signed or
  per-request cryptographic approvals. Production identity/approval infrastructure is absent.
- No provider/MCP transport is installed by default. Adapter clients must enforce their
  protocol, local-only model requirements and transport authentication themselves.
- No full source migration, production side effect, source retirement or live-device
  verification is claimed. In-memory Registry remains unauthenticated.

## Next Recommended Action

Review the Phase 2 stacked PR against the phase specification and source-characterization
record. After human review and resolution of PR #4, select one real source capability
for a separate characterization-backed adapter; preserve the shared Bridge policy path.
