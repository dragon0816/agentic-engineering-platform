# Filling empty card summaries in `market-intel`

Owner's rules (2026-11-05, through the orchestrator): through ingest, not a side door; AI summarises only from the card's own source text; where the source has nothing the field stays empty; fill only, never a filled value or `verified`/`evidence_grade`; sample data stays marked; evidence kept like any field; the owner reviews before anything applies.

Status: run `e3de934115f0` is staged on the real vault, nothing committed; it waits for the owner's review.

**Owner's decisions (2026-11-05, through the orchestrator):** `scope` is not filled. The 13 demo cards are not filled, and were later marked as samples by the owner's decision (commits of 2026-11-05, `擁有者決定標成範例資料-*.csv`), with one more, `大銀 直驅馬達伺服模組`. 99 samples of 760. The vault's 4 uncommitted changes stay untouched until the owner answers about them.

## Cause

`page_import.parse_page` reads only the frontmatter. `page_import.apply` keeps the whole page as a source (`add_source(text=page)`) and links it through `evidence`, so the body is **dropped from the card but still reachable**. All 481 sources read back. A page import uses no model by design, so **a future page import leaves summaries empty too**. AI ingest fills them (`extract.READING_RULES`): none of the 441 comes from an AI run.

The 441: 328 have a page named as the card, 12 a page named otherwise, 101 no page at all, only CSV or folder evidence.

## What the 441 hold

Counted after dropping dataview blocks, headings, placeholders, empty template labels, and any line repeated word for word on 4 or more cards. Usable is 40 or more characters, thin is 1 to 39.

| Type | Real usable | Real thin | Real none | Sample usable | Sample thin | Sample none | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ecosystem | 25 | 52 | 25 | 0 | 0 | 9 | 111 |
| Node | 15 | 14 | 20 | 0 | 0 | 2 | 51 |
| Account | 13 | 15 | 19 | 0 | 0 | 4 | 51 |
| TestSolution | 0 | 11 | 8 | 1 | 9 | 2 | 31 |
| Application | 0 | 5 | 14 | 0 | 3 | 7 | 29 |
| CustomerProduct | 15 | 0 | 9 | 0 | 0 | 4 | 28 |
| Technology | 8 | 10 | 1 | 1 | 3 | 2 | 25 |
| Concept | 13 | 1 | 9 | 0 | 0 | 1 | 24 |
| SupplyLink | 6 | 7 | 3 | 0 | 0 | 3 | 19 |
| Trend | 4 | 8 | 3 | 0 | 0 | 2 | 17 |
| RevenueFact | 0 | 6 | 4 | 0 | 0 | 5 | 15 |
| Opportunity | 0 | 2 | 5 | 1 | 0 | 4 | 12 |
| Competitor | 4 | 0 | 4 | 0 | 0 | 2 | 10 |
| Others (six sample types) | 0 | 0 | 0 | 1 | 0 | 17 | 18 |
| **Total** | **103** | **131** | **124** | **4** | **15** | **64** | **441** |

`usage` and `scope` are missing on 466 cards: these 441, plus 25 that have a sourced summary (Signal 23, VisitLog 2).

## Trial

30 cards (27 real, 3 sample; 21 usable, 9 thin), one call each, real model, read by hand against the source.

| Round | Summaries filled | Faithful | Faults |
|---|---:|---:|---|
| 1, plain rules, text without headings | 30 | no invented fact | 5 author notes as summaries, 6 off the point; never returned null |
| 2, strict rules, text without headings | 16 | 15 | **1 reversed the source** |
| 3, strict rules, text with headings | 20 | 20 | 5 thin; 1 quote not verbatim |

Round 2's fault was the input, not only the model: with the heading `## 尚待確認` and the line `不構成供貨關係` removed, `- 供貨關係` and `- 量產` read as facts. **Headings and evidence notes must reach the model.** Removing them is right for counting only. Round 3 returned null on that card and put `不構成供貨關係` in `scope`.

Round 3, `usage`: 5 filled, 4 fair, 1 only a label. `scope`: 12 filled, 8 fair, 4 true but not a scope (a market, a source region, a chain, a fact). No invented fact in any field.

Round 3 per call: 507 tokens in, 497 out, 7.6 s.

## Also found

- 13 cards were not marked sample though their text said fictional or demonstration, such as `Account-A` and `Cert-Lab-B` (first counted as 11). Marked since; `sample_not_marked` now reads a card's own text.
- Several page sources have garbled names, such as `暾餅絲` for `鴻海`: the card matches by frontmatter, the source's name is wrong.

## The run

`capabilities/bi_cards/reading_runs.py`. **A page import leaves `summary` and `usage` empty**, by design: it reads the frontmatter and uses no model. The page's body stays a source of the card. To fill them, start this run after an import:

```
POST /api/bi/runs {"dataset": "vault-<id>", "kind": "ingest", "reading": true, "skip": [<card id, key or name>]}
```

`"kind": "trial"` shows the same candidates and cannot be committed; `"card_ids"` limits it to some cards. It is one model call per card, two at a time; an identical request repeats its answer unless `"fresh": true`. Candidates, review, commit and retry are any AI run's: `GET /api/bi/runs/<id>`, `POST .../candidates/<id> {"dataset", "review": "accepted"}`, `POST .../commit`. Nothing is written before the commit.

Rules in code: a card is read only if it lacks a field in `reading_runs.FIELDS`, is not a sample, and has text of its own beyond headings, notes and lines repeated on 4 or more cards. Its text is a card page's body and its `body` field, with headings and evidence notes kept. A value goes when its quote is not word for word in that text, or when it is only the card's name. Each merges as `fill`; a value filled since then stays, and the new one is a proposal. `scope` is not filled, by the owner's decision; adding it to `FIELDS` is all it would take if that changes.

**The page opens this run** (`bi-review-table`, `docs/phases/BI_PAGE_SIMPLE.md` §8): step 2's 審核 lists the waiting runs in a combobox, labelled 補摘要, with no source chosen.

## Measured on a copy, through the run

The vault's local data copied to a temp plain dataset, so no shared folder is known to it. `plan`: 258 cards, of which 237 lack both fields and 21 (Signal) only `usage`; 85 samples and 123 with no text of their own are not read. 13 demo cards are not filled, by the owner's decision, leaving 245.

24 cards, the real model, then accepted and committed on the copy: 18 summaries and 3 usages, read by hand against the source, none with an invented fact, 6 cards left empty, no failure. 18 cards changed, only those fields added; no filled value, mark or name moved. 11,252 tokens in, 10,256 out, 69.5 s. For 245 cards that is about 220,000 tokens and 12 minutes. Yield 18 of 24, so about 180 summaries; a small sample.

## Garbled source names

15 sources, 14 cards, 68 evidence rows, such as `暾餅絲.md` for 鴻海, `銝…-KY.md` for 世芯-KY. **Not AEP's doing**: those 15 file names are garbled on disk in the folders given to the import (`aidc-bi-kb` 10, `BI_Vault_Example` 3, `Aerospace-BI-KB` 2): UTF-8 bytes once read as Big5, as an unpacking on Windows leaves them. AEP kept what it was given. The import now guards it: `page_import.garbled_name` tells such a name, and the source is kept under its card's name.

**Existing records, not repaired.** The names stand in the vault's units: 15 `source:`, 76 `evidence:`, 16 `field:` and 2 `proposal:` ops across 9 of 45 commit files; in 15 shared file names under `applications/*/sources`; in 14 pages of `cards/`; and in the published snapshots. Commits and files are never rewritten, so a repair is a new commit restating those units with the right name, through a small one-off tool that does not exist yet, then push, tag and publish; `cards/` rewrites 14 pages. The shared file names and the old snapshots would stay as they are, since a written file cannot change. On a copy first.

## The real run

Run `e3de934115f0` on `market-intel`, main `aba2c203`, 2026-11-05: 245 cards asked (224 for both fields, 21 Signal for `usage`), 13 demo cards skipped. 144 candidates: 140 summaries, 12 usages, all `fill`, all pending. 101 cards stayed empty, including every Signal card. 0 failed. 114,238 tokens in, 91,343 out, 684 s. The yield is 140 of 224, below the trial's 18 of 24. After a commit 301 of the 441 would still have no summary.

Stopped at staging: nothing committed. Cards, fields, evidence, relations, proposals, push state, published tag and the shared folder are the same before and after. It wrote the run to `staging.sqlite` and answers to the local answer cache.

20 candidates outside the trial, read against their sources: no invented fact, none reversed. 11 good, 8 faithful but thin or awkward, 1 a bare label that should be empty (`Keysight TSN 一致性方案`: 「競品方案。」). One summary drops a limit its text puts on the figure (`啟碁-2026前三季-公司`: 「不可與 2025 全年直接算同比」).
