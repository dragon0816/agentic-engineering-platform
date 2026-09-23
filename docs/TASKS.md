# Tasks and progress

The single place that answers "what is done, and what is next". Completed rows
are kept, never deleted, so the record accumulates rather than being replaced.

Backfilled on 2026-09-22 from the merged pull requests and the phase
specifications. Dates are Asia/Taipei and match `docs/ROADMAP.md`.

## Where everything else lives

| Question | File |
|---|---|
| What is the platform meant to be | `docs/ARCHITECTURE.md` |
| Which phase is active, and its exit criteria | `docs/ROADMAP.md` |
| What a slice must do to be accepted | `docs/phases/PHASE_N_*.md` |
| Why a source behaviour was adapted, migrated or refused | `docs/PHASE_N_MIGRATION.md` |
| What each shared contract means | `docs/CONTRACTS.md` |
| Where the current work stopped and how to resume | `HANDOFF.md` |

Decisions are recorded per phase in `docs/PHASE_N_MIGRATION.md` rather than in
one `docs/DECISIONS.md`. Those files are appended to and never rewritten, so
the history is complete; this table is the index into them.

## Status

Phases 0 to 6 complete, closure records included. Phase 7 is active under
`docs/phases/PHASE_7_MIGRATION.md`; slices 1, 2a, 2b, 2c to 2j
slice 3a (workflow 11 up to its plan) and slice 3b (the workbook writer)
have merged, slice 3c puts workflow 11 into the installable bundle and slice
3d makes that bundle extractable on Windows, slice 3e documents the grants it
needs to run and slice 3f corrects the source workflow number it was migrated
under. Workflow 10 is now the active work: slice 4 characterizes the source
and plans four slices. Workflow 11's live parity run is deferred behind it by
the owner decision of 2026-09-23, and only the owner can produce it. 77 pull requests merged (#1 to #82; #5 was closed unmerged and superseded
by #6, the numbers #24 and #25 were never pull requests, and #49 was closed
unmerged when its base branch was deleted and landed through #51). The count
stood at 64 while fifteen of those had merged, counted against GitHub on
2026-09-23. A row says `done`
only once its pull request has merged; until then it says `in review`, so the
committed record never asserts a merge that has not happened.

The suite is 1114 passed, 4 skipped on Windows, with `ruff`, `mypy`,
`pip check` and `python -m build` clean. Three skips need symbolic-link
privileges and one needs an IPv6 loopback; all four run on Linux CI.

## Cross-cutting

| Work | PR | What landed |
|---|---|---|
| Progress record | #40 | This file, backfilled from the merged pull requests, and named in the reading order of `CLAUDE.md` and `AGENTS.md` |
| Flaky progress test | #44 | `test_workflow_progress` compared payload digits against the whole event, including a random run id that contained them about once in a few hundred runs |

## Phase 0 — Architecture and inventory (complete)

| Work | PR | What landed |
|---|---|---|
| Architecture baseline | #1 | `docs/ARCHITECTURE.md`, `AGENTS.md`, the roadmap and the source inventory |
| Governance contracts | #3 | Scoped asset identity, lifecycle and execution-authorization semantics |

## Phase 1 — Foundation (complete)

| Work | PR | What landed |
|---|---|---|
| Skeleton and baseline | #2 | Package layout, pytest, lint, type checks, CI, agent-neutral workflow rules |
| Contracts and proof | #4 | Provider-neutral contracts, in-memory Registry, Bridge advertisement, the first evaluation case schema |

## Phase 2 — Agent and capability layer (complete)

| Work | PR | What landed |
|---|---|---|
| Routing and dispatch | #6 | Deterministic-first routing, Skill registry, permission-checked dispatch, injected MCP adapter (#5 closed unmerged) |
| First capability | #7 | The source's `read_file` adapted as a governed filesystem capability |

## Phase 3 — Workflow platform (complete, 14 slices)

| Slice | PR | What landed |
|---|---|---|
| 1 workflow engine | #8 | Job runner semantics adapted into a governed engine |
| 2 Gateway dispatch | #9 | Routed requests dispatched through one Gateway contract |
| 3 step inputs | #10 | Explicit step inputs and result chaining |
| 4 retries and duplicates | #11 | Bounded read retries, caller idempotency keys |
| 5 bounded resumable state | #12 | Inspect and resume finished runs under explicit policy |
| 6 Gateway run control | #13 | Inspection and resumption exposed through the Gateway |
| 7 progress streaming | #14 | Bounded progress streams to run owners |
| 8 optional n8n adapter | #15 | Offline adapter over the same Gateway contracts |
| 9 checkpoint contracts | #16 | Checkpoint contracts and a bounded in-memory reference store |
| 10 SQLite backend | #17 | Single-writer SQLite checkpoint store |
| 11 payload storage | #18 | Content-addressed, verified payloads |
| 12 engine recovery | #19 | Run journal and recovery after a restart |
| 13 durable run evidence | #20 | Journal-backed run control through the Gateway |
| 14 checkpoint retention | #21 | Finished history retired behind key tombstones |

## Phase 4 — Knowledge platform (complete 2026-09-21, 9 slices)

| Slice | PR | What landed |
|---|---|---|
| 1 vault safety model | #22 | `drop/` and `raw/` immutable, dry run default, backups, whole-plan rejection |
| 2 Drop to Raw | #23 | Write-once Raw with content identity and a drift chain |
| 3 office extraction | #26 | PDF, PPTX and DOCX with page, slide and image relationships |
| 4 image description | #27 | Vision description through `ModelClient` at intake |
| 5 ingest planning | #28 | Two-pass planning, condensation cache, provenance repair |
| 6 static lint | #29 | Typed lint report and the two certain link repairs |
| 7 conflicts and decisions | #30 | Append-only `decisions.md`, markers cleared in one write |
| 8 query with provenance | #31 | BM25 with CJK support, every passage cited |
| 9 migration adapter | #32 | An existing vault adopted by content hash without rewriting `raw/` |
| closure | #33 | Exit criteria recorded in the roadmap, architecture status and README |

## Phase 5 — Model gateway (complete 2026-09-22, 5 slices)

| Slice | PR | What landed |
|---|---|---|
| 1 catalog and selection | #34 | Capabilities declared per endpoint, deterministic selection, typed misses |
| 2 OpenAI-compatible adapter | #35 | One adapter for the company gateway and any OpenAI-shaped API |
| 3 Ollama adapter | #36 | Ollama's native wire format, and `models.wire` extracted |
| 4 credentials and construction | #37 | `SecretRef` resolved per request, clients built from a catalog |
| 5 observability and example | #38 | `duration_ms` on responses and streams, `models.proof` |

## Phase 6 — Evaluation, policy and observability (complete 2026-09-22, 5 slices)

| Slice | PR | Status | What it covers |
|---|---|---|---|
| 1 grading harness | #39 | done | A case's declared assertions decide whether it passed; every grader proven to reject |
| 2 observable execution | #41 | done | One shared runner sends every routed case through a real Gateway; a check that could not see its evidence no longer passes |
| 3 policy and forbidden outcomes | #42 | done | The first `scenario` case; the Roadmap's four prohibitions checked as evidence of what happened |
| 4 model-involving evaluation | #43 | done | The `agent` category, and one case across configured aliases with repetition, compared on correctness, reliability, latency and usage |
| 5 trace capture | #45 | done | `ExecutionTrace` beside every observation: route, dispatches in Bridge order, approvals, workflow progress, model usage, duration and outcome, redacted by construction and refused if a credential remains; `SECRET_PATTERN` spans whole secrets and refuses its own marker |
| closure | #46 | done | Exit criteria recorded as met in the roadmap and the phase specification; architecture status and README updated |

## Phase 7 — End-to-end migration and controlled deprecation (active)

| Slice | PR | Status | What it covers |
|---|---|---|---|
| 1 enrollment foundation | #48 | done | Invitation-only users, independent Bridge device identity, single-user company workstation and multi-user shared test workstation contracts plus an inert reference registry |
| 2a company host preview | #49, landed via #51 | done | Hash-verified offline Windows package, per-user install, local doctor and credential-free empty enrollment request; company-computer install/doctor/export confirmed, no live transport or workflow capability |
| 2b Bridge access tokens | #62 | done | Binding a member to a machine issues a token for that pair; the platform keeps a fingerprint and never the secret, an unknown token and a wrong secret are one answer, and a token becomes the `AuthenticatedActor` entitlement is read from |
| 2c local-first control contracts | #50, landed via #51 | done | Registry package acquisition, verified local inventory, timestamped status projection and actor/device-scoped remote jobs |
| 2d resident local Agent and durable local state | #53 | done | `LocalAgent` admits by the shared device rule and the device's own membership copy on every ingress, routes through the existing Gateway, executes exact remote jobs idempotently, settles timed-out runs, and records runs in a single-writer SQLite local state that outlives the process |
| 2e Telegram ingress | #54 | done | `channels.telegram`: outbound long polling over the platform's transport, numeric sender mapped to exactly one actor with an empty map admitting nobody, `/skill command` translated to the deterministic form, token through `SecretRef` and its shape added to `SECRET_PATTERN`, the same Agent admission and Gateway path |
| 2f company host runtime | #56 | done | `aep-host` assembles the resident Agent from the workspace files (membership, grants, Skill and Workflow manifests) and gains `ask`, `status` and `telegram`; `doctor` reports what the host has been given; the Telegram offset is durable |
| 2g member-decided asset authorization | #58 | done | A member chooses which Workflows, Skills and tools their devices may run; the control plane refuses a decision they may not make and derives the Bridge's grants from the capability's own specification; a host installs and grants only what was chosen |
| 2h identity-derived entitlement | #60 | done | An invitation records which groups accepting it grants; an authenticated actor says who and until when and carries no group; what a member may use follows from the platform's record, and a decision needs a valid session and the member's own name |
| 2j one member per machine, and who asked | #64 | done | Every machine holds one active binding, whatever its kind: a shared test workstation runs as a virtual member of its own, so no colleague's credential sits on a machine other people can read. A request and a run record who asked when that is not who runs; the field is recorded and never consulted. A company workstation refuses delegation outright, and a Telegram sender who is not the machine's member drives a shared machine as the virtual member on their behalf |
| 2i authenticated shared-platform transports | #66 | done | `common.sync` is the six-operation wire; `ControlPlaneService` answers it over the in-memory references and `ControlPlaneServer` serves it from the standard library; `PlatformClient` presents the Bridge access token, classifies every answer (answered, unreachable, withdrawn, rejected, refused) and applies a sync only after the whole reply is verified; jobs are polled, run through the resident Agent, settled and reported; `aep-host probe|sync|jobs`. Unreachable is never treated as revoked |
| 3b workflow 11: writing the plan into the workbook | #70 | done | A typed `WorkbookWriter` and the source's order of operations behind it: back up, stage, verify the sheet is the one that was planned, upsert, retire last week's marks across the whole sheet, tint, border and pink what is new, recolour, link every key, prepend in red with a black tail. `ExcelComWriter` is the one adapter and the only thing that knows about COM; every test drives a recording writer. `weekly-report/apply` is the first side-effecting capability, approval required |
| 3c the offline bundle carries workflow 11 | #72 | done | The preview bundle carried `pydantic` alone, so the artefact a member can install could not run the workflow slices 3a and 3b shipped, and the install instruction named a package index this platform is not published to. The `excel` and `windows` extras are bundled as wheels, the builder refuses a bundle missing one, the installer takes them from `wheels/` with `--no-index`, CI imports them from the installed bundle, and every instruction that named an index is corrected |
| 3d a bundle nobody can extract is a bundle nobody can install | #74 | done | The owner's first download of the slice 3c bundle failed with a missing wheel. The zip was complete: two of its files needed more than Windows' 260-character path limit once downloaded as an artefact and extracted in a Downloads folder, and Explorer left them out silently. The bundle and artefact names shrink, the builder refuses names that would not survive the download, and the installer measures the path and names the cause before it reports a missing file |
| 3e the grants the weekly report actually needs | #76 | done | Following the preview's README produced `permission_denied` before Jira was reached: all five capabilities declare that they need an approval, the four reads included, and the page said only the write did. The README writes out every grant, and a test parses that JSON and puts it through the real policy, so the page and the capabilities cannot drift |
| 3f the workflow this phase migrated is number 11 | #78 | done | The owner asked why the settings were the weekly report's while the documents said workflow 7. The source numbers the weekly report 11; workflow 7 is `jira_team_tickets`, a different job this repository has never read. The wrong workflow file was paired with the right job in the candidate table on 2026-09-22 and propagated everywhere. Every reference is corrected, the decision record gains a dated correction rather than a silent edit, and source workflow 7 is recorded as unmigrated |
| 3g Excel macros and a failed save | #80 | done | The adapter opened Excel without suppressing events, so a team workbook's `Workbook_Open` would run inside an unattended job, and it folded saving into closing, which the executor treats as best effort: a failed save left the report out of the file and the run then copied the staged workbook back and reported success. Saving is now its own refusal, `save_failed`, and the executor lets that one through its cleanup |
| 4 workflow 10 characterization and plan | #80 | done | The source read in full: 1253 lines of rules, a 683-line job, its 706 lines of tests and the 511-line mapping specification that declares itself authoritative over the code. Disposition recorded per part, a parity gate, twelve source defects each decided as preserved or fixed with the reason, and four slices. The team's real ruleset is not in the pinned source, so the parity run needs the owner's own file |
| 4a workflow 10: the rules, ported pure | #82 | done | The source's 1253 lines of transformation ported with no I/O and no clock, and its own tests as the oracle: 149 cases pass, case for case. The ruleset is a closed contract instead of an unvalidated dictionary, so a misspelt key is a refusal rather than a rule that quietly stopped applying; the source's own example file ships as the default and travels in the wheel. Five source defects fixed, each with a test that names it |
| 5 workflow 11 reads GitHub instead of Jira | #85 | in review | Jira is switched off and the project information moved to a GitHub Projects board whose issues were rebuilt from the weekly workbook. The board is characterized from a real read, the owner's three decisions are recorded, and the client that reads it is built: the board's field values, the issue behind each row and its comment thread, with the secret resolved per call. An issue the token may not read is a refusal rather than an empty week |
| 5a a configuration that cannot be used says which field | #87 | in review | The owner edited `host.json` by hand and every command answered `configuration is missing or invalid; no input values were displayed`, which named nothing. The field is not a value: the refusal now lists the fields that are wrong and the rules they broke, says where a file that is not JSON stops, and distinguishes a file it cannot read, while still showing nothing the file contains |
| 5b ask the registry whether Excel is there | #89 | in review | The check for Excel called a function that does not exist in `pywin32`, so on every real host it raised an attribute error that the check swallowed and reported as `excel_missing`. Every host would have been told it cannot write. It now reads the registry directly, and the test that was missing asks the real registry about a ProgID every Windows machine has |
| 3h installing over a configured host keeps its configuration | #84 | in review | Reinstalling the preview replaced `host.json`, so an update discarded the integrations and credential mappings the operator had typed, without saying so. The installer now keeps every key it does not write itself and names them, and refuses rather than overwrites a file it cannot read. CI installs over a configured host and checks what survived |
| 3a workflow 11: rules, Jira fetch and plan | #68 | done | The source's weekly-report rules ported pure with its own tests as the oracle; a Jira client over the platform's transport with the secret resolved per call; four read capabilities (resolve the window, search Jira, read the scratch sheet without Excel, plan) and the preview Workflow over them; the plan is the dry run and the evidence; `aep-host export-assets`, `integrations` in `host.json` and a doctor check. Nothing writes a workbook; how the platform writes one is a decision for the owner |
| 3 workflow 11 parity | — | planned | The Jira report against a test workbook on the company Bridge, compared with the working old Host Bridge. Needs a machine with Excel: the evidence is the owner's to produce and CI never claims it |
| 4 workflow 13 parity | — | planned | Release package behavior in dry-run and an isolated test repository before any approved push |
| 5 knowledge parity | — | planned | Adopt, query, update and restore a full copy of the source vault |
| 6 controlled cutover | — | planned | Per-entry-point evidence, rollback rehearsal, owner approval and observation before freezing old entry points |

## Open items carried forward

Recorded where they were found. None blocks a completed phase's exit criteria
or the start of Phase 7. The two Phase 7 entries are consequences of owner
decisions rather than defects; they are here so that whoever operates a Bridge
knows about them.

| From | Item |
|---|---|
| Phase 3 | A payload sweep, and process-liveness or lease-based suspension |
| Phase 4 | A retrieval cache, host wiring that plans from an adopted document, a size-and-mtime shortcut for adopted-file drift checks, image description for legacy `raw/` |
| Phase 5 | Tool calling in either adapter (it needs a registry that can render a contract as a provider schema), reading `tool_calls` back, retry behaviour, a pooled or async transport, a production credential backend |
| Phase 6 | Nothing persists an `ExecutionTrace` yet (a host writes them beside its checkpoints); `SECRET_PATTERN` is deliberately narrow and a provider-specific token shape it does not name is not redacted; `stayed_in_namespace` has no allowance for a capability legitimately shared across namespaces |
| Phase 7, slice 2j | Taking somebody off a shared machine is a host action: their `telegram.json` entry keeps working after `disable_user` or `unbind`, because the request runs as the virtual member and `on_behalf_of` is never consulted. Offboarding has to include editing that file. Moving the sender list into the authorization bundle is the change that would make it a platform action, and the owner decided against it |
| Phase 7, slice 3b | `ExcelComWriter` has never been run. There is no Excel in CI and none on this machine, so the adapter is written to the documented COM object model and exercised only through a recording writer, exactly as the pinned source's own tests exercised its Bridge. One run on a company workstation against a copy of the workbook should confirm it before any run against the real one — the same caveat the model adapters carry |
| Phase 7, slice 2i | A polled job whose settle was lost is re-offered by the platform and, after `aep-host jobs` restarts, runs again: the idempotency key lives in the engine's in-memory table, because the company host runs its engine without a journal. Durable idempotency for polled jobs (a journal for the host's engine, or the platform's own lease) is deferred to the first workflow whose side effects make it necessary |
| Phase 7, slice 5 | The workflow asset is still called `engineering/jira-weekly-report`, which now names the wrong source. Renaming it changes an asset identity that grants, installed manifests and any platform decision refer to, so it is a migration of its own and not a rename made in passing |
| Phase 7, slice 4a | `test_health_and_bad_requests_over_http` fails about once in a dozen whole-suite runs and never on its own: it passed eight times in isolation, six times with its own module, and twenty-four consecutive whole-suite runs after the one failure that was seen, which left no output to read. It predates this slice. The suspect is the refusal of a request declaring a 64 MiB body, where the client may see the connection close before the reply; the bounded lingering close added in slice 2i reduced that and evidently did not end it. Nothing is changed on a suspicion without a reproduction |
| Phase 7, slice 4 | The team's real `chipset-map.json`, the ruleset workflow 10 transforms with, is not in the pinned source: it carries only `chipset-map.example.json`, so every run in that tree falls back to the example. The real file exists on the company machine and is needed for the parity run. It is host configuration, not content for this repository |
| Phase 7, slice 3f | Source workflow 7, `jira_team_tickets` / `workflows/07_jira_team_tickets_to_excel.json`, has never been inspected, characterized or migrated. It was named in the Phase 7 candidate table by mistake, in place of the weekly report that was actually built. Whether it is migrated at all, and where it belongs in the order, is an owner decision that has not been asked for |
| Phase 7, slice 2j | An approval on a tool selection may still name the acting member (`approved_by == actor`), as it could on a company workstation before the slice. Whether an approval must come from a second person is an owner policy decision that has not been asked for |

**Leaked credentials in the pinned `telegram-local-agent` source, checked
2026-09-23.** Its `config.yaml` is tracked and carries two values. The
Telegram bot token is **already dead** (`getMe` answers 401, and the config
itself says so). The GitLab personal access token is for a **local Docker
GitLab in WSL2** (`http://172.26.111.166:8929`), whose distribution is not
running, so there is nothing live to revoke; `docker/setup_template.py`
reissues it by design. The repository is private on GitHub, and this
repository never carried either value: `.scratch/` is gitignored and nothing
under it is tracked. What remains is that both sit in that repository's
history. Scrubbing it would change the commit the Phase 7 rollback baseline
is pinned to, so it is deliberately **not** done while that pin stands; it
belongs with the cutover, when the pin is retired.

**Never exercised against a live endpoint.** Neither the Ollama adapter nor
the company gateway has been run against a real server. Both are written to
documented APIs and covered by tests with an injected transport. One real
request against each should confirm the field names before anyone relies on
them, particularly Ollama's `prompt_eval_count`, `eval_count` and the
streaming `done` flag.

## Owner decisions

| Date | Decision |
|---|---|
| 2026-09-21 | Provider adapters are in-process code; a proxy, if ever deployed, is a host artifact, and the platform never starts a provider process |
| 2026-09-21 | Phase 5 providers are Ollama and the internal OpenAI-compatible gateway; Codex and Claude Code are excluded as model providers |
| 2026-09-22 | Codex and Claude Code are out of scope for Phase 6 entirely: not evaluated, not driven, not a capability the platform invokes |
| 2026-09-22 | Remaining slices are completed without check-ins unless something cannot be decided |
| 2026-09-22 | Phase 7 prioritizes workflow 7 (`jira_team_tickets`) then workflow 13 (`release_package`), followed by knowledge on a copy |
| 2026-09-23 | Workflow 10 (`sales_to_chipset`, the sales opportunity list projected into the chipset requirement workbook) is migrated next, ahead of workflow 11's live parity run. Workflow 11 stays in scope and complete in code; only its run on a company workstation is deferred. Asked and answered when the owner found that the workflow they need is 10, not the one this phase had been building |
| 2026-09-23 | Jira is switched off. Workflow 11 reads its project information from the GitHub Projects board `dragon0816/rs-sde-projects` instead, whose issues were rebuilt from the weekly workbook and keep the original Jira keys in their titles |
| 2026-09-23 | The workbook stays workflow 11's deliverable: GitHub replaces Jira as the source and nothing downstream moves |
| 2026-09-23 | The reporting week is still chosen by time, with the same default window as before and an explicit range that can be configured for special cases. The board's `Week` field is not the selector |
| 2026-09-23 | The board's `Week` field is a note for people, not data this platform reads. It is going to be deleted, so nothing is built on it. The consequence, accepted: selecting the week by time finds nothing for the weeks before the board was rebuilt, and the report runs forward from the rebuild |
| 2026-09-23 | The board's fields are authoritative for Company, Status, Assignee and Sales; the block in each issue's body is a snapshot of the rebuild and is not read |
| 2026-09-23 | Correction to the row above, `Phase 7 prioritizes ...`: the workflow Phase 7 migrated is the GTM weekly report, `jira_weekly_report` / `workflows/11_jira_weekly_report.json`, which the source numbers **11**. `jira_team_tickets` / `workflows/07_jira_team_tickets_to_excel.json` is a different workflow that has never been inspected or ported. The behaviour that was characterized and built is unchanged; only the number was wrong (`docs/PHASE_7_MIGRATION.md`, "Correction") |
| 2026-09-22 | Platform registration is invitation-only; the shared-platform host cannot use company LDAP |
| 2026-09-22 | Production-like execution occurs on an enrolled company Agent + Bridge; the current old Host Bridge can run workflows 11 and 13 and remains the parity/rollback baseline |
| 2026-09-22 | A company workstation has one employee/platform member and corporate resource access; a shared test workstation has multiple invited platform users, no corporate access, one shared Windows account and no claimed OS-level isolation |
| 2026-09-22 | CI remains inert. Source repositories and old entry points are retained at pinned revisions until parity and rollback rehearsal; archive is a later decision and deletion is outside Phase 7 |
| 2026-09-22 | A platform user decides, for each device they may use, which Workflows, which Skills and which tools that device may run for them; nobody decides for anyone else |
| 2026-09-22 | The shared platform runs on an internal-network shared workstation: reachable from company computers, signed in to by several people, and still unable to use company LDAP |
| 2026-09-22 | A Bridge is bound to a user, and the user's authentication decides which Workflows and Skills they may use; group membership comes from the invitation, not from the authentication |
| 2026-09-23 | Binding a user to a machine issues an access token for that pair, kept on the Bridge; several members on one machine hold several tokens, and a Bridge presents one to authenticate with the shared platform, as the pinned Host Bridge exchanged a user sign-in for a machine token |
| 2026-09-23 | Every machine is bound to exactly one platform member. A shared test workstation gets a virtual member of its own and no real employee binds to it; employees who need it drive it through Telegram, and the record says which employee asked. This supersedes the 2026-09-22 row above that gave a shared test workstation multiple platform users, and with it the "several tokens on one machine" part of the row above: one member per machine means one token per machine |
| 2026-09-23 | A shared test workstation is wired to particular instruments and laid out as a test environment for automated testing; it belongs to that rig rather than to a desk, which is why a virtual member rather than a rota of employees fits it |
| 2026-09-23 | The workbook is written through Excel itself (COM) on the company workstation rather than through a library. Delegated: the owner asked for the slice to be finished after being given both options and a recommendation. Reversible — the executor writes through a `WorkbookWriter` protocol and knows nothing about COM |
| 2026-09-23 | Being an invited, authenticated member is the gate for using the platform's resources. A request is not narrowed further by who asked for it, and the list of people who may drive a machine stays host configuration rather than something the control plane delivers |

## Resolved owner decisions (Phase 7)

Who decides what a device may run, and where the shared platform runs, were
answered on 2026-09-22 and are in the table above. What is still open is the
authentication design the transports needed, which the owner settled on
2026-09-23: a Bridge presents an access token issued for one member on one
machine. Who decides, what a member may use and what a Bridge presents are all
settled now, and slice 2i can be built.

The four decisions that previously blocked the specification are resolved by
the dated owner decisions above and `docs/phases/PHASE_7_MIGRATION.md`:

1. Candidates/order: workflow 11, workflow 13, then knowledge; retire individual
   entry points only after evidence, never an entire mixed repository first.
2. Parity: normalized source/platform behavior and safety gates are explicit for
   each candidate; timestamps and container metadata are not byte-parity targets.
3. Environment: shared platform here, real work on an enrolled company Bridge;
   external credentials remain on that Bridge. CI never performs live validation.
4. Rollback/retention: pin and retain the source plus working old Host Bridge;
   rehearse rollback before cutover. Archive later; do not delete in Phase 7.
