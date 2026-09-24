# Handoff — Phase 7, the weekly mail and the ways in

Updated: 2026-09-24 (Asia/Taipei).
Branch: `phase-7/weekly-mail-effort`, pushed, no pull request opened yet.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Where this stopped

Two things were asked for and both are built:

1. **The weekly mail.** `weekly.mail 2026_39W` now reads the board, counts the
   week's effort, draws a pie chart and saves a draft in Outlook. It never
   opens the workbook and it never sends.
2. **Ways in that are not a command line.** `aep-host chat` opens a window
   onto the resident Agent, and the bundle now carries four things an
   operator double-clicks plus a Windows scheduled task.

Everything below is committed on this branch and the verification chain
passes at its tip.

### The mail, in pieces

- `capabilities/weekly_report/effort.py` — who worked on what, counted the
  way the source counted it. Tickets, not hours; a ticket naming several
  instruments counts under each; an item whose timestamp merely moved is not
  work, and the ones left out are **named**, not subtracted.
- `capabilities/weekly_report/mail.py` — what the mail says, pure.
- `capabilities/weekly_report/chart.py` — the pie, drawn here. No matplotlib,
  which would have meant numpy, Pillow, fonttools and contourpy in an offline
  bundle installed with `--no-index`. `zlib` and `struct` write the PNG. No
  text is drawn: the legend is the HTML table under the picture, one colour
  swatch per row.
- `integrations/outlook_draft.py` — the draft through Outlook COM. **No call
  that sends a mail exists in it, and a test reads its own source to keep it
  that way.**
- `capabilities/weekly_report/handlers.py::MailHandler` and `MAIL_SPEC`, the
  `engineering/jira-weekly-report-mail@1.0.0` workflow, the `weekly mail`
  Skill command, and the host wiring.

### The ways in

- `host_runtime/window.py` and `aep-host chat` — a Tk window over the same
  `LocalAgent`, on the same `local` ingress, building the same request the
  command line builds. No routing, policy or capability lives in it.
- `deploy/windows-preview/chat.cmd`, `weekly-preview.cmd`, `weekly-apply.cmd`,
  `weekly-mail.cmd`, `schedule-weekly.ps1`.

## The next action

**The owner has redirected the interface work to a web UI.** Decided
2026-09-24, in this order of priority:

1. A web interface served by the host, replacing the Tk window. The Tk window
   stays for the next release because it is finished and works; it is removed
   once the web one does the same job.
2. It must be **generic**. No application-specific screens: there is to be no
   "weekly report page". The weekly report is one installed asset among many
   and appears only in the generic lists.
3. First version to contain: the Agent conversation and command execution;
   the installed Skills and Workflows on this machine; the Skills and
   Workflows other people have published on the shared platform; and support
   for **several agents, each configured with its own skills, LLM and memory**.
4. Reachable from **this machine only**: bound to the loopback address with a
   token the command prints. Network access was considered and deferred.

Before writing any of it:

- The several-agents requirement is an **architecture question, not an
  interface one**. Today a host assembles one resident Agent bound to one
  member. Whether a machine may hold several, each with its own skills, model
  and memory, is a change to `docs/ARCHITECTURE.md` and must be specified
  there before code, per this repository's own rule. Do not invent it inside
  a UI.
- `src/control_plane/http.py` is the precedent to follow: an HTTP service from
  the standard library alone, bearer-token authenticated, with TLS. A web UI
  adds no dependency and must not: a company machine behind a proxy cannot
  fetch a CDN, so everything is served by the host itself.
- A local web server that runs capabilities is an ingress with a real attack
  surface the Tk window did not have — any process on the machine, any browser
  tab. Loopback binding and a per-run token are the floor, not a nicety.

**Workflow 10** (`sales_to_chipset`) slices 4b, 4c and 4d remain unbuilt and
are deferred behind the interface work by the owner's ordering. Slice 4a is
done; `docs/PHASE_7_MIGRATION.md`, "Workflow 10" is the specification and the
source's own `docs/W1_MAPPING.md` in `.scratch/rs-source` is the acceptance
specification for the transformation.

## Open items for the owner

- **A sheet was lost from the real workbook on 2026-09-24 and has not been
  restored.** The first real write renamed `2026_38W` to `weekly report temp`.
  The cause is found and fixed, and a save guard now refuses a write that
  loses a sheet. The backup taken before that run still holds `2026_38W`, and
  restoring it into the live workbook is the owner's to do.
- **The Outlook drafter has never been run against a real Outlook**, exactly
  as the workbook writer was unproven before 2026-09-24. Neither this
  developer machine (`OPENLAB01`) nor CI has Office: the registry says so.
- **The real ruleset is needed for workflow 10's parity run.** The pinned
  source carries only `config/chipset-map.example.json`; the real
  `config/chipset-map.json` lives on the company machine and is host
  configuration, not repository content.
- The leaked credentials in the pinned `telegram-local-agent` source were
  checked on 2026-09-23 and the finding is in `docs/TASKS.md`: neither is
  live. Revoking them is still the owner's to do — the Telegram token through
  @BotFather, the GitLab token in that WSL2 instance once it is running.
- CI should walk the documented operator steps under a legacy code page. Every
  failure the owner hit between 2026-09-23 and 2026-09-24 could only happen on
  their machine, never on this one, because the code was verified here and the
  operator's path never was.
- The workflow assets are still named `jira-weekly-report*` although Jira is
  gone and the source is a GitHub project board. Renaming them is a published
  identity change nobody has asked for.
- Source workflow 7, `jira_team_tickets`, has never been inspected. It was
  named in the Phase 7 candidate table by mistake. Whether it is migrated at
  all is an owner decision nobody has asked for.
- Whether a tool approval must come from a second person is an owner policy
  decision nobody has asked for.
- Taking somebody off a shared machine is still a host action, not a platform
  one (slice 2j).

## How to verify

On Windows in `.venv` (Python 3.12), from the repository root:

```text
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe -m pip check
git diff --check
```

At this commit: **1178 passed, 4 skipped**, ruff and mypy clean. Three skips
need symbolic-link privileges and one an IPv6 loopback; all four run on Linux
CI, which runs the same chain on Windows and Ubuntu against Python 3.11 and
3.12. The weekly-report tests need a workbook reader (`openpyxl`, the `excel`
extra, which `office` also contains); none of them needs Excel, Outlook or
`pywin32`.

The Tk window was additionally driven for real, not only unit-tested: a window
was opened over a real host, a request typed into it, and the answer read back
out of the transcript widget. `tkinter` ships with the CPython the bundle's
virtual environment is built from, so no dependency was added.
