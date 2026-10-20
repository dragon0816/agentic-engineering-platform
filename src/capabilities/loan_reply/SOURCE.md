# Workflows 06 / 06b — loan_scan / loan_process (rs_workflow_system)

Strategy: **ADAPT with the source modules carried** (decision 2026-10-20 in
`docs/DECISIONS.md`). WRAP was not possible: the jobs call the source Bridge
over HTTP (`requests`) and its PowerShell-started Edge sessions, neither of
which AEP has. The pure modules are the source text apart from declared
replacements; the two jobs are the source text with seams for AEP's own
Outlook, browser and queue folder, and `process_one` split in two.

| | |
|---|---|
| Source | `dragon0816/rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43` (local clone `C:\Users\Chi_L\Documents\claude\n8n_workflow_system`) |
| Jobs | `host-bridge/jobs/loan_scan.py`, `loan_process.py`, `_loan_queue.py`, `_loan_rules.py`, `_loan_templates.py` (all committed at that revision) |
| Templates | `config/loan-templates/*.txt` — **not committed** in the source; SHA-256 below |
| n8n workflows | `workflows/06_loan_customer_block_reply.json`, `06b_loan_queue_consumer.json`: orchestration only (schedule every 30 min, a webhook, "run 06b if the queue has items"); replaced, not ported |
| AEP Workflows | `engineering/rs-loan-customer-block-scan` (06, `/run 6`), `engineering/rs-loan-queue-reply` (06b) |

SHA-256 of the inspected files (first 12 digits; in full in `docs/CONTRACTS.md`,
"Workflows 06 / 06b parity"): `_loan_queue.py` 5d818baa6d7f, `_loan_rules.py`
f94ce39f2246, `_loan_templates.py` f6ba083eabd2, `loan_process.py` ea07cfc230c7,
`loan_scan.py` 5f7961091c92. Template files: blocked-reply 12b3a49da66a,
customer-not-found-body 4401dd130c20, customer-not-found-subject 5df6de7fdda8,
failure-body 2c349ed06b20, failure-subject 5152bafce46c, shipping-reply
f35470f5ab2c, README 88733b124a13.

## Where each part went

| Source | AEP | How |
|---|---|---|
| `_loan_rules.py` | `rules.py` | carried; two import lines (pinned by `tests/test_loan_reply_parity.py`) |
| `_loan_templates.py` | `templates.py` | carried; the default folder is the package's `loan-templates/` (the source's dumped files, identical to the built-in text) |
| `_loan_queue.py` | `queue.py` | carried; imports, a home-folder default root (the host always passes its workspace), `_read` returns only JSON objects, `psutil.pid_exists` -> `processes.pid_exists` (psutil is not an AEP dependency) |
| `loan_scan.py` | `scan.py` | carried; `run(..., bridge, root, stamp)`; `resolve_start(write=False)` for the read step; `write_start_stamp` for the write step; no CLI |
| `loan_process.py` | `process.py` | carried; `process_one` = `look_up` + `draft_reply`; failure notice named `draft_failure_notice`; `run(..., bridge, root)`; screenshots beside the queue (`loan-shots`); `requests` errors -> built-in `ConnectionError` (`BridgeUnavailable`); no CLI (`--write-templates`, `--show-templates`) |
| `jobs/_bridge_client.py` | `bridge_api.py` (protocol, `BridgeClientError`) and `bridge.py` (`LoanBridge`) | the same calls and payloads, answered by `integrations.outlook_mail` (new `list_bodies`, HTML and SMTP sender), `integrations.outlook_draft` (new `reply`, never sends) and `integrations.browser.Browser` |
| `jobs/edge_session.py` | `edge_session.py` | names, ports and ready titles kept; open/close go to `LoanBridge`; no leases (nothing else drives these profiles) |
| source tests `test_loan_*.py` | `tests/test_loan_*_source.py` | vendored; imports and `requests.ConnectionError` only (`tests/loan_oracle.py`) |
| n8n 06 schedule / webhook | none | manual runs from Agent Web and Telegram; a schedule is the person's choice later |
| n8n 06 -> 06b chaining | `follow_up` on the scan's result | offered as a form (Agent Web) or a button (Telegram) the person presses |

## Capabilities (extracted building blocks)

| Capability | Side effect | What |
|---|---|---|
| `loan/scan-mail` | read | one Outlook folder, parsed (`scan.run` in dry-run mode without stamping) |
| `loan/enqueue` | write (local queue), approval | stamp the first-run cut-off, add the decided items; idempotent per borrow number |
| `loan/look-up` | read (web) | each queued form in the loan portal and C4C (`process.look_up`); claims nothing |
| `loan/draft-replies` | write (Outlook drafts, queue), approval | claim each item, save its reply / notice draft (`process.draft_reply`) or failure notice, finish done / failed |
| `loan/offer-send` | write (local cards), approval | one `ls-` send card per draft, only when the run asked |
| `loan/send-reply` | external_side_effect, approval, high risk | **declared, never installed**: only a person's press on one card sends (`host_runtime/loan_reply_cards.py`) |

## Differences from the source (each with a test)

1. **Split into steps.** The scan is read + write; the consumer is look-up, draft,
   offer. Ordering per run changes from "per item: read, draft" to "read all, then
   draft all"; per item the result is the same (`test_the_reply_drafts_what_the_source_job_drafts`).
2. **A dry run writes nothing.** The source's dry scan wrote the first-run stamp;
   AEP stamps on the first real run (`test_a_scan_dry_run_writes_nothing_not_even_the_first_run_stamp`).
3. **Loan links are opened only on the configured portal** (`portal_origin`,
   default `https://rstw-portal.rsint.net`); another link is a failed item with a
   notice, never opened (`test_a_link_to_another_site_is_never_opened`).
4. **No HTTP Bridge**: an unreachable Outlook or browser is `BridgeUnavailable`
   (built-in `ConnectionError`), handled as the source handled an unreachable
   Bridge: the item goes back to the queue, nothing is failed.
5. **Notices are HTML drafts** with the same text and line breaks (the source
   saved plain text); replies keep the source's plain text above the quote.
6. **Optional per-message send** (owner 2026-10-20), absent in the source.
7. **The run lock** is not taken by the read step; overlap is prevented by
   `occupies_machine` and by claiming each item atomically in the draft step.
8. **Settings** replace `config/workflow-06.json`: `mail_folder`,
   `max_messages`, `process_from`, `require_sender`, `sender_smtp`,
   `exclude_categories`; `alert_recipient`, `template_dir`, `portal_origin`,
   `c4c_home_url`, `loan_account`, `close_browsers_after`, `show_browser`, the
   three timings. Not carried: `loanProfile`/`c4cProfile`/ports (fixed names).

## Install

Shipped **switched off** (`host_runtime.assets.shipped_off`): Agent Web >
Capabilities > the Workflow > switch on, then its settings. Capabilities are
registered only while a Workflow using them is switched on; the device owner
gets grants as for every installed capability. Real-PC checks are listed in
`docs/phases/RS_WORKFLOW_MIGRATION.md`.
