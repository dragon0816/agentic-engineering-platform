# K2 — Layered bilingual index (specification, for owner review)

Stage K2 of `docs/phases/KNOWLEDGE_PIPELINE_RELEASE.zh-TW.md` (sections 4.1, 4.2).
Goal: the Karpathy index works at this vault's scale, and English questions reach
Traditional Chinese pages, without two parallel language copies.

## Facts (2026-10-11)

- Published vault `rs-k`: 2,007 wiki pages (concepts 633, entities 800, sources 508,
  syntheses 66), raw + wiki about 27 MB.
- `index.md`: 2,910 entries, about 364,000 characters, every entry Chinese. That is far
  beyond the "about a hundred sources, hundreds of pages" scale at which Karpathy reads
  the whole index.
- Its Raw files come from the owner's earlier tooling, without platform provenance, so
  the pipeline cannot ingest them until they are adopted (`knowledge.migrate.adopt`
  records a ledger; Raw bytes stay untouched).
- Frequent tags: Market 1,442, Productions 299, 5G-NR 277, Knowledge 254, PCB 248,
  AI 209, data-center 171, satellite 108, UAV 108.

## Where the work happens

In a **sandbox of `rs-k`** (K1), never in the published vault. Promotion to the published
vault is the merge of stage K3 and needs the owner's approval.

## Design

### 1. Layered index

```
index.md                          top: the categories, each with a one-line bilingual description
index/market-<market>.md          5 markets of the domain matrix
index/product-<product-line>.md   4 product lines
index/technical.md                technical concepts not tied to one market or product
index/companies.md                companies, customers, competitors
index/sources-<year>.md           source summary pages by year
```

- Each sub-index line: `- [[Page]] — <繁中一行> / <English one line> (aliases: …)`.
- A page may appear in several sub-indexes (a market and a product line).
- **Category assignment:** existing tags and folder first (Market/Productions/Knowledge,
  satellite/UAV → aerospace-defense or automotive/UAV, AI/data-center → AI, …), then the
  Gateway model for pages the rules cannot place, in batches.
- `index.md` keeps working for old readers: the top level links to the sub-indexes, and the
  existing flat list moves to `index/all.md`, unchanged.

### 2. Bilingual aliases and summary

- Each page's frontmatter gains `aliases:` (English, Chinese, abbreviations, model numbers)
  and `summary:` (one line in each language), written by the Gateway model in batches of
  about 20 pages, so about 100 calls for 2,007 pages.
- Written through the vault write path, so each page is backed up first and only the
  frontmatter changes. A page whose body would change is refused.
- Retrieval reads `aliases` and `summary` (they are already in the page text it indexes).

### 3. Ingest and query follow the index

- **Ingest planning:** the relevance pass gets the top index plus the sub-indexes the model
  picks (two short prompts) instead of all 2,007 titles.
- **Query:** the multi-round search (`retrieval_rounds`) may open sub-indexes as search
  results, so a round can walk index → sub-index → page.

### 4. Legacy Raw adoption

- `knowledge.migrate.adopt` on the sandbox, so its existing Raw documents become ingestible.

## Measurement

1. Register the K2 sandbox as a candidate Knowledge version (the existing
   `knowledge_evolution` manifest and digests).
2. Run the 36 core questions with `reference_grade` against it (core-007), binding the
   candidate temporarily in host.json (backup first, restored after).
3. Accept K2 if answerable coverage is at least core-005's 0.40, with the 0.50 target, and
   median latency does not worsen by more than 20%.

## Slices

K2.1 adopt legacy Raw in a sandbox of rs-k → K2.2 category assignment and layered index
(rules + model) → K2.3 bilingual aliases and summary (frontmatter only) → K2.4 ingest and
query follow the index → K2.5 candidate registration and benchmark core-007.

## For the owner to decide

1. Category scheme above (5 markets, 4 product lines, technical, companies, sources by year):
   right, or other top-level groups?
2. About 100 company-model calls to write bilingual aliases and summaries for all pages:
   acceptable?
3. The sub-index lines and the new frontmatter fields are written in the sandbox only;
   promotion to the published vault waits for the K3 merge. Agreed?

## Outcome of K2.4-K2.5 (2026-10-11)

- Index-led query (e097aa0) measured worse (core-007) and was reverted; candidate data on
  the old code was also worse (core-008), because the layered `index.md` removed the
  flat list query navigation ranks and sub-index pages became citable.
- As adopted (owner, option C): query keeps ranking the previous flat list, read from
  `wiki/index/all.md` when `index.md` is layered; `wiki/index/` pages are never evidence.
  Offline on the 36 core questions, the live vault and the K2 sandbox return identical
  passages for all five retrieval paths (180 of 180), so no benchmark rerun was needed.
- The layered index serves ingest: one category call (at most 3), then the relevance call
  over those categories' pages with their bilingual lines; a flat index keeps the single
  relevance call. Whether the bilingual lines help query is still unmeasured.
