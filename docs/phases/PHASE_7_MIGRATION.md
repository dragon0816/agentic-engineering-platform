# Phase 7 — End-to-end migration and controlled deprecation

Status: active. Owner decisions recorded 2026-09-22 (Asia/Taipei).

## Goal and deployment boundary

Prove selected source behavior on the real deployment topology before any old
entry point is retired:

```text
Shared-platform computer (control plane)
        |
        +-- invitation-only platform account and Bridge enrollment
        |
Company Windows computer (one employee)          Shared test Windows computer
Agent + Bridge + corporate resource access       Agent + Bridge, one virtual member
old Host Bridge remains available for parity     one shared Windows account
```

The shared-platform computer is an internal-network shared workstation
(owner decision, 2026-09-22). It is reachable from company computers on the
internal network and several people can sign in to it, so its own store is not
confidential from them, and it cannot use company LDAP or company resources. A
user first receives an invitation, registers at the shared-platform entry point,
and then enrolls a Bridge. Platform identity, Bridge device identity, runtime
authorization, and credentials for Jira/GitLab/SAP-C4C remain separate.

The company computer has one employee user and may access corporate resources.
The shared test computer cannot access corporate resources. Owner decision
(2026-09-23): **every machine is bound to exactly one platform member.** A
shared test computer is bound to a virtual member of its own, a virtual
employee, and no real employee binds to it; employees who need it drive it
through the Telegram ingress, and the request records which of them asked.
Every run retains its platform actor and Bridge identity. Workspaces are separated for
organization and cleanup, but this is not an OS security boundary: users of the
same Windows account can read one another's local files and processes. Interactive
work is serialized to one user/run at a time.

The company workstation's Agent interface, installed Skills/Workflows and complete
run state are local. It uses the shared platform to publish, discover and obtain
assets, but already-installed local behavior does not require that connection unless
its manifest declares `central_required`. The shared platform additionally controls
Bridge computers through governed remote jobs. A company workstation accepts only
its one bound owner; a shared test workstation accepts the virtual member it runs
as, and work an employee asked for through an ingress runs as that member and
records who asked. A Telegram adapter may deliver commands to the resident local
Agent only after mapping the sender to a platform actor. The shared platform never becomes the authority
for local run state.

CI remains inert. Production-like evidence is produced only by an explicitly
enrolled company/test Bridge. Secrets stay in its execution environment and are
never copied into Registry assets, invitations, evaluation cases, traces or Git.

## Migration order

1. Enrollment foundation: invitation-only users, independent Bridge identity, and
   device-profile contracts for the company workstation and the shared test
   workstation (one member each, since slice 2j).
2. Deployment: package and install Agent + Bridge on a company workstation;
   verify registration, binding, capability advertisement and a read-only probe.
3. Local-first control contracts: Registry package acquisition and verified local
   inventory; timestamped shared status projection; governed, member-scoped remote
   jobs for enrolled Bridge computers.
4. Local Agent interface and authenticated transports: operate company work locally,
   synchronize Registry packages, and let shared test Bridges poll approved jobs.
5. Workflow 7: `07_jira_team_tickets_to_excel.json` /
   `jira_weekly_report.py`, report generation against a test workbook.
6. Workflow 13: `13_release_package.json` / `release_package.py`, first in dry-run
   and an isolated test repository, then an explicitly approved non-production push.
7. Knowledge platform: adopt and exercise a copy before any source vault changes.
8. Model adapter live smoke checks when a host and approved endpoint credentials
   are available; these do not block workflows that do not use a model.
9. Cut over each source entry point separately after its parity gate and rollback
   rehearsal pass. Repository-level deprecation is last.

## Parity gates

Parity means the important behavior and safety invariants match. It does not mean
byte-identical files when timestamps, workbook metadata or archive metadata differ.
Every production-like run exports redacted evidence that the Phase 6 harness can
grade; credentials and sensitive payloads remain on the Bridge.

### Workflow 7 — Jira team tickets to Excel

- The same reporting week, base JQL and updated window select the same Jira issue
  keys, subject to an explicit safety cap.
- Only `weekly report temp` is created or changed. Existing `YYYY_NW` sheets are
  read/seed sources and remain unchanged.
- Rows are upserted by Jira key. A new ticket without marker-tagged comment content
  in the reporting window is not added; an existing row is refreshed.
- Marker-tagged weekly comments are prepended once, in red, while older comment
  text remains and uses its normal color. A repeated run does not duplicate text.
- This week's key highlight and new-row formatting match the declared source rules;
  stale weekly marks are retired without removing the table structure.
- A dry run produces a preview and performs no Excel or Outlook write. Jira/auth,
  workbook and Bridge errors produce a failed run with no false success claim.

Evidence: normalized Jira key set, plan summary, workbook sheet hashes before and
after, normalized rows for the scratch sheet, formatting assertions, repeat-run
comparison, run trace and source/platform status. The actual workbook is not
uploaded to the shared platform unless separately approved.

### Workflow 13 — release package

- Required inputs are rejected when absent. Branch naming, selected/published
  chipset version, next/explicit release version and requirements lines match.
- The working copy is serialized on its Bridge. Two release jobs cannot switch the
  same checkout concurrently.
- Input selections are bare names inside the configured inbox (or one upload set);
  traversal, missing files, unknown kinds and mixed upload/name modes fail closed.
- The normalized package file manifest, destination directories, requirements.txt
  and release.yaml semantic fields match. Timestamp-only metadata is ignored.
- Dry-run may prepare the isolated working copy but creates no commit and no push.
  A non-dry run is attempted only after separate approval; commit/push evidence
  must match the declared policy and an existing release must not be overwritten.
- Timeout or lost connectivity is not automatically retried because the prior run
  may still be executing. Re-run is an explicit owner decision after inspection.

Evidence: input digest/selection manifest, normalized Git diff and file hashes,
release.yaml semantic projection, requirements lines, branch/commit/push state,
run trace and source/platform status. Customer file contents and credentials stay
on the Bridge.

### Knowledge platform

Use a full copy. Compare content identities, immutable Raw files, source/page/image
provenance, duplicate/drift behavior, query citations, whole-plan refusal, backups
and a completed restore rehearsal. The original vault is not the first test target.

## Rollback and deprecation

Source repositories and the working old Host Bridge are retained and frozen at a
recorded commit while parity runs. No source repository is deleted in Phase 7.
Each candidate has its own cutover record: source revision/config backup, new asset
version, evidence references, known differences, rollback command/runbook, owner
approval and observation result. The platform owner approves cutover; the operator
of the affected company Bridge performs and records the rehearsal.

On failure, stop new submissions, inspect any uncertain side effect, restore data
from the candidate-specific backup when needed, and return the entry point to the
pinned old Host Bridge. A source entry point may be frozen/disabled only after its
new path passes parity and rollback rehearsal. Archive is a later owner decision;
deletion is outside this phase.

## Slice 1 — enrollment foundation acceptance

1. Invitation metadata never contains an invitation token, password or credential.
   Only a trusted host that already validated the invitation proof may accept it.
2. An invitation is for one actor and is accepted once. Users and devices can be
   disabled independently.
3. A company workstation has dedicated-user Windows mode, corporate resource scope
   and exactly one active platform member. A shared test workstation has shared-user
   Windows mode, external-only scope and may bind multiple invited users.
4. A binding grants use of that Bridge only. It does not grant a capability,
   resolve a secret or imply that a published asset may execute.
5. Every admitted execution subject names both actor and Bridge. Membership and
   device/user status are checked at use time; actor switching never changes an
   existing run's ownership.
6. The reference implementation is an in-memory control-plane proof with no LDAP,
   password store, HTTP server, production RBAC, installer or live Bridge call.

Tests precede implementation and cover validation, one-time invitations, owner
isolation, the two device profiles, single/multi-user binding, disable behavior,
Bridge advertisement matching, snapshot isolation and the absence of credentials
or execution authority.

## Slice 2a — company host technical preview acceptance

The first deployment artifact intentionally stops before authenticated transport
and production capabilities. It establishes a reviewable installation boundary
that can be carried to a company computer while the enrollment host is designed.

1. The artifact is one hash-manifested ZIP for Windows AMD64 and CPython 3.12.
   It installs from bundled wheels without network access and records the source
   revision and exact target in `manifest.json`.
2. Installation is per Windows user in a versioned directory. It requires an
   explicit platform actor and derives a stable default Bridge ID from the normalized
   Windows computer name, with an explicit override for collisions. It creates only
   its workspace, venv and non-secret `host.json`, and is safe to repeat. A computer
   name is device metadata and never authentication proof.
3. `aep-host doctor` checks the OS, exact Python minor, company device profile and
   workspace without opening a socket or invoking a capability. It states that no
   live transport and no workflow 7/13 capability exist in this preview.
4. `aep-host enrollment-request` exports a closed `BridgeDevice` plus an empty
   `BridgeRegistration`. The output is not invitation proof, authentication,
   authorization or a secret, and does not grant execution.
5. Every bundled payload is SHA-256 checked before install. The bundle contains no
   local configuration, token, password, browser profile, company path or state.
6. Uninstall is dry-run by default and may remove only the versioned directory
   beneath `%LOCALAPPDATA%\\AgenticEngineeringPlatform`.
7. CI builds and installs the package locally on Windows without any live endpoint
   or external-system call. A real company-computer run remains owner evidence.

This sub-slice is installation and device preflight, not completion of Phase 7
deployment. Following slices must add the authenticated enrollment transport, local
Agent interface and read-only connectivity probe before workflow migration.

## Slice 2b — local-first distribution and member-scoped control acceptance

1. A published asset package is a Registry record with an exact scoped identity,
   artifact reference and SHA-256. Discovering or planning it grants no execution.
2. A local host verifies every selected artifact before changing its installed
   inventory. The inventory remains usable without the Registry once installed.
3. The Bridge owns authoritative installed-asset and run state. A shared-platform
   view records when the snapshot was observed/received and reports `stale` after a
   declared interval; it never invents current state while disconnected.
4. A remote job names an ingress (`shared_platform` or `telegram`), exact Workflow,
   actor, Bridge, trace and matching runtime authorization. Secret values and
   arbitrary shell commands have no field.
5. Company workstations accept only their registered/bound owner. Shared test
   workstations accept their bound actors. Both preserve the actor and expose a
   bounded poll queue; Telegram never bypasses the same membership/policy checks.
6. This slice has no socket, downloader, code loader or process execution. It is the
   contract/reference proof for later authenticated transports and local UI work.

## Slice 2d — resident local Agent and durable local state acceptance

Migration step 4 names three things: a local Agent interface, Registry
synchronization and authenticated Bridge polling. They are three slices, because
the first needs no network and the other two need an authentication design.
This slice is the resident Agent on the Bridge computer and the durable local
state it owns. It is exercised entirely in-process; no socket is opened.

1. `common.local_agent.BridgeMembership` is the Bridge computer's own copy of
   who may use it: its `BridgeDevice` and the `BridgeBinding`s for that device.
   The contract refuses a binding for another device, a repeated actor, and, on
   a company workstation, more than one active binding or an active binding that
   is not the registering owner. It grants nothing beyond use of the device.
2. `common.local_agent.LocalAgentRequest` is one request to the resident Agent
   from any ingress (`local`, `shared_platform`, `telegram`): actor, Bridge,
   namespace, message, trace and optional session. It refuses credential
   material and unknown fields. A remote job arrives as the existing
   `RemoteWorkflowJob`, unchanged.
3. `host_runtime.agent.LocalAgent` admits before it routes, on every ingress
   alike: the request names this device, the device is active, on a company
   workstation the actor is the registered owner, and the actor holds an active
   binding. The device half of that rule is `common.enrollment.admit_device`,
   the same function the control plane's remote-job reference applies, so the
   two cannot drift. A refusal is a typed `LocalAgentOutcome` with a code and
   nothing else; nothing is dispatched, nothing is recorded, and the Bridge's
   event log stays empty.
4. An admitted message goes through the existing `Gateway` with the request's
   actor, namespace and trace and the ingress as its channel, so deterministic
   routing, Bridge policy and the workflow engine apply exactly as they do for
   any other caller. An admitted `RemoteWorkflowJob` executes its exact workflow
   through `Gateway.execute_workflow` with no routing and no model, with the
   job id as the idempotency key so a job delivered twice joins the run it
   already started. The engine answers for what is installed on this Bridge:
   its pre-flight rejection comes back as a workflow result that started
   nothing, and no run is recorded for it.
5. Every workflow run the engine actually starts is recorded as a
   `LocalRunSummary` in durable local state under the platform actor who
   started it. A later record for the same run may change its status, never
   its actor: actor switching never changes an existing run's ownership
   (slice 1, item 5). A run that outlives the caller's wait is recorded as it
   stands and settled to its final state in the background; `settled()` waits
   for that. A record that cannot be written is reported on the outcome as
   `unrecorded`, never raised over the workflow's result, because the result
   is what the caller needs most.
6. `host_runtime.state.SqliteLocalState` is the durable local inventory and run
   state on one local SQLite file, single-writer, every write one committed
   transaction, reads under the same lock, timestamps stored in UTC, and every
   failure a `LocalStateError` code with nothing echoed. Installation applies
   the same verification rule as the in-memory reference
   (`common.distribution.verify_installation`, now shared): every artifact's
   digest is checked and the whole plan is refused before one row changes. The
   inventory and runs survive closing and reopening the file, the file refuses
   another device's identifier, and `snapshot(observed_at)` yields the
   authoritative `BridgeStateSnapshot` the control plane projects.
7. Company work needs no control plane present. A test drives a workflow whose
   manifest declares no central service through the Agent with no Registry,
   control plane or transport object in the process at all.
8. Nothing here authenticates, downloads, polls or opens a socket. Registry
   synchronization is slice 2f; Telegram sender mapping and polling is slice 2e.

Tests precede implementation and cover: membership validation; request
validation; owner-only admission on a company device and bound-actor admission
on a shared test device, with the refusal codes and an empty event log; a routed
message reaching a real workflow through the Gateway; a remote job executing its
exact workflow once however often it is delivered; a pre-flight rejection that
starts nothing and records no ghost run; a run that outlives the wait settled
to its final state; a workflow that ran reported even when its record cannot
be written; run ownership that cannot change and updates that never go
backwards; time order independent of the clock's offset; whole-plan install
refusal leaving the SQLite inventory untouched; inventory and runs surviving
reopen, the snapshot carrying both, and the file refusing another device; and a
run with no control plane in the process.

## Slice 2e — Telegram ingress acceptance

The pinned `telegram-local-agent` channel was inspected read-only at
`4b40a215909e4fdd4b65519d70669a84e9abd43d` (`docs/PHASE_7_MIGRATION.md`,
"Telegram ingress"). What survives: outbound long polling, a numeric sender
checked before anything is routed, and a slash command that reaches the
deterministic router without a model. What does not: a token in a
configuration file, an empty allowlist that admits everyone, HTML
presentation, and attachment handling.

1. `channels.telegram.TelegramIngressConfig` names the bot token as a
   `SecretRef`, the Bridge it serves, the namespace requests are routed in,
   and a sender map of numeric Telegram ids to platform actors, one to one. A
   token pasted anywhere in the record is refused: the shape of a Telegram
   bot token is now part of the repository's one `SECRET_PATTERN`, so the
   registry, the evidence grader, the trace and the model adapters refuse or
   redact it too. An empty map admits nobody.
2. `TelegramIngress.poll_once` calls `getUpdates` over the same `Transport`
   the model adapters use, with the same failure rules (`models.wire`,
   parametrized by a code prefix), resolving the token through the host's
   `CredentialResolver` on every call and holding it nowhere. A transport
   fault, a non-200 status, a malformed reply or an unresolvable credential is
   a typed `Failure` with the token already redacted (the shared helper now
   redacts before it trims, so a token straddling the cut cannot survive as a
   fragment), and the offset stays where it was. HTTP 409 is
   `telegram_conflict`. `run` stops on any failure that will not fix itself
   (a conflict, a revoked token, a credential the host cannot produce) and
   returns it; a retryable failure is waited out with a doubling delay.
3. Every update is a `TelegramDelivery`. A sender not in the map is
   `unmapped_sender` before its text is looked at, and is not answered: a
   stranger who finds the bot learns nothing and drives no outbound call. A
   non-text message, an empty one, or one the request contract refuses for
   credential material is `unsupported_content` and is not forwarded.
   `/help`, `/start` and `/status`, in any spelling Telegram sends
   (`/status@botname`, trailing words), are `answered` locally; `/status` is
   the Agent's snapshot in words, read off the event loop. Handling one update
   never takes the loop down: what raised becomes a `failed` delivery with the
   error named and redacted, and the sender is told the request could not be
   handled.
4. Everything else becomes a `LocalAgentRequest` with ingress `telegram`, the
   mapped actor, the configured Bridge and namespace, a trace named for the
   update and a session named for the chat. `/skill command rest` is
   translated to the platform's `skill.command rest` form so it reaches the
   deterministic router; other text is passed as written. The Agent admits or
   refuses by the same membership rule as every ingress: a mapped sender whose
   actor is not bound on the Bridge is `refused` with the Agent's code, and
   nothing is dispatched or recorded.
5. Replies are plain text in pieces Telegram accepts, naming identities,
   statuses and codes and never a payload, and redacted. A reply that cannot
   be sent is recorded on the delivery as `replied=false`, never raised over
   the outcome.
6. An update id handled in this process is not handled again if Telegram
   redelivers it; the batch is confirmed by advancing the offset only after
   its updates were handled. Redelivery across a restart is a known
   limitation recorded in the handoff.
7. Nothing here imports a Telegram library, opens an inbound port or stores
   an attachment. The runtime install stays `pydantic` alone.

Tests precede implementation and cover: the configuration refusing a pasted
token, a duplicate sender or actor, and a non-https origin, and normalizing a
trailing slash; the token shape and the `bot_token` field name refused by the
shared secret scanner; an unmapped sender neither routed nor answered, with
one credential resolution for the poll itself; an unbound actor refused by the
Agent with nothing dispatched; a mapped and bound sender's text and slash
command reaching the real release workflow through the Agent and being
recorded under the actor with a trace named for the update; `/help`,
`/start@botname extra` and `/status@botname` answered without a run; the token
appearing in the Bot API URL and nowhere on the ingress, resolved once per
call; a transport error carrying the URL deep in its text reported without any
token fragment, an unresolvable credential non-retryable and a 429 retryable;
the loop stopping on a conflict, a 401 and a missing credential and backing
off on a 503; a redelivered update handled once and a batch handled in order
with the offset confirmed; non-text and credential-bearing messages not
forwarded; an update whose handling raised recorded as `failed` while the
next one in the batch is still handled; reply chunking and scrubbing without
truncation; and a failed reply recorded, not raised.

## Slice 2f — the company host runs what it was given

Slices 2d and 2e built the resident Agent and a channel into it, but nothing
assembled either on a real computer: the only wiring was in a test module, the
preview CLI could inspect the machine and nothing else, and the Telegram
offset lived in memory, so a restart replayed whatever was not confirmed.

1. `host_runtime.host.HostLayout.under(workspace_root)` is the one place a
   company host keeps what it needs: `membership.json`, `grants.json`,
   `assets/skills/*.json`, `assets/workflows/*.json`, `telegram.json` and
   `state.sqlite`. The installer creates the directories; the operator fills
   them. There is no second configuration file naming paths.
2. `build_runtime(config)` assembles the Agent from those files and returns a
   `HostRuntime` holding the Agent, the durable state and, when configured,
   the Telegram ingress. Nothing is discovered: a manifest is loaded because
   it is in the assets directory, a capability handler exists because the
   package ships it, and a grant applies because the grants file says so. A
   file that is missing, describes another device, or cannot be read is a
   `HostError` naming the file and the reason, never its contents.
3. Routing on a company host is deterministic only. No model is configured,
   so an unrecognized message is `needs_input` rather than a guess. The one
   capability handler the package ships (`filesystem/read-file`) is installed
   and rooted at the workspace; a step naming any other capability fails
   closed, because installing a manifest does not install code.
4. Installing an asset is not permission to run it. With no grants file the
   policy refuses every dispatch, and a grant that omits an approval the
   capability's own policy requires refuses it too. The route still resolves
   and the run is still recorded: what did not happen is the dispatch.
5. `aep-host` gains `ask`, `status` and `telegram` beside `doctor` and
   `enrollment-request`. `ask` sends one local request as the device owner or
   `--actor`, in the host's namespace or `--namespace`; the platform does not
   guess a namespace, so a host that names none must be told per request.
   `status` prints the Bridge's own snapshot. `telegram` polls until
   interrupted, or once with `--once`.
6. `doctor` reports what the host has been given as well as what the machine
   is: `membership`, `assets` and `state`, with a third check status
   `pending` for what has not arrived yet. A freshly installed host is not
   broken, it is not enrolled, and the report says `resident agent: pending`
   without failing. `status` remains this machine's preflight and nothing
   else, so a stale membership record in a retained workspace never aborts a
   reinstall; what the host was given is `runtime` and the checks themselves.
   Reporting changes nothing: the state file is opened only if it exists, and
   then read-only, so no table is created and no schema version is migrated.
   A file that cannot be read is a failed check, never a traceback.
7. The Telegram offset is durable. `SqliteLocalState` keeps one cursor per
   channel, refuses to rewind it, and the ingress reads and advances it
   instead of holding it in memory, so a restart resumes where the last
   confirmed batch ended. A cursor that cannot be read stops the poll, because
   polling without it would replay a batch that was already acted on; a cursor
   that cannot be advanced is reported beside the deliveries that were
   handled. Both are retryable: the usual cause is another process holding the
   file for a moment, which is not a reason to end the ingress.

Tests precede implementation and cover: the layout under one workspace and a
relative workspace refused; a complete host reading a real workspace file end
to end through the CLI and recording the run under the actor who asked; what
the operator sees for a run and for `status`; a dispatch refused without a
grant and without an approval; an unbound actor refused with nothing recorded;
a missing, invalid and foreign membership record each named; an unreadable
asset named without its contents; `doctor` reporting pending, ready and failed
without writing anything, and a corrupt state file reported by `doctor` and
refused by `ask` rather than raised; a version-1 state file still at version 1
after a report, and the read-only store refusing to write, refusing another
device's file and refusing one that is not there; a Telegram ingress built only when its secret is
mapped and refused when it names another Bridge; the `telegram` command
without a configured ingress; a host that will not guess a namespace; the
durable offset surviving a restart and refusing to rewind; and a cursor that
cannot be read stopping the poll.

## Slice 2g — the member decides what a device may run

Owner decision (2026-09-22): **a platform user decides, for each device they
may use, which Workflows, which Skills and which tools that device may run for
them.** Nobody decides for anyone else, and a decision reaches no further than
the devices that user is bound to.

The three lists are different things and stay different. A Workflow or Skill
selection decides what the device **installs**, so an unselected manifest sitting
in the assets directory is not installed and a route to it resolves to nothing.
A tool selection decides what the Bridge policy **grants**, because a tool is a
capability and the policy is what authorizes a dispatch. A Workflow whose steps
need a tool the user did not select still installs, and its step still fails
closed: choosing a Workflow is not choosing the tools it reaches for.

1. `common.authorization.DeviceAssetSelection` is one user's decision that one
   device may run one asset for them: `bridge_id`, `actor`, `kind`
   (`workflow`, `skill` or `capability`), `asset`, `decided_at`, `status`, and
   for a tool an `approval_ref` with the `approved_by` who gave it. A selection
   names no permission and no policy reference: a user chooses **which** assets,
   never what they are allowed to do, so a decision cannot widen itself.
2. `common.authorization.DeviceAuthorization` is every active decision for one
   device at one moment: the device, when it was issued, and the selections.
   It refuses a selection for another device and two selections of the same
   asset by the same actor. `for_actor`, `installable` and `tools` read it.
3. `control_plane.authorization.InMemoryAuthorizationRegistry` refuses a
   selection whose actor is not an active bound member of that device, a
   Workflow or Skill that is not published in the Registry with that kind, and
   a tool the device does not advertise. A device says what it can run; a user
   cannot select a tool that is not there.
4. A tool whose own `CapabilitySpec` requires approval cannot be selected
   without an `approval_ref`, and the `approved_by` must itself be an active
   member of that device. On a company workstation the one member is the owner,
   so the owner approves their own irreversible tools and the record says who
   and when; on a shared test workstation another bound member may approve.
   Whether an irreversible tool should need a second party is an open question
   for the owner, recorded rather than decided here.
5. A decision dated in the future is refused where it arrives, because a
   bundle refuses a decision newer than itself and one such record would
   leave that device with no authorization at all. A tool whose
   specification declares no policy reference is refused too: a grant names
   the policy it was made under, so such a tool cannot be granted to
   anybody, and refusing it when it is chosen keeps one unusable tool from
   breaking the whole device's authorization later.
6. `grants(bridge_id)` derives the device's `CapabilityGrant`s from the
   advertised `CapabilitySpec`, not from the selection: the permissions and
   policy references are the ones the capability itself declares. Grants are
   per actor, so on a shared test workstation one member's decision authorizes
   that member's runs and nobody else's, which is what the platform already
   guarantees by keeping the actor on every run.
7. A company host reads `authorization.json` when it is there. Only the
   Workflows and Skills it names are installed, and the grants are derived from
   its tool selections; `grants.json` remains the way to configure a host that
   has no control plane, and both files at once is refused rather than
   merged. `doctor` reports the decisions as their own check, counts the
   assets this host would actually install, and shows a conflict before a
   command fails on it.

Tests precede implementation and cover: a selection refusing a permission it
was not asked for, approval only for a tool, `approval_ref` and `approved_by`
together, and credential material refused; a bundle refusing a foreign device
and a repeated asset; an unbound actor, an unpublished Workflow, a kind that
does not match the publication, and an unadvertised tool each refused; a tool
requiring approval refused without one and refused when the approver is not a
member; a derived grant carrying the specification's permissions and policy
references rather than anything the user wrote; two members of a shared device
each getting their own grants and neither authorizing the other; revocation
removing a grant; and, on a real host, only the selected Workflow installed,
the selected tool authorizing a run end to end, the same run refused once the
tool is revoked, and both authorization files at once refused.

## Slice 2h — a member's identity decides what they may use

Owner decision (2026-09-22): **a Bridge is bound to a user, and the user's
authentication decides which Workflows and Skills they may use.** Slice 2g let
a member choose what their devices run; this decides what there is to choose
from, and it is the platform's own record that decides it, not a claim
arriving with the request.

The platform has no company directory, so where a member's groups come from
has to be answered: the invitation says. An invitation already names one
actor and is accepted once; it now also names the teams or organizations that
acceptance grants, and the platform user records them. An authenticated actor
therefore carries who they are and until when, and never what they belong to,
because a membership claim that travels with a request is a membership claim
that can be widened by whoever sends it.

1. `Invitation.groups` and `PlatformUser.groups` record which teams,
   organizations or services accepting an invitation makes the actor a member
   of. Both default to none, so an invitation that grants no membership still
   makes a platform user, and the existing records stay valid.
2. `common.identity.AuthenticatedActor` is what an entry point produces after
   it decided who someone is: the actor, the `method` it used, when it
   happened and when it stops being true. It carries no credential and no
   group. `valid_at(now)` is false once it expires, and the contract refuses
   an expiry that is not after the authentication.
3. `common.identity.entitled(metadata, actor, groups)` decides whether one
   actor may use one published asset. An unpublished asset is never usable.
   The owner may always use it, whether the owner is that actor or a group
   the actor belongs to, and so may a recorded contributor. Otherwise
   `public` and `organization` are usable by any member of the platform, and
   nothing else is usable by anybody else. That last line decides `team` and
   `private` together, and for a group-owned asset they come to the same
   answer, because the owning group is the team.
4. `InMemoryAuthorizationRegistry.select(identity, selection)` requires an
   authenticated actor whose session is still valid and who is the member the
   decision belongs to: a member decides as themselves, and an expired
   session decides nothing. A Workflow or Skill the actor is not entitled to
   is refused, and the groups are read from the platform's record of that
   user, never from the identity. Revocation takes the same identity.
5. `available(identity)` answers the question the decision names directly:
   which published Workflows and Skills this member may use. It is the list a
   member chooses from, and choosing is still a separate act that grants
   nothing by itself. A list of what somebody may use is itself something
   only they should see, so it answers for the same people a decision does: a
   valid session, a member the platform knows, and one it has not disabled.
   It offers only the kinds a decision can name.
6. Entitlement is checked when a decision is made, not when a run happens: an
   authorization is a record of what was decided, and a member whose
   entitlement is withdrawn keeps their device's existing bundle until the
   control plane issues a new one. Reissuing on a change is part of the
   delivery slice, and the staleness is recorded rather than hidden.

Tests precede implementation and cover: an invitation carrying groups and an
accepted user recording them; an authenticated actor refusing an expiry that
is not after its authentication, and expiring; entitlement for each visibility
against an owner, a group member, a contributor and a stranger, and an
unpublished asset usable by nobody; a member deciding as themselves only; an
expired session deciding nothing; a Workflow the member is not entitled to
refused while one they own is not; groups read from the platform's record and
not from the identity; the available list naming exactly what a member may use and
refusing an expired session, an unknown actor and a disabled one; and a
group-owned asset answering the same at `team` and `private` while a
user-owned one marked `team` stays with its owner.

## Slice 2b — Bridge access tokens

Owner decision (2026-09-23): **binding a user to a machine issues an access
token for that pair, kept on the Bridge; several members on one machine hold
several tokens, and a Bridge presents one of them to authenticate with the
shared platform.** The owner named the precedent: the pinned Host Bridge asks
for a user sign-in when a machine is not bound and exchanges it for that
machine's own token (`docs/PHASE_7_MIGRATION.md`, "Bridge access tokens").

This is the last piece of who-may-do-what. It produces the
`AuthenticatedActor` slice 2h already consumes, so a token turns into an
identity, an identity into entitlement, and entitlement into what a member may
choose for their devices.

1. `common.identity.BridgeAccessGrant` is the platform's record of one token:
   `token_id`, the `actor` and `bridge_id` it was issued for, a `fingerprint`
   of the secret, when it was issued, when it expires if it does, and its
   status. The secret is not in it, and no contract in the repository has a
   field it could be put in.
2. `common.identity.IssuedAccessToken` is the one moment the secret exists
   outside the Bridge: the grant plus the value, returned once by issuing and
   deliberately not a `Contract`, because a contract is serializable,
   validated and loggable, which is everything a secret must not be.
3. `control_plane.identity.InMemoryAccessTokens.issue(requested_by, actor,
   bridge_id)` issues only for a member the platform currently admits on that
   device, so a token cannot exist without the binding that justifies it, and
   only for a caller who is that member or may administer the device: minting
   a secret that authenticates as somebody is no smaller an act than binding
   them, and takes the same check. Revoking takes it too. It generates the
   secret itself with the standard library's `secrets`; a caller-supplied one
   is refused below a minimum length, because the verification below is sound
   only for a value with real entropy. One pair holds one active token.
4. `authenticate(token_id, secret, now=)` verifies the secret before it says
   anything about the token's state, and an unknown `token_id` and a wrong
   secret are the same answer: `authentication_failed`. Telling them apart
   would tell somebody who holds neither that a token exists. Comparison is
   `hmac.compare_digest` over the fingerprint, as the source compares its own
   token.
5. Once the secret matched, the holder is told exactly why it did not work:
   `token_revoked`, `token_expired`, or `binding_withdrawn` when the platform
   no longer admits that member on that device, which covers a revoked
   binding, a disabled member and a disabled device alike.
6. A successful authentication produces an `AuthenticatedActor` naming the
   member and the machine the token was issued for, whose session ends no
   later than the token does. The `method` names the token so the evidence
   says how the decision was made. An entry point where somebody signs in
   directly has no machine, so that stays absent rather than invented.
7. A token that has expired is spent: it stops being listed as one the device
   can be used with, and stops standing in the way of issuing another for that
   pair. A withdrawn binding is history in the same way, so a member taken off
   a machine can be put back on it.
8. `InMemoryEnrollmentRegistry.unbind` withdraws a binding, and
   `revoke_for(requested_by, actor, bridge_id)` revokes the tokens that
   binding justified.
   Revoking means a person has to be at that keyboard again, which is what
   makes revoking mean something.

Tests precede implementation and cover: a token issued only for an admitted
member; two members on one machine holding two tokens with different secrets;
the grant never carrying the secret and the issued token not being a contract;
authentication producing an identity that the entitlement registry accepts; an
unknown token and a wrong secret answering identically; a revoked, expired and
withdrawn token each naming its own reason only after the secret matched; an
identity naming the machine its token was issued for; a token id that is not
even the shape of one answering like any other unknown token; issuing and
revoking refused for a caller who is neither the member nor an administrator
of that device; a session ending no later than its token; a supplied secret
refused when it is too short; a spent token no longer listed and no longer in
the way of a new one; and unbinding revoking the tokens it justified while
leaving the member able to be bound again.

## Slice 2j — one member per machine, and who asked

Owner decision (2026-09-23): every machine is bound to exactly one platform
member; a shared test machine gets a virtual member of its own and no real
employee binds to it; employees reach it through Telegram, and the record says
which employee asked. The owner also decided what not to build: being an
invited, authenticated member is the gate for using the platform's resources,
so a request is not narrowed further by who asked for it, and the list of
people who may drive a machine stays host configuration rather than something
the control plane delivers.

A shared test workstation is not a desk that several people take turns at. It
is wired to particular instruments and laid out as a test environment, and the
employees who use it want that environment, not that computer. Giving it a
virtual member of its own says that in the model: the machine belongs to its
rig, and people reach the rig through an ingress.

This removes the shared-workstation credential problem rather than mitigating
it. One member on a machine means one token on that machine, so there is no
colleague's credential there to take.

1. A device holds one active binding, whatever its kind. The enrollment
   registry refuses a second (`device_single_user`, which replaces the
   company-only code), and a Bridge's own `BridgeMembership` refuses one too,
   so the rule holds on both sides of a delivery.
2. `LocalAgentRequest.on_behalf_of` and `LocalRunSummary.on_behalf_of` record
   the member who asked, when that is not the member who runs. They are
   recorded and never consulted: admission, grants and entitlement all read
   the acting member, so nothing about this field can widen what may happen.
   A field that looks like authorization and is not would be worse than no
   field at all, so both contracts say so where they are declared.
3. A company workstation refuses delegation outright
   (`delegation_not_allowed`). The architecture says it accepts only its one
   bound owner, and a request performed on somebody else's behalf is not that.
   Only a shared test workstation runs work for a member who is not bound to
   it.
4. The Telegram ingress maps a sender to a platform actor as before. When that
   actor is the machine's bound member, the request runs as them and records
   nobody else. When it is not, and the machine is a shared test workstation,
   the request runs as the bound member on behalf of the mapped actor.
5. Attribution is as good as the ingress and no better. A Telegram request
   carries evidence of which account asked; a person at that machine's own
   keyboard is the bound member and there is nobody else to record. The sender
   map stays trusted host configuration, so the operator decides who may drive
   a machine, and the platform does not.
6. Follows from 5, and is the price of the owner's decision not to have the
   control plane deliver the requester list: **taking somebody off a shared
   machine is a host action, not a platform one.** Disabling a member or
   withdrawing a binding does not stop their sender-map entry from driving that
   machine, because the request runs as the virtual member and `on_behalf_of`
   is never consulted. Before this slice the same request was refused
   `actor_not_bound`. Removing the entry from the host's `telegram.json` is
   what revokes the access; offboarding has to include it. Slice 2i does not
   change this, and moving the list into the authorization bundle is the
   change that would.
7. An approver on a tool selection is checked against the platform's active
   members rather than the device's. One member per machine would otherwise
   leave `approved_by` able to name only the acting member, so a colleague the
   platform knows may now approve work on a machine they are not bound to. The
   rule is not that the approver is a second person: `approved_by == actor` is
   still accepted, as it was on a company workstation before this slice, where
   the device's one member was the only approver available. Requiring a second
   person is a policy the owner has not asked for and is recorded as an open
   item in `docs/TASKS.md`.

Tests precede implementation and cover: a second binding refused on both kinds
of device, and a Bridge membership refusing one too; a request and a run
recording who asked while admission reads only the acting member; a company
workstation refusing delegation; a mapped Telegram sender who is the bound
member running as themselves with nothing recorded; a mapped sender who is not
running as the virtual member on their behalf, with the run naming both; an
unmapped sender still ignored; a shared machine with one virtual member holding
exactly one token; an approver who is an active platform member accepted while a
stranger and a disabled member are refused and the acting member's own approval
still stands; and the sender map alone granting access to a shared machine, with
an actor the platform has never heard of driving it.

## Slice 2i — authenticated shared-platform transports

Migration step 4 named three things; the resident Agent (2d) and the Telegram
ingress (2e) are done, and this is the third: the wire between a Bridge and
the shared platform. Everything a Bridge says to the platform is one of six
operations, each presented with the Bridge access token of slice 2b, and
everything the platform says back is a closed contract. Nothing member-facing
is on this wire: a member signs in at the platform's own entry point, which
this slice does not build, and a Bridge only ever acts as the one member it is
bound to.

The pinned Host Bridge's shape is kept where it was right and refused where it
was not (`docs/PHASE_7_MIGRATION.md`, "Shared-platform transport"): outbound
only, so a company computer opens no inbound port; a doubling back-off after a
failure; and the one invariant carried from `Test-DeviceBinding` — **unreachable
is never treated as revoked.** Only the platform saying so, to a Bridge that
proved its secret, is revocation. Everything else leaves the token, the
authorization and the installed assets exactly where they are.

1. `common.sync` holds the wire: `ProbeReply`, `AdvertiseRequest`/`Reply`,
   `SyncRequest`/`SyncReply`, `ReportRequest`/`Reply`, `PollRequest`/`Reply`,
   `SettleRequest`/`Reply` and `WireFailure`. A sync reply carries the device's
   `DeviceAuthorization`, an `InstallationPlan` for what the Bridge said it
   does not have, and the artifact bytes for exactly those packages; the
   contract refuses a plan without its bytes and bytes without a plan. A
   settle names one of `ran`, `rejected`, `cancelled`, and carries a
   `LocalRunSummary` exactly when it ran. No contract on this wire has a field
   a secret could be put in.
2. `control_plane.service.ControlPlaneService` is the platform's side,
   transport-agnostic: every operation takes a token id and secret, decides
   who is asking through `InMemoryAccessTokens.authenticate`, and acts only on
   the device the token was issued for. A payload naming another device is
   `device_mismatch`, whatever it says. The service is what a test drives
   directly and what the HTTP server hands requests to. It serves the
   in-memory references; a durable platform store is a later slice, and the
   spec says so rather than pretending otherwise.
3. `control_plane.http` is that service over HTTP from the standard library
   alone: `POST /v1/<operation>` with `Authorization: Bearer <token_id>:<secret>`,
   JSON in and out, a body limit, one request per connection, no redirect, no
   request logging, and one unauthenticated `GET /v1/health` that says
   nothing but that the process is up. Failures come back as `WireFailure`
   codes with the status they deserve, and a contract the platform could not
   build while answering is its own `internal_error`, never the Bridge's
   `invalid_request`; nothing in a reply echoes a request.
4. `host_runtime.sync.PlatformClient` is the Bridge's side. It resolves the
   token's secret through a `SecretRef` on every call and holds it nowhere,
   refuses a plain-HTTP platform anywhere but loopback, and classifies every
   answer into exactly one of: `answered`; `unreachable` (a transport fault,
   a 5xx, a reply that is not one), retryable; `withdrawn` (the platform told
   a Bridge that proved its secret that its token is revoked or expired or its
   binding withdrawn); `rejected` (the secret did not match: this host's
   configuration is wrong); `refused` (anything else the platform declined).
   Only `answered` changes anything on the Bridge.
5. `synchronize` is the one operation that writes. It refuses before calling
   when `grants.json` is present (two answers to one question), tells the
   platform what is installed, and applies the reply in this order: the whole
   plan verified by `verify_installation` (every digest, this device, nothing
   already installed); every artifact parsed as the manifest its package kind
   names and carrying the identity the package claims; every file it would
   write checked against a hand-placed asset of the same identity, which is a
   conflict unless the bytes are identical; then the manifests written, the
   inventory recorded in one transaction, and `authorization.json` replaced
   atomically. A refusal before the first write leaves the workspace
   untouched; the one write that can fail after the inventory is recorded,
   the bundle, is reported as a refusal that also says what was installed,
   so nothing is hidden. A second sync with nothing new installs nothing and
   rewrites only the bundle.
6. `advertise` sends what this host can run — the capabilities its Bridge
   policy could ever dispatch — as a `BridgeRegistration`, and the platform
   replaces the device's advertisement with it
   (`InMemoryEnrollmentRegistry.advertise`); what is installed travels in the
   snapshot, and what is authorized comes back in the bundle. `report` sends the
   Bridge's authoritative `BridgeStateSnapshot`, which the platform projects
   and never rewrites. `probe` is read-only and is what an operator runs to
   ask "does the platform still know this machine as me": it changes nothing
   on either side.
7. Jobs. `poll` returns the open jobs for this device, oldest first. The
   Bridge runs each through `LocalAgent.execute` — the same admission, the
   same engine, the job id still the idempotency key — and settles it: `ran`
   with the run record, `rejected` when the Agent refused it or the engine
   answered before starting anything, `cancelled` when the platform had asked
   for that before the Bridge got to it. A settle is final, so it says what
   actually happened: a run that outlives the wait is waited for until it
   ends before it is settled, and a job the platform asks to cancel after
   this Bridge already ran it (a settle that was lost, then a cancel) is
   settled `ran`, because the idempotency key knows. A job whose settle could
   not be delivered stays open at the platform and is offered again; the
   Bridge joins the run it already started and settles it again, so nothing
   runs twice within one process. That guarantee is the engine's in-memory
   idempotency table: a company host runs its engine without a journal, so a
   job whose settle was lost and which is re-offered after `aep-host jobs`
   restarts runs again. Durable idempotency for polled jobs is a known
   limitation, recorded in `docs/TASKS.md`. A job id is therefore held to
   the shape of an idempotency key at the contract. A `RemoteJobRecord`
   gains those three final states and the run
   that settled it; `poll` no longer returns a settled job, `cancel` refuses
   one, and a settle for another device's job or with a run that names a
   different actor or workflow is refused. `RemoteWorkflowJob` gains
   `on_behalf_of` with the same meaning as everywhere else since slice 2j,
   and `execute` records it.
8. `run_jobs` loops poll, execute, settle and report until asked to stop, with
   the Telegram ingress's rule: a retryable failure is waited out with a
   doubling delay, and one that will not fix itself — a poll answered
   `withdrawn`, `rejected` or `refused`, or a settle answered `withdrawn` or
   `rejected`, which also stops the rest of that batch — ends the loop and is
   returned. A settle the platform declined for one job (`job_settled`,
   `job_missing`, `job_mismatch`) is that job's business: it is recorded on
   the delivery and the loop goes on, because the next poll simply does not
   offer that job again. The snapshot is reported after a batch that did
   something and otherwise once a minute, not on every idle poll. The loop
   never deletes or rewrites anything on a failure: a Bridge that has been
   thrown out keeps doing local work with what it has, which is the
   local-first rule.
9. The host. `CompanyHostConfiguration.platform` is optional: `base_url`,
   `token_id` and the `SecretRef` naming the token's secret, which the host
   maps to an environment variable as it does the Telegram token; the value is
   never in a file. `aep-host` gains `probe`, `sync` and `jobs [--once]`, and
   `doctor` gains a `platform` check that reads the configuration and opens no
   socket. A host without a platform configured is a host that works locally,
   and every earlier command still runs on it.
10. Nothing here is a durable platform store, a member sign-in, an installer of
    anything but Skill and Workflow manifests, or TLS termination. The server
    takes an `ssl.SSLContext` and wraps its socket with it when given one; a
    platform reached over the network is expected to be served that way, and
    the client's loopback exception exists so the wire can be exercised in a
    test without a certificate.

Tests precede implementation and cover: every wire contract's closed shape and
refusals; the service answering each operation for a real token and refusing a
wrong secret, a revoked token, a withdrawn binding and another device's payload
with the right code; the HTTP server and client end to end on a loopback port,
including health without a token, an unknown operation, a body that is not
JSON, an oversized body and a missing header; a probe that names the actor and
device; the five classifications with unreachable retryable and nothing
changed on the Bridge for any of them; a sync that installs a Workflow and a
Skill onto a real host, records them in SQLite, writes the bundle, and leaves
the rebuilt host running the synced Workflow through the real Gateway; a
second sync that installs nothing; a sync refused for `grants.json`, a tampered
artifact, a manifest claiming another identity and a hand-placed conflict, with
the workspace untouched; an advertisement that replaces the device's; a
snapshot that the platform projects as online; a job polled, run, settled
`ran` and gone from the queue; a cancelled job settled without running; a job
for a Workflow this host lacks settled `rejected`; a settle refused for a
settled job and for another device; the loop ending on a rejected token and
backing off on an unreachable platform; every failure message free of the
secret; and the CLI commands with their exit codes and the doctor's platform
check in each of its three states.

## Slice 3a — workflow 7: the weekly report's rules, the Jira fetch and the plan

Migration step 5 is workflow 7, `07_jira_team_tickets_to_excel.json` /
`jira_weekly_report.py`: the GTM tickets updated this week, upserted into the
scratch sheet of the team's weekly workbook with the marker-tagged comments of
the week prepended in red. Its parity gate is above. The source job is one
module of orchestration over three of rules, a Jira client and an Excel
executor; the rules are pure and were tested against the real workbook and the
real project, so they are ported as they stand
(`docs/PHASE_7_MIGRATION.md`, "Workflow 7").

This slice is everything up to the point where the workbook is written: the
week and its window, the Jira fetch, the reading of the scratch sheet, and the
plan — which is also the dry-run preview and the evidence. It stops there on
purpose: how the platform writes a workbook (Excel through COM on the company
Bridge, as the pinned Host Bridge does, or a library such as `openpyxl`, which
this slice adds for reading only) changes what parity can claim about the rest
of the workbook, and is recorded as a decision for the owner rather than made
here. Nothing in this slice writes a workbook, opens Excel or touches Outlook.

1. `capabilities.weekly_report.rules` is the source's `_weekly_rules` ported
   pure: week naming in the three styles the workbook has used, the week's
   range, the `updated` clause and its composition under the user's `ORDER
   BY`, the column contract with the `Sales`/`Salse` alias, the newest weekly
   sheet chosen by `(year, week)` strictly before the week reported, ADF and
   plain comment bodies flattened alike, marker headers matched as short
   lines with the observed synonyms, blocks cut at the next marker or date
   header with a leading date kept as the block's own, blocks merged per day
   and rendered newest first in the workbook's `M/D:` shape, and the two
   dedupe rules that keep a second run in one week from stacking the block.
   Every rule has the source's own test as its oracle.
2. `integrations.jira.JiraClient` is the source's client over the platform's
   transport: Basic `email:token` for Cloud and Bearer for Server, the secret
   resolved per call through a `SecretRef` and held nowhere; token-paged
   `POST search/jql` for Cloud with a remembered fall-back to offset paging
   when a site answers the probe 404 or 410, offset-paged `POST search`
   otherwise, both under the safety cap and both reading every page while
   the site's `total` says more remain; comment threads re-fetched when the
   search truncated them; bounded retries on 429 and 5xx honouring `Retry-After` up to a minute, with an
   injectable sleeper; 401 and 403 a typed `jira_auth` refusal; every failure
   a code with a redacted message. `UrllibTransport` gains `request` for a
   method other than POST; `Transport` itself is unchanged.
3. Four read capabilities, each with a spec, closed input and output
   contracts, and a handler the host constructs from its configuration:
   `weekly_report.resolve_window` (the request's week or today, the window,
   the stamp date, the composed JQL and the cap), `jira.search` (issues
   normalized to the report's fields with their comments flattened to text),
   `excel.read_scratch_sheet` (headers, `Key -> Comments` of the scratch
   sheet or of the seed sheet when the scratch sheet is absent, the seed
   chosen strictly before the week, and a digest of the scratch sheet's rows
   as it stands), and `weekly_report.plan`, the source's `build_plan` as a
   typed `WeeklyReportPlan`: rows to upsert by key, new and updated keys, the
   blocks to prepend with their markers, the blocks already present that
   only need their colour back, what was skipped and why, the keys to tint,
   and the rendered preview, which says in capitals when the cap cut the
   search short. A ticket the sheet has never seen earns a row only with
   marker content this week; a row already there is always refreshed.
4. The plan is the evidence the parity gate names: the normalized key set,
   the plan summary, the scratch sheet's digest before, the normalized rows
   and the repeat-run comparison (a second plan against a sheet that already
   holds the block skips it). It carries no credential and is graded by the
   Phase 6 harness like any other run.
5. `capabilities.weekly_report.manifest` ships the Skill (`weekly`, with
   `preview`) and the Workflow `engineering/jira-weekly-report-preview` that
   runs the four steps in order and names them as the capabilities it needs,
   so a host lacking one refuses the run before its first step; `aep-host
   export-assets` writes them as
   the JSON files a workspace or the Registry takes. The host gains
   `integrations.jira` (the connection, its secret a `SecretRef` mapped like
   every other) and `integrations.weekly_report` (the workbook, the scratch
   sheet, the week style, the base JQL, the markers, the colours and the cap,
   with the source's defaults); a host so configured installs the four
   capabilities, and one without them still runs everything it did. The
   host's step timeout becomes configuration (`capability_timeout_seconds`,
   default ten minutes): the platform's thirty seconds suits a file read,
   not a Jira search with a throttle waited out; a caller's wait
   (`workflow_wait_seconds`, default fifteen minutes) is never shorter, so
   the caller is not told `workflow_timeout` while the step may still finish.
   A step's handler that raises `ValueError` fails the step as
   `invalid_input`: a window that ends before it starts, a week the calendar
   has not got, a sheet without `Key` and `Comments` columns.
6. `openpyxl` (MIT, 3.1.x, maintained) joins the `office` extra for reading a
   workbook without Excel; `types-openpyxl` joins the dev tools. On a host
   without the extra `doctor` says so, and a run that reaches the sheet step
   fails closed rather than raising past the executor. Nothing here writes
   with it.
7. `BridgeExecutor` validates a step's inputs strictly against JSON rather
   than strictly in Python: a step's arguments are what an earlier step's
   output serialized to, so a list is a tuple and an ISO string is a date,
   while `"1"` is still not an integer. Typed data between steps was not
   possible before this; the existing workflows pass scalars and are
   unaffected.

Tests precede implementation and cover: the ported rules against the source's
own cases; the Jira client over a fake transport for both auth modes, both
paging styles, the cap, comment hydration, a 429 waited out and a 401 refused,
with the secret in no failure; the scratch-sheet reader on a workbook built
on disk with a scratch sheet present and absent, the seed chosen strictly
before the week, and a stable digest; the plan for each rule of the parity
gate — a new ticket without content not added, an existing row refreshed, a
block prepended once and skipped on the repeat, tinting only what gained
content or arrived, markers and lines counted; and the preview workflow
running end to end on a real host through the real Gateway with a fake Jira
and a workbook on disk, writing nothing.

## Slice 3b — workflow 7: writing the plan into the workbook

Slice 3a stopped at the plan. This is the other half: executing it against the
team's workbook, with the parity gate's evidence on both sides of the write.

Owner decision, delegated (2026-09-23): the owner asked for the slice to be
finished and for problems to be raised, having been given the choice between
Excel through COM and a library with a recommendation for COM. **COM on the
company Bridge** is therefore what the writer does, for the reason recorded in
`docs/PHASE_7_MIGRATION.md`: the parity gate requires that every sheet but
`weekly report temp` is unchanged, which Excel gives for nothing and a library
has to be measured for. The choice is reversible: the executor writes through
a `WorkbookWriter` protocol and knows nothing about COM.

1. `integrations.excel_writer` is the protocol and its operations as
   contracts: `Upsert` (managed headers only, by key), `Fill`, `ClearFill`,
   `FontColour`, `Border`, `Hyperlink` (an `=HYPERLINK()` formula, never a COM
   Hyperlink object, which leaks references and keeps Excel alive), `TextRun`
   for a rich cell, and the reads a write needs (`fills`, `cell_text`,
   `last_row`). `ExcelComWriter` is the one adapter, `pywin32` imported
   lazily so every other host still loads; a host without it says so rather
   than raising. It carries the source's `_excel_upsert` rules: the last data
   row comes from the used range because hidden rows count, only managed
   headers are ever written so the hand-kept `Comments` column survives, and
   header matching is case-insensitive.
2. `capabilities.weekly_report.apply` executes a plan in the source's order,
   which is the order the marks mean what they say: back up, stage, ensure the
   scratch sheet, **verify the sheet is the one that was planned**, upsert,
   retire last week's marks across the whole sheet, tint what gained content,
   border and pink what is new, recolour the blocks already present, link
   every key, then prepend each block in red with a black tail. A block the
   writer reports as already present is recoloured instead, because the reset
   has just turned it black.
3. The digest is the guard the source did not have: a plan carries the scratch
   sheet's digest as it stood, and applying it to a sheet that has since
   changed is refused (`sheet_changed`) rather than written. Presence counts
   as much as content, so a plan made without a scratch sheet is not written
   into one somebody has made since; a plan for a sheet that is still absent
   creates it from the seed. The guard runs before anything is copied or
   backed up, so a refused run leaves nothing behind.
4. Staging, as measured in the source: the workbook is copied somewhere no
   sync client is watching, driven there, and written back once. A workbook
   somebody has open is refused before anything is copied, and a run that does
   not finish leaves the real workbook untouched and says where the staged one
   is. Staging is configuration and can be turned off.
5. `weekly-report/apply` is the first capability in this repository with a
   side effect: `write`, approval required, so the Bridge policy refuses it
   without an `approval_ref` and the member's decision must carry one. The
   Workflow `engineering/jira-weekly-report` is the preview's four steps plus
   apply; `jira-weekly-report-preview` stays exactly as it was, so a dry run
   remains a separate asset a member can be given on its own.
6. `WeeklyReportApplied` is the evidence: the digests before and after, the
   backup's path, what was inserted, updated, tinted, marked new, recoloured
   and prepended, and every comment cell that could not be written. A failed
   prepend does not fail the run — the source kept going and reported them —
   but it is in the evidence and in the outcome.

Tests precede implementation and cover: every operation the executor issues,
in order, against a recording writer, for a plan with a new row, a refreshed
row, a block to prepend and a block to recolour; the reset covering the whole
sheet and not only the rows touched; only this job's pink retired and the
member's own status colours left alone; a second apply in the same week
prepending nothing and recolouring instead; a sheet that changed since
planning refused with nothing written; a workbook somebody has open refused
before it is copied; a run that fails part way leaving the real workbook
untouched with the staged copy named; a failed prepend reported without
failing the run; the hyperlink written as a formula; the capability refused
without an approval; and the whole Workflow end to end on a real host with a
recording writer, with the evidence carrying both digests.


## Slice 3c — the offline bundle carries workflow 7

Slices 3a and 3b finished workflow 7 in the repository and told the owner to
install it with `pip install "agentic-engineering-platform[office,windows]"`.
That instruction could not work and never could: **this platform is published
to no package index**, public or internal. The owner's first attempt on a
company computer failed against the corporate index, as it had to.

The supported install is the offline Windows preview bundle, which carries
every wheel it needs and installs with `--no-index`. It carried `pydantic`
only, so the bundle a member can actually install could not have run the
workflow the two previous slices shipped. No new behavior is added here; what
changes is that the shipped artefact contains what its own documentation says
it does.

1. The `excel` extra (`openpyxl`) is named on its own rather than reached
   through `office`, so a company Bridge installs a spreadsheet reader and not
   the whole PDF/PPTX/DOCX stack. `windows` (`pywin32`) is the Excel bridge.
   Both are imported lazily, so every other host is unaffected.
2. `scripts/build_windows_preview.py` requires the wheels those extras need
   (`openpyxl`, `et_xmlfile`, `pywin32`) in the dependency directory and
   refuses to build a bundle without them. A bundle missing a wheel is a
   failed install on a machine with no index to fall back on, so it is
   refused where it is built rather than where it is used.
3. `install.ps1` installs the requirement `agentic-engineering-platform`
   with its `excel` and `windows` extras from `wheels/` alone. The corporate
   pip index on a company computer is neither needed nor consulted.
4. CI downloads the three packages into the bundle it builds, and the Windows
   install job then imports `openpyxl` and `win32com.client` from the
   installed environment and checks that `export-assets` wrote the
   weekly-report manifests. An offline bundle that cannot import what it
   claims to carry fails the build.
5. Every install instruction that named a package index is corrected:
   `HANDOFF.md`, `deploy/windows-preview/README.md`, and the doctor's own
   message when the workbook reader is missing. The host runtime's
   `LIMITATIONS` no longer says workflow 7 cannot run here; it says what
   workflow 7 needs and that `doctor` reports whether this host has it.

Because the bundle now always carries the Excel bridge, an importable
`win32com` stopped being evidence of anything: a doctor that answered "can
write it" on the strength of it would promise a write that fails at the first
`DispatchEx` on a workstation without Excel. `require_com` therefore resolves
the `Excel.Application` ProgID, which reads the registry and starts nothing,
and `excel_missing` (no Excel on this machine) is told apart from
`library_missing` (no bridge in this installation), because different people
fix them.

Verified by installing the built bundle into a clean directory: the doctor
ran, `openpyxl` and `pywin32` were importable and `aep-host export-assets`
wrote all three manifests. `require_com()` reports `excel_missing` on this
machine, which is the correct answer: there is no Excel here. That is an
install check, not the parity run; the parity run still needs Excel and Jira
credentials on a company workstation.


## Slice 3d — a bundle nobody can extract is a bundle nobody can install

Reported by the owner on 2026-09-23, on the first download of the bundle
slice 3c fixed: `install.cmd` stopped at

```text
Bundle file is missing: wheels\agentic_engineering_platform-0.1.0-py3-none-any.whl
```

The zip was complete and its hashes were right. Windows refuses a path of 260
characters or more unless long paths are enabled, and Explorer extracts what
fits and leaves out the rest without saying so. The bundle is downloaded as a
CI artefact and extracted twice before it is run — the artefact folder, whose
name carries a 40-character commit, then the folder made from the zip's own
name — and inside an ordinary `Downloads` folder the two longest wheel names
needed 268 and 263 characters. Those two were missing; the other fourteen
files were there. The installer could only report the first absence, which
reads as a broken download and sends the reader to the wrong place.

1. The bundle's own names are the only part of that path we control, so they
   shrink: `aep-windows-preview-0.1.0` in place of
   `agentic-engineering-platform-windows-preview-0.1.0`, and the same for the
   CI artefact. At the exact location that failed the longest path falls
   from 268 to 209 characters, and the budget the builder enforces, which
   assumes a longer Windows user name, falls from 276 to 217. Either way
   there are more than forty characters left for a deeper folder.
2. `worst_case_path` states the arithmetic — Downloads, the artefact folder,
   the extracted folder, the bundle root, the file — and the builder refuses
   to produce a bundle any of whose files would exceed it. The failure now
   happens where the names are chosen instead of on a company computer. The
   test asserts the refusal against the exact names that broke, so the
   arithmetic is checked against the incident it comes from.
3. `install.ps1` measures the longest path in its manifest before verifying
   anything and names the cause and the fix: extract somewhere shorter, such
   as `C:\aep`, and nothing is wrong with the download. The missing-file
   message says to extract the whole zip again rather than implying the
   bundle is corrupt.

Verified by building the bundle with the new names, extracting it, installing
it end to end (doctor reports the same nine checks) and running the installer
from a deliberately deep folder, where it refuses with the path length and
the remedy instead of a missing file.


## Slice 3e — the grants the weekly report actually needs

The owner installed the bundle and asked what to do next. Following the
preview's own README produced

```text
run run-...: failed, 0 step(s) completed
failure: permission_denied
```

before Jira was ever reached. The page said that the grant for
`weekly-report/apply` must carry an `approval_ref`, which read as "only the
write needs one". Every one of the five capabilities declares
`approval_required`, the four reads included, so a grant without a reference
is not a weaker grant: it is no grant, and `LocalPolicy` returns an empty
authorization that names nothing. An operator sees a refusal with no cause.

1. The README writes out `grants.json` in full, all five, each with its own
   permissions, policy reference and an approval reference, and says plainly
   that the reads need one too. It also says that `membership.json` must name
   the operator, and that the number of completed steps in a failed run is
   where it stopped.
2. The first walkthrough had the same defect: it told an operator to run
   `files.read` and never showed the grant that needs, so the page's very
   first command always failed. It is written out too.
3. `test_weekly_report_documented_grants` parses the README's own JSON and
   puts it through the real `LocalPolicy` against every capability a host
   installs: each one has a documented grant, each documented grant is
   accepted, and dropping the approval reference refuses each in turn. The
   page and the policy now fail together or not at all.

Verified by building the whole workspace an operator would write — host
configuration, membership, grants, exported assets and a workbook — and
running it: `doctor` reports `host status: ready` with every check passed,
and `weekly.preview` routes to the installed Workflow and reaches the Jira
step, which is as far as a machine with no Jira credential can go.
