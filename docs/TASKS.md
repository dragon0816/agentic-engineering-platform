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

- [x] Add Agent Web context Settings and local session management (2026-10-03):
  show declared model capacity separately from effective recent-message and
  UTF-8 history-text limits; apply saved limits to Gateway and local CLI chat;
  reject oversized current questions without truncation; keep a rolling
  100-message transcript and allow owner-scoped session deletion. Cross-session
  memory remains out of this owner-selected slice.

Phases 0 to 6 are complete. Phase 7 remains active under
`docs/phases/PHASE_7_MIGRATION.md`. The enrollment, resident Agent, platform
transport, authorization and workflow 11 implementation slices have merged;
workflow 10 rules and a guarded local preview/apply slice are ported; the
owner's actual source workbooks, mapping rules and a real Excel parity run are
still open. Workflow 13 has a source-pinned read-only preview and an isolated
prepare slice, with governed release execution still open. Workflow 7 is
paused at the owner's request while `MRT1CV` access is resolved. PR #96 merged
the local interfaces, company-model wiring, bounded
SOP-to-Workflow authoring, installed-browser automation and weekly mail draft.
A product-direction review merged in PR #97 and is documented in
`docs/AGENT_HARNESS_ARCHITECTURE_PROPOSAL.md`. The owner approved its fixed
E2E order. E2E-02 merged in PR #98, E2E-03 merged in PR #99 and E2E-05 merged
in PR #100 after each exact head passed Windows/Python 3.12 CI. E2E-04 merged in
PR #101 after its exact head passed Windows/Python 3.12 CI. E2E-01's inert
simulator proof and Windows owner-run physical validation entry point are
implemented; the production-like company-host run remains pending.

## Productization 1 — Personal Agent Web and Workflow Marketplace (complete)

| Slice | Status | Acceptance evidence |
|---|---|---|
| 1 shared catalog read path | done | Authenticated, entitlement-filtered catalog over the existing platform transport; Web distinguishes published, authorized and installed state; discovery has no installation or execution side effect |
| 2a member selection contract and entry point | done | PR #143: direct member session, entitlement-filtered Workflow list and select/revoke HTTP/page proof; Bridge credential is rejected and selection grants no execution permission |
| 2b invitation member sign-in adapter | done | PR #145: one-time high-entropy invitation proof is stored only as a fingerprint, accepts the named secret-free invitation and produces the short-lived member session used by slice 2a; real HTTP proof carries no identity/permission claims |
| 2c deployable Shared Platform composition | done | PR #147: one lifecycle serves the Bridge API and Member Portal over shared in-memory state; `aep-platform` writes one-time invitation links to an explicit delivery file and Personal Agent Web links to the separate member origin without forwarding its Bridge token |
| 3 explicit synchronization | done | PR #149: Personal Agent Web invokes the existing all-or-nothing sync only from an explicit button and returns typed before/after, installed, selection and refusal state; catalog discovery remains read-only |
| 4 generic Workflow launch | done | PR #151: Personal Agent Web lists exact installed Workflows and input-contract names, accepts one JSON argument object and executes through Local Agent admission, Gateway exact targeting, Workflow engine and Bridge policy with idempotent run/trace results |
| 5 grounded Knowledge asking | done | PR #153: exact configured Knowledge versions are listed without Vault paths; one closed question request executes the existing exact Knowledge capability through Local Agent admission and Bridge policy and returns grounded Raw citations |
| 6 durable Registry | done | PR #155: published package metadata and digest-verified artifact bytes persist in SQLite behind the existing catalog and synchronization contracts; sessions, selections, jobs and execution remain outside the store |

The approved scope and first user-level acceptance scenario are in
`docs/phases/PRODUCTIZATION_1_AGENT_WEB_MARKETPLACE.md`. This milestone does not
add another Telegram/GitHub orchestration layer.
PR #107 merged the remote Hermes feedback loop with restricted Draft PR
delivery, machine-readable `hermes-next-action/v1` handoffs, and a separate
`hermes-retest-passed` notification path. Hermes polls and deduplicates trusted
payloads to collect evidence or retest an exact repair SHA; the configured
reviewer alone decides whether to merge. The next slice adds an explicit,
bounded validation-request lifecycle so Hermes can start from a requested
validation instead of waiting for a manually constructed failure Issue.
A row says `done` only after its pull request merges.

## Productization 2 — Agent Add-on Marketplace (complete)

| Slice | Status | Acceptance evidence |
|---|---|---|
| 1 Skill selection and activation | done | PR #157: member portal lists/selects exact Workflows and Skills, derives kind from the Registry, syncs the Skill and proves a rebuilt Agent uses its deterministic command without adding grants |
| 2 portable Knowledge package | done | PR #159: one exact manifest, immutable Raw and curated Wiki content install through a path-safe closed package without a publisher-controlled local Vault path |
| 3 Knowledge marketplace activation | done | PR #161: member selection and sync create an exact host-derived local Knowledge binding; rebuilt Personal Agent Web answers with Raw citations while selection adds no capability grant |
| 4 Agent profile package and activation | done | PR #163: member selection installs an inert exact profile; explicit local activation validates every dependency and narrows Skills, Knowledge, capabilities and model requirements without delegation |
| 5 version change and rollback | done | PR #165: atomic exact-version replacement updates or rolls back active selection while retaining verified prior local bytes and leaving capability grants unchanged |

## Productization 3 — Bridge Extensions and Application Catalog (complete)

| Slice | Status | Acceptance evidence |
|---|---|---|
| 1 category and metadata contracts | done | PR #166: closed Bridge Extension compatibility/process/health/rollback metadata and an independent Application projection over governed Software; extensions remain outside Agent Add-ons |
| 2 inert extension staging | done | PR #169: Ed25519 verifier boundary plus trust/revocation, digest, compatibility and path validation precede an atomic isolated-version write; no publisher code runs |
| 3 bounded extension runner | done | PR #171: one device/policy-approved version uses an offline isolated environment and fixed JSON-lines subprocess; only healthy exact declarations advertise, while failure removes them and preserves/recovers a healthy prior version |
| 4 Application catalog | done | PR #172: authenticated members discover entitled released external Software and declared integration points without naming a Bridge or receiving selection/install/activation operations |
| 5 marketplace lifecycle UI | done | PR #175: Personal Agent Web shows valid staged Extension packages and atomically persisted runtime state without activation controls; the direct-member marketplace lists entitled external Applications and only opens declared Web UI links |

Productization 2 and Productization 3 have reproducible passing exit paths.
Their independently verified boundaries remain in the phase specifications.

At PR #96's merged head the combined Windows result is 1282 passed, 4 skipped, with
`ruff`, `mypy`, `pip check` and `python -m build` clean. Nine browser
cases blocked by the command sandbox passed when rerun outside it. The same
commit passed GitHub Actions on Windows and Ubuntu with Python 3.11 and 3.12.

## Cross-cutting

| Work | PR | What landed |
|---|---|---|
| Progress record | #40 | This file, backfilled from the merged pull requests, and named in the reading order of `CLAUDE.md` and `AGENTS.md` |
| Flaky progress test | #44 | `test_workflow_progress` compared payload digits against the whole event, including a random run id that contained them about once in a few hundred runs |
| Remote Hermes failure feedback | #105, replacement pending | `codex-fix` is being migrated from API-billed `openai/codex-action` to a typed GitHub queue consumed by a trusted local Codex Pro worker; Issue content remains bounded untrusted evidence and no workflow merges code |
| Remote Hermes repair handoff | #107 | Restricted Draft PR delivery, bot-authenticated `hermes-next-action/v1` payloads, and a green-retest reviewer notification; no Action merges code |
| Hermes validation lifecycle | pending | Versioned validation request/owner-decision contracts and a GitHub control-plane state machine that queues Hermes preflight/test, repair handoff and terminal notification without granting access or executing Issue text |
| Company Agent deployment integration | #129 | A successful `main` Windows preview build creates one dynamic, artifact-pinned `aep-company-agent-integration-v1` request covering SOP draft, exact Knowledge query and fixture-scoped Personal Proof; the action has no checkout, Bridge connection, credential, or merge authority |
| Collision-safe validation loopback | #131 | The Company Agent profile declares a bounded loopback-only port range so Hermes can skip existing listeners, own only its fixture server and avoid blocking the full proof on a machine-wide fixed port |
| Fixture-scoped proof authorization | #125 | `personal.proof` receives a distinct read-only capability rooted only at the Hermes-owned fixture directory, so its test grant cannot become a general workspace read grant |
| Local developer credentials | pending | Each development computer may load allowlisted `GH_TOKEN`/`AEP_GITHUB_TOKEN` values from a Git-ignored `.env/local.yaml`; the tracked example is empty and the platform runtime never auto-discovers it |
| Local Codex Pro repair worker | #133, #135 | GitHub emits idempotent `codex-local-request/v1`; a Windows logon task runs token-isolated `codex exec`, applies fixed verification, opens a Draft PR, and GitHub emits exact-SHA `hermes-next-action/v1`. PR #133 fixed executable/result diagnostics and bounded retry. Issues #132/#134 then exposed a contract mismatch: Hermes returned the requested complete results under `evidence_details`, while the queue rejected that optional field and silently reused the older payload. PR #135 adds a bounded, exact-identity structured-evidence extension; human review remains the merge gate. |
| Validation/Coding Telegram coordination | #137 | One optional shared group removes manual message copying: owner `/status`, role-neutral `aep-agent-coordination/v1`, bounded mechanism blockers, GitHub-verified implementation-event acknowledgements, durable offset/event dedupe and best-effort worker state notifications. Hermes and Local Codex currently fill replaceable roles. GitHub remains authoritative for code; Telegram cannot supply commands or merge. |
| Bounded Telegram mechanism guidance | #140 | The first deterministic handler maps only unresolved `MODEL_ROUTING_NOT_CONFIGURED` to `provision_profile_model_routing` and retry of the same request. Existing persisted blockers are upgraded in place; unknown codes remain review-only and Telegram still cannot start Codex or mutate GitHub. |

## Product E2E gates (active)

The order is fixed by `docs/PRODUCT_ACCEPTANCE_TESTS.md`; a later row cannot
start until the preceding row has a reproducible passing path.

| Gate | PR | Status | What it covers |
|---|---|---|---|
| E2E-02 SOP to deterministic Workflow | #98 | done | Natural-language SOP through resident Agent/Gateway, semantic capability requirements, inert fixture execution through Gateway/Workflow/Bridge, independent output grading, human publication decision and no-model deterministic replay |
| E2E-03 parser/transformation development | #99 | done | Pinned bounded workspace, pre-mutation plan, actual patches, injected declared validator, deliberately failing first candidate, one structured repair, new plus regression validation, trace and Skill versions; no commit/push/publish |
| E2E-05 knowledge continuous evolution | #100 | done | Exact version query with Raw citations, feedback evidence, approved Bridge candidate write, immutable Raw, persisted rejected claims, new plus regression evaluation, separate domain approval, versioned republish and rollback |
| E2E-04 software continuous evolution | #101 | done | Exact external repository metadata, report routing, pre-change reproduction, approved Harness development, issue plus regression validation, inert PR preparation, separate human review/merge/release/republish and exact rollback |
| E2E-01 DUT/chipset engineering | #102, #103 | owner validation pending | Provider-neutral contracts, bounded Harness + simulator proof, exact Skill/resource admission, high-risk Bridge policy, fixed local driver boundary and evidence CLI; real enrolled-company-PC evidence remains required |

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
| 5 workflow 11 reads GitHub instead of Jira | #85 | done | Jira is switched off and the project information moved to a GitHub Projects board whose issues were rebuilt from the weekly workbook. The board is characterized from a real read, the owner's three decisions are recorded, and the client that reads it is built: the board's field values, the issue behind each row and its comment thread, with the secret resolved per call. An issue the token may not read is a refusal rather than an empty week |
| 5a a configuration that cannot be used says which field | #87 | done | The owner edited `host.json` by hand and every command answered `configuration is missing or invalid; no input values were displayed`, which named nothing. The field is not a value: the refusal now lists the fields that are wrong and the rules they broke, says where a file that is not JSON stops, and distinguishes a file it cannot read, while still showing nothing the file contains |
| 5b ask the registry whether Excel is there | #89 | done | The check for Excel called a function that does not exist in `pywin32`, so on every real host it raised an attribute error that the check swallowed and reported as `excel_missing`. Every host would have been told it cannot write. It now reads the registry directly, and the test that was missing asks the real registry about a ProgID every Windows machine has |
| 5c a host that will not guess a namespace still says what it has | #90 | done | `no namespace is configured` named nothing, and somebody who has just installed a host has no way to know which namespace its own assets are in. It now says: one namespace, several, or that nothing is installed yet, which are three different problems |
| 5d the doctor checks the token's variable is set | #91 | done | A host whose secret was mapped but whose environment variable was empty passed its own doctor and then failed at the first fetch with `github_credential`. `setx` on Windows sets a variable for the next process, not the one running, which is exactly how this happens. The doctor now names the variable that is not set, without reading what would be in it |
| 5r the Windows preview identifies and repairs its installed build | #104 | done | A company-PC install still exposed an older `0.1.0` runtime, so `version` looked current while `dut-validate` was absent; its retained membership also named another Actor/Bridge and the optional board token kept the resident Agent pending. The installer now verifies `dut-validate`, retains the exact source revision, writes the company workstation's single-owner membership from the requested Actor and derived Bridge ID, and repairs it on reinstall. `verify.cmd` checks the installed revision/command. An absent board token is pending for that integration while the local Agent remains ready. Membership still grants no capability; grants, approval and physical enablement remain separate. |
| 5e name what GitHub refused | #92 | done | A refusal from GitHub arrived as `github_bad_reply` whatever it was, so a token without project access and a malformed answer read alike. GitHub types its GraphQL errors, and those kinds are now codes: a missing scope, a forbidden query, something not found, a throttle. The throttle is transient beside an outage |
| 5f say it in UTF-8 whatever the console is | #93 | done | `--json` crashed part way through its answer on the owner's machine: a Traditional Chinese Windows console is cp950, and what this prints is the team's own board titles and comments. The command line now writes UTF-8 whatever code page the console has. The character that broke it is in a regression test |
| 5g `ask --output` writes the answer itself | #93 | done | Redirecting the answer with PowerShell's `>` writes UTF-16, so the file was not the JSON anybody asked for and reading it failed on the first byte. The command writes the file itself, in UTF-8, and the screen and the file now say the same thing |
| 5i no run may lose a sheet | #95 | done | The first real write lost a week's own sheet from the team's workbook and nothing noticed until somebody looked at the tabs. The backup taken before the run has it. That every sheet but the scratch one comes through untouched is the parity gate's first line and was trusted rather than checked; the run now reads the sheet names before and after and refuses to save if any went or any arrived. The cause is still being found |
| 5j the cause: the seed was renamed, not the copy | #95 | done | The sheet lists before and after showed it: the workbook kept the same number of sheets and `2026_38W` became `weekly report temp`. `Copy` put the new sheet where this code could not see it, and the position it then renamed still held the seed. The sheet that gets the name is now the one that appeared, found by comparing the names; nothing appearing is a refusal |
| 5m the mail's chart, its draft and `weekly.mail` | #96 | done | The chart is drawn by this package: matplotlib would have meant numpy, Pillow, fonttools and contourpy in an offline bundle installed with `--no-index`, tens of megabytes, on a bundle that has already had one install fail for a path that was too long. A pie is arithmetic and a circle, so `chart.py` rasterises one and writes the PNG with `zlib` and `struct`. No text is drawn: the legend is the HTML table beneath the picture with a colour per row, which is better than a drawn legend rather than a compromise — the labels stay selectable, they wrap on a phone, and a reader whose client blocks images still has every number. The draft is Outlook through COM and **nothing in it can send**: a test reads the module's own source to keep it so. `weekly.mail` is its own workflow of three steps and its own grant, because it reads the board and never the workbook, so a member who may draft the mail need not be one who may write the team's file. The doctor now says whether this machine can draft at all |
| 5k who worked on what, and the mail that says it | #96 | done | The source's weekly mail counted tickets per member, per instrument and per account and mailed the totals with a pie chart. The counting and the mail's words are ported with the board's own shapes as the cases: an instrument field holding several names is counted under each and the mail says its totals exceed the ticket count rather than hiding it; a name nobody listed is still the answer; a ticket whose timestamp merely moved is not work, and the ones excluded are named rather than left to vanish. The chart, Outlook draft and `weekly.mail` command are completed in the same review |
| 5o a company host may be given a model | #96 | done | The owner said on 2026-09-24 that the team runs a LiteLLM gateway in front of the company's internal LLM. That gateway is what Phase 5 migrated *from*, and the model layer built for it was complete and exercised in CI while nothing on a company host could reach it: `build_gateway` made the router without a model and `CompanyHostConfiguration` had no field to put one in. It now has `models`, and the router is given a client built from it. Three refusals rather than one: an unmapped secret stops the host being assembled instead of failing at whatever somebody typed first; a provider this build has no adapter for is refused at assembly too; and a host that sets `require_local_model` while naming a gateway is refused where it was written rather than at the first message, where it would read as the model declining to answer. That flag is the path left open for a workstation with the memory to load a model itself, and for one that must keep working with nothing reachable; it is about compute, not about the network, and it is off by default because naming a gateway and mapping its credential is already the decision. (An earlier draft of this slice had it the other way round, as `allow_remote_models`, on a misreading of `local` as a data boundary: it would have put a line in every host that carried no information. Corrected the same day.) What the model proposes is still checked against what is installed — a name it invents never becomes a run — and a command that matches deterministically never reaches the gateway at all. Driven end to end against a stand-in gateway shaped like LiteLLM's, including the non-standard `usage` field `docs/PHASE_5_MIGRATION.md` recorded |
| 5n a web interface, served by the machine itself | #96 | done | The owner's decision of 2026-09-24: the interface is a web page, not a desktop window, because what it has to grow into is a catalogue — publishing and installing Skills and Workflows — and HTML is what a catalogue is made of. `aep-host web` serves it from the standard library alone, like `control_plane.http` and for the same reason: a company machine installs with `--no-index` behind a proxy that reaches no CDN, so every byte comes from the host and a test asserts the page reaches for nothing. It is **generic**: there is no page for the weekly report or any other work, because a page written for one workflow has to be written again for the next. Loopback only, a token made afresh each run, a header on every API call so no other origin can drive it, and a `Host` check so a name that resolves to 127.0.0.1 cannot either. Every guard is tested over a real socket, because a guard tested through a function call was never asked the question an attacker asks. The Tk window stays until this replaces it |
| 5l a window, a double-click and a schedule | #96 | done | Every route into this host was a command with four flags, and an operator who has to type one to see a week's plan does not run it. `aep-host chat` opens a window over the same resident Agent the command line and Telegram reach, as the same `local` ingress: no routing, policy or capability lives in it, so it can do no more and no less than `ask`. It takes one request at a time, because two would be two runs against the one workbook. Tk is in the standard library, so the offline bundle does not grow; a Python built without it says so and names `ask`. Beside it the bundle now carries `chat.cmd`, `weekly-preview.cmd`, `weekly-apply.cmd` and `schedule-weekly.ps1`, which registers a Windows task that runs the preview only — writing stays something a person does |
| 5p bounded SOP-to-Workflow authoring | #96 | done | A written procedure is drafted into the existing typed `WorkflowManifest` contract, then checked for declared dependencies, permission classification and dry-run viability. The result remains an unpublished candidate and cannot bypass review or execution authorization. |
| 5q installed-browser adapter | #96 | done | A Bridge may drive an already-installed Chromium browser through typed navigation, element inspection, form actions and screenshots using a dedicated profile. The adapter exposes neither arbitrary JavaScript nor shell execution; its real-browser suite runs separately from inert CI cases where needed. |
| 3h installing over a configured host keeps its configuration | #84 | done | Reinstalling the preview replaced `host.json`, so an update discarded the integrations and credential mappings the operator had typed, without saying so. The installer now keeps every key it does not write itself and names them, and refuses rather than overwrites a file it cannot read. CI installs over a configured host and checks what survived |
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
| Phase 5 | Ollama tool calling, streaming tool-call deltas, provider-schema mappings beyond the approved installed-command argument object, retry behaviour, a pooled or async transport, a production credential backend |
| Phase 6 | Nothing persists an `ExecutionTrace` yet (a host writes them beside its checkpoints); `SECRET_PATTERN` is deliberately narrow and a provider-specific token shape it does not name is not redacted; `stayed_in_namespace` has no allowance for a capability legitimately shared across namespaces |
| Phase 7, slice 2j | Taking somebody off a shared machine is a host action: their `telegram.json` entry keeps working after `disable_user` or `unbind`, because the request runs as the virtual member and `on_behalf_of` is never consulted. Offboarding has to include editing that file. Moving the sender list into the authorization bundle is the change that would make it a platform action, and the owner decided against it |
| Phase 7, slice 3b | `ExcelComWriter` has never been run. There is no Excel in CI and none on this machine, so the adapter is written to the documented COM object model and exercised only through a recording writer, exactly as the pinned source's own tests exercised its Bridge. One run on a company workstation against a copy of the workbook should confirm it before any run against the real one — the same caveat the model adapters carry |
| Phase 7, slice 2i | A polled job whose settle was lost is re-offered by the platform and, after `aep-host jobs` restarts, runs again: the idempotency key lives in the engine's in-memory table, because the company host runs its engine without a journal. Durable idempotency for polled jobs (a journal for the host's engine, or the platform's own lease) is deferred to the first workflow whose side effects make it necessary |
| Phase 7, slice 5 | Every failure the owner hit while setting up a host was at the seam between the software and the written instructions, and none of it could happen on a development machine: no Excel, a UTF-8 console, a token that already had the right scopes, a generated rather than hand-written configuration. The suite tests the code; nothing tests the operator's path. CI already installs the bundle, and should walk the documented steps instead of a script: hand-written configuration, membership and grants, exported assets, doctor, a preview against a scripted board, under a legacy code page |
| Phase 7, slice 5 | The Jira-era helpers in `capabilities.weekly_report.rules` are now read by nothing but their own tests: `issue_to_row`, `REPORT_FIELDS`, `default_jql`, `compose_jql`, `jql_updated_clause`, the two custom field numbers, `adf_to_text` and `comment_body_text`. Jira is switched off, so nothing will call them again, but removing a family of rules is its own reviewable change and not one made while the owner is waiting to test |
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
| 2026-10-01 | Shared Platform browser access is invitation-only and persists a revocable browser-login proof locally; short member sessions remain memory-only. The first bootstrap invitation creates a `platform_admin`, who can issue and revoke later invitations. |
| 2026-10-01 | Claude Code, Codex and Copilot are restricted local conversation backends, separate from `ModelCatalog`. They receive bounded text context in an isolated working directory and cannot return executable Agent tool calls; deterministic slash commands and Gateway tool calls remain under Bridge policy. |
| 2026-10-01 | A Skill may reference scripts for documentation, but execution requires a separately installed script-tool capability with an exact package-relative path, SHA-256, fixed Python/PowerShell host, JSON stdin/stdout and normal Bridge approval. |
| 2026-10-01 | Shared Platform member Add-on selections are durable authorization records in the same SQLite database as identity state. Select/revoke replaces one exact record, while version replacement commits the revoked and active records atomically; persistence still grants no execution permission by itself. |

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
# Productization 4 — Personal Agent Usability

- [x] Approve the incremental usability boundary: preserve the existing
  Agent/Gateway/Bridge contracts and make them visible and configurable before
  adding a bounded conversation/tool loop.
- [x] Define a closed model-settings request that accepts endpoint metadata,
  model id, routing alias and optional SecretRef/environment names, never a
  credential value.
- [x] Project actionable natural-language, shared-platform and installed-asset
  readiness through Personal Agent Web.
- [x] Derive clickable command hints from installed Skill manifests.
- [x] Add a local Settings page for the existing OpenAI-compatible Gateway,
  with full configuration validation, atomic save and restart semantics.
- [x] Add durable local conversation sessions and clarification UX, with
  host-owned identity, bounded message history, result status and trace evidence.
- [x] Add a provider-neutral bounded tool loop with installed-command aliases,
  OpenAI-compatible tool exchange, Bridge policy on every call, bounded context,
  durable Workflow evidence and typed stop reasons.
- [x] Add standardized feedback/candidate-asset creation from the conversation
  workspace without bypassing review or publication governance.
- [x] Repair the emitted Agent Web JavaScript startup failure and replace the
  diagnostic Installed/Shared Platform tables with an interactive capability
  workspace, searchable installed categories, truthful lifecycle state and a
  filtered shared catalog. Token bootstrap behavior remains unchanged.

# Windows delivery roles

- [x] Keep the company/test-computer artifact as the Personal Agent Web +
  Bridge execution role, with a bundled Traditional Chinese `START-HERE.md`.
- [x] Add an independent offline Shared Platform Windows artifact for the
  Registry, Member Marketplace and Bridge API control-plane role.
- [x] Make both installers expose only their own executable entry point and
  preserve separate versioned installation roots and configuration.
- [x] Install and smoke-test both artifacts in Windows/Python 3.12 CI; keep
  Hermes company-agent validation pinned to the Agent + Bridge artifact.
- [x] Put the exact Agent + Bridge artifact name, workflow-run link and bundled
  manual instruction in every automated deployment-validation Issue.

# Shared Platform identity and marketplace usability

- [x] Persist invitation-only users, roles, groups, invitation proofs and member sessions.
- [x] Make the first accepted bootstrap invitation recipient a platform administrator.
- [x] Add authenticated account and administrator invitation management to Marketplace.
- [x] Add backward-compatible asset categories and entitled category filtering.
- [x] Publish harmless test Skills, Workflows and one governed Bridge Extension.
- [x] Verify member Add-on selection/sync separately from administrator Extension staging.
- [x] Persist member Add-on selections and restore them across Shared Platform restarts.

# Agent persona, chat backends and capability authoring

- [x] Add local Agent name, introduction and bounded `soul.md` settings.
- [x] Add restricted local Claude Code, Codex and Copilot conversation backends.
- [x] Replace Ask hints with a deterministic slash-command palette and multiline input.
- [x] Add kind-specific Skill, Workflow, Knowledge, Extension and App detail sections.
- [x] Add governed Python/PowerShell script tool contracts and Bridge execution.
- [x] Move new Skill/Workflow draft creation into Capabilities and remove Improve.

# Productization 5 — Agent Web experience refinement

- [x] Remove Ask readiness cards and move backend selection into the composer footer.
- [x] Keep a configured Gateway selectable while showing credential readiness separately.
- [x] Add fixed, explicit Codex, Claude Code and Copilot authentication flows.
- [x] Replace top page tabs with New session, Capabilities and Settings sidebar actions.
- [x] Move searchable multi-session management into the left sidebar.
- [x] Refine Capabilities into installed list/detail panes with complete Skill Markdown.
- [x] Add Share Platform Skills, Workflows, Extensions and Apps library tabs and actions.
- [x] Verify the revised experience in the local preview and update handoff evidence.
- [x] Diagnose Gateway chat failure caused by a missing credential in the Agent
  process, show the mapped environment variable in failed turns, and verify a
  live `gpt-5.5` conversation after fixing the local preview launch.

# Multi-backend Agent Orchestrator and complete Workflow migration

- [x] Audit current Agent, Gateway, CLI backend, Harness, Knowledge, Workflow,
  Bridge and Marketplace boundaries against the proposed multi-backend target.
  Record source inventories, conflicts, baseline tests and an incremental
  sequence in `docs/MULTI_BACKEND_ORCHESTRATOR_PHASE0.md`.
- [x] Set the initial unclassified-data rule: use only a suitably approved
  internal Gateway; require explicit PUBLIC classification for Codex/Claude.
- [x] Review and approve the incremental backend/data-policy design before
  implementing the first contract slice (owner approval 2026-10-02).
- [x] Implement slice 1: exact backend profile/health/selection contracts,
  Gateway conversation adapter, equivalence and denial tests. Full local
  selection: 1,516 passed, 4 skipped, 2 environment-specific deselected;
  ruff, mypy and sdist/wheel build passed on 2026-10-02.
- [x] Implement slice 2 data trust: host-admin Gateway approval tied to the
  exact routed endpoint and allowed classes; treat full model requests as
  UNCLASSIFIED and block provider transport without approval. External CLI
  text chat requires a new explicitly PUBLIC session, complete-history label
  matching and no local persona or slash-command results. Full local selection:
  1,523 passed, 4 skipped, 2 environment-specific deselected; ruff, mypy,
  JavaScript syntax and sdist/wheel build passed on 2026-10-02.
- [x] Implement JEV-ready Phase 1A: a typed Decision Service around the
  existing rule-first/Gateway route, payload-free traces, local accelerator
  configuration defaulting to `NONE`, and negative tests for zero optional
  provider calls and pre-egress authorization. Keep the actual JEV adapter
  disabled until the benchmark and policy gates in
  `docs/MULTI_BACKEND_ORCHESTRATOR_JEV_PLAN.md` are met. Full local selection:
  1,548 passed, 4 skipped, 2 environment-specific deselected; ruff, mypy and
  sdist/wheel build passed on 2026-10-02.
- [x] Extend the same Decision Service to `Gateway.converse` Skill candidates:
  preserve the full installed catalog with `NONE`, reject invalid accelerated
  subsets, and remove omitted commands from both tool exposure and dispatch.
  A real JEV provider remains behind egress authorization and benchmarks.
  Full local selection: 1,550 passed, 4 skipped, 2 machine-specific
  deselected; ruff, mypy and offline sdist/wheel build passed on 2026-10-02.
- [x] Record the owner's explicit approval of this workstation's
  `company` Gateway at `http://127.0.0.1:4000/v1` for `UNCLASSIFIED` data in
  the installed preview `host.json`; provide an editable, secret-value-free
  `deploy/windows-preview/gateway-default.json`. Preserve approval when only
  the model ID changes and clear it when the route or credential changes.
  The local doctor parses the approval. A host-permission check confirmed
  LiteLLM listening on port 4000; live chat still needs `LITELLM_MASTER_KEY`
  in the Agent process environment.
- [x] Diagnose the Agent Web `{"detail":"Not Found"}` report: the browser had
  opened LiteLLM's `http://127.0.0.1:4000/v1` API root, not the Agent Web.
  Start a fresh Agent Web on a separate loopback port and verify its page and
  backend API return HTTP 200; use the temporary address printed at launch.
- [x] Add a backend-neutral Task contract, digest-only portable run state,
  additive SQLite persistence and independent artifact-byte validation with
  restart, transition and negative tests. This contract slice does not yet
  drive normal ingress or native Agent task execution.
- [x] Extend the portable contract with task type, initial classification,
  capability scope, execution constraints, normalized candidate backend
  results, backend use history and evidence-backed monotonic classification.
  Keep backend transitions disabled until re-authorization is implemented.
- [x] Add an executable explicit Gateway task path through `aep-host run-task`:
  enforce local admission, exact Gateway approval and installed read-only
  capability scope; persist bounded completed steps and issue codes; write a
  local answer artifact and validate its bytes before reporting success.
  Ordinary Web chat and Workflow routing remain unchanged in this slice.
  Full local selection: 1,560 passed, 4 skipped, 2 machine-specific
  deselected; ruff, mypy and offline sdist/wheel build passed on 2026-10-02.
- [ ] Complete portable state semantics for backend transitions: enumerate
  every transferable material and require a fresh full-context policy decision
  before changing backend. No transition or native task fallback is enabled.
- [ ] Attach portable task state and independent validation to ordinary Agent
  ingress, then add governed native task adapters with containment tests.
- [ ] Migrate source Workflow/job behavior with static and runtime parameter
  contracts, generated Web/Telegram forms, flexible `/run` aliases and parity.
- [x] Add optional typed Workflow runtime parameters to manifests, validate
  them against the exact installed Workflow on Agent Web launch, and render
  labeled Web controls for the three weekly-report Workflows. Older manifests
  retain the JSON editor. Static setting persistence, dynamic options and
  Telegram controls are still open under the parent task.
- [x] Add a manifest-declared numeric Workflow alias and deterministic Web
  parsing for `/run 11` and `/run workflow 11`. Workflow 11's alias selects
  only the read-only preview; missing/ambiguous aliases require an exact
  identity. CLI `ask` returns nonzero when the routed Workflow fails or is
  unavailable. Verification is recorded in `HANDOFF.md`.
- [x] Validate the installed Workflow 11 read-only preview on this Host. The
  owner updated the Windows user `AEP_GITHUB_TOKEN`; Project and Issue reads now
  succeed. The installed preview manifest lacked `run_alias: 11`, so the
  current shipped manifest was backed up and installed for that one Workflow.
  An explicit-week Web run and both bare `/run 11` / `/run workflow 11` runs
  returned `succeeded` with no refusal. No report write or mail action ran.
- [ ] Compare Workflow 11's live preview plan and workbook-read evidence with
  the source against a workbook copy. A successful run proves the installed
  route and read-only execution, not report parity. See
  `docs/VALIDATION_GAPS_2026-10-02.md`.
- [x] Resolve Workflow 11's Outlook draft authorization on this Host. After
  the owner asked to make the change, added exactly one persistent grant for
  `leo.chi` / `weekly-report/mail@1.0.0` / `outlook.draft` with
  `weekly-report-mail-policy`; preserved the other eight grants and backed up the
  original under `.scratch/workflow11-mail-grant-20261002/`. The installed
  `0.1.0` runtime was older than the installed manifest and rejected its
  `run_alias` and `parameters`; installed the current local wheel in the Host
  environment so all five Workflows load. One `weekly.mail 2026_40W` run
  succeeded in three steps. Outlook read-back found the item in Drafts, unsent,
  with empty To/CC. The Agent Web was restarted on port 53582 with `--open`;
  apply and mail remain separate Workflows.
- [x] Update Workflow 11's local Outlook recipients and SDE draft layout,
  plus Excel Status colours, Comments alignment and highlighted-Key whole-row
  sort. The Host configuration now holds 1 To and 8 CC addresses and the
  `SDE Weekly Report` prefix; no address is hardcoded in a shared asset.
  Focused tests passed (67 tests; one pre-existing machine-specific Excel
  absence test deselected). Excel COM moved the row in memory on a disposable
  copy, but this automation session's Excel opened files read-only, so saved
  workbook parity remains to be checked from the user's normal Host session.
- [x] Add a source migration parity contract to `docs/CONTRACTS.md`: pin each
  original Workflow/job revision or file digest, compare source-derived
  fixtures before adapting, and record every user-visible difference. Workflow
  11's local GitHub mail adapter is untracked in the pinned source checkout,
  so its digest and the owner's reference Outlook draft are identified as
  separate baseline evidence. Full visual mail and saved workbook parity are
  still open.
- [ ] Validate Knowledge query, convert, ingest and lint with a small
  independent local test Vault before using the owner-supplied OneDrive tree.
  The existing Host manifest points to a different proof Vault and has no
  binding. Keep this test Vault separate from the source tree.
- [x] Stage the synthetic fixture Vault in an isolated local Host workspace,
  verify exact manifest digests and clean static lint, and confirm Agent Web
  lists the bound Knowledge identity over loopback HTTP. Focused grounded
  asking/policy tests passed with a scripted model. The Codex process has no
  `LITELLM_MASTER_KEY`, so live Gateway asking and installed convert/ingest/lint
  remain open. See `docs/KNOWLEDGE_VALIDATION_2026-10-02.md`.
- [ ] Plan a provenance-preserving conversion of `RS_Knowledge` into a valid
  platform Vault, then stage a verified copy and exact manifest/binding.
  The source root lacks required index/log files; the owner will later specify
  which subset may be queried through the internal Gateway.
- [ ] Migrate source Workflow 7 (`jira_team_tickets`) using the same GitHub
  Project as Workflow 11, beginning with a read-only preview. Map GitHub
  identity, type/status, comments and fields to the source contract before
  touching Excel. Workflow 11 is the first live validation target; its
  Project read permission is being updated by the owner.
- [x] Characterize source Workflow 7's input schema, read/preview/write
  behavior, Excel invariants and source tests in
  `docs/WORKFLOW_7_SOURCE_CONTRACT.md`. Migration and parity against a workbook
  copy remain pending.
- [x] Add Workflow 7's first installed GitHub Project read-only preview with
  `/run 7` manifest alias, `tickets.preview` Skill route, source managed-column
  mapping, explicit missing-field/truncated-thread evidence and a denial-before-
  network test. Focused Project/Workflow tests: 39 passed; clean full
  repository selection: 1,567 passed, 4 skipped, 2 machine-specific
  deselected. The real Project run and all Excel parity remain open.
- [ ] Review and publish the active Hermes Skills and validated Workflows as
  governed default Marketplace assets.
- [ ] Prove SOP-to-Workflow, Knowledge and natural-language Skill integration
  through user-level tests and the required enrolled-Bridge evidence.
- [ ] Build a golden bounded-decision dataset and only then implement an
  optional JEV provider for decision types with proven latency/accuracy gain;
  keep data classification, authorization and strict validation deterministic.
- [x] Start the JEV-first validation track requested by the owner. Add a
  PUBLIC-only synthetic 16-case bounded-decision corpus, an offline NONE
  baseline and metrics runner; add an injected-transport TypeSafe SystemOne
  Skill-choice adapter with malformed/low-confidence/error fallback tests.
  The owner selected the official TypeSafe API and PUBLIC-only initial data.
  No live JEV request, Host wiring or private-data egress is enabled yet.
- [x] Add an explicitly invoked TypeSafe diagnostic for the pinned PUBLIC
  synthetic corpus. It verifies the exact reviewed digest before reading
  `AEP_JEV_API_KEY`, calls only the official SystemOne endpoint for four Skill
  cases, and reports baseline/JEV coverage, accuracy, fallback and latency
  without payloads or guessed cost. Offline fake-transport tests pass. The
  owner has now prioritized making RS Knowledge Ask work before comparing
  live JEV results, so no TypeSafe request was sent in this slice.
- [ ] Before enabling JEV in Agent Web, add exact TypeSafe endpoint approval,
  whole-request PUBLIC provenance for system/persona/history/installed Skill
  metadata, Host-owned credential mapping, circuit-breaker behavior and a
  representative repeated benchmark showing accuracy, latency, fallback and
  cost relative to the unchanged baseline. Keep ordinary UNCLASSIFIED Gateway
  conversations on the approved internal LiteLLM route.
- [ ] Add Agent scheduled jobs. Start with typed, durable, timezone-aware
  recurrence and a deterministic due-run claim; execute the exact installed
  Agent Task or Workflow through existing admission and Bridge grants, record
  outcomes, and provide create/pause/resume/history controls. The owner is
  choosing whether the first release schedules both Agent tasks and Workflows
  and whether the first control surface includes Agent Web; no scheduled
  action may bypass write, draft, send or other approval policy.
- [x] Add the inert local schedule foundation: exact-version Workflow/Agent Task
  contracts, timezone-aware daily/weekly recurrence, durable SQLite definitions
  and atomic due claims. Focused tests, schedule-file lint/typecheck and wheel
  build passed. A Host worker, claim reconciliation, admission/Bridge execution,
  and Agent Web/CLI controls remain open; no scheduled job runs yet.
- [x] Add an explicitly invoked Schedule worker with per-occurrence trusted
  execution authorization, Local Agent/Bridge policy checks, durable outcome
  recording and no automatic replay of uncertain claims. The worker supports
  exact installed Workflows and trusted exact Agent Task templates; 15 focused
  schedule tests, Ruff and mypy passed. It is not auto-started and no live
  schedule was created. Host lifecycle, policy configuration, CLI/Web controls
  and operator reconciliation of cross-restart uncertain claims remain open.
- [x] Correct Workflow 7's first preview source back to company Jira after the
  owner clarified that GitHub belongs only to Workflow 11. The source-based
  Jira read-only adapter and `/run 7` assets are committed. Previous GitHub
  Workflow 7 entries above are superseded, not evidence of live parity. The
  owner entered a new PAT; Jira `/rest/api/2/myself` returned HTTP 200, but
  `MRT1CV` returns 404 until the owner grants project Browse access.
- [x] Bind the owner-authorized *entire* `RS_Knowledge` query corpus to this
  Host from a short Windows path, with exact digests, engineering namespace
  Skill, permission and profile authorization. The source tree now has
  `index.md` and `log.md`; the old missing-root/subset entry above is
  superseded. Keep the source unchanged and state that the staging copy
  excludes Drop originals while preserving all Raw/Wiki queryable content.
  Installed Agent asking now answers a narrow CMX500 version question with a
  cited Raw file. Broad market mapping still needs retrieval/grounding quality
  work; do not claim unsupported conclusions.
- [x] Validate Workflow 11's corrected mail statistics against a real read:
  group by GitHub Issue Assignees, split comma-separated GitHub Project
  Production values into individual instruments, and show every instrument
  without an `Other` aggregate. A real Project read found five Issue-assigned
  items and one comma-separated Production value. The installed mail Workflow
  saved an unsent Outlook draft with 1 To, 8 CC, the expected subject, chart
  image and no `Other` aggregate; all nine resolved Exchange primary SMTP
  addresses matched the Workflow receipt. The installed Excel Workflow updated
  `2026_40W`: all 22 highlighted Key rows are contiguous at the top, their
  current-week Comments are red with older text black, all 19 highlighted
  `In Progress` cells have `#F8AD3E`, and all 241 Comments cells are aligned
  top-left. This workbook was backed up before applying. Older, untouched
  Status cells keep their hand-maintained fills by contract.
- [x] Fix Excel colour sorting when the workbook has manually hidden rows.
  Excel's ordinary colour sort skipped the hidden records; the adapter now
  carries a temporary row ID through the sort, restores each record's hidden
  state and retains its AutoFilter range. It refuses an active filter before
  mutation. A real Excel copy preserved the hidden-record multiset and filter
  range; the installed Workflow then passed saved-workbook validation.
- [ ] Complete Workflow 11 visual draft parity against the owner's reference
  Outlook draft, and evaluate whether duplicate test drafts created during
  diagnostics should be removed. Draft creation does not grant send permission.
- [x] Adapt Workflow 11's pinned source composite chart to the GitHub-backed
  weekly mail: one headless blue-family PNG now contains the instrument pie
  and stacked bars per Issue assignee. Keep all comma-split Production values,
  with no `Other` bucket. Map the Excel Assignee cell from the GitHub Issue's
  `assignees` connection, retain its Issue URL for the Key hyperlink, and
  package the optional plotting stack in the Windows offline preview. Synthetic
  source-shape and bundle regressions cover this slice; the open visual-draft
  task above still requires a real Outlook/source comparison.
- [ ] After the owner grants Browse permission to Jira `MRT1CV`, run Workflow
  7's exact read-only preview with the already valid User `AEP_JIRA_TOKEN`,
  compare it with the pinned source fixtures, then plan Excel parity.
- [ ] Improve broad, bilingual `RS_Knowledge` retrieval before claiming an
  answer to the owner's high-speed communications product/option question.
  The staged Raw corpus includes relevant product specifications and market
  notes, but the exact Chinese question's top lexical hits are mostly unrelated
  market/image paragraphs; a narrow English CMX500 question already answers
  with a Raw citation. Add a source-backed evaluation case that retrieves both
  market context and product/option evidence, without hardcoding R&S product
  names in the core ranker. Every final claim must retain Raw provenance, and
  insufficient evidence must remain an explicit result.
- [x] Add an opt-in bilingual evidence-coverage retrieval mode for broad
  high-speed communications market questions. Synthetic evaluation and a
  read-only diagnostic against the installed Vault retrieve Raw market
  context plus two distinct product/option specifications; narrow questions
  retain their previous ranking. The installed Host was updated and one live
  broad query succeeded with two Raw citations. An identical second query
  failed closed as `knowledge_not_grounded`, so stable synthesis and claim
  quality are still open. No product names are hardcoded in the ranker.
- [x] Add one bounded Raw-only synthesis retry for a first answer with invalid
  Wiki or per-sentence citations; the second prompt contains only the same
  Raw evidence, and another invalid answer still fails closed. Then narrow
  long retrieved Raw sections to local five-line excerpts for broad questions
  and reject an option code plus technical acronym unless one cited excerpt
  contains both. This reproduced and blocked the B81/high-speed-USB
  misattribution. After Host reinstall, the exact broad question succeeded
  twice without that B81 error; 19 focused tests, Ruff/mypy and the 1,622-test
  non-browser selection passed. The final option-code guard also recognizes
  letter-suffixed codes such as B200A; the full non-browser run preceded that
  narrow follow-up, whose focused regression passed. The pre-fix model output
  was not retained, so the exact citation defect behind its
  `knowledge_not_grounded` result is not known.
- [ ] Evaluate full semantic grounding and market-to-product/option coverage
  against source-backed cases. The local excerpt and lexical guard do not
  prove semantic entailment; a live post-fix answer still paraphrased one
  interface capability more broadly than the cited excerpt supports. Keep
  the broad mapping question open until claims and Raw citations are checked.
  The pinned three-source audit now verifies source bytes and retrieval, and
  flags a narrow unsupported product-to-800G/1.6T assertion. A live Agent Web
  answer cited the expected Raw sources but incorrectly joined them into
  market-fit claims; the diagnostic marked two assertions unsupported. The
  Query Engine now prompts for a clear distinction and retries/refuses that
  narrow cross-source claim. Its post-fix live behavior still needs checking
  after the running preview is refreshed; the standalone source-runtime
  process lacks the LiteLLM key.
- [x] Make explicitly named RS_Knowledge questions work in Agent Web Ask.
  An unambiguous installed Knowledge name such as `RS_Knowledge` now dispatches
  the original question to the exact Bridge Knowledge capability without a
  preliminary model tool-selection turn. The Ask reply names its cited Raw
  files, and a Bridge/model/grounding failure exposes a specific code. A
  case-insensitive acronym guard fixes one false rejection when Raw writes an
  interface such as `usb` and the model says `USB`. The owner's exact Chinese
  question succeeded through the source runtime and the reinstalled 53582 Web
  API with `knowledge-query/ask@1.0.0`, Raw references and no capability
  failure. The source excerpts support the named interface and option facts;
  any broader claim that the products satisfy a particular 800G/1.6T market
  requirement remains an inference, not established by these excerpts.
- [x] Add a source-backed evaluation before TypeSafe comparison. The pinned
  public RS_Knowledge Raw files and automated diagnostic distinguish named
  interface/RF capabilities from unverified 800G/1.6T market fit; see
  `evaluation/knowledge/README.md`. This is a review aid, not a general
  semantic entailment proof or a JEV Knowledge-answer path.
- [x] Prepare the owner's local Laya comparison in place of a live TypeSafe
  JEV test. `evaluation.laya_offline` maps all 16 pinned PUBLIC synthetic
  cases to Laya 0.3.24 typed choices, keeps the unchanged NONE baseline and
  records coverage, accuracy, confidence, latency, fallback, warm-up and
  checkpoint revision without prompt text. Its mapping tests pass without
  installing Laya. No TypeSafe request or Agent Web activation is involved.
- [ ] Run the pinned Laya checkpoint on a machine with sufficient free RAM,
  after prefetching it, and inspect repeated offline results. This Host had
  about 5.4 GiB free after the optional CPU environment was installed on
  2026-10-03, but company Zscaler denied the public Hugging Face checkpoint
  download with HTTP 403. No model-backed inference has run here; the offline
  CLI reports a missing cached checkpoint. Use a machine with enough free RAM
  and permitted model access. NONE still has 4/4 Skill coverage and 1/4 exact
  match; the other three baseline types remain unavailable.
- [x] Give each Host Knowledge Vault an owner-editable `privacy` setting:
  `private` by default or `public`. Record the owner's current RS_Knowledge
  selection as `public` in the installed Host config. Do not impose a separate
  classifier field or infer the privacy of another Vault from this one.
- [x] Pin original `rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43d`
  and migrate Workflow 10's typed local preview and staged temp-sheet apply.
  The Agent/Bridge route distinguishes `chipset-report.read` from an approved
  `excel.write`; preview returns source/drop/digest evidence, and apply refuses
  a stale target or open workbook and verifies the staged workbook before
  copyback. The source-diff baseline advances only after verified copyback.
  Synthetic workbook and fake-COM regression tests passed. See
  `docs/WORKFLOW_10_HOST.md` and `docs/CONTRACTS.md`.
- [ ] Validate Workflow 10 against the owner's actual FY source workbooks,
  mapping rules and an isolated copy of the real macro workbook. The source
  files and `chipset-map.json` were unavailable on this Host; Excel opened a
  synthetic workbook read-only in the sandbox, so a real COM write and
  source-vs-AEP workbook parity have not been proven. Do not apply to the
  production workbook on this evidence alone.
- [x] Pin Workflow 13's source contract and install a governed read-only local
  preview with alias `13`. It projects branch/version, release YAML, pinned
  requirements, selected-file digests and changed paths without running Git
  or changing the checkout. See `docs/WORKFLOW_13_SOURCE_CONTRACT.md`.
- [x] Add a separate, no-alias Workflow 13 isolated preparation Workflow.
  Explicit Host settings must name a marked allowed root and no-remote Git
  checkout. The Bridge requires both the exact write grant and an approval
  reference. Local preparation is locked and returns `committed=false` and
  `pushed=false`; Agent/Bridge tests cover missing grant, missing approval and
  approved preparation in a temporary checkout. It is not a production
  release path.
- [ ] Complete Workflow 13's governed release path: source-compatible version
  lookup, controlled upload transfer, branch/template handling, serialized
  checkout, Git status and distinct approved commit/push effects. Compare an
  isolated run with the original source job and collect company-host parity
  evidence before calling the migration complete.
- [ ] Apply the owner's corrected migration priority after the JEV gate: for
  remaining `rs_workflow_system` jobs, assess direct reuse or a thin Bridge
  wrapper around the pinned Python/PowerShell implementation before porting
  business logic. Map its existing parameters to AEP forms. n8n development
  is outside the current scope and is not a required task.
  Treat an exact, durable Host grant for owner-approved local Excel writes or
  unsent Outlook drafts as sufficient for that effect, without repeated human
  approval prompts. Do not conflate a saved draft with sending mail. Record
  concrete incompatibilities before a rewrite; keep remote release/push behind
  their separate authorization.
- [ ] Pause Workflow 7 at the owner's request. `AEP_JIRA_TOKEN` is set and
  Jira identity returned HTTP 200; the separate `MRT1CV` Project returned
  HTTP 404. Do not replace its Jira source or continue its migration until
  the owner reopens the task and Project Browse access is confirmed.
- [x] Add manual `aep-host schedules` create/list/pause/resume/history
  controls over the durable schedule store. The CLI does not auto-start the
  worker or grant scheduled execution. Agent Task creation requires a trusted
  template and remains refused until that configuration is wired.
- [x] Stage one private default-Marketplace candidate for the installed
  Workflow 11 preview. This is a draft, not published or installed; no Hermes
  Skill is repackaged without an exact source pin and licensing review.
- [x] Verify the Workflow 10/13 local slices: focused migration, schedule and
  Marketplace selection passed; strict mypy checked 325 files; Ruff and an
  offline wheel build passed. The non-browser repository selection passed
  1,690 tests with five platform skips and one real-browser deselection when
  run outside Windows filesystem sandbox interference. Chromium/CDP remains
  unavailable on this host; real-file Workflow 10/13 parity is still open.

- [x] Add the first product/market Knowledge evidence matrix for five R&S
  product families and five target markets. A read-only Bridge capability scans
  exact installed Raw passages once and returns 25 typed cells, with evidence
  level, source/section, excerpt and next knowledge gaps. The new Skill and
  Agent Web natural-language route use this capability; neither claims market
  fit from lexical co-mentions. The owner's staged RS_Knowledge scan produced
  15 nearby mentions and 10 separate-passage leads in about nine seconds;
  these counts are retrieval leads, not validated suitability. Focused tests
  cover output ordering, evidence level, no-fit invariant, exact grant and Web
  route. Full verification and installed-host activation are recorded in
  `HANDOFF.md`.
- [ ] For each chosen product/market cell, confirm the application and market
  standard, product/option specifications, and customer evidence, then use
  grounded Knowledge Ask to produce a reviewed strategy recommendation.
- [ ] Close the general Knowledge harness gaps documented in
  `docs/HARNESS_6_LAYER_STATUS.md`: define an explicit evidence-sufficiency
  result, bounded re-retrieval policy and independent final-claim validation
  for one selected cell before generalizing task/domain routing policy.
- [x] H1: record an exact selected matrix cell's evidence-sufficiency result.
  Its three missing facets are machine-readable (market requirements,
  product/options, customer use case); nearby mentions and separate Raw
  passages remain `needs_evidence`. Agent Web shows the unresolved 25-cell
  count. Focused tests, Ruff and touched-source mypy passed; full verification
  awaits the owner's merge checkpoint.
- [x] G1: introduce a common provider-neutral harness plan envelope and
  optional Skill guidance across Knowledge, Workflow/Task and Coding. Three
  versioned test Skills cover the domains. Planning preserves TaskContract
  capability scope and Host checks; a Skill cannot add grants or retry beyond
  the Host budget. Focused five-case contract tests, Ruff and touched-source
  mypy passed. This is a planning contract, not live execution yet.
- [x] G2 contract/state slice: add a serializable shared run state with
  ordered payload-free observations, bounded retry, `needs_input`/failure and
  completion only after every Host check is reported. Ten focused plan/run
  tests passed, including a negative path for each domain. This is still a
  pure state machine; live adapters and independent validator wiring are G3/G4.
- [x] G2 execution slice: add one provider-neutral runner for Knowledge,
  Workflow/Task and Coding actions. It records context/execution evidence
  references, delegates execution and Host checks to the supplied adapter,
  and enforces the shared retry/stop state machine. Fifteen focused tests,
  Ruff and touched-source mypy passed. Live domain adapters remain G3/G4.
- [ ] G3: use the candidate Knowledge Asking Skill to test data coverage,
  retrieval, answer validation and gap feedback in Agent Web. Keep the
  published 1.0.0 Skill immutable; activate a new version only after review.
- [x] G3 first vertical path: Agent Web can explicitly select an installed,
  versioned Knowledge Asking Skill. Its exact Bridge query now runs through
  the shared plan/runner, reports the Skill, phase, attempts and Raw citation
  count, and preserves Bridge permission denial. The Host revalidates the
  grounded record; uninstalled Skills cannot run. Facet coverage is explicitly
  `not_assessed` until evidence-sufficiency and bounded re-retrieval are wired.
  Focused Knowledge Web tests (16), shared harness tests (15), Ruff and
  touched-source mypy passed; full suite remains at the owner's merge checkpoint.
- [x] Install the validated private G3 candidate into the owner's local Host
  Skill directory without publishing it. A `build_runtime`/Agent Web assets
  smoke check found it selectable. The prior Web port had no listener; live
  model testing still needs a process started from the owner's credentialed
  shell and the remaining evidence-sufficiency checks.
- [x] Make natural Knowledge chat use the one installed, selectable Knowledge
  Asking Skill when a question names the installed asset. Keep exact Bridge
  authorization, expose shared harness/evidence status, and retain the legacy
  route when zero or multiple eligible Skills exist. Fix lexical retrieval of
  explicitly named Raw files and Chinese product-test questions over English
  Raw sources. The owner's live Agent Web on port 53583 answered both a named
  CMX500 file question (one Raw citation) and a general CMX500 test question
  (four Raw citations), each with `harness.phase=validated`. Focused tests:
  33 passed. Final checks: repository Ruff and mypy passed, wheel/sdist build
  passed, and the full suite had 1,791 passed, 5 skipped, one Windows directory
  replacement failure that passed on isolated retry. A separate type-only test
  annotation correction made the repository-wide mypy check pass. This verifies
  Raw citations, not semantic entailment or strategy facet sufficiency.
- [x] Prepare G3 evaluation inputs at two levels: three standalone questions
  (market trends, product options/specs, technical knowledge) and combined
  market/product comparison plus competitive strategy with SWOT and project
  actions. The typed suite rejects a strategy case missing competitor or other
  required facets and requires Raw citations or an explicit gap. Two focused
  contract tests, Ruff and mypy passed. No live model result is claimed yet.
- [x] Diagnose the earlier G3 combined-case acceptance failures: the two existing combined scenarios were
  run through the live Agent Web on 2026-10-04. `market-product-wireless-cmp180`
  stopped at routing (`needs_input`) because it does not name the Knowledge
  asset; prepending `RS_Knowledge` reached the harness but still returned
  `knowledge_insufficient_evidence`. `full-competitive-strategy-wireless`
  reached the harness and returned the same evidence stop. Its top eight
  retrieved passages included CMP180 product/option and nearby market notes,
  but no verified competitor comparison. Both returned zero accepted Raw
  citations and `facet_status=not_assessed`; a multi-source strategy/SWOT has
  not been validated. Next: Skill-guided intent/asset selection, facet-specific
  retrieval, explicit missing-facet feedback and bounded re-retrieval before
  allowing a strategy result.
- [x] Diagnose G3 combined-case failures before changing runtime behavior.
  The unnamed market/product case misses Knowledge routing; named cases enter
  the harness but receive a single whole-question `k=8` retrieval, zero
  permitted harness retries and only Raw-citation/nonempty Host checks. The
  installed candidate Skill's prose is not an executable retrieval plan;
  `facet_status` remains `not_assessed`. CMP180 source material and some
  CMX500 competitor battle cards exist, but direct CMP180 competitive fit is
  unverified. See the causal analysis in
  `docs/phases/HARNESS_6_LAYER_INCREMENTAL.md`. This identifies process wiring
  as primary, Skill contract as secondary and data coverage as still open.
- [x] G3 guided-evidence slice: a private Skill 1.2.0 supplies typed natural
  intent, per-facet searches and direct-link guidance. Exact commands retain
  precedence. The Knowledge adapter retries only missing facets; independent
  Host checks require cited Raw for requested facets, direct relationships for
  combinations and basic claim/source overlap. Shared harness plan and runner
  remain domain-neutral. Focused Knowledge/Web tests: 143 passed; Ruff and
  mypy passed. The non-browser repository suite passed under short system Temp
  (1,837 passed, 5 skipped); wheel and source package builds passed.
- [x] G3 exhaustive controlled combinations: evaluate all 15 nonempty subsets
  of market, product/option/spec, technical and competitor facets using
  supported, missing and misleading co-mention cases. The read-only live
  RS_Knowledge retrieval probe found facet candidate passages for all 15, but
  direct connected links for 5/15 selected questions. This is retrieval
  evidence, not a claim that the other facts are absent from the Vault.
- [ ] G3 owner Agent Web acceptance: install the private Skill 1.2.0 into the
  preview Host, restart the Web process and let the owner ask representative
  standalone and combined questions. Review cited answer quality and refine
  Skill search guidance or data coverage based on observed failure layer. The
  install/restart and two local Web smoke turns are complete: a CMP180 product
  question validated with cited support, while a market-plus-CMP180 question
  stopped at `needs_input` with missing facet/direct-link evidence. Owner
  answer-quality acceptance is still pending.
- [x] Rename Knowledge evaluation-only schema, cases and test to `scenario`
  names so they cannot be mistaken for a separate Knowledge harness. Shared
  runtime contracts remain under `src/agent`; the candidate Skill remains
  separate from the published version.
- [ ] G4–G6: adapt exact Workflow/Task and Coding runs to the same state and
  validation envelope, then prove all three from Agent Web. Order and
  acceptance are in `docs/phases/HARNESS_6_LAYER_INCREMENTAL.md`.
- [x] Convert an invalid configured Knowledge Vault into a Host startup error
  that names the configured Vault path instead of leaking a `VaultError`
  traceback. The owner's preview binding currently points to an existing Vault;
  the same `host.json` passes the local Host startup/status check. If startup
  fails again, inspect the exact path in the new error rather than assuming the
  original RS_Knowledge directory was modified.
- [x] Replace the stale portable Agent Web process on port 53582 with the
  current project runtime and verify the live page plus 25-cell Knowledge
  matrix through authenticated HTTP. The exact intermittent cause of the
  owner's earlier Knowledge catalog startup refusal remains unproven; the
  current Vault, manifest digests and Host configuration now validate.
- [x] Render Markdown in Ask replies and saved-session history as readable
  headings, lists, code and horizontally scrollable tables. Keep API messages
  as text and build only allowed DOM nodes; unsafe links and raw HTML remain
  inert text. Focused browser-script and DOM safety tests passed, and a local
  Edge screenshot was visually inspected. Full repository verification remains
  deferred to the owner's merge checkpoint.
- [ ] G3 Wiki-first Knowledge candidate 1.3.0: source Vault schema and
  `ask-market` / `ask-competitor` Skills were reviewed. An opt-in index-to-Wiki-
  to-Raw navigator and Skill answer guidance are implemented locally with
  focused tests; the live Web remains on rollback Skill 1.1.0. Isolated tests
  of the owner's three questions found: CMP180/market has partial Raw but no
  proven option-to-trend link; NTN validates CMX500 but the answer copies PR
  marketing and omits other candidate products; CMP180/competitor has only a
  CMX500 battle-card co-mention. Finish source-aware partial answering,
  market/source-date and competitor comparability checks, then rerun the three
  questions before installing the candidate in Agent Web.
- [ ] G3 Hermes reference comparison and acceptance: the owner's Downloads
  `rs-knowledge-base_SKILL.md` and `html-report-delivery_SKILL.md` match the
  local Hermes versions exactly. The former requires index-first navigation,
  bilingual Wiki/Raw search and separate market, technical and product/option
  evidence; the latter is only for HTML artifact delivery. Candidate 1.3.0
  now finds CMP180 market and option Raw that previously fell below top-k,
  retains the NTN signal-generator source as well as CMX500, bounds long Raw
  sections before Gateway synthesis, retries one empty model response, and
  can preserve individually cited claims. Focused Query/Knowledge tests:
  92 passed; guided Agent Web tests: 4 passed; Ruff and mypy passed.
  **Acceptance remains open:** a live NTN answer still got `validated` despite
  recommending a product only because NTN appears as a target market and
  including a citation-only line and clipped phrase. Strengthen semantic
  recommendation/source-role checks, make partial answers readable, and rerun
  all three owner questions before installing 1.3.0 in Agent Web.
- [ ] G3 candidate 1.3.0 live quality checkpoint after Hermes Skill review:
  the three owner questions now run in an isolated Host with the real Vault and
  Gateway. CMP180/market returns cited market and option facts while retaining
  `needs_input` for the absent direct link; however the chosen 5G market trend
  is not yet well matched to the cited WLAN/other CMP180 options. NTN rejects
  an OSP/NTN reseller target-market co-mention and validates only the narrower
  supported CMX500/related test use cases; it still misses other instrument
  roles such as signal generation. CMP180/competitor returns cited option and
  RF-test facts with explicit competitor/direct-link gaps. Fix iterative
  product-to-market retrieval, source-role breadth, and answer quality before
  installing this candidate in Agent Web. A credential-like example in Raw is
  now redacted before answer recording; `Rel. 17` stays intact in citation
  parsing. Local Query/Knowledge/Agent Web tests: 175 passed, 2 deselected;
  Ruff and mypy were run on changed modules. Full merge verification remains
  pending.
  A follow-up NTN query expansion trial found the signal-generator slide in
  Raw but still failed to surface the independent NTN whitepaper in the final
  product evidence set because several CMX500 sources filled the bounded
  slots. That query-only trial was reverted. The next slice should diversify
  product source roles and prioritize direct technical documents over repeated
  promotional sources, with a real-Vault acceptance check before deployment.
  A source/family diversity implementation now brings the NTN whitepaper into
  the real-Vault evidence set while retaining CMX500 sources. Its isolated
  live answer still fell back to one CMX500 sentence, so the remaining work is
  source-section selection and multi-role answer synthesis/validation, not
  another expansion of keyword lists. Re-run the three owner questions after
  that change; candidate 1.3.0 remains uninstalled.
  Handoff checkpoint on 2026-10-04: diagnosed the single-sentence fallback as
  a successful Gateway response with empty visible text at the candidate's
  800-token synthesis cap. Candidate 1.3.0 now declares 3072 tokens through a
  Skill procedure field; a real isolated NTN probe produced a Chinese,
  multi-item, Raw-cited answer. Source-aware recommendations now accept a
  nearby context sentence (PVT360) while still rejecting a reseller-only NTN
  market list. The most recent isolated three-question run validated NTN, but
  CMP180/market and CMP180/competitor remain `needs_input` and their partial
  answer text is clipped or incomplete. A latest adjacent-Raw-section context
  edit passed focused tests but has not had a real-Vault/Gateway rerun. Claude
  Code handoff and exact next action are in `HANDOFF.md`; Skill 1.3.0 remains
  uncommitted, uninstalled and unreleased.
- [x] G3 candidate 1.3.0 answer-salvage and retrieval fixes (Claude Code,
  2026-10-04): real-Vault/Gateway reruns of the three owner questions traced
  the remaining loss of supported facts to process defects, not Vault gaps.
  (1) Sentence splitting treated list markers (`1.`) and a second citation
  group (`。[5][7]`) as uncited sentences, failing whole drafts. (2) A failed
  first draft was discarded and a thinner retry kept; the adapter now keeps
  the draft with more Raw-grounded sentences. (3) The NTN recommendation
  check split PDF hard-wrapped lines and missed nearby NTN context (PVT360);
  it now unwraps lines and treats a Raw file named for the focus (NTN
  whitepaper) as focused context, still rejecting the reseller list. (4) The
  handler and Host required the literal subject (`CMP180`) in answer text;
  a claim cited from the subject's own Raw document now counts. (5) Number
  checks hid digits next to CJK text (`2026年`). (6) Skill 1.3.0
  `market_trend` stopped at its first weak hit; it now pools all queries
  with a Chinese query and terms, surfacing the 2026 Taiwan wireless market
  report. Live results: CMP180/market `needs_input` with Wi-Fi 7/320 MHz
  market facts and KM351/KM352/KM280 option facts (direct link unverified);
  NTN `validated` with CMX500, options, PVT360, ZNA/ATS1800C, TS-LBS and
  signal-generator roles; CMP180/competitor `needs_input` with cited option
  facts and a genuine competitor data gap. Full pytest: 1887 passed, 5
  skipped, 2 failed (Windows-flaky `test_extension_runtime` file lock and
  pre-existing `test_local_developer_environment` cp950 decoding failure,
  which also fails at HEAD). Ruff and mypy passed. Candidate not yet
  installed in the live Agent Web.
- [ ] Scheduled tasks (定期任務) without n8n: owner decided on 2026-10-04 not
  to use n8n. Existing `common.scheduling`, `SqliteScheduleStore`,
  schedule worker and `aep-host schedules` CLI need a per-schedule execution
  grant, a CLI tick plus optional Host-resident loop, stuck-claim resolution
  and Agent Web API/panel. Owner decisions still open: Workflows only or also
  Agent Tasks; CLI first or Agent Web in v1; resident loop, Windows Task
  Scheduler or both; which effect classes may run unattended; skip or catch
  up missed runs.
- [x] G3 labeled Knowledge inference (Claude Code, 2026-10-04, owner
  requested explicit labels): Knowledge procedure field `inference_label`
  (opt-in; candidate 1.3.0 uses `【推論】`). Labeled lines may connect
  separately cited Raw facts, at most three, only beside a supported fact;
  every product/option code and number must appear in the cited premises and
  each cited premise must share wording with the line. Facet and
  `direct_relationship` status are unchanged by inferences. Live isolated
  probe: CMP180/market kept one grounded inference (Wi-Fi 7/802.11be ↔
  CMP-KM352) and dropped two that introduced an unseen number or an
  unrelated premise. Candidate 1.3.0 is now installed in the live Agent Web
  (1.1.0 moved to `assets/skills/disabled/` for rollback). Full pytest: 1890
  passed, 5 skipped, 2 known environmental failures; Ruff and mypy passed.
- [x] G3 Wiki-primary Knowledge citation and report answers (Claude Code,
  2026-10-05, owner decision recorded in `docs/DECISIONS.md`; E2E-05
  criterion 1 amended). `citation_policy: wiki_primary` lets a Skill cite
  curated Wiki sections (chunked by heading, tables intact) with each cited
  page's Raw provenance; 2004/2007 real Wiki pages trace to Raw, untraceable
  pages are cited and labeled 缺來源連結. Answers may be Markdown reports:
  headings and table header/divider rows are structure, each table row is a
  claim whose codes must appear in its cited sources, and filters keep the
  structure. Candidate Skill 1.4.0 (wiki_primary, 高速通訊 focus expansions,
  report guidance, 8192-token budget) is installed in the live Agent Web
  (1.3.0 moved to `disabled/`). Live probes: high-speed communications
  mapping `validated` as a report (CMX500, ZNB/ZNA, FSWP50, SMW200A, FSWX
  options, scenarios, limits); NTN `validated` report; CMP180/market and
  CMP180/competitor `needs_input` with cited partial facts. Full pytest:
  1907 passed, 5 skipped, 1 known pre-existing failure; Ruff and mypy passed.
- [x] Scheduled tasks v1 on branch `schedules-v1` (owner decisions of
  2026-10-04; see `docs/DECISIONS.md` and `docs/CONTRACTS.md` "Scheduled
  tasks v1"). Host-owned `ScheduleExecutionGrant` and per-occurrence
  `ScheduleGrantAuthorizer`: `read` unattended with a grant, `write`/`execute`
  also need the Bridge grant, `external_side_effect` always waits for per-run
  approve/deny. Store schema v2 (grants, operator decisions, v1 migration),
  catch-up of only the latest missed run within `schedules.catch_up_hours`,
  stuck-claim resolution. Agent Task targets from `assets/agent-tasks/`
  through `LocalAgent.run_task`. CLI `schedules tick|grant|revoke|pending|
  approve|deny|resolve|run`; opt-in resident loop in `aep-host web
  --schedules` / `schedules.resident_loop`; Agent Web `/api/schedules*` routes
  and Schedules panel; `deploy/windows-preview/schedule-tick.ps1`. Ruff and
  `mypy src` passed. Full pytest: 1917 passed, 5 skipped, 6 failed; the same
  6 (`test_default_marketplace_candidates` snapshot, `test_jev_live` x2,
  `test_laya_offline` x3) also fail at base commit `dcf2122` in the same
  checkout. Not merged to `main`; no live schedule created. Open: Registry
  asset kind and runtime parameters for Agent Tasks; doctor reporting of
  schedules; live Windows Task Scheduler check.
- [x] Agent Web grouped conversation turns (Claude Code, 2026-10-05, owner
  request): each question and answer render as one card; hovering shows
  thumbs up / thumbs down / normal (neutral) and reply; a rating opens an
  optional reason note stored as `MessageFeedback` on that answer through
  `/api/conversations/feedback` (an annotation that keeps the transcript
  append-only); right-click offers reply, copy and rating. Reply sends
  `reply_to`, keeping the chosen exchange directly before the new question in
  model history and attaching the original question to Knowledge routing.
  Tests: contract, history placement, feedback persistence, authenticated
  endpoint, page safety (Node harness); browser screenshots inspected.
- [x] Agent Web concurrent sessions (Claude Code, 2026-10-05, owner request;
  decision recorded): per-session turn queue and record lock, exclusive lock
  only for commands/settings/sync/profile/schedules, `BridgeExecutor.exclusive`
  around workflow runs and non-read capabilities. The page keeps the input
  usable, shows queued/running turns, marks busy sessions in the sidebar and
  switches session immediately. Also: confirmed per-session delete, backend
  selector sync fix, and a Gateway model picker in Settings. Concurrency
  tests cover parallel sessions, in-session order, rating during a turn and
  Bridge effect serialization; browser check inspected. Full pytest: 1955
  passed, 5 skipped; remaining failures are the known intermittent
  `test_knowledge_stage` and pre-existing cp950 `test_local_developer_environment`.
- [ ] rs_workflow_system full migration with one parameter declaration
  (owner request 2026-10-05): inventory, gap analysis, contract extension,
  generators (Agent Web, schedule, Telegram, Agent tool schema, settings),
  slice order and owner decisions are in
  `docs/phases/RS_WORKFLOW_MIGRATION.md`. Awaiting owner decisions before S1.
- [x] rs_workflow_system migration S1, parameter declaration contract
  (Claude Code, 2026-10-05): optional `WorkflowParameter` fields and kinds,
  `progress_steps`, `occupies_machine`, cross-field order/needs/placeholder
  validation, defaults applied by `validate_run_parameters`; unused new
  fields serialize as before so published manifest bytes are unchanged.
  Owner decisions recorded in `docs/DECISIONS.md`. Full pytest: 1977 passed,
  5 skipped, 1 known pre-existing failure. Next: S2 generated forms.
- [x] rs_workflow_system migration S2, generated forms (Claude Code,
  2026-10-05): `common.workflow_forms.form_fields(manifest, channel)` orders
  runtime fields (identity group first, then `order`), filters by channel and
  normalizes choices/help/defaults; Agent Web's run form and the schedule
  form now share one renderer (`renderParameterForm` / `collectParameterValues`)
  covering every kind, defaults, labelled choices, confirmation of privileged
  fields and inline validation. Dynamic `ref:`/`fn:` choices render as text
  until S6. Browser DOM check confirmed rendering, pattern refusal and value
  collection. Next: S3 Agent tool schema.
- [x] rs_workflow_system migration S3, Agent tool schema (Claude Code,
  2026-10-05): `agent_tool_schema(manifest)` builds a closed JSON Schema from
  the declaration (agent-channel runtime fields only; privileged `confirm`,
  internal, static and secret fields are never offered). `ModelTool` carries
  an optional provider-neutral `input_schema`; declared Workflow tools use it,
  undeclared tools keep the generic object. Tool calls are refused before
  execution if they set a non-offered field or fail `validate_run_parameters`
  (defaults applied otherwise). Next: S4 Telegram question flow.
- [x] rs_workflow_system migration S4, Telegram question flow (Claude Code,
  2026-10-05): `/run <number or name>` asks a Workflow's telegram-channel
  fields one at a time (`channels.telegram_flow`, generated from the
  declaration): inline keyboards for choices and yes/no, comma/new-line lists,
  `/skip` only for optional fields, `/cancel`, defaults shown, shared field
  validation. A run that can change or send something, or a privileged field
  that was set, waits for a Run tap (owner decision 1). Button taps arrive as
  callback queries and are acknowledged. Execution uses
  `LocalAgent.execute_workflow` with `LocalWorkflowRequest` now accepting the
  `telegram` ingress and `on_behalf_of` (granting nothing). Required uploads
  are refused on Telegram (attachments excluded); flow state is in memory with
  a 15-minute expiry. Next: S5 workflow_settings store and editor.
- [x] rs_workflow_system migration S5, per-install Workflow settings
  (Claude Code, 2026-10-05, owner clarified the two parameter kinds:
  pre-run settings that adapt a Workflow to a person's computer vs run-time
  parameters asked every run). `scope: static` fields are stored per install in
  `<workspace>/workflow-settings.json` keyed by `namespace/name` (kept across
  upgrades, credential-like values refused), edited on Agent Web's Settings
  page from the declaration, and merged by `WorkflowEngine` into every run
  from every channel; a missing required setting stops the run with
  `workflow_settings_incomplete`, and a run can never supply a setting. Not
  yet done: moving existing `HostIntegrations` settings (W13 first, then
  W07/W10/W11 in their own slices). Next: S6 dynamic choices.
- [x] Workflow 13 settings moved to per-install Workflow settings (Claude
  Code, 2026-10-05). Fixes a regression S5 introduced: W13 declared
  `checkout_path` / `inbox_path` / `allowed_root` as required static fields, so
  the engine refused it with `workflow_settings_incomplete` while the values
  still lived in `HostIntegrations` (S5 was committed after a subset run that
  missed `test_release_package.py`). W13 steps now select those settings from
  the run by path and the handlers build their settings per run;
  `ReleasePreviewRequest` ignores non-run fields. Old host.json
  `release_package` / `isolated_release_apply` values are fallback settings
  (settings-page values win). W13 capabilities register when an installed
  Workflow uses them or the old host.json still configures them, so an
  unrelated host does not advertise them. A real-browser schedule test now
  waits for the panel's asynchronous target list. Full pytest: 1998 passed;
  remaining failures were known intermittent/pre-existing and passed on rerun
  except the cp950 test.
- [x] rs_workflow_system migration S6a, dynamic `ref:` choices (Claude Code,
  2026-10-05): published sets in `<workspace>/reference-sets.sqlite`
  (owner decision 3) with tag filters waiting for earlier answers; engine
  rejects unpublished sets (`reference_set_unavailable`) and stale values
  (`workflow_choice_unavailable`); Agent Web dropdowns via
  `/api/workflow-options`; Telegram buttons. Publishing from a Workflow run
  (`publishes`) comes with the Workflow 12 slice; `fn:` with the first slice
  that needs it.
- [x] Workflow 90 bundle_smoke migrated (WRAP, Claude Code, 2026-10-05):
  `packages/rs-workflow-system/w90-bundle-smoke/` carries the pinned job
  byte-identical (hash-verified by `run.py`) as a governed script tool, with a
  generated Workflow manifest (`/run 90`, `greeting`, `fail`) and skill. The
  script-tool manifest is a candidate awaiting owner publication/approval.
  Parity tests run the pinned job through Bridge policy in a real host.
  Ruff excludes vendored source directories.
- [x] rs_workflow_system migration S6c: `fn:` choice functions
  (`host_runtime/choice_sources.py`). A read-only host function receives the
  Workflow's per-install settings and bound `{field}` arguments; one resolver
  serves engine validation (`choice_function_unavailable`), Agent Web
  `/api/workflow-options` and Telegram buttons. Tests:
  `tests/test_choice_functions.py`.
- [x] Building block `outlook.draft` (`capabilities/mail_draft`): a governed
  write that saves one Outlook draft with optional file attachments, `skip`
  and `best_effort`, and has no send. `MailDraft` gained `attachments`.
  Tests: `tests/test_mail_draft_capability.py`, `tests/test_outlook_draft.py`.
- [x] rs_workflow_system Workflow 14 (ncc_improvement_plan), ADAPT:
  `capabilities/ncc_plan` (`prepare` read / `render` write) plus
  `outlook.draft`, `/run 14`, station menu `fn:ncc_plan.stations`, settings
  for catalogue/template/output/photos. Source rules carried with the
  source's 51 rule tests as oracle; local parity test gives the same document
  text as the source job on the real template. Not carried yet: source
  document re-import and hidden overrides (see `capabilities/ncc_plan/SOURCE.md`).
- [x] Agent Web settings (owner request 2026-10-05): Telegram bot section
  (token to the Windows user environment only, allowed senders, on/off; Agent
  Web polls Telegram itself and swaps the loop on save) and Capabilities
  "Recent runs" moved to a collapsed section at the bottom. Tests:
  `tests/test_telegram_settings.py`.
- [x] Workflow 11 merged into one Workflow `engineering/gtm-weekly-report`
  (`/run 11`, owner request 2026-10-05): GitHub board -> plan -> workbook ->
  mail draft, `dry_run` (default off) and `draft_mail` (default on), precise
  `start_time`/`end_time`; board selection aligned with source
  `github_weekly_report.py` (GTM keys only, closed skipped, comment edit time,
  migrated body log fallback, moment window). Tests:
  `tests/test_weekly_github_source_rules.py`, `tests/test_weekly_report_workflow.py`.
- [x] Workflow 11 renamed `engineering/gtm-weekly-report` ->
  `engineering/sde-weekly-report` (owner request 2026-10-05); same steps and
  parameters, `/run 11` unchanged.
- [x] JEV benchmark `--endpoint` for a tunnelled self-hosted SystemOne
  (Laya, 2026-10-05); first live run and findings recorded in
  `docs/JEV_ADAPTER_READINESS.md` (state shape, threshold not applied in the
  benchmark, latency above 300 ms default, corpus too small).
- [x] JEV adapter sends only the latest user message as `state`; the
  benchmark applies the confidence threshold (`--threshold`) and scores the
  live route with fallback; Laya results at 0.9 and 0.3 in
  `docs/JEV_ADAPTER_READINESS.md`.
- [x] Skill `selector_hint` (owner approval 2026-10-05): manifest field,
  Gateway `selector_hints`, JEV adapter uses hints and strips the shared
  suffix, concrete preserve option; hints on weekly, NCC, team-tickets 2.1.0
  and company-agent Skills 1.1.0 (installed live, old versions in
  `skills\disabled\`); corpus `skills-v3` (46 cases). Laya at 0.5: 63 % with
  fallback (baseline 22 %), 91 % of admitted choices correct. Tests:
  `tests/test_skill_selector_hints.py`.
- [x] JEV shadow mode (2026-10-05): `decision_accelerator.mode=shadow`,
  `skill_max_tools`, `egress_approval`; Host wiring sends nothing without the
  approval; background shadow decisions logged to `workspace/jev-shadow.jsonl`
  with the model's tool calls (no text); replay with
  `python -m evaluation.jev_shadow_report`. Adapter keeps the most likely
  tools when `skill_max_tools > 1`. Not enabled live until the owner records
  an approval. Tests: `tests/test_jev_shadow.py`.
- [x] Telegram settings keep a token and senders saved while the bot is off
  (owner report 2026-10-05: saving unticked discarded input and blanked the
  form); first-time form starts ticked. JEV shadow mode enabled live (owner
  approval `owner-approved-2026-10-05-laya-shadow`, `skill_max_tools` 3,
  timeout 1500 ms); shadow outcome `kept_catalog` named. GitLab credential
  mapping `gitlab_token -> AEP_GITLAB_TOKEN` added and the token verified.
- [x] Telegram free text talks to the Agent (owner report 2026-10-05: "hi"
  answered `model_unavailable`): JSON mode names "json" in the request
  (vLLM 400), a null route is `no_matching_route`, and free text goes to
  `LocalAgent.converse` with 12 turns kept in memory; `/new` clears them.
  Commits `f30ec7f`, `bb711ee`, `a4051e0`.
- [x] A Workflow's settings are shown with that Workflow under Capabilities
  and no longer on the Settings page (owner request 2026-10-06). Commit
  `cf6ee1b`; checked live in a browser.
- [x] Telegram shows a "working on it" message, edited in place with elapsed
  time and each skill as it runs and ends, then the answer (owner request
  2026-10-06). `agent.gateway.TOOL_PROGRESS`; tests in
  `tests/test_telegram_ingress.py`. Commit `abb0fd8`.
- [x] Coding on the Bridge C1-C6 (owner decisions 2026-10-06, plan
  `docs/phases/CODING_ON_BRIDGE.md`): restricted Windows runner (low
  integrity, one-process Job, memory/time limits, allowlisted environment)
  and firewall-rule check/probe (`harness/restricted_runner.py`,
  `harness/network_block.py`); detached git worktree and restricted pytest as
  declared commands (`harness/git_worktree.py`, `harness/pytest_commands.py`);
  model change author (`harness/model_author.py`); `coding/change@1.0.0`
  with Workflow `engineering/coding-change` and Skill `coding`, host binding
  `coding`, doctor check. Harness fix: an unchanged repair is a typed stop
  (`change_made_no_difference`). Installed live: runner CPython 3.12.14 +
  pytest 9.1.1 under `%LOCALAPPDATA%\AgenticEngineeringPlatform\coding-runner`,
  practice repository `C:\Users\Chi_L\Documents\aep-coding-practice`,
  grant `owner-approved-2026-10-06-coding-practice`. Tests:
  `test_restricted_runner.py`, `test_coding_worktree_pytest.py`,
  `test_coding_model_author.py`, `test_coding_change_capability.py`.
- [ ] Coding on the Bridge C7: owner creates the firewall rule (elevated, see
  HANDOFF), then the first live run implements `format_duration` in the
  practice repository through Agent Web or Telegram.
- [ ] Coding on the Bridge C8: native Claude Code author for PUBLIC-only tasks.
- [x] SOP to Workflow W1 (plan `docs/phases/SOP_TO_WORKFLOW.md`, owner
  decisions and approval of harness designs A/B 2026-10-06): practice
  shipment site, tracking workbook and SOP PDF
  (`python -m evaluation.sop_practice prepare|serve`). Found: pypdf returns
  Kangxi radicals for some glyphs in printed PDFs (客⼾ for 客戶); the
  Workflow author now folds them (`common/cjk_text.py`). Tests:
  `test_sop_practice.py`, `test_cjk_text.py`.
- [ ] Knowledge PDF ingestion (`knowledge/office.py` `PdfExtractor`) has the
  same look-alike radical problem; folding there changes extracted text and
  therefore Vault evidence digests, so it needs a re-ingestion plan first.
- [x] SOP to Workflow W2-W7 (plan `docs/phases/SOP_TO_WORKFLOW.md`):
  fixed step inputs (`{"source": "fixed"}`, owner decision); recorded web
  procedures (`integrations/web_script.py`) as `web/read` (refuses clicks
  that could change a site) and `web/act`; `data/select`; `excel/read-sheet`
  and `excel/upsert-rows` (never deletes, refuses open workbooks and
  workbooks with drawings, backs up, has `preview`); `WorkflowEngine.preview`
  (design A); authoring sessions (`host_runtime/authoring.py`, design B) with
  the conversational drafter (`workflow_author/conversation.py`; the host
  fills fixed manifest fields, the model writes steps); Agent Web
  "Create a Workflow from an SOP" panel and `/api/authoring/*`. Tests:
  `test_fixed_step_input.py`, `test_web_script.py`, `test_web_capabilities.py`,
  `test_excel_blocks.py`, `test_workflow_preview.py`,
  `test_authoring_conversation.py`, `test_authoring_sessions.py`,
  `test_authoring_web.py`. Full pytest 2198 passed, 1 failed (the known cp950
  test).
- [x] SOP to Workflow W8 live, up to preview: the practice SOP PDF was
  uploaded, the Gateway model asked for the site, workbook, table and button
  details, and after the answers it drafted
  `engineering/daily-shipment-tracking` (web read, Excel upsert, select,
  web act). The preview read the practice site, planned the Excel changes and
  the two notifications, and changed nothing. Installing waits for the owner
  (Agent Web, session `sop-20261006-094136-07236f`).
- [ ] SOP to Workflow: owner approves and installs the practice Workflow, runs
  it, then one real SOP chosen by the owner; then W9 business cards.
- [x] Regression check after coding and SOP W1 (owner question 2026-10-06):
  full pytest 2162 passed, 1 failed (`test_local_developer_environment`, the
  cp950 stderr decoding failure that predates this work). Live Agent Web:
  direct Knowledge ask answered; chat routed a Knowledge question to
  `knowledge__ask` and never to `coding__change`; Workflow 14 dry run
  succeeded and wrote nothing; `aep-host run-task --prompt` validated.
- [x] Reverted my 2026-10-05 live install of
  `company-agent/knowledge-query@1.1.0` (selector hint). It reused a version
  that already existed with different content (the owner's earlier 1.1.0,
  disabled and superseded by 1.4.0) and added a second `knowledge` alias. Moved to
  `assets/skills/disabled/company-agent__knowledge-query__1.1.0.selector-hint-20261005.json`.
  The repo still ships that identity (`company_agent/manifest.py`): its
  version needs an owner decision.
- [x] Knowledge asked in chat fails before and after this work (A/B checked
  live): capability tools reach the model with no input schema, so the model
  guesses `question`/`query`/`q` and never sends the required `asset`;
  every call is refused `invalid_input`. The fix changes how conversation
  tools are built (harness), so it waits for the owner (options in the
  2026-10-06 chat; record the choice in DECISIONS).
- [x] One conversation tool per Knowledge vault (owner decision 2026-10-06):
  `KnowledgeManifest` gains `purpose`/`boundaries` (omitted when unset);
  the Gateway offers a Skill command that names the Knowledge query
  capability once per queryable vault (`<alias>__<vault>`), described by the
  vault's purpose and boundaries, with only `question` for the model and the
  vault bound by the host. Live: the chat question that used to fail with
  `invalid_input` now answers with the vault's evidence. Commit `e5c0207`;
  tests `tests/test_knowledge_vault_tools.py`.
- [x] `engineering/rs-knowledge@1.0.1` published (owner approval
  `owner-approved-2026-10-06-rs-knowledge-1.0.1-purpose`): 1.0.0's content
  (all three digests re-verified against the vault) plus the owner-approved
  purpose; boundaries empty by the owner's choice. host.json binds 1.0.1
  (backup `host.json.bak-20261006-163601-before-rs-knowledge-1.0.1`); 1.0.0
  stays installed for rollback. Live: the chat tool `knowledge__rs-knowledge`
  carries the purpose and answered with evidence.
- [x] coding_v1 benchmark and baseline (owner request 2026-10-06):
  `benchmarks/coding_v1/` (frozen fixtures with SHA-256 manifest, prompts,
  validators with self-test, fixture HTTP server, Agent Web chat adapter,
  runner). `baseline-run-001`: 20/20 BLOCKED, 0 PASS, no false completion
  claims. Gaps G1 (no file/code tool in chat), G2 (coding/change only for a
  configured repository with existing tests); defects D1 (Knowledge intent
  routing captures web/spec tasks, 5 tasks) and D3 (`empty_model_answer`,
  2 tasks). See `runs/baseline-run-001/report.md` and `findings.md`.
- [x] coding_v1 fixes G1 (`coding/run-python`, Workflow `engineering/run-python`,
  Skill `engineering/coding@1.1.0`), D1 (local-work messages skip the
  Knowledge intent route) and a Skill-selector guard (JEV can never narrow to
  coding); live checks: Knowledge asking, W14 dry run and run-task unchanged.
  `fix-run-001` invalid (runner folder ACL left by the AppContainer probe; the
  doctor now probes the runner restricted). `fix-run-002`: 7 PASS, 13
  BLOCKED; remaining D3 (1024-token conversation output cap truncates tool
  calls, 11 tasks), G3 (4 tool calls per turn), G4 (no chat Workflow
  install/run), G5 (no subprocess in the runner).
- [x] coding_v1 D3 fix (conversation output cap) awaits the owner: it changes
  every conversation turn, including Knowledge asking. Resolved: the owner
  approved it and it shipped in `fea13ff` (row below).
- [x] D3 (8000-token conversation output cap, `model_output_truncated`) and
  G3 (8 tool calls per turn), `fea13ff`, after the owner allowed the edit.
- [x] G4 conversational authoring: `authoring__draft/preview/run/install/list_workflows`
  host tools, owner approval buttons in Agent Web (`/api/approvals`), run
  values for run-python scripts (`d8cbad9`, `0d8b943`). Telegram buttons: open.
- [x] Lab gaps L1-L3: `browser/operate` + `browser__operate` (Edge, allowed
  origins, downloads), `desktop/operate` + `desktop__operate` (UI Automation
  helper, registered apps only), run-python child processes (max 4);
  live: lab origin, `desktop.applications` (Expense), grants owner-approved.
- [x] coding_v1 validators 1.1-1.3 (T20 fault evidence, T12 any table format,
  T09/T13 measured when the program ran); fix-run-003 15/20, -004 16/20,
  -005 18/20, **fix-run-006 20/20**.
- [x] Lab fix-001: 4 PASS of 16 (W03, C03, C04, C04 exit-2); grader 1.1.
- [x] Owner 2026-10-07: 20 tool calls per turn and a tool record carried
  across turns (`3532c3d`); several calls per reply run in order; Telegram
  approval buttons (A5 done); Edge profile recovery; desktop `clear_dialogs`
  and placeholders; coding Skill 1.5.0; runner `tzdata`.
- [x] Lab fix-002 5/16, fix-003 invalid (leftover Edge), fix-004 9/16
  (grader 1.2 would add D03 and W04); grader 1.2.
- [x] Lab fix-005 and coding_v1 re-verification on the current build (done;
  results in the rows below).
- [x] Lab fix-005 11/16, fix-006 13/16, fix-007 12/16 (X02 asked first, then
  an upstream 400), fix-008 12/16 with **X01 passing** (all three interfaces,
  unchanged-code rerun). coding_v1 fix-run-007 20/20, -008 18/20 (validator
  1.4 fixes T14), -009 19/20 (T08 Agent variance). Each run's `findings.md`
  lists causes and follow-ups.
- [x] A refused desktop step names the failed action (`CapabilityRefused.where`,
  "Refused at action N (kind)"), never the helper's message (`a8a4864`,
  lab fix-008 D01). Lab bypass scan: `expense_app\b`.
- [x] coding_v1 fix-run-010 interrupted at T09 by an Agent Web defect: a
  reply quoting `Authorization: Bearer <token>` failed the stored-message
  credential check and dropped the request. Messages now redact instead
  (`4becd6b`). **coding_v1 fix-run-011: 20/20 on `4becd6b`.**
- [x] Lab fix-009 on `4becd6b` stopped at the owner's request (GUI tests only
  while the owner is away): W01–W04 PASS (W01 rerun passes for the first
  time), D01 FAIL (rerun), the rest not run.
- [ ] Lab fix-010, all tasks, on `4becd6b`, run while the owner is away from
  the computer (see HANDOFF.md for which tasks drive the GUI).
- [x] Lab grader 1.3 (owner approved): a rerun may use a version run or
  installed before the request, with no draft after it (`b44412a`); fix-008
  W01 regrades to PASS (13/16). Draft guide and coding Skill 1.7.0: run the
  installed Workflow and check its output before calling it reusable
  (`552bc7f`, installed live). The live desktop test runs only with
  `AEP_GUI_TESTS=1` (`967249b`). coding_v1 fix-run-012: 20/20.
- [x] Asset ownership step 1 (owner decisions, `docs/phases/ASSET_OWNERSHIP.md`):
  chat Workflow versions continue from the highest installed one; a name
  another owner installed is refused with that owner (`9f07861`). Live after
  the next Agent Web restart.
- [ ] Asset ownership step 2 (Registry-wide owner, co-editors, automatic
  versions, one active version per person, publish UI) after the lab stage.
- [x] Asset ownership step 2, Registry and member service (2026-10-07,
  `01fc30e`, not merged): `(namespace, name)` ownership record in both
  Registries (additive `name_owners` table, existing names derived from their
  earliest version), owner / team / co-editor publish check, assigned
  (patch/minor/major) or strictly higher versions, co-editors, transfer,
  deprecation beside the name, one active version per member per device per
  name in `select()`, and member portal routes for the owner operations.
  Tests: `tests/test_asset_ownership.py`. Not live: the Shared Platform needs
  a restart on the merged code.
- [ ] Asset ownership step 2 remainder: a member publish route (artifact
  upload plus a review queue reusing `Review` / `TechnicalPolicy`), the
  Agent Web publish and ownership UI, and showing deprecations to Hosts.
- [x] knowledge_v1 benchmark (owner request 2026-10-07): the owner's 1,100
  questions, pinned; 110-question stratified sample; loop + Vault-verified
  citations + Gateway-model review (`ab9cb3e`).
- [x] knowledge_v1 sample-001: 64 of 110 acceptable (PASS 31, INSUFFICIENT 33);
  direct route 22/34 PASS, tool route 9/58, no Knowledge 18 (`c64a724`).
- [x] Knowledge fixes (owner approved): synthesis 4000 tokens + one retry on
  truncation, "say when Knowledge gave no answer" (`8e25b8b`); rs-knowledge
  1.0.2 purpose (live binding); facet credit from cited passages, supported
  answers kept with the gap named, tool route uses the harness Skill
  procedure, Skill 1.5.0 fixture with three market hints (`72af226`).
- [x] knowledge_v1 sample-002: 75 of 110 acceptable, Knowledge used every time,
  no synthesis cut-offs (`db38f28`).
- [x] Final build `db38f28` live (Skill 1.5.0 installed): lab fix-010 14 of 16
  PASS, every rerun reuses its Workflow, X03 passes (`041c746`); coding_v1
  fix-run-013 19 of 20 (T13 parsing, Agent variance) (`1d81472`).
- [x] knowledge_v1 sample-003 on `db38f28`: 68 of 110 acceptable; direct route
  25/34 PASS (was 19), tool route 10/74 (was 15) (`9eefe75`). knowledge_v1
  `compare.py` for cross-run comparison (`3ce2b8a`).
- [x] coding_v1 fix-run-014 on `db38f28`: 19 of 20 (T16: read only the top of
  input/ and "verified" empty outputs). Two runs on this build: 19, 19, each
  failing a different task (Agent diligence variance).
- [ ] Phase gate decision (owner): coding_v1 has 20/20 on `4becd6b` and
  `967249b` but 19/20 twice on the lab's build `db38f28`; the rule-following
  analysis proposes coding Skill 1.8.0 wording (read rules in full, missing
  values follow the request/template, keep template formulas, check outputs
  against inputs) plus a separately tested X02 wording.
- [ ] Knowledge tool route (owner decision): return the harness's validated
  answer as is, or route more Knowledge questions to the direct harness.
- [x] Per-person pixel-art avatars in Agent Web (owner request; owner chose to
  keep the One Piece sheet in the repo) (`cbb11e0`). Live after the next
  restart.
- [ ] Lab remaining gaps: W01/D01 reruns where the Agent revises the Workflow
  instead of reusing it; X02 overdue invoices dated before the period; X03
  depends on X01's Workflow taking project and output name as run values.
- [ ] Conversational authoring A1-A3, A7, A8.
- [x] Business workflow lab (owner request 2026-10-06):
  `benchmarks/business_workflow_lab/` with an SAP-like site, a Tk desktop
  Expense app, a quote CLI, 4 Excel templates, 15 prompts, expected answers,
  a self-tested grader and a batch runner through Agent Web chat. Mocks 42/42
  smoke checks. `baseline-001`: 16/16 BLOCKED (no browser, desktop or process
  tool for the Agent; G3/D3 ended every turn first); scripts read mock
  internals (isolation limit observed). Gaps L1-L7 in
  `runs/baseline-001/findings.md`.
- [x] Lab gaps L1-L3 and L7 await owner decisions (browser, desktop and
  process tools for the Agent; mock data isolation). Resolved 2026-10-07: the
  owner chose Edge, Windows UI Automation and a relaxed runner (done, see the
  L1-L3 row); for L7 the owner said the mocks need no isolation.
- [ ] Natural-language Workflow authoring and modification (owner request
  2026-10-05): direction and owner decisions in
  `docs/phases/NL_WORKFLOW_AUTHORING.md`; P1 building blocks are extracted
  during the rs_workflow_system migration, P2-P4 follow the migration.
- [x] Test stability (subagent, 2026-10-08): cp950 pwsh decoding, Windows
  rename locks retried narrowly (`common/filesystem.py`), SOP PDF wait, Agent
  Web refused-POST reset, marketplace snapshot line endings. Full pytest
  2318 passed, 0 failed (`3a102e3`).
- [x] Asset ownership step 2 merged (`9a81382`, `9d875d7`): Registry name
  owners, co-editors, ordered versions, one active version per member,
  owner operations and member routes; not live until the Shared Platform
  restarts; five design choices await owner confirmation.
- [x] Web access (owner 2026-10-08): every http(s) page may be used,
  `web.allowed_origins` "*" by default; non-web schemes refused (`236e1bb`);
  live host.json uses ["*"].
- [x] Attachments in Agent Web (owner 2026-10-08): images, PDF, CSV, HTML,
  TXT, JSON, YAML, MD, ZIP; 25 MB / 10 files; vision on for the company
  endpoint; checked live (CSV average and image text read correctly)
  (`d91fc0f`).
- [ ] Paused by the owner: phase gate decision (coding Skill 1.8.0 wording) and
  the Knowledge tool-route choice; the owner will check the Agent by hand first.
- [x] Telegram accepts files and photos (owner 2026-10-08): documents and the
  largest photo size are downloaded via `getFile` after the sender check,
  saved with the shared `AttachmentStore` per chat and sender, and given to
  the conversation model as Agent Web does. An album within one poll batch
  is one turn. Size, count, type and Telegram's 20 MB download limit are
  refused with Chinese replies. `/new` deletes the chat's files, and the
  token never leaves the download call. `tests/test_telegram_attachments.py`.
- [x] External authoring X1-X5 (owner 2026-10-08,
  `docs/phases/EXTERNAL_AUTHORING.md`): Claude Code, Codex and Copilot check,
  submit, test and request installs of Workflows and Skills through
  `aep-host assets` or the stdio MCP server `aep-host mcp`. Approvals are the
  owner's (Agent Web: Installed, "外部 Agent 提交"). Skill candidates and
  installs are new. The catalog and results keep the PUBLIC rule. Creator
  Skills are installed with `aep-host assets connect`.
  `tests/test_external_authoring.py`.
- [x] External authoring X6, Claude Code: `benchmarks/authoring_v1` r001,
  PASS on W1, W2 and S1 (installed Workflows rerun with hidden values; the
  Skill loads beside all others) (`7cc9cb7`).
- [ ] External authoring X6, Codex and Copilot: CLIs not installed on this
  machine; run r002 once they are installed and signed in.
- [x] Task folders checked when a Workflow is drafted (owner 2026-10-08, after
  `coding_workspace_not_allowed` at an approved run): the Agent is told the
  coding roots, a draft is refused if a fixed run-python or browser
  workspace lies outside them, and a missing folder inside them is created.
  Live root `C:\Users\Chi_L\Documents\aep-workflows` added (`af1450d`).
- [x] Workflow 13 up to the commit (owner 2026-10-08): `release-package-prepare`
  (version lookup, branch from template, files, plan and fingerprint) and
  `release-package-commit` (only the reviewed, unchanged prepare), two
  approved runs, isolated local origin only. `benchmarks/w13_parity` p001:
  the source job and AEP match on all 4 cases. `tests/test_release_run.py`.
- [ ] Workflow 13 push: its own approval against the real GitLab (needs a
  valid GitLab token), the pipeline watch, upload sets from attachments, and a
  dry-run comparison against the real release repository.
- [x] One-click Agent Web (owner 2026-10-08): `aep-host open` opens the running
  server's recorded address, or starts it in the background first;
  `aep-host shortcut` made "AEP Agent" on the desktop and in the Start menu.
  The token still changes every start. `tests/test_launcher.py`.
- [x] Capabilities page (owner 2026-10-08): the SOP authoring and contribution
  forms are removed; "我的草稿（尚未安裝）" lists uninstalled Workflow and Skill
  drafts with Install (the owner's approval) and Delete (`/api/drafts`).
- [x] Installed Workflows run without asking again and without a restart
  (owner 2026-10-08); drafts card under the capability browser; Agent
  profile moved to Settings.
- [x] Conversation feedback to the Shared Platform (owner 2026-10-08): Agent
  Web ratings, with the question and answer, are queued locally
  (`feedback_outbox`) and sent by the `feedback` Bridge operation once the
  platform answers; the platform keeps the newest rating per answer and
  `aep-platform feedback` exports it. `tests/test_feedback_sync.py`.
- [ ] Feedback follow-ups: a platform page to read and triage feedback;
  Telegram ratings.
- [x] MCP servers in Agent Web Settings (owner 2026-10-08): stdio and
  Streamable HTTP; every tool of an added server becomes a granted Bridge
  capability `mcp-<server>/<tool>@1.0.0`, offered in conversations (also
  during coding) and usable as a Workflow step; secrets only in the user's
  environment. `tests/test_mcp_servers.py`.
- [x] Harness telemetry for Atlas (owner 2026-10-08): `aep.telemetry.v1` events
  from routing, Skill selection, every model and Bridge call, Workflow,
  Knowledge and coding harness states; non-blocking recorder, local SQLite
  (30 days / 500 MB), read API + WebSocket stream for Atlas without a token
  (local origins only), JSONL export. Contract v0.2 in `docs/telemetry/`.
  `tests/test_telemetry.py`.
- [ ] Atlas side (owner: Atlas): event-stream provider, run timeline, state
  graph, heatmap (contract v0.2 §8).
- [x] Harness unification U1-U6 (owner 2026-10-09,
  `docs/phases/HARNESS_UNIFICATION.md`): Coding, Workflow, conversation turns
  and the Knowledge tool route run on the shared plan/execute/validate/retry
  state machine; Workflows may declare output checks; conversation answers
  are checked against the turn's real tools and files; the Knowledge tool
  route returns the validated Harness answer and retries widen retrieval;
  revisions that drop steps must say so; external agents run installed
  Workflows directly.
- [ ] Harness unification U7: benchmarks after the change (non-GUI any time,
  GUI while the owner is away) and a Knowledge Skill 1.6.0 with a retry
  budget on the live host.

- [x] knowledge_v1 reference answers (2026-10-09): `reference.py` (Claude Code,
  read-only, quotes verified) and `reference_grade.py` (company model labels
  key-point coverage). Trial: Q0011, Q1001, 8/8 quotes verified each. Grader
  1.2 reads the tool route's host-validated answer; the Gateway keeps its
  cited passages (a18421a, 875d3e3).
- [x] knowledge_v1 reference answers for all 36 core questions (667088f);
  core-001 compared against them (3c7ff81).
- [x] Bilingual retrieval for wiki-primary Knowledge, Skill 1.7.0 (f729827):
  reference-file recall 0.12 -> 0.26; core-002 on the 22 answerable
  questions PASS 13 -> 16, false insufficient 6 -> 0, FAIL 3 -> 6.
- [x] Knowledge answer overreach: Skill 1.8.0 guidance (2026-10-10). core-003
  on the 22 answerable questions: PASS 18, FAIL 2 (was 6), coverage 0.28.
- [x] Knowledge multi-round retrieval, Skill 1.9.0 (13354e4, 2026-10-10):
  reference files offered to synthesis 22% -> 41%, cited 17% -> 26%;
  answerable coverage 0.28 -> 0.30, contradictions 7 -> 4, median latency
  137 -> 200 s (runs/core-004/review.zh-TW.md).
- [x] Owner kept Knowledge Skill 1.9.0 (2026-10-10): better grounding over
  about 60 s more per answer.
- [x] Knowledge synthesis evidence budget, Skill 1.10.0 (9cbe3ca, 2026-10-10):
  answerable coverage 0.30 -> 0.40, FAIL 3 -> 4, contradictions 4 -> 4,
  overreach items 35 -> 63 (runs/core-005/review.zh-TW.md). Kept.
- [ ] Optional: reduce Knowledge overreach under Skill 1.10.0.
- [x] Benchmark results into telemetry for Atlas (d29ac63, contract v0.3):
  knowledge_v1 (+ reference grading), coding_v1 and the business workflow
  lab emit benchmark runs; /runs filters by trace_id and parent_run_id.
- [x] Atlas consumer for benchmark telemetry (uncommitted in the Atlas
  working tree on top of Codex's uncommitted AEP integration; see Atlas
  docs/HANDOFF.md). npm test 112 passed, build passed, live shell check passed.
- [ ] Atlas browser acceptance and an owner-approved commit plan for the Atlas
  working tree.
