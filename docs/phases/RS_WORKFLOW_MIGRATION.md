# rs_workflow_system migration with one parameter declaration

Status: proposed (2026-10-05), awaiting owner decisions below. Source:
`dragon0816/rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43`
(local clone `C:\Users\Chi_L\Documents\claude\n8n_workflow_system`). Follow
`.agents/skills/migration/SKILL.md` and the migration rules in
`docs/CONTRACTS.md`; the source repository is never modified.

## Goal

Migrate every source workflow/job into AEP so a contributor declares a
workflow/task once and AEP generates its run form in Agent Web, its schedule
form, its Telegram question flow, its Agent tool schema and its per-install
settings editor. No n8n dependency (owner decision 2026-10-04).

## Source design to preserve

- Run-time parameters: each job declares `PARAMS_SCHEMA` (JSON Schema draft-07)
  with an `x-ui` block per field: `control` (text/list/toggle/file/folder/upload),
  `options` (`enum`, `ref:<published set>`, `fn:<host function>`, `{field}`
  substitution), `needs`, `group` (`identity` asks "same as last time?"),
  `order`, `accept`, `multiple`, `start`. Fields without `x-ui` are hidden once
  any field has it. Source: `docs/BRIDGE_API.md` §6.1–6.6,
  `host-bridge/jobs/release_package.py:87-191`. Also `STEPS {id,title,optional}`
  for progress and reserved result keys `verdict`, `files`, `tables`.
- Dashboard form (`ops-dashboard/static/app.js:4258-4760`) and Telegram
  (`ops-dashboard/app/services/telegram_pack.py:490-545`,
  `telegram_bot.py:321-385`) are both derived from that schema.
- Per-install settings: `SettingGroup` / `SettingField`
  (`host-bridge/app/routers/settings.py:78-166`) with `privileged` fields that
  need confirmation (for example the double send gate `email.allowSend` plus the
  per-workflow `send` switch).

## AEP today

- `WorkflowParameter` (`src/common/assets.py:251`) has name, label, kind
  (text/integer/date/boolean/select), scope, description, required, options,
  minimum, maximum; `validate_run_parameters` in `src/common/workflow_parameters.py`.
- Agent Web launch form and schedule form are two hand-written copies in
  `src/host_runtime/web_page.py`; Telegram has no parameter flow or inline
  keyboard; the Agent tool schema is one open generic object; per-install
  settings are hardcoded per workflow in `HostIntegrations`
  (`src/host_runtime/contracts.py:266`), which conflicts with AGENTS.md rule 11.

| Source workflow | Effect | AEP status |
|---|---|---|
| 90 bundle_smoke | read | WRAP done: `packages/rs-workflow-system/w90-bundle-smoke/` (candidate, owner approval pending) |
| 12 chipset_readiness | read + publish reference sets | not started |
| 14 ncc_improvement_plan | write + Outlook draft | ADAPT done: `src/capabilities/ncc_plan/` + `outlook.draft`; source re-import not carried yet (see its SOURCE.md) |
| 07 jira_team_tickets | write (Excel) | read-only preview; paused on Jira `MRT1CV` access |
| 10 sales_to_chipset | write (Excel) | rules ported, guarded preview/apply; no real-workbook parity |
| 11 github_weekly_report + email (was Jira) | write + draft (send double-gated) | one Workflow `sde-weekly-report` (plan, write, draft; dry run); GitHub selection rules aligned 2026-10-05; real-workbook parity open |
| 13 release_package (+ pipeline_watch) | external_side_effect (git push) | read-only preview + isolated preparation |
| 03 c4c_tickets_by_creator | write, occupies the machine | not started |
| 06 loan_scan / 06b loan_process | queue write; customer-facing draft | not started |

## Proposed contract extension (backward compatible)

Extend `WorkflowParameter` with optional fields only: `default`, `help`,
`examples`, `order`, `group` (`identity` reserved), `pattern`, `min_length`;
kinds `number`, `text_list`, `emails`, `file`, `folder`, `upload`;
`choices: {value,label}` (old `options` remains shorthand); `choices_source`
(`ref:<set>` / `fn:<name>` with `{field}` substitution) and `needs`;
`channels` (web, telegram, schedule, agent; default all); `confirm` (privileged).
Add `WorkflowManifest.progress_steps`. Static per-install values move to a
generic `host.json` `workflow_settings` map validated against `scope: static`
fields, edited in Agent Web. Secrets remain SecretRef names only.

Generators in a new pure module `src/common/workflow_forms.py`:
`form_spec(manifest, channel)` (one shared web renderer for launch and
schedule forms), `telegram_flow(spec)` (question sequence, inline keyboards,
`/skip` only for optional fields, `/done`, `/cancel`, identity reuse; state in
the local SQLite store; answers validated by `validate_run_parameters`), and
`agent_tool_schema(manifest)` (agent-channel fields only, never static or
secret fields).

## Slices

| # | Slice | Acceptance |
|---|---|---|
| S1 | Contract fields and validators | legacy manifests valid; order/needs/default errors refused |
| S2 | `form_spec` + shared web renderer (launch and schedule) | generated spec snapshots for W11/W13; DOM safety tests |
| S3 | `agent_tool_schema` | static/secret fields never exposed |
| S4 | Telegram question flow, then inline keyboard/callbacks | fake transport drives each question; required field refuses `/skip` |
| S5 | `workflow_settings` store and editor | credential-shaped values refused; W13 `checkout_path` migrated off `HostIntegrations` |
| S6 | Dynamic choices `ref:` then `fn:` (read-only, policy-checked) | |
| S7+ | One workflow per slice: 90, 12, 14, 07, finish 10/11/13, 03, 06/06b | source pytest suite as oracle; dry-run plan and normalized output parity recorded in CONTRACTS format |

Strategy per workflow: REUSE for 90; WRAP (hash-verified pinned source job)
for 12, 14, 07, 03, 06/06b unless a job opens COM directly; continue ADAPT for
10, 11, 13; pipeline_watch folds into 13.

## Owner decisions needed

1. Telegram runs of `write` / `external_side_effect` workflows: require an
   approval tap per run? (Recommended: yes for send, push and customer drafts.)
2. Credentials to provision as SecretRefs: Jira PAT, GitLab, Artifactory,
   C4C/Entra session, GitHub.
3. Where published reference sets (`ref:`) live without the ops dashboard:
   local SQLite (recommended first) or the Registry.
4. Whether "occupies the machine" (`block`) becomes a manifest field.
5. Whether loan replies may ever move from draft to send (recommended: never
   unattended).

## Must be verified on a real company PC

Excel/Outlook automation in a non-elevated session; Edge persistent profile
and auto-login for C4C and the loan portal; GitLab/Artifactory reachability
and an isolated push; the owner's real W10 workbooks and `chipset-map.json`;
Jira `MRT1CV` access; Telegram long polling through the corporate proxy.

## Building-block extraction (owner decision 2026-10-05)

Each workflow slice keeps WRAP parity and also extracts the reusable
operations inside the job as capabilities with typed contracts, declared side
effects and dry run, feeding `docs/phases/NL_WORKFLOW_AUTHORING.md` P1:
W03 (C4C web capture, Excel upsert), W06/06b (portal web, Outlook draft),
W07/W10 (Excel read/upsert), W11/W14 (Outlook draft/send), W12/W13 (GitLab
projects, pipelines, branches, controlled push). Record each extracted
capability and the source code it came from in the slice's SOURCE.md.
