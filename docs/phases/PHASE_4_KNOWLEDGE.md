# Phase 4 — Knowledge platform

Implementation scope derived from the approved Roadmap (Phase 4) and
Architecture ("Knowledge platform", rule 10: raw knowledge is immutable;
generated/curated knowledge preserves provenance). The pipeline to reach:

```text
Drop originals
  -> extraction (text, tables, images + vision description, page/slide/source metadata)
  -> Raw Markdown
  -> validation / conflict handling
  -> Wiki curation
  -> retrieval / query
```

The source is the vault tooling in `dragon0816/knowledge_management`
(`vault/ingest.py`, `conflicts.py`, `brain.py`, `snapshot.py`, `collect.py`),
pinned at `2f5e6d0431c5b6af8fbee05c6c0a5779e1a84bb9`. Source decisions are
recorded in `docs/PHASE_4_MIGRATION.md`. Exit criteria from the Roadmap:

- a PDF/PPT/DOCX sample corpus round-trips to Raw with traceable
  source/page/slide/image relationships;
- Wiki generation cannot mutate Raw;
- query answers can cite source provenance.

## Invariants carried from the source

These are the vault's safety properties. Each is preserved by contract and
enforced in code, never left to a prompt:

1. **Raw is immutable.** Nothing under `raw/` (and, new here, nothing under
   `drop/`) is ever written by the platform. Writes are confined to `wiki/`,
   `index.md`, `log.md` and `decisions.md`.
2. **Dry run is the default.** Nothing is written without an explicit apply,
   and the plan a dry run shows is exactly the plan an apply executes.
3. **Every overwrite is backed up** before it happens; a knowledge base has no
   tests to catch a silently dropped section.
4. **A plan that breaks the rules is rejected whole**, never partially applied.
5. **Provenance is a typed value, not a frontmatter convention.** The source's
   `source_path` becomes `KnowledgeSource` (identity, content hash, original
   reference, page/slide/parent), carried from Drop through Raw into Wiki.
6. **Conflict decisions are append-only and injected**: a rejected claim stays
   rejected across later sources, and a conflict is visible on the page a
   reader meets, not only in a log.
7. **What can be computed is computed**: static lint is exact and free; only
   judgement goes to a model, and every model call goes through
   `models.contracts.ModelClient` with declared `ModelRequirements` — no
   provider, gateway URL or credential appears in knowledge code.

## Requirements and acceptance (slice 1 — vault safety model)

1. `knowledge.vault` defines the vault layout as a contract: the immutable
   areas (`drop/`, `raw/`), the writable areas (`wiki/`, `index.md`, `log.md`,
   `decisions.md`) and the required files. A path outside the writable areas,
   or one that escapes the vault root, is refused with a closed code before
   anything is touched.
2. A `WritePlan` is a typed, serializable contract (pages with `create`/`update`
   and complete content, index entries per section, a log body, contradictions)
   — the model's output shape in later slices, and data here. Its validation is
   a pure function returning closed `PlanProblem` codes: no pages, no
   `wiki/sources/` page, a sources page without its `KnowledgeSource`
   provenance, a write outside `wiki/`, empty content, a wikilink carrying a
   path.
3. The two repairs the source makes are preserved exactly: a path inside a
   wikilink becomes the bare page name, and a slash-separated enumeration
   becomes separate links; anything ambiguous is left for validation to reject.
   A reported contradiction that no page carries is written onto an entity or
   concept page as a `⚠️` block.
4. `Vault.apply(plan, mode)` with `mode` in `dry_run` / `apply` returns a typed
   outcome listing every path that was (or would be) written, backed up or
   refused; `dry_run` writes nothing; `apply` backs up every overwritten page
   first, inserts index entries under their section with duplicate suppression
   and appends the log block. Rejection leaves the vault untouched.
5. Characterize the pinned source before implementing: excerpt tests pin
   `safe_write` refusals and backups, `validate` problems, both link repairs,
   the conflict marker, index insertion and log appending. Regression tests
   cover the adapted implementation for the same behaviors plus the new typed
   provenance and the closed codes. All existing tests, lint, strict types,
   packaging and CI must continue to pass.

## Requirements and acceptance (slice 2 — Drop → Raw with provenance)

1. `knowledge.raw` defines `RawSection` (kind `text` / `table` / `image`, the
   text, optional `page` and `slide`, an `image_ref` exactly for images) and
   `RawDocument` (a document-level `KnowledgeSource` whose `raw_ref` names the
   file, the extractor that produced it, the creation date, at least one
   section). `render` writes the Raw Markdown — provenance as frontmatter,
   every section behind a marker carrying its page/slide/image — and `parse`
   reads it back; the two round-trip exactly for any text (marker-like body
   lines are escaped, line endings are one), so a reader, a lint and a query
   all recover the same relationships from the file alone. A Raw written for
   a drifted original records what it `supersedes`.
2. Identity is the content: `source_for(bytes, original_ref)` derives the
   `sha256` and a `source_id` from the bytes, so the same original dropped
   under two names is one source and a changed original is a new one. The
   path-keyed dedup of the source tooling is not migrated.
3. `Vault.write_raw` is the only way the platform writes under `raw/`: it
   creates and never overwrites (`raw_exists`), so Raw stays immutable in the
   only sense a pipeline can honour — write once, never change. `drop/` is
   never written at all.
4. `DropIntake.intake(drop_rel, mode, today)` reads one original from `drop/`
   (refusing anything outside it) and returns a typed `IntakeOutcome`:
   `written` (a new Raw document, its path chosen from the drop path),
   `duplicate` (the content is already in Raw; nothing written, the existing
   `raw_ref` reported), `drifted` (the same `original_ref` is in Raw with other
   content; the old Raw is kept, the new one is written beside it under a
   hash-suffixed name, and `supersedes` names the latest old source),
   `unsupported`, `undecodable`, `empty` or `unrepresentable`. Every status is
   closed: nothing an original contains escapes as an exception. Dry run is
   the default and reports exactly what an apply would write, name included.
5. Extraction is behind an `Extractor` protocol keyed by suffix. Plain text and
   Markdown extractors ship with no new dependency; office formats and images
   are slices 3 and 4.
6. Raw files without provenance frontmatter (an existing vault's content) are
   ignored by the intake's index, never rewritten; adopting them is slice 9.
7. Tests cover the contracts and their refusals, the render/parse round trip
   with pages, slides and images, both extractors, every intake status in both
   modes, that Raw is never overwritten and Drop never written, and that
   identity follows content rather than path.

## Requirements and acceptance (slice 3 — office extraction)

1. `knowledge.office` provides `PdfExtractor`, `PptxExtractor` and
   `DocxExtractor` behind the `Extractor` protocol. The libraries are the
   optional extra `office` (`pypdf`, `python-pptx`, `python-docx`; licenses
   and maintenance recorded in `docs/PHASE_4_MIGRATION.md` before adoption);
   every import is lazy, so the platform without the extra still loads and
   simply has no extractor for those suffixes.
2. Relationships are kept in the sections: PDF text and images per page;
   PPTX text frames, tables and pictures per slide in shape order; DOCX
   paragraphs (headings as Markdown `#`), tables and inline pictures in body
   order, with no page (Word has none). Tables are GitHub-style Markdown with
   cells flattened and pipes escaped.
3. An extractor never writes. It hands image bytes to an `AssetSink`; the
   intake stages them, names each by its content under the Raw document's own
   `<stem>/assets/` directory, lists them in `written`, and writes them only
   on apply through `Vault.write_raw_bytes` — write-once like Raw, with the
   same bytes at the same name a no-op and different bytes refused.
4. A corrupt or unreadable original is the closed status `undecodable`,
   whatever the library raised; an encrypted PDF that an empty password does
   not open is the same.
5. Tests generate a PDF (with a real xref and an embedded image), a PPTX and a
   DOCX in the test itself, and show the corpus round-tripping to Raw with
   page/slide/image relationships intact, a repeated picture stored once, dry
   run and apply agreeing, and Drop untouched. CI installs the extra.

## Requirements and acceptance (slice 4 — image description)

1. `knowledge.describe.ImageDescriber(model, alias=…)` asks a `ModelClient`
   to describe an image with `ModelRequirements(vision=True)` declared and the
   image carried inline as a `data:` URI in a provider-neutral `ModelMessage`.
   No provider, endpoint or credential appears in knowledge code; the alias is
   host configuration.
2. Raw is write-once, so description happens at intake: `DropIntake` takes an
   optional describer and, on apply, describes every image section that has
   no text yet before the Raw file is written. The description becomes the
   image section's text, marked `described=<alias>` in the section marker so
   a model's words are never mistaken for the source's.
3. Every failure is a closed `ImageDescription` status — `described`,
   `too_large`, `unsupported_type`, `model_failed` (with the model's
   `Failure`; an adapter that raises is one too), `empty_answer`,
   `missing_bytes` — reported on the `IntakeOutcome`. A model failure is the
   host's environment, not the document's content, so it stops the write:
   the intake status is `description_failed`, nothing is written, and a
   later apply can try again instead of baking the gap into write-once Raw.
   Every other status writes the document without that image's text.
4. A picture is described once: memoised by content for the describer's
   lifetime, and a drifted original reuses the descriptions its superseded
   Raw already holds for identical pictures. A dry run spends no tokens: it
   reports how many distinct images still need a description
   (`images_to_describe`) — the one place a dry run cannot show the exact
   text an apply writes, stated as such.
5. Tests use a fake vision model: the request shape, every status including
   an adapter that raises, memoisation and trace ids, the marker in the Raw
   file, the intake in both modes, a model failure stopping the write and a
   retry succeeding, reuse across drift, and an intake without a describer
   asking nothing.

## Requirements and acceptance (slice 5 — ingest planning)

1. `knowledge.planning.IngestPlanner(model, vault, alias=…)` plans one Raw
   document's ingest in two passes through `ModelClient` with
   `structured_output` declared: relevance (which existing wiki pages matter,
   from an inventory of paths and titles, filtered to pages that exist and
   capped at 8), then the writes (with those pages in full, the current
   `index.md`, the settled decisions and the source text). The conventions
   the model follows are a platform default a host may replace; no vault
   schema file is read.
2. A source longer than a threshold is condensed chunk by chunk first, and
   the result is cached under the vault (`.ingest-cache/<key>.md`, the key a
   hash of everything the condensed text depends on: the rendered source,
   the chunking, the prompt and the model alias) so a plan rejected
   downstream never costs the condensation twice and a changed input never
   reads a stale one; a failure or an empty part leaves no cache.
3. The model's answer is data: structured output when the adapter provides
   it, else JSON extracted from fences or prose. It becomes a `WritePlan`
   whose sources page is repaired to carry the source's provenance lines
   (deterministic, so omitted ones are added rather than rejected) and whose
   pages are `create` or `update` by what the vault holds, never by the
   model's guess; a contradiction that only says "none" is not one. The plan
   is validated by a vault dry run. The planner never writes wiki, index, log,
   raw or drop; the caller applies the plan through `Vault.apply`.
4. Every outcome is a closed `PlanningOutcome` status — `planned`, `invalid`
   (with the plan and its problems), `model_failed` (with the failure, an
   adapter that raises included), `unparseable` — plus what pass 1 chose,
   whether the source was condensed and whether the cache answered.
5. Tests use a fake model: the source text the model sees (images in place),
   JSON extraction, provenance repair, both passes and their prompts, a plan
   the vault applies end to end, prose answers, invalid and malformed plans,
   failures on either pass, condensation with chunk count and cache reuse
   across planners, and the cache's confinement.

## Requirements and acceptance (slice 6 — static lint)

1. `knowledge.lint.scan(vault)` computes, by reading alone, a typed
   `LintReport`: page and type counts; orphans (no inbound link, entry
   points excepted); dangling links ranked by how often the missing page is
   referenced; links that carry a path or a `.md` naming a wiki page;
   pages without frontmatter; a legacy `source_path:` that no longer
   resolves; a `source_id:` that names no Raw in the index; Raw sources no
   `wiki/sources/` page carries (a superseded Raw handed its evidence on and
   is not pending); open `⚠️` conflicts with their line; pages that cannot be
   read. Nothing in it calls a model, and nothing a page contains aborts the
   report — an empty link, a bare marker, a malformed identifier or a
   non-UTF-8 page is a finding, never an exception. Frontmatter is read
   leniently (Obsidian lists, blanks and comments are not fields, not
   errors); a judgement pass may take the report as context later.
2. The pinned `brain.py` scan is characterized first, with the pinned ingest
   and conflicts excerpts supplying what it imported; the adapted scan
   reproduces its rules, including that only `.md` is stripped from a page
   name and that a trailing `.md` is wrong only when it names a wiki page.
3. `fix_links(vault, report, stamp=)` is the one mechanical repair: the
   flagged path-carrying links become bare page names, case-corrected to an
   existing page, aliases and anchors kept, untouched otherwise; every
   rewritten page goes through `Vault.write` with a backup and one line
   ending on every platform, only the flagged pages are read, and nothing
   under `raw/` or `drop/` is ever written.
4. Manual-edit detection and decision bookkeeping are slice 7; the report
   gains them there.
5. Tests: characterization of the excerpt and regression over the adapted
   report as typed values, the repair with aliases, anchors and backups, and
   a link that leaves the vault not counting as a page.

## Requirements and acceptance (slice 7 — conflicts and decisions)

1. `knowledge.conflicts.Decision` (topic, keep, reject, reason, pages — one of
   the first three required) is appended to `decisions.md` by
   `append_decision`, the header written once; `decisions_text(vault)` is the
   block the planner injects, `(no settled decisions)` when the file is
   absent or only the header. The file is append-only: nothing rewrites it.
2. `open_conflicts(vault)` finds every `⚠️` line by reading, through the same
   `find_conflicts` the lint report uses. `clear_conflicts(vault, page,
   lines, stamp=)` removes the marker lines of one page in one write — one
   backup of the original however many markers — and only lines that match
   the marker rule: a heading or prose that mentions the symbol, or a line
   that moved, is left alone. A page keeps its own line endings.
3. `resolve(vault, decision, clear=, today=, stamp=)` checks the clear list,
   records the decision, then clears per page, reporting what was cleared
   and what was missed. A marker is never cleared without its reason on
   record, and nothing can fail half-way.
4. Manual-edit detection is computed into the lint report from the pages it
   already read: `record_state` stores every page's hash; `note_written`
   refreshes only the pages the tool just wrote, so its writes are not
   reported as a person's while a later change to the same page still is;
   `manual_edits` reports edited, added and removed pages since. A corrupt,
   odd or absent state is a first run, not a failure.
5. Tests over the pinned conflicts excerpt already exist (slice 1); regression
   tests cover the record, injection, finding and clearing, resolution with a
   moved marker, and manual edits across two recorded states.

## Requirements and acceptance (slice 8 — query with provenance)

1. `knowledge.query.retrieve(vault, question, k=)` ranks passages — every
   Raw section with text and every Wiki paragraph — deterministically
   (BM25; ties by corpus order), with character bigrams for CJK text so a
   question in Chinese matches inside a run without a segmenter.
2. Every `Passage` carries a `Citation`: a Raw passage names its
   `KnowledgeSource`, file and section, with the page or slide the
   extractor knew; a Wiki passage names its page and, when the page carries
   `source_id`, the source behind it. This is the Roadmap's "query answers
   can cite source provenance".
3. `QueryEngine(vault, model=, alias=).ask(question, k=)` returns an `Answer`
   with a closed status: `retrieved` (passages only, no model), `answered`
   (a synthesized text whose every `[n]` citation names a retrieved
   passage), `uncited` (the model's text was refused for citing nothing or
   something it was not given), `model_failed` (an adapter that raises
   included) or `no_match`. Synthesis goes through `ModelClient`; no
   provider is named.
4. Tests: tokenization with CJK bigrams, ranking that is stable across calls,
   citations resolving to pages and slides, wiki passages citing the source
   behind a sources page, image sections without text not being passages,
   and synthesis accepted only when every citation is real.

## Later slices (each needs its own requirements section before work starts)

- Slice 9 — Migration adapter for an existing Obsidian vault: adopt existing
  Raw and Wiki content under typed provenance, report path-versus-hash drift,
  snapshot before adoption and restore on demand. Existing knowledge is not a
  greenfield corpus and `raw/` is never rewritten.

## Out of scope for Phase 4

The LiteLLM/company gateway and its credential handling (Phase 5), the coding
agent and benchmark suite (Phase 6), any Obsidian plugin, Google Drive
synchronization, a web UI, and automatic ingestion on a schedule (n8n stays an
optional trigger through the existing Gateway contract). The vault's runtime
`CLAUDE.md` schema is not read by the platform: the conventions it encodes
become typed contracts here, and a host that keeps a schema file for its own
maintainers does so outside the platform.
