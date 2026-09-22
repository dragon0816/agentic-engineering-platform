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

## Retirement rule

Keep source repositories and the old Host Bridge frozen at recorded revisions
through parity and rollback rehearsal. Disable one entry point at a time only
after its evidence passes. Archive remains a later owner decision; deletion is
outside Phase 7.
