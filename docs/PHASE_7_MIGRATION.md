# Phase 7 source inspection and disposition

Initial source: `dragon0816/rs_workflow_system`, commit
`896046e8fe2170d21f9213e56e5ce2f93c05ba43`, inspected read-only on
2026-09-22. The company computer can run the pinned old Host Bridge paths and
therefore supplies the comparison baseline. No source repository is modified.

## Initial candidates and decision

| Candidate | Proven behavior that must survive | Decision |
|---|---|---|
| `workflows/07_jira_team_tickets_to_excel.json`, `host-bridge/jobs/jira_weekly_report.py` | Manual/daily trigger; no HTTP retry; fixed week/JQL window; scratch-sheet-only writes; upsert by Jira key; marker-filtered comment prepend with local and remote dedupe; formatting retirement; dry-run preview | **PRESERVE + ADAPT** after company-Bridge enrollment. Characterize the job's rules and project them into typed capability/workflow contracts. Keep Jira and Excel execution on the company Bridge. Do not copy credentials, file paths or n8n transport configuration. |
| `workflows/13_release_package.json`, `host-bridge/jobs/release_package.py` | One blocked run per working copy; no automatic HTTP retry; required values; version/branch/requirements/release.yaml rules; safe inbox names; dry-run without commit/push; explicit commit/push | **PRESERVE + ADAPT** after workflow 7. First run only against an isolated test repository with dry-run. Keep Git/file execution on the company Bridge and retain explicit approval for push. Do not interpret publication or device binding as release authority. |
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
