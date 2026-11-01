# Atlas dashboard read goldens (vendored)

Producer: Atlas, `web/tests/fixtures/atlas_dashboard_golden/` at commit `49600737` (branch
`bi-analysis-dashboard-atlas-brief-a1-a2-i1`), contract `docs/AEP_DASHBOARD_READ_CONTRACT.md` revision
2026-11-01. Consumer: AEP's Atlas dashboard import (BI K2,
`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md`).

`list.json`, `dashboard-mixed.json` and `dashboard-legacy.json` are the exact HTTP response bodies (no final
newline), copied byte for byte. Never edit them here: a contract change starts in Atlas. Check for drift
against an Atlas checkout:

    python scripts/check_atlas_dashboard_golden.py --atlas <Atlas repo>
