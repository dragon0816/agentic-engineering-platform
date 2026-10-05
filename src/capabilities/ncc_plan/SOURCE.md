# Workflow 14 — ncc_improvement_plan (rs_workflow_system)

Strategy: **ADAPT** (decision 2026-10-05 in `docs/DECISIONS.md`). WRAP was not
possible: the job needs python-docx/lxml, pdfplumber, requests and the source's
ops and Bridge clients, and script tools run stdlib-only.

| | |
|---|---|
| Source | `dragon0816/rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43` |
| Job | `host-bridge/jobs/ncc_improvement_plan.py`, `_ncc_rules.py`, `_ncc_sources.py` |
| n8n workflow | replaced by the AEP Workflow `engineering/rs-ncc-improvement-plan` (`/run 14`) |

## Where each part went

| Source | AEP | How |
|---|---|---|
| `_ncc_rules.py` | `rules.py` | carried; only the `typing` import line modernised (pinned by a test) |
| `tests/test_ncc_rules.py` | `tests/test_ncc_rules_source.py` | 51 rule tests unchanged except the import path |
| `stations_from_config`, `find_station`, `run` load/price part | `planning.py` (`prepare_plan`) | ported; resolves every document string |
| docx helpers and `run` render part | `document.py` (`render`) | ported; python-docx from the `office` extra |
| `create_draft` (Bridge `email_draft`, `send=False`) | `capabilities/mail_draft` (`outlook.draft`) | **extracted building block**: draft only, file attachments, `skip`, `best_effort` |
| `publish_reference_sets` (`ref:nccStations`) | `fn:ncc_plan.stations` | a choice function over the catalogue the settings name |
| `STEPS` | `progress_steps` (prepare, render, draft) | |
| `PARAMS_SCHEMA` x-ui fields | one parameter declaration in `manifest.py` | same names for the 11 system ticks |
| `config/workflow-14.json` `paths` | per-install settings `catalogue_file`, `template_file`, `output_dir`, `photo_dir` | |

## Not carried yet

- `reimportSources` and `sourceFiles` uploads: re-reading the MODA station
  table (.docx), the price list (.pdf, needs pdfplumber or pypdf) and the
  template's system list into the catalogue. Until then the catalogue file is
  edited directly or produced by the source job.
- `refreshOnly`: not needed; the station menu is read live.
- Hidden one-off overrides without a form control in the source: `services`,
  `equipmentModel`, `power`, `serviceChannels`, `contractor`, `planYear`
  (the catalogue's station and document values apply).
- The catalogue's `params` section (for example a default `dryRun`) and its
  `ops` section are not read.

## Parity evidence

- `tests/test_ncc_rules_source.py`: the source's rule tests.
- `tests/test_rs_w14_ncc_plan.py`: the job-body behaviour the source pinned
  (dry run writes nothing and has `verdict.ok = None`; written plan reports
  `verdict` and `files`; an absent output folder is refused, not created; a
  document open in Word is refused with nothing changed; the draft is never a
  send and a failed draft does not fail the run; the dry-run switch comes
  before the station) through a real host with Bridge grants, plus generated
  web, settings, Agent and Telegram forms; and, where the source clone and its
  uncommitted `ncc_paper/` documents exist, the same document text as the
  source job on the real template and catalogue.

## Install

The Workflow and Skill ship in `host_runtime.assets.shipped()`. A run needs
grants for `ncc-plan.prepare`, `ncc-plan.render` (approval) and
`outlook.draft` (approval), and the four settings on the Workflow settings
page. Outlook drafting needs the `windows` extra on the company PC.
