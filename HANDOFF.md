# Handoff

Date: 2026-10-02 (Asia/Taipei)
Branch: main. The last implementation commit is 43dc5bc (approved Gateway task path). This handoff covers the owner's first live capability and Workflow 11 validation; no push, source Vault edit, Excel write or mail action occurred.

## Current objective

The owner wants Knowledge connected from an existing OneDrive Vault, Workflow 11 or 7 validated, and a clear inventory of remaining development. Workflow 11 read-only preview was selected as the first run. The detailed readiness and gap inventory is docs/VALIDATION_GAPS_2026-10-02.md. The active checklist is docs/TASKS.md.

## Completed and observed

- The prior explicit aep-host run-task Gateway slice was built and tested: 1,560 passed, 4 skipped, 2 machine-specific deselected; ruff, mypy, offline sdist and wheel passed. It is CLI-only and --prompt exposes no capabilities. The owner ran it live through the approved Gateway and received a nonempty answer; that validation does not prove a grounded inventory or Knowledge/Workflow use.
- Installed Host workspace: five Skill manifests, five Workflow manifests and one published Knowledge manifest. The knowledge Skill has an ask capability command; the weekly Skill exposes preview/apply/mail Workflow commands. Installation does not grant execution.
- The owner-supplied external Knowledge Vault exists and has drop/raw/wiki; listed content is 6,928 files and about 1.1 GB. The Host has no Knowledge binding. Its installed validation/company-agent-guide manifest refers to an unrelated proof Vault and pinned digests. Do not bind it directly to the owner Vault or ingest into the original. Stage a full copy, characterize it and publish/bind a matching exact asset before query/convert/ingest/lint parity.
- A read-only weekly.preview 2026_40W run was attempted through the actual Host and Bridge. It completed the reporting-window step and failed at GitHub Project with github_auth before workbook reading or planning. The JSON result is in the ignored .scratch directory. The CLI process exit code was zero even though the nested Workflow status was failed; do not infer Workflow success from CLI exit code.
- A status-only GitHub /user check returned HTTP 200 for the configured AEP_GITHUB_TOKEN, but the configured Project V2 lookup returned GraphQL FORBIDDEN. The token exists and is accepted by GitHub; the configured Project is not readable with it. No token value or Project payload was printed or saved in tracked artifacts.
- The Host doctor reports Workflow 11 preview support but no Excel COM bridge for apply and no Outlook bridge for mail. Workflow 7 is the distinct source jira_team_tickets job; it is not characterized or migrated, and Jira has been retired.
- Docs/TASKS.md and docs/VALIDATION_GAPS_2026-10-02.md now record these findings. No implementation code changed in this validation turn.

## Next actions in order

1. Restore read access to the configured GitHub Project for AEP_GITHUB_TOKEN, rerun Workflow 11 read-only preview for the intended reporting week, and inspect the plan and workbook-read evidence. Use a workbook copy for any later Excel apply/parity run.
2. Stage a controlled full copy of the Knowledge Vault, build an exact published manifest and Host binding for the copy, then validate grounded query and source-preserving convert/ingest/lint/restore.
3. If Workflow 7 is still required, inspect its pinned source contract and choose a replacement data source for retired Jira before implementation.
4. Continue ordinary Agent ingress integration, static/runtime Workflow parameter UI and aliases, default Marketplace packages, native backend transition gates, product E2E evidence and the optional benchmark-gated JEV adapter.

## Constraints

The previous owner-approved policy remains: UNCLASSIFIED material uses only the exact host-approved internal Gateway; native Codex/Claude tasks require complete explicitly PUBLIC context. Do not infer permission from a published/installed asset. The OneDrive Vault is source evidence and must not be modified by validation. The Workflow 11 preview performs reads only; apply and mail are separate commands.
