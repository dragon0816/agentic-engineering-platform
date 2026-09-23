# Phase 7 source inspection and disposition

Initial source: `dragon0816/rs_workflow_system`, commit
`896046e8fe2170d21f9213e56e5ce2f93c05ba43`, inspected read-only on
2026-09-22. The company computer can run the pinned old Host Bridge paths and
therefore supplies the comparison baseline. No source repository is modified.

## Initial candidates and decision

| Candidate | Proven behavior that must survive | Decision |
|---|---|---|
| `workflows/11_jira_weekly_report.json`, `host-bridge/jobs/jira_weekly_report.py` | Manual/daily trigger; no HTTP retry; fixed week/JQL window; scratch-sheet-only writes; upsert by Jira key; marker-filtered comment prepend with local and remote dedupe; formatting retirement; dry-run preview | **PRESERVE + ADAPT** after company-Bridge enrollment. Characterize the job's rules and project them into typed capability/workflow contracts. Keep Jira and Excel execution on the company Bridge. Do not copy credentials, file paths or n8n transport configuration. |
| `workflows/13_release_package.json`, `host-bridge/jobs/release_package.py` | One blocked run per working copy; no automatic HTTP retry; required values; version/branch/requirements/release.yaml rules; safe inbox names; dry-run without commit/push; explicit commit/push | **PRESERVE + ADAPT** after workflow 11. First run only against an isolated test repository with dry-run. Keep Git/file execution on the company Bridge and retain explicit approval for push. Do not interpret publication or device binding as release authority. |
| Phase 4 knowledge source | Immutable Raw, provenance, whole-plan refusal, backups/restore and query citations | **ADAPT** after both workflows, using a full copy before the source vault. Existing Phase 4 characterization remains the baseline. |

The n8n graph is optional scheduling/coarse orchestration. Parity belongs to the
underlying job outcome and safety rules, not to matching n8n node JSON. Agent,
CLI and optional n8n paths must converge on the same platform workflow contract.

## Enrollment foundation

There is no invitation, account or multi-user device behavior in the pinned Host
Bridge to reuse. This is new control-plane behavior required by the approved
deployment topology. Decision: **ADAPT** existing provider-neutral identity,
Bridge advertisement and policy separation; add closed enrollment contracts and
an in-memory reference model. Do not migrate `X-Bridge-Token` as the platform
identity model and do not implement production authentication/RBAC in this slice.

Rollback removes `common.enrollment`, `control_plane.enrollment`, their tests and
Phase 7 docs. Existing Bridge/Gateway behavior and every source path remain intact.

## Windows preview deployment

The pinned source contains an offline bundle builder, a per-user Bridge installer,
interactive-session startup and a safe uninstall path. Decision: **ADAPT** the
proven packaging invariants only: no credentials/configuration/state in the bundle,
target Python/platform recorded, payload hashes checked before install, per-user
versioned installation, and dry-run removal of owned files. Do not copy its token
login, HTTP server, job implementations, browser profile, system-wide prerequisites
or autostart behavior into this preflight slice.

The new preview packages the provider-neutral wheel and its Python 3.12 Windows
dependencies. Its CLI can inspect the local host and export a credential-free empty
Bridge advertisement. Because the shared-platform enrollment transport and Jira,
Excel and Git capability adapters do not yet exist, it cannot execute workflows 7
or 13. Rollback removes the installed version directory or reverts the preview
package files; the old Host Bridge remains unchanged and usable.

## Local-first control and Telegram ingress

The pinned `telegram-local-agent` source at
`4b40a215909e4fdd4b65519d70669a84e9abd43d` already runs a resident local Agent,
uses Telegram polling so it needs no public inbound port, checks numeric Telegram
user IDs before routing, preserves direct `/run`, `/release` and `/build` paths, and
supports status/Skill discovery plus attachments. Decision: **ADAPT** those proven
channel and deterministic-routing behaviors in a later transport slice. Do not copy
its bot token configuration, HTML presentation, provider coupling, path handling or
unsafe empty-allowlist behavior (the source permits every sender when the list is
empty).

This contract slice records `telegram` as an ingress but performs no Telegram call.
A future adapter resolves its token through `SecretRef`, maps an allowed numeric
sender to exactly one platform actor, uses outbound polling, and passes the same
device membership, exact Workflow authorization and Bridge policy checks as the
shared-platform ingress. The company device admits only its registered/bound owner;
the shared test device admits its active bindings. Rollback removes the new contracts
and references without touching the pinned local agent.

## Retirement rule

Keep source repositories and the old Host Bridge frozen at recorded revisions
through parity and rollback rehearsal. Disable one entry point at a time only
after its evidence passes. Archive remains a later owner decision; deletion is
outside Phase 7.

## Resident local Agent and durable local state

Two source behaviours overlap this slice. The pinned `rs_workflow_system` Host
Bridge keeps job state on the Windows computer that runs the job and reports it
outward, characterized in `docs/PHASE_3_MIGRATION.md` when its job runner became
the workflow engine. The pinned `telegram-local-agent` runs a resident local
Agent that routes deterministically before anything else, characterized in
`docs/PHASE_2_MIGRATION.md`. Decision (2026-09-22): **ADAPT** both through the
contracts this repository already has, and write no new runtime. The resident
Agent is a thin admission layer over the existing `Gateway`; local run state is
the existing `LocalRunSummary` on a SQLite file that follows the checkpoint
store's single-writer rule. Neither source's transport, token handling or
process model is copied.

Three choices were made here. Admission happens on the Bridge from its own copy
of membership, not by asking the control plane, because company work must not
stop when the shared platform is unreachable (Architecture, "Local-first
resilience"); the device half of the rule is one function in
`common.enrollment` that the control plane's reference and the Agent both call,
and the membership copy carries the company-owner rule in its own validator,
so the two cannot drift. Review of the first version found the rule written
twice with two vocabularies, which is exactly the drift the slice claimed to
prevent. The ingress becomes the request's channel
and nothing more, so a Telegram sender, a polled job and a local operator are
refused or admitted by one rule and routed by one Gateway. And the installation
rule was lifted out of the in-memory reference into `common.distribution` so
the durable store and the reference cannot disagree about what a valid install
is; the reference now reports the shared rule's refusals in its own codes.

Review also found that the Agent recorded the engine's pre-flight rejections as
runs (the engine mints a run id for a rejection it never starts, and the Agent
projected it), wrote a timed-out run once and never again although the engine
keeps driving it, executed a redelivered job twice, and raised a state error
over a workflow result that had already happened. The Agent now records only
runs the engine knows, settles a timed-out run in the background, uses the job
id as the idempotency key, and reports a failed record on the outcome. The
engine, not the durable inventory, answers for what is installed on the
Bridge: packages obtained from the Registry and manifests loaded into the
engine are two records today, and joining them is transport work for slice 2f.

Slice 2d was split from the "local Agent and transports" row into three: this
slice needs no network, while Telegram polling (2e) and the authenticated
shared-platform transports (2f) each need an authentication design that is
better reviewed on its own.

Rollback removes `common.local_agent`, `host_runtime.agent`,
`host_runtime.state` and their tests, and moves `verify_installation` back
into the in-memory reference. The Gateway, engine, Bridge, enrollment and
distribution references are unchanged.

## Telegram ingress

Source: `dragon0816/telegram-local-agent` at
`4b40a215909e4fdd4b65519d70669a84e9abd43d`, `core/channels/telegram_handler.py`
(606 lines), `telegram_channel.py`, `channels/base.py` and `config.yaml`,
cloned read-only into `.scratch/` and inspected on 2026-09-22.

| Source behaviour | Observed | Decision |
|---|---|---|
| Outbound long polling (`run_polling`, webhook deleted at start) | No inbound port; the library retries network errors; a second instance on the same token is a `Conflict` | **ADAPT**: `getUpdates` over the platform's own `Transport`; HTTP 409 is `telegram_conflict` and stops the loop |
| Sender check `_is_allowed(user_id)` before every handler | Numeric Telegram user ids from `allowed_users`; **an empty list admits everyone** | **ADAPT the check, invert the default**: a sender map of id to exactly one platform actor; an empty map admits nobody |
| `/run`, `/release`, `/build` route straight to a named skill, bypassing the LLM | Hard-coded command-to-skill table | **ADAPT generically**: `/skill command rest` becomes the platform's `skill.command rest`, which the deterministic router already understands; no table |
| Free text routed through the LLM | `router.route(user_message, ...)` | Already the platform's path: the Gateway routes deterministically first and a model only if configured |
| `bot_token` in `config.yaml`; a real token and a GitLab token are committed there | Plain text in a tracked file | **NOT MIGRATED**: the token is a `SecretRef` resolved per call and never held; the shape is added to `SECRET_PATTERN` so it cannot be pasted into any record. The source's committed tokens were reported to the owner and not copied |
| `user_info` (username, first name, id) passed to the router | Identity by Telegram id, presentation by name | Only the mapped platform actor is carried; names are not |
| HTML `ParseMode`, `esc()` everywhere, 4000-character chunking | Presentation coupled to Telegram's HTML rules | **ADAPT chunking only**: plain text, no markup, so nothing needs escaping |
| Document and photo download into `FileManager`, `pending_files` per user | Attachments stored on disk and attached to the next command | **NOT MIGRATED in this slice**: a non-text message is `unsupported_content`; attachments are a later slice with their own storage rule |
| `/skills`, `/mcps`, `/status`, `/reload` queries | Router-internal queries | `/status` answers from the Agent's snapshot; `/help` is static; the rest have no platform equivalent yet |

Decision (2026-09-22): **ADAPT** polling, the numeric sender check and the
direct-command idea; **REFUSE** the token-in-file, the empty-allowlist default,
the HTML coupling and, for now, attachments. The adapter adds no authority:
mapping decides which actor a sender is, and the resident Agent's membership
rule and the Gateway decide everything after that, as they do for every
ingress. The runtime install stays `pydantic` alone; no Telegram library is
imported.

Review of the first version found four things worth recording. An exception
from the Agent or the state store escaped `poll_once`, killed the loop and
lost the update; handling is guarded and what raised becomes a `failed`
delivery. The loop stopped only on a conflict and re-polled a revoked token
once a second forever; it stops on anything not retryable and backs off
otherwise. `models.wire.redacted` trimmed before it redacted, so a token
straddling the cut survived as a fragment, which the token-in-URL made
reachable; the shared helper redacts first, and the wire's failure rules are
parametrized by prefix rather than copied, so a 429 is retryable here as it
is for a model. And an unmapped sender was answered, letting a stranger drive
unbounded outbound calls; the source ignored disallowed senders silently on
every handler but `/start`, and so does this adapter, on every handler.

Known limitation: an update handled in this process is not handled again on
redelivery, but the offset lives in memory, so a batch handled just before a
restart may be redelivered once. The engine's idempotency key does not cover a
routed message; a durable offset belongs with the durable local state in a
later slice.

Rollback removes `src/channels/` and `tests/test_telegram_ingress.py` and the
two additions to `SECRET_KEYS` and `SECRET_PATTERN`; nothing else depends on
them.

## Company host runtime

No source repository is migrated here. The pinned `rs_workflow_system` Host
Bridge reads its configuration from a directory beside the installation and
keeps job state on the machine that runs the job; both were characterized in
`docs/PHASE_3_MIGRATION.md`. Decision (2026-09-22): **ADAPT that shape**, a
workspace of readable files plus a local state file, and write no new runtime:
the host module wires the Gateway, policy and engine this repository already
has. Its token login, HTTP server and job implementations remain out.

Three choices worth recording. The layout is convention under one configured
workspace rather than a set of configured paths, because an installer and an
operator have to agree on it and a second configuration file is a second thing
to get wrong; the layout is a contract, so `doctor` can print it. The host
installs exactly one capability handler, the one the package ships, and says
so: a manifest can be installed without its code existing, and a step that
reaches for an absent capability fails closed rather than silently doing
nothing. And a company host configures no model, so routing is deterministic
only; a model on the company computer is a later decision with its own
credential and endpoint questions.

`doctor` gained a third check status rather than reporting a freshly installed
host as broken. "Not enrolled yet" is the expected state of a new preview
installation, and an installer that prints a failure for the normal case
teaches the operator to ignore it.

The Telegram cursor moved from memory into the Bridge's own durable state,
which closes the redelivery gap recorded when slice 2e landed. A cursor that
can rewind replays messages that were already acted on, so `advance_cursor`
refuses to move backwards, as `record_run` refuses a stale update.

Review of the first version found the diagnostic doing exactly what its own
comment forbade: opening the state store created its tables and migrated the
schema mark from 1 to 2, so a rollback to the previous package could no longer
open its own file. `SqliteLocalState` gained a read-only mode, which is also
the honest way to say that a report looks and does not touch. The same review
found a corrupt file escaping as a SQLite exception, because the opening
`PRAGMA` runs outside the write transaction; every SQLite error on open is now
this class's own `unavailable`. And the new checks had been allowed to change
`status`, which would abort a reinstall over a stale membership record; the
preflight answers for the machine and `runtime` answers for what the host was
given.

Rollback removes `src/host_runtime/host.py`, the new `aep-host` subcommands,
the cursor table and its two methods, and the additions to
`CompanyHostConfiguration` and `DoctorCheck`; the Agent, the ingress and the
preview package keep working as they did.

## Member-decided asset authorization

No source repository is migrated here: neither pinned source has accounts,
devices or per-member authorization, which `docs/PHASE_7_MIGRATION.md` already
recorded when the enrollment foundation was written. This is new control-plane
behaviour required by the owner's rule of 2026-09-22, and it is built from
contracts this repository already has.

Four choices worth recording. A selection names an asset and nothing else,
because a decision that could also name permissions would be a decision that
can widen itself; the capability's own `CapabilitySpec` stays the only place
that says what a tool may do. The three lists stay separate and are enforced
in different places, because installing a Workflow and granting a tool are
different acts: choosing a Workflow is not choosing the tools its steps reach
for, and a step that reaches for an unchosen tool fails closed, which is the
behaviour the platform already had. Each plane derives the grant from the
specification it holds, the shared platform from what the device advertised
and the Bridge from what it installed, rather than sharing a derivation
function across a boundary the architecture keeps apart; both read the same
declaration, so a difference between them is a difference between the device's
claim and its reality, which is worth seeing rather than hiding. And a bundle
carries only the decisions in force, so nothing has to read a status to know
what applies.

Open question for the owner, recorded rather than decided: on a company
workstation the single member approves their own irreversible tools, because
there is nobody else bound to that device. The record says who approved and
when, and the Phase 6 prohibition against an unapproved irreversible effect is
satisfied by construction, but a second approver would be a different rule. On
a shared test workstation another bound member may already be the approver.

Rollback removes `src/common/authorization.py`,
`src/control_plane/authorization.py`, their tests, the `authorization.json`
branch in `host_runtime.host` and the two accessors added to the enrollment
and package registries; `grants.json` keeps working exactly as before.

## Identity-derived entitlement

Owner decision (2026-09-22): a Bridge is bound to a user, and the user's
authentication decides which Workflows and Skills they may use. No source
repository is migrated here; neither pinned source has accounts or
entitlement, and the pinned Telegram agent's numeric allowlist was already
declined as an identity model in slice 2e.

Two choices worth recording. Groups live on the platform's record of a user
rather than on the authentication, because an authentication that carries its
own group list is an authorization that whoever issues it can widen; the
invitation says what accepting it grants, acceptance records it, and
entitlement is read from there. And entitlement is checked when a decision is
made rather than when a run happens, because an authorization is a record of
what was decided: re-deciding at dispatch would make a Bridge's behaviour
depend on a control plane it is designed to work without. The cost is
staleness, which the delivery slice has to close by reissuing.

Still open, and the reason slices 2b and 2i stay planned: what a Bridge
presents to the shared platform to prove it is acting for its bound user, and
what the control plane checks and stores. The shape of the answer already has
a place to land: `AuthenticatedActor` is what an entry point produces once it
has decided, whatever it did to decide.

Review of the first version found the one new unguarded entry point: the
list of what a member may use answered for an expired session, for somebody
the platform had never invited and for a disabled member, while making a
decision refused all three. A list of what somebody may use is itself
something only they should see, so it is guarded like a decision. The same
review found the `team` branch of `entitled` unreachable, which was true and
worth saying out loud rather than deleting quietly: team visibility is
decided by the owning-group test above it, and for a group-owned asset
`team` and `private` mean the same thing.

Rollback removes `src/common/identity.py`, the `groups` fields and the
identity parameters on `select`, `revoke` and `available`; the selections and
bundles from slice 2g keep working.

## Bridge access tokens

Source: `dragon0816/rs_workflow_system` at
`896046e8fe2170d21f9213e56e5ce2f93c05ba43`, `host-bridge/app/auth.py`,
`host-bridge/app/config.py` and `host-bridge/run-bridge.ps1`, cloned read-only
into `.scratch/` and inspected on 2026-09-23. The owner named this flow as the
precedent for the decision.

| Source behaviour | Observed | Decision |
|---|---|---|
| `X-Bridge-Token` on every endpoint but `/health`, compared with `hmac.compare_digest` | One shared token per Bridge, generated at first run, stored in a gitignored `config/bridge.json` and mirrored into `container/.env` | **PRESERVE the comparison, REFUSE the model.** Already recorded here when the enrollment foundation landed: a single shared token cannot tell two members of one machine apart. `hmac.compare_digest` is kept |
| `Request-DeviceBinding`: a person at the keyboard signs in with their ops username and password, and the dashboard returns this machine's own token | The token is stored in the machine's config and presented as `X-Ops-Token`; the response also reports `boundUsers`, "this machine may be used by: ..." | **ADAPT.** This is the decision's shape: a person exchanges their own credential for a machine-scoped token. The source issues one per machine and treats the user list as information; the platform issues one per member and machine, which is what makes a token separately revocable per member. Slice 2j then bound each machine to exactly one member, so in practice a machine holds one token and the source's `boundUsers` list has no counterpart at all |
| `Test-DeviceBinding`: only an explicit `DEVICE_UNBOUND` means revoked; unreachable does not | "Treating a closed laptop lid or a changed network as you have been thrown out would ask people to type their password for no reason" | **ADAPT as an invariant for the transport slice**: unreachable is not revoked. The reference model already separates the two answers, `binding_withdrawn` against everything else |
| Binding again needs a person at that keyboard | "Both are meant to need a person at this keyboard, that is what makes revoking mean something" | **PRESERVE** as the meaning of revocation: `unbind` plus `revoke_for` leaves the machine unable to act for that member until somebody signs in again |
| The token is written to a config file in plain text, and printed to the console for pasting into `.env` | Gitignored, but on disk and in the scrollback | **REFUSE.** The value is handed over once by `issue` and then belongs to the host's own credential store, reached through a `SecretRef` and a `CredentialResolver`, as the Telegram bot token already is. Nothing writes it into a workspace file |
| The platform stores the token it expects and compares the presented value against it | A stolen server-side store yields working tokens | **REFUSE.** The platform keeps a SHA-256 fingerprint and never the value |

Two choices worth recording beyond the table. The secret is verified before
anything is said about the token's state, so an unknown token and a wrong
secret are one answer: telling them apart tells somebody who holds neither
that a token exists. And a plain digest is used rather than a slow one,
because the secret is 32 random bytes from `secrets`, not a password; that is
also why a caller-supplied secret under 32 characters is refused rather than
accepted and hashed.

Known limitation, and the one the owner may want to answer next: the tokens
live on the Bridge, and on a shared test workstation the members share one
Windows account with no OS-level isolation, so one member can read another's
token and act as them. Issuing one token per member and machine makes their
requests distinguishable and separately revocable, which a single shared token
never could, but it does not make them unforgeable between people who already
share that account. Narrowing that needs either per-member Windows accounts on
shared machines, or a proof the Bridge cannot replay from a file.

(Superseded on 2026-09-23 by slice 2j: a shared test workstation is bound to a
virtual member of its own and no real employee binds to it, so there is no
colleague's credential on that machine to take. The limitation above is
recorded as it stood.)

## Shared-platform transport

Source: `dragon0816/rs_workflow_system` at
`896046e8fe2170d21f9213e56e5ce2f93c05ba43`, `host-bridge/app/auth.py`,
`host-bridge/app/services/relay_worker.py`, `host-bridge/app/services/ops_client.py`
and `host-bridge/run-bridge.ps1`, read in `.scratch/rs-source` on 2026-09-23.

| Source behaviour | Observed | Decision |
|---|---|---|
| The Bridge pulls work from the dashboard's relay instead of being called: outbound long-poll (`CLAIM_WAIT_SEC = 25`), run with the ordinary job runner, post the answer back | "This is what lets the bridge stop listening ... the machine it runs on needs no inbound firewall rule, and therefore no administrator" | **PRESERVE the shape.** `poll` and `settle` are outbound only; a company computer opens no inbound port. The Telegram ingress already followed the same rule |
| A lease on each claimed job, extended by a heartbeat thread every 5 s against a 90 s lease, and a pool of four in-flight runs | Needed so "a twenty-five-minute C4C scrape keeps its claim" | **DEFER.** The platform's `poll` hands the Bridge every open job and `settle` closes it; a job whose settle is lost stays open and is offered again, and the job id as idempotency key keeps it from running twice. That is correct without a lease within one Bridge process; across a restart the engine's in-memory idempotency table is gone and a job whose settle was lost runs again, which is recorded as a known limitation. A lease, durable idempotency and concurrency belong with the first workflow that needs them |
| `OpsClient` telemetry is fire-and-forget and drops when its queue is full; the relay explicitly does not reuse it because "a dropped `complete` leaves a caller hanging for sixteen minutes" | Two transports with two loss rules | **ADAPT.** One client, two rules stated where they apply: `report` is best effort and its failure is reported, never raised; `settle` is never dropped, because an unsettled job is re-offered |
| `X-Ops-Token` / `X-Bridge-Token` headers compared with `hmac.compare_digest` | One token per machine | **ADAPT.** `Authorization: Bearer <token_id>:<secret>`; the platform compares a fingerprint with `hmac.compare_digest` (slice 2b) and the token names one member on one machine |
| `Test-DeviceBinding`: only an explicit `DEVICE_UNBOUND` means revoked; unreachable leaves the token alone and lets the bridge start | "treating a closed laptop lid or a changed network as you have been thrown out would ask people to type their password for no reason" | **PRESERVE as the transport's invariant.** The client classifies every answer, and only `token_revoked`, `token_expired` and `binding_withdrawn`, told to a Bridge that proved its secret, are `withdrawn`. A transport fault, a 5xx, a reply that is not one, and an intermediary's bare 401 are all `unreachable`, retryable, and change nothing on the Bridge |
| Exponential back-off on ingest failure, 15 s doubling to 300 s, with a circuit that blocks sends meanwhile | | **ADAPT.** `run_jobs` doubles its delay to a 300 s cap on a retryable failure and resets on success, the same rule the Telegram loop has; no circuit, because there is one loop and it is the thing being slowed |
| FastAPI application behind `requests`; the relay and the ops client each build their own HTTP session | | **REFUSE the dependencies.** The platform's install is `pydantic` alone: the server is `http.server.ThreadingHTTPServer`, the client is the `UrllibTransport` every adapter already uses, and there is no redirect following anywhere |
| `/health` answers without a token and everything else requires one | | **PRESERVE.** `GET /v1/health` says only that the process is up; every operation authenticates |
| The relay enrolls a worker with `POST /api/relay/enroll` during install and the token is useless "until an administrator" acts | Enrollment is a member's action at the dashboard | **PRESERVE the boundary.** Nothing member-facing is on this wire: invitation, registration, binding and token issue stay trusted-host calls on the platform, and a Bridge presents a token it was given |
| The dashboard is the durable store of workers, runs and events | | **DEFER.** The service serves the in-memory references and says so; a durable platform store is a later slice |

## Workflow 11

Source: `dragon0816/rs_workflow_system` at
`896046e8fe2170d21f9213e56e5ce2f93c05ba43`, `host-bridge/jobs/jira_weekly_report.py`,
`_weekly_rules.py`, `_jira_client.py`, `_excel_upsert.py`, the tests beside
them and `workflows/11_jira_weekly_report.json`, read in
`.scratch/rs-source` on 2026-09-23. The job is one module of orchestration
over pure rules, a Jira client and an Excel executor; the n8n graph is a
manual or daily trigger that posts to the Host Bridge's job runner and reports
success or failure, nothing more.

| Source behaviour | Observed | Decision |
|---|---|---|
| `_weekly_rules`: week naming in three styles, the `updated` clause composed under the user's `ORDER BY`, the `Sales`/`Salse` column alias, the newest weekly sheet by `(year, week)` strictly before the week, ADF flattened, marker headers as short lines with the observed synonyms, blocks cut at the next marker or date header, merged per day and rendered `M/D:` newest first, two dedupe rules | Every rule derived from the real workbook and project and tested against it; no I/O in the module | **PRESERVE as it stands**, ported pure into `capabilities.weekly_report.rules` with the source's tests as the oracle. The email job's effort, instrument, chipset and account derivations belong to a different entry point and are not ported |
| `build_plan`: a ticket the sheet has never seen earns a row only with marker content this week; a row already there is always refreshed; the tint names the rows that gained content, already hold it, or arrived; a block already at the top of a cell is recoloured rather than re-added; the plan is both what is executed and what the dry run prints | Written for the things that were quietly wrong (red on rows never touched, a tint on every JQL match, the run date on work written another day) | **PRESERVE**, as the typed `WeeklyReportPlan` in `capabilities.weekly_report.plan`, with the same skip reasons and the same preview shape |
| `_jira_client`: Basic `email:token` on Cloud, Bearer on Server; `search/jql` token paging with a remembered fall-back to offset paging on 404/410; offset paging on Server; comment threads re-fetched when the search truncated them; retries on 429 and 5xx honouring `Retry-After`; 401/403 an auth error | A `requests` session with the credential in its headers for its whole life; the token read from a config file with a placeholder, falling back to the environment | **ADAPT.** The same paging, fall-back, hydration and retry rules over the platform's transport, with the secret a `SecretRef` resolved per call and held nowhere; no session, no `requests`, no config file. The error body is not echoed, because Jira quotes the request back and the request carried the credential |
| Offset paging stops on a page shorter than asked for | A site that caps `maxResults` below the page size would end the week at its first page | **ADAPT.** A short page ends the search only when the site gives no `total`; with one, every page is read until it is reached |
| A `week` that is not a sheet name silently falls back to today's week | | **REFUSE.** `WeeklyReportRequest` refuses it: the parity gate says the same week selects the same keys, and a silent substitution is how a report for the wrong week gets written |
| The dry run reads the scratch sheet with `openpyxl` read-only and writes a preview JSON and an ops text under `state/` | "openpyxl only reads the file bytes; it never starts Excel and never writes" | **ADAPT.** The scratch sheet is read the same way, as a capability; the preview is the plan's own rendering and travels with the run rather than being written to a state directory |
| Excel is driven through the Host Bridge's COM API: `excel_write` upsert by key, `excel_format` resets and fills, `rich-prepend` with `tailColor`, `set-rich`, hyperlink formulas; the workbook staged to a local copy and written back once | Chosen over openpyxl for writes; character-level colour runs measured at 10–45 ms per probe; OneDrive staging measured 1001 s versus 137 s | **PRESERVE (owner decision, delegated 2026-09-23).** COM on the company Bridge, behind a `WorkbookWriter` protocol so the choice is reversible by writing another adapter and nothing else. The parity gate requires every sheet but `weekly report temp` to be unchanged, which Excel gives for nothing and a library would have to be measured for; openpyxl also does not model charts, images and some formatting that a 75-sheet hand-built workbook carries. The cost is that the adapter cannot run in CI, so it is tested through a recording writer exactly as the source tested it, and is unproven until the owner runs it |
| `rich-prepend` captures the first character's colour and writes two runs, not N | Reading a character's colour costs 10–45 ms whatever the cell's length, so a 2000-character scan took 73 s; reassigning the value destroys every run anyway | **PRESERVE**, including `tailColor`: last week's block is itself red, so letting the tail inherit would creep red over the whole history |
| The reset repaints rows the run does not otherwise touch, losing a colour applied by hand | Agreed with the user on 2026-08-01: it is the only way to make "this week" mean this week | **PRESERVE**, and say so where it happens: the text is never touched, only the colour |
| `_excel_upsert`: the last data row from the used range (hidden rows count), only managed headers written, case-insensitive header matching, the key as a `=HYPERLINK()` formula | Each rule exists because of a real bug in the older PowerShell scripts | **CARRY FORWARD** into the writer slice; none of it is needed to plan |
| Outlook draft (`jira_weekly_email`) | A second job on the same rules | **OUT OF SCOPE** for step 5; the parity gate names the workbook |

`openpyxl` 3.1.5 (MIT; `et-xmlfile`, MIT) joins the `office` extra for
reading, and `types-openpyxl` (Apache-2.0) the dev tools. It was chosen
because the source already used it for exactly this, read-only. Nothing in
this slice writes with it.

Review of the first version found two lifecycle holes and two missing caller
checks. A withdrawn binding was written as a tombstone that `bind` then read
as a duplicate, so a member taken off a device could never be put back on it;
and an expired token was never marked spent, so it both blocked its pair from
being issued another and was listed as if it still worked. Issuing and
revoking took no requester, although every other change to a device's records
does, so any caller could mint a secret that authenticates as any admitted
member; both now take the same check as binding. The review also found the
specification claiming a test for a behaviour that was not expressible, since
an authentication carried no device: it carries one now, which the transport
slice needs anyway.

Rollback removes `src/control_plane/identity.py`, the token contracts in
`common.identity`, `InMemoryEnrollmentRegistry.unbind` and their tests;
enrollment, entitlement and the member decisions keep working.


## Correction (2026-09-23): this workflow is number 11, not 7

Raised by the owner while configuring the first live run: the settings this
platform asks for are the GTM weekly report's, which the source numbers 11,
while every document here called it workflow 7.

The source has both, and they are different workflows:

| Source workflow | Its job | Migrated |
|---|---|---|
| `workflows/11_jira_weekly_report.json`, "11 · Jira GTM → Weekly Report + Email (W2)" | `jira_weekly_report` | Yes, in Phase 7 slices 3a and 3b |
| `workflows/07_jira_team_tickets_to_excel.json`, "07 · Jira Team Tickets → Excel (Issue Tracking)" | `jira_team_tickets` | No. Never inspected, characterized or ported |

What was built is unaffected. Every behaviour in the candidate row above and
in "Workflow 11" below was read from `host-bridge/jobs/jira_weekly_report.py`
and its rules module, which is workflow 11's job, and the port was tested
against that job's own tests. Only the number and the workflow file cited
beside it were wrong, in the candidate table, the migration order, the parity
gate, and from there in every later document and docstring. Those are
corrected in place so nobody follows the wrong file; this section is what
they used to say.

The wrong number entered at the first inspection on 2026-09-22 and was never
checked against the source directory, which lists both files. The owner's
decision of 2026-09-22 therefore also names `jira_team_tickets` where it
meant the weekly report; `docs/TASKS.md` carries that correction beside the
original row rather than editing it.

**Workflow 7 (`jira_team_tickets`) remains unmigrated and unassessed.** Where
it belongs in the order is the owner's decision, not this correction's; it is
recorded as an open item.


## Workflow 10

Source: `dragon0816/rs_workflow_system` at
`896046e8fe2170d21f9213e56e5ce2f93c05ba43`, `host-bridge/jobs/sales_to_chipset.py`,
`_chipset_rules.py`, `_source_snapshot.py`, the tests beside them,
`config/chipset-map.example.json`, `config/workflow-w1.example.json`,
`workflows/10_sales_opportunity_to_chipset.json` and the mapping specification
`docs/W1_MAPPING.md`, read in `.scratch/rs-source` on 2026-09-23. The job is
called W1 throughout the source. The n8n graph is a manual or Monday 08:00
trigger that posts `{"job": "sales_to_chipset", "params": {...}}` to the Host
Bridge and reports success or failure, nothing more.

What it does: reads the CMP180 project lists, explodes every project row into
chipset x technology rows, aggregates them across projects and fiscal years,
compares them with the `Chipset_requirement` sheet of the chipset readiness
workbook, and writes the result to that workbook's `temp` sheet. It never
writes `Chipset_requirement`.

`docs/W1_MAPPING.md` declares itself the single specification of the
transformation and says that where the code and the document disagree, the
document wins and the code is corrected. This migration treats it that way:
it is the acceptance specification, and `_chipset_rules.py` is the reference
implementation.

### What the parity baseline actually is

**The production rules data is not in the pinned source.** The tree contains
`config/chipset-map.example.json` and no `config/chipset-map.json`, so every
run in the pinned tree falls back to the example. The real file, which holds
the team's own chipset, vendor and brand knowledge, exists only on the
company machine. Two consequences:

1. Parity cannot be judged from this repository alone. The owner's own
   `chipset-map.json` and `workflow-w1.json` are needed for the parity run,
   and they are configuration for the host, not content for this repository.
2. The source's own tests assert the *example* file's contents in places
   (the suggested owner for Qualcomm, the four fill colours, the vendor
   order, the `SoftBand` and `Infenion` corrections). The example therefore
   travels into this repository as test data, and the tests are honest about
   testing rules against a known ruleset rather than testing the ruleset.

### Source inspection and disposition

| Source behaviour | Observed | Decision |
|---|---|---|
| `_chipset_rules`: cell cleaning, the chipset-cell parser, vendor inference, technology inference, match keys, unit and schedule parsing, company splitting, aggregation, matching against the existing sheet, row rendering, ordering and row colours | 1253 lines, one function does I/O (`load_rules`) and one reads the clock (`build_trace`); everything else is pure. 43 of the source's 45 tests cover this module and nothing else | **MIGRATE** ported pure into `capabilities.chipset_report.rules`, with the source's tests as the oracle, exactly as workflow 11's rules were. The two impure seams become parameters: the ruleset is passed in, and the date is passed in |
| `config/chipset-map.json`: separators, noise, filler and role words, vendor tokens and prefix rules, chipset aliases, technology keywords and model rules, brand and MFG alias tables, priority map and rank, suggested owners, output colours and formats | 246 lines of data in the example; no schema, no validation, and a misspelt key silently reverts to a code default | **ADAPT**. The ruleset becomes a typed contract, so a misspelt key is a refusal at load rather than a rule that quietly stopped applying. The example file ships as the default ruleset and as test data; a host may point at its own |
| `sales_to_chipset.run`: the order of operations, the guards, the parameter defaults, the statistics it returns | 683 lines, and the source's tests cover **two** of them (the protected-sheet guard). The orchestration, the reads, the writes, the dry run, the backup and the snapshot feature have no regression coverage at all | **ADAPT** into the platform's own shape: pure planning first, writing second, with the plan as the evidence. Tests are written here, because there are none to port |
| `assert_not_protected`: `Chipset_requirement` is never written, checked case-insensitively and whitespace-stripped, before the dry run and again before the write | The only part of the job with tests, and the reason the job is safe to run at all | **PRESERVE exactly**, as a refusal in the contract layer rather than an assertion inside a writer, so it cannot be bypassed by a different writer |
| Writing: `mode="replace"`, headers always rewritten at `A1`, then a formatting pass (header fill, bold, thin border, wrap text over the block, one fill per row by match level, per-cell fill and bold for changed watched fields, autofit) | A full clear-and-rewrite of one sheet, not an upsert. The formatting order is load-bearing and commented as such: the row colour says how the row matched, the cell colour says what changed on it | **PRESERVE** the operations and their order. The protocol gains a sheet-replace operation and the formatting operations it does not have yet |
| The target workbook is a macro workbook (`.xlsm`) whose headers are on **row 2**, because row 1 carries a sort button | Reading the wrong header row does not fail; it produces a sheet whose columns are named after a row of data. The job's own docstring still says `.xlsx`, and the job contains no macro handling: event suppression lives in the Bridge's Excel service | **PRESERVE** the configurable header row, as a required setting with no guessed default. Macro safety is this platform's writer's responsibility and was added for it |
| Source snapshots: each run stores the source rows it read, compares them with the previous run's, and reports what changed, with chipset, end-product and purpose changes called out as critical. The baseline advances only after a successful run | Nobody annotates the project list when they correct a chipset, so the diff is the only way a reader learns that last week's figures moved | **MIGRATE** as its own slice. It is the feature most likely to be wanted and least likely to be understood from the output alone |
| The `offline` mode that writes with `openpyxl` instead of Excel | Loses formatting elsewhere in the workbook, takes no backup, and would strip the macros from an `.xlsm` because it does not pass `keep_vba`. The source calls it development-only | **DROP.** This platform reads without Excel and writes with Excel; a second writer that silently damages the workbook is not worth carrying. A host without Excel gets the plan, which is what `weekly preview` already established |
| `dryRun` writing a CSV and a JSON preview into `state/w1-preview/` | The dry run is how the job is actually used before a write | **ADAPT.** The plan is the dry run and is the evidence, as it is for workflow 11. No preview files are written; the plan is the answer |
| n8n orchestration, Bridge HTTP transport, `PARAMS_SCHEMA`, the `x-ui` form hints | Transport and front-end concerns of the old system | **DROP.** The platform has its own transport, its own contracts and its own authorization |

### Defects found in the source, and what this migration does with each

The parity gate compares behaviour, so a defect that changes output cannot be
fixed quietly on the way through: the comparison would then fail and nobody
would know whether the port or the fix caused it. The rule adopted here is
**preserve what the gate measures, fix what is nondeterministic, unsafe or a
crash, and record every preserved defect**.

| Defect | Effect | Decision |
|---|---|---|
| Technologies that are not in the canonical list are appended in `set` iteration order | Output varies between processes | **FIX.** First-seen order. Nothing in the shipped ruleset reaches this path |
| `aggregate` returns its dropped rows by mutating an attribute on the function object, which `transform` reads back | Not re-entrant; two runs in one process leak each other's dropped lists | **FIX.** Returned properly. No output change |
| `format_schedule` renders the month with `%b`, which is locale-dependent | On a non-English Windows the whole column silently changes language and stops round-tripping | **FIX.** An explicit English month table. On an English host the output is identical |
| `parse_schedule` accepts a month of `0` or `13` to `99` from a `YYYY/M` cell and hands it to `date()` | Uncaught `ValueError`, which on this platform would be an unexplained failed step | **FIX.** Treated as unparseable text, which is what every other unparseable schedule does |
| `_kw_regex` builds a corrupted character class for any keyword containing a space | `wi fi` also matches `wi[fi` and `wi]fi` | **FIX.** The intended pattern. It only removes matches that should never have happened |
| `parse_units` replaces a comma with a space, so a text cell `1,200` parses as nothing and silently moves from the total to the notes | Under-counts the business figure | **PRESERVE**, recorded. It changes a number the gate compares, and the owner should decide after seeing one real run |
| `render_row` prepends a new trace block without removing the previous one | The `Comments` cell grows on every run, without bound | **PRESERVE**, recorded. Workflow 11 solved the same problem by retiring last week's marks; doing that here is a change the owner should ask for, not one made in passing |
| A genuine unit total of exactly `0` renders as the unknown marker `?` | Zero and unknown are not the same thing | **PRESERVE**, recorded |
| `_paren_is_tech` tests role words as substrings, so a parenthesis containing `pa`, `ic`, `end`, `lna` or `fem` anywhere is treated as a role note | `(Japan)` is a role note because it contains `pa` | **PRESERVE**, recorded. It changes which text lands in the chipset name |
| The partial-match rule is an unanchored substring test in both directions | A synthetic placeholder key can match a real row | **PRESERVE**, recorded. Placeholders are dropped before matching by default, so the path is unreachable with the shipped ruleset |
| `match_key` concatenates tokens with no separator and is order-sensitive | `MT79 77` and `MT7977` collide; `A+B` never matches `B+A` | **PRESERVE.** This is the identity the whole match evidence in `W1_MAPPING.md` was validated against. Changing it would change which rows are reported as already tracked |
| Dead code and dead configuration: `_looks_like_model`, `version`, `split.keepCompositionTogether`, `split.lineSeparator`, `split.sharedPrefixExpansion`, `output.colors.header` | Read by nothing | **DROP.** A typed ruleset cannot carry a key nothing reads without saying so |

### Parity gate — workflow 10

- The same project rows are included: the status filter, the all-empty row
  skip and the per-source `enabled` flag select the same rows.
- Every project row explodes into the same chipset x technology rows, with
  the same display spellings, the same vendors and the same technologies.
- Aggregation matches: the same business totals with the same
  once-per-opportunity counting across fiscal years, the same earliest
  schedule, the same highest priority, the same brand and MFG lists in the
  same order.
- The same rows are reported as `tracked`, `tracked-other-tech`, `partial`
  and `new`, against the same existing sheet.
- Only the `temp` sheet is created or changed. `Chipset_requirement` is
  byte-identical afterwards, and so is every other sheet. The workbook still
  has its macros.
- The written sheet has the target's own headers in the target's own order
  and spelling, including the trailing space in one of them, followed by the
  trace columns when they are asked for.
- The formatting is the same: header fill, bold and border; wrap text over
  the block; one fill per row by match level; changed watched fields filled
  and bolded per cell; columns autofitted.
- A run that writes nothing produces the same plan as the old job's dry run,
  row for row.
- The evidence is the plan and the applied record, as for workflow 11: the
  digests of the `temp` sheet before and after, the backup's path, every
  count, and every row that was dropped with the reason it was dropped.
