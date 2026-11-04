# Filling empty card summaries in `market-intel`

Owner's rules (2026-11-05, through the orchestrator): through ingest, not a side door; AI summarises only from the card's own source text; where the source has nothing the field stays empty; fill only, never a filled value or `verified`/`evidence_grade`; sample data stays marked; evidence kept like any field; the owner reviews before anything applies.

Status: measured on copies, nothing written to the vault. No full run, no product code yet.

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

## Full run, if approved

234 real cards with text, not sample cards: about 235,000 tokens, about 15 minutes at 2 calls at a time. At the trial's 20 of 27 this gives about 170 summaries, leaving about 270 empty. A sample of 30 gives a wide margin.

## Also found

- 11 cards are not marked sample though their text says fictional or demonstration, such as `Account-A` and `Cert-Lab-B`; `sample_not_marked` only reads the `SAMPLE-` name.
- Several page sources have garbled names, such as `暾餅絲` for `鴻海`: the card matches by frontmatter, the source's name is wrong.
