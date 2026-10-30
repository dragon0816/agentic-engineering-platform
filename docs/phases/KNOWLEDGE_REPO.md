# Knowledge repositories: one version mechanism for wiki and BI knowledge (design, for owner review)

Owner direction, 2026-10-30. Every AEP knowledge base, wiki (LLM wiki, `src/knowledge/`) and BI (cards,
`src/capabilities/bi_cards/`), is maintained the same way, by one person or by several: **commit, push,
revert, tag/publish**. What differs between the two is only how a knowledge base is *built*: its **schema**
and its **skills**. Both live inside the knowledge base, so whoever maintains it can see which schema
classifies the data and which skill does the work.

This design replaces the BI vault change-file model (`BI_VAULT.md` §3–§4) and the wiki sandbox, push and
publish flow (`KNOWLEDGE_K3.md` §4, `KNOWLEDGE_COLLAB.md` §6) as the way knowledge is updated. What those
documents say about building knowledge (conversion, extraction, section operations, the deletion guard,
benchmarks, quality checks, analyses) stays and becomes the per-type part described in §3.

## 1. Owner decisions (2026-10-30)

| # | Decision |
|---|---|
| 1 | The schema in the repository is authoritative. A PC whose built-in copy of that version differs refuses to open the repository and says why; it never falls back to its own copy. |
| 2 | Written classification rules (today the BI domain `notes`) move into skills; structural configuration (segments, chains, node patterns, aliases) stays configuration. |
| 3 | A skill names the schema version it was written for. A skill whose version differs from the repository's is not run until it is updated. |
| 4 | Every change, a field edit included, goes into the person's working copy first. 「確認匯入」 may commit at once. |
| 5 | Every commit states its purpose (required, one sentence; the system drafts it). |
| 6 | Any maintainer may revert. |
| 7 | Revert writes a new commit that restores a version; history is never deleted or rewritten. |
| 8 | The Agent reads the published version only. A repository never published is read at the maintenance head. |
| 9 | Any maintainer may tag and publish; publishing is one person's confirm click, recorded with who and when. The model never publishes. No permission control (as for BI vaults, 2026-10-29). |
| 10 | Both types move to this mechanism now, wiki and BI (no existing users to keep compatible). |
| 11 | Wiki pages are read from a local, rebuilt, read-only folder that Obsidian can open; edits are made in the working copy and committed. |

## 2. Today and what is replaced

| | Wiki knowledge | BI vault | This design |
|---|---|---|---|
| Personal changes | sandbox: a full copy of the vault | none: 「確認匯入」 writes the shared folder at once | **working copy** for both |
| commit | none | each write is a change file, without a purpose | **commit**: local, purpose required, many changes in one |
| push | three-way merge into the project vault, in place, backups in `.ingest-backup/` | none | **push**: own commits into the maintenance repository |
| revert | roll back to the previous published copy; undo a push from its backup | undo one import | **revert** to any commit or tag, as a new commit |
| tag/publish | publish a merged candidate as a new local version, switch the binding, restart | none (snapshots §9 not tied to versions) | **tag** names a commit; **publish** makes a tag the version the Agent reads |
| Schema, skills in the knowledge base | yes (`CLAUDE.md`, `skills/`) | no (built-in schema, rules in code and `notes`) | yes for both, versioned by commits |

Removed after migration: BI `changes/` and its op format, wiki sandbox copies with `.base`, in-place push
with `.ingest-backup/`, `pushes/` records, and candidate directories `<base>-<version>`.

## 3. A repository = a common skeleton + its type

| Common to every repository | Per type (defined by schema and skills) |
|---|---|
| folder layout (§4), commits, push, revert, tags, publish | **schema**: what the units of knowledge are and what they may hold |
| sources and their Markdown revisions | **skills**: how sources become units |
| working copy, sync, conflicts decided by a person | **unit diff**: what one unit is, so the common engine can merge |
| history, purpose, who and when | **push checks**: what must hold before a push |
| the Agent reads the published version | **reading**: how the Agent and pages use the knowledge |

The two types:

| | `wiki` | `bi` |
|---|---|---|
| Schema file | `schemas/wiki.schema@<ver>.md`: page categories, sections, frontmatter, link and ⚠️ rules (what `CLAUDE.md` holds today) | `schemas/bi.schema__v1.1@<ver>.json` (as today) plus a generated, human-readable `…md` |
| Unit | one `## ` section of one page, and each page's frontmatter field | one field of one card, and each configuration key |
| Operations | `create`, `add_section`, `append_to_section`, `replace_section`, `set_frontmatter` (K3.2), `delete_page` | card create/delete, field set, evidence, proposal, configuration set (the BI ops of today) |
| Skills | ingest skills chosen by source folder (`applies_to`, K3.1) | a classify skill generated from the schema, then extraction skills per domain or source kind |
| Push checks | deletion guard (no sourced line lost) **blocks**; benchmark: a regression **blocks** (owner 2026-10-11) | quality checks (V13) reported as new and resolved findings; not blocking (V13 is read only) |
| Reading | full-text and layered index over the published folder | cards, dashboard, analyses and search over the published database |

The common engine knows only units, operations and checks through one interface per type; it never reads a
card or a page itself.

## 4. The repository folder

```
<shared or local folder>/<repo-id>/
  repo.json                      written once at creation: id, title, purpose, type (wiki | bi), created
  REPO.md                        generated (§9); never the source of truth
  schemas/<id>@<ver>.<json|md>   schema versions, immutable; a BI JSON also gets a generated .md
  skills/<name>/rev-<n>-<author>.md   skill revisions, immutable (§8)
  sources/<folder>/<sha8>-<file name>              originals, immutable
  sources/<folder>/markdown/<sha8>/rev-<n>-<author>.md   their Markdown revisions, immutable
  commits/<author>/<seq>.json    pushed commits (§5)
  tags/<name>.json               tags, immutable (§7)
  publish/<author>/<seq>.json    publish records (§7)
```

- **Only add, never edit another person's file**, as in BI vaults: every file except `REPO.md` is written
  once by its author and never changed. OneDrive sync then cannot overwrite work.
- **Folders under `sources/`** come from the type: BI uses the market chart's application segments and the
  `library/` folders (`BI_VAULT.md` §4); wiki uses its data categories (Market, Productions, Knowledge,
  Competitor). A source's folder selects its skill.
- **A file not referenced by a pushed commit does not exist** for anyone else. A commit that references a
  file OneDrive has not delivered yet waits ("等待同步"); a file whose hash does not match is reported as
  changed and not used.
- **Single person**: the same folder on a local disk. **Several**: the folder in a shared OneDrive or
  SharePoint library set to 「一律保留在此裝置上」. Moving a local repository into a shared folder keeps its
  history.

Per PC, outside the folder, under `<workspace>/knowledge-repos/<repo-id>/`:

- `head`: the maintenance state, rebuilt from the pushed commits (BI `bi.sqlite`; wiki a page folder);
- `published`: the published version, rebuilt the same way (§7);
- `work`: the working copy: the person's local commits not pushed yet and uncommitted changes (BI
  `staging.sqlite` and pending operations; wiki the edited pages);
- indexes, and the position of the last applied commit.

The wiki `head` and `published` folders open in Obsidian. They are read only: AEP rewrites them on every
sync and an edit made there is lost; the page says so and offers to copy such an edit into the working copy.

## 5. Commit

A commit is **local** until pushed (`work/commits/<seq>.json`), in the format it is pushed in:

```json
{
  "format": "aep.knowledge.commit/v1",
  "id": "<sha256 of the canonical commit without id>",
  "repo": "market-bi",
  "author": "leo.chi",
  "seq": 42,
  "clock": 318,
  "base": "<id of the last pushed commit this one was made on>",
  "created": "2026-10-30T14:05:00+08:00",
  "purpose": "加入 2025Q3 AIDC 財報，更新台達的電力鏈供貨關係",
  "kind": "change",
  "schema": "bi.schema/v1.1@2.0.0",
  "files": [{"path": "sources/aidc-power/3f9a1c2b-delta-2025q3.pdf", "sha256": "…", "bytes": 812345}],
  "ops": [{"op": "field", "type": "SupplyLink", "key": "…", "field": "source_date", "value": "2025-11-12",
           "base_version": 3, "evidence": {"file": "…", "rev": 1, "lines": [120, 124], "quote": "…"}}],
  "checks": {"quality": {"new": 0, "resolved": 2}}
}
```

- `kind` is `change`, `import` (a whole existing knowledge base, §11), `revert` (§6) or `schema` (a schema
  version or skill revision made current).
- `purpose` is required, 1 to 500 characters. The commit dialog drafts it from the operations (for example
  "匯入 3 個來源，新增 12 張卡、修改 5 個欄位"); the person edits and confirms.
- The commit dialog shows the diff first: files added, units added, changed (old → new) and removed, skill
  lines changed, schema changes.
- Several commits may be made before a push. A local commit can be dropped before it is pushed; after a
  push only revert undoes it.
- BI 「確認匯入」 writes the import as one commit at once (decision 4); the person only completes the
  purpose. Field edits, configuration saves, Markdown edits and skill edits collect as uncommitted changes
  until the person commits.

## 6. Push, sync and revert

**Order.** Every PC applies pushed commits in one total order, sorted by (clock, author, seq), as BI vaults
do today. A commit's clock is one more than the highest clock its PC had seen, so a commit made after seeing
another sorts after it. A commit that arrives late with an earlier key makes the PC rebuild `head` from all
commits; every PC with the same files has the same state.

**Sync** (any time, and before a push). Apply the commits others pushed. The repository header shows:
behind (others' commits not applied yet), ahead (own local commits), uncommitted changes, open conflicts,
and files waiting for OneDrive.

**Push.**
1. Sync. If others pushed since the person's base, their local commits are merged on top, unit by unit:
   a unit only one side changed is taken; a unit both changed differently is a **conflict**, shown side by
   side and resolved by the person before the push goes on. Resolving writes the chosen values into the
   person's commit.
2. Run the type's push checks on the result (§3). A blocking check stops the push and says why; nothing is
   written.
3. Copy the referenced files into the repository first, then the commit files into `commits/<author>/`.
   A commit is never visible before its files are written.
4. A race that OneDrive reveals later (two pushes within the sync delay) is caught on replay: an operation
   whose base version is not the unit's state at that point is not applied and becomes a pending proposal
   on the unit, shown to everyone, as BI vaults do today. Nothing is dropped silently.

**Revert** (decision 7). The person picks a commit or a tag and gives a purpose. AEP computes the operations
that turn the current head into that version (units, configuration, current schema version and current
skill revisions) and writes them as one `revert` commit with `"restores": "<commit id or tag>"`. It is
pushed like any commit, and can itself be reverted. Sources are never deleted; a reverted state simply no
longer references them. Reverting to a version on an older schema reverts the schema reference too, so
units and schema stay consistent; if the older schema cannot hold units added since, those units are listed
before the revert is confirmed.

## 7. Tag and publish

- **Tag.** `tags/<name>.json`: name (lower-case letters, digits, `.`, `-`), commit id, by, at, purpose. A
  tag never moves; a new state gets a new name (`2026q4-review`, `2026q4-review.1`). Tags are the versions
  people talk about and revert to.
- **Publish** (decision 9). The person picks a tag (publishing an untagged head first asks for a tag name)
  and confirms. AEP writes `publish/<author>/<seq>.json` with the tag, who, when and a clock. The current
  published version is the newest publish record in the commit order. Publishing again an older tag is how
  a bad publication is withdrawn.
- **The Agent reads the published version** (decision 8): each PC rebuilds `published` from the commits up
  to the published tag and serves only that, digest-checked, as Knowledge bindings are served today. A
  repository without a publish record is served at `head`. When a new publish record arrives the PC
  rebuilds `published`; whether the Agent picks it up live or at its next restart follows the binding code
  and is settled in slice R5.
- Read-only snapshots for readers who do not maintain (`BI_VAULT.md` §9) are made from a published tag.

## 8. Schema and skills inside the repository

**Schema** (decision 1).
- Creating a repository writes the chosen schema version into `schemas/`, built in or not, and a `schema`
  commit making it current. A BI JSON schema gets a generated `…md` beside it: types, each field's meaning,
  allowed values, links between types.
- A PC opening the repository installs the schemas it holds. If its built-in copy of the same version has
  different content, the repository does not open and the page says which file differs.
- Upgrading writes a new version file and a `schema` commit naming the version it came from. Session A
  drafts it as today. Skills written for the old version are listed as needing an update.

**Skills** (decisions 2 and 3). One format for both types, `skills/<name>/rev-<n>-<author>.md`, Markdown
with frontmatter as the wiki `SKILL.md` files are today:

```markdown
---
name: aidc-supply-chain
revision: 3
schema: bi.schema/v1.1@2.0.0
role: extract            # classify | extract (bi); ingest (wiki)
applies_to: [sources/aidc-computing, sources/aidc-power]
card_types: [SupplyLink, RevenueFact, Account, Ecosystem]
table_recipes: []        # bi only: header patterns mapped to fields, the rule path without a model
---
ODM、電源、散熱、網通製造商是 Account；晶片、晶圓代工、封測、PCB/CCL、光通訊與國際大廠是 Ecosystem。
鏈別由節點名稱中段（L2-PWR-…）判斷，不是欄位。
（examples: quote → expected cards）
```

- A skill revision becomes current through a commit, so it is pushed, merged and reverted with everything
  else. Two people editing the same skill from the same revision is a conflict on push (the unit is the
  skill); the second person sees the other's text before choosing.
- **BI processing**: source → Markdown → the **classify** skill (generated from the schema: which types,
  which domain and segment; editable) → the **extract** skill whose `applies_to` matches the source's folder
  → candidates → review → commit. The fixed evidence rules (V11) stay in code and cannot be edited away.
- **Wiki processing**: as K3.1, the schema plus the ingest skill whose `applies_to` matches the folder.
- A skill whose `schema` differs from the repository's current version is shown as 「需要更新」 and not
  run (decision 3); Session B offers the update.
- The BI domain configuration keeps segments, chains, node patterns and aliases; its `notes` move into the
  domains' extract skills (decision 2).

## 9. REPO.md: what a maintainer reads first

`REPO.md` is generated from the commits, tags and publish records, and rewritten by the PC that pushes or
publishes. It is derived: the same commits give the same text, a lost copy or an OneDrive conflict copy is
harmless and is rewritten at the next push. It holds:

1. Purpose and type (from `repo.json`).
2. **Schema in use**: version, file, its readable `.md`, and where it came from.
3. **Skills in use**: name, revision, role, folders it applies to, schema version, and any 「需要更新」.
4. **Versions**: the published tag, and how many commits the maintenance head is ahead of it; the last five
   commits with purpose, author and date.
5. **How to maintain**: which folder a new source goes into and which skill will read it; to add a field,
   upgrade the schema with Session A, then update the listed skills; to change a rule, edit the skill and
   commit; to share, push; to release, tag and publish; to undo, revert.

The Agent Web page shows the same content live.

## 10. Agent Web

One 「版本」 area on the Knowledge pages of both types:
- the header from §6 (behind, ahead, uncommitted, conflicts, waiting files) with **同步**;
- **Commit** (diff, purpose), **Push**, **History** (commits with purpose, author, date; open one to see its
  diff), **Revert to this version**, **Tag**, **Publish** (confirm click);
- conflicts side by side, choose a side or edit.

The wiki three-step page (Pull data, Ingest data, Testing data) keeps its steps; "push" there becomes commit
and push of this design. The BI 「建立與匯入」 steps keep theirs; 「確認寫入」 becomes the import commit.

## 11. Migration (decision 10: no compatibility kept)

- **BI**: the vault format with `changes/` is replaced. `market-bi` in OneDrive `BI_Knowledge` is rebuilt as
  a repository from its sources: the manager's five knowledge bases go into `sources/` as originals, the
  schema and the skills into the repository, the cards come in through the import path as commits. Done with
  the owner present (it writes the shared folder); the old folder is renamed, not deleted, until the owner
  removes it.
- **Wiki**: an existing wiki folder (for example the `rs-k` copy) is imported as one `import` commit: its
  pages as units, `raw/` and `drop/` originals into `sources/`, `CLAUDE.md` as the first wiki schema
  version, `skills/*/SKILL.md` as first revisions. The owner's real `RS_Knowledge` folder is never written;
  importing a copy of it is a separate owner decision.
- Sandboxes, `.base`, `.ingest-backup/`, `pushes/` and candidate directories are no longer created.

## 12. Slices

| # | Content | Depends on |
|---|---|---|
| R1 | Common version layer: repository folder, commit format, local commits, push with unit merge and conflicts, ordered replay, sync status, revert, tags, publish records. Type-agnostic, tested with a minimal test type. | — |
| R2 | BI type on R1: card, field, evidence, proposal and configuration operations as units; working copy; the import commit; quality checks as push report; schema in the repository with its generated `.md`, the repository's schema authoritative. Replaces BI vault change files. | R1 |
| R3 | Skills in the repository: the format of §8, schema binding and 「需要更新」, the generated classify skill, domain `notes` moved into extract skills, Session B editing a skill revision. | R2 |
| R4 | Wiki type on R1: section and frontmatter units, the wiki schema file, ingest skills, deletion guard and benchmark as blocking push checks, rebuilt read-only `head`/`published` folders. Replaces sandboxes, in-place push and candidate publish. | R1, R3 |
| R5 | Agent reads the published version for both types; `REPO.md` generator; the 「版本」 area on both pages. | R2, R4 |
| R6 | Rebuild `market-bi` with sources, schema and skills (owner present); import a test copy of `rs-k`. | R5 |

Each slice: contract in `docs/CONTRACTS.md`, tests, full verification, a row in `docs/TASKS.md`.

## 13. Acceptance

1. Two maintainers on one shared folder commit different fields of one card (BI) and different sections of
   one page (wiki); both push; both PCs end with both changes and the same `head`.
2. Both change the same field or section: the second push shows one conflict and writes nothing until it is
   resolved.
3. A push that would lose a sourced wiki line, or regress a benchmark question, is blocked; a BI push shows
   its new and resolved quality findings.
4. Revert to a tag gives exactly that tag's state, as a new commit; reverting the revert gives the state
   before it.
5. Publish a tag: the Agent answers from it while the head moves on; a repository never published is
   answered from its head.
6. A skill bound to 2.0.0 is not run after the repository upgrades to 2.1.0 and is listed in `REPO.md`.
7. A PC whose built-in 2.0.0 differs from the repository's file refuses to open it, naming the file.
8. The same procedure works with the folder on a local disk (one person) and in OneDrive (several).
