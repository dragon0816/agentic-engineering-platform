# knowledge_v1: Knowledge asking through the harness

Owner request, 2026-10-07. This benchmark checks that a Knowledge question runs through the harness loop and comes back with real, reasonable evidence. It is a harness check, not a gold-answer test: the question bank deliberately has no golden answers.

## Question bank

`questions/source.md` is the owner's file (`RS_Knowledge_1100_Benchmark_Questions.md`), copied unchanged. `questions.py` pins it by sha256, so a run never asks a rewritten question.

The bank has 1,100 questions:
- Q0001–Q1000 cover 5 markets × 4 product families × 50 questions.
- Q1001–Q1100 are product-related foundation questions.

`python benchmarks/knowledge_v1/questions.py` writes:
- `questions/questions.json`: the parsed questions;
- `questions/sample.json`: the fixed 110-question sample, made of 5 questions per market × product cell (the left-out question type rotates between cells) plus every tenth foundation question.

## Running

    .venv\Scripts\python benchmarks\knowledge_v1\run.py --run-id <id> --set sample --workers 2
    .venv\Scripts\python benchmarks\knowledge_v1\run.py --run-id <id> --set all --workers 2
    .venv\Scripts\python benchmarks\knowledge_v1\run.py --run-id <id> --regrade

`--set` also accepts a comma-separated list of question IDs.

The runner works as follows:
- Each question goes to Agent Web chat, the same path a person uses, in a new conversation. Questions are sent as written, without naming a knowledge base, so the Agent must pick Knowledge itself.
- Runs resume: questions that already have a result are skipped unless `--force` is given.
- `--regrade` grades the stored traces again without asking.
- It needs a running Agent Web (found through `.scratch/agent-web-*.out.log`) and the reviewer's key in the user environment (`LITELLM_MASTER_KEY`, mapped in host.json). The key is never written to disk.

The benchmark uses no GUI, so it can run during working hours.

## Grading (grader 1.1, reviewer 1.0)

| Status | When |
|---|---|
| PASS | The Knowledge loop ran (the direct harness or the `knowledge__*` tool), the answer cites evidence, every cited file exists in the Vault with the passage text in it, and the reviewer finds the main points supported and the conclusion reasonable |
| INSUFFICIENT_KNOWLEDGE | The loop ran and reported that the Vault lacks the evidence, with no citations. The question file counts this as acceptable. A gap reply that still cites evidence (a partial answer naming what is missing) is checked and reviewed like any answer (grader 1.1) |
| FAIL | Knowledge was not used (`EXECUTION_GAP`), no or unverifiable citations (`VALIDATION_GAP`), or the reviewer found the answer unsupported or unreasonable (`REASONING_GAP`) |
| NEEDS_HUMAN_REVIEW | The reviewer gave no verdict, or gave one with low confidence |
| SYSTEM_ERROR | A timeout, an HTTP error, or the conversation or Knowledge call failed |

The reviewer (`judge.py`) is the company Gateway model. It sees only the question, the answer and the cited passages, never the Vault or the web, so "reasonable" means reasonable on the cited evidence. The bar is a reasonable, evidence-backed answer, not a line-by-line audit. Claims that go beyond the passages are listed for reference. Every verdict and reason is stored in the question's `result.json` for spot-checks.

How citations are located depends on the route:
- **Direct route:** the answer's `[n]` numbers index the Knowledge record's passages.
- **Tool route:** the conversation model names sources by file path, so the passages of every Knowledge call in the turn are matched to the files the answer names.

Each run writes, under `runs/<id>/`:
- `metadata.json`;
- one folder per question, holding `trace.json` (the full reply) and `result.json` (status, gap, citations checked, review);
- `report.md`, with counts by market, product family and question type, the harness routes and gap types, and every question that did not pass.

`python benchmarks/knowledge_v1/selftest.py` checks the grader offline, with one synthetic reply for each status.
