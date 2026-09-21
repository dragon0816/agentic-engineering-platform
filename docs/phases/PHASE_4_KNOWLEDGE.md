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
   reads it back; the two round-trip exactly, so a reader, a lint and a query
   all recover the same relationships from the file alone.
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
   hash-suffixed name, and `supersedes` names the old source), `unsupported`,
   `undecodable` or `empty`. Dry run is the default and reports exactly what an
   apply would write.
5. Extraction is behind an `Extractor` protocol keyed by suffix. Plain text and
   Markdown extractors ship with no new dependency; office formats and images
   are slices 3 and 4.
6. Raw files without provenance frontmatter (an existing vault's content) are
   ignored by the intake's index, never rewritten; adopting them is slice 9.
7. Tests cover the contracts and their refusals, the render/parse round trip
   with pages, slides and images, both extractors, every intake status in both
   modes, that Raw is never overwritten and Drop never written, and that
   identity follows content rather than path.

## Later slices (each needs its own requirements section before work starts)

- Slice 3 — Office extraction: PDF, PPTX and DOCX adapters behind the
  `Extractor` protocol as an optional dependency extra (license and maintenance
  recorded before adoption); text, tables as Markdown, image files saved beside
  Raw with their page/slide relationship preserved in the section metadata.
- Slice 4 — Image description through `ModelClient` with `vision=True`
  declared; the description attaches to the image's Raw section with the same
  provenance. No vision provider is named anywhere in knowledge code.
- Slice 5 — Ingest planning through `ModelClient`: the two-pass plan
  (relevance over an inventory, then writes), chunked condensation cached by
  content hash, structured output validated into a `WritePlan`. The model
  proposes; slice 1 validates and applies.
- Slice 6 — Static lint as a typed report: orphans, dangling links ranked by
  reference count, path-carrying links, missing frontmatter, provenance that no
  longer resolves, raw sources never ingested, open conflicts, manual edits.
  Mechanical link repair with backups. Judgement-based lint through
  `ModelClient` is a separate, optional pass.
- Slice 7 — Conflicts and decisions: an append-only `Decision` record injected
  into later planning, `⚠️` conflict markers found by reading, resolution that
  records why, and manual-edit detection by page hash.
- Slice 8 — Query with provenance: retrieval over Raw and Wiki returning an
  answer whose every citation names a `KnowledgeSource` (with page/slide where
  known). Deterministic lexical retrieval first; model synthesis, when used,
  may cite only what retrieval returned.
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
