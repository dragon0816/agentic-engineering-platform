# Handoff

Updated: 2026-10-05 (Asia/Taipei), by Claude Code

## Repository and runtime state

- Branch `main`, all work committed locally, nothing pushed.
- Live Agent Web: `aep-host web --config %LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\host.json --port 53583 --open --schedules`
  started from the repo `.venv` (editable install), restarted after Workflow 14
  (logs `.scratch/agent-web-w14-*.log`). The token changes on every restart.
- W14 is installed live: Workflow + Skill in `workspace\assets\`, grants for
  `ncc-plan.prepare` / `ncc-plan.render` / `outlook.draft` (backup
  `grants.json.bak-20261005-125644-before-w14`), Workflow settings pointing at
  the source `config/workflow-14.json`, the `ncc_paper` template and photos,
  output `C:\Users\Chi_L\Documents\NCC-plans`.
- Installed Knowledge Skill: candidate `company-agent/knowledge-query@1.4.0`.
  Rollback: move its JSON out of `workspace\assets\skills\` and move
  `disabled/company-agent__knowledge-query__1.3.0.json` back, then restart.
- Test Vault copy `C:\Users\Chi_L\AppData\Local\AEP\rs-k` must equal `.scratch/k`.

## Current work: rs_workflow_system migration

Plan `docs/phases/RS_WORKFLOW_MIGRATION.md` (status table per workflow),
building blocks feed `docs/phases/NL_WORKFLOW_AUTHORING.md` P1. Done: S1-S5,
S6a `ref:` sets, S6c `fn:` choice functions, Workflow 90 (WRAP, candidate
awaiting owner approval), the `outlook.draft` building block and Workflow 14
(ADAPT; `src/capabilities/ncc_plan/SOURCE.md` lists what is not carried yet).
Owner-agreed order next: **W12 chipset_readiness**, then **W03 C4C**.

### W12 notes (next)

- Source `host-bridge/jobs/chipset_readiness.py` with `_gitlab_client.py`,
  `_artifactory.py`, `_chipset_rules.py`; uses `requests`, so it cannot run as a
  stdlib-only script tool unchanged. Extract GitLab (projects, pipelines,
  branches) as capabilities on stdlib HTTP, as the plan says.
- It publishes reference sets (chipsets, package versions) that W13's form
  offers: implement the S6b `publishes` declaration with it.
- Credentials (owner has the tokens): the owner sets Windows user environment
  variables `AEP_GITLAB_TOKEN` (read_api is enough for W12) and optionally
  `AEP_ARTIFACTORY_TOKEN`, and adds to `host.json` `credentials`
  `{"secret": "gitlab_token", "environment_variable": "AEP_GITLAB_TOKEN"}` and
  `{"secret": "artifactory_token", "environment_variable": "AEP_ARTIFACTORY_TOKEN"}`.
  Values never go in files. GitLab base `https://code.rsint.net`, group
  `rs-wmt-projects/chipsets`, header `PRIVATE-TOKEN`; Artifactory `Bearer`.
- Owner agreed: script tools may receive only their declared SecretRefs as
  environment variables. Not implemented yet; record it in DECISIONS when built.

## Verification (last full run, this commit series)

Full pytest (unsandboxed, `--deselect tests/test_local_developer_environment.py`,
cp950 failure at HEAD): 2074 passed, 5 skipped, 2 failed. The failures:
`test_knowledge_stage` (known flaky, passes on rerun) and
`test_weekly_report_workflow` export list (fixed by adding the two W14 assets,
file rerun passes). Ruff and mypy (`src`) pass. The W14 parity test against the
source job ran on this machine (source clone and `ncc_paper/` present) and
passed. Run pytest outside the Claude Code sandbox.

## Open items for the owner / data team

- Approve (publish) the W90 candidate package if wanted.
- Feedback on Knowledge Skill 1.4.0 report answers in Agent Web.
- Knowledge data gaps: CMP180 competitor comparisons (Anritsu MT8870A,
  LitePoint, Keysight), market-to-option links, more market-trend sources.
- Try W14 in Agent Web (`/run 14`), dry run first.

## Next recommended action

Start W12: read the source job and its tests, decide which GitLab and
Artifactory operations become capabilities, implement `publishes`, then the
script-tool secret injection if a wrapped part still needs a token.
