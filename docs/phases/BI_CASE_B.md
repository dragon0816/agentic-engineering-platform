# BI Knowledge Case B: multi-table reports, with guided steps

> **Status.** Spec draft, 2026-10-27 (Claude Code). Owner approved Case B as the next BI slice
> (`docs/DECISIONS.md` 2026-10-27 "BI Knowledge Case B next; RS_Knowledge may go live"). Open choices are in §8;
> nothing is implemented yet.
>
> **Source.** Knowledge Strategy v1.3 §4.4.2 and §4.7 (`docs/proposals/KNOWLEDGE_STRATEGY_v1.3.md`), Case A as built
> (`docs/DECISIONS.md` 2026-10-21, `docs/CONTRACTS.md` "BI cards API and capability"), and the upstream tool
> `tests/fixtures/bi_vault_example/tools/bi_ingest.py` with its samples under `tools/samples/real/`.

## 1. What Case B adds, in one paragraph

A maintainer drops one report (a Markdown file or an Excel workbook) that holds several tables, for example a
supply-chain study with a vendor-comparison table, a chipset table and a cert-lab table. AEP turns all of it into
BI cards of the right types in **one preview**: customers become Account, test-instrument makers become
Competitor, chip/RF/module/lab companies become Ecosystem. One company named two ways (聯發科 and MediaTek) ends up
as one card. Nothing is written until the maintainer confirms, and the whole import can be undone, as in Case A.

## 2. The steps a maintainer follows (the owner's point: steps as clear as the Wiki's)

The BI 卡片 import view becomes a stepper with the same look and behaviour as the Wiki's Pull → Ingest → Test
(`#kp-stepper`, `KP_STAGES`): numbered steps, "Step N of 4", Next / Back, a step unlocked only when the one
before it is done.

| Step | The maintainer | AEP shows |
|---|---|---|
| **1 放入報告** | Chooses the dataset, drops a `.md`, `.xlsx` or `.csv` file, and picks a **recipe** (§3) from the dataset's saved recipes or uploads one. | Every table found: its heading or sheet name, its columns and row count, and which recipe pass will read it. Tables no pass reads are listed as "not used". |
| **2 檢查對應** | Reads the warnings; fixes the recipe or the file and re-runs if needed. | Per pass: the card type, the column → field mapping, and the row counts (create / update / unchanged / skipped). Warnings, including the new ones in §5. Alias merges ("聯發科 → MediaTek"). |
| **3 確認寫入** | Selects rows (all by default) and confirms. | The per-card diff exactly as Case A, across all passes; then the result with **Undo**. |
| **4 檢查結果** | Opens the Dashboard and asks a question in the chat. | Links to the cards written, the Dashboard gap sections that changed, and two suggested questions for the dataset (e.g. "哪些 Ecosystem 公司提供 WiFi-7 晶片？"). |

A plain one-table CSV goes through the same four steps; a CSV needs no recipe (Case A's behaviour, a single pass).

## 3. The recipe: one file for one kind of report

Upstream runs its CLI several times on one file, each run with its own `--table` filter, `--type` and mapping
(`tools/samples/real/README.md`). Case B puts those runs into one JSON **recipe**, so one preview covers the
whole report and the order of passes is fixed.

```json
{
  "schema_version": "aep.bi.recipe/v1",
  "name": "supply-chain-study",
  "dataset_schema": "bi.schema/v1.1",
  "name_aliases": {"聯發科": "MediaTek", "R&S": "Rohde & Schwarz"},
  "passes": [
    {"id": "accounts",   "tables": "has:廠商|客戶",  "entity_type": "Account",    "mapping": {"columns": {}}},
    {"id": "instruments","tables": "has:儀器",       "entity_type": "Competitor", "mapping": {"columns": {}}},
    {"id": "suppliers",  "tables": "2-3",           "entity_type": "Ecosystem",  "mapping": {"explode": [], "derive": {}, "compose": {}}}
  ]
}
```

- `tables` uses upstream's selector: `all`, indexes and ranges (`0,2-3`), or `has:colA|colB`. Markdown tables are
  numbered in file order; an Excel workbook's tables are its sheets, selected by index or `sheet:<name>`.
- `mapping` is Case A's mapping (`columns`, `entity_type`, `enum_aliases`, `defaults`, `skip_rows`) plus the
  advanced keys in §4. Unknown keys are **refused** with `mapping_key_unknown` (today they are silently ignored).
- Recipes are stored per dataset (`recipes` table in `bi.sqlite`, versioned, with who saved it and when), so the
  next report of the same kind uses the same recipe. A subscribed (read-only) dataset cannot save recipes.
- Bundled example recipes: the six `tools/samples/real/` mappings rewritten as one recipe, as test data.

## 4. Advanced mapping keys (behaviour taken from `bi_ingest.py`, reimplemented, not imported)

Applied per pass, before column mapping, in upstream's order: `skip_rows` → `text_replace` → `explode` →
`exclude_names` → `derive` → `compose`.

| Key | Behaviour |
|---|---|
| `text_replace` | `{column, pairs: [[regex, replacement]], into?}`: regex substitutions, optionally into another column. |
| `explode` | `[{column, into, strip_after?, set?}]`: one cell split on `; ，、 \| , newline` (not inside brackets) becomes one row per part; a trailing `(…)` goes to `__ticker` (four digits) or `__note`; `set` adds constants. |
| `exclude_names` | Rows whose alias-resolved name is listed are dropped. |
| `derive` | `{target: {from: [cols], map: {regex: value}, all?}}`: fills an **empty** target from the first (or all) matching patterns. |
| `compose` | `{target: template}` with `{col}` placeholders; a line whose placeholders are all empty is dropped. Used for `body`. |
| `name_aliases` | Recipe-level map; resolves `name`, `product_name` and link targets before the card key is built. |

Regular expressions are compiled with a length cap and checked when the recipe is saved (`recipe_invalid` names
the pass and key), so a bad recipe fails at step 1, not halfway through a preview.

## 5. Where AEP deliberately differs from upstream

| Upstream | AEP | Why |
|---|---|---|
| New non-empty values overwrite stored ones. | Case A rules: a field a person edited is kept and the import adds a proposal (`human_kept`). | v1.3 §4.4.3: never overwrite human content. |
| Lists are unioned on merge. | Lists are unioned too, and each added item records its source (`ref` = `file#table:row`). | VE-05 needs two sources on one card. |
| Roles are separated only by running passes in order with `exclude_names`. | Same, plus a **role conflict** warning when one resolved name would become two types in one preview (e.g. Account and Ecosystem). The earlier pass wins; the later row is shown as skipped with the reason. | VE-06 (中磊 is Account, never Competitor); the maintainer sees the decision instead of a silent drop. |
| Writes Obsidian files directly. | Writes `bi.sqlite` through `store.apply`, one import record for the whole report; undo reverses all passes. | Case A's single write path. |

New warnings: `alias_merged`, `role_conflict`, `table_unused`, `exploded_row` (count per source row, shown once).

## 6. Contract changes (to be written into `docs/CONTRACTS.md` before code)

- `POST /api/bi/import/preview` accepts `{file_name, file_base64 | csv_text, recipe | recipe_id}`. `.md`, `.xlsx`
  and `.csv` are read; anything else is `file_type_unsupported`. Size cap as Case A's body limit.
- The preview reply adds `tables[]` (index, title or sheet, columns, rows, `pass_id | null`) and `passes[]`
  (id, entity type, counts, warnings); rows carry `pass_id`.
- `GET/POST /api/bi/recipes`, `GET /api/bi/recipes/{id}` per dataset; read-only datasets refuse POST (409).
- Apply and undo are unchanged; the import record lists the passes.
- The agent tool stays query-only in Case B (an import tool would be a side effect needing approval; later).

## 7. Tests (acceptance, all automated, fixture data only)

1. A `tools/samples/real/` extract plus its recipe previews to the expected counts per pass; the preview writes
   nothing (store bytes unchanged).
2. VE-05: 聯發科 and MediaTek become one `Ecosystem:MediaTek` with both sources; no `Ecosystem:聯发科`.
3. VE-06: 中磊 is never created as Competitor; a role conflict shows `role_conflict`.
4. Each advanced key has unit tests matching the upstream samples' outputs (compared, not imported).
5. Re-importing the same report creates no duplicates; a person's edit is kept as a proposal.
6. Undo of a multi-pass import restores every pass.
7. Excel: a two-sheet workbook selected by `sheet:<name>`; dates come out ISO.
8. Recipe validation: unknown key, bad regex, missing pass id are refused at save time.
9. Browser test of the four steps (headless), with a step locked until the previous one is done.

## 8. Choices for the owner before implementation

1. **Who writes a recipe?** Recommended for Case B: the maintainer uploads or edits recipe JSON (examples
   bundled), and AEP validates it. Later (not in Case B): the `knowledge/bi-import-mapping` Skill drafts a recipe
   from the tables' headings and columns for the maintainer to confirm.
2. **Role conflicts:** recommended as in §5 (earlier pass wins, shown as a warning). Alternative: stop the preview
   until the maintainer picks a role for each conflicting name.
3. **Scope check:** Markdown and Excel reports, recipes and the four-step UI are in; Concept candidates (Case C),
   quality view (Case D), slides (Case E), real customer data and an import tool for the agent are out.

## 9. Implementation order (after §8 is answered)

Contract → recipe model and validation → readers (Markdown, Excel) → transform pipeline (§4) → multi-pass
preview and role/alias warnings → store list provenance → API → four-step UI → browser test → docs and handoff.
