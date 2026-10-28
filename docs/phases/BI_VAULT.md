# BI vaults: a shared, purpose-built knowledge base

> **Status.** Design for the owner's review, 2026-10-28 (Claude Code). Nothing below is implemented. It
> follows the owner's review of the built BI ingest flow (`docs/phases/BI_INGEST.md`, phases 1–7) and the
> owner's answers of 2026-10-28, recorded in `docs/DECISIONS.md` "2026-10-28 — BI vaults"; the owner's
> answers to §8 are in §8.
>
> **Builds on.** `docs/phases/BI_INGEST.md` (runs, candidates, evidence, review, commit, Sessions A and B),
> `docs/CONTRACTS.md` "BI cards API and capability", "BI dataset sharing", and the existing `bi__query` tool.

## 1. Goal

A **vault** is a knowledge base with one stated purpose. The first one: see market needs and signals,
link them to our products, and check whether what sales is doing with customers follows the market. A team
of maintainers designs the vault's schema and extraction Skill, brings in sources, and improves it together
with AI help. The AEP Agent finds the vault by its purpose and reasons from what the vault holds.

The owner's processing chain, which the page must show step by step:

```
original file ──convert──▶ Markdown ──schema + extraction Skill──▶ cards
                                                                   + search index
                                                                   + the original file and its Markdown
```

## 2. What the owner found missing (review of 2026-10-28)

| Owner's finding | Cause | Fix here |
|---|---|---|
| Datasets cannot be chosen, imported or created as a vault; demo looks like the only one | The dataset picker sits in the BI bar, not in the build flow; demo is preselected; no import | Step 1 「知識庫」: choose, create or join a vault (§7.1); demo is one entry |
| No convert-to-Markdown step; no search index | Tables went to the rule path and text to the model directly; search scans the cards | Every source becomes Markdown first, kept and editable (§5); a real index (§6) |
| No AI session for the schema | Session A existed only inside an opened draft | Session A is always visible in the schema step (§7.1) |
| The extraction Skill cannot be chosen or adjusted | Called 「方法」, empty list until one is made, Session B hidden until then | Named 「擷取 Skill」, two built-ins always listed, Session B always visible (§7.1) |
| A card shows nothing meaningful | The list shows type, name, key and a field count only | Later, from the owner's ideas (§8.2, V7) |
| What is 「匯入 CSV」 for | The 2026-10-21 import, now duplicated by 「建立與匯入」 | Removed (§7.1) |

## 3. Collaboration: change files in a shared folder (owner's choice, option 1)

**Constraint.** No VM can be had. The shared PC 172.25.228.141 is reachable only on the office LAN (its
Wi-Fi reaches the internet, but company VPN users cannot reach it), so it cannot be the server everyone
writes to. A SQLite file synced by OneDrive breaks when two machines write it.

**Design.** The truth of a vault is a **shared folder** (a Teams/SharePoint library or a shared OneDrive
folder, synced by the OneDrive client on each maintainer's PC). Each maintainer only ever **adds new files
of their own**; nobody edits a file another person wrote. Each PC keeps its own SQLite **built from the
folder**, so no database file is ever synced.

- A write (「確認匯入」, a person's field edit, accepting a proposal, undo) becomes one **change file**
  `changes/<author>/<seq>.json`: the author, a per-author sequence number, a Lamport clock (one more than
  the highest clock the author's PC had seen), the run id, and per card and field the new value, its
  provenance and evidence, and the **base version** it was made from.
- Every PC applies change files in one total order, sorted by (clock, author, seq). A change made after
  seeing another always sorts after it; a file that arrives late with an earlier key makes the PC rebuild
  its SQLite from all change files, so every PC that has the same files has the same cards.
- **Conflicts.** A field change whose base version is not the field's state at that point in the order is
  not applied; it becomes a pending proposal on the card, shown to everyone, decided by a person (the same
  `human_kept` proposal review that exists). Two cards created with the same type and key become one card
  with a merge prompt. Nothing is dropped silently.
- The commit key stays the run id, so a run written twice is applied once.
- Unchanged: trial runs, candidates, review and Sessions A and B stay local (`staging.sqlite` per PC); only
  the result of 「確認匯入」 is shared.

Costs, stated: changes reach others when OneDrive syncs (seconds to minutes), and conflicts are found after
the fact, not prevented. The folder must be set to 「一律保留在此裝置上」 or OneDrive syncs only placeholders.

**141's role** (optional, in the office only): keep the folder synced and running, rebuild and check it,
back it up daily and publish read-only snapshots (§9). The vault works without it.

**Later.** If IT ever makes a server reachable to the team, the change files load into one central
database unchanged; nothing built here is thrown away.

## 4. The vault folder

```
<shared folder>/<vault-id>/
  VAULT.md                    purpose, when the Agent should use it, folders, how to maintain it (for people
                              and the Agent)
  vault.json                  machine-readable: id, title, purpose, schema ref, folders, the coverage matrix
  schemas/<id>@<ver>.json     published schema versions (immutable)
  skills/<name>/rev-<n>-<author>.json   extraction Skill revisions (immutable)
  applications/<segment>/sources/       sources for one market segment (11 folders, from the owner's chart)
  library/products/sources/             our products and options
  library/competitors/sources/          competitors and their products
  library/technologies/sources/         technical background
  <folder>/sources/<sha8>-<file name>   the original, never changed
  <folder>/markdown/<sha8>/rev-<n>-<author>.md   its Markdown, each edit a new revision (§5)
  changes/<author>/<seq>.json            every write (§3)
```

Per PC, outside the shared folder: `<workspace>/bi/vaults/<vault-id>/` holds `bi.sqlite` (cards, evidence,
history, index) rebuilt from the folder, `staging.sqlite`, and the position of the last applied change.

**Cards are stored once per vault**, never per folder: a competitor that matters to three segments is one
card with three segment values. A folder's view lists the cards whose fields name it (§6.2). A source's
folder pre-fills the segment of the candidates made from it; the reviewer confirms it.

Existing local datasets (including demo) keep working as they are. 「把資料集轉成 vault」 writes one
initial change file holding every card with its provenance and history.

## 5. Convert to Markdown, then extract

Every source is converted once, the Markdown is kept beside the original, shown in the page and editable.

| Source | Markdown | Extraction default |
|---|---|---|
| CSV, TSV, Excel | One Markdown table per sheet or table | 「表格規則」 (no model; the existing rule path and recipes read the tables) |
| PDF (text layer), Word, PowerPoint | Headings, paragraphs and tables in order (the `office` extra: pypdf, python-docx, python-pptx) | 「AI 擷取」 |
| Markdown, text | As is | 「AI 擷取」 |

- A scanned PDF without a text layer is refused with a clear message (no OCR).
- Editing the Markdown saves a new revision; the original is never changed. A run records the revision it
  read, and evidence line numbers point into that revision.
- A person may switch a table to 「AI 擷取」 (owner, 2026-10-28: tables follow the recommendation).

## 6. Search index and coverage

### 6.1 Index

A SQLite FTS5 index with the `trigram` tokenizer (works for Chinese without a word splitter; checked on
SQLite 3.53.1) over card names and field values and over Markdown chunks with their file and lines. It is
rebuilt from the folder like the cards. The result step and the vault header show its state: cards and
chunks indexed, last rebuilt, behind by N changes. `bi__query` and the cards page search use it. No vector
search is claimed.

### 6.2 The coverage matrix (from the owner's chart)

`vault.json` defines the matrix once: 5 markets with 11 segments (Cell Phone, AP/CPE, Module/IoT, AIDC
Computing, AIDC Power, Car/eBus electronics, Robotics/AMR, Space Satellite, UAV, Radar/EW, OSAT), 5
technology areas (Wireless & Comm., RF, High Speed I/O, Power/Generic IO, EMC), the priority cells, and the
BDM or TM who owns each row and column. Session A can draft it from the chart.

The vault's schema (a local `bi.schema/v1.1` superset) adds two multi-value fields to the relevant types:
`segments` (the 11 values) and `tech_areas` (the 5). Candidates get `segments` from the source's folder and
`tech_areas` from the extraction with evidence; existing cards are back-filled by a normal run, reviewed and
committed. Application cards stay finer-grained use cases inside a segment.

A read-only **coverage API** returns, per cell and card type: card count, share of fields with a source,
newest update, and fields still empty. The BI Dashboard shows the matrix like the owner's chart; a cell
opens its cards.

### 6.3 Personal dashboards in Atlas

AEP supplies the data; each person's own dashboards live in Atlas
(`C:/Users/Chi_L/Documents/claude/atlas-analysis-dashboard`), reading the coverage API as a REST source.
Later, an AI session in AEP writes an Atlas dashboard definition (declarative JSON, validated, no code
run). The BI Dashboard gets an 「在 Atlas 開啟」 button; the Atlas address is a per-browser preference next
to it (default `http://127.0.0.1:8127`; each person runs their own Atlas, so it is not a Host setting), and
the button says so when Atlas is not running. Atlas still needs its own
browser acceptance before it is relied on.

## 7. Pages

### 7.1 「建立與匯入」 becomes

1. **知識庫**: choose a vault or dataset, create a vault (title, purpose, shared folder path, schema), or
   join one by pointing at its folder. Demo is one entry, not the default.
2. **來源與轉檔**: add files to a folder of the vault; each is converted and its Markdown shown, editable.
3. **Schema**: the current version and upgrade on top; **Session A always visible** below. The first
   message makes a draft from the current version.
4. **擷取 Skill**: built-ins 「AI 擷取」 and 「表格規則」 always listed; saved Skills with revisions;
   **Session B always visible**; applying its first suggestion to a built-in saves a copy. Trial and compare.
5. **逐卡審核**, 6. **確認寫入** (writes a change file for a vault), 7. **結果**: cards written, index state,
   the originals and their Markdown.

The 「匯入 CSV」 tab is removed.

### 7.2 Cards

Waits for the owner's ideas (§8.2). Proposed so far: each list row shows a one-line point (summary,
so-what or one-liner by type) and two or three key fields; the detail shows the point, key fields, related
cards as links, the evidence with quotes, then empty fields.

## 8. Owner answers (2026-10-28)

1. **Shared folder: SharePoint**, where RS_Knowledge already lives, synced by the OneDrive client. The vault
   path is a setting; tests use temporary folders. Writing into the real SharePoint folder follows the
   standing rule: only with the owner present, after a backup and the owner's confirmation.
2. **Cards: unchanged for now.** The owner will bring ideas later; V7 waits for them.
3. **`segments`** (UI: 「應用領域」) is accepted.

## 9. Agent use and sharing

- `VAULT.md` and `vault.json` state the purpose; `bi__query` lists the vaults on this PC with their purpose,
  so the `engineering/bi-knowledge` Skill picks the vault that fits the question.
- Readers who do not maintain can join the folder or subscribe to a snapshot. **Gap fixed here:** snapshots
  carry cards, history and the schema but not evidence; they will carry evidence, and link to the originals
  and Markdown in the shared folder rather than packing the files.

## 10. Permissions: last (owner, 2026-10-28)

No new permission or per-folder classification until the end, so nothing gets in the way of testing. The
existing rule stays: a source goes to the model only in a data class Settings approves; for testing the
owner adds INTERNAL to the approval in Settings (no code change).

## 11. Phases

| # | Content | Depends on |
|---|---|---|
| V1 | Page fixes: Session A and B always visible, 「擷取 Skill」 with built-ins, remove 「匯入 CSV」, Atlas button. **Done 2026-10-28** | — |
| V2 | Convert to Markdown with editable revisions; extraction reads the Markdown | — |
| V3 | FTS5 index and its status | V2 |
| V4 | Vault folder, create/join, change files, ordered replay, conflicts as proposals, dataset-to-vault | V2 |
| V5 | `segments`/`tech_areas`, coverage API, matrix on the Dashboard | V4 |
| V6 | `bi__query` finds vaults by purpose; snapshots carry evidence; 141 as backup and publisher | V4 |
| V7 | Card list and detail redesign | owner §8.2 |
| V8 | Permissions and per-folder classification | last |
