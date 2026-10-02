# Handoff

Date: 2026-10-02 (Asia/Taipei). Branch: `main`. This is an incremental
checkpoint for the owner's Agent/Knowledge/Workflow program, not completion of
all remaining Phase 7 and Orchestrator work. This session did not push, edit
the source Vault, write an Excel workbook or publish to the Marketplace. A
user-run Agent apply previously wrote the report workbook; this session saved
one separate Outlook draft for `2026_40W` after the owner requested the fix.

## Goal and decisions

The owner wants the multi-backend Harness, executable Workflows, Knowledge,
default Marketplace assets and user-level Agent validation completed. The
first live target, Workflow 11's read-only preview, now executes on this Host
after the owner updated the token and the installed preview manifest was
refreshed. Source/workbook parity remains open. Knowledge begins with a separate
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
  preview, Excel invariants and parity gate. The Project client now requests
  creation time and author login, while the Jira/GitHub semantic differences
  remain explicit before any parity claim.
- Typed `WorkflowManifest.parameters` now distinguishes static declarations
  from runtime fields. Agent Web renders labeled runtime controls and validates
  the exact installed Workflow's arguments before execution; older manifests
  retain JSON input. Workflow 11's shipped preview, apply and mail manifests
  declare week, date-window and issue-cap fields. Static persistence, dynamic
  option providers and Telegram controls are not yet implemented. See
  `docs/CONTRACTS.md` and `docs/DECISIONS.md`.
- Workflow 7's first read-only GitHub Project adapter now has a shipped
  exact Workflow and `tickets.preview` Skill. It preserves the source managed
  column order, routes Task/Sub-task to Task, leaves Jira Resolution explicitly
  unavailable, names missing GitHub fields and refuses to treat truncated
  comments as complete. An offline installed-Agent/Bridge run passed, and a
  missing local grant prevented GitHub transport use. No Excel code is wired
  into this Workflow. See `docs/WORKFLOW_7_SOURCE_CONTRACT.md`.
- The owner saved a new Windows user `AEP_GITHUB_TOKEN`. Read-only GraphQL
  checks confirmed authentication, Project #1 access and Issue content access.
  The older process token still returned `FORBIDDEN`; it must not be mistaken
  for the new user value. The installed Workflow 11 preview manifest lacked
  `run_alias: 11` and typed parameters. Its exact old file was backed up under
  `.scratch/workflow11-refresh/backup/`, then only that local installed asset
  was replaced by the current shipped preview manifest. No repository runtime
  code, Host grants, report workbook or mail action was changed at that point.
- A synthetic Knowledge Vault, exact matching manifest and isolated Host
  configuration were staged under `.scratch/knowledge-validation/`. They are
  ignored local test artifacts, not the enterprise Vault. Catalog registration
  and static lint passed (one Raw file, two wiki files, clean lint). A
  temporary loopback Agent Web returned HTTP 200 with the exact bound Knowledge
  identity. Four focused grounded-answer/policy tests passed with a scripted
  model. See `docs/KNOWLEDGE_VALIDATION_2026-10-02.md`.
- The owner requested the Outlook draft permission fix. The installed Host's
  `grants.json` now has one `leo.chi` grant for
  `weekly-report/mail@1.0.0` / `outlook.draft` /
  `weekly-report-mail-policy`, with an approval reference tied to this request.
  The original eight grants are preserved, and the prior file is backed up in
  `.scratch/workflow11-mail-grant-20261002/`.
- The installed Host runtime was stale: it rejected `run_alias` and
  `parameters` in the already-installed Workflow 11 preview manifest. The
  current repository wheel was built locally and installed into the existing
  preview virtual environment. `host.json`, the workspace and run history
  were retained. The old package was archived in the same `.scratch` folder.
  One Agent Web instance was restarted on port 53582 with `--open`; older
  53580/53581 processes were stopped.

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
- After the Workflow 7 preview slice, 39 focused Project/Workflow tests passed.
  The full repository selection passed **1,567 tests, 4 skipped, 2 deselected**
  in a clean rerun; the two deselections remain the machine-specific browser
  WebSocket and Excel COM cases. `ruff check src tests`, `mypy src tests` and
  `git diff --check` passed. An initial full attempt had one Windows loopback
  connection abort in the existing Host-header security test; that unchanged
  test passed alone and in the clean full rerun. No live Project preview was
  possible because direct Project V2 read still returned `github_auth`. An
  offline sdist/wheel build passed, and the wheel contains all four new
  `capabilities.team_tickets` modules.
- After refreshing the installed Workflow 11 preview manifest, the focused
  numeric-alias Agent Web regression passed (1 passed). A live Web-command run
  with explicit `2026_39W` and the new user token returned `succeeded`. Both
  exact bare commands `/run 11` and `/run workflow 11` then returned
  `succeeded` with no Agent refusal or Workflow failure. These runs used the
  same four-step read-only preview asset; report parity was not inspected.
- A later user-run Agent applied Workflow 11 successfully in five steps. Its
  separate mail Workflow failed after two steps with `permission_denied` at
  `weekly-report/mail@1.0.0`, before Outlook was invoked. The installed AEP
  virtual environment's doctor reports Excel and Outlook COM available; the
  source checkout's virtual environment lacks those optional bridges and must
  not be used to assess the running Agent. At the time of that failure, this
  Host's `grants.json` had no `outlook.draft` grant for the mail capability.
  Empty mail recipients are the configured safe default. Three focused tests
  covering successful draft, missing approval and missing Outlook passed
  without external effects.
- With the new grant and current runtime, one installed CLI
  `weekly.mail 2026_40W` run succeeded in three steps. The final Outlook
  receipt named Drafts and carried an EntryID. A read-only COM lookup found
  that exact item in Drafts with `Sent=False` and empty To/CC. No send was
  attempted. The installed Host doctor returned `host status: ready`,
  `resident agent: ready`, and passed assets, integrations and models when
  launched with the existing Windows user credentials. The bare Web root
  returns 401 by design; `--open` launches the fresh token-bearing address.

## Open work and known limits

1. Inspect Workflow 11's successful live preview plan and workbook-read
   evidence against the source on a workbook copy. Do not run apply/mail
   against a real workbook or recipient list during this preview. The installed
   manifest fix is local to this Host; rebuild/re-export assets when updating
   other Hosts, and start a new Agent process after changing environment
   variables so it receives the current token.
2. Use `.scratch/knowledge-validation/host.json` for a live Gateway question
   once the launching Agent has the existing key in its environment. The
   isolated Host has no Shared Platform binding and is only for Knowledge
   validation. `/wiki-convert`, `/wiki-ingest` and `/wiki-lint` are not yet
   installed executable Workflows. Later plan a provenance-preserving
   conversion of the supplied OneDrive tree: its root has `drop/raw/wiki` but
   lacks the required root `index.md` and `log.md`; no nested directory has
   all four. Many entries are OneDrive cloud reparse points.
3. Refresh the installed Workflow 7 preview asset and run it against the real
   Project with the new token. The offline first stage is implemented; the
   credential gate is now clear. Source tests are in the pinned
   `rs_workflow_system` checkout and remain read-only. Later Excel parity uses
   a workbook copy and explicit write approval.
4. Complete generic static/runtime parameter contracts and generated Web and
   Telegram controls, ordinary Agent/task state integration, backend transfer
   authorization, governed native adapters, default Marketplace packages,
   SOP/Knowledge/Skill end-to-end evidence, and optional benchmark-gated JEV.
5. The owner should use the fresh address opened by `aep-host web --open` for
   further Agent Web tests; an old token or the bare `53582/` address returns
   401. Keep only one resident Web process for this Host during validation.
   Report apply and mail are separate Workflows; do not infer that apply
   creates another draft. The locally installed wheel still reports version
   `0.1.0`; a later reinstall from an older bundle could reintroduce the
   manifest/runtime mismatch unless the bundle is rebuilt from current source.

The active checklist is `docs/TASKS.md`; observed readiness is in
`docs/VALIDATION_GAPS_2026-10-02.md`. Prior Gateway policy still applies:
UNCLASSIFIED material uses only the exact approved internal Gateway, and
native Codex/Claude tasks require complete explicitly PUBLIC context.
Publishing or installing an asset grants no execution permission.
