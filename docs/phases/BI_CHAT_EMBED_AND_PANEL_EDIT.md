# BI: Atlas panels embedded in the chat, and the AI editing a panel

Status: owner decisions 2026-11-02 (relayed by the BI orchestrator); design by Claude Code the same day.
Amends `docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` (C2, C3, K1). Decision record: `docs/DECISIONS.md`
2026-11-02 "BI: the chat embeds Atlas; the AI edits existing panels; AEP never writes Atlas dashboards".

## 1. Owner decisions

1. A general AI chat **embeds real Atlas panels or dashboards** (iframe). When Atlas is not running it falls back
   to today's AEP chart (C2 HTML) with a note that opening Atlas shows the full version.
2. On the BI Knowledge page a "dashboard" is a single panel, so there is no layout problem. **The AI may change a
   panel's content directly**: its data source (which card types, fields and tables the query reads), its
   computation rules (SQL, or a guarded script where analyses allow it today), its parameters and how it is
   displayed (chart type, x/y/series, title). This covers **existing** analyses. Changes are staged in the vault
   with the owner's approval in Agent Web; push and publish stay manual; published changes reach Atlas through the
   feed.
3. **AEP never writes Atlas dashboards.** Atlas layouts stay personal.

## 2. What exists and what is missing (read 2026-11-02)

| Path | Today | Gap against decision 2 |
|---|---|---|
| General chat, `propose_change` kind `bi_analysis` (C3) | new slug only | no way to edit; the card cuts SQL at 400 characters |
| General chat, `bi__query` | sections carry title, chart and rows | the model never sees the SQL or script it is asked to change |
| Knowledge page analysis AI (T3), session `analysis:<slug>` | the model is shown the saved analysis, "its slug stays"; 「存成分析」 stages | the slug is a prompt request, not enforced; no before/after; a save meanwhile is silently overwritten; omitted `params`/`requires` are silently dropped |
| Analysis AI, session `analysis:new` | | proposing a slug that exists silently overwrites it; the model cannot read saved analyses |
| Analysis AI, `bi_analysis__propose_dashboard` (K1) | apply refuses existing slugs (`analysis_exists`) | cannot edit an analysis in a dashboard |

## 3. Part P: editing a panel

### One comparison

`analyses.changes(before, after)` lists the fields that differ among `title`, `question`, `kind`, `code`, `chart`,
`params`, `requires` (`{field, before, after}`); `analyses.digest` of the same fields is the edit's base. Both
paths below show this list and neither stages a change when it is empty.

### P1 The general chat proposes an edit: `propose_change` kind `bi_analysis_edit`

Web only, like `bi_analysis`; the BI side stays in `host_runtime/bi_chat_save.py`.

Values: `vault`, `slug` (must exist in the vault's working copy), and only what changes: `title`, `question`,
`chart` (only its keys given), `sql` **or** `script`, `params`, `requires`. Omitted fields keep their value; `params: {}` or
`requires: {}` clears them. (`sql`/`script`, never a key named `code`: `propose_change` refuses secret-shaped
names.)

The plan merges the values over the working copy's unit, `analyses.checked` validates, and the card shows:

- a Now/After row per changed field (clipped at the card's 400 characters, marked `…`);
- **the whole code** in the card's `preview`: a unified diff when the code changed (`bi_analysis` also gets its full
  SQL here);
- `Result on the working copy`, Now and After: rows and the first three of each, with the defaults.

**Scripts**: analyses allow them, so the owner's decision covers them, and the C3 rule "never a script from the
chat" stays for new analyses. A script from the chat is **not run until Apply**: `run_python` is "a guard against
mistakes and stray model output, not a boundary against a determined attacker", the person seeing the script is
the point of it, and the general chat (unlike the analysis AI) reads mail, web pages and other untrusted text
before it proposes. So the card says "Not run yet" and shows the whole script; `analyses.save` on Apply runs it,
checks the chart against its columns and stages only if both hold. A saved script whose code does not change
runs at plan time, as the Dashboard runs it.

The fingerprint is the working unit under the slug, so a save meanwhile makes the card stale. Apply is
`analyses.save`, staging only.

`bi__query analysis=<slug>` gains `definition` (`kind`, `code`, `question`, `params`, `requires`), for one slug and
not for `all`, so the model can edit what it reads. It reads the published version; the card's Now column is the
working copy, which is what changes. An analysis that was never published is not readable from the chat, and the
Knowledge page's AI edits it.

### P2 The Knowledge page's analysis AI edits for real

- The session's context lists the vault's analyses; a new tool `bi_analysis__read {slug}` returns one in full.
- `bi_analysis__propose` on a saved slug is an edit: `question`, `params` and `requires` the model omits keep their
  value (`{}` clears them).
- A session on `analysis:<slug>` refuses another slug back to the model (its slug stays, now enforced).
- The suggestion gains the additive `edit: {before, base, changes, preview}` (`preview` is the saved version's
  result, for side-by-side charts); no `edit` key means a new analysis.
- The page shows the changes (each field's before and after), the before and after charts, and 「套用修改」.
- Apply refuses a base that changed since (`analysis_stale`), a slug saved meanwhile when the suggestion said new
  (`analysis_exists`), and an empty change (`analysis_unchanged`; the page offers no button).

### P3 A dashboard proposal may edit too

`bi_analysis__propose_dashboard` accepts saved slugs. Its suggestion gains `dashboard.edits: {slug: {before, base,
changes}}`; the page marks them 「修改」 and shows the changes. Apply checks every base before staging anything and
refuses as P2 does.

### P4 Published edits reach Atlas

A test: an applied edit, committed, pushed, tagged and published, changes that analysis's `digest` in the feed
listing and its result, and leaves the other analyses' digests alone.

### P5 Browser test of the approval card

A real-browser turn: the scripted model proposes `bi_analysis_edit`; the card in the conversation shows the Now and
After rows with the SQL and the chart; Apply stages the edit.

## 4. Part E: embedding Atlas in the chat

Built against Atlas's `docs/AEP_EMBED_CONTRACT.md`, final at Atlas commit `4104c8d` (branch `atlas-embed`). Its
goldens are vendored in `tests/fixtures/atlas_embed_golden/`. A frame left on `waiting` is not a fallback: only a
failed server-side probe falls back, and the page reads no embed state.

The contract overrides the first brief in two places: `referrerpolicy="origin"` (Agent Web sends `Referrer-Policy:
no-referrer`, and `localhost:53583` framing `127.0.0.1:8127` is cross-site, so Atlas answers 403 without it), and the
file viewer's `sandbox="allow-scripts"` cannot be used (an opaque origin cannot load Atlas's scripts).

| ID | Task | Status |
|---|---|---|
| E1 | Vendor the contract's goldens byte for byte with a drift check | done |
| E2 | The answer part and the tool | built |
| E3 | The probe and the fallback | built |
| E4 | The model asks for an embed; dashboards listed by name | built |
| E5 | Browser test with a stand-in Atlas; real-model acceptance | done, see below |

### E2 The answer part

`bi__atlas_show` writes `atlas_embed` into its tool data; the stored answer gains `atlas_embeds` (at most 6), each
`{kind: panel, vault, slug, params, path, title, fallback?}` or `{kind: dashboard, name, path, title, fallback?}`.
**The Host builds `path`** (`host_runtime/bi_atlas_embed.py`): `/embed/panel?vault=&slug=&<param>=` with form
encoding, or `/embed/dashboard/<name as one encoded segment>`. The tool's input has no URL. The page puts the
browser's Atlas address (the existing `bi-atlas-url` preference, default `127.0.0.1:8127`) in front of it, and frames
only a path starting with one of those two prefixes.

The iframe has `sandbox="allow-scripts allow-same-origin"`, `referrerpolicy="origin"` and a title. The page refuses
to frame an address that is its own origin (`allow-scripts allow-same-origin` on a same-origin frame would undo the
sandbox) or that is not loopback. Height: the default of `.frame-wrap`, then `atlas-embed-size` messages, accepted
only when `event.source` is that frame and `event.origin` is its Atlas origin, clamped to 160–1200 px.

### E3 Probe and fallback

The page asks before framing, on every render (Atlas may have stopped since the answer): `GET
/api/bi/atlas-embed?port=` → `{ok, port, framable}`, which sends `HEAD http://127.0.0.1:<port>/embed/panel` without
Origin, 2 s, no proxy. Only 200 is framable. Otherwise the answer shows the note 「Atlas 沒有執行，這裡顯示 AEP 的圖表；
開啟 Atlas 可看到完整版本。」 and the `fallback` chart page through the existing sandboxed viewer. That page is written
when the tool runs and is one of the answer's files, so it is served like any other; the page shows it only through
its embed.

### E4 The tool: `bi__atlas_show`

Offered with `bi__query`. Input `dataset` + `analysis` + `params`, or `dashboard`, or nothing (lists Atlas's
dashboards). Agent Web only: on Telegram it says to use `bi__query`.

- **Panel**: read through the same `CapabilityInvocation` as `bi__query` (grants and audit unchanged), so an unknown
  slug or a bad value goes back to the model rather than reaching Atlas as `invalid_link`. A parameter the analysis
  does not declare is refused (`bi__query` itself ignores it); only parameters asked for go in the URL, in the enum's
  own spelling, and the rest keep the feed's default after a republish. The rows return to the model.
- **Dashboard**: the names come from `bi_atlas_import.names` (the server-side read of K2), and the name must be one of
  them. Its fallback page draws its AEP panels (at most 12, each slug once, top to bottom) through the same read; a
  panel that cannot be read is left out, as for a dashboard imported from a file with another PC's vault. When none
  can be read there is no chart, and the note says only that opening Atlas shows it.
- **Atlas down when the tool runs** (dashboards only; a panel needs nothing from Atlas): `atlas_unreachable`, with the
  instruction to show the analyses through `bi__query` and say that opening Atlas shows the full version.
- **One chart, not two**: `bi_chart_files` drops `bi__query`'s page for an analysis the same turn also frames.

Ad-hoc SQL and card answers stay C2's HTML: Atlas has no panel for them.

### E5 Live acceptance (2026-11-02)

A real model (`gpt-5.5` through the gateway) and a real Atlas with `VITE_AEP_BI_PORT=53622` (panel, fallback and edit
built from `ab2635d`, whose contract is `c7f9468`; dashboard rerun on `f75560c`, whose contract is `4104c8d`), in a
temp workspace under `%TEMP%` with its own Agent Web on 53622 and Atlas on 8128 with a temp data folder. The driver is
not committed; it called `bi_feed_api.refresh` after joining the fixture vault and set the server's read port to 8128.

- **Panel**: the model called `bi__atlas_show`; the frame reached `ready` and drew TW 3, DE 1, JP 1, US 1, the feed's
  rows, sized to 450 px by Atlas's message.
- **Atlas stopped**: the same answer showed the note and the C2 chart in `sandbox="allow-scripts"`, with no Atlas frame.
- **Edit**: the first run failed. The model sent `chart: {"type": "line"}`, and replacing the whole chart was refused
  for lacking x and y. Now a chart changes only the keys given (with a regression test). On the rerun the card showed
  Title and Chart before and after; Apply staged it. Committed and pushed, the feed's digest and the open frame did not
  move. Published, only that analysis's digest moved and the open frame turned to the new title and a line chart in 6
  s without a reload. Its numbers gained EU, the card pushed after v1, as publishing that commit should.
- **Dashboard**: the model opened `Embed fixture` by name; the frame reached `ready` with its panels' data.
- **Regression found by the targeted run after that fix**: `{"type": "table"}` inherited the old x and y, so a new
  script's Apply was refused. A table now inherits no axes (with a test).

Seen and left: the frame's caption keeps the title stored with the answer after a republish, and the fallback page's
chip stays under the answer while Atlas is framed.

## 5. Tasks and order

| ID | Task | Depends on |
|---|---|---|
| P1 | `analyses.changes`; `bi_analysis_edit`; the full code in the card; `bi__query` `definition` | — |
| P2 | Analysis AI edits: read tool, merge, enforced slug, diff, stale refusal, page | P1 |
| P3 | K1 accepts edits | P2 |
| P4 | Feed digest test | P1 |
| P5 | Browser test of the card | P1 |
| E1–E5 | §4 | Atlas embed contract |

## 6. Choices inside the decisions

- **A new kind, not a flag on `bi_analysis`**: its create and edit rules are opposite (slug must not exist, must
  exist; whole analysis, only what changes), and the model's description stays plain.
- **A script from the chat runs only after Apply** (§3 P1). The analysis AI keeps running its own scripts while it
  works, as T3 does: that conversation is about this vault's data and the person opened it for this.
- **The edit's base is a digest, not a timestamp**: re-saving the same content is not a conflict.

## 7. Risks and open points

- `_apply_dashboard` stages unit by unit: a run failing partway leaves the earlier units staged (as K1 today; they
  are visible in the working copy and nothing is committed).
- The tool reads Atlas's dashboard list on the default port (8127), while the frame uses the browser's address
  preference, which the server cannot see. An Atlas on another port is framed correctly once named, but its list
  is not read: a dashboard answer on such a PC says Atlas is not running.
- From the chat the model reads the published definition and edits the working copy; when they differ, the card's
  Now column shows what really changes, and the person decides.
