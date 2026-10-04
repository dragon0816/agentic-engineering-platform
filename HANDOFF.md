# Handoff

Updated: 2026-10-04 (Asia/Taipei), by Claude Code

## Goal and repository state

Improve Agent Web Knowledge Ask (six-layer harness, G3 in
`docs/phases/HARNESS_6_LAYER_INCREMENTAL.md`) using RS_Knowledge as the test
Vault, while keeping the shared harness generic for Workflow/Tasks and Coding.
Knowledge retrieval rules live in the Knowledge Skill and adapter, not in the
shared runner. The owner's reference is the Hermes `rs-knowledge-base` Skill
(see `docs/DECISIONS.md`).

- Branch `main`. Candidate Skill `company-agent/knowledge-query@1.3.0` and its
  adapter fixes are committed (see `git log`); nothing was pushed.
- **Candidate Skill 1.4.0 (`wiki_primary` citation, report answers) is installed
  in the live Agent Web** on port 53583 (restarted 2026-10-05 from the repo
  `.venv`, logs `.scratch/agent-web-14-*.log`). Rollback: move
  `company-agent__knowledge-query__1.4.0.json` out of
  `%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\workspace\assets\skills\`,
  move `disabled/company-agent__knowledge-query__1.3.0.json` back, restart.
  Exactly one Knowledge-selectable Skill must be installed.
- Wiki is the primary answer source (owner decision 2026-10-05, see
  `docs/DECISIONS.md`; E2E-05 criterion 1 amended). Wiki/Raw conflicts are
  resolved by data experts at ingest, not by the answer layer.
- Test Vault copy `C:\Users\Chi_L\AppData\Local\AEP\rs-k` had disappeared; it
  was recreated by mirroring the staged copy `.scratch/k`, whose Raw,
  decisions and content digests match the published manifest
  `engineering/rs-knowledge@1.0.0`. A plain copy of the source Vault does
  **not** match (the stage step rewrites Wiki links and adds `decisions.md`).
  The source Vault on OneDrive was not changed.

## Completed in this session

Six process defects fixed with focused tests (details in `docs/TASKS.md` and
`docs/DECISIONS.md`): list-marker/grouped-citation sentence splitting;
best-of-both synthesis drafts; PDF hard-wrap and focus-named-document context
for NTN recommendations; subject check by cited Raw document (handler and
Host `claim_support`); CJK-adjacent number extraction; Skill `market_trend`
now pools all queries with a Chinese query and terms.

Last real isolated results (`.scratch/cc_record_q.py`, records passages and
model outputs to JSON for offline replay of filters):

1. CMP180 / wireless market — `needs_input` (correct). Cites the 2026 Taiwan
   wireless report (Wi-Fi 7, 6 GHz/320 MHz), 5G FWA slide and CMP-KM351/KM352/
   KM280 facts; `direct_relationship` unverified.
2. NTN products — `validated`. CMX500, KC665B, KF651X, callbox configuration,
   TP 298/296, PVT360, ZNA/ATS1800C, TS-LBS, signal generator + MATLAB (item
   count varies by run).
3. CMP180 / competitor — `needs_input` (correct). Cited option/RF facts;
   competitor comparison genuinely absent from the Vault.

## Verification (exact)

- `pytest tests/test_query.py tests/test_knowledge_evidence.py tests/test_agent_web.py -m "not browser"` → 186 passed (before the CJK-number fix); focused Query/Evidence after it → 107 passed.
- Full `pytest` (unsandboxed) → 1887 passed, 5 skipped, 2 failed:
  `test_extension_runtime` (Windows file-lock flake; different test fails per
  run, file passes on rerun) and
  `test_local_developer_environment::test_loader_rejects_unknown_names_without_setting_them`
  (cp950 subprocess decoding; also fails at HEAD). `test_knowledge_stage` is
  intermittently flaky the same way. Inside the Claude Code sandbox more
  file-permission failures appear; run the suite unsandboxed.
- `ruff check src tests` passed; `mypy src` passed (214 files); `git diff --check` passed.

## Open items and risks

- Knowledge-base gaps for the data team: no CMP180-vs-competitor material
  (e.g. Anritsu MT8870A, LitePoint, Keysight non-signaling testers; only a
  portfolio line in the CMX500 Anritsu battle card); no source directly
  linking market trends to CMP180 option selection; market-trend sources are
  thin beyond one 2026 Taiwan report and OneNote slides.
- Labeled inference is implemented (owner chose explicit labels); see
  `docs/DECISIONS.md`. The owner should judge in Agent Web whether the
  inference checks are too strict or too loose.
- Scheduled tasks: owner decisions (2026-10-04): no n8n; Workflows **and**
  Agent Tasks; Agent Web screens in v1; resident loop inside the running
  Bridge/Host execution process; `external_side_effect` (sending) always needs
  per-run approval, write/draft may run unattended only with a durable Bridge
  grant plus a schedule grant; catch up a missed run once. Implementation is
  in progress on branch `schedules-v1` (separate worktree under
  `.claude/worktrees/`), not merged. Existing code: `src/common/scheduling.py`,
  `src/host_runtime/schedules.py`, `src/host_runtime/schedule_worker.py`,
  `aep-host schedules` CLI. Do this in a separate branch/worktree because it
  touches `web.py`.

## Next recommended action

Collect the owner's Agent Web feedback on Skill 1.4.0 reports (four probe
questions incl. `R&S 高速通訊市場產品與 Option 對接`). Branch `schedules-v1` is
verified (trial merge: only docs/DECISIONS.md and docs/TASKS.md conflict, keep
both sides; 230 focused tests passed) and awaits the owner's merge approval.
