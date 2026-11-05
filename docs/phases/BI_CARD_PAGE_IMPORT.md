# Importing Obsidian card pages into a BI dataset

Status: design, 2026-11-03, by Claude Code from the owner's decisions relayed by the BI orchestrator. Decision record:
`docs/DECISIONS.md` 2026-11-03 "The card-page importer, and samples". Needed by R6 (`docs/runbooks/R6_MARKET_BI.md` §3): two of
the five bases hold their cards only as pages.

## 1. Rules (owner)

- It reads an Obsidian card page's frontmatter and maps it to schema fields the way CSV import does. **No model; deterministic.**
- The same preview → apply → commit path as the existing imports.
- **The page is the evidence.** Unknown fields and invalid values are listed in the preview, never invented or silently dropped.
- `SAMPLE-` pages and `BI_Vault_Example/tools/samples` are imported and **marked as samples**, not left out.

## 2. Reading a page

`capabilities/bi_cards/page_import.py`, pure apart from the store it previews against. No YAML package (the install stays
as it is); the frontmatter these pages use is a small subset, read strictly:

- between the first two `---` lines: `key: value`, `key: [a, "b, c"]`, `key:` followed by `- item` lines, and `key:` empty;
- quotes removed; `[[Target]]` and `[[Target|shown]]` become `Target`, since the schema's link fields hold names;
- **anything else is a problem listed for that page and line** (a nested map, an unterminated list, a line with no key). The
  rest of the page is still read, so one bad line does not hide the others.

The type comes from the page's `type:`, matched to the schema's types without regard to case or `_`. A page with no
frontmatter, or an unknown type, is a listed problem. `_Templates/` and pages holding Templater syntax (`<%`) are listed as
skipped. A `.csv` in the same request is read as CSV import reads it, with its type from the file name or headers: this is how
`tools/samples` goes in.

## 3. Mapping and preview

Rows go through `importer.preview`, the same code as CSV: column mapping, `Registry.normalize`, name aliases, create, update or
unchanged, and its warnings. So a page's fields behave as a CSV's columns do. Two small additions:

- a frontmatter list stays a list (`normalize` takes one as it is), because `split_list` would break an item holding `、` or `;`;
- rows can be handed over directly instead of as CSV text.

Links between pages in the same request count as known, so a link to a card coming in with it is not reported missing.

`POST /api/bi/import/pages/preview` `{dataset, pages: [{path, text}], samples?: bool}` writes nothing and answers
`{preview_id, summary, types: [{entity_type, columns, rows}], problems: [{path, line?, code, message}], skipped: [{path, reason}]}`.
An unknown field is a column with status `unknown`; an invalid value is a row warning with its field left empty.

## 4. Apply

`POST /api/bi/import/pages/apply` `{preview_id, folder?}`. For the rows that have something to write:

1. Each page becomes a source (`Staging.add_source`, deduplicated by content), so it is kept, and in a vault it travels to the
   shared folder.
2. A run of kind `ingest` records the sources; `store.commit_run` writes every row in **one transaction and one import commit**,
   with one evidence row per value: the source, `locator: {line, key}`, the frontmatter line as `excerpt`, basis `fact`. So a base
   makes one commit of its sources and one of its cards (D3).
3. **Same-named cards merge** (owner's D3; `merge_rows`, in this path only, seed CSVs through it too; CSV and run paths elsewhere stay as they are):

   | The card holds | This row has | Result | Preview counts it as |
   |---|---|---|---|
   | Nothing | A value | Written | `fill` |
   | The same value | | Nothing changes; the page's evidence is added | `same` |
   | A list, or the row has one | Other items | Joined, old items first, nothing lost | `join` |
   | A different scalar | | **A proposal for review; never overwritten** | `proposal` |
   | A value a person set | Anything else | Theirs stays; a proposal, as for any import | `human_kept` |
   | A derived field | Another value | No proposal; the later value stays. In the shipped schemas that is only `updated` | `bookkeeping` |

   Rows of one request merge with each other the same way. Apply does what the preview said: a card that moved since then refuses the whole
   request (`cards_changed`).
4. **Evidence from each base stays on the merged card**, also from a row that changed nothing. A proposal's evidence does not sit on the value it did not change.
5. **Samples.** A card keeps its mark. A row whose mark differs from its card is listed in `mark_conflicts` and all its new and different values become
   proposals. So another base's sample row cannot turn a real card into a sample, nor a real page turn a sample into fact, without a person. (`store`'s "once
   marked stays marked" is not reached in this path, since the row takes its card's mark.) A combined dry run found none of these, so no count to weigh.

Nothing here reaches a model, and nothing is written before the apply.

## 5. Samples

**The mark already exists:** a card's `synthetic`. `importer.FICTIONAL` sets it from any value matching `虛構|範例|示範|^SAMPLE-` (until 2026-11-05 also `待…驗證|待查證`, which marked real cards),
and a synthetic card is never `trusted`. Pages get the same rule. `samples: true` marks every row of a request, for files like
`tools/samples` whose rows do not all say so; the person ticks it on the page. **A ticked row also gets the `SAMPLE-` name prefix**, never
twice (owner, 2026-11-03), so the default pack leaves it out unless `include_sample`. A link from one such row to another follows the
rename; a link that still does not resolve is listed in the preview. Rows not ticked keep their names.

What each reader does with a sample, read at this branch:

| Reader | Before | Now |
|---|---|---|
| `bi__query`, card search | Returns `synthetic: true`, `trusted: false`; the Skill tells the model to say 範例資料. It rests on the model. | The same, plus a **host-written line** under the answer with the count |
| `bi__query`, default pack | `_prelude.cards()` drops only names starting `SAMPLE-`, unless `include_sample` | Unchanged, plus a host-written line when the data holds samples |
| `bi__query`, `sql` and saved SQL analyses | No filter: `cards.synthetic` is a column they may use | Unchanged, plus a host-written line when the data holds samples |
| `aep_bi_query` | As `bi__query` | Returns the same line as `sample_note` |
| Dashboard's quality check | `sample_not_marked` for a `SAMPLE-` name not marked | Unchanged |

The host line is added like the source line, so the answer says so whatever the model wrote: 「注意：這次查詢含 N 張範例資料，不是事實。」
A note about an analysis or SQL says the data holds samples that it may include, since rows cannot be traced back to a card.
An answer carries one note per dataset: the count of sample cards its searches returned, each counted once; the general note only if they returned none.

**Why the default pack does not drop every marked card.** It was tried. Every shipped demo card is `synthetic`, and `FICTIONAL` also matches
「待查證」, so 90 of robotics' 104 seed cards would vanish from the Dashboard and the tests of the demo Dashboard fail. So a card marked only by
its wording, with no `SAMPLE-` name, **still counts in a built-in analysis**, and the host's line says it may.

Measured again on 2026-11-05, on the real `market-intel` and on this rule moved to `synthetic`: 20 of its 31 pack analyses move, robotics' demo seed loses 29 tables, and 7 cards marked only by 「待查證」 leave, such as `WiFi-7`, that 29 real cards link to. Not changed; the decision is the owner's.

## 6. Page

Under step 1 of the build flow: 「匯入卡片頁（Obsidian）」, a folder picker that reads the `.md` and `.csv` files in the browser, a
tick box 「全部標成範例資料」, the preview's counts, problems, unknown fields and skipped files, then 「確認匯入」. `.obsidian/` and other
non-card files are never sent. Requests stay under the 8 MiB JSON limit; a larger selection is refused with the size, and the person
picks a smaller folder (the largest base is 2.3 MB).

## 7. Tests and dry run

Fixtures are fictional, written in the tests, and committed under `tests/`. Nothing from `files\` goes into a commit. The dry run
over the five real folders is a read-only script in `.scratch` on a temporary workspace; only its counts are recorded, in `docs/TASKS.md`.
