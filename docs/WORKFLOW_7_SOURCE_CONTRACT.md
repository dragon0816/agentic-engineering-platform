# Workflow 7 source contract and migration gate

Characterized on 2026-10-02 from the read-only `rs_workflow_system` checkout at
`896046e8fe2170d21f9213e56e5ce2f93c05ba43`: `workflows/07_jira_team_tickets_to_excel.json`,
`host-bridge/jobs/jira_team_tickets.py`, `host-bridge/jobs/_excel_upsert.py`,
`host-bridge/tests/test_jira_team_tickets.py`, and `docs/W3_PORT.md`. This is a
source inventory, not a platform migration or a live run. No source file was
changed.

## Observed behavior

The n8n graph has a manual trigger and a daily 09:00 trigger. Both call the
Host Bridge job, branch on success, and report completion or an error. The job
builds a Jira query from a project, reporter usernames and optional extra JQL,
reads issues and recent comments, maps eleven managed issue fields, and routes
Task/Sub-task types to the Task sheet and other types to the Issues sheet.
Comment-fetch failure becomes visible text in the `Jira activity` field rather
than aborting the entire run. An offline `mockIssuesFile` can replace Jira.

`dryRun` writes a JSON plan to `state/w3-preview/` and does not call the Excel
Bridge. The normal path upserts by Issue Key, updates existing rows in place,
appends new rows, renders Key as an Excel hyperlink formula, hides closed rows
without deleting them, and unhides rows that become active. Only managed
columns are refreshed. The hand-written `Comments` column and any other
unmanaged columns are preserved. Header and status matching are
case-insensitive. Hidden rows count toward the used range when locating keys.
The Bridge makes a workbook backup, keeps seven backups, and refuses a locked
workbook. Configured obsolete columns and sheets can be removed. These are
write-side effects and must not be inferred from a preview or installation.

## Parameters and their future UI ownership

The source has a closed JSON Schema for invocation parameters: `config`,
`project`, `reporters`, `extraJql`, `excelPath`, `commentCount`, `maxResults`,
`mockIssuesFile`, and `dryRun`. Its config also defines source endpoint,
sheet names, task types, hide statuses, removable columns/sheets, notes column,
comment concurrency, backup, timeout and TLS behavior. A platform static
binding should own the endpoint, workbook path, sheet/column policy and secret
reference. A runtime form can expose the bounded query/filter, comment count,
issue cap and preview choice. The source puts a Jira PAT in its config; a
platform asset must carry only a `SecretRef`, never that value. The exact split
requires a typed parameter contract and owner review before implementation.

## Earlier GitHub preview direction (superseded on 2026-10-03)

Jira is retired on the target Host, so the source's Jira JQL and ticket URLs
cannot be copied as an executable platform Workflow. On 2026-10-02 the owner
selected the same GitHub Project as Workflow 11 for a read-only first stage.
Its issue identity, issue types, comments, reporters and statuses still need
an explicit mapping to the source contract. The source's pure record
mapping and Excel planning are candidates for reuse or adaptation after that
mapping is explicit. Before any write capability is enabled, compare a dry-run
plan with source fixtures, test idempotent upsert, preservation of unmanaged
columns and hidden rows, backup/lock behavior, and run against a workbook copy
on an enrolled company Bridge. The source tests provide the initial parity
oracle; no platform parity or live Excel validation has been claimed.

Before the first migrated slice, `GitHubProjectClient` exposed project field
values, issue title, state, update time, URL and comments, but not issue
creation time or author. The read-only query was extended to request both
under the same credential policy. Author login is the available reporter
substitute; it is not Jira's display-name field.

## First migrated slice: GitHub read-only preview (2026-10-02)

Strategy: **ADAPT** the source's managed-column order, Task/Sub-task routing,
date-cell format and latest-comment formatting behind the existing GitHub
Project client. The read-only query now asks for Issue `createdAt` and author
login. The installed `engineering/github-team-tickets-preview@1.0.0`
Workflow has alias `7` and one `team_tickets.preview` read capability; the
`tickets.preview` Skill routes deterministically to it. Installation and
publication still do not grant execution. A local `github.read` grant with
`github-read-policy` is required before the Bridge calls GitHub.

The preview uses Issue `owner/repo#number` as Key, Project `Type` or `Issue
Type` to choose Task versus Issues, Project Status with Issue state fallback,
Project Priority and Assignee fields, Issue author login for Reporter, and
Issue created/updated timestamps. The source searches `ORDER BY created DESC`,
so the adapter sorts Issue creation timestamps newest first before applying
`max_items`; GitHub Project board order is not the source order. GitHub has no
Jira Resolution equivalent: that cell is empty and `unmapped_fields` names it.
Any other absent mapped
field is also named. The legacy `Jira activity` column contains the latest
available GitHub comments in source format; when the client reports a
truncated thread, that cell is left empty and the key appears in
`truncated_threads`, so an incomplete first page cannot be mistaken for the
latest comments. `capped` distinguishes an intentional issue limit from a
complete board read. No workbook path, file write, Excel Bridge or email
handler is part of this Workflow.

This is a preview migration, not parity or source deprecation. The source's
reporter/JQL filters, static workbook configuration, Excel upsert, row
visibility, manual-column preservation and backups remain open. The real
Project preview is blocked until the Host's GitHub credential can read
Project V2. Offline Agent/Bridge tests cover mapping, no workbook creation and
denial before network access.

On 2026-10-03, a read-only Project query using this Codex process's mapped
`AEP_GITHUB_TOKEN` returned `github_auth` from GraphQL (`FORBIDDEN`, with no HTTP
error status). The installed Host workspace also has no Workflow 7 manifest yet.
This does not establish that a separately running Agent has the same token;
refreshing the installed manifest and a successful real Project read remain
required before claiming live validation.

## Current Jira read-only slice (owner correction, 2026-10-03)

The owner clarified that Workflow 7 must continue to read company Jira at
`https://jira.rsint.net/`; the prior GitHub Project substitution above was an
incorrect assumption for this Workflow. Workflow 11's GitHub Project remains
separate. The pinned source revision and files at the top of this document are
the behavioral baseline. The AEP Jira preview uses the existing
`integrations.jira.JiraClient` with Server Bearer PAT authentication, obtained
from a Host `SecretRef`. No PAT is stored in a shared asset or repository file.

The source's non-secret local `config/workflow-07.json` has project `MRT1CV`,
reporter usernames `CHI_L`, `peng_k`, `fang_ke`, `chen_jen`, `teng_je`, comment
count `2`, comment concurrency `5`, and maximum results `2000`. These values
are candidates for this Host's `integrations.team_tickets` static project,
reporters and comment-concurrency settings; the
original workbook path is intentionally absent from the read-only slice.
Runtime fields are `max_items`, `comment_count`, and optional `extra_jql`.
The original JQL shape (`project = ... AND reporter in (...) [AND (...)] ORDER
BY created DESC`), eleven managed column values, Jira browse URLs,
Task/Sub-task routing, newest-N comment formatting, `Unresolved` fallback,
and per-ticket comment-error degradation are pinned by offline tests.

The new asset is `engineering/jira-team-tickets-preview@1.0.0` with alias `7`,
and its Skill is `engineering/team-tickets@2.0.0`. The Jira capability is
`team-tickets/jira-preview@1.0.0`, classified `read`; it requires a separate
`jira.read` grant under `jira-read-policy`. Exported defaults no longer include
the old GitHub Workflow 7 asset. This is a read-only preview: no Excel writer,
workbook path, schedule, or mail action is installed. Parity for the original
Excel upsert, hidden-row behavior, backup and lock handling remains open.
The configured PAT did not authenticate in the separate read-only `myself`
probe (HTTP 401). No live Jira data validation is claimed.
