# Handoff

Rewritten 2026-11-06 18:40 (Asia/Taipei) by the BI orchestrator (Claude Code), handing over to
Codex agents because the Claude account is near its limit. Progress history is in
`docs/TASKS.md` and decisions in `docs/DECISIONS.md`; this file only says where work stopped.

## Goal

Release a Windows installer of AEP to colleagues today (owner's word, 2026-11-06), after the BI
Knowledge page was confirmed to work end to end through the GUI. Atlas is not in the installer.
The owner is the only person who confirms a push to GitHub.

## Where things are

- **Local `main` = `1663447c`**, about 190 commits ahead of `origin/main` (`d8fce30f`). Not pushed.
  It holds every acceptance fix F1-F27 (see `docs/TASKS.md` 2026-11-05/06 rows), the script-guard
  fix, the shortcut start fix, the schema suggestion, batch ingest, the one-step share and the
  design document `docs/design/BI_KNOWLEDGE_BASE.zh-TW.md`.
- **Agent Web on the owner's PC** runs an older build (started 15:12 from `9d81844c`-era code on
  port 53583). Restart only after checking `/api/activity` is idle:
  `.venv\Scripts\python .scratch\restart_web.py` from the main checkout. Startup takes 2-6 minutes
  on a loaded PC; `MODEL_VERSION` is 11, so the first open of each vault rebuilds `bi.sqlite` once.
- **Full suite** was started 18:03 on `681cc1ff` in worktree
  `C:\Users\Chi_L\.paseo\worktrees\2qnenase\installer-python-check` (detached HEAD, Python 3.12 venv),
  log `C:\Users\Chi_L\AppData\Local\Temp\fs\full-681cc.log` (`-rfE`, so failures are named at the
  end). `1663447c` only adds a faster share route and share-test waits on top; if the run is clean,
  run `test_bi_share_step`, `test_bi_share_step_ui`, `test_bi_page_simple` on `1663447c`.
  Known environment-only noise: `test_bi_atlas_file_import` has 2 setup errors (Windows env var
  limit); earlier one-off failures that passed alone are listed in `docs/TASKS.md`.
- **LiteLLM gateway** (`127.0.0.1:4000`, model `gpt-5.5`, key in env var `LITELLM_MASTER_KEY`, never
  print it) was restarted by the owner at 16:25 and answered. It has hung twice today; the agent
  cannot stop its process (permission check). If it hangs, ask the owner to end the two
  `gateway.py` python processes and double-click
  `C:\Users\Chi_L\Documents\claude\customized_LLM_vscode_plugin\LiteLLM_Gateway.vbs`.

## What remains, in order

1. **Full suite result** (above). Fix any real failure on a branch; rerun alone to tell flakes.
2. **Restart Agent Web** on final `main` (check `/api/activity` first). Tokens change every start.
3. **Re-shoot the SOP screenshots on final main**, fictional data only, no token in any shot:
   BI walk notes and old shots are in `%TEMP%\bi-accept\sop\` (`NOTES.md`, 95 files), cards and
   org chart in `%TEMP%\bi-accept\sop-cards\` (18 files, `NOTES.zh-TW.md`). Temp workspaces
   `%TEMP%\bi-accept\pc1`, `pc2` can be reused (their `host.json` must keep
   `local_owner_grants` at its default true). Real model calls take 1-4 minutes each.
4. **Write `docs/guides/BI_SOP.zh-TW.md`** (Traditional Chinese, numbered steps, one screenshot per
   step, what to press, what to expect, what to do on failure) with images in
   `docs/guides/images/bi-sop/`, after reading each image for real data or tokens (public repo).
   Branch `bi-guide` (`136e5da5`, not merged) already has the rewritten `BI_BUILD.zh-TW.md`, the
   release-script copy of the guides into the release's `BI_SOP/` folder, and a placeholder SOP;
   merge it with main first. Include: AI steps can take 1-4 min; approving a tool means you read
   and trust the code (the guard is not a sandbox); F5 in the same tab is fine, a new tab needs the
   desktop shortcut; card photos via Telegram or attach a file (no camera on the page).
5. **Build the installer**: `scripts\release.cmd` from the main checkout on a clean tree (it runs
   ruff, mypy and the full suite itself unless `--quick`; it tags locally, never pushes). Then
   install the zip into a temp folder and check Agent Web starts and the BI page opens.
6. **Owner confirms**, then push `main` (GitHub credential manager hangs; use
   `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push origin main`
   with a timeout). The owner already said pushing is fine after the package succeeds.
7. Atlas `bi-series` (agent "Atlas B" in the Atlas workspace) waits for the owner to say 確認 push
   in that session; not part of this installer.

## Known limits to state in the release notes and SOP

- The owner's same-card rule (summary unchanged, evidence and links appended, time a union) is
  **not** what the code does yet: a second table import replaces a summary silently; two appends to
  one field's evidence conflict; `updated` conflicts. The owner has not chosen between releasing
  with this documented (A, recommended) or fixing first (B).
- Chat has no data-class check on BI cards and analysis rows; add no source above INTERNAL.
- Test results are local to the PC that ran them. Upload to the Shared Platform, encryption, and
  the per-domain name dictionary are not built (`docs/phases/BI_PLATFORM_RELEASE.md` is on branch
  `bi-platform-release`, plan only).
- The default analysis pack excludes samples by the `SAMPLE-` name (78), while 95 cards are marked.

## Real data

`market-intel` (shared folder `C:\Users\Chi_L\OneDrive - Rohde & Schwarz\BI_Knowledge\market-intel`)
is pushed, 95 samples of 760, per-domain questions and dashboards assigned, published
`2026q4-r6.2` (older than the working copy). Staged reading run `e3de934115f0` (144 summary
candidates) waits for the owner's review in the page. Write to it only through the page or its API
with `/api/activity` idle and `pending` empty, and never commit someone else's pending work.
A snapshot with real data, `.scratch\bi-assign-snap-20261106-011110` under worktree
`bi-step1-domain`, waits for the owner's word before deletion.

## Rules that bind whoever continues

Read `CLAUDE.md` and `AGENTS.md`. Reply to the owner in Traditional Chinese, short and plain.
No AEP file permission controls (IT decides). Never print or commit secrets. Run browser tests one
at a time with your own `--basetemp`, kill browsers you start, and sweep the BI browser files on the
merged head before a restart. Don't re-ask decisions the owner made (`docs/DECISIONS.md`).
