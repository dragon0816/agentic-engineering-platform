# BI step 3 and the skill AI on the harness

Status: T1 done (2026-10-31); T2 next, then T3. Owner decisions: `docs/DECISIONS.md` 2026-10-31 "BI step 3 and the
skill AI: owner decisions". Builds on knowledge repositories (`KNOWLEDGE_REPO.md`, BI vault type R2/R3) and
the three-step BI page (`docs/DECISIONS.md` 2026-10-31 "BI 「建立與匯入」 as three steps").

## 1. Why

The page's step 3 (測試與 Push) must show, before a push, whether the knowledge base built from the working
copy answers better or worse than the published one, the way users will use it. The skill AI must be able to
see that effect itself (owner: otherwise nobody can confirm its rule matches the built knowledge base and
what users get). Experts also want charts and tables drawn by SQL or a script, made in an AI conversation.

## 2. Slices (in the owner's order)

| Slice | What | Done when |
|---|---|---|
| T1 | Benchmarks of a BI vault: question sets (chat answers) and extraction cases (cards), kept in the vault, run on the working and the published version, shown in step 3, checked on push | contract, tests, page, browser test |
| T2 | The skill AI on the Agent harness with BI tools (read a source, trial run in staging, compare, run the benchmarks, ask like a user) | harness seam, tools, panel, tests |
| T3 | Analyses by AI conversation: read-only SQL and constrained Python scripts, charts and tables saved in the vault and shown in the Dashboard | runner, conversation, page, tests |

## 3. T1: benchmarks of a BI vault

### 3.1 Kept in the vault (committed and pushed like cards and skills)

Two new unit kinds (BI type `unit_problem`):

- `check:question:<set>/<slug>` → `{"question": str, "must": [str], "must_not": [str]}`. Same meaning as a
  wiki question file (`knowledge/questions.py`): graded by case-insensitive terms; a question with no terms is
  listed as ungraded and not scored.
- `check:extract:<slug>` → `{"note": str, "folder": str | null, "expected": <aep.bi.benchmark.expected/v1>}`:
  a short source text, the vault folder it belongs to (picks the extract skill) and what extraction must find
  (`capabilities/bi_cards/benchmark.py`).

They never become rows of `bi.sqlite` (materialize ignores them), so they do not show as cards and the Agent
never reads them.

### 3.2 Running

`host_runtime/bi_bench.py`, started from the page as a background task; one run tests both kinds:

- **Questions**: each question is asked twice through the Agent harness (`Gateway.converse`, as a Host sub-run:
  no memory, no session, only the `bi__query` tool), once with `bi__query` reading the working database
  (`<workspace>/bi/vaults/<id>/bi.sqlite`, read-only view) and once reading the published one
  (`published/bi.sqlite`, what the Agent reads today). A turn-scoped Host tool replaces `bi__query` for that
  turn only (`agent.gateway.turn_host_tools`); the live chat is not affected. Graded as the wiki benchmark;
  a regression is a question that passes on published and fails on working.
- **Extraction cases**: each case's note is added as a source of the vault dataset, a trial AI run reads it
  with the working skills of its folder (the real ingest path), and the candidates are scored by
  `benchmark.score`. Only the working side is run (the published skills already produced the published cards).

The report (`aep.bi.bench_report/v1`) is saved after every question in
`<workspace>/bi/vaults/<id>/benchmarks/<run>.json` and records the digest of the working units it tested.

### 3.3 Push check

On push the BI type's check finds the newest finished run for exactly the units being pushed: question
regressions block the push (as for a wiki repository); without such a run the push goes ahead with the note
「沒有測過」. A run is never started by a push (it asks the model for minutes).

### 3.4 Page (step 3)

「題目與擷取測試」 in step 3 above 「版本」: the question sets and cases (add, edit, delete: staged like any
change), 「跑測試」, and the latest report: per question working vs published answer and grade, regressions
first; per case score and failed checks.

## 4. T2: the skill AI on the harness (outline)

The skill session becomes a Gateway sub-run with BI Host tools: `bi_skill__read_source`, `bi_skill__try`
(trial run in staging with a draft rule, never staged in the vault), `bi_skill__compare`,
`bi_skill__benchmark` (T1 run on the draft), `bi__query` on the trial result, and `bi_skill__suggest` (the
final suggestion, checked as today). Applying, committing and pushing stay the person's.

## 5. T3: analyses (outline)

An analysis conversation on the same harness with `bi_analysis__sql` (read-only connection on a copy, row and
time limits) and `bi_analysis__python` (own process with `-I`, scratch folder, time and output limits, no
network, audit hook refusing sockets, subprocesses and writes outside the scratch folder; the script is shown
with its output). A saved analysis (`analysis:<slug>` unit: question, SQL or script, chart spec) is committed
and pushed and shown in the Dashboard, rerun on the current data.
