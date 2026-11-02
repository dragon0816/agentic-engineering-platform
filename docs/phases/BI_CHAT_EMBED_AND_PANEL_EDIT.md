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
`chart`, `sql` **or** `script`, `params`, `requires`. Omitted fields keep their value; `params: {}` or
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

Waits for the Atlas embed contract (Atlas worker, branch `atlas-embed`). This section gets the URL format and the
goldens from that commit; nothing here guesses them.

| ID | Task |
|---|---|
| E1 | Vendor the contract's goldens byte for byte, with a drift check |
| E2 | A chat answer part: an iframe to Atlas's embed route. The host builds the URL from vault, slug and parameters or a dashboard name; the model never supplies a URL. The Atlas address is the existing per-browser preference (default `http://127.0.0.1:8127`). `sandbox="allow-scripts allow-same-origin"`, `referrerpolicy="no-referrer"`; the frame is sized from the contract's postMessage, accepted only from the Atlas origin |
| E3 | Fall back to the C2 HTML with a note when Atlas does not answer |
| E4 | A tool or `bi__query` option for the model to ask for an embed; listing dashboards by name through the server-side read `bi_atlas_import` already does |
| E5 | Browser test with a stub Atlas on a loopback port; real-model live acceptance in a temp workspace |

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
- From the chat the model reads the published definition and edits the working copy; when they differ, the card's
  Now column shows what really changes, and the person decides.
