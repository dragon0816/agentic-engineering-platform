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

## Migration gate

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

The existing `GitHubProjectClient` exposes project field values, issue title,
state, update time, URL and comments. It does not currently query issue
creation time or reporter. A Workflow 7 adapter must either extend that
read-only query under the same credential policy or explicitly mark those
source columns unavailable; it must not invent source-equivalent values.
