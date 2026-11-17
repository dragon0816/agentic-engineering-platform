# BI Knowledge as an in-process plugin (proposal r3) — handoff

Updated 2026-11-17 before an owner PC restart. Worktree
`C:/Users/Chi_L/.paseo/worktrees/2qnenase/it-owned-tools-20261112`, branch
`phase-plugins/bi-facade-20261114` (local commits only, NOT pushed).

## Goal and scope
The owner's goal: stop needing to update/reinstall AEP whenever BI Knowledge (later
LLM Wiki) changes. Approved design: proposal r3,
`docs/phases/FEATURE_PLUGIN_BI_STAGE2_PROPOSAL_DRAFT_20261115.md`. A feature plugin's
page fragments and Python code load into the AEP process at Host start, so install or
update takes effect after an AEP restart. The pages stay exactly as they are. There is
no iframe, no token isolation and no BI worker process. The owner rejected those in r2
(see `docs/DECISIONS.md`, 2026-11-16 entries).
AGENTS rule 22 consent is recorded in `docs/DECISIONS.md` for stages A and B. That
consent covers Web routing, tool registration, the Knowledge BI bypass, answer
post-processing, startup plugin loading, and Shared Platform `sync.py` installs of
subscribed BI datasets. Permissions and approvals are unchanged. LLM Wiki, main merge
and push are not covered.
Run tests with `C:/Users/Chi_L/Documents/ChatGPT/agentic-engineering-platform/.venv/Scripts/python.exe`
and env `PYTHONPATH=src` (the venv's editable install points at another checkout).
Always pass your own `--basetemp` and `-p no:cacheprovider`.

## Done (committed)
- `8f6029cd` stage A. Core reaches BI only through `src/host_runtime/features.py`. The
  BI contributions are in `features_bi.py` and the BI page parts in `bi_page.py`. With BI
  installed, the page sha256 is unchanged at `86646dc3…`. The empty feature set gives a
  working AEP without BI, with stand-ins for the 7 BI names the shell calls.
  New test file: `tests/test_feature_set_without_bi.py`.
  Verified: ruff, format, mypy (all files), 277 BI-focused tests and 9 new tests.
- `8f05be83` B1, Plugin API 1.2 (`CORE_PLUGIN_API_VERSION` 1.2.0):
  - Manifest field `in_process` {package `aep_*`, entry}.
  - Package area `python/`.
  - `src/plugins/in_process.py`: bundled roots (source `feature_plugins/`, env
    `AEP_BUNDLED_PLUGINS`, or `<venv>/aep-feature-plugins`) plus the workspace ledger.
    The newest enabled copy wins. `bundled-off.json` holds bundled plugins the owner
    switched off.
  - `features.for_host()` loads the plugins at `build_runtime`. A failure is skipped
    and recorded as `plugin_load_failed`.
  - The manager shows bundled plugins and `restart_required`. Bundled plugins can be
    disabled but not uninstalled.
  - `__pycache__` under `python/` is tolerated by verification and cleared before
    import.
  Tests: `tests/test_plugin_in_process.py` (11) and all plugin tests (87) pass, plus
  mypy. The test pinning the API version moved from 1.1.0 to 1.2.0; this is a
  legitimate contract change.
- `43bca516`:
  - The Windows bundle copies `feature_plugins/*/{plugin.json,python}` to
    `feature-plugins/`, and `install.ps1` copies that to `.venv/aep-feature-plugins`.
  - `scripts/build_bi_knowledge_plugin.py` builds `dist/bi-knowledge.aep-plugin.json`.
  - `in_process.ensure_bundled_importable()` is for the Shared Platform.
  Windows bundle/python tests (33) and installer tests (45) pass.

## In progress / interrupted by the restart
1. B2: physically moving BI out of `src/`. A subagent was working in a separate
   worktree `C:/TEMP/claude-bi/move`, branch `phase-plugins/bi-move-20261117`, based on
   `8f6029cd`. At the restart it had about 280 uncommitted changes and no commit. They
   are unverified, so inspect them (`git -C C:/TEMP/claude-bi/move status`) or redo
   the move. Target layout:
   - `feature_plugins/bi_knowledge/python/aep_bi/cards/` ← `src/capabilities/bi_cards/`
   - `aep_bi/host/` ← `src/host_runtime/bi_*.py` and `bi_page.py`
   - `aep_bi/feature.py` ← `features_bi.py`
   - Rewrite all imports and string module paths in src, tests and scripts.
   - `control_plane/bi_datasets.py` → `aep_bi.cards.snapshot`.
   - pyproject: pytest `pythonpath`, and mypy `files`/excludes for the new path; drop
     the bi_cards package-data.
   - Page sha256 must stay `86646dc3…`, and no test assertion may be weakened.
2. The stage A full-suite run (frozen copy `C:/TEMP/claude-bi/stageA` at `8f6029cd`)
   was at about 13% with 2 failures so far. The restart kills it. The log is
   `C:/TEMP/claude-bi/full-stageA.log`. Rerun it when the PC is quiet; the baseline is
   7029 passed / 16 skipped. Classify any failure against known CI flakes
   (`test_bi_many_sources_ui`, `test_bi_version_link_ui`, `test_weekly_report_workflow`)
   before trusting it.

## Next steps, in order
1. Finish B2 and merge it into this branch. In `features.py` set `BUILTIN = ()`.
2. Add `feature_plugins/bi_knowledge/plugin.json`: identity e.g. `bi-knowledge.bi`
   1.0.0, core_api 1.2.0–2.0.0, `in_process {package: aep_bi, entry: aep_bi.feature}`.
   BI then loads as a bundled plugin. Check that the package fits the limits (256 files,
   6 MB total, 2 MB per file) with `scripts/build_bi_knowledge_plugin.py`.
3. Call `ensure_bundled_importable()` before the `aep_bi` import in
   `control_plane/bi_datasets.py`.
4. Run the full suite, the 445 Knowledge comparison, ruff, format, mypy, and the
   wheel/sdist build. Check that the core wheel holds no BI modules. Then do a real
   update test: install BI 1.0.1 (one visible text change) from the Plugins page →
   restart → see the change; disable → restart → the BI tab is gone.
5. Get an independent Claude Code review. Then write `zh-TW` usage docs for owners
   (update BI = install the plugin + restart), add a TASKS row and finish this handoff.
6. Later, with its own scope consent: LLM Wiki the same way.

## Known risks
- BI code depends on about 15 core internal modules. A core change to those can
  require a new BI plugin version; `core_api` and compatibility tests manage this.
- A bundled plugin cannot be uninstalled, only switched off. A newer installed copy
  overrides the bundled one; uninstalling it falls back to the bundled copy.
- An earlier CI run failed on 3 BI UI timing tests that predate this work. They are not
  fixed here.
