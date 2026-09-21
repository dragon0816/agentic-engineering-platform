# Phase 6 source inspection and disposition

Source: `dragon0816/knowledge_management`, commit
`2f5e6d0431c5b6af8fbee05c6c0a5779e1a84bb9` (read-only shallow clone), inspected
this time for its benchmark suite: `bench/run.py` (684 lines),
`bench/selftest.py` (200), `bench/README.md` (100), plus `bench/problems/` and
`bench/reference/`.

| Source | Observed behavior | Decision and preserved boundary |
| --- | --- | --- |
| `bench/run.py` | prompts each configured model with ten coding problems, writes the generated code to a scratch directory and runs a hidden `unittest` module against it; also grades by diff similarity to a baseline and by AST rules (`forbid_nodes`, `require_calls`, `allow_imports_only`) | NOT MIGRATED. It measures a model's coding ability, which is a procurement question, not the platform's behavior. It needs a live gateway and executes model-written code in a subprocess, so it cannot satisfy the Roadmap's "runs in CI without production side effects" |
| `bench/selftest.py` | runs every hidden suite against a reference solution, and runs deliberately wrong answers against the graders to confirm they are rejected | **ADAPT the idea** in slice 1. "A grader that passes anything would report a perfect score and be believed" is exactly the risk in a harness that reads declared assertions. Every grader in `common.evaluation` must have a case that fails it |
| `bench/README.md` "Two axes, kept apart" | a problem failing in `tools` mode but passing in `plain` mode is a gateway finding, not a model verdict | ADAPT as an invariant: a deterministic case that fails is a platform regression, and a model-involving case is a separate class that cannot be read as one |
| `bench/README.md` "`--repeat 1` is not a measurement" | the models are not deterministic; a single cell is not a conclusion | ADAPT in slice 3, where repetition is part of the contract rather than a flag someone remembers to pass |
| `bench/README.md` scoreboard header | records the dated upstream build id taken from the provider directly, because LiteLLM rewrites `response.model` to the model group name | Already carried into Phase 5: `ModelResponse.model_alias` is the platform's alias and a provider's echo is never treated as evidence of what served a request |
| `bench/problems/`, `bench/reference/` | ten problem directories with prompts, hidden tests, fixtures and reference solutions | NOT MIGRATED; they are inputs to the coding benchmark above |

## Slice 1 source-first decision

Decision (2026-09-22): **do not migrate** the benchmark, and **ADAPT** its one
transferable idea, that graders must be proven to reject.

Why not migrate: the platform's evaluation asks whether *the platform* routes,
authorizes and executes correctly. The source's benchmark asks whether a model
can write working Python. Both are useful and they are not the same suite; the
second belongs to whoever is choosing a model, needs a live endpoint, and
executes generated code in a subprocess that its own README is careful to note
is not a sandbox. Migrating it would put a live-model dependency and arbitrary
code execution into the repository's CI, which the Roadmap's exit criterion for
this phase rules out in as many words.

What is adopted instead is the discipline around it. The source's
`selftest.py` exists because the author found a problem no correct answer could
satisfy and a test that contradicted its own prompt, and because a grader that
accepts everything is indistinguishable from a working one until something
depends on it. The platform's harness has the same exposure in a sharper form:
`EvaluationCase.assertions` has been a tuple of free symbols since Phase 1 that
nothing interprets, so a misspelled assertion and a satisfied one look alike.
Slice 1 makes an unrecognized assertion fail its case, and gives every grader a
test that feeds it a deliberately wrong observation.

Intentional differences: the platform's graders read typed evidence rather than
running generated code; a failure names the assertion and its reason rather
than a pass/fail cell; and no scoreboard file is written, since CI failing is
the report for a deterministic suite.

Rollback removes the additions to `src/common/evaluation.py` and
`tests/test_evaluation.py`; `EvaluationCase` and the case files predate this
phase and stay.
