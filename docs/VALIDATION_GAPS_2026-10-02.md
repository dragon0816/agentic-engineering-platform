# Agent, Knowledge and Workflow validation gaps (2026-10-02)

This is a repository and workstation readiness audit, not a claim that an
installed asset is executable. It follows the owner's request to validate
source workflow 11 first and to use the existing OneDrive Knowledge Vault as
the source for a later controlled copy. No source Vault files were changed.

## Observed on the company Host

- The installed workspace has five Skill manifests, five Workflow manifests
  and one published Knowledge manifest. `aep-host run-task --prompt` remains a
  text-only task with no allowed capabilities; a nonempty answer can validate
  without describing the actual installed catalog or using Knowledge.
- The configured GitHub credential environment variable was present. A minimal
  GitHub `/user` request returned HTTP 200, but the configured Project V2
  lookup returned GraphQL `FORBIDDEN`. A read-only `weekly.preview 2026_40W`
  run completed its reporting-window step, failed its GitHub Project step with
  `github_auth`, and did not reach workbook reading or report planning. Its
  CLI command wrote a result file and returned zero, so inspect the nested
  Workflow run status, not only the process exit code. The credential value
  and Project response content were not recorded in this document.
- The Host doctor reports Workflow 11 preview support, but no Excel COM bridge
  for the write phase and no Outlook bridge for mail. The source of Workflow 11
  is now GitHub Project; its legacy `jira-` asset identity has not been renamed.
- The owner-supplied external Knowledge Vault has `drop`, `raw` and `wiki`
  directories, 6,928 files and approximately 1.1 GB of listed content. The
  Host has zero Knowledge bindings. Its one installed Knowledge manifest names
  an unrelated proof Vault and pinned digests. Binding that manifest directly
  to the owner's Vault would fail exact path and digest checks. Phase 7 requires
  validation against a full copy rather than modifying the original Vault.

## Pending development versus validation

| Area | Current state | Next concrete checkpoint |
| --- | --- | --- |
| Workflow 11 preview | Implemented, installed, blocked by Project authorization | Restore read access for the configured token, rerun `weekly.preview` for a chosen week, inspect plan and workbook-read evidence without applying changes |
| Workflow 11 apply/mail | Code exists; this Host lacks Excel COM and Outlook bridges; live parity is unproven | On a suitable company workstation, use a workbook copy and source/platform parity evidence before any real write or mail action |
| Workflow 7 | `jira_team_tickets` exists only in the pinned source; it has not been characterized or migrated | Inspect source contract and decide a replacement for retired Jira before implementing and validating it |
| Knowledge source Vault | Pipeline and exact Knowledge contracts exist, but this Vault is not staged or bound | Make a controlled full copy, characterize Raw/decision/content digests, publish an exact manifest for the copy, bind it, then test query, convert, ingest, lint and restore |
| Natural-language Agent | Explicit CLI Gateway task path exists; ordinary Ask and task state are separate; `--prompt` is tool-free | Ground capability descriptions in installed and authorized inventory, then route suitable natural-language requests through policy and independent validation |
| Workflow UX | Exact `/run workflow namespace/name@version` exists; static/runtime parameter schema and generated Web/Telegram controls are missing | Define one parameter contract and render forms for Workflow 11; add tested `/run workflow 11` and `/run 11` aliases |
| Native backend orchestration | Restricted Codex/Claude/Copilot text chat exists; native task execution and backend transitions do not | Inventory transferred material, re-authorize full context, and add containment/denial tests before a PUBLIC native task adapter |
| Shared Marketplace defaults | Catalog, selection and sync paths exist; owner-requested Hermes Skills and validated Workflows are not all governed default packages | Review provenance, license, dependencies and policy; publish only reviewed exact versions |
| Product evidence and JEV | SOP-to-Workflow, Knowledge and Skill end-to-end cases remain unproven; JEV provider is not installed | Collect enrolled-Bridge evidence, then benchmark bounded decisions before enabling an optional JEV provider |

The active implementation checklist remains `docs/TASKS.md`; the source and
parity requirements are in `docs/PHASE_7_MIGRATION.md` and
`docs/MULTI_BACKEND_ORCHESTRATOR_PHASE0.md`. No credential values or OneDrive
content belong in repository artifacts.
