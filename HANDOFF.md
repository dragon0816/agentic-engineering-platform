# Handoff — Phase 7, next is migration step 5, workflow 7 parity

Updated: 2026-09-23 (Asia/Taipei).
Branch: `main`, after PR #66 (slice 2i) merged with two review rounds applied.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Where this stopped

Slice 2i is merged and nothing is in flight. Every slice of migration step 4
is done: the resident Agent (2d), the Telegram ingress (2e) and the
authenticated shared-platform wire (2i). A company host can now be probed,
synchronized and driven by polled jobs from a control plane that serves the
in-memory references over HTTP.

## What 2i settled, because the next steps build on it

- A Bridge talks to the platform through six operations, each presented with
  its access token, and classifies every answer: only `answered` changes
  anything; `unreachable` is never treated as revoked.
- `synchronize` is how Skills and Workflows reach a company host: the member
  decides on the platform, the host installs the verified bytes and the
  bundle. A workflow migrated in the next steps is published as a package,
  chosen by the member, and synced — not hand-placed.
- Jobs reach a Bridge through `poll`/`settle`. Nothing runs twice within one
  process; across a restart of `aep-host jobs` a job whose settle was lost
  runs again (known limitation, `docs/TASKS.md`).
- The platform has no durable store and no member sign-in yet. Both are
  later slices; the server is run from a script that builds the references.

## Next: migration step 5, workflow 7 parity

`docs/TASKS.md` row 3; parity gate in `docs/phases/PHASE_7_MIGRATION.md`,
"Workflow 7 — Jira team tickets to Excel"; source characterization to write
into `docs/PHASE_7_MIGRATION.md` from the pinned
`host-bridge/jobs/jira_weekly_report.py`, `_weekly_rules.py`,
`_excel_upsert.py` and `_jira_client.py`, and
`workflows/07_jira_team_tickets_to_excel.json`, all in `.scratch/rs-source`.

What can be built inertly, and should be, before any live run:

1. The job's rules as typed capability and Workflow contracts: a Jira search
   capability over the platform's `Transport` (issue keys for a week, base
   JQL and updated window, with the safety cap), and an Excel capability
   that touches only `weekly report temp`, upserts by Jira key, prepends
   marker-tagged comments once in red, and retires stale weekly marks. Both
   fail closed and report typed failures; neither is retried by the engine.
   The old Host Bridge writes Excel through COM; how the platform writes a
   workbook (COM on the company Bridge, or a library) is a decision to
   record before the capability is written.
2. A dry run that produces the preview and performs no Excel or Outlook
   write.
3. Evidence the Phase 6 harness can grade: the normalized key set, the plan
   summary, sheet hashes before and after, normalized scratch-sheet rows,
   formatting assertions and a repeat-run comparison — all redacted, with
   the workbook itself never uploaded.
4. Tests against a fake Jira transport and a workbook on disk.

What cannot be built here: the parity evidence itself. It comes from a real
company Bridge with Jira credentials in its execution environment, compared
with the working old Host Bridge, and CI never claims it. When the code is
ready, the owner runs it; the handoff then records the evidence references.

Then workflow 13 (step 6), knowledge parity (step 7) and controlled cutover.

## How to verify

On Windows in `.venv` (Python 3.12), from the repository root:

```text
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m build
git diff --check
```

At this commit: 806 passed, 4 skipped, everything else clean. Three skips
need symbolic-link privileges and one an IPv6 loopback; all four run on
Linux CI, which runs the same chain on Windows and Ubuntu against Python 3.11
and 3.12.

## Open item for the owner

The pinned `telegram-local-agent` source's `config.yaml` commits a Telegram bot
token and a GitLab personal access token. Neither was copied into this
repository. Revoking them is an action in that repository, not this one.
