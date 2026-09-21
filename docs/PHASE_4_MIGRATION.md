# Phase 4 source inspection and disposition

Source: `dragon0816/knowledge_management`, commit
`2f5e6d0431c5b6af8fbee05c6c0a5779e1a84bb9` (`main` at inspection, 2026-09-21,
read-only shallow clone). The repository mixes four concerns — a LiteLLM
gateway, a coding agent, a benchmark suite and the Obsidian vault tooling —
and only the vault tooling belongs to Phase 4. `docs/SOURCE_REPOSITORIES.md`
already records the strategy: preserve the safety invariants and decompose by
platform boundary; address the known gaps (images ignored, no query) explicitly.

## Slice 1 source-first decision

Inspected `vault/ingest.py` (764 lines), `vault/conflicts.py` (177),
`vault/brain.py` (536), `vault/snapshot.py` (137) and `vault/collect.py` (266),
plus `vault/README.md` and the vault-related entries of the source's
`docs/DECISIONS.md`.

Decision: **ADAPT** the vault safety model into typed contracts and a pure
validation/apply core in `knowledge.vault`, characterized by pinned excerpts
(`tests/fixtures/source_vault_ingest.txt`, `source_vault_conflicts.txt`).
The source's `Gateway` client, prompts, condensation, CLI and run loop are not
migrated in this slice; a `WritePlan` is data here, and the model that will
propose one arrives in slice 5 behind `ModelClient`. The source repository is
unchanged. Rollback removes `knowledge/vault.py`, its tests, fixtures and docs;
nothing else imports them.

Why not WRAP: the safety core is entangled with `print`, `SystemExit`, module
globals (`VAULT_DEFAULT`, `WRITE_ALLOWED`) and a plan that is an untyped dict.
Wrapping would keep an untyped boundary at exactly the place the platform's
contracts must hold (rule 10: provenance preserved). Why not REWRITE: the
behaviors are proven on a real 190-page vault and each carries a recorded
reason; they are pinned and reproduced, not reinvented.

| Source | Observed behavior | Decision and preserved boundary |
| --- | --- | --- |
| `ingest.py` `Vault.safe_write` | refuses any path not under `wiki/`, `index.md`, `log.md`; refuses a path that escapes the vault root; backs up an existing target to `.ingest-backup/<stamp>/<rel>` before overwriting | ADAPT into a typed layout with closed refusal codes; `drop/` and `decisions.md` join the layout (`decisions.md` writable, `drop/` immutable); backup before overwrite preserved |
| `ingest.py` `validate` | rejects a plan with no pages, no `wiki/sources/` page, a sources page missing `source_path: <rel>`, a write outside `wiki/`, empty content, or a wikilink carrying a path; a plan is rejected whole | ADAPT as `check_plan` returning `PlanProblem` codes; `source_path` text becomes a typed `KnowledgeSource` in the plan; whole-plan rejection preserved |
| `ingest.py` `repair_wikilinks` | `[[wiki/x/Foo]]`/`[[raw/x/Foo]]`/`[[Foo.md]]` → `[[Foo]]`; `[[A / B / C]]` → `[[A]] / [[B]] / [[C]]`; anything else with a slash left for rejection | ADAPT unchanged; repairs reported in the outcome |
| `ingest.py` `ensure_conflicts_visible` | if contradictions are reported and no page carries `⚠️`, append a `## ⚠️ 待裁決的衝突` block to the first entity/concept page (else the first page) | ADAPT unchanged, including the preference order |
| `ingest.py` `update_index` | insert each entry under the matching `## Section` heading (case-insensitive substring), before trailing blank lines, skipping exact duplicates; create the section at the end if absent | ADAPT unchanged |
| `ingest.py` `append_log` | append `## [date] ingest \| <source stem>` plus body and `- ⚠️` lines | ADAPT; the date is injected, not read from the clock, so tests are deterministic |
| `ingest.py` `ingested_paths`/`pending` | dedup key is the `source_path` recorded in `wiki/sources/` frontmatter — a moved source looks un-ingested, a changed one looks done | NOT MIGRATED here; slice 2 replaces path identity with content-hash provenance and reports drift (the source's own README names this as its sharp edge) |
| `ingest.py` `Gateway`, prompts, `condense`, `plan_ingest` | OpenAI-compatible HTTP client with retries, Traditional-Chinese maintainer prompts, chunked condensation cached by content hash, two-pass planning | NOT MIGRATED in this slice; slice 5 through `ModelClient`, with condensation cache and two passes preserved as behaviors |
| `conflicts.py` | append-only `decisions.md`, `⚠️` markers found by regex over `wiki/`, `clear_conflict` by line, page hashes in `.brain-state.json`, manual-edit detection excluding tool-written pages | Pinned now; ADAPT in slice 7 |
| `brain.py` static `scan` | orphans (entry points excluded), dangling links by count, path-carrying links (with the `[[CLAUDE.md]]` exception), missing frontmatter, unresolved `source_path`, pending sources; `page_name` strips only `.md` | Inspected; pin and ADAPT in slice 6 |
| `snapshot.py` | copy `wiki/`, `index.md`, `log.md`, `decisions.md`, `.brain-state.json` to `.brain-snapshot/<stamp>`; restore snapshots the current state first | ADAPTED in slice 9 as the migration adapter's safety net |
| `collect.py` | copy project READMEs and `docs/**/*.md` into `raw/Programming/<project>/`, hash-compare duplicate checkouts, exclude `HANDOFF.md` by name | NOT MIGRATED; a Drop intake (slice 2) subsumes it, and the exclusion becomes host configuration |
| Runtime `CLAUDE.md` schema sent as the system prompt | conventions live in the vault and are read at run time | NOT MIGRATED: the platform encodes the conventions it enforces as contracts; a host may still keep a schema file for human maintainers |

## Characterization and intentional differences

`tests/fixtures/source_vault_ingest.txt` and `source_vault_conflicts.txt` are
verbatim line excerpts (see `tests/fixtures/README.md` for ranges and
checksums). Tests exercise them against temporary vault directories; the
excerpts print nothing the tests depend on and touch nothing outside pytest's
temporary directory.

Intentional differences in the adapted implementation:

- Refusals are closed codes on a typed outcome, not `ValueError` messages.
- `drop/` is immutable alongside `raw/`; `decisions.md` is writable alongside
  `index.md` and `log.md` (the source writes it from `conflicts.py` without
  going through `safe_write`).
- Provenance in a sources page is a `KnowledgeSource`, validated as a value;
  the source compared a frontmatter string.
- Dates and backup stamps are injected so behavior is reproducible.
- No `print`, no `SystemExit`, no environment defaults: a missing vault is a
  typed refusal, and the vault root is always explicit.
- The layout check runs on the resolved location as well as the requested
  path, so a link inside `wiki/` cannot reach `raw/`; the root-level files
  match exactly rather than by prefix; reads cannot leave the vault either.
- `PlannedPage.action` is enforced (`create_exists`, `update_missing`) — the
  source carried the field and ignored it, which let a model replace a page it
  had never seen with only the backup as a trace.
- A plan naming one page twice is `duplicate_path`; the source would have
  backed the first write up over the original.
- An apply is whole or not at all: a write that fails part-way is rolled back
  from what the vault held before. The source wrote page by page and a failure
  left the vault half-applied.
- The backup stamp is a single path component and the automatic one carries
  microseconds; the source used a second-resolution clock stamp.

## Slice 2 source-first decision

Re-inspected `vault/collect.py` (copy project docs into `raw/Programming/`,
hash-compare duplicate checkouts, report docs that changed after ingestion) and
the `Vault.raw_sources` / `ingested_paths` / `pending` excerpt (dedup by the
`source_path` recorded in `wiki/sources/`).

Decision (2026-09-21): **ADAPT** the intent — originals enter Raw exactly once,
duplicates are detected by content, a changed original is reported rather than
silently treated as done — into `knowledge.raw`, and **do not migrate** the
path-keyed dedup. `collect.py`'s hash comparison is the behavior worth keeping
and is now the identity rule itself: `source_for` derives the source from the
bytes. `collect.py`'s project-scanning roots and its `HANDOFF.md` exclusion are
host concerns, not platform behavior.

Intentional differences: Raw files carry typed provenance frontmatter
(`source_id`, `source_sha256`, `original_ref`, `raw_ref`, `extractor`,
`created`) and per-section markers for page/slide/image, so relationships are
recoverable from the file alone; the source's Raw was whatever a human or
`collect.py` dropped there. Raw is write-once (`Vault.write_raw` refuses an
existing file) rather than merely "never written by the tool". A drifted
original keeps the old Raw and writes the new one beside it under a
hash-suffixed name; the source's `--force` rebuilt the wiki page in place and
left no trace of the earlier text. Existing Raw files without provenance are
skipped by the index until adopted (slice 9, ledger by content hash, snapshot first).
The section marker is escaped inside body text so any original is
representable, and line endings are normalized to `\n` on entry and on disk;
the source stored whatever bytes the model or a human produced. Paths are
canonicalized so equivalent spellings are one identity, and the drift chain is
recorded in each Raw's `supersedes` line so the latest version is found by
following links, not by directory order.

Rollback removes `knowledge/raw.py`, `Vault.write_raw` / `read_original` /
`raw_files` / `exists` and the tests; nothing else imports them.

## Slice 3 source-first decision

The source tooling has no office extraction: its README lists images as a known
gap and it ingested Markdown only. There is nothing to wrap or adapt, so this
slice is new platform behavior against the Roadmap's requirement (PDF/PPT/DOCX
round-trip to Raw with page/slide/image relationships).

Decision (2026-09-21): adopt three libraries as the optional extra `office`,
each behind the `Extractor` protocol so nothing else in the platform imports
them. Recorded before adoption, from the installed distributions' metadata and
PyPI release history:

| Library | Version pinned | License (`License-Expression`) | Recent releases | Typing |
| --- | --- | --- | --- | --- |
| `pypdf[image]` | `>=6,<7` (6.19.0) | BSD-3-Clause | 6.19.0 (2026-09-16), 6.18.1 (2026-09-11), 6.18.0 (2026-09-07) — weekly cadence | `py.typed` |
| `python-pptx` | `>=1,<2` (1.0.2) | MIT | 1.0.2 (2024-08-07), 1.0.1, 1.0.0 (2024-08) — stable, slow | `py.typed` |
| `python-docx` | `>=1,<2` (1.2.0) | MIT | 1.2.0 (2025-06-16), 1.1.2 (2024-05-01) — stable, slow | `py.typed` |

Transitive: `lxml` (BSD-3-Clause), `Pillow` (MIT-CMU; also declared directly
through `pypdf[image]`, since image extraction needs it), `XlsxWriter`
(BSD-2-Clause), `typing_extensions` (PSF). All permissive; no copyleft. Both
OpenXML libraries are mature and release rarely because the format is stable;
`pypdf` is actively maintained by the py-pdf organisation. Alternatives not
taken: `pdfplumber`/`pdfminer.six` (heavier, MIT, would add table heuristics
that are better left to a later slice if needed); `PyMuPDF` (AGPL — excluded by
license); `unstructured` (large dependency surface for a small need).

Extraction maps the parsers' documented error types — `PyPdfError`,
`PythonPptxError`, `OpcError`, `LxmlError`, plus the standard-library errors a
broken stream raises — to the closed status `undecodable` with the cause
chained; a bare `Exception` boundary was rejected in review because it would
turn a programming error into a data status. An unreadable image inside a
readable original is skipped rather than fatal (also from review: one
undecodable picture must not cost every page's text). Shapes are classified
by type, never through `shape_type`, which raises for elements python-pptx
does not model. Rollback removes `knowledge/office.py`, its tests, the extra and the
CI install line; the `AssetSink` addition to the protocol stays useful for any
later extractor.

## Slice 4 source-first decision

The source tooling's README names images as a known gap ("Images under `raw/`
are ignored; the schema expects them to be read where relevant, which needs a
vision-capable model on the gateway"). There is no source behavior to adapt.

Decision (2026-09-21): describe at intake, through `ModelClient`, with the
image inline. Alternatives not taken: describing already-written Raw files
(Raw is write-once, so that would need a sidecar or a new Raw version for what
is a derived text — deferred until a need appears); passing the image as a
file path or vault reference in `ModelMessage.images` (would make every
adapter a file reader and would not work for staged, not-yet-written bytes);
naming a provider's vision API (rule 6: knowledge code depends on the model
interface only). The architecture rule "multimodal ingestion through model
capability requirements rather than a hard-coded vision provider" is met by
`ModelRequirements(vision=True)` on the request. A dry run deliberately spends
no tokens and therefore cannot show the exact description an apply would
write; it reports the count instead, and the phase spec says so.

From review: a model failure does not write. The first draft wrote the Raw
with empty image sections, and because identity is the content, the same
original could never be described later — a transient outage would have
baked the gap into write-once Raw. Now `model_failed` stops the write
(`description_failed`) and a later apply retries; `too_large`,
`unsupported_type` and `empty_answer` are properties of the image or the
answer, not the environment, so they write without text. Also from review:
the section marker records `described=<alias>` (rule 7, provenance of derived
text), an adapter that raises is a status, descriptions are memoised by
content and reused across drift, and the undescribed document is validated
before any token is spent.

## Slice 5 source-first decision

Re-inspected `vault/ingest.py`'s `plan_ingest`, `condense`, `extract_json`,
the three prompts and `Gateway.ask` (pinned excerpt covers the safety core,
not these). Behaviors worth keeping, each with a recorded reason in the source:
two passes (relevance over an inventory, then writes) are cheaper and more
accurate than one; condensation of long sources chunk by chunk, cached by
content hash, because a rejected plan otherwise redoes the most expensive step;
JSON extracted from fences or prose because models wrap it; the settled
decisions injected into the prompt so a rejected claim is not reinstated.

Decision (2026-09-21): **ADAPT** those behaviors into `knowledge.planning`
behind `ModelClient`; **do not migrate** the HTTP gateway client, its retries,
key handling and health check (Phase 5's model adapters own transport), the
`--review-dir` output (a host concern over `PlanningOutcome`), or the runtime
`CLAUDE.md` schema (the conventions are a platform default a host may replace).

Intentional differences: requests declare `structured_output` and an output
contract, so an adapter that can return structured data does, and text is the
fallback rather than the only path; the provenance a sources page must carry
is repaired in rather than demanded of the model (it is deterministic, and the
source's own experience was that a rejected plan wastes the condensation);
every failure is a closed status; the prompts are in English by default, where
the source's were Traditional Chinese for one vault — a host passes its own
conventions and the planner does not care which language they are in. The
planner never writes wiki content: the plan goes back through `Vault.apply`,
which is slice 1's whole point.

From review: the cache key is a hash of everything the condensed text depends
on (rendered source, chunking, prompt, model alias), not the original's hash
alone — a described image or a different model must not read a stale
condensation; an empty condensed part is a failure, never cached; whether a
page is created or updated is decided from the vault, not asked of the model
(engineering rule 1: deterministic details belong in code, not prompts); a
contradiction that only says "none" is dropped rather than written as a ⚠️
block; and every failure outcome reports whether the source was condensed.

Rollback removes `knowledge/planning.py`, `Vault.cache_read` / `cache_write` /
`wiki_pages` and the tests; nothing else imports them.

## Slice 6 source-first decision

Inspected and pinned `vault/brain.py`'s static half (`page_name`, `scan`,
`fix_links`; `tests/fixtures/source_vault_lint.txt`). The judgement half (the
lint prompt, `gather_content`, the 120 KB budget) and the CLI are not pinned:
they are a model pass over the computed report, deferred until a need appears,
and would go through `ModelClient` like every other model call.

Decision (2026-09-21): **ADAPT** the computed findings into a typed
`LintReport` with the source's rules kept exactly — only `.md` stripped from a
page name (the `Continue.dev` lesson), a trailing `.md` wrong only when it names
a wiki page (the `[[CLAUDE.md]]` lesson), entry points excepted from orphans,
dangling links ranked by reference count, only flagged links repaired and case
corrected against real page names. The source's `source_path` check is kept as
`broken_source_path` for an existing vault's pages and joined by
`unknown_source_id` for typed provenance; its `pending` (raw files never
ingested, by path) becomes `pending_sources` by `source_id` against the Raw
index, so a legacy Raw file without provenance is not reported until slice 9
adopts it. `manual_edits` waits for slice 7's state file.

Intentional differences: findings are closed contracts, not dict entries; the
report is data for a host to render (the source printed Traditional Chinese
lines); `fix_links` writes through `Vault.write` with the stamp the caller
gives, so a lint repair is backed up like any page write. From review: the
report can no longer be aborted by what a page contains (an empty link, a
bare `⚠️`, a malformed `source_id`, a non-UTF-8 page — each is a finding);
frontmatter is read as leniently as the source read it (the first draft
reused the strict Raw reader and would have called ordinary Obsidian
frontmatter missing); a superseded Raw is not pending; and `Vault.write`
writes `\n` on every platform so a repair does not change line endings.
Rollback removes `knowledge/lint.py`, its tests and the excerpt; nothing else
imports them.

## Slice 7 source-first decision

Re-inspected the pinned `conflicts.py` excerpt (`tests/fixtures/
source_vault_conflicts.txt`, characterized in slice 1): append-only
`decisions.md` injected into prompts, `⚠️` markers found by regex, a marker
cleared by line number with a moved-line refusal, page hashes in a state file
and manual edits reported with tool-written pages excluded, chosen over git
because the vault lives in a synced folder.

Decision (2026-09-21): **ADAPT** all of it. The decision is a contract, the
header and field labels are English (the source's were Traditional Chinese;
the record's language is the host's), `resolve` writes the decision before
clearing any marker so a marker is never removed without its reason on record
(the source did both from one CLI command in the same order), clearing goes
through `Vault.write` with a backup, and the state file is `.ingest-state.json`
through the vault rather than `.brain-state.json` beside it. Manual-edit
detection lives in `knowledge.lint` because it is computed by reading, and the
lint report carries it. From review: the source's `tool_written` exclusion
was recorded *after* the tool's writes, so a person's later change to a
tool-written page was invisible until the next state write — replaced by
`note_written`, which refreshes those pages' hashes at the moment the tool
writes them; several markers on one page are cleared in one write so the
one backup is the original; only lines matching the marker rule are ever
removed (the source deleted any line containing the symbol); a page keeps
its line endings; and a malformed clear list is refused before any write. Rollback removes `knowledge/conflicts.py`, the state
functions in `knowledge/lint.py`, `Vault.state_read` / `state_write` and the
tests; nothing else imports them.

## Slice 8 source-first decision

The source tooling's README lists `Query`, the schema's third operation, as
not implemented; there is nothing to adapt. This slice is new platform
behavior against the Roadmap's exit criterion that query answers cite source
provenance.

Decision (2026-09-21): deterministic lexical retrieval first (BM25, no index
to maintain, no dependency), because it is exact, explainable and enough for a
vault of hundreds of pages; embeddings or a vector index would add a model
dependency and a stored artifact for a gain this corpus size does not need,
and can come later behind the same `retrieve` shape. CJK is handled with
character bigrams rather than a segmenter (no dependency; adequate for a
Traditional-Chinese vault). Synthesis is optional and strict: a model may cite
only the passages it was given, and text that cites nothing or something else
is refused as `uncited` rather than returned as an answer — words without a
retrieved source behind them are not an answer in a knowledge base whose whole
point is provenance. Review of the PR sharpened this: a text that cites
nothing is what the prompt asks for when the passages do not answer, so it is
`unanswered` with its sentence kept, not refused; citations written as
`[1, 3]` or `[1-3]` count; a superseded Raw is not in the corpus (its
successor holds the evidence); CJK is indexed by character as well as bigram
so a one-character question matches; a Latin term glued to CJK is its own
token; wiki bodies are split from frontmatter by the lint module's reader
(CRLF pages included); the adapter-exception-to-`Failure` rule now lives once
in `knowledge/modelcalls.py` for description, planning and query; and a
default trace is derived per request rather than constant. Rollback removes
`knowledge/query.py`, `knowledge/modelcalls.py` (inlining the helper back into
`describe.py` and `planning.py`), `knowledge.lint.body_of` and the query tests;
nothing else imports them.

## Slice 9 source-first decision

Re-inspected `vault/snapshot.py` (copy `wiki/`, the root files and
`.brain-state.json` to `.brain-snapshot/<stamp>`; a restore snapshots the
current state first) and the README's "one sharp edge" (a sources page counts
as ingested by the `source_path` it records, so a moved Raw file looks
un-ingested and a changed one looks done).

Decision (2026-09-21): **ADAPT** `snapshot.py` as the migration adapter's
safety net (`knowledge.migrate.snapshot` / `restore`, the same managed set with
the platform's state and ledger in place of `.brain-state.json`, a name that
is one path component, and no clock: the stamp is injected) and **adopt
legacy Raw through a ledger rather than by rewriting it**. Two other paths
were rejected: rewriting each legacy file to carry provenance frontmatter
would break the one rule the platform exists to keep (`raw/` is never
written), and treating legacy files as new drops would duplicate every one
of them under `raw/` with a hash-suffixed name and sever the sources pages
that already point at the old paths. The ledger keeps the bytes where they
are, gives each file a content identity the index, lint, planning and query
share with ingested Raw, and makes drift visible: a file that no longer
hashes to what was adopted is out of the index and reported until someone
re-adopts it by name. The `source_path` sharp edge is closed the same way —
a page's path is resolved once to a content identity and the typed lines are
added beside it, so a later move of the file changes nothing the page relies
on.

Intentional differences: adoption is a dry run by default with the exact
write list; an apply that writes is preceded by a snapshot and writes all or
nothing (the source's snapshot had no adopt step; `Vault.apply`'s
remember-and-put-back rule is reused); a Big5 or empty legacy file is
reported, not adopted; a sources page keeps its `source_path:` and its line
endings; and nothing here prints, exits or reads a clock. Review of the PR
added: a damaged typed head is neither typed nor legacy and is never
adopted; a note's own frontmatter is not a passage; the same bytes twice
are one source (the first path wins, as a duplicate drop would); an emptied
adopted file is drift and a deleted one is dropped from the ledger; a page
the vault would refuse to write is reported before anything is written; a
reused stamp is refused before any write; snapshots copy links as links and
a restore refuses a managed directory that is itself a link; and the typed
scan runs once per adoption.
Rollback removes `knowledge/migrate.py`, `Vault.ledger_read` /
`ledger_write`, the `ledger` branch of `RawIndex.scan`, `RawEntry.adopted`,
`adopted_document` / `load_document` (query returns to `parse`) and the
tests; nothing else imports them.
