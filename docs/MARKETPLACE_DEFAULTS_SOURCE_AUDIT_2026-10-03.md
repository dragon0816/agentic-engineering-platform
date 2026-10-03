# Default Marketplace asset source audit — 2026-10-03

This is a **candidate inventory**, not a publication, installation, execution
grant, or claim of source parity. The Hermes Skills directory was inspected
read-only. No Skill instructions, supporting files, or credentials were copied
into this repository. The complete machine-readable inventory is
[`data/hermes-skills-snapshot-2026-10-03.tsv`](data/hermes-skills-snapshot-2026-10-03.tsv).

## Reproducible Hermes Skill baseline

- Active directory inspected: `%HERMES_HOME%/skills`, where this Host sets
  `HERMES_HOME=C:\Users\Chi_L\AppData\Local\hermes`. This directory is **not a
  Git checkout**; a `SKILL.md` on disk is a candidate, not proof that the Skill
  is enabled in the Hermes UI.
- Snapshot: **67 `SKILL.md` files in 12 top-level categories**. The inventory
  records each relative path, the SHA-256 of `SKILL.md`, the SHA-256 of the
  complete Skill folder, file count, script count and per-folder license-file
  count. The folder digest is SHA-256 over UTF-8 lines of sorted
  `relative/path\nfile_sha256` entries joined with `\n`; `.git`, `__pycache__`
  and `node_modules` are excluded. Recheck it before any conversion.
- **17 folders contain `.py`, `.ps1`, `.sh`, `.js`, `.ts`, `.bat` or `.cmd`
  files.** An AEP Skill may describe those resources, but executable scripts
  require a separate governed capability/Extension and Bridge policy. A
  Marketplace install must not execute them automatically.
- **Only 5 folders contain a local LICENSE/LICENCE/COPYING file.** This is
  neither a license determination for those folders nor evidence that the
  remaining 62 cannot be distributed. Review each original source and its
  parent license before publication.
- The local checkout `%HERMES_HOME%/repos/hermes-agentic-ai-skills` is clean
  at Git revision `41e577a2bef4570ea18f4458cfc3ff8f5af45f5e`. Its 8
  `SKILL.md` paths include a duplicate `pdf-linked-markdown`; **7 distinct
  active folders** match the corresponding checkout folder digest exactly:
  `outlook-email-workflows`, `pdf-linked-markdown`, `business-cards`,
  `html-report-delivery`, `leo-work-automation`, `rs-workflow-jobs`, and
  `rs-knowledge-base`. The other **60** have only the local folder snapshot as
  source evidence; their upstream revision, license and dependencies remain
  unverified.

| Hermes category | Candidate count |
| --- | ---: |
| apple | 4 |
| autonomous-ai-agents | 5 |
| creative | 10 |
| devops | 1 |
| email | 4 |
| media | 3 |
| note-taking | 1 |
| productivity | 19 |
| research | 5 |
| social-media | 1 |
| software-development | 13 |
| web | 1 |

## AEP Workflow candidates and source parity

`src/host_runtime/assets.py::shipped()` currently emits five Workflow
manifests. The four engineering Workflows are candidates; the fifth is a
deployment proof fixture, not a team-default business Workflow.

| Exact AEP identity | Original baseline | Current evidence and remaining gate |
| --- | --- | --- |
| `engineering/jira-weekly-report-preview@1.0.0` (`/run 11`) | `rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43`, `workflows/11_jira_weekly_report.json`, `host-bridge/jobs/jira_weekly_report.py` | Live read-only GitHub Project run succeeded. Compare the plan and workbook-read evidence with source fixtures and a workbook copy; source Jira-to-GitHub differences must be recorded. |
| `engineering/jira-weekly-report@1.0.0` | Same Workflow 11 source | Installed apply and saved `2026_40W` workbook checks passed for 22 red current-week Comments blocks, 19 orange highlighted `In Progress` cells, top-left alignment and contiguous highlighted-Key ordering. Older untouched Status fills remain intact. Write-side approval stays separate from publication. |
| `engineering/jira-weekly-report-mail@1.0.0` | Same Workflow 11 source plus the separately identified local mail/reference-draft baseline in `docs/CONTRACTS.md` | The installed Workflow saved an unsent draft with verified subject, 1 To, 8 CC, chart image and no `Other` aggregate. Full visual parity against the reference draft remains open; no send permission follows from draft permission. |
| `engineering/jira-team-tickets-preview@1.0.0` (`/run 7`) | `rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43`, `workflows/07_jira_team_tickets_to_excel.json`, `host-bridge/jobs/jira_team_tickets.py` | Offline Jira source-field mapping and refusal tests exist. The User PAT authenticates (HTTP 200); `MRT1CV` still returns 404 until project Browse access is granted. This is a read-only preview, not source-equivalent Excel behavior. See `docs/WORKFLOW_7_SOURCE_CONTRACT.md`. |
| `company-agent/personal-proof@1.0.0` | AEP controlled deployment fixture | Exclude from the default business catalog; its fixture-scoped read grant is not general file access. |

The revision above is the repository's pinned, read-only source baseline in
`docs/PHASE_7_MIGRATION.md`. This inventory does not claim the original
checkout was re-fetched or that the running Host matches a clean AEP commit.

## Contract mapping and next gate

Strategy: **ADAPT** each reviewed Hermes procedure into an AEP
`SkillManifest`, preserving the exact source snapshot and documenting any
changed instructions. Do not convert a local directory directly to a
published package. For each candidate, establish its upstream owner/license,
dependencies, platform compatibility, needed secrets as `SecretRef`, script
capabilities and side-effect policy; add source-derived evaluation cases and
record any deliberate deviation. Keep unreviewed items as drafts. The
`SkillManifest` stores procedure Markdown in `instructions`, categories in
`metadata.categories`, exact command bindings in `commands`, and separately
governed executable references in `script_tools`. Hyphenated Hermes names
need an explicit AEP command alias because aliases use letters, digits and
underscores.

For Workflows, use the original revision and source behavior as the first
oracle. Characterize original inputs, outputs, side effects and failures;
compare source-derived fixtures before adapting Jira to GitHub or changing
rendering; record every intentional difference and the parity result. A
reviewed `WorkflowManifest` needs exact capability identities, static/runtime
parameter contracts, compatibility, validation evidence and package SHA-256.
Publishing a `PublishedAssetPackage` requires a `published` lifecycle and an
exact artifact digest, but **does not grant Bridge execution permission**.
Member entitlement, installation and runtime grants remain separate.

No candidate in this audit was published or installed. The next independent
slice can validate manifest conversion for a single text-only, licensed Skill
against its pinned snapshot, then exercise Marketplace discovery/sync with a
fixture package. Production defaults should wait for source/license review
and the relevant parity or evaluation evidence.
