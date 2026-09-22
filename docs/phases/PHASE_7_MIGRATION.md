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
Agent + Bridge + corporate resource access       Agent + Bridge, many platform users
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
The shared test computer cannot access corporate resources; several invited
platform users may bind to one Bridge while sharing one Windows account. Every
run retains its platform actor and Bridge identity. Workspaces are separated for
organization and cleanup, but this is not an OS security boundary: users of the
same Windows account can read one another's local files and processes. Interactive
work is serialized to one user/run at a time.

The company workstation's Agent interface, installed Skills/Workflows and complete
run state are local. It uses the shared platform to publish, discover and obtain
assets, but already-installed local behavior does not require that connection unless
its manifest declares `central_required`. The shared platform additionally controls
Bridge computers through governed remote jobs. A company workstation accepts only
its one bound owner; a shared test workstation accepts its bound platform users. A
Telegram adapter may deliver commands to the resident local Agent only after mapping
the sender to that platform actor. The shared platform never becomes the authority
for local run state.

CI remains inert. Production-like evidence is produced only by an explicitly
enrolled company/test Bridge. Secrets stay in its execution environment and are
never copied into Registry assets, invitations, evaluation cases, traces or Git.

## Migration order

1. Enrollment foundation: invitation-only users, independent Bridge identity,
   one-user company workstation and multi-user shared test workstation contracts.
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
