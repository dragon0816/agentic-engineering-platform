# R6: rebuild `market-bi` from raw sources, and import an `rs-k` copy

**Run with the owner present.** It writes the shared OneDrive folder and may restart Agent Web. An agent prepares and
reads; the owner decides at each ☐ below. Records this rests on: `docs/phases/KNOWLEDGE_REPO.md` §11–§12,
`docs/phases/BI_VAULT.md` §12, `docs/phases/BI_BUILD_FLOW.md`, `docs/TASKS.md` 2026-10-29.

**Never:** a tool that migrates the V4 format (owner, 2026-11-02); writing to the real `RS_Knowledge` folder; deleting
the old `market-bi` folder (the owner removes it later, by hand).

## 1. Why

`OneDrive - Rohde & Schwarz\BI_Knowledge\market-bi` is in the V4 format (`changes/`, `vault.json`). AEP neither reads
nor writes it since R2. The repository format needs its sources, schema, skills and cards as commits, so it is rebuilt.

## 2. Decisions

| # | Decision | Why it matters | Status |
|---|---|---|---|
| D1 | **The new vault's id is `market-intel`.** | Creating `market-bi` again is refused on the owner's PC (`vault_exists`): that PC still holds `bi/vault-market-bi` and the registry entry, and there is no route to leave a vault. The id is fixed forever. | Decided (owner, 2026-11-02) |
| D2 | **The originals go into the shared folder; every PC keeps all of them on the device. No size limit.** | **R6 cannot run until this branch is merged and running:** before it, a BI vault's sources stay on the PC that added them. Design: `docs/phases/BI_SOURCES_IN_REPOSITORY.md`. | Decided (owner, 2026-11-02, 2026-11-03) |
| D3 | **Base by base through the page, one commit per base, conflicts settled in review.** The 2026-10-29 one-off merge script (`--fill-only`), which is not in the repository, is not brought back. | It reported 7 scalar conflicts last time; a commit per base can be reverted on its own. | Decided (owner, 2026-11-02). The pages go through the card-page importer (`docs/phases/BI_CARD_PAGE_IMPORT.md`): open points in §3 |
| D4 | **Import `%LOCALAPPDATA%\AEP\rs-k-v1.0.3` (28 MB) as a test copy into `C:\Users\Chi_L\OneDrive - Rohde & Schwarz\Wiki_Knowledge` (exists, empty). Do not bind it to the Agent until the owner has compared answers.** | Binding a second vault changes how questions route (§8). The real `RS_Knowledge` is never written. | Decided (owner, 2026-11-02, 2026-11-03) |
| D5 | **The first tag is `2026q4-r6`.** | Tags never move. | Decided (owner, 2026-11-02) |

## 3. Raw sources

All five bases are under the AEP main checkout, `C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\files\`
(git-ignored, never committed); confirmed by the owner, 2026-11-03. **The owner reviews this list at the session.** It comes
from reading the folders: names and counts, read only.

| Base | Size | Goes in as sources | Stays out |
|---|---|---|---|
| `aidc-bi-kb` (AIDC) | 169 files, 1.2 MB | `BI/` (121 pages, 12 named `SAMPLE-`), `seed/` (24: 22 CSV seeds per the record), `sources/compute.md`, `sources/power_cooling.md`, `README.md` | `tools/` (18), `package.json`, `package-lock.json`, `Dashboard-AIDC.md` |
| `Aerospace-BI-KB` (aerospace) | 101 files, 493 KB | `BI/` without `_Templates/` (51 card pages of 72), `seed/` (22 CSV), `README.md` | `tools/` (5), `BI/_Templates/`, `Dashboard-Aerospace.md` |
| `robotics_kb_sample` (robotics) | 134 files, 586 KB | `BI/` without `_Templates/` (104 card pages of 116), `README.md`, `PATCH-NOTES.md` | all of `tools/`, including its 12 seed CSVs (owner, 2026-11-03), `BI/_Templates/`, `build_sample.py`, `Dashboard-Robotics.md` |
| `Wireless-Module-BI-KB-SAMPLE` (wireless module) | 87 files, 463 KB | `BI/` without `_Templates/` (55 card pages of 77, 47 marked samples), `README.md` | `tools/` (6), `tests/` (3), `BI/_Templates/` |
| `BI_Vault_Example` (wireless example) | 154 files, 2.3 MB | `BI/` without `_Templates/` (103 card pages of 115), `tools/samples/*.csv` (3, sample data), `README.md` | `.obsidian/` (13), the rest of `tools/` (with `__pycache__`, `prompts`), `BI/_Templates/` |

Largest file under 1.4 MB; no PDFs. Reasons for the stays-out column: build tools and tests are not knowledge,
`_Templates/` are Templater templates with no data (`<% tp.file.title %>`), and `Dashboard-*.md` are generated Dataview
pages the vault's Dashboard replaces. `SAMPLE-` pages and `BI_Vault_Example/tools/samples` go in **marked as samples** (owner,
2026-11-03): tick 「全部標成範例資料」 for `tools/samples`, which also names those rows `SAMPLE-`. `tools/name-aliases*.json` (AIDC, aerospace) stay out as files but hold the
name aliases to carry over.

Two AIDC reports: `C:\Users\Chi_L\OneDrive - Rohde & Schwarz\BI_Knowledge\market-bi\applications\aidc-compute.md` and
`aidc-power_cooling.md`. Read only; copy out, never move. Compare them with `aidc-bi-kb/sources/compute.md` and
`power_cooling.md` first, by content: add one copy of each.

Schema: built in, `bi.schema/v1.1@2.0.0` (21 types; `segment` already has the 11 market segments). The old folder
`market-bi` is a reference for a person only: nothing is converted from it by a tool.

**Card pages go through the built-in importer** (owner, 2026-11-03: `docs/phases/BI_CARD_PAGE_IMPORT.md`), 「匯入卡片頁（Obsidian）」 in
step 1. No model. Read-only dry run over the five folders on 2026-11-03, each base alone on the shipped schema; nothing was
written to `files\`:

| Base | Pages → new cards | Skipped, why | Sample-marked | Seed CSV → new cards | Sample-marked |
|---|---|---|---|---|---|
| AIDC | 121 → 121 | — | 12 | 22 card CSVs → 323 | 14 |
| Aerospace | 51 → 51 | 21 templates | 1 | 22 → 91 | 9 |
| Robotics | 104 → 100, 4 with no name | 12 templates | 0 | 12 → 104 (not imported) | **90** |
| Wireless module | 55 → 55 | 21 templates, 1 Dashboard | 47 | none | — |
| Wireless example | 103 → 100, 3 with no name | 11 templates, 7 with no frontmatter | 7 | 3 samples → 9 | 9 (ticked) |

No frontmatter problems in any base. Every base has fields the schema does not hold, listed in the preview and not written:
`ingested_from` (import bookkeeping) and `Application.priority`. `seed/name_aliases_review.csv` and `seed/unresolved_links.csv` in AIDC
are not card files and are listed as such. A full apply of AIDC's 121 pages on a temp vault took 86 s, then 29 s to push: one
commit of sources and one of cards.

**The order (owner, 2026-11-03):**

| Base | Goes in | Stays out |
|---|---|---|
| AIDC | Seeds, then pages | |
| Aerospace | Seeds, then pages | |
| Robotics | Pages only (100 cards) | Its seed CSVs, which mark 90 of 104 as samples |
| Wireless module | Pages | |
| Wireless example | Pages, and its 3 `tools/samples` CSVs with 「全部標成範例資料」 ticked: they get the `SAMPLE-` name, never twice | |

The table above ran each base alone. **Combined dry run** on a temp vault, in this order, with no model and nothing written to `files\`
(2026-11-03). Same-named cards merge: an empty value is filled, a list joined with nothing lost, a differing scalar becomes a proposal for
review, never an overwrite; a value a person set stays theirs (`docs/phases/BI_CARD_PAGE_IMPORT.md` §4):

| Step | New | Merged | Fills | Joins | Proposals | Fields of the proposals |
|---|---|---|---|---|---|---|
| AIDC seeds | 323 | 0 | 0 | 0 | 0 | |
| AIDC pages | 0 | 90 | 90 | 0 | 0 | |
| Aerospace seeds | 86 | 5 | 7 | 3 | 5 | `Ecosystem.role` 2, `Ecosystem.body` 2, `Competitor.body` 1 |
| Aerospace pages | 0 | 44 | 62 | 2 | 12 | `Application.domain` 6, `Trend.domain` 4, `CustomerProduct.domain` 2 |
| Robotics pages | 94 | 6 | 19 | 13 | 2 | `Ecosystem.node` 2 |
| Wireless module pages | 51 | 4 | 3 | 4 | 0 | |
| Wireless example pages | 79 | 13 | 8 | 14 | 11 | `Ecosystem.node` 5, `Ecosystem.role` 4, `Concept.category` 1, `Concept.one_liner` 1 |
| Wireless example samples | 8 | 1 | 2 | 5 | 1 | `Competitor.pricing_position` 1 |

**641 cards** (10/29: 639), 85 marked as samples, 78 named `SAMPLE-`, **31 proposals** (10/29: 7 scalar conflicts). 191 fills and 41 joins with nothing
lost. No card and row disagreed about being a sample. It took about 5 minutes. For the session:

- **12 of the 31 proposals are `domain`**: `Application`, `Trend` and `CustomerProduct` hold one domain each in schema 2.0.0, so a card in two bases asks which. A
  widening of those fields to lists would settle them all (Session A); that is the owner's call, not an import setting.
- 10/29's 7 came from a one-off script with its own rule (lists joined, first name kept), which is not in the repository, so 31 and 7 may not measure the same thing.
- The 2 cards more than 10/29's 639 have not been traced.

The 7 pages with no name (4 robotics, 3 example) are listed in the preview and not imported; name them or leave them.

## 4. Pre-checks a script can run beforehand

Read-only: it only asks whether files exist and how they are named. It opens nothing and writes nothing, so OneDrive
downloads nothing. **The owner runs it, or asks for it to be run, on the real paths**; agents working in temp
workspaces do not.

```powershell
$f = "C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\files"
python scripts/r6_precheck.py `
  --shared "C:\Users\Chi_L\OneDrive - Rohde & Schwarz\BI_Knowledge" `
  --base "$f\BI_Vault_Example" --base "$f\robotics_kb_sample" --base "$f\Aerospace-BI-KB" `
  --base "$f\Wireless-Module-BI-KB-SAMPLE" --base "$f\aidc-bi-kb" `
  --wiki-copy "$env:LOCALAPPDATA\AEP\rs-k-v1.0.3" --real-wiki "<RS_Knowledge, the real folder>" `
  --wiki-target "C:\Users\Chi_L\OneDrive - Rohde & Schwarz\Wiki_Knowledge" `
  --workspace "<AEP workspace>" --vault-id market-intel
```

| Check | Fails when |
|---|---|
| `shared_folder` | The folder is missing |
| `old_vault` | It is not V4: already a repository (R6 may have been done), empty, or unrecognised |
| `old_vault_on_this_pc`, `base:*` | Warns when files are cloud-only: set 「一律保留在此裝置上」 first |
| `rename_target` | `market-bi.v4-old` already exists |
| `vault_id_free` | This PC already holds that id (`--vault-id market-bi` fails here on the owner's PC: D1) |
| `base_count`, `base:*` | Warns on a count other than 5, or a base with no pages, or no seeds and no reports |
| `wiki_copy`, `wiki_copy_is_a_copy`, `wiki_target` | Not a wiki folder; inside the real wiki; target inside the imported folder |

Exit code 0: nothing failed. Do not start on 1.

People with write permission on the SharePoint folder can open what is in it; company IT decides who that is.

Also, by hand: `GET /api/tasks` and `/api/activity` are idle before any
restart; a free afternoon, since the extraction uses real models.

## 5. The session, in order

Agent Web must run code with the build flow (`docs/phases/BI_BUILD_FLOW.md`). Page labels below are as of 2026-11-02;
that flow is changing, so read the current ones on the page.

| # | Step | Checkpoint before going on |
|---|---|---|
| 1 | Run §4. Settle the open points of §3 with the owner and record them in `docs/DECISIONS.md`. | Exit code 0; each recorded |
| 2 | Restart Agent Web if it predates the build flow (check `/api/tasks` first, AGENTS rule 19). | Page shows the build-flow steps |
| 3 | Rename the old folder to `market-bi.v4-old` in Explorer. Wait for OneDrive to finish. | Old folder present under the new name on OneDrive's site; nothing deleted |
| 4 | Knowledge > BI > 建立與匯入 > 建立共用知識庫（vault）: id `market-intel`, in `BI_Knowledge`, schema `bi.schema/v1.1` (2.0.0), author `leo.chi`. | `repo.json` in the folder; `/api/knowledge/askable` lists it with `nothing_pushed` |
| 5 | Step 1: add the AIDC base's sources (§3's list), let them become Markdown. They reach the shared folder with the push (D2). | Each source has Markdown; spot-check two tables |
| 6 | Step 2: Session A only if the schema must change; Session B for the skills. Move the manager's reading rules there. | The owner reviewed every schema change and skill |
| 7 | Import the AIDC seeds first (`seed/`, the 22 card CSVs): preview, apply. Then its pages through the card-page importer (§3). | 22 CSVs → 323 cards; §7's AIDC numbers match |
| 8 | Repeat 5–7 in §3's order: aerospace, robotics, wireless module, wireless example. **Commits per import**, each with its sources in a commit of their own. | After each: quality check read; new conflicts settled (D3); no fact without a source |
| 9 | Fix the links written in another spelling of a merged card (28 last time), as field edits with a reason. | Quality check's unresolved links explained |
| 10 | Step 3: benchmark questions and the Dashboard (the analysis AI, or an Atlas import of the order). | Owner approved each question and the order |
| 11 | Testing: run the benchmark on the working copy. | No regression the owner did not accept |
| 12 | Push. | `status`: ahead 0, no conflict; the owner sees the commits and the originals under `sources/` on OneDrive |
| 13 | Tag `2026q4-r6`, publish with confirmation. | `/api/knowledge/askable` says 可以在對話裡問, `reads.tag` is the tag |
| 14 | In a new general chat: ask a cross-domain question and a BI question that needs SQL. | The answer carries `資料來源：知識庫 vault-<id> 發佈版本 <tag>`; numbers match the Dashboard; `bi__query` was on (Skill, capability, grant) |
| 15 | Atlas: open the panels of the new vault. | Panels show the published analyses (Atlas layouts stay personal) |
| 16 | A colleague joins the folder (`join`). | Their Agent reads the same tag; they see the originals, with none waiting once OneDrive has delivered them |
| 17 | `rs-k` copy: §6. | |
| 18 | Update `docs/TASKS.md`, `HANDOFF.md`; **the owner** deletes the old folder when satisfied, later. | |

## 6. The `rs-k` copy import

Page: Knowledge > 知識庫維護 > 新增知識庫 > 匯入既有 wiki 資料夾的副本 (`POST /api/knowledge/repos/import`). The
folder given is only read. Needs `knowledge_pipeline` in `host.json` for the page to show the card.

1. Source: `%LOCALAPPDATA%\AEP\rs-k-v1.0.3`. Target: the folder the owner names (step 1). Title and purpose: say that
   it is a test copy.
2. Checkpoint: `imported` counts match the folder (2,007 wiki pages at K2, 508 Raw, plus later growth); `skipped` read;
   the source folder's digest unchanged.
3. Push happens with the import. Tag and publish `rs-k-test.1`.
4. Not during the import (D4). Only after the owner has compared answers: on the Knowledge page 「讓 Agent 可以問這個知識庫」, read the card's effects, Apply, restart
   (check `/api/tasks`). The existing `rs-knowledge` stays the first binding, so `aep_knowledge_ask` keeps using it.
   Compare a few answers, then 「解除 Agent 的綁定」 if it was only a test.

## 7. Reference numbers from 2026-10-29

A difference is not a failure; each must be explained.

| What | Then |
|---|---|
| Cards after the five bases | 639 |
| AIDC seeds | 22 CSVs, 323 cards, every column mapped |
| AIDC evidence | B 42, C/D 9 |
| AIDC compute chain | 49 supply links; power and cooling 2 |
| Quality | 23 issues in the manager's data, 3 deliberate gaps; AIDC alone 0 issues |
| Known data issues | 8 links to unwritten cards, 致茂 and 鴻海 in two types, 7 revenue facts without a source, 2 sample nodes off the name format, 1 A-grade link without a date |
| Merge conflicts | 7 scalar conflicts |

## 8. Rollback

| Where you are | What to do | Loses |
|---|---|---|
| Before a push | Discard or `revert` the local commits on the page | Local work since |
| After a push, before publishing | `revert` the commit (a new commit); the Agent reads the head only while never published | Nothing |
| After publishing | Publish the earlier tag again (`KNOWLEDGE_REPO.md` §7); nothing moves | Nothing |
| Binding of the wiki copy was wrong | 「解除 Agent 的綁定」 and restart; `host.json.bak-<stamp>-knowledge` is the earlier file | Nothing |
| A file was pushed by mistake | Withdraw it on the page, once that is built. It does not remove OneDrive's version history or what commits hold: `BI_SOURCES_IN_REPOSITORY.md` §5 | The file, for everyone |
| The rebuild is abandoned | Rename the new folder to `market-intel.r6-failed`; rename `market-bi.v4-old` back to `market-bi`. The old vault stays unreadable by this AEP either way (R2). | The session's work stays in the renamed folder |
| Agent Web will not start after a `host.json` change | Restore the backup; check `assets/knowledge/` holds the manifest of each binding | Nothing |

The owner's copy of the old data is the renamed folder. **Do not remove it during the session.**
