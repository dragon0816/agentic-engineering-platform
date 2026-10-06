# coding_v1

Twenty natural-language tasks submitted to the AEP Agent through its existing
entry point (Agent Web chat), checked by independent validators.

| Folder | Who reads it |
|---|---|
| `prompts/` | the Agent under test (one prompt per task, filled with its workspace and URLs) |
| `fixtures/T??/input/` | the Agent (copied into the task's workspace) |
| `fixtures/web/`, `fixtures/servers.py` | served over HTTP on 127.0.0.1 for T09-T13 |
| `evaluator/` | the evaluator only: validators, reference samples, self-test |
| `adapters/` | the evaluator: the Agent Web chat adapter |
| `runs/<run_id>/` | results: `metadata.json`, `results.jsonl`, `report.md`, `T??/` evidence |

## Prepare

```
.venv\Scripts\python.exe benchmarks\coding_v1\fixtures\build_fixtures.py   # rebuild; hashes must equal MANIFEST.json
.venv\Scripts\python.exe benchmarks\coding_v1\prompts\write_prompts.py
.venv\Scripts\python.exe benchmarks\coding_v1\evaluator\selftest.py        # expect "0 self-test problem(s)"
```

Fixtures are deterministic (`MANIFEST.json` holds every SHA-256). Dependencies:
the repository `.venv` (Python 3.12, openpyxl, pypdf) and a running Agent Web
started from this repository (`aep-host web ...`, log in `.scratch/`).

## Run

```
.venv\Scripts\python.exe benchmarks\coding_v1\run.py --run-id baseline-run-001 --tasks pilot
.venv\Scripts\python.exe benchmarks\coding_v1\run.py --run-id baseline-run-001 --tasks all
.venv\Scripts\python.exe benchmarks\coding_v1\run.py --run-id <new-id> --tasks T01,T18
```

Each task: a fresh workspace `runs/<run_id>/T??/workspace` (inputs copied),
a new chat session, the prompt sent as one chat turn (T20 gets the scripted
threshold answer once if the Agent asks), then the validators. A task already
recorded in a run is skipped unless `--force`. Never rerun into a baseline
run ID after changing AEP; use a new run ID.

## Status rules

`PASS` all checks true. `FAIL` the Agent produced output or claimed completion
but checks fail. `BLOCKED` no output and no usable tool (entry, tool or
permission gap). `TIMEOUT` over 600 s. `NOT_RUN` not submitted. A check whose
evidence is missing is `null` and never counts as passed.
