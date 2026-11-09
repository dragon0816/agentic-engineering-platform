# C4C SOP Workflow: authenticated live acceptance

Owner requested a real automatic run after the attachment/draft acceptance.
This supersedes the earlier evaluation's untested-live status; it does not
rewrite its historical draft/fixture evidence.

## Execution and outcome

- The separate native Edge session completed company SSO without credentials.
- Followed Sales Orders / All / Advanced Search / Document Date Between the
  supplied fiscal-year dates. The actual view uses DD.MM.YYYY and decimal comma.
- No Export/Spreadsheet control exists in this view. The SOP says copy the
  table, so Browser reads all visible pages and restricted local Python creates
  Excel. No SAP HTTP endpoints, application internals, order edits or messages.
- Full WorkflowEngine -> Bridge -> Browser/coding -> shared Workflow Harness
  replay succeeded. The installed dedicated coding interpreter retained its
  outbound firewall requirement and production-approved workspace root.
- Initial query returned 749 rows; later live runs returned 750. The manifest
  validates the current displayed count rather than hardcoding either number.
- Final run `run-e390791473b84a95af7cbb43b6bfa923`: 750 raw/enriched records,
  750 unique order IDs. Independent verification matched every raw field, date,
  currency conversion and all 106 monthly groups. Full-precision EUR sums and
  source-currency totals reconcile; display uses two decimals. Mapping input is
  byte-identical to the owner's original.
- 173 records have no mapping: nine nonempty Owner names and two blank records.
  They remain in raw/detail/monthly totals with explicit UNMAPPED department and
  Exceptions rows. No guessed departments or silent omissions. Completing the
  business department classification requires extending the supplied lookup.

Private package under `%USERPROFILE%/Documents/aep-workflows/c4c-sales-order-report`:
`workflow.json`, copied lookup in `input/`, report and summary in `output/`.
Business rows, raw totals, source files and the manifest remain outside Git.
Evidence and independent verifier live in `.scratch/c4c-live-validation/` and
`.scratch/verify_c4c_live.py`. The unused draft output-name form field was removed;
the output filename is fixed. The saved manifest's final defaults/input contracts
were validated again after that presentation cleanup.

## Failures caught before acceptance

- DOM click did not activate SAP controls: trusted press/release regression failed
  before the native-pointer fix. Read-mode refusal still precedes event delivery.
- Hidden duplicate navigation and role=option matching had failing regressions
  before fixes. Visible ambiguity continues to refuse.
- Sales expands with its panel arrow; the title/icon alone is insufficient.
- Guessed label captions were replaced by observed stable CSS targets.
- Old query tables/counts remain while new queries start. Await the loading
  marker and numeric count; use a non-busy table selector.
- Frozen ID cells lag other fields during pagination. Changed row data alone
  accepted mixed snapshots; independent unique-ID validation rejected them.
  Stable snapshots and declared key columns now wait for complete ID progress.
- Engine capability completion alone was not accepted as proof of Excel success.
  Use the shared Harness, delete the previous target report before processing,
  require a nonempty report, and independently assert both Python exit codes.

## Verification

- Final Browser/web-script/session modules: 39 passed in 262.65s.
- Final authoring/preview modules: 8 passed in 55.74s.
- Independent live report/source/mapping/amount/monthly verification: passed.
- Ruff check/format (1398 files), Mypy (1052 files), sdist/wheel build and pip
  dependency check: passed.
- Full-suite collection: 6026 items / 524 modules, four disjoint file shards;
  GUI opt-in disabled as in previous full runs. Two later readiness/frozen-key
  regressions are included in the final 39-test module run above.
- Full-suite initial result: 6013 passed, 10 item skips, 3 failures, no errors.
  Shards: 1453/2 pass/skip (4197.81s); 1402/2 plus one failure (2547.37s);
  1631/5 plus one failure (2864.71s); 1527/1 plus one failure (4353.56s).
  Optional av also skips at collection. Initial full run was not green.
- Every initial failure was inspected and its whole unchanged module rerun:
  PowerShell script_timeout -> test_script_tools.py, 6 passed in 12.38s;
  Library wide-layout assertion measured narrow layout -> test_library_content_web.py,
  6 passed in 95.95s; legacy web capability got profile_in_use at its origin-refusal
  assertion -> test_web_capabilities.py, 4 passed in 45.25s. No production fix
  inferred from those reruns and no assertion/timeout relaxation. The Library
  failure also appeared in the earlier document full suite before this change.
- Final normal collection: 6028 items/524 modules. Compared case counts with the
  full run, allowing timestamp-generated parameter labels: none removed, only
  the two new readiness/frozen-key regressions added; both passed in the final
  39-test run. Evidence: .scratch/c4c-coverage-delta.json, c4c-shard-N.log/.xml,
  c4c-suite-result.json. Full-run failures are retained, not rewritten as passes.
- Final diff architecture guard passed: generic Browser/typed-contract changes,
  unchanged control/execution plane split and approval/origin policies; no
  SAP-specific core routing, provider change, secrets or publishing authority.

## Delivery limits

No resident Host update/restart, installation, publication or push. This is the
modified-source runtime's live acceptance. The resident Host must first receive
the new Browser action contract before it can install this manifest through its
normal approval flow. The separate test browser is closed. Missing lookup entries
are a reported business-data limitation, not a silently successful department join.
