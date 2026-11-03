# A BI vault's originals in the shared folder

Status: design (S1), 2026-11-02, by Claude Code from the owner's decisions relayed by the BI orchestrator. **Nothing here
is built.** S2 onward starts on the integrated result of `bi-build-flow`, `bi-chat-embed-edit` and `bi-vault-asking`, when
the orchestrator names the base. Decisions: `docs/DECISIONS.md` 2026-11-02 "A BI vault's originals go into the shared
folder" and "Owner's answers on a BI vault's originals". Builds on `docs/phases/KNOWLEDGE_REPO.md` §4, §5, §11. R6 waits
for this (`docs/runbooks/R6_MARKET_BI.md`).

## 1. Owner decisions

| # | Decision |
|---|---|
| D2 | Originals go into the repository's `sources/`, so a colleague who joins can read them |
| O1 | The per-file limit is set after measuring the real sizes. S6 waits for that number |
| O2 | **Every classification may be pushed**, `CONFIDENTIAL` and `RESTRICTED` included. No push refusal by classification. The owner accepts that anyone with folder access can read every original permanently |
| O3 | Build the withdrawal record (§5) |
| O4 | Every PC keeps all originals on the device. The page warns on cloud-only files. No lazy read |

## 2. What exists (read at `a7629341` and `bi-build-flow` `e631f880`)

- The engine carries files: `stage_file`, the commit's `files` (`path`, `sha256`, `bytes`), `_copy_in` writing each file
  before a commit names it, "waiting" until the file is delivered, "changed" on a hash mismatch. The wiki type uses them.
- BI does not. `Staging.add_source` keeps the original at `<dataset dir>/sources/<sha256><ext>` and its Markdown in the local
  `staging.sqlite`. `bi-build-flow`'s B2 copies them into a new vault's local staging on convert.
- Evidence already travels: `runs` writes `excerpt` (up to 500 characters) and `source_id` into evidence units, which are
  pushed in commits. `source_id` is a random id only one PC can resolve.

## 3. Design

**Files and unit.**
- The original: `sources/<folder>/<sha8>-<name>`. Markdown revisions:
  `sources/<folder>/markdown/<sha8>/rev-<n>-<author>.md` (`KNOWLEDGE_REPO.md` §4). Paths stay within `MAX_PATH` (240).
- A new unit `source:<sha256>`: `{name, folder, classification, media_type, bytes, file, markdown: {rev, file}}`, so the
  list, history and revert go through the version layer. Added to `UNIT_PREFIXES`; ignored when the cards database is built.
- The folder is chosen when the source is added, since it selects the skill (`applies_to`); today it is chosen at the AI
  run (decision 2026-10-30).
- The source id is derived from the sha, so evidence means the same on every PC. A vault rebuilt at R6 has no old rows; a
  source `convert` brings is re-identified then.

**Commit and push.** In a vault, adding a source stages its files and unit. They go in **their own commit**, because the
engine makes a whole commit wait for its files: one slow PDF on OneDrive must not hold back a colleague's cards. Size is a
refusal when adding and a blocking push check (limit: O1). `_copy_in` copies by stream instead of holding the file in memory.

**A colleague's PC.** `Staging` gets rows from the `source:` units on sync and reads through to the repository file, with no
second copy. So the source list, Markdown, the search index, AI runs and quality checks work there. Runs, candidates and
sessions stay on the PC that made them.

**Cloud-only files (O4).**
- `_stored_sha` guards only `stat()` and then reads the whole file, so an unreadable file is an uncaught `OSError` that can
  fail a sync, and `bi__query` syncs before answering. An `OSError` while hashing becomes "waiting", with the file named.
- The page warns per source (`st_file_attributes`, as `scripts/r6_precheck.py` does), and says to set
  「一律保留在此裝置上」. It does not avoid the download: reading the file to check it brings it down, as O4 expects.
- CI cannot make real placeholders: tests simulate the read failure, and one check on the owner's PC covers the rest.

**Classification (O2).** Pushed like any other source, and it stays in the unit. The existing check before an AI run
(`check_classification` against `approved_classes`) stays as it is, on every PC, so a colleague's model use is still bound
by it. The add-source page says that the shared folder has no permission control beyond who can open it.

## 4. Tasks

| # | Task | Size | Depends on |
|---|---|---|---|
| S1 | This design and the decisions | small | — |
| S2 | Engine: a file that cannot be read is "waiting"; streamed copy; wiki tests stay green | small | base |
| S3 | `source:` unit, stage on add, own commit, stable id, the size check with its limit configurable | large | S2 |
| S4 | Sync into a colleague's `Staging`, read through, search index | large | S3 |
| S5 | Convert stages the sources too (replaces `bi-build-flow`'s local copy; its design §4 and §10 and its page line change) | small | S3 |
| S6 | Files over about 6 MiB: `/api/bi/sources` takes base64 under an 8 MiB body | medium | O1's number |
| S7 | Page: folder when adding, per-source state (local, pushed, waiting, only in the cloud), wording | medium | S3, S4 |
| S8 | Two-PC browser test, contracts, runbook | medium | S3–S7 |
| S9 | Withdrawal record (§5), engine, BI, page, tests | medium | S3 |

Estimate from reading the code, no prototype. S3 and S4 are where it may grow: many callers read `Staging`.

## 5. Withdrawal (O3)

A file pushed by mistake cannot simply be deleted: files are immutable, commits name them, and a missing file leaves its
commit waiting for good on every PC.

**The record.** `withdrawn/<author>/<seq>.json`, add-only like every other file: `{files: [{path, sha256}], reason, at}`,
one record for the original and its Markdown, each `path` under `sources/` only. BI only in this version: the wiki's `materialize` reads `raw/` files back, and would need its
own answer. The confirmation on the page lists §5.2 before anything happens. Any member can do it, as BI vaults have no
permission control; the record says who.

**What the engine does.**
1. Writes the record first, then deletes the file and its Markdown revisions from the folder. If OneDrive delivers the
   deletion first, the commit waits only until the record arrives.
2. `_files_state` treats a withdrawn path as present, so its commit stays applied and a rebuild still works. The cards
   database does not read source files, so tags and publishing are unaffected.
3. The record decides, with no commit: the `source:<sha>` unit stays in history. Each PC, at its next sync, removes that
   source from `Staging`, its stored original, its Markdown, its search passages and any staged copy under `work/files`.
4. `_copy_in` and `stage_file` refuse a withdrawn path (`source_withdrawn`). This matters: another PC's unpushed commit
   naming the file would otherwise copy it straight back with its push. The same bytes cannot be added again; there is no
   undo in this version, since a withdrawal is for a mistake.

**§5.1 What it removes.** The file and its Markdown from the shared folder, for everyone once OneDrive has delivered the
deletion; the source from AEP on each PC, once AEP has synced there; and from then on it cannot be read or chosen in AEP.

**§5.2 What it does NOT remove.** The page says this before the person confirms.
- **OneDrive's and SharePoint's own copies**: version history and recycle bins. AEP has no reach there. Removing them is
  for whoever administers the site.
- **Another PC's copy, until that PC acts**: AEP's copy goes at its next sync, so a PC that is off keeps it until then;
  OneDrive's local copy goes when OneDrive syncs. AEP cannot confirm either from another PC.
- **Copies outside AEP**: anything downloaded, copied, backed up or mailed. And whatever a model was already sent.
- **What was extracted from it**: cards, field values and evidence `excerpt`s (up to 500 characters) live in commits, in
  the shared folder, and a commit's id is the hash of its content, so they cannot be rewritten. Editing a card adds a later
  change; the older commit still holds the old text.
- **Its name and hash**: the commit's `files` list and the record itself stay in history.

**The owner's answers (2026-11-02).**
- **Q1. Excerpts and values staying in the immutable commits is accepted.** The page names rebuilding the vault from its
  sources without that file, in a new folder, as the way to remove everything AEP can reach.
- **Q2. Candidates not yet written are removed at sync; run records stay with their excerpts blanked.**
- **Q3. Open**: how long SharePoint keeps deleted files and versions on this library, from IT. It depends on the tenant's
  policy, which AEP cannot read, and it does not hold up S9. Until a period is known the page states none:

> 共用資料夾的檔案和 AEP 裡的副本會移除。OneDrive／SharePoint 可能還保留版本紀錄和資源回收筒裡的檔案，保留多久由公司的設定決定，AEP 無法移除；需要完全清除時請找管理這個資料夾的人。

The rest of the page's confirmation is §5.2 in plain words, ending with: 卡片、欄位值和引用的摘錄留在版本紀錄裡；要移除 AEP 能觸及的一切，請不帶這個檔案重建知識庫。

## 6. Risks

- OneDrive may treat a delete and a re-add of the same name as a conflict: the record's refusal covers AEP's own writes, not
  a person copying the file back by hand (an unreferenced file does not exist for anyone).
- Disk use on every PC grows with the vault (O4): the runbook's pre-check gives the total to look at first.
- Pushing is permanent in the sense of §5.2 from the first push. The runbook has the owner check who can open the folder.
