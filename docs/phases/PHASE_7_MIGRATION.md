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

CI remains inert. Production-like evidence is produced only by an explicitly
enrolled company/test Bridge. Secrets stay in its execution environment and are
never copied into Registry assets, invitations, evaluation cases, traces or Git.

## Migration order

1. Enrollment foundation: invitation-only users, independent Bridge identity,
   one-user company workstation and multi-user shared test workstation contracts.
2. Deployment: package and install Agent + Bridge on a company workstation;
   verify registration, binding, capability advertisement and a read-only probe.
3. Workflow 7: `07_jira_team_tickets_to_excel.json` /
   `jira_weekly_report.py`, report generation against a test workbook.
4. Workflow 13: `13_release_package.json` / `release_package.py`, first in dry-run
   and an isolated test repository, then an explicitly approved non-production push.
5. Knowledge platform: adopt and exercise a copy before any source vault changes.
6. Model adapter live smoke checks when a host and approved endpoint credentials
   are available; these do not block workflows that do not use a model.
7. Cut over each source entry point separately after its parity gate and rollback
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
   explicit platform actor and Bridge ID, creates only its workspace, venv and
   non-secret `host.json`, and is safe to repeat.
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
deployment. Slice 2b must add the authenticated invitation/device enrollment host
flow and read-only shared-platform connectivity probe before workflow migration.
