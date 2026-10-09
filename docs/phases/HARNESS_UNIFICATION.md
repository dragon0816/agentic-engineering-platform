# Harness unification: one skeleton, domains as Skills and adapters

Owner decision 2026-10-09 (review of `docs/HARNESS_DESIGN.zh-TW.md`): Coding, Workflow execution, Knowledge asking and conversation tasks run on one Harness skeleton. What differs is declared by Skills and implemented by domain adapters. The Workflow engine and the coding sandbox stay, as ways of executing. The Knowledge tool route returns the answer the Harness validated. Benchmarks run any time when they need no GUI; GUI tasks run only while the owner is away.

## The skeleton

```
plan (Skill guidance + Host task) → [collect] → execute → validate (Host checks)
     → validated | retry (budget) | needs_input | failed
```

- `agent/harness_plan.py`, `agent/harness_run.py` and `agent/harness_runner.py` are the single control loop.
- A domain adapter implements `HarnessActions`: `collect_context()`, `execute()` and `validate()`. It reaches capabilities only through the Bridge. Its checks come from the Host and are never the model's claim.
- The Skill declares the domain, required evidence, fallback, retry budget and, from this change on, the Host checks to run. The Skill can narrow what is done; it can never grant anything.
- **Kept, not merged:**
  - the Workflow engine's journal, checkpoints and recovery: deterministic execution under `execute`;
  - the coding runner's isolation (low integrity, Job object, no network, worktree);
  - the Bridge as the only authorization point.

## Slices

| Slice | What | Done when |
|---|---|---|
| U1 | Core: build a plan without a full TaskContract; a `retry_from` stage, so a repair goes back to execute rather than replanning; adapter-named exhaustion codes; the `coding_change` telemetry run kind | Contract tests; existing Knowledge tests unchanged |
| U2 | Coding: `CodingHarness.run` drives `CodingActions` through the shared runner (plan = collect, change = execute, declared commands = validate, repair = retry from execute). Result contract and failure codes unchanged | All coding harness tests pass unchanged |
| U3 | Workflow: `WorkflowActions` (collect = static preflight, execute = engine run, validate = steps succeeded plus the Workflow's declared output checks). Retry budget 0 (a re-run could repeat side effects) | Workflow tests unchanged, plus output-check tests |
| U4 | Conversation: each turn's answer goes through Host checks (no claim of a completed action without a tool, named output files exist and are not empty). One retry with the failed check as feedback | Gateway tests, plus negative cases |
| U5 | Knowledge: the Harness is a host module used by both routes. The tool route returns the validated answer as the turn's answer. The retry budget comes from the Skill, and a retry broadens retrieval | Knowledge tests; knowledge_v1 sample before and after |
| U6 | Small items: draft revisions that remove steps need an explicit acknowledgement; external agents run an installed, unchanged Workflow directly; stale documents updated | Tests |
| U7 | Verification: the full suite at each slice; the knowledge_v1 sample and the coding_v1 non-GUI tasks after U4 and U5; lab and GUI tasks when the owner is away; telemetry compares strategy_ids | Findings written |
