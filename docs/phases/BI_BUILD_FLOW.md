# The BI knowledge-base build flow, end to end

Status: B1–B8 done (2026-11-02); §12 has the commits, §13 the live acceptance. Owner goal 2026-11-02: the BI build flow works end to
end in Agent Web, with an AI session in each step that calls for one:

```text
data import + convert ─▶ modify schema and skills (AI) + ingest ─▶ add benchmark and dashboard (AI) ─▶ testing
```

Decision: `docs/DECISIONS.md` 2026-11-02 "The BI build flow". Builds on `BI_INGEST.md` §9 (Sessions A and B),
`BI_VAULT.md`, `BI_TEST_AND_TOOLS.md` (T1–T3), `BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` (K1, K2).

## 1. What was missing (audit at `a7629341`, each one checked in the code)

| # | Gap | Found |
|---|---|---|
| 1 | Session A has no tools and cannot try its draft | `schema_session.session_turn` calls `sessions.ask` (one model call); the route passes no asker |
| 2 | `bi_skill__benchmark` of the T2 design was never built | `bi_skill_agent.py` has `test_cases` (extraction only); no tool sees the effect on what users get |
| 3 | Benchmark questions are typed by hand | only `bi-b-bq-form`; no session |
| 4 | No browser test of ingest into a vault, or of the K1/K2 page parts | `test_bi_vault_ui` has no ingest step; K1/K2 only reach the script parse test |
| 5 | No browser test of the whole flow | none |
| 6 | "Convert" means two things on the page and in the docs | §2 |
| 7 | **New, found here:** converting a dataset to a vault leaves its sources behind | `vault.convert` moves `bi.sqlite` units only and never touches `Staging`, so the vault's `staging.sqlite` starts empty: after upload → Markdown → convert, steps 2 and 3 have no source to read and the person must upload again |

## 2. "Convert" means two things

1. **File → Markdown** (`BI_VAULT.md` §5): each source becomes kept, editable Markdown. Automatic when a
   source is added; it writes no card.
2. **Dataset → vault** (`vault.convert`): a local dataset becomes a shared knowledge base as one `import`
   commit; the dataset stays as it was.

The page keeps 轉換 for neither alone: step 1 is titled 「資料輸入與轉檔」, file conversion is called 轉成
Markdown and the dataset action 把這個資料集轉成 vault, with a line saying that it writes a commit, takes the
sources along on this PC and leaves the dataset as it was.

## 3. Slices

| Task | What | Done when |
|---|---|---|
| B1 | This design, the decision | committed |
| B2 | Convert takes the sources along (§4); the page's wording (§2) | tests, including the Markdown revisions |
| B3 | Session A on the Agent harness with read-only tools (§5) | tools, panel, tests; the one-call path stays where no harness exists |
| B4 | `bi_skill__benchmark` (§6) | tool, tests |
| B5 | AI help for benchmark questions (§7) | session kind, tools, apply, panel, tests |
| B6 | Browser tests: ingest into a vault; K1 and K2 page parts | tests pass in headless Chromium |
| B7 | One browser test of the whole flow with scripted models on a temp vault (§8) | test passes |
| B8 | Contracts, TASKS, HANDOFF; live acceptance with real models (§9) | evidence recorded |

## 4. B2: convert takes the sources along

`vault.convert` copies the dataset's sources into the new vault's `staging.sqlite` with their stored files,
Markdown revisions and classification; runs, candidates and sessions stay with the dataset (they refer to its
cards and drafts). This stays on this PC: nothing goes to the shared folder, so it does not touch the open R6
question (§10). A copy, not a move: the dataset is left as it was.

## 5. B3: Session A on the harness

As T2 and T3: `host_runtime/bi_schema_agent.py` gives `schema_session.session_turn` an `asker` (a Host sub-run of
`Gateway.converse`, no memory, no session) with tools for that turn only. `BenchRuntime.schema_asker_for`
supplies it in Agent Web; without one the turn stays one model call (contract unchanged). Every tool only reads
or tries; nothing is written to the draft, the cards or the vault.

| Tool | Does |
|---|---|
| `bi_schema__sources`, `bi_schema__read_source` | list and read the dataset's sources (classification checked, fenced as data) |
| `bi_schema__cards` | counts by type, and sample cards of one type with their field values |
| `bi_schema__try` | applies `changes` to a copy of the draft: diff, validation errors, the impact on the existing cards (`schema_versions.impact`), sample cards checked against the result; with `source_id`, also a trial run with that schema (candidates only) |
| `bi__query` | the cards the way the Agent reads them, on the working copy |
| `bi_schema__suggest` | the final suggestion, checked as today; problems go back to the model |

A trial of an unsaved draft keeps the tried document in the run's layout (`trial_schema`), and
`runs.registry_for` prefers it; the run's ref stays `draft:<id>@rev<base>`, and a draft run can never be
committed, as today. `aep.bi.schema_suggestion/v1` gains the verdict `answer`: the person only asked a question;
its changes must be empty. 「套用到草稿」, 「用樣本試跑」 and publishing stay the person's.

## 6. B4: `bi_skill__benchmark`

T2's owner reason: the skill AI must see the effect of its rule on the knowledge base that is built and on what
users get. A draft skill changes only what is extracted next, so the tool builds that effect:

- input: `changes` (the draft; omitted: the skill as it is), `source_ids` (up to 3 sources to read with it);
- each source gets a trial run with the draft, and its clean candidates are written to a **scratch copy** of the
  working `bi.sqlite` under a temporary folder, which never becomes a commit and is deleted after the call;
- each graded question of the vault (first 10) is asked the T1 way (`bi_bench.agent_ask`'s turn) on the working
  copy and on the scratch copy, and graded; `regressions` are questions passing before and failing after;
- the extraction cases are scored with the draft, as `bi_skill__test_cases`.

The result goes back to the model only. It is not a T1 report: it is not saved in `benchmarks/` and never
satisfies the push check, which needs a run on exactly the units being pushed. Without `source_ids` or questions
it says what it could not test.

## 7. B5: AI help for benchmark questions

A session of the new kind `questions` (target `questions:<set>`) in the vault's `staging.sqlite`, on the harness
(`host_runtime/bi_questions_agent.py`, `BenchRuntime.questions_asker_for`), as analyses: no harness, no turn.

| Tool | Does |
|---|---|
| `bi__query` | the working cards, as the Agent reads them |
| `bi_questions__analyses` | the vault's saved analyses: title, question, and the first rows on the working data |
| `bi_questions__try` | asks one draft question the T1 way on working and published and grades it (saves nothing) |
| `bi_questions__propose` | the final proposal: `reply`, `questions: [{question, must, must_not}]`, `reasons` |

Code checks a proposal (`aep.bi.questions_suggestion/v1`) and sends problems back to the model: at most 20
questions, each passing `vault_checks.checked_question`, each graded (some `must` or `must_not`), not a repeat of a
saved question, and **every `must` term actually found** in the working cards or the saved analyses' results (a
term that nothing supports would be a question nothing can pass). The page lists the questions with a tick each;
「加入測試題」 stages the ticked ones as `check:question:<set>/<slug>` units. They reach others by commit and push,
like every unit. Nothing is staged before that click.

A vault with the default pack has 31 Python analyses at about 2 s each, read once for the model and once for the
check. `saved_results` runs four at a time and keeps the last results until the analyses or the data change.

## 8. B7: the whole flow in one browser test

`tests/test_bi_build_flow_ui.py`, real Agent Web server and routes, temp workspace, a temp folder as the shared
folder, scripted Agent and extractor models: upload → Markdown → convert to vault → Session A suggestion, applied
to a draft, published and the vault moved → Session B suggestion applied → ingest trial → ingest → review → write
→ AI benchmark questions applied → AI dashboard (K1) applied → bench run working vs published → commit → push →
publish, ending with what the Agent reads.

## 9. B8: live acceptance

With real models (owner decision 2026-11-02), through the existing model configuration, only in a temp workspace
under `%TEMP%` with its own Agent Web on a free loopback port. Never port 53583, the owner's workspace or
OneDrive/SharePoint folders. Evidence goes into `docs/TASKS.md`; no secret is printed, copied or committed.

## 10. Open, not decided here

- **R6, sources on one PC.** A vault's sources stay on the PC that added them; they are not shared through the
  folder. This is an open owner decision for R6 (rebuilding `market-bi`). B2 keeps to it.

## 11. Two page bugs the browser tests found

- Opening a vault with no benchmark run yet raised 「讀不到測試：Cannot read properties of null」, because
  `bi.benchWatch` and the missing run id were both undefined. Fixed in B6.
- Step 3's 「還沒給大家的改動」 was not read again on entering the step, so after an ingest it still said there was
  nothing to push. Entering step 3 now reads the vault's status. Fixed in B6.
- A bench report could stay on 「還沒有跑過測試」 after a run finished: the page's read right after starting a run can
  come before the run's first report, and that read stopped the polling; an older read arriving late could also cancel
  it. The page now keeps reading until it sees the run it started, and only the newest read counts.
- A bench run could die for good: Windows refuses to replace a report the page's polling has open, the run's thread
  ended, the report stayed `running` and every later run was refused as `bench_running`. A T1 bug. `_save` now waits it
  out (`schema_versions.replace`).
- The question AI read all 31 Python analyses of the default pack twice per turn, about 100 s. See §7.

## 12. Status

| Task | Commit | Test |
|---|---|---|
| B1 | `bc35f84c` | |
| B2 | `ac900646` | `test_bi_vault.py::test_converting_a_dataset_takes_its_sources_along` |
| B3 | `f0a71cf6` | `test_bi_schema_agent.py` |
| B4 | `c84ca577` | `test_bi_skill_benchmark.py` |
| B5 | `97cf00fe`, `5055018f` | `test_bi_questions_session.py` |
| B6 | `a0ba92f9` | `test_bi_vault_steps_ui.py` |
| B7 | `4439cb39` | `test_bi_build_flow_ui.py` |
| B8 | live acceptance: §13 | |

A dataset still needs its `bi.sqlite` before it can be converted (`vault.convert` refuses `dataset_unknown`
otherwise, and the page hides the button): someone starting from nothing creates the dataset or the vault first.

## 13. Live acceptance with the real model (2026-11-02)

Gateway `127.0.0.1:4000`, alias `company`, model `gpt-5.5`, key by name only (`LITELLM_MASTER_KEY`), each run in its own
`%TEMP%\bi-live-*` workspace with its own Agent Web on a free loopback port, in headless Chromium, on invented data.
About 115 model calls in all, every run under a stated cap.

**One deviation.** BI's model normally comes from the Knowledge handler, which exists only when a wiki Knowledge asset is
bound. These hosts had none, so the runs gave BI the same real client and alias directly (see "BI-only host" in
`HANDOFF.md`).

| Run | Cap, actual | Result |
|---|---|---|
| 1, a note labelled 虛構範例 | 120, 58 | Sessions, questions, dashboard, bench, push and publish ran; ingest made 0 cards |
| Six extraction calls on run 1's workspace | no counter, 6 | Why: with the skills the model refused to make fictional cards, without them 4 candidates each time |
| 2, the same note unlabelled | 80, 42 | Every step passed; ingest wrote 1 of 4 accepted cards |
| 3, ingest to publish | 12, 4 | Ingest wrote 4 of 4; stopped at the commit, a fault of this reduced script |
| 4, the same, entering step 3 | 12, 5 | Passed: 4 cards in published `v1` |

Run 2, step by step:

- Session A: sources, cards, read, `bi_schema__try` with a trial, suggest; `budget_band` applied, published, the vault
  moved to `@3.1.0`. The field was filled from the source on ingest (`中等`).
- Session B: trial, cases and `bi_skill__benchmark`; the model reported 「哪家客戶在評估 TSN？」 going from failing to
  passing with no regression. Applied as a new revision.
- AI questions: two, both with supported `must` terms, added after the tick.
- Dashboard: `bi_analysis__propose_dashboard`, applied.
- Bench: working 2/3, published 0/3, no regression. The third question failed on a `must_not` the model itself chose.
- Commit, push, tag, publish: the push note named the run for exactly those units; `v1` read back.

**What the scripted models had hidden, all found here:**

- The model's reason for making nothing was dropped, so an empty run explained nothing, even to Session B. It now
  reaches the page and the AI sessions.
- The accept-all race wrote only the cards accepted before moving on (run 2). 「下一步」 now waits.
- The question AI put a true term in `must_not`. Its role now forbids that; not re-tested live.

Not covered live: the phone layout, Atlas import (K2), and BI's model through the Knowledge handler itself.
