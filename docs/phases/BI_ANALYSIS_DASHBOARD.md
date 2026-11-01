# BI: schema, skills, cards and analyses only (Dashboard as analyses, Atlas as a viewer)

Status: design approved in direction by the owner (2026-11-01); AEP side built 2026-11-01 (F1–F3, P1–P5,
D1–D4; see `docs/TASKS.md`); Atlas A1/A2, I1 and the owner's I2 remain. Builds on
`docs/phases/BI_TEST_AND_TOOLS.md` (T1–T3: benchmarks, the skill AI and analyses on the Agent harness) and
`docs/phases/KNOWLEDGE_REPO.md` (vaults: commit, push, publish). Decision record: `docs/DECISIONS.md`
2026-11-01 "BI: retire the domain configuration and the coded Dashboard".

Parallel work: Claude Code builds the AEP side in this repository; Codex builds the Atlas side in
`C:/Users/Chi_L/Documents/claude/atlas-analysis-dashboard` (brief: `BI_ANALYSIS_DASHBOARD_ATLAS_BRIEF.md`). The
two meet only at the feed contract in §5 and the fixtures in §6, which are frozen before either side starts.

## 1. Why

The owner's two objections (2026-11-01):

1. **The domain configuration duplicates schema and skills.** A BI knowledge base should need only a schema
   (what cards and fields exist, and their allowed values), skills (how sources are read) and the cards. The
   domain configuration (`aep.bi.domains/v1`, BI vaults V10) holds a taxonomy, value chains and name aliases
   that belong in those three.
2. **The Dashboard is hard-coded.** `capabilities/bi_cards/dashboard.py` (sections 1–19, from the robotics
   sample's Dataview dashboard) and `market.py` (20–31, A–A3, from the manager's bases) are Python a user
   cannot change, which another project cannot reuse, beside T3's editable analyses and the separate Atlas
   dashboards: three ways to do one thing.

Target: **four concepts** — schema, skills, cards, analyses. The Dashboard is the vault's analyses. Atlas is an
optional viewer of the same analyses through a read-only feed; it owns only its own layout.

## 2. After the change

| Concept | Holds | Where | Edited by |
|---|---|---|---|
| Schema | card types, fields, kinds, **allowed values with labels and aliases** (segments, technology areas, chains) | vault, `schema` unit + schema document | Session A (AI) or by hand; a new schema version |
| Skills | how sources in each folder are read (classify, extract) | vault, `skill:<name>` units | the skill AI on the harness (T2) or by hand |
| Cards | the data, including **each entity's aliases** (an Account's other names) and a Node's chain | vault, card/field units | ingest, review, hand edits |
| Analyses | questions answered by SQL or a guarded Python script, with a chart spec and parameters | vault, `analysis:<slug>` units | the analysis AI (T3) or by hand |

The Dashboard tab renders the vault's analyses (in an order the vault keeps). The coverage matrix and the
chain views become analyses too. `bi__query`'s `analysis` argument names a saved analysis.

## 3. Part D: retire the domain configuration

What `aep.bi.domains/v1` holds today (`capabilities/bi_cards/domains.py`) and where each part goes:

| Part | Used by today | Moves to |
|---|---|---|
| `domains[].segments` (application segments) | coverage matrix rows/columns, market sections | the schema field's allowed values (`segment`; 2.0.0 already lists the 11 market segments) with labels and aliases |
| `areas` / `area_field` (technology areas) | coverage matrix | a schema field `tech_areas` (list of allowed values) on the types that need it, in a new schema version |
| `domains[].nodes`, `domains[].chains` (`node_pattern`) | market chains A–A3 | Node cards: field `chain` (allowed values = the chains, in the schema); the chain pattern becomes data, not configuration |
| `name_aliases` | canonical names in CSV imports and AI candidates | an `aliases` field (list) on the entity types that are matched by name (Account, Competitor, ...). Matching reads the cards' aliases (a lookup built from the store), so a pushed card brings its aliases |
| `notes` | extraction notes | already moved to `<domain>-extract` skills (R3) |

D-steps (each its own slice, tests first):

- **D1 Schema allowed values with aliases.** The schema already supports allowed values and enum aliases (V9).
  Add `tech_areas` and `chain` fields in a new BI schema version (`bi.schema/v1.1@2.1.0`), generated like
  2.0.0 (`scripts/build_bi_schema_v2.py`).
- **D2 Card aliases.** An `aliases` field on name-matched types; `importer` and `ai_runs._canonical_names`
  resolve names through the store's aliases instead of `domains.Config.name_aliases`.
- **D3 Migration.** `vault.migrate_domains(vault)`: one change commit (purpose 「把領域設定搬進 schema 與卡片」) that
  upgrades the schema, writes each alias onto its card (creating none: an alias whose card is missing is
  listed in the report, not invented), sets `chain` on Node cards from the old patterns, and removes the
  `meta:domains` unit. A dry run shows the change list first (the person confirms).
- **D4 Remove.** `domains.py`, the 「領域設定」 panel, `/api/bi/domains` and their tests, once nothing reads them.
  A dataset only on this PC with a domain configuration gets the same migration.

## 4. Part P: the Dashboard as analyses

### 4.1 Analysis parameters and requirements

An analysis unit (`analysis:<slug>`, T3) gains two optional keys:

- `params`: `{"<name>": {"type": "enum"|"bool"|"date"|"text", "default": ..., "values_from"?: "<Type>.<field>"}}`
  — e.g. `domain` (values from a schema field), `include_sample` (bool), `today` (date, default today).
  SQL receives them as named parameters (`:domain`); a script reads `PARAMS["domain"]`.
- `requires`: `{"types": [...], "fields": ["<Type>.<field>", ...]}` — the analysis is offered only when the
  vault's schema has them (as `market.REQUIRES` does today).

And the vault keeps `meta:dashboard` = `{"order": [slug, ...], "hidden": [slug, ...]}` (a unit, committed and
pushed) for the Dashboard's order.

### 4.2 Analysis packs

A pack is a file `aep.bi.analysis_pack/v1`: `{"format", "id", "title", "version", "analyses": [<analysis unit
values with slug>]}`. AEP ships one built-in pack, `bi-market-default`, written by converting every section of
`dashboard.py` and `market.py` into SQL (preferred) or a guarded script. Importing a pack stages the analyses
the schema satisfies (`requires`) and lists the rest; a new vault imports the default pack. Any vault can
export its analyses as a pack, and another vault (another project) can import it.

### 4.3 Parity, then removal

- **P1 Params and requires** in `analyses.py` (run, check, page parameter controls).
- **P2 Convert** each section into the default pack. **Parity test per section**: on the fixtures (robotics
  sample, `tests/fixtures/bi_schema_v8/`, the market fixture vault of §6), the pack analysis returns the same
  rows as the Python section for every domain and with/without samples. No section is dropped silently: a
  section that cannot be expressed is listed in the pack's report and kept until it can.
- **P3 The Dashboard tab renders analyses** (order from `meta:dashboard`, parameters at the top, gap/warning
  badges from a result column `level` of `gap`|`warning`, counts summed for the strip).
- **P4 `bi__query`** `analysis` names a saved analysis (and its params); the chat reads the published version.
- **P5 Remove** `dashboard.py`, `market.py`, `coverage.py` section code and their tests once P2's parity tests
  pass on every section; the coverage matrix is an analysis.

## 5. Part F: the read-only feed for Atlas (`aep.bi.analysis_feed/v1`)

Same rules as the telemetry reads (`docs/telemetry/AEP_ATLAS_TELEMETRY_CONTRACT.md` §1 item 2): **GET only,
loopback only, no token, cross-origin allowed only for page origins on this machine** (`127.0.0.1`,
`localhost`, `[::1]`, any port); any other `Origin` is refused (403). Every other Agent Web route keeps its
token. Base: `http://127.0.0.1:<agent web port>/api/v1/bi`. Responses are JSON (`application/json;
charset=utf-8`), at most 8 MiB; errors are `{"ok": false, "code", "message"}` with 400/404/409.

| Route | Answer |
|---|---|
| `GET /health` | `{"format": "aep.bi.analysis_feed/v1", "ok": true}` |
| `GET /vaults` | `{"vaults": [{"id", "dataset", "title", "purpose", "schema", "reads": {"tag": str\|null, "commit": str}}]}` |
| `GET /vaults/{id}/analyses` | `{"vault": id, "version": {"tag", "commit"}, "order": [slug], "analyses": [{"slug", "title", "question", "kind", "chart": {"type", "x"?, "y"?, "series"?}, "params": {...}, "requires": {...}, "digest"}]}` — the **published** version's analyses (what the Agent reads) |
| `GET /vaults/{id}/analyses/{slug}/result?<param>=<value>...` | `{"slug", "digest", "version": {"tag", "commit"}, "params": {...}, "columns": [str], "rows": [[...]], "truncated": bool, "computed_at"}`; `409 result_not_ready` for a script result not computed yet (see below); `400 param_invalid` |

- **Enum choices**: in `/analyses`, every `enum` parameter carries `params.<name>.values` — the allowed
  choices (strings) resolved by AEP, next to the `values_from` they came from. Atlas offers exactly these and
  never resolves `values_from` itself.
- **Only the published version** is served (the Agent's version); unpushed work never leaves Agent Web.
- **No code runs because of a feed request**: SQL results and script results are computed by AEP — on
  publish, on sync when the published version changes, and when the person runs an analysis in Agent Web — and
  cached by `(analysis digest, published commit, params)`. A feed request for parameters not yet computed
  answers `409 result_not_ready` and queues the computation (default parameters are always computed). This
  keeps a tokenless GET from starting a script.
- **Chart mapping** (Atlas): `table`→table, `bar`→bar, `line`→line, `scatter`→scatter. Atlas may place panels
  freely and filter or sort in its own transforms; it never writes to AEP and never changes an analysis. A
  column named `level` with `gap`/`warning` values may be shown as badges.
- Versioning: additive keys only within v1; a breaking change is `aep.bi.analysis_feed/v2` on a new path.

## 6. Integration testing (AEP ↔ Atlas)

1. **Golden fixtures (AEP, written first).** `scripts/bi_feed_fixtures.py` builds a fictional fixture vault
   (`tests/fixtures/bi_feed/vault/`: a few dozen cards, three analyses — one SQL bar, one SQL table with a
   `level` column, one script line chart — one parameter `domain`) and writes the feed answers to
   `tests/fixtures/bi_feed/golden/*.json` (`health`, `vaults`, `analyses`, `result-<slug>[-<params>].json`,
   plus `error-*.json`). `computed_at` and commit ids are fixed in the fixture. AEP's contract test asserts that
   the live routes on the fixture vault return exactly the golden files.
2. **Fixture server (AEP).** `python scripts/bi_feed_server.py --port 53611` serves only the feed routes on
   the fixture vault in a temporary workspace (no model, no token, no other route), for Atlas development and
   end-to-end tests. It prints `ready <url>` when listening.
3. **Atlas consumer tests (Atlas).** Atlas vendors the golden files (`web/tests/fixtures/aep_bi/`) and tests
   its provider and panel mapping against them. A check (`npm run check:aep-bi -- --aep <AEP repo>`) fails when
   the vendored copy differs from AEP's golden files, so a contract change cannot drift silently.
4. **End-to-end (both).** One command from the Atlas repo with `AEP_REPO` set: start the fixture server, start
   Atlas, open the **AEP BI** dashboard headless, and assert: the vault list, every analysis panel rendered with
   the golden numbers, a parameter change refetches, `result_not_ready` shows a waiting state, a stopped AEP
   shows offline with the last data kept, and a request from a non-local `Origin` is refused. Screenshots to
   `.scratch/`. Documented in both repos.
5. **Live acceptance (owner present).** Real Agent Web and a real vault: publish a version in AEP, see Atlas
   update; edit an analysis in AEP with the AI, push and publish, see Atlas show the new chart.

## 7. Tasks and order

Frozen first (this document, §5 and §6.1–6.2 outputs) so both agents can work in parallel.

| ID | Side | Task | Depends on |
|---|---|---|---|
| F1 | AEP | Fixture vault, golden files, `bi_feed_fixtures.py` | — |
| F2 | AEP | Feed routes `/api/v1/bi/*` (loopback, origin rule, published only, result cache, `result_not_ready`) + contract test against golden | F1 |
| F3 | AEP | `bi_feed_server.py` | F2 |
| A1 | Atlas | AEP BI provider (vaults, analyses, results, params, offline/stale, 409 waiting) against vendored golden files | F1 |
| A2 | Atlas | **AEP BI** application: panels from chart specs, parameter controls, `level` badges; drift check | A1 |
| I1 | both | End-to-end test (§6.4) | F3, A2 |
| P1 | AEP | Analysis `params`, `requires`, `meta:dashboard` | — |
| P2 | AEP | Default pack from `dashboard.py`/`market.py` + per-section parity tests; pack import/export | P1 |
| P3 | AEP | Dashboard tab renders analyses | P2 |
| P4 | AEP | `bi__query` reads saved analyses | P2 |
| D1 | AEP | Schema 2.1.0 with `tech_areas`, `chain` | — |
| D2 | AEP | Card `aliases` and name matching from the store | D1 |
| D3 | AEP | Domain migration (dry run, one commit) | D1, D2 |
| P5 | AEP | Remove coded Dashboard sections | P2–P4 |
| D4 | AEP | Remove the domain configuration | D3, P5 |
| I2 | owner | Live acceptance (§6.5); R6 rebuilds `market-bi` on this structure | I1, D4 |

Suggested parallel run (Paseo, one worktree per agent): Claude Code takes F1→F2→F3 first (Codex is unblocked
after F1), then P1→P2→P3/P4, D1→D3, P5, D4. Codex takes A1→A2 against the golden files, then I1 once F3 is
merged. AEP's rule stands: verified commits go to AEP `main` (a worktree branch is merged locally after its
checks pass; no pull requests), and nothing in the Atlas repository is changed by the AEP agent.

## 8. Risks and open points

- **Parity of 31+ sections** is the largest piece (P2). Some sections compute in Python with dates and lists;
  they may need scripts rather than SQL. Parity tests decide; nothing is removed before they pass.
- **Script results without a token**: handled by never running code for a feed request (cache, 409).
- **Atlas dashboards are personal** (layout in Atlas's data folder); the analyses themselves stay in the vault
  so a colleague sees the same numbers in AEP.
- **`market-bi` (V4 format)** is rebuilt at R6 on this structure, not migrated in place.
