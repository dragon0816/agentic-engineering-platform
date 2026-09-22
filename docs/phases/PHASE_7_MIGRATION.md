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

The shared-platform computer cannot use company LDAP or company resources. A
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
   alike: the request names this device, the device is active, the actor holds
   an active binding, and on a company workstation the actor is the registered
   owner. A refusal is a typed `LocalAgentOutcome` with a code; nothing is
   dispatched, nothing is recorded, and the Bridge's event log stays empty.
4. An admitted message goes through the existing `Gateway` with the request's
   actor, namespace and trace and the ingress as its channel, so deterministic
   routing, Bridge policy and the workflow engine apply exactly as they do for
   any other caller. An admitted `RemoteWorkflowJob` executes its exact workflow
   through `Gateway.execute_workflow` with no routing and no model; a workflow
   not installed on this Bridge is refused before anything runs.
5. Every workflow run the Agent starts is recorded as a `LocalRunSummary` in
   durable local state under the platform actor who started it. A later record
   for the same run may change its status, never its actor: actor switching
   never changes an existing run's ownership (slice 1, item 5).
6. `host_runtime.state.SqliteLocalState` is the durable local inventory and run
   state on one local SQLite file, single-writer, every write one committed
   transaction. Installation applies the same verification rule as the in-memory
   reference (`common.distribution.verify_installation`, now shared): every
   artifact's digest is checked and the whole plan is refused before one row
   changes. The inventory and runs survive closing and reopening the file, and
   `snapshot(observed_at)` yields the authoritative `BridgeStateSnapshot` the
   control plane projects.
7. Company work needs no control plane present. A test drives a workflow whose
   manifest declares no central service through the Agent with no Registry,
   control plane or transport object in the process at all.
8. Nothing here authenticates, downloads, polls or opens a socket. Registry
   synchronization is slice 2f; Telegram sender mapping and polling is slice 2e.

Tests precede implementation and cover: membership validation; request
validation; owner-only admission on a company device and bound-actor admission
on a shared test device, with the refusal codes and an empty event log; a routed
message reaching a real workflow through the Gateway; a remote job executing its
exact workflow and a job for an uninstalled workflow refused; run ownership that
cannot change; whole-plan install refusal leaving the SQLite inventory untouched;
inventory and runs surviving reopen; the snapshot carrying both; and a run with
no control plane in the process.
