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
| 13 release_package (+ pipeline_watch) | external_side_effect (git push) | ADAPT: prepare, commit, push as three approved Workflows (2026-10-15); real GitLab behind `remote_release`; pipeline_watch not started |
| 03 c4c_tickets_by_creator | write, occupies the machine | not started |
| 06 loan_scan / 06b loan_process | queue write; customer-facing draft; optional per-message send | ADAPT done (2026-10-20): `src/capabilities/loan_reply/` as two Workflows `engineering/rs-loan-customer-block-scan` (`/run 6`) and `engineering/rs-loan-queue-reply`, shipped switched off; source tests vendored as the oracle; real-PC checks below |

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

*As built:* there is no host.json `workflow_settings` map. Per-install values are
stored in `workspace\workflow-settings.json` (`host_runtime/workflow_settings.py`,
keyed by `namespace/name` so an upgrade keeps them, read on every run without a
restart) and set in Agent Web under Capabilities → select the Workflow → "Settings on
this computer". Credentials never live there; a Workflow declares a `SecretRef` that
host.json maps to an environment variable.

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
| S5 | `workflow_settings` store and editor (as built: `workspace\workflow-settings.json`, Capabilities → "Settings on this computer") | credential-shaped values refused; W13 `checkout_path` migrated off `HostIntegrations` |
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
5. ~~Whether loan replies may ever move from draft to send.~~ **Closed
   2026-10-20 (owner): draft by default, optional per-message approved send.**
   Each saved draft may get its own send card; a mail leaves only when a person
   presses 寄出 on that card in Agent Web. Never unattended, never by the model,
   never in bulk (`docs/DECISIONS.md` 2026-10-20, "Loan replies 06 / 06b").

## Must be verified on a real company PC

Excel/Outlook automation in a non-elevated session; Edge persistent profile
and auto-login for C4C and the loan portal (06b: see "Loan replies: what the
owner verifies on the company PC" below); GitLab/Artifactory reachability
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

## Loan replies 06 / 06b as built (2026-10-20, owner decisions of that day)

- **Two Workflows**, like 06 and 06b: `engineering/rs-loan-customer-block-scan`
  (producer, `/run 6`; the `rs-` prefix marks an rs_workflow_system port as for
  `rs-ncc-improvement-plan` and `rs-wmt-package-release`; the name says what it
  checks for) and `engineering/rs-loan-queue-reply` (consumer; no number,
  because "6b" is not a run alias). Each runs alone.
- **Hand-off, not a chain.** The source's n8n 06 started 06b itself when the
  queue had items. AEP's producer returns a `follow_up`: Agent Web shows the
  consumer's run form under the answer, Telegram a button that opens its
  questions; the person presses Run. The consumer drives two signed-in browser
  profiles and writes customer-facing drafts in the person's mailbox, which the
  run-approval model confirms per run (owner decision 1 of 2026-10-05), so an
  automatic chain would bypass that confirmation.
- **Capabilities** (building blocks, `src/capabilities/loan_reply/SOURCE.md`):
  `loan/scan-mail` (read, Outlook), `loan/enqueue` (write, the queue in
  `workspace/loan-reply/loan-queue`), `loan/look-up` (read, loan portal and
  C4C), `loan/draft-replies` (write, Outlook drafts), `loan/offer-send` (write,
  send cards), `loan/send-reply` (external_side_effect, declared and never
  installed: only a card press sends).
- **Queue:** a dedicated workspace queue (the source's file queue: one JSON per
  borrow number in pending / claimed / done / failed), not the Memory Service
  `sync_state`: it needs per-item claims by atomic rename, a reclaim TTL, a
  run lock and failed items a person clears, which a forward-only sync cursor
  does not model; the queue files stay readable with a file manager.
- **Replies:** Outlook drafts; optional one send card per draft (`ls-`), pressed
  in Agent Web only, each press one mail, a draft changed in Outlook is not sent.
- **Credentials:** none. The portal and C4C sign in through their browser
  profiles (`workspace/loan-reply/edge/loan`, `.../c4c`): the portal's Entra
  account picker is clicked as in the source (`loan_account` names the tile's
  address; no password). No SecretRef is needed.
- **No schedule** is created; USER_GUIDE §9.3 says how the person adds one.
- **Shipped switched off** (`host_runtime.assets.shipped_off`): a team's
  business Workflows that need that team's portal and C4C access and write
  customer-facing drafts; colleagues on the loan desk switch them on.

### Loan replies: what the owner verifies on the company PC

1. Switch both Workflows on; set `alert_recipient`; leave `show_browser` on.
2. `rs-loan-customer-block-scan` dry run: the listed borrow numbers match the
   inbox's 簽核通知 (Outlook HTML listing and the SMTP sender of Exchange mail).
3. A real scan: items appear in `workspace\loan-reply\loan-queue\pending`; the
   answer offers `rs-loan-queue-reply`.
4. `rs-loan-queue-reply` dry run, one item: Edge opens the loan form (Entra
   account tile clicked when the session lapsed), then C4C Customers > Accounts,
   the search, Details and both Delivery Block fields; the preview names the
   right outcome. This proves the selector, typing and Enter translation on
   the real SAPUI5 pages and the persistent-profile sign-in.
5. A real run: the reply draft is on the approval notice with the C4C
   screenshot attached (and an internal notice for an unknown customer); check
   who Outlook addressed the reply to.
6. With send cards: press 寄出 on one card only; exactly that mail is sent.
   Edit another draft in Outlook, then press 寄出: it is refused as changed.

