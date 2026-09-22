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
`docs/phases/PHASE_7_MIGRATION.md`; slices 1, 2a and 2c have merged. 47 pull
requests merged (#1 to #51; #5 was closed unmerged and superseded by #6, the
numbers #24 and #25 were never pull requests, and #49 was closed unmerged
when its base branch was deleted and landed through #51). A row says `done` only once
its pull request has merged; until then it says `in review`, so the
committed record never asserts a merge that has not happened.

The suite is 722 passed, 3 skipped on Windows, with `ruff`, `mypy`,
`pip check` and `python -m build` clean. The three skips need symbolic-link
privileges and run on Linux CI.

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
| 2b company Bridge enrollment | — | planned | Authenticated invitation/device enrollment, capability advertisement transport and a read-only shared-platform connectivity probe |
| 2c local-first control contracts | #50, landed via #51 | done | Registry package acquisition, verified local inventory, timestamped status projection and actor/device-scoped remote jobs |
| 2d resident local Agent and durable local state | #53 | in review | `LocalAgent` admits by the device's own membership copy on every ingress, routes through the existing Gateway, executes exact remote jobs, and records runs in a single-writer SQLite local state that outlives the process |
| 2e Telegram ingress | — | planned | Outbound polling, numeric sender mapped to exactly one bound actor, fail closed on an empty or unmapped allowlist, token through `SecretRef`, the same admission and Gateway path |
| 2f authenticated shared-platform transports | — | planned | Registry package synchronization, Bridge job polling and snapshot reporting over an authenticated transport; needs an authentication design first |
| 3 workflow 7 parity | — | planned | Jira report behavior against a test workbook, compared with the working old Host Bridge |
| 4 workflow 13 parity | — | planned | Release package behavior in dry-run and an isolated test repository before any approved push |
| 5 knowledge parity | — | planned | Adopt, query, update and restore a full copy of the source vault |
| 6 controlled cutover | — | planned | Per-entry-point evidence, rollback rehearsal, owner approval and observation before freezing old entry points |

## Open items carried forward

Recorded where they were found. None blocks a completed phase's exit criteria
or the start of Phase 7.

| From | Item |
|---|---|
| Phase 3 | A payload sweep, and process-liveness or lease-based suspension |
| Phase 4 | A retrieval cache, host wiring that plans from an adopted document, a size-and-mtime shortcut for adopted-file drift checks, image description for legacy `raw/` |
| Phase 5 | Tool calling in either adapter (it needs a registry that can render a contract as a provider schema), reading `tool_calls` back, retry behaviour, a pooled or async transport, a production credential backend |
| Phase 6 | Nothing persists an `ExecutionTrace` yet (a host writes them beside its checkpoints); `SECRET_PATTERN` is deliberately narrow and a provider-specific token shape it does not name is not redacted; `stayed_in_namespace` has no allowance for a capability legitimately shared across namespaces |

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
| 2026-09-22 | Platform registration is invitation-only; the shared-platform host cannot use company LDAP |
| 2026-09-22 | Production-like execution occurs on an enrolled company Agent + Bridge; the current old Host Bridge can run workflows 7 and 13 and remains the parity/rollback baseline |
| 2026-09-22 | A company workstation has one employee/platform member and corporate resource access; a shared test workstation has multiple invited platform users, no corporate access, one shared Windows account and no claimed OS-level isolation |
| 2026-09-22 | CI remains inert. Source repositories and old entry points are retained at pinned revisions until parity and rollback rehearsal; archive is a later decision and deletion is outside Phase 7 |

## Resolved owner decisions (Phase 7)

The four decisions that previously blocked the specification are resolved by
the dated owner decisions above and `docs/phases/PHASE_7_MIGRATION.md`:

1. Candidates/order: workflow 7, workflow 13, then knowledge; retire individual
   entry points only after evidence, never an entire mixed repository first.
2. Parity: normalized source/platform behavior and safety gates are explicit for
   each candidate; timestamps and container metadata are not byte-parity targets.
3. Environment: shared platform here, real work on an enrolled company Bridge;
   external credentials remain on that Bridge. CI never performs live validation.
4. Rollback/retention: pin and retain the source plus working old Host Bridge;
   rehearse rollback before cutover. Archive later; do not delete in Phase 7.
