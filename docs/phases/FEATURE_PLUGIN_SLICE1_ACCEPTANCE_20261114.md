# Feature Plugin Slice 1 verification and delivery

Date: 2026-11-14. Branch: `phase-plugins/slice1-20261113`.
Assessment and scoped consent were reviewed by Claude Code and pushed at
`6d0132ed`; typed contracts were committed at `8035f78c` before parallel work.

## Delivered scope

Generic fixture-only feature packages now install through authenticated Agent
Web without approval cards, register namespaced Bridge tools and declarative
pages, and activate bundled Skills/Workflows without restarting the Host.
Multiple plugins coexist. Update, disable, enable, restart recovery and uninstall
own only the plugin's contributions; uninstall preserves data and user edits.
Workers use the current interpreter and ordinary environment, with bounded JSONL
requests, responses and timeouts. They are separate processes, not sandboxes.

The original per-turn successful-effect receipts are unchanged. No durable
receipt guarantee or automatic retry of uncertain writes was added. Packages
declare digests; matching a digest is not publisher trust or business approval.
Publisher HTML/JavaScript/iframes, dependency installation, database migrations,
BI/Wiki extraction and Knowledge routing/model changes are outside this slice.
Agent package-install tooling is not implemented in this slice, not prohibited.

## Independent review and fixes

Claude Code handled contracts/manager, Web/browser and independent integration
tests in parallel after the contract freeze. A separate source reviewer reproduced
the junction-cleanup, exact-dependency update and interrupted-upgrade asset-loss
bugs with synthetic data. These were fixed and re-reviewed. Further repairs cover
ledger-first teardown, output-model capture, live-refresh rollback, retirement
recovery and byte revalidation before worker restart. The Python3.11 junction
fallback has a causal missing-API simulation; no real3.11 execution is claimed.
Final source, compatibility and UI-delta reviews: Critical0, Important0.

## Actual test results

| Check | Original result |
| --- | --- |
| All plugin tests, including real browser | 231 passed, 1 privileged-symlink skip |
| Full suite | 6954 passed, 3 failed, 16 skipped; 2:02:50 |
| UI/settings/plugin Web/browser modules after repairs | 176 passed; 1:00 |
| Exact Knowledge baseline in full suite | All445 cases present and passed, identical outcomes |
| Knowledge source integrity | 46 files unchanged before and after repairs |
| Global Ruff / format / configured mypy | Passed; 1508 formatted files, 1139 type-checked files |
| Wheel/sdist build and pip check | Passed; no broken requirements |
| Wheel source comparison / isolated imports | All580 Python files match after newline normalization; imports passed |

The full run was **not green**. One failure was introduced by the plugin panel
placeholder sitting in the BI test's text range. Moving the complete plugin
section after Reviews repaired the panel boundary without editing the BI test.
The other two were pre-existing expectations of `IT/OS/service permissions`,
left behind when owner-approved commit `a902df0f` removed the IT prerequisite.
Tests now require the exact current `OS/service permissions` wording and also
assert that the old IT wording is absent. No assertion was removed or loosened.
All three cases passed in the 176-case affected-module run.

Only page placement, these exact test expectations and source-package inputs
changed after the full run. Execution contracts, manager and Knowledge sources
did not change. A second full suite was not run; the final result is a retained
original full failure plus passing targeted repairs, not a claimed all-green
full rerun. Original XML/logs and their hashes are preserved locally; committed
metadata is in `FEATURE_PLUGIN_SLICE1_VERIFICATION_20261114.json`.

All tests use synthetic workspaces. Opt-outs: AEP_OUTLOOK_TESTS=0,
AEP_GUI_TESTS=0 and AEP_NATIVE_CLI_TESTS=0. The browser tests do run headlessly;
live company resources and real-model Knowledge answer quality were not tested.
The16 skips are environment/live-service cases, listed in the local raw evidence.

Before build, all1696 frozen files matched. After build, only the documented
UI/test/package-input changes and generated egg-info differ. The source archive
includes the example, builder, canonical worker and its package helper. Wheel
imports were checked directly from the wheel with isolated Python; the shared
editable environment was never rebound.

## Usage and remaining boundaries

See `FEATURE_PLUGIN_SLICE1_USAGE_20261113.md`; example package:
`examples/plugins/hello.aep-plugin.json` (`demo-hello.fixture`). This is a local
synthetic demo, not an extracted BI/Wiki feature or a public plugin SDK.

Known nonblocking limits: a late post-commit live registry refresh failure may
leave old live entries until safe restart; configured status may remain active
after a changed-package worker restart is refused, though every call reports the
failure and changed code is not run. Both were explicitly reviewed and documented.

No main merge, resident restart/update, shared Gateway change, company processing
or replacement of the previously accepted Sales Order package was performed.
The next functional slice is a separately scoped BI/Wiki extraction with backup,
restore and Knowledge equivalence evidence, subject to AGENTS22 consent.
