# Handoff — Phase 7, workflow 10 is the active work

Updated: 2026-09-23 (Asia/Taipei).
Branch: `phase-7/chipset-rules`, slice 4a committed and in review.

Progress across every phase is in `docs/TASKS.md`. This file is only where
the current work stopped and how to resume it, and is rewritten each time.

## Where this stopped

The owner asked for **workflow 10**, `sales_to_chipset`: the CMP180 sales
opportunity lists projected into the `temp` sheet of the chipset readiness
workbook. It had never been inspected. It is now characterized in full, planned as
four slices, and slice 4a is built: the transformation is ported and the
source's own 149 test cases pass against it.

Read before continuing, in this order:

1. `docs/PHASE_7_MIGRATION.md`, "Workflow 10" — what the source does, what
   this migration does with each part, the parity gate, and twelve source
   defects each decided as preserved or fixed with the reason.
2. `docs/phases/PHASE_7_MIGRATION.md`, "Slice 4" — the four slices.
3. The source's own `docs/W1_MAPPING.md` in `.scratch/rs-source`, 511 lines,
   which declares itself authoritative over the code. It is the acceptance
   specification for the transformation.

**Workflow 11, the GTM weekly report, is complete in code and deferred.** Its
live parity run on a company workstation is still the thing only the owner
can produce, and it now comes after workflow 10 by the owner's decision of
2026-09-23. Nothing about it is unfinished in this repository; the steps for
that run are in `docs/phases/PHASE_7_MIGRATION.md` and
`deploy/windows-preview/README.md`.

## The next action

Slice 4b: reading, and the plan. `integrations.excel` reads row 1 as the
headers and turns every cell into text; this workflow needs the target's
headers from row 2, and needs real numbers and real dates to reach the rules,
which tell them apart from their text spellings. Then the capabilities that
read a project list and the target sheet, the planning capability, and the
preview Workflow over them.

From here on there is no safety net: the source's tests cover the rules and
almost nothing else, so every test for the reads, the plan, the write and the
change tracking is written here.

Before writing code, apply `.agents/skills/architecture-guard/SKILL.md` and
`.agents/skills/contract-development/SKILL.md`. The migration rule this phase
adopted is in the characterization: preserve what the parity gate measures,
fix only what is nondeterministic, unsafe or a crash, and record every
preserved defect rather than fixing it in passing.

## What is already done on this branch

- The owner's decision to migrate workflow 10 next is recorded.
- Two defects in the Excel adapter are fixed, found by reading the pinned
  source Bridge's Excel service, which is the parity baseline. It opens Excel
  with events suppressed and this adapter did not, so opening a team workbook
  would run its macros inside an unattended job. It also saves explicitly,
  where this adapter folded saving into closing, which the executor treats as
  best effort: a failed save left the report out of the file and the run then
  copied the staged workbook back and called it a success. Both are checked
  against a stand-in for Excel.
- Workflow 10 is characterized and planned.
- Slice 4a is built: the rules, the typed ruleset and the shipped default,
  with the source's tests passing case for case and five source defects
  fixed, each with a test naming it.

## Open items for the owner

- **The team's real ruleset is needed for the parity run.** The pinned source
  carries only `config/chipset-map.example.json`; the real
  `config/chipset-map.json`, which holds the team's chipset, vendor and brand
  knowledge, exists on the company machine. The example ships here as the
  default and as test data. The real file is host configuration and does not
  belong in this repository.
- Source workflow 7, `jira_team_tickets`, has never been inspected or
  migrated. It was named in the Phase 7 candidate table by mistake, in place
  of the weekly report that was actually built. Whether it is migrated at
  all is an owner decision nobody has asked for.
- The leaked credentials in the pinned `telegram-local-agent` source were
  checked on 2026-09-23 and the finding is in `docs/TASKS.md`: the Telegram
  bot token is already dead and the GitLab one is for a local WSL2 Docker
  instance that is not running, so neither is live. This repository never
  carried either (`.scratch/` is gitignored). Revoking them is still the
  owner's to do: the Telegram token through @BotFather, the GitLab token in
  that instance once WSL2 is running.
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
.venv\Scripts\python.exe -m build
git diff --check
```

At this commit: 1087 passed, 4 skipped, everything else clean. Three skips
need symbolic-link privileges and one an IPv6 loopback; all four run on Linux
CI, which runs the same chain on Windows and Ubuntu against Python 3.11 and
3.12. The weekly-report tests need a workbook reader (`openpyxl`, the `excel`
extra, which `office` also contains); none of them needs Excel or `pywin32`.
