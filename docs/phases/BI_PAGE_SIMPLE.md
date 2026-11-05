# The BI Knowledge page, redesigned to be simple

Status: S1 and S3 done, 2026-11-05; S2, S4–S8 not started. Decision `docs/DECISIONS.md` 2026-11-05. Base `main` 86a7d614, branch `bi-page-simple`.

**The owner's rule, verbatim:** 「ui請以簡單為主，善用table，menu/comobox」.

So: tables, menus and comboboxes rather than long text, stacked forms and rows of buttons. No explanatory paragraphs on the main path. The owner chose the whole redesign before release, even if the date slips, so **scope is not cut to meet a date**.

Line numbers below are `src/host_runtime/web_page.py` at 86a7d614.

## 1. The owner's flow: the only things on the main path

| Step | Part | What the person does |
|---|---|---|
| 1 輸入與轉檔 | 1 | Choose the vault |
| | 2 | Choose the market field |
| | 3 | Add files |
| | 4 | Press convert, then review the converted result |
| 2 Schema 與 Ingest | 1 | A button: from the newly added data, the system suggests whether to add a class to the schema |
| | 2 | Review the current skills and tools; change or add them through an AI session that stays on this page |
| | 3 | Ingest button |
| | 4 | Review the cards and decide whether to apply |
| 3 測試 | 1 | View or edit the dashboard; an AI session can help |
| | 2 | View or edit the question set in a table; a selected row opens an editable section on the right |
| | 3 | Start the test run |
| | 4 | View results and the dashboard, and decide whether to commit |

The top section (dataset, domain, sample, refresh, dataset management, schema line) and step 1's knowledge base block are duplicates, and both go away as separate blocks.

## 2. What the code says (checked, not assumed)

| Finding | Evidence | Consequence |
|---|---|---|
| `#bi-dataset` is the page's state; `#bi-b-ds` only mirrors it | `biDataset()` used 92 times; mirror at 14619, filled at 13234 | One select, keep the id, drop the mirror |
| A subscribed copy cannot be built | Build tab hidden at 16084, redirect in `biShowView` at 12144, mirror filters read-only out at 13235 | Moving the select into step 1 would strand someone on a subscribed copy. See §3.1 |
| `#bi-domain` only filters reading | `biDomain()` 11905; `biRunBody` 15260 never sends it | It is not the owner's "market field" |
| The owner's "market field" is `#bi-b-src-folder` | Sent as `folder` at 14974; selects the extract rule | Promote it. Shown only for a vault, as today |
| Adding a file already converts it | `Staging._keep` converts before anything is kept; `source_no_text` refuses, another failure is kept with its reason | No backend needed. 「加入來源」 becomes 「轉檔」. A file is not converted separately |
| A run takes one source | `biRunBody` sends `source_id`; `_extract` reads `run["source_ids"][0]` | Batch needs design. §5, S4 |
| `check_fit` is only a tick on a run, and a custom method ignores it | `biRunBody` returns at 15264 before the tick | The suggest button needs its own path. §5, S2 |
| `propose_type` is a recorded decision, not a schema change | `schema_fit.py` line 8 | A suggestion ends in Session A, not in a write |
| The bench gate is real, but only for a test that was run | `bi_bench.gate`: blocks on `regressions` of the newest finished run whose `units_sha256` matches. **With no such run it blocks nothing and only notes it**. `repo.push` returns `status: blocked` | A share step must stop on `blocked`, and must show the "not tested" note. §5, S6 |
| Publish takes a person's confirm | `vault.publish` refuses without `confirm: true` | One click on a share button can carry it, only with a confirmation in front |
| A question is overwritten by its `set` and `slug` | `checked_question` + `_stage`; the list returns both | Edit in place is possible with no backend. Changing `set` is delete plus save |
| Five AI session kinds, five panels | `sessions.KINDS`; panels `bi-b-sa`, `-sb`, `-ska`, `-ana`, `-qa` | One panel. §5, S3 |

**The Knowledge page's other tab, `kn-pane-pipeline`,** opens first and is a different product: an English three-step sandbox wizard for wiki folders (`kp-*`, routes `/api/knowledge/pipeline/*`), with a block saying sandboxes will give way to knowledge repositories. It shares no controls with the BI pane. **Not in this redesign** (the owner, §7).

## 3. Target layout

```
[ 建立與匯入 | Dashboard | 卡片 ]                         12 張卡片 · 更新於 …   [ 進階 ▾ ]
 ① 輸入與轉檔  ② Schema 與 Ingest  ③ 測試                   (stepper)

 Step 1
 知識庫 [combobox]  [管理 ▾]   領域 [combobox]  機密等級 [combobox]   [選檔]  [轉檔]
 ┌ table of sources: 使用 | 來源 | 格式 | Markdown | 大小 | 機密等級 | 共用資料夾 | 加入時間
 [ 進階 ▸ ]                                                    [ 下一步 ]
```

### 3.1 One selection, and no trap

`#bi-dataset` moves into step 1, with its existing option groups (我的資料集, 已訂閱). Its id does not change, because 92 reads and 39 test references use it.

**The trap and its fix.** Today selecting a subscribed copy hides the build tab. With the select inside step 1, that would hide the only way back. So:

- The build tab stays visible for every dataset, and step 1 stays reachable.
- A read-only dataset still opens on the Dashboard, as today, with its banner.
- On a read-only dataset, step 1 shows the select, the banner and a link to the cards, and hides the add-file row. Steps 2 and 3 are disabled in the stepper.

So the Dashboard and 卡片 tabs are the reading entry for subscribed copies and stay until S5; only then is it decided whether they remain as tabs. They hold what a colleague who only reads needs.

### 3.2 Advanced

- **One page-level `#bi-advanced`:** things about the dataset rather than a step.
- **One 進階 section per step:** things used in that step.

Advanced is a `<details>`, closed by default. Anything opened from elsewhere in the page opens its details first.

## 4. Where every control goes

"S1" means moved by slice 1. A later slice is named where it replaces the control. **Nothing here removes a backend route.**

### Top section and tabs

| Control | Goes to |
|---|---|
| `bi-dataset` | Step 1 |
| `bi-domain`, `bi-sample` (read filters) | `#bi-advanced` |
| `bi-counts` | One line beside the tabs |
| `bi-refresh` 更新 | **Removed.** Changing dataset and opening a tab reload |
| `bi-publish`, publish panel, result, `bi-pub-state` | `#bi-advanced` |
| `bi-manage`, `bi-new`, `bi-install`, `bi-demo` and panels | `#bi-advanced` |
| `bi-schema-note` | `#bi-advanced` |
| `bi-empty-state` | Stays above the tabs, a line and two buttons |
| `bi-ro` | Stays above the tabs |
| `bi-subs` | `#bi-advanced` |
| `bi-hint`, `bi-ask` 到對話中問 | **Removed** |
| `bi-atlas-open`, `bi-atlas-set`, `bi-atlas-url` | Stay on the Dashboard tab; chat embeds need the address and this is its only setter |
| `bi-dom` (legacy domains) | Stays; shows only for an old dataset |
| Cards tab, `bi-fts` | Tab stays. `bi-fts` stays in its details |

### Step 1

| Control | Goes to |
|---|---|
| `bi-b-ds`, its handler | **Removed** (the mirror) |
| Long text in `bi-b-vault`, `bi-b-src-shared`, the conversion paragraph | **Removed** |
| `bi-b-v-new`, `-join` (create, join a vault), `bi-b-v-sync` | Menu 管理 ▾ beside the select |
| `bi-b-v-convert` | 進階 of step 1 |
| `bi-b-v-state` | Stays under the select: conflicts and unreadable files must be seen |
| `bi-b-askable` | 進階 of step 1 |
| `bi-b-props` (proposals) | Step 2 review; shows only when some are open |
| `bi-b-src-folder` | Row, labelled 領域 |
| `bi-b-file`, `bi-b-class`, `bi-b-upload` | Row; `bi-b-upload` reads 轉檔 |
| `bi-b-sources` table, `bi-b-md` viewer | Stay |
| `bi-b-src-withdraw` | Stays; appears when asked |
| `bi-b-pages` (Obsidian) | 進階 of step 1 |

### Step 2

| Control | Goes to |
|---|---|
| `bi-b-fit` | 進階, until S2's button replaces it; then removed |
| `bi-b-skills` list, `bi-b-tl-list`, `bi-b-ska` | Main path, part 2 |
| `bi-b-sk-new`, `bi-b-sk-form` | **S3:** `bi-b-sk-new` is on the main path and opens the AI panel: name, folder, and the first sentence, saved as revision 1 (staged) so the session has a rule to talk about. `bi-b-sk-form` stays in 進階, only for a row's direct edit |
| `bi-b-profile`, `bi-b-rerun`, tool code form | 進階. Tool approval renders in `bi-b-tl-list`, which stays on the main path |
| `bi-b-sa` (Session A), drafts, `bi-b-versions`, `bi-b-upgrade` | 進階, with schema publish and upgrade reachable there |
| `bi-b-m-pick` | Main path, part 3 |
| `bi-b-start` | Main path, part 3: this is the ingest button |
| `bi-b-fresh`, `bi-b-folder`, method naming, `bi-b-sb`, `bi-b-entity`, recipe, instructions, trial, compare | 進階 |
| `bi-b-cands`, `bi-b-accept-clean`, `bi-b-same` | Main path, part 4 |
| Commit and result stages | Stay as the end of part 4, not separate entries in the stepper |
| Correction notes, evidence review | Stay in the card and candidate detail they are drawn in |

### Step 3

| Control | Goes to |
|---|---|
| `bi-b-to-dash`, `bi-b-to-cards` | Main path until S5 embeds the dashboard |
| `bi-b-an-list`, `bi-b-an-new`, `bi-b-ana` | Main path, part 1 |
| `bi-b-an-pack`, file import, export, `bi-b-atl` | 進階 |
| `bi-b-bq-list`, `bi-b-bq-form`, `bi-b-qa` | Main path, part 2 |
| `bi-b-bc-*` (extraction cases) | 進階 |
| `bi-b-bench-run`, report | Main path, parts 3 and 4 |
| `bi-b-ver-*` commit, push, conflicts | Main path after the results |
| `bi-b-ver-history` (tag, publish, revert) | Stays reachable; **tag and publish must not be hidden until S6 gives them a place**. Colleagues and the Agent read only published versions |
| `bi-b-ver-discard` | 進階 |

## 5. Slices, in order

The estimates are agent hours of work plus test runs, unmeasured, from the size of these parts of the page. A browser test file takes minutes and the machine is shared, so waiting time can be larger than work. Each slice ends with CI checks and its browser tests, and adds a `docs/TASKS.md` row.

| # | Slice | Backend | Estimate |
|---|---|---|---|
| S1 | **The restructure.** §3 and §4: one selection, no trap, stepper of three, advanced areas, paragraphs out, ingest button in part 3. No new feature | None | 8–12 h, about half of it tests in 23 files |
| S2 | **The suggest button.** A run that asks only the fit question over the newly added sources, answered as a table: class, why, how many items. It costs model output (recorded earlier as 40–50% more on an ingest), so it is a press, not automatic. Adopting a suggestion opens Session A with it. Remove `bi-b-fit` | A fit-only route or kind. Must work for a custom method, which today skips it | 6–10 h |
| S3 | **One AI panel. Done.** `#bi-ai` in `kn-pane-bi`: fixed at the right at full height (the page makes room beside it), the lower part on a phone. Opened from the row or button it concerns, with one log and one input; closes on a dataset change. `biAiOpen(spec)`: a kind gives its title, what it is about, what goes to the model, and how to get ready to send. Removes the five panels | None | Done |
| S4 | **Batch.** Tick several sources; ingest runs them; review across them. Recommended: one run per source, a batch id grouping them, the review table reading all of them, and one apply. Rejected unless it proves needed: one run over many sources, because `_extract` and the source evidence assume one | Batch grouping; apply over several runs | 10–16 h |
| S5 | **Step 3.** Question table with an editor on the right (save by `set` and `slug`; changing `set` is delete plus save); dashboard embedded; a results view for the commit decision, side by side with the dashboard. Decide then whether the Dashboard tab stays | None for questions; to check for the embedded dashboard | 10–14 h |
| S6 | **Share.** Commit then push, tag, publish as one step with a confirmation. Stops on `blocked` or `conflicts`, showing why; shows "這次內容沒有跑過測試" from the gate's note. **Does not weaken the gate**: the gate stays in `repo.push`. An untested push stays allowed, with the note (the owner, §7) | A thin route, or none if the page sequences it. The tag name is a proposed date, editable | 4–8 h |
| S7 | **Tables everywhere left.** Skills and tools; candidate review; cards; history. Menus for row actions | None | 6–10 h |
| S8 | **Final pass.** Screenshots at 1366 and 390 px, wording, accessibility, the whole-flow browser test, user guide and install docs, the full suite | None | 4–8 h |

**Total: about 56–92 agent hours.** No date is promised from this.

### What can run in parallel on `web_page.py`

The file has one big block of markup and one of script, so edits collide by region rather than by file.

- **S1 runs alone and first.** It moves almost all the BI markup; anything alongside it would conflict.
- **S3 runs alone, straight after S1.** It touches all three steps.
- **After S3, S2, S5 and S6 can run at the same time.** S2 is the top of step 2, S5 is step 3's questions and dashboard, S6 is `bi-b-ver-*`. S5 and S6 meet at the commit decision, so S5 hands over `bi-b-ver-*` untouched and S6 owns it. Expect small rebases.
- **S4 runs after S2,** because both change step 2's ingest start, and can overlap S5 and S6.
- **S7 touches every region.** It runs after S2–S6, or is split per step and given to the slice that owns that step.
- **S8 is last and alone.**

Every slice may add to `tests/bi_page_driver.py`; those are small rebases.

## 6. Tests

- Ids are kept wherever a test needs them, and a test that used a removed control is rewritten to the new flow, not weakened. The removed ids are `bi-b-ds`, `bi-refresh`, `bi-hint` and `bi-ask`.
- A control inside a closed `<details>` still takes a script's `.click()`, so tests that drive by script keep working. That proves less than a person could: **S8's whole-flow test opens the details it uses**, so a control that cannot really be reached fails there.
- New static tests pin the main path: which ids sit outside any 進階, no explanatory paragraph in it, and one select.
- The feed goldens and Atlas are not touched. ADR-K10 guard unchanged: this is page markup.

## 7. The owner's answers (2026-11-05, through the orchestrator)

1. **`kn-pane-pipeline` is out of scope.** The Knowledge page opens on the BI tab when this PC has a BI dataset or vault. Small, so it is done in S1.
2. **Tag names in S6:** the page proposes a date as the tag name, editable.
3. **A push with no test run stays allowed,** with a visible note. S6 keeps that and shows the note.

## 8. The review table (part of S7)

Status: built, branch `bi-review-table`, 2026-11-05. Combobox `#bi-b-run-pick` of the dataset's waiting runs (every ingest run, and reading trials; a page's own trial stays in its step), table `#bi-b-cands` with a type and a state filter and a count, `#bi-b-cand` beside it with accept and reject first, then the fields, then the source with the quote marked. A decision moves to the next undecided row. Measured on 180 fictional candidates: open 1.5 s, redraw 11-14 ms, accept 178 in 16-19 s with a counter on the button (one request each; no bulk route was needed). Not yet seen on the real run. Test: `tests/test_bi_review_table_ui.py`.

The brief as given:

Brief from the orchestrator, 2026-11-05. D's `bi-summary-fill` adds a reading run, `POST /api/bi/runs {reading: true, ...}` in `reading_runs.py`, started through the API. `#bi-b-cands` shows only `bi.build.run`, so such a run cannot be opened. About 180 candidates will wait there. Base it on main once D's branch is in. Stay inside the review stage: Lane D is on the AI panel.

- **A combobox of the dataset's runs waiting for review.** The chosen one opens in the review list. `GET /api/bi/runs` or similar: check what exists. `biBuildFetchRun(runId)` then `biBuildRenderRun()` already draw one run.
- **Candidates as a table** with its own scroller, using `.bi-split`, `.bi-split-list`, `.bi-scroller`, `.bi-split-pane` (see `#bi-b-src-split` and `biListTable`): card name, field, proposed value.
- **Selecting a row shows source text and the quote on the right,** with accept and reject. Today's detail is `#bi-b-cand`.
- **180 must be workable,** including `#bi-b-accept-clean`. Measure the draw, as `test_bi_many_sources_ui` does.
- **Test with a reading run:** nothing built for ordinary runs may trip. Read `biBuildAllowed`, which allows `commit` only when `run.kind === "ingest"`, and `biBuildRenderRun`, which returns early for any other kind. Check what `kind` a reading run has.
- **Tests that use the list today:** `#bi-b-cands button` in `test_bi_build_flow_ui`, `test_bi_build_ui`, `test_bi_vault_ui` and others. Rewrite them to the table; do not weaken them.

## 9. The working domain (工作領域)

Status: designed 2026-11-05, decision `docs/DECISIONS.md` 2026-11-05. **The owner, verbatim:** 「我們要支援多人開發一個vault，所以這個頁面不是應該要選擇要編輯的domain，例如aidc，之後的修改，就依選擇的domain來做後續的ingest和testing」.

One combobox says which part of the vault this person is working on. Steps 1, 2 and 3 follow it. **It narrows what a person sees and what they add. It is not isolation and not a permission:** content, commit, push and the bench gate stay whole-vault.

### 9.1 What a folder, a domain and a home are

The code already has the relation; nothing new is invented.

| Word | What it is | Where |
|---|---|---|
| **home** | `<application>` or `library/<entry>`, the short form. It owns sources, skills, tools and a profile | `homes.home_of`, `vault_skills.home_list` |
| **domain** | A coarse label on a card; a card may hold several | The schema's `domains`, the `domain` field |
| **home to domain** | The schema domain of the same name, ignoring case: `aidc` is `AIDC`. A library entry spans domains, so it has none | `homes.domain_of_folder`, already used by ingest |

**The working domain is a home.** On screen it is 工作領域, the word the owner uses. So:

- `aidc`, `aerospace`, `robotics`, `wireless` each have a card domain as well.
- `library/products`, `library/technologies`, `library/competitors` are chosen the same way, for people keeping shared reference data. They have sources, skills and questions, and no card domain, so the Dashboard's domain does not move for them.
- **`mobile` has no folder, so it cannot be chosen.** Its cards are still read through the Cards and Dashboard filters. Creating `applications/mobile` is a vault decision and is not done here.
- **A card is not in one domain.** An ingest in `aidc` can touch a card also holding `wireless`. Nothing stops it, and the commit list says which homes the change touches (§9.5).

### 9.2 The combobox

`#bi-b-src-folder` keeps its id and its values (a home's `sources` folder, `sources` for everything) and moves out of step 1's row to one line above the stepper, labelled 工作領域. It is in sight on all three steps. The options come from a new `homes` list in the vault's skills reply: the vault's homes, plus any home found among its folders and sources. Subfolders are no longer options, and a source in one counts for its home.

- **全部領域 replaces 「不指定資料夾」.** **A person can look with no domain and cannot add with none:** every list shows everything, waiting runs can be reviewed, and a bench covers the whole vault, but 轉檔 and 放進共用資料夾 wait for a choice, with a short line saying so. A file added to no home gets no extract skill and no profile, which is the failure this request is about. Old sources sitting in `sources` stay visible under 全部領域 and can still be ingested. The API is unchanged and still accepts `sources`; the guard is the page's.
- **Kept per person and per PC:** `localStorage`, key `bi-scope-<dataset>`, like `bi-build-<dataset>`. A stored home that no longer exists falls back to 全部領域.
- **First visit:** 全部領域, nothing hidden. Choosing for someone could put a file in the wrong folder.
- **A vault with no homes** shows only 全部領域, and adding works as it does today, into `sources`.
- **A plain dataset and a read-only copy** do not show the combobox: a dataset has no homes, and a subscribed copy is only read.

Changing it deselects a source outside the new scope, closes the AI panel, and redraws the lists below. The tab 卡片 and its filter do not follow: that filter starts on every domain, because the owner found cards missing when it did not.

### 9.3 Step 2

| Thing | In a working domain |
|---|---|
| Skills | Those applying to its folders, and those applying to everything (`classify`). A count says how many are hidden. A new rule starts on its folder |
| Tools | Those of its home (`tool:<home>/<name>`) |
| Profile | The 進階 picker starts on its home |
| Ingest | The sources table shows only its sources, so the run takes that source's folder and skill as it does now. `run_folder_mismatch` still refuses a mismatch |
| Review | `#bi-b-run-pick` lists this domain's runs and runs with no home first (a reading run spans the vault), and the rest in an option group 其他領域. **Runs from elsewhere stay one choice away and are never opened by themselves.** |

No backend change: a run's home comes from its source's folder, in the page.

### 9.4 Step 3

**What has a domain today (checked):** a question has only a `set`. An extraction case has a `folder`. A bench run has neither. An analysis has none, but takes a `domain` parameter, and the Dashboard passes one.

- **A question gets one optional field, `home`.** Absent means it belongs to the whole vault (全庫). Every question today is that, so nothing moves. The unit's digest is unchanged for an untagged question, and an older AEP ignores the field. New questions and AI suggestions take the working domain. The table gets a 領域 column.
- **A working domain shows its own questions and the 全庫 ones.** The 全庫 questions also run, because they are the vault's general checks. 全部領域 shows and runs all of them.
- **A case's home is its folder's.** One with no folder counts as 全庫.
- **`POST .../bench` takes an optional `home`.** Absent is the whole vault, as today. The report records `scope` and `not_covered`. **The report says what it covered:** 「涵蓋 aidc 與全庫 5 題；沒測 7 題」.
- **Dashboard and analyses:** no new field. Choosing a home with a domain sets the Dashboard's domain and the default of an analysis's `domain` parameter. A person can still change either.

### 9.5 The gate, and several people

`bi_bench.gate` read only the newest finished run on the same content. With scoped runs that would be a hole: **a whole-vault run finds a wireless regression, then a newer aidc run on the same content hides it.** So:

- **The gate takes each question's newest verdict across all finished runs on that content.** A regression stands until a later run on the same content passes that question. A whole-vault run as the newest behaves exactly as today, including a rerun clearing a regression.
- **The block names the question and its domain:** 「測試退步（wireless）：…」. A question's domain does not exempt anyone: **a person in `aidc` is blocked by a wireless regression**, because the push carries the whole vault.
- **They see it before pressing push.** `GET .../checks` adds `standing`, the gate's answer for the working copy, drawn in step 3 in every scope. Without it a green aidc report could sit above a push that will be refused. To clear it: fix it, ask the colleague who owns it, or rerun in that domain or in 全部領域.
- **A push with some questions untested stays allowed, as a push with none is (§7), and the note says how many were not tested.** This is not weaker than today, when a person could push with no test at all.

**Commit and push stay whole-vault units.**

- **Commit carries every uncommitted change on this PC, in any domain.** `pending` adds `homes` to each change, and the list starts with a count per home: 「aidc 5 項・wireless 2 項・其他 1 項」. A warning appears when some are outside the working domain. Discard also covers everything, as it says today. Choosing part of a change set is not offered: it would be a change to the repository's model.
- **When a colleague's work arrives** through sync, as today: the status line counts it, their sources join the list and are hidden from this scope's rows but counted (「顯示 2／15 份」), and their commits show in the history. **Their arrival changes the content's digest, so an earlier bench no longer applies:** the note goes back to 「沒有跑過測試」. That is the existing rule, and it matters more with several people.
- A card's homes come from `card_app_folders`. A card with none counts as 其他.

**The owner's goal does not need the repository model changed.** What this does not give: one person's work cannot be held out of another's push once both are in the same commit history, and a person cannot push only one domain. If the owner wants domains published or blocked separately, that is a repository redesign, not this slice.

### 9.6 The AI panel

The panel's line about what it is working on names the working domain. Each turn sends `scope`, and the route puts one line naming the home and folder in front of the message, for all five kinds. It is checked with `home_problem`, so only a home's name can arrive. The line is kept with the turn, since it was sent, and the log does not show it. Accepting AI questions tags them with that home. A panel closes when the working domain changes, so a session never talks across two.
