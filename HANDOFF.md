# Handoff

Updated: 2026-10-05 (Asia/Taipei), by Claude Code

## Repository and runtime state

- Branch `main`, all work committed locally, nothing pushed. `schedules-v1`
  is merged (merge commit `605cb3d`); its worktree was removed, the branch kept.
- Live Agent Web: `aep-host web --config %LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\host.json --port 53583 --open --schedules`
  started from the repo `.venv` (editable install), logs `.scratch/agent-web-18-*.log`.
  The token changes on every restart.
- Installed Knowledge Skill: candidate `company-agent/knowledge-query@1.4.0`
  (`wiki_primary` citation, report answers). Rollback: move its JSON out of
  `%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\workspace\assets\skills\`
  and move `disabled/company-agent__knowledge-query__1.3.0.json` back, then
  restart. Exactly one Knowledge-selectable Skill must be installed.
- Test Vault copy `C:\Users\Chi_L\AppData\Local\AEP\rs-k` must equal the
  staged copy `.scratch/k` (published manifest digests); a plain copy of the
  OneDrive Vault does not match.

## Done in this session (details in `docs/TASKS.md`, decisions in `docs/DECISIONS.md`)

- Knowledge: answer-salvage fixes, labeled inference `【推論】`, Wiki-primary
  citation with Raw provenance (E2E-05 criterion 1 amended by the owner),
  Markdown report answers, Skill 1.4.0 with high-speed communications focus.
- Scheduled tasks v1 merged (no n8n; Workflows and Agent Tasks; Agent Web
  Schedules panel; resident loop via `--schedules`; sending always needs
  per-run approval; catch up once).
- Agent Web: grouped turns with thumbs up/down/normal + reason note and
  reply-to-exchange; right-click menu; per-session delete; backend selector
  sync fix; Gateway model picker in Settings; concurrent sessions with
  per-session turn queues and `BridgeExecutor.exclusive` for workflows and
  non-read capabilities.

## Verification (last full run)

Full pytest (unsandboxed): 1955 passed, 5 skipped. Known non-regressions:
`tests/test_local_developer_environment.py::test_loader_rejects_unknown_names_without_setting_them`
(cp950, fails at HEAD) and intermittent `test_knowledge_stage` /
`test_extension_runtime` / `test_application_catalog` (Windows file-lock or
socket timing; pass on rerun). Ruff and mypy pass. Run pytest outside the
Claude Code sandbox; inside it more file-permission failures appear.

## In progress

Owner request: migrate every `rs_workflow_system` workflow/task (local clone
`C:\Users\Chi_L\Documents\claude\n8n_workflow_system` at pinned
`896046e8`) into AEP with one parameter declaration that generates the
workflow settings UI, the Agent Web parameter GUI and the Telegram parameter
GUI. A read-only inventory and plan is being prepared; follow
`.agents/skills/migration/SKILL.md` and `docs/CONTRACTS.md` migration rules.
No migration code has been written yet.

## Open items for the owner / data team

- Knowledge data gaps: CMP180 competitor comparisons (Anritsu MT8870A,
  LitePoint, Keysight), market-to-option links, more market-trend sources.
- Owner feedback on Skill 1.4.0 report answers in Agent Web.

## Next recommended action

Review the rs_workflow_system migration plan with the owner, record the
parameter-declaration contract decision, then migrate one workflow slice at
a time with characterization tests and parity evidence.
