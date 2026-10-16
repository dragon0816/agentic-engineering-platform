# Member publish to the Shared Platform

Owner request: 2026-10-15. Status: **approved 2026-10-15. Control plane, Agent Web and CLI done; owner and access decisions of 2026-10-15 (below) done, live test pending.**

This closes the open item 5 of `docs/phases/ASSET_OWNERSHIP.md` ("member publish route
and UI").

## Goal

A person publishes a Skill or Workflow from their own Personal Agent (Agent Web or CLI)
to the Shared Platform. A platform administrator reviews it. Only an approved version
enters the catalog, where other members can select it for their Bridges.

## Owner decisions (2026-10-15)

1. **Identity.** The Agent publishes as the person (a member login), not as the
   machine. The first publisher of a name becomes its owner (ASSET_OWNERSHIP rule 1).
2. **Review.** Every submission waits in a review queue. An administrator approves or
   rejects it in the Member Portal. Only an approval publishes.
3. **Entry points.** An Agent Web "Publish to shared platform" action, plus
   `aep-host assets publish` for automation.

   *As built:* the Agent Web entry point is a card headed "Publish to the shared
   platform" (Skill or Workflow picker, change, who can use it, note, "Publish for
   review"), not a per-row action in the installed lists.

## What exists (code survey 2026-10-15)

- Registry, ownership and version rules: `AssetOwnershipService.publish_as` /
  `publish_next` (`control_plane/ownership.py`), and `SqliteRegistry.publish_as`
  (`control_plane/registry_sqlite.py`), which checks the artifact hash, owner,
  co-editors and that the version is above every existing one.
- The artifact of a Skill or Workflow is the manifest's UTF-8 JSON
  (`control_plane/preview_catalog.py`). The Agent installs those exact bytes as
  `assets/{skills,workflows}/{ns}__{name}__{version}.json` (`host_runtime/sync.py`).
  Publishing is the inverse: read the installed manifest and send it.
- Member Portal: JSON over POST with `Authorization: Bearer <session>`; a `Login`
  bearer (30 days, revocable, stored in the platform's SQLite) mints sessions
  (`member_http.py`, `member_login.py`). Bodies are capped at 256 KiB.
- `assets/next-version` already returns the next version for a change level.
- Missing:
  - any upload route;
  - any pending or review storage (`PublishedAssetPackage` must be `published`);
  - any review check in the Registry;
  - any Agent-side code that builds a package or talks to the Member Portal.

## Design

### 1. Agent login (identity)

- **Issuing.** A new portal operation `logins/issue-agent` (member session required)
  issues a `Login` labelled `Personal Agent` and shows its bearer once.
  - The portal gets a "Connect a Personal Agent" button that displays the code to copy.
  - Invitations stay single use; the browser keeps its own login.
- **Storing.** The Agent stores the bearer through the existing credential mechanism:
  - host.json `platform.member_credential: {"name": "platform_member_login"}`;
  - the secret is mapped in `credentials` to an environment variable;
  - the file never holds the value (`reject_embedded_secrets` still applies).
- **Using.** Before each portal call, the Agent exchanges the login for a one-hour
  session (`POST /v1/member/session`) and keeps the session only in memory.
- **Revoking.** The member revokes the login from the portal. The Agent then gets
  `authentication_failed` and Agent Web says to reconnect.

### 2. Submission (member routes, member session)

| Operation | Body | Result |
|---|---|---|
| `assets/submit` | `kind` (skill/workflow), `change` (patch/minor/major), `note`, `manifest` (the manifest JSON object) | `submission_id`, assigned `version`, `status: pending` |
| `assets/submissions` | — | the member's own submissions with status and reviewer reason (designed as `assets/submissions/mine`; built as `assets/submissions`) |
| `assets/submissions/withdraw` | `submission_id` | a pending submission is withdrawn |

**Checks on submit, before anything is stored:**
1. Parse the manifest as `WorkflowManifest` or `SkillManifest`. Reject unknown fields
   and embedded secrets.
2. The platform assigns the version with `next_version(change)` and rewrites the
   manifest metadata:
   - `version` = the assigned version;
   - `owner` = the submitter, or the name's existing owner;
   - `lifecycle: published`;
   - both reviews `pending`;
   - provenance records the submitter and the Agent.

   Author-written approvals are never trusted, as in `skill_authoring.py`.
3. Run the ownership pre-check (`admit_member_version`). A non-owner who is not a
   co-editor is refused now, not at approval.
4. A Skill's command targets must already be published, or be pending submissions by
   the same member. Otherwise the submission is refused with `missing_dependency`.
5. Size: the manifest must fit the existing 256 KiB body limit; a larger one is
   refused with `artifact_too_large`.

**Stored** in a new SQLite table `submissions`, in the same database as the Registry:
- id, kind, identity, submitter, change, note;
- artifact bytes and their sha256;
- status (`pending` / `approved` / `rejected` / `withdrawn`);
- reviewer, reason, timestamps.

The version is reserved: a second submission of the same name gets the next number
above both published and pending versions.

### 3. Review (admin routes)

| Operation | Body | Result |
|---|---|---|
| `admin/submissions/list` | `status` filter | the queue |
| `admin/submissions/get` | `submission_id` | the manifest, a diff against the previous published version, and the risk summary |
| `admin/submissions/approve` | `submission_id`, `evidence` | the package is published |
| `admin/submissions/reject` | `submission_id`, `reason` (required) | rejected |

- **Approval** sets both reviews to `approved`, with the reviewer and evidence
  `submission:<id>; <evidence>`. It builds the `PublishedAssetPackage` with
  `artifact_ref registry://ns/name/version` and the artifact sha256, then calls
  `publish_as(package, publisher=submitter)` in one transaction. Ownership and
  version rules are checked again there.
- **No self-review (as designed).** The reviewer must not be the submitter
  (`self_review_refused`). This is the gap ASSET_OWNERSHIP names ("a member could
  otherwise assert their own reviews").

  *As built (owner decision 2026-10-15, temporary):* the platform config field
  `allow_self_review` defaults to **true** (`control_plane/app.py`), so an
  administrator may approve their own submission while publishing is being verified.
  Setting it to false restores the `self_review_refused` check
  (`control_plane/submissions.py`). To be revisited.
- **Risk.** A Workflow's risk is the highest `required_permissions` risk of its steps;
  it is shown to the reviewer. High or critical risk keeps `approval_required`.
- **Portal UI.** The admin sees a "Review queue" section (list, view manifest, approve
  or reject with a reason). Every member sees "My submissions".

### 4. Agent side

- `host_runtime/platform_publish.py`:
  - reads an installed Skill or Workflow manifest;
  - signs in with the member login;
  - calls `assets/submit`, `assets/submissions/mine` and `withdraw`.

  It never sends the Bridge token to the portal, and never sends the member login to
  the Bridge API.
- **Agent Web.** The installed Skills and Workflows lists get "Publish to shared
  platform":
  - a dialog asks for the change level and a note, then shows the assigned version
    and "waiting for review";
  - a "Shared platform submissions" list shows status and any rejection reason;
  - Settings gets the member portal URL and a "Connect" status.
- **CLI.**
  - `aep-host assets publish --kind workflow --asset ns/name@version --change minor
    [--note ...]`
  - `aep-host assets submissions`
- **Task list.** Each submission is a `TaskLog` record, kind `publish`.

### 5. Transport and security

- Loopback HTTP is allowed: this test reaches 141 through an SSH tunnel, with the
  portal at `http://127.0.0.1:28776`. Beyond loopback, HTTPS stays required, as now.
- New credential errors use the existing codes. No credential, invitation or session
  value is logged or put in the task list.
- The submission body is data. The platform never runs a submitted Workflow during
  review.

## Tests

- **Control plane:**
  - submit (version assignment, metadata rewrite, author approvals dropped, ownership
    pre-check, missing dependency, size);
  - list and withdraw;
  - approve (package published, hash, owner, co-editor);
  - reject (reason required);
  - self-review refused;
  - two pending submissions of one name get distinct versions;
  - restart keeps the queue.
- **Portal HTTP:** auth for each operation; a non-admin cannot list, approve or reject.
- **Agent:** builds the submission from an installed manifest, keeps login and session
  separate from the Bridge token, handles errors and revocation, CLI output.
- **End to end in process:**
  1. a member submits a Workflow and a Skill;
  2. a second admin approves;
  3. both appear in another member's catalog;
  4. a Bridge sync installs the exact bytes.

## Live test on 172.25.228.141

1. Redeploy the Shared Platform bundle with this change, keeping the loopback listener
   and ports 8775/8776.
2. The owner signs in as `leo` and issues an Agent login. The value goes to the
   environment variable on this PC, never through the chat.
3. From this PC, publish one Skill and one Workflow:
   - the Workflow is a harmless one, for example a weekly-report preview without
     running it;
   - the Skill targets that Workflow.
4. A second administrator account approves them in the portal. Self-review is refused
   by design, so the owner invites e.g. `leo-review` as `platform_admin`.
5. Confirm both appear in the catalog.

## Owner decisions on the open questions (2026-10-15)

1. **Reviewer.** Self-review stays refused; the test uses a second administrator
   account (`leo-review`). No `allow_self_review` switch.

   *Superseded later on 2026-10-15:* the owner allowed self-review for now; the
   `allow_self_review` switch exists and defaults to true (see "Review" above).
2. **Login storage.** The existing environment-variable credential.
3. **Namespace.** The asset keeps its current namespace.

## Owner and who can use it (owner decisions 2026-10-15)

Live finding (2026-10-15, Shared Platform on 172.25.228.141): two assets
published by `leo` were invisible to `leo.chi`. `submit` replaced the declared
owner (`team engineering`) with the submitter (`user leo`) and kept the author's
visibility `team`; `entitled` lets only that user see a user-owned `team` or
`private` asset.

Decisions:
1. **Keep a declared team owner.** For a new name, a declared `team` or
   `organization` owner is kept when the submitter belongs to it (their platform
   groups); otherwise the submitter owns it. A declared person or service is
   never kept. An existing name keeps its recorded owner.
2. **The publisher chooses who may use it at submit time.** `AssetSubmitRequest`
   takes an optional `visibility` (default: the manifest's). Agent Web's publish
   card offers "As the Skill or Workflow says", "Only my team" and "Everyone in
   the organization" and explains the effect; `aep-host assets publish
   --visibility`. Any combination is allowed; the dialog says what it means.
3. **Changing it later.** The name's owner, a member of an owning team or a
   platform administrator changes who may use it in the Member Portal ("My
   published assets"; administrators also see "All published assets"). The
   decision is a `NameAccess` record beside the name: a visibility override plus
   extra members and groups, stored in an additive `name_access` table
   (`schema_version` unchanged). `entitled` applies it everywhere a member's
   assets are listed, offered or accepted (portal catalog, `select`, `replace`,
   Bridge `catalog` and therefore what a sync can install). Routes
   `assets/access` and `assets/access/update`; anyone else gets
   `not_name_owner`. Narrowing it does not withdraw selections already made.
4. **Portal fixes.** The invitation Account field shows `leo.chi` and the rule
   (letters, digits, `.` `-` `_`; no `@`) and checks it in the page; a refused
   name answers `invalid_request` with `reason` `account_invalid` /
   `group_invalid` and a message; the page renews its one-hour session from its
   stored login and retries once instead of failing with `session_expired`.
5. **Test asset.** `aep-host assets publish --file <manifest.json>` publishes a
   manifest file instead of an installed asset. `deploy/samples/sync-test.workflow.json`
   (`company-agent/sync-test`, owner team `engineering`, visibility
   `organization`) reads only the personal-proof fixture.

Fixing the two assets already published: the owner (`leo`) opens the Member
Portal, "My published assets", presses "Who can use it" on each and chooses
"Everyone in the organization" (or adds `leo.chi` as a member). Their recorded
owner stays `user leo`; a transfer to team `engineering` (`assets/transfer`) is
the alternative.

## Not in scope

- Bridge token issuance.
- Deprecation notices to Hosts.
- Reconciling chat-authored local versions with the Registry.
- Knowledge vault publishing.
- Production identity provider and TLS.
