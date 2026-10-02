# Handoff

Date: 2026-10-02 (Asia/Taipei). Branch: `main`. This is an incremental
checkpoint for the owner's Agent/Knowledge/Workflow program, not completion of
all remaining Phase 7 and Orchestrator work. No push, source Vault edit, Excel
write, mail action or Marketplace publication occurred.

## Goal and decisions

The owner wants the multi-backend Harness, executable Workflows, Knowledge,
default Marketplace assets and user-level Agent validation completed. The
first live target is Workflow 11's read-only preview. The owner will update
the configured GitHub Project permission; the current token authenticates to
`/user` but Project V2 returned `FORBIDDEN`. Knowledge begins with a separate
small local test Vault; only a later owner-selected subset of the supplied
`RS_Knowledge` tree may be used for model queries. Workflow 7 replaces retired
Jira with the same GitHub Project, starting with a read-only preview.

## Completed in this checkpoint

- Commit `89efa76` makes `aep-host ask` return nonzero for failed, unavailable,
  unresolved or unrecorded Workflow/capability outcomes. The previous Workflow
  11 run reported `github_auth` but returned process exit code zero; regression
  coverage now checks the failure status and JSON evidence.
- Commit `ed1a05e` adds optional numeric `WorkflowManifest.run_alias`,
  `/run 11` and `/run workflow 11` in Agent Web, and refusal of missing or
  ambiguous aliases. Only the shipped Workflow 11 read-only preview declares
  `11`; the exact resolved identity still goes through Agent admission and
  Bridge policy. Installed preview assets and package will need updating
  before the owner sees this command on the existing Agent Web process.
- `docs/WORKFLOW_7_SOURCE_CONTRACT.md` records the pinned source job's input,
  preview, Excel invariants and parity gate. Existing `GitHubProjectClient`
  lacks source-equivalent creation-time and reporter fields; mapping must be
  explicit before claiming parity.
- Typed `WorkflowManifest.parameters` now distinguishes static declarations
  from runtime fields. Agent Web renders labeled runtime controls and validates
  the exact installed Workflow's arguments before execution; older manifests
  retain JSON input. Workflow 11's shipped preview, apply and mail manifests
  declare week, date-window and issue-cap fields. Static persistence, dynamic
  option providers and Telegram controls are not yet implemented. See
  `docs/CONTRACTS.md` and `docs/DECISIONS.md`.
- A synthetic Knowledge Vault, exact matching manifest and isolated Host
  configuration were staged under `.scratch/knowledge-validation/`. They are
  ignored local test artifacts, not the enterprise Vault. Catalog registration
  and static lint passed (one Raw file, two wiki files, clean lint). A
  temporary loopback Agent Web returned HTTP 200 with the exact bound Knowledge
  identity. Four focused grounded-answer/policy tests passed with a scripted
  model. See `docs/KNOWLEDGE_VALIDATION_2026-10-02.md`.

## Verification

- Full repository selection after code changes: **1,562 passed, 4 skipped,
  2 deselected**. The two deselections are the existing machine-specific
  Chromium WebSocket and Excel COM tests; each failed in an initial unfiltered
  run on this machine. Command:
  `python -m pytest tests --ignore=tests/test_browser.py -q -p no:cacheprovider --basetemp .scratch/pytest-20261002-final --deselect tests/test_agent_web.py::test_capability_workspace_is_interactive_in_a_real_browser --deselect tests/test_excel_com_writer.py::test_a_machine_with_the_bridge_and_no_excel_says_which`.
- `python -m ruff check src tests` passed. `python -m mypy src tests` passed
  with no issues in 288 source files. Offline `python -m build --no-isolation
  --sdist --wheel --outdir .scratch/dist-20261002-next` produced both artifacts.
- Knowledge-focused tests: 4 passed. No live Gateway answer was run in this
  Codex process because `LITELLM_MASTER_KEY` is absent from its environment.
- After the runtime-field change, focused contract/Web tests passed (91 passed,
  1 machine-specific browser test deselected). The full repository selection
  passed **1,564 tests, 4 skipped, 2 deselected** in a clean rerun. A first
  full attempt had one intermittent Windows workspace-write refusal in an
  unrelated Knowledge Marketplace test; that case passed alone and in the
  clean full rerun. `ruff check src tests`, `mypy src tests`, Node syntax check
  of the inline Agent Web script and offline sdist/wheel build passed.

## Open work and known limits

1. Recheck Project access after the owner updates `AEP_GITHUB_TOKEN`
   permissions, then rerun `weekly.preview` on the installed Host for the
   chosen week. Inspect the nested plan and workbook-read evidence. Do not run
   apply/mail against a real workbook or recipient list during this preview.
   A 2026-10-02 read-only recheck outside the network-restricted command
   sandbox still returned `github_auth`, so Project V2 access was not available
   yet. The sandboxed CLI reported `transient_failure` and exited nonzero.
2. Use `.scratch/knowledge-validation/host.json` for a live Gateway question
   once the launching Agent has the existing key in its environment. The
   isolated Host has no Shared Platform binding and is only for Knowledge
   validation. `/wiki-convert`, `/wiki-ingest` and `/wiki-lint` are not yet
   installed executable Workflows. Later plan a provenance-preserving
   conversion of the supplied OneDrive tree: its root has `drop/raw/wiki` but
   lacks the required root `index.md` and `log.md`; no nested directory has
   all four. Many entries are OneDrive cloud reparse points.
3. Build Workflow 7's GitHub-to-source field mapping and read-only preview.
   The same Project credential gate applies. Source tests are in the pinned
   `rs_workflow_system` checkout and must remain read-only. Later Excel parity
   uses a workbook copy and explicit write approval.
4. Complete generic static/runtime parameter contracts and generated Web and
   Telegram controls, ordinary Agent/task state integration, backend transfer
   authorization, governed native adapters, default Marketplace packages,
   SOP/Knowledge/Skill end-to-end evidence, and optional benchmark-gated JEV.

The active checklist is `docs/TASKS.md`; observed readiness is in
`docs/VALIDATION_GAPS_2026-10-02.md`. Prior Gateway policy still applies:
UNCLASSIFIED material uses only the exact approved internal Gateway, and
native Codex/Claude tasks require complete explicitly PUBLIC context.
Publishing or installing an asset grants no execution permission.
