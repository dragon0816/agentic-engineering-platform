# R6: rebuild `market-bi` from raw sources, and import an `rs-k` copy

**Run with the owner present.** It writes the shared OneDrive folder and may restart Agent Web. An agent prepares and
reads; the owner decides at each ☐ below. Records this rests on: `docs/phases/KNOWLEDGE_REPO.md` §11–§12,
`docs/phases/BI_VAULT.md` §12, `docs/phases/BI_BUILD_FLOW.md`, `docs/TASKS.md` 2026-10-29.

**Never:** a tool that migrates the V4 format (owner, 2026-11-02); writing to the real `RS_Knowledge` folder; deleting
the old `market-bi` folder (the owner removes it later, by hand).

## 1. Why

`OneDrive - Rohde & Schwarz\BI_Knowledge\market-bi` is in the V4 format (`changes/`, `vault.json`). AEP neither reads
nor writes it since R2. The repository format needs its sources, schema, skills and cards as commits, so it is rebuilt.

## 2. Decide these first

| ☐ | Decision | Why it cannot wait | Recommendation |
|---|---|---|---|
| D1 | **The new vault's id.** | Creating `market-bi` again is refused on the owner's PC (`vault_exists`): that PC still holds `bi/vault-market-bi` and the registry entry, and there is no route to leave a vault. The id is fixed forever. | A new id, e.g. `market-intel`: nothing local has to be deleted. The alternative, keeping `market-bi`, needs removing the old local entry and data by hand first. |
| D2 | **Decided (owner, 2026-11-02): the originals go into the shared folder.** | **R6 cannot run until this is built:** today a BI vault's sources stay on the PC that added them. Its scope and the owner's open points (per-file limit, confidentiality, removing a file pushed by mistake) are in `docs/DECISIONS.md` 2026-11-02 "A BI vault's originals go into the shared folder". | Look at the total size first (§4). |
| D3 | **How the five bases are merged.** | The 2026-10-29 merge was a one-off script (`--fill-only`: lists joined, first name kept, bodies kept per base), **not in the repository**, and it reported 7 scalar conflicts. | Import base by base through the page, one commit per base, and settle conflicts in the review step. Do not bring the old script back without reading it. |
| D4 | **Which `rs-k` copy, and is it bound to the Agent?** | Binding a second vault changes how questions route (§8). `KNOWLEDGE_REPO.md` §11: importing a copy of the real `RS_Knowledge` is a separate decision. | Import `%LOCALAPPDATA%\AEP\rs-k-v1.0.3` (already a copy) as a test; do not bind it until the owner has compared answers. |
| D5 | **The first tag's name.** | Tags never move. | e.g. `2026q4-r6`. |

## 3. Raw sources

| Source | Where | Notes |
|---|---|---|
| Manager's five bases: wireless example, robotics (schema v4), aerospace (v7), wireless module (v8), AIDC (v8) | Local, never committed; the AIDC one was `files/aidc-bi-kb`. **The owner names the other four paths.** | Obsidian + Dataview, seed CSVs, `tools/bi_schema.py`, `bi_ingest.py` |
| Two AIDC reports | Old folder, `applications/aidc-*/sources/` | Read only; copy out, never move |
| Name aliases (148+4), chains | Old folder's domain configuration | For a person to read. Aliases and chain names are now written on the cards; reading rules move to the vault's skills |
| Schema | Built in: `bi.schema/v1.1@2.0.0` | 21 types; `segment` already has the 11 market segments |

The old folder is a reference for a person only. Nothing is converted from it by a tool.

## 4. Pre-checks a script can run beforehand

Read-only: it only asks whether files exist and how they are named. It opens nothing and writes nothing, so OneDrive
downloads nothing. **The owner runs it, or asks for it to be run, on the real paths**; agents working in temp
workspaces do not.

```powershell
python scripts/r6_precheck.py `
  --shared "<OneDrive - Rohde & Schwarz>\BI_Knowledge" `
  --base "<wireless>" --base "<robotics>" --base "<aerospace>" --base "<module>" --base "<aidc-bi-kb>" `
  --wiki-copy "$env:LOCALAPPDATA\AEP\rs-k-v1.0.3" --real-wiki "<RS_Knowledge>" `
  --wiki-target "<folder for the new wiki repository>" `
  --workspace "<AEP workspace>" --vault-id "<D1's id>"
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

Also, by hand: total size of the bases and reports, and the largest single file (D2); `GET /api/tasks` and `/api/activity` are idle before any
restart; a free afternoon, since the extraction uses real models.

## 5. The session, in order

Agent Web must run code with the build flow (`docs/phases/BI_BUILD_FLOW.md`). Page labels below are as of 2026-11-02;
that flow is changing, so read the current ones on the page.

| # | Step | Checkpoint before going on |
|---|---|---|
| 1 | Run §4. Settle D1–D5, write them in `docs/DECISIONS.md`. | Exit code 0; decisions recorded |
| 2 | Restart Agent Web if it predates the build flow (check `/api/tasks` first, AGENTS rule 19). | Page shows the build-flow steps |
| 3 | Rename the old folder to `market-bi.v4-old` in Explorer. Wait for OneDrive to finish. | Old folder present under the new name on OneDrive's site; nothing deleted |
| 4 | Knowledge > BI > 建立與匯入 > 建立共用知識庫（vault）: D1's id, in `BI_Knowledge`, schema `bi.schema/v1.1` (2.0.0), author `leo.chi`. | `repo.json` in the folder; `/api/knowledge/askable` lists it with `nothing_pushed` |
| 5 | Step 1: add the AIDC base's sources, let them become Markdown. They reach the shared folder with the push (D2). | Each source has Markdown; spot-check two tables |
| 6 | Step 2: Session A only if the schema must change; Session B for the skills. Move the manager's reading rules there. | The owner reviewed every schema change and skill |
| 7 | Import the AIDC seeds first: preview, apply, commit with a purpose. | 22 CSVs → 323 cards; §7's AIDC numbers match |
| 8 | Repeat 5–7 for robotics, aerospace, wireless module, wireless example. **One commit per base.** | After each: quality check read; new conflicts settled (D3); no fact without a source |
| 9 | Fix the links written in another spelling of a merged card (28 last time), as field edits with a reason. | Quality check's unresolved links explained |
| 10 | Step 3: benchmark questions and the Dashboard (the analysis AI, or an Atlas import of the order). | Owner approved each question and the order |
| 11 | Testing: run the benchmark on the working copy. | No regression the owner did not accept |
| 12 | Push. | `status`: ahead 0, no conflict; the owner sees the commits and the originals under `sources/` on OneDrive |
| 13 | Tag (D5), publish with confirmation. | `/api/knowledge/askable` says 可以在對話裡問, `reads.tag` is the tag |
| 14 | In a new general chat: ask a cross-domain question and a BI question that needs SQL. | The answer carries `資料來源：知識庫 vault-<id> 發佈版本 <tag>`; numbers match the Dashboard; `bi__query` was on (Skill, capability, grant) |
| 15 | Atlas: open the panels of the new vault. | Panels show the published analyses (Atlas layouts stay personal) |
| 16 | A colleague joins the folder (`join`). | Their Agent reads the same tag; they see the originals, with none waiting once OneDrive has delivered them |
| 17 | `rs-k` copy: §6. | |
| 18 | Update `docs/TASKS.md`, `HANDOFF.md`; **the owner** deletes the old folder when satisfied, later. | |

## 6. The `rs-k` copy import

Page: Knowledge > 知識庫維護 > 新增知識庫 > 匯入既有 wiki 資料夾的副本 (`POST /api/knowledge/repos/import`). The
folder given is only read. Needs `knowledge_pipeline` in `host.json` for the page to show the card.

1. Source: the copy of D4. Target: D4's folder. Title and purpose: say that it is a test copy.
2. Checkpoint: `imported` counts match the folder (2,007 wiki pages at K2, 508 Raw, plus later growth); `skipped` read;
   the source folder's digest unchanged.
3. Push happens with the import. Tag and publish `rs-k-test.1`.
4. Only if D4 says so: on the Knowledge page 「讓 Agent 可以問這個知識庫」, read the card's effects, Apply, restart
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
| The rebuild is abandoned | Rename the new folder to `<id>.r6-failed`; rename `market-bi.v4-old` back to `market-bi`. The old vault stays unreadable by this AEP either way (R2). | The session's work stays in the renamed folder |
| Agent Web will not start after a `host.json` change | Restore the backup; check `assets/knowledge/` holds the manifest of each binding | Nothing |

The owner's copy of the old data is the renamed folder. **Do not remove it during the session.**
