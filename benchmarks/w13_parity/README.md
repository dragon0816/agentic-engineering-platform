# w13_parity

This benchmark checks that Workflow 13 behaves the same in the original `rs_workflow_system` job and in AEP when both get the same inputs. See `docs/WORKFLOW_13_SOURCE_CONTRACT.md`.

```
.venv\Scripts\python.exe benchmarks\w13_parity\parity.py --run-id p001 --source C:\Users\Chi_L\Documents\claude\n8n_workflow_system
```

Each case runs in two isolated roots that start as identical copies of one bare `origin`. The original job runs in one root, through `source_runner.py`. That script needs a Python with `requests` (the system Python), and it never reads the real `config/workflow-13.json`. AEP's prepare, then commit, runs in the other root. Nothing is pushed.

`runs/<id>/results.json` holds every compared field. The working copies stay in `runs/<id>/work/`, which git ignores.
