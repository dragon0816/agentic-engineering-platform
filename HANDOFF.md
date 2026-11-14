# BI Overview next slice — verified preparation, awaiting H1/H4 consent

Updated2026-11-14. Worktree:
C:/Users/Chi_L/.paseo/worktrees/2qnenase/it-owned-tools-20261112
Branch phase-plugins/bi-facade-20261114 from pusheda0496ae0.
Owner asked「請執行下個階段的實作」. This authorizes domain preparation but
is NOT inferred as new harness consent under AGENTS22. Exact H1/H4 scope was
presented using the async question tool; no owner answer yet. Do not edit core
schema/manager/process until explicit approval arrives. Do not infer from time,
Claude READY, agent notifications or the general request.

## Scope and files
Plan: docs/phases/FEATURE_PLUGIN_BI_OVERVIEW_PLAN_20261114.md.
Verified metadata: docs/phases/FEATURE_PLUGIN_BI_PREPARATION_20261114.json.
Domain source: feature_plugins/bi_overview/worker/aep_plugin_bi_overview/reader.py.
README states clearly it is not an installable plugin yet.
Tests: test_bi_facade_characterization.py, test_bi_overview_reader.py,
test_plugin_v1_compatibility.py; golden fixtures tests/fixtures/plugins_v1/.

Reader uses explicit bi_root, URI mode=ro/query_only and a per-database read
transaction. No BI imports, rebuilds, syncs, source writes or schema migration.
Unavailable/outdated/locked data isn't zero. Vault numbers refer to local working
projections, NOT published question-answer sources; freshness unknown. Selected
subscription copies only; never follow external registry paths. Five-second budget
bounds lock waits between datasets, not query/file-system time; conservative
leftover-journal refusal is documented.

## Actual verification and review
Final combined preparation:28 passed,0 failed/skipped in50.01s, JUnit/log under
.scratch/plugin-bi/preparation-freeze.*. Uncached global Ruff/format pass1517files;
mypy1144 sources pass including external reader. Reader latest tiny delta and
scope plan independently Claude-reviewed: Critical0/Important0. Newgoldenv1
package/stage/ledger captured from an actual unchanged PluginManager install;
4 tests verify identical digests, actual install and restored live tool reads.
No absolute paths/company data. Preserve fixtures before schema changes.
Characterization initial4pass1failure was a wrong test prefix, corrected using
production VAULT_PREFIX; reader additions had causal RED/GREEN tests.

Core src/ unchanged froma0496ae0,46 Knowledge source hashes unchanged. No new445
Knowledge/full-suite/build run claimed: this is unregistered domain preparation,
not finished Plugin packaging. No resident/main/Gateway/shared venv changes.
Actual Claude workers4cfe1b4e reader,9ba0d06a characterization,63582bfb goldenv1,
46cc8ffd independent review all finished; nothing polling or running.

## Proposed core changes, NOT implemented
H1: optional manifest declaration of existing BI location, explicit reserved
AEP_PLUGIN_READ_BI context on start/restart. This is declared context, not an
IT/tool permission gate or sandbox. Deriving today's path from data_root is
possible but rejected as undeclared coupling; see plan.
H4: UI-only read service contribution, default existing tools unchanged. No
CapabilitySpec policy/grants/ToolAccess/TurnEffects modifications. Cover old-v1
canonical digest preservation (omit ONLY new fields at their defaults), golden
restore, namespace ownership, tool-to-page version switch/rollback/busy.
Only common/plugins.py, plugins/{manager,process}.py plus plugin source/packaging/
tests proposed. No existing Host/Web/Telegram/BI/Knowledge paths may change.
If implementation needs them, present expanded scope instead of silently editing.

## Existing Slice1 CI and prior work
CI43537708699 completed failure:2 failed,6897 passed,74skipped (BI version-link
viewport and weekly draft assertion), plus artifact quota and RuffI001.
The Ruff import-order bug reproduced with --no-cache, fixed in95d003fd only in
tests/plugin_fixture_helpers.py. Other failures retained, not claimed fixed.
Original localfull6954pass3fail16skip followed by176passing UI repairs, and original
445Knowledge equivalence, remain documented in Slice1 acceptance; do not rewrite
as greenCI. Previous code/acceptance pushed througha0496ae0 on Slice1 branch.
Main still must not absorb excluded e564e1ad legacy false-success finding.

## Next actions
1. Keep preparation committed and reviewable; no installer/package success claim.
2. Wait for explicit owner H1/H4 approval; record exact words in DECISIONS/TASKS.
3. Freeze compatible contract using existing goldenv1 BEFORE parallel worker/UI
   packaging, then implement within the stated files and perform acceptance.
4. Full BI/interactive GUI or Wiki extraction requires later concrete scope and
   backup/restore evidence. No data movement in this overview slice.
