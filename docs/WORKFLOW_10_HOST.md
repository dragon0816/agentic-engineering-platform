# Workflow 10 Host configuration and validation

The AEP Workflow 10 slice uses `rs_workflow_system` at commit
`896046e8fe2170d21f9213e56e5ce2f93c05ba43d` as its behavioral baseline:
`host-bridge/jobs/sales_to_chipset.py`, `_source_snapshot.py`,
`config/workflow-w1.example.json` and `docs/W1_MAPPING.md`. The source
repository is read-only. The pure transformation and ruleset were ported
earlier; the installed AEP preview now reads the configured source workbooks,
applies those rules to the existing managed sheet and returns a typed plan.

Set the following under `integrations` in the Host configuration. Use your
own absolute paths; these placeholders are not valid files:

```json
{
  "chipset_report": {
    "source_files": [
      {"path": "C:\\path\\to\\FY2526-sales.xlsx", "fiscal_year": "FY2526"},
      {"path": "C:\\path\\to\\FY2627-sales.xlsx", "fiscal_year": "FY2627"}
    ],
    "target_file": "C:\\path\\to\\chipset-readiness.xlsm",
    "target_sheet": "Chipset_requirement",
    "target_header_row": 2,
    "temp_sheet": "temp",
    "rules_file": "C:\\path\\to\\chipset-map.json",
    "backup": true
  }
}
```

The `chipset_report` object belongs alongside existing `integrations` entries;
do not replace those entries when editing a real `host.json`. If no `rules_file`
is set, the shipped example ruleset is used. That is useful for a synthetic
test, but it is not proof of parity with the team's actual mapping file.

`/run 10` invokes the read-only `engineering/sales-to-chipset-preview@1.0.0`.
The explicit `engineering/sales-to-chipset@1.0.0` Workflow runs preview then
an approved write step. The `chipset` Skill defaults to preview; its `apply`
command targets the write Workflow. Installation alone gives neither
`chipset-report.read` nor `excel.write` permission. The Host must provide
exact Bridge grants and the write approval required by the capability.

Before writing, the adapter checks the managed sheet and temp-sheet digests,
refuses an open workbook, creates a backup, edits a staged copy with Excel COM,
and verifies sheet names, managed and other sheet values/formulas and VBA
project bytes before copyback. It writes only the temp sheet and advances the
source-diff baseline only after verified copyback. This is an AEP safety
adaptation; compare the staged result with the source job on a workbook copy
before claiming production parity. The owner's actual source workbooks and
mapping rules were unavailable during this slice, and real Excel COM writes
could not be verified in the sandbox because Excel opened a synthetic workbook
read-only. Fake-COM and Agent/Bridge admission tests passed.
