# BI card model: stable ids, relations, profiles, ingest-only edits

Status: design, 2026-11-03, by Claude Code (worker D) from the owner's decisions relayed by the BI orchestrator. **No code yet.** Source:
`docs/proposals/AEP_BI_Card_Database_Proposal.md` v1.2. Where the proposal and the owner's decisions differ, the decisions win. Decision record:
`docs/DECISIONS.md` 2026-11-03 "The BI card model".

Deadline: Phase 1 merged **Wed 2026-11-04 about noon**, R6 that afternoon, release Thu 21:00. So this is the smallest Phase 1 that meets the decisions. §9 says what goes first if it runs long, §8 what runs in parallel.

## 1. Terms

| Word | Means | Where it lives |
|---|---|---|
| **domain** | A coarse label on a card: `wireless`, `AIDC`, `robotics`, `mobile`, `aerospace`. A card may hold several | The `domain` field; the allowed values in the schema's `domains` |
| **application (folder)** | A market data folder, the owner's 「application」: one expert's sources, skills, tools and profile. Code name `application`; the id is a folder name | `applications/<application>/`; the list is the vault's `meta:vault_segments` (today's `sources/applications/<segment>`) |
| **`Application` (card type)** | A finer-grained use case, as a card. **Not a folder.** Always written with the capital and backticks | One of the 21 types. The link field `applications` points at these cards, not at folders |
| **`segment` (field)** | A fact about an entity. Its enum holds 5 chain values and the 11 market segments, on 4 types | A list field. Not used to place a card in a folder |

A vault names its own application list at creation, so **the list is data**. **Owner, 2026-11-04: the default is `aidc`, `aerospace`, `robotics`, `wireless`** (wireless module and wireless example both go in `wireless`); the 11 segments stay as `segment` values on cards. No card page names one of the 11, so sorting pages into them would have been by hand.

A card belongs to the applications whose sources gave it evidence. This is **derived** at rebuild (evidence → `source:` unit → path) into `card_app_folders`, so it needs no unit and cannot conflict. A card with no evidence belongs to none.

## 2. Inventory: 現況 → 提案 → 修改點

| Topic | 現況 (read 2026-11-03) | 提案 and decision | 修改點 |
|---|---|---|---|
| Card id | `vault.card_id_for(type, key)`: 12 hex of a hash, same on every PC. `units_from_db` **recomputes it from the key on every capture**, so a new key would be a new card | D1: hash at first creation, then fixed | §3.1. `units_from_db` keeps the id of a known card |
| Rename | None | D1: an op, old name becomes an alias | §3.1 |
| Links | Field values hold names; `importer` warns `link_missing`; `quality` reports unresolved | D1: stored by id | §3.2 |
| Authority | Commit units; `bi.sqlite` rebuilt from them. **Already D2** | §7's card files as authority is dropped | None. `cards`, `fields` keep their shape |
| Relations | None; `service` reads link fields | D3, proposal §5, §6 minus `file_path` | §3.3 |
| Editing | `POST /api/bi/cards/<id>/field` | D4: retired | §5 |
| Re-run | A run commits candidates of one source; no compare across a scope | D4 | §5.3 |
| Card file | None; card pages are only an import source | D5: generated, read-only | §6 |
| Folders | `schemas/ skills/ sources/applications/<segment>/ sources/library/` | D6 | §4. Engine `FILE_AREAS`, `path_problem`, `withdraw`, `readme`, `skills.py`'s path pattern |
| Published | A rebuilt copy per PC in `<local>/published/` | D6: plus a snapshot in the folder | §6.2 |
| Profile | None. Skills carry `applies_to` | D7 | §4.2 |
| Summary | `summary` on 2 types of 21, `usage` and `scope` on none. `body` on all | D8 | §3.6 |
| Missing values | `schema.EMPTY` turns `n/a`, `tbd`, `待定` into nothing | D9 | §3.4 |
| References | `evidence`: source, locator, excerpt, basis, at | D9 | §3.5 |
| Time | `updated` on 16 types, `source_date` on 2, `date` on 2; `cards.created`, `cards.updated` | D9: only what is missing | §3.6 |
| `priority` | Never stored; the importer warns (`manifest.py`, #222) | D9: as is | None |
| Permissions | None in AEP | D10: drop the proposal's ACL and workspace items | None |
| Feed, Atlas | Goldens pinned to `bi.schema/v1.1@2.0.0`, fixture vault in the old layout | D2: must not change | Proof in §11 |

Non-vault datasets (local `bi/datasets`) have no units. They get the new tables empty, and the retired route is gone for them too. Everything else here is vault only.

## 3. Storage shape (frozen once T1 lands; Phases 2 and 3 build on this)

New unit prefixes on `BiType`; an old unit stays valid and is never rewritten:

```
card:<id>                    + "former_keys": [..]            (optional)
field:<id>:<field>           "value" items may be {"card": <id>, "name": <name at write>}
state:<id>:<field>           {"state", "reason", "raw", "ref", "by", "at"}; null clears
evidence:<id>:<field>        rows gain "reference_id", "stance", "reference_at", "reference_time_basis"
relation:<rel id>            {"from", "type", "to", "origin", "status", "scope", "note", "by", "at"}
relation_evidence:<link id>  {"relation", "basis_card", "reference_id", "stance", "assessment", "by", "at"}
profile:<application>        {"revision", "author", "path", "sha256", "schema"}
skill:<application>/<name>   as skill:<name>; the old form stays readable
tool:<application>/<name>    {"revision", "author", "path", "sha256"}
```

New tables in `bi.sqlite`, all rebuilt from units:

```sql
relations(relation_id PK, from_card_id, relation_type, to_card_id, status, origin,
          source_field, scope, note, by, at)                 -- indexes on from and on to
relation_evidence(evidence_link_id PK, relation_id, basis_card_id, reference_id, stance,
                  assessment, by, at)                        -- assessment: JSON, for Phase 2
field_states(card_id, field, state, reason, raw, origin, ref, by, at, PK(card_id, field))
card_names(card_id, name, kind)                              -- kind: former | alias
card_app_folders(card_id, application, PK(card_id, application))
-- evidence gains: reference_id, stance, reference_at, reference_time_basis
```

The rebuild starts from nothing, so no SQL migration. `PRAGMA user_version` (`card_model.MODEL_VERSION`) makes an older `bi.sqlite` of a vault rebuild once when a `BiStore` opens it, and the published copy's marker holds it too. Not in `meta`: every `meta` row is a unit. **A lane that changes what a rebuild produces raises `MODEL_VERSION`.** A non-vault dataset that was never written since keeps its old tables, so a reader of a new table on one uses `_tables`-style guarding.

`capabilities/bi_cards/card_model.py` holds the prefixes, allowed values and id functions; use them, never compute these ids elsewhere. `tests/test_bi_card_model_shape.py` pins the hashes.

### 3.1 Stable id and rename (D1)

- `card_id_for` stays for **creation only**. A card already in the units keeps its id.
- `POST /api/bi/cards/<id>/rename {dataset, name, base_version, reason}` runs through `capture`: the card's `key` and `name` change, the old key joins `former_keys`, and the naming field is updated. Nothing else is touched, because links are by id (§3.2).
- `names.py` also resolves `former_keys`, so an import of the old name lands on the same card, on every PC.
- A former name stays reserved. A new card with that name would hash to the same id, so it **is** that card. If another entity really has the name, it needs a different one. Rejected: a salted id, since two PCs would then disagree.
- Rename to a taken name is refused. Two PCs doing it at once (rename X→Y, create Y) both reach the folder, so `materialize` is deterministic: the card created first keeps the key, and the other shows as `<key>#<id>` with a `key_conflict` quality item until a person renames it. `check` also blocks this at push when it is visible.
- Like an alias today, a former name resolves across types in `names.canon`: a row of another type with exactly that name takes the new name. It shows in the preview. Rare; left as aliases behave.
- `Signal` and `VisitLog` are named by `date` and `title`: rename takes the key's fields.

### 3.2 Links by id (D1)

Stored by id; shown as names, so `fields` and `card_values`, the 31 analyses and the feed see what they always did.

- **At capture**, a link value that changed goes name → `{"card", "name"}` if exactly one card of its `link_to` types answers it, by name, alias or former key. Otherwise it stays text, as today. An unchanged value keeps its unit, so a capture never makes a false diff.
- **At materialize**, `{"card"}` renders the card's current name, or the stored `name` if the card is gone. Text renders as written, even when it resolves through an alias: a resolved rendering would change feed goldens and old analyses.
- **Only under a schema of this model** (one with `relation_types`, 5.0.0 and later). A vault on an older schema keeps writing text: the feed's fixture vault, pinned to 2.0.0, must rebuild byte for byte. An upgrade starts it, for values that change.
- So a rename touches one card's units and no other's, and creates no conflicts on cards linking to it.
- History, proposals and the conflict page must render these items too. This is the likeliest place for a bug, so it has its own tests.

### 3.3 Relations (D3)

- **Derived (`schema_field`):** at materialize, one row per link item that resolves. Type is the field's `relation_type`, default `has_<field>`, so `supplier` → `has_supplier` and the 82 link fields need no listing. Status `unreviewed`; never blocks use. Rebuildable; not a unit.
- **Units:** `ai_inferred` and `registered`. Types must be in the merged schema's new `relation_types` (from/to types, label). `relation_id` = hash of (from, type, to), so two PCs get the same id. Evidence is a separate unit so that adding evidence never conflicts with a status change.
- **Status:** `unreviewed` (derived only), `inferred`, `confirmed`, `disputed`, `rejected`, `pending`. A `relation:<id>` with the id of a derived row overrides its status (Phase 2's review UI).
- **Review, Phase 1:** only AI-inferred relations are reviewed item by item, in the run's existing review. Only a decided one is written: `confirmed` or `rejected`, so a re-run does not ask again. Undecided ones stay with the run.

### 3.4 Missing values (D9)

`field_states`, separate from the value; `fields` never holds a sentinel.

| Importer reads | State | Kept |
|---|---|---|
| `n/a`, `na` | `not_applicable` | `raw` |
| `tbd`, `待定` | `pending_confirmation` | `raw` |
| `""`, `nan`, `none`, `null`, `-`, `—` | none (reads as `unknown`) | |

`Registry.normalize` is unchanged. A new `missing_state(text)` is called by `importer`, `page_import` and `recipes` before it, and `PlannedRow` gains `states`.

- If the card already has a value and the row says `n/a`, the value stays and the preview lists it. A later value clears a state.
- `not_applicable` is also **computed** at rebuild (`origin: profile`): no value, no explicit state, and every application the card belongs to has a profile that does not use the field. A card in no application is never computed, so it reads `unknown`.
- `pending_confirmation` is also computed from a pending proposal, whose value is the candidate.
- `confirmed_none` comes only from a correction note (§5.2), so it has evidence. An empty list never implies it.
- `bi__query` card output gains `field_states`, so the model can tell 未知 from 不適用. This adds a key to the contract.

### 3.5 References (D9)

`reference_id` = hash of (source id, locator), stable across PCs and unchanged when a withdrawal blanks an excerpt. Old rows get it at rebuild. `stance`: `supports` (default), `refutes`, `context_only`. `reference_at` is the source's date, else the evidence time with `reference_time_basis: submission_fallback`. Phase 1 has the model set `stance` and shows it; correcting it is Phase 2's UI.

### 3.6 Schema 5.0.0

Generated by `scripts/build_bi_schema_v5.py`, additions only, so an upgrade is in place:

- `summary` on the 19 types without it; `usage`, `scope` on all 21 (judgement). AI text is `basis: inference`; `unknown` writes nothing.
- `last_confirmed` (derived, later date stays) and `review_due` on all 21. No generic `event_date`.
- Optional `relation_type` on a link field; top-level `relation_types`.
- Per field `used_by: [applications]`, written by the merge in §4.3.

A missing summary is a warning with counts at publish, never a block.

## 4. Folder layout (D6)

```
<vault>/repo.json, REPO.md
  schemas/<id>@<ver>.json|md
  cards/<stable-id>.md, cards/_manifest.json        generated, §6.1; not in any commit
  applications/<application>/sources/, skills/<name>/rev-<n>-<author>.md,
                             tools/<name>/rev-<n>-<author>.<ext>, profile/rev-<n>-<author>.json
  library/<products|technologies|competitors>/{sources/, skills/, tools/, profile/}   same shape as an application
  library/skills/<name>/rev-<n>-<author>.md         generated classify skill: it spans everything
  commits/, tags/, publish/, published/<tag>.sqlite
```

**Library entries have an application's shape (owner, 2026-11-04):** product specs and options under `products`, technology knowledge under `technologies`. The entry list is data, like the application list. Cards still go only in `cards/<stable-id>.md`, wherever their source lies.

`classify` spans everything, so it stays at `library/skills/`. No path collides, because an entry's skills are one level deeper, provided **`skills` is refused as an entry name**.

**A "home"** is `applications/<id>` or `library/<entry>`; the code handles both alike. Unit keys and `card_app_folders.application` use its **short form, `<id>` or `library/<entry>`**, so an application that happens to be called `products` cannot collide with the entry: `profile:library/products`, `skill:library/products/<name>`, `tool:library/products/<name>`. `not_applicable` is computed from a card's homes' profiles the same way.

- The engine's areas become per type: `path_problem` takes the type's areas, `withdraw` and `readme` ask it what a source path is. **The wiki type keeps `schemas`, `skills`, `sources`, and nothing else in it changes.**
- Old paths stay readable: commits are immutable and name their paths. New writes use the new layout; `checked_folder` accepts `applications/<id>/sources` and `library/<entry>/sources`. The feed's fixture vault proves old vaults still load.
- Tools in Phase 1: stored by the existing file mechanics, listed, **never run**.

### 4.2 Profile (D7)

`applications/<application>/profile/rev-<n>-<author>.json`, immutable, current revision in `profile:<application>`:

```json
{"format": "aep.bi.profile/v1", "application": "aidc", "revision": 1, "schema": "bi.schema/v1.1@5.0.0",
 "types": {"SupplyLink": {"category": "the expert's explanation of this type here",
                          "fields": {"supplier": {"use": "required", "note": "…"},
                                     "source_date": {"use": "optional"}}}},
 "proposals": [{"type": "SupplyLink", "field": "…", "definition": {}, "reason": "…", "status": "proposed"}]}
```

A type or field not listed is not used there. A definition (kind, enum) in a profile is refused, except inside a proposal.

- **Ingest:** `extract` shows the model only the profile's types and fields, with notes and category explanations. Validation stays against the merged schema, so a value outside the profile but in the schema is a candidate marked `outside_profile`, not dropped. No profile: the whole schema, as today, with a notice.
- **Required in a profile** is a warning in the review and at publish; only the schema's `required` refuses.
- **Review:** the category explanation shows beside the candidates.
- Seed and page imports do not read the profile, except for computing `not_applicable`.

### 4.3 A new field (D7)

Profile proposal → reviewed → merged into a new schema version with `used_by`. A new name is compatible and merges by the reviewer's confirmation, with no second step. The same name with another definition stops as `schema_conflict` for a person. It reuses `schema_versions` drafts, diff and upgrade. Two PCs merging at once conflict on the `schema` unit, as any two schema changes do today.

## 5. Editing (D4)

### 5.1 What is retired

The route goes (404 `route_unknown`). **`store.set_field` stays as an internal method**: proposal accept and the domain migration need it, and tests use it for set-up.

| Caller | Today | After |
|---|---|---|
| `bi_cards_api.py:455` route → `_set_field` (858) | Person's edit | **Removed** |
| `web_page.py:12667`, `biEditField` 12674–12725, `stale_edit` message | 「編輯」 button | Becomes 「提更正單」 (§5.2) |
| `bi_cards_api.py:770` `_decide_proposal` accept → `_set_field` | Writes the proposal's value as `human`, enforces `reason_required`, `stale_edit` | **Kept**: review is confirming a sourced difference. Stays on a private helper |
| `migrate.py:266,272` `store.set_field` | Aliases and chain, in a person-confirmed migration | **Kept**, internal |
| `runs.py:600–625` edit of a candidate in review | Marks `basis: human`, keeps `edits` | **Kept**: it is inside ingest. CONTRACTS line 4173 stops saying "as `/field`" |
| `bi_cards_tools`, chat | No field-write path | Nothing |

**History and reason:** the `history.reason` and `old_source` columns stay, as does the `history` part of a `field:` unit (`vault.py:259,403,518`), so old commits replay. `reason` is now filled by proposal accept, correction notes, rename and migration. `reason_required` for judgement fields moves with accept and to correction notes. A confirmed re-run needs no typed reason: its evidence and skill revision are the reason.

**`trusted` depends on this:** `service.trusted` needs `confidence: verified` of kind `human`. A correction note writes kind `human`, and so does an accept, so a person can still mark a card verified, now with evidence. An import still cannot.

**Tests:** route calls are in `test_bi_cards` (3), `_ui` (1), `test_bi_ingest_runs` (2), `test_bi_schemas` (2), `test_bi_card_page_import`, `test_bi_search_index`, `test_bi_subscriptions`, `test_bi_vault` (1 each); helper `_edit` in `test_bi_vault` (8), `_published` (4), `_sources` (1). (`test_bi_chat_edit`'s `_edit` is about analyses, unaffected.) Tests of the route become one test that it is gone. Tests using it as set-up, including two-author merges, move to the correction note. Their assertions stay.

### 5.2 Correction note (更正單)

The button opens a form: field, new value or state, reason (required), author. It writes a small Markdown source with frontmatter (`card`, `field`, `value` or `state`, `reason`) into the `sources/` of the card's first home, or `library/corrections/sources/` for a card with none, and goes through source → preview → confirm → commit. **Read deterministically, no model** (same reader as `page_import`), so it works with no gateway. Evidence: locator = the key, excerpt = the line, kind `human`. A free-form note with no such frontmatter is an ordinary source for a normal AI ingest.

### 5.3 Re-run and diff

`POST /api/bi/reruns/preview {dataset, application, skill_revision, sources|all}`:

1. Shows the source count first (each costs model calls) and runs the existing extraction, with candidates kept in staging.
2. Compares with the cards. **Only differing values are listed**: card, field, current, new, evidence, skill revision, and whether a person set the current one. Values the same, and values absent from the new result, are not listed: a model that found less must not clear anything.
3. `POST /api/bi/reruns/<id>/confirm {items}` commits only those through `commit_run`, one commit. Nothing else is written, and no proposals are created, so nothing floods the review.

Refused with `cards_changed` if a listed card moved. Seed and page cards have no model, so re-import with the mapping is their path, under the merge table of `BI_CARD_PAGE_IMPORT.md` §4.

## 6. What is written to the shared folder at publish

### 6.1 `cards/<stable-id>.md` (D5): at publish, by the publishing PC

Pure function of (commit, schema): title, attributes with states, summary/usage/scope, references, time, related cards as `[[<id>|name]]` from `relations`; frontmatter with `aliases` so Obsidian's search finds a name, and a sample mark. Never read back.

| Option | For | Against |
|---|---|---|
| **At publish, into `cards/`, only changed files (chosen)** | Keeps the layout; shows what readers read; few writes | `cards/` is the one exception to only-add. Two people publishing at once can leave an OneDrive conflict copy |
| At every push (the orchestrator's suggestion) | Fresher | Shows unpublished content; every author overwrites the same files, so conflict copies are routine, not rare |
| Per tag, `published/<tag>/cards/` | Strictly only-add | About 640 more files for each tag; Obsidian shows every old card; links span versions |

The exception is safe because nothing reads `cards/` back, so a conflict copy cannot change any result, and the next publish fixes the file. Writes are atomic; only files whose hash differs from `_manifest.json` are written (a compare that needs no download of a cloud-only file); removed cards are deleted; the manifest (`tag`, `commit`, `at`, `by`, hashes) is written last. It always renders the version currently published after sync, so a slower publisher cannot put an older view back. A failure does not undo the publish: the status says the view is behind, and the next publish repairs it. Excerpts of a withdrawn source are blank.

### 6.2 `published/<tag>.sqlite` (D6)

Written once with no overwrite (a second publish of the tag keeps the first), and its hash goes in the publish record. **Phase 1 only writes it: readers keep rebuilding from units** (`refresh_published`). Reading it (always via a local copy, never opened in the folder) is on the Phase 3 list; the units stay the truth. This narrows `BI_VAULT.md`'s "no SQLite in OneDrive": the rule was about files several PCs write.

**Known limit:** a withdrawn source's excerpts stay in an old snapshot, as they do in commit files today (`BI_SOURCES_IN_REPOSITORY.md`).

## 7. Migration

No tool rewrites commits, and V4 stays out (runbook).

- **A 4.0.0 vault:** the new code rebuilds `bi.sqlite` once and old units load as they are: text links stay text, evidence gets computed `reference_id`, old paths stay. New writes use the new forms. A person upgrades the schema to 5.0.0 through the existing path.
- **R6:** a new vault, directly in the new shape.
- **Mixed versions:** an older AEP refuses a vault with new units at sync (`unit_problem`). Colleagues joining after R6 need Thursday's release; the runbook says so.

## 8. Tasks

Sizes are estimates, not measured: **S** about 1 h, **M** 2–3 h, **L** 4 h or more. Summed they come to about 25 agent hours, so **one worker cannot make Wednesday noon. It needs 4 lanes.**

| # | Task | Size | Depends | Lane |
|---|---|---|---|---|
| T1 | CONTRACTS for §3–§6; schema 5.0.0 and generator; empty new tables; `BiType` accepts new units; tests pinning the newest version move (list in `.scratch/v4b.py`) | M | | A, **first** |
| T2 | Stable id, `former_keys`, rename, `names.py`, `key_conflict` | M | T1 | A |
| T3 | Links by id, render everywhere | M–L | T2 | A |
| T4 | Relations: derive, units, tables, `relation_types`, run review | M | T3 | A |
| T5 | Field states, `missing_state`, three importers, `bi__query` key | M | T1 | B |
| T6 | References: `reference_id`, `stance`, time | S | T1 | B |
| T7 | Summaries in extraction, `basis`, publish warning | S | T1 | B |
| T8 | Engine areas per type; new layout across `vault_sources`, `vault_skills`, `skills.py`, page; tools stored | M–L | T1 | C |
| T9 | Profile: file, unit, ingest prompt, `outside_profile`, `card_app_folders`, computed `not_applicable` | M | T8, T5 | C |
| T10 | Field proposal → schema merge, `used_by`, conflict | S–M | T9 | C |
| T11 | Retire the route; correction note; move tests | M | T1 | D |
| T12 | Re-run and diff, with page | M | T11, T9 for the profile prompt | D |
| T13 | `cards/*.md`, manifest, snapshot on publish | M | T4 reads `relations` | D |
| T14 | Integrate, dry run, runbook, handoff; then the full suite | M | all | Orchestrator or A |

**Parallel.** T1 first: once merged to the working branch the shape is frozen and all lanes start. Lanes touch mostly different files; `vault.py`, `store.py` and `web_page.py` are shared, at different places, so each lane rebases often and integrates small.

**Phases 2 and 3 start Wed morning from T1's contract, in their own agents, and need no Phase 1 code to design against:**

| Lane | Work | Reads |
|---|---|---|
| P2-a | Per-application tools in ingest: guard + `run_python`, first-run approval per revision with visible code, output only as candidates | `tool:` units, T8 |
| P2-b | Schema fit per item (proposal §8.1) | Profile, T10 |
| P2-c | Evidence review UI | `relation_evidence.assessment`, `stance`, relation override |
| P3-a | Multi-hop retrieval in `bi__query`, passages; reading the snapshot | `relations` indexes |
| P3-b | Benchmark error classes | Independent |

They merge after R6.

### 8.1 Lane briefs

Every lane: base is T1's commit on `bi-card-model`; own worktree and `.venv` (dev,office); own `--basetemp`; targeted tests only, the full suite is the orchestrator's; verify like CI (`ruff format --check .`, `ruff check .`, `mypy src tests`); no push; fixtures fictional, nothing from `files\` in a commit; nothing written under OneDrive. `git diff --stat tests/fixtures/bi_feed` stays empty: run `test_bi_feed_api`, `test_bi_feed_fixtures` before each hand-in. Tests that pin behaviour move, they are not weakened. Add a `docs/TASKS.md` row per task. **A storage shape question goes to lane A, not around it.** If a read of §3 and a read of the code disagree, say so.

- **Lane A (worker D): T2, T3, T4.** `vault.py` `units_from_db` and `materialize` for ids, links and relations; `names.py`; rename route; `service` reads.
- **Lane B: T5, T6, T7.** Read §3.4, §3.5, §3.6.
  - T5: `schema.missing_state`, called in `importer`, `page_import`, `recipes`; `PlannedRow.states`; `store` writes `field_states` with `origin: unit`; `units_from_db` and `materialize` round-trip `state:` units, and compute `origin: proposal`; `bi__query`'s `field_states`. Computing `origin: profile` is T9's.
  - T6: `reference_id`, `stance`, `reference_at`, `reference_time_basis` on evidence rows in `store`, `runs`, `page_import`, and through `units_from_db` and `materialize`; a row with none gets its `reference_id` computed at rebuild. The evidence unit stays unchanged when nothing changed, or every capture diffs.
  - T7: `extract`'s prompt asks for `summary`, `usage`, `scope` with `basis`; `unknown` writes nothing; `vault.publish` returns a warning with per-type counts of cards with no summary; it never blocks.
  - In `vault.py`, touch only the state and evidence branches; lane A owns the card, field and relation ones.
- **Lane C: T8, T9, T10.** Read §1, §4.
  - T8: homes as in §4, library entries included; `repository.path_problem` and `RepoType` get per-type areas; **the wiki type's behaviour is unchanged** (run `test_knowledge_repo*`, and the wiki tests); `withdraw` (`repository.py:691`) and `readme.py:143` ask the type what a source path is. BI: `vault_skills.APPLICATIONS`, `LIBRARY`, `checked_folder`, `domain_folders`, classify text; `skills.py`'s path pattern and `skill:<application>/<name>`; `vault.SEGMENTS` default becomes the owner's four, still data; `_new_vault` folders; the `web_page.py` placeholders at 2750, 2955; tools stored by `stage_file` and a `tool:` unit, never run. Old paths stay readable: `tests/fixtures/bi_feed/vault` is the proof.
  - T9: `profile.py`, file format §4.2, `profile:` units; `extract` filters by it and marks `outside_profile`; `card_app_folders` and `origin: profile` states in `materialize`.
  - T10: §4.3 on `schema_versions`.
  - ADR-K10: the engine and other generic modules must not name BI types; run `test_bi_cards`'s guard and `test_harness_cross_domain`.
- **Lane D: T11, T12, T13.** Read §5, §6.
  - T11: remove the route; `_decide_proposal` accept keeps its checks on a private helper; correction note reader, form and button; move the tests listed in §5.1.
  - T12: §5.3.
  - T13: `card_markdown.py`, pure; hook in `vault.publish`; `published/<tag>.sqlite` and the publish record's hash. Reads `relations`, so an empty table is fine until T4: render with what is there. `repo.publish` lives in the generic engine, so the snapshot's record goes through the type, not a BI name in the engine. Tests write only temp folders.

## 9. Cut first if it runs long

**Never cut: anything that shapes commit files or paths** (T1, ids, link form, relation units, states, references, layout, profile file). R6 fills a shared folder, and changing those afterwards means rebuilding it.

Cut in this order; each leaves the data right and adds later without a rebuild:

1. AI-inferred relations in the extraction prompt and review. Units stay and are tested; R6 then has derived relations only.
2. Rename's page button: API only. R6 does not need it.
3. Field proposal's page: API only.
4. Tools listing on the page. R6 keeps `tools/` out anyway.
5. Re-run over "all sources": explicit list only.
6. `bi__query`'s `field_states` key.
7. T10 whole, with new fields through Session A as today. Fails D7's path until Phase 2, so tell the owner.

## 10. R6 and V1–V7

**R6 runbook (T14):** schema 5.0.0; §3 gives each base its application; step 5 chooses it; a new step before AI extraction, the owner approves a profile for each application doing AI ingest (the two AIDC reports; seeds and pages need none); step 9 (the 28 link spellings) becomes correction notes or added aliases, since field edits are gone; step 12 checks `applications/*/sources`; step 13 checks `published/<tag>.sqlite` and `cards/`, about 640 more OneDrive files; step 16 joins with the new release only.

**V1–V7** (`docs/testing/BI_INTEGRATED_ACCEPTANCE.md`, the orchestrator's to commit):

| Item | Change |
|---|---|
| V1 | #1 expects the new layout; #2–4 choose an application; #6 adds a profile first, candidates only from it, summaries as `inference`; #8 adds the summary warning, snapshot, `cards/`; #9 adds counts of relations, states, resolved links. New: open `cards/` in Obsidian. |
| V2 | #2, #3 use correction notes, not edits: two notes on the same field must still surface as a conflict. #10 adds two publishers on `cards/`. New: rename X→Y while the other PC creates Y; a rename while the other edits a card linking to X, with no conflict. |
| V3 | #2 becomes re-run → only differences → confirm a subset → check the rest are unchanged. #3 goes through a profile proposal, plus a same-name conflict. #5 records tools as stored, not run. |
| V4 | #5 cannot use an edit: create the missing-source record by a CSV import. Option: panels on `field_states`, `relations`. |
| V5 | New: 不適用 vs 未知 answered correctly. #6 may read `relations`. Multi-hop is Phase 3, not here. |
| V6, V7 | No change; that is the point of D2. |

## 11. Tests

Fixtures fictional, committed; nothing from `files\` in a commit.

- **Feed contract:** `test_bi_feed_*` unchanged, `git diff --stat tests/fixtures/bi_feed` empty. Also the Atlas check, as before.
- **Round trip:** `units_from_db(materialize(units)) == units`; a capture with no change stages nothing. Two temp PCs give the same tables.
- **Each decision:** rename keeps id and links, old name re-imports to the same card; concurrent rename and create; derived vs inferred status; states from `n/a`, `tbd`, `待定`; a re-run where the model finds less writes nothing; profile filtering of the prompt; route gone; `trusted` via a correction note; publisher races on `cards/`; old-layout vault loads; wiki repo unchanged.
- **Evidence: combined dry run** (`.scratch/combined.py`, read-only on `files\`, no model, about 4 min). Baseline on 4.0.0: 641 cards, 203 fills, 41 joins, 19 proposals, 0 mark conflicts, 85 synthetic, 78 `SAMPLE-`. Those must hold, or the difference is explained. New counts: states per kind, links by id vs text, derived relations, `.md` files, publish time. Also the 31 analyses on that data, compared before and after.
- **Verify like CI** per lane; full suite and real-model runs only on the orchestrator's go.

## 12. Risks

| Risk | Handling |
|---|---|
| The schedule: 25 agent hours in about 12 clock hours, with heavy machine load already seen | Lanes (§8), cuts (§9). If T1–T4 are not done by Wed 09:00, say so then, not at noon |
| Link rendering missed somewhere (history, conflicts, proposals) shows raw ids | Own tests; the dry run checks no `{"card"` in any shown value |
| New schema pins many tests again | Mechanical, list exists |
| `cards/` adds about 640 OneDrive writes during R6 | Only at publish; report the time; the owner is present |
| Older AEP cannot read the vault | Runbook; Thursday's release |
| A former name stays reserved, so a true namesake needs another name | Rare; stated in the rename reply |
| Phase 1 gets little real-model testing before R6 | The extraction prompt changes (profile, summaries). One small real run on a fictional source, on the orchestrator's go, before merge |
