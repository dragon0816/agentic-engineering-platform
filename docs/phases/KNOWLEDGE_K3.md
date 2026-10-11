# K3 — Schema-driven ingest, section-level writes, sandbox merge (specification, for owner review)

Plan: `docs/phases/KNOWLEDGE_PIPELINE_RELEASE.zh-TW.md` sections 4.3, 4.4, 4.8 and stage K3.
Acceptance (plan): ingest into a test vault loses no existing content; two sandboxes that
change different sections merge automatically; changes to the same section are listed as
conflicts.

## Findings that shape K3

1. **The owner's RS_Knowledge already works this way.** It has the following files:
   - `CLAUDE.md` is the schema and the ingest system prompt.
   - `skills/ingest-<category>/SKILL.md` holds one rule set per data category (Market,
     Productions, Knowledge, Competitor). It has `applies_to: raw/<category>` and is
     chosen by the Raw folder the source sits in.
   - `checks/` holds rules that a program runs rather than the model.

   Domain owners edit these files in Obsidian without changing code. The AEP copy of
   `rs-k` has neither `CLAUDE.md` nor `skills/`, so today its ingest uses the built-in
   conventions.
2. **Ingest rewrites whole pages.** `PlannedPage.content` is the complete file. Existing
   content is protected only by the prompt ("do not delete"). A whole-page rewrite also
   makes merging two sandboxes a page-level conflict every time.

## 1. Schema and rules live in the vault (proposal)

- The pipeline reads `CLAUDE.md` as the base schema (as K1 already does). It appends the
  one `skills/ingest-<category>/SKILL.md` whose `applies_to` matches the source's Raw
  folder. A source in `raw/drop/` or with no matching skill gets the schema only. This is
  the owner's existing rule ("放對資料夾就等於選對了規則").
- Copy the owner's `CLAUDE.md` and the four `ingest-*` skills into the `rs-k` copy, plus
  one added language rule: bilingual `aliases` and `summary_zh`/`summary_en` in
  frontmatter (plan 4.2). The OneDrive vault is not modified.
- The built-in conventions remain the fallback for a vault without `CLAUDE.md`, rewritten
  to the Karpathy base (sources/entities/concepts/syntheses, index, log, ⚠️ lines with
  dates, `decisions.md` final, `wiki/paths/` human-only).
- The plan preview shows which schema and which skill were used.
- `ask-*`, `quiz-build` and `checks/` are not part of K3. Program checks fit K6
  verification.

## 2. Domain scope: rules by category, scope by matrix cell (proposal)

- **Rules** follow the owner's existing four data categories, chosen by Raw folder.
- **Scope** for merge review follows the 5 markets × 4 product lines matrix. It uses the
  K2 `index_categories` of each touched page:
  - A sandbox declares its domain (for example `product-vna`) when it is created.
  - A merged change to a page outside that domain, or to a shared page (technical
    concepts, companies), is marked "proposal" in the merge report.
  - Nothing is blocked; the owner decides. This is workflow, not permission control.

## 3. Section-level writes and a deletion guard

New page operations in a plan, replacing whole-page `content` for existing pages:

| op | meaning |
|---|---|
| `create` | new page, whole content (as today) |
| `add_section` | append a new `## heading` section to an existing page |
| `append_to_section` | append lines at the end of an existing section |
| `replace_section` | replace one section's body; allowed only if every sourced line it removes is kept or `correction: {reason, source}` is given |
| `set_frontmatter` | change listed frontmatter fields only (`updated`, `tags`, `aliases`, …) |

- A "sourced line" is a line with a `[[source page]]` link or a ⚠️ line.
- The Host enforces the guard, not the prompt. A plan that removes a sourced line without
  a correction is invalid and shown as such.
- `wiki/paths/` is refused (human-written).
- Pages keep their headings as section identity (`## heading`, with duplicates numbered).
- Back-compat: a whole-page `update` from an old-style answer is converted into section
  operations by diffing against the current page, and then the same guard applies.

## 4. Sandbox merge

- At creation a sandbox already keeps a snapshot of its base. Merge does a three-way
  comparison per page and per section: base snapshot, sandbox, and current published
  vault.
  - A section changed only in the sandbox is taken.
  - A section changed only in published is kept.
  - A section changed in both is a **conflict**, listed with both texts. It is not merged
    until the owner picks one.
  - New pages and new Raw are a union; Raw is content-addressed and never conflicts.
- After the merge preview: static lint, plus a check that no sourced line from either
  side was lost.
- Publishing is a separate, always-confirmed step:
  - write a new Knowledge version (new vault directory and manifest with digests, as in
    K2.5's candidate);
  - switch the `host.json` binding with a backup;
  - restart. The previous version stays for rollback.
- The merge result never edits the published vault in place.

## Acceptance

1. Ingest of the K1 test sources into a test vault with section operations: no sourced
   line lost (checked by program against the pre-ingest vault).
2. Two sandboxes of one base: A edits section X of a page, and B edits section Y of the
   same page. Merge is automatic and both edits are present.
3. A and B both edit section X: the merge lists one conflict and writes nothing for it.
4. Live: one source from each of the four categories ingested into an `rs-k` sandbox
   with the owner's schema and skills. The owner reviews the pages.

## Slices

K3.1 schema + category skill selection (vault-resident) → K3.2 section operations and the
deletion guard → K3.3 three-way merge preview with conflicts → K3.4 publish as a new
version (confirmed) → K3.5 live run on `rs-k` with the owner's schema.

## Owner decisions (2026-10-11)

1. Schema and skills live in the vault (proposal 1).
2. Rules by data category, scope by matrix cell (proposal 2).
3. Publishing a merged version needs one person's approval (one confirm click).
