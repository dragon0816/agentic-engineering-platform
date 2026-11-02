# BI: charts in the chat, and where a vault's Dashboard comes from

Status: owner decisions 2026-11-01 (relayed by the BI orchestrator); design by Claude Code the same day.
Builds on `docs/phases/BI_ANALYSIS_DASHBOARD.md` (analyses, `meta:dashboard`, the feed for Atlas, §5 chart
spec) and `docs/phases/BI_TEST_AND_TOOLS.md` §5 (the analysis AI, T3). Decision record: `docs/DECISIONS.md`
2026-11-01 "BI: charts inline in the chat; Dashboards from the analysis AI or an Atlas import".

## 1. Owner decisions

(a) **Charts in the general AI chat are shown inline in the conversation**: a self-contained HTML file in the
existing chat file viewer (sandboxed iframe, `FILE_VIEW_CSP`, no network). Not an Atlas link, not the agent
browser.

(b) **A chart from the chat can be saved as an analysis in a vault, with the owner's approval.** Push and
publish stay the existing manual steps; once published, Atlas shows it (verified in the I2 rehearsal,
2026-11-01).

(c) **The Knowledge page's Dashboard has two sources**: (1) the analysis AI conversation proposes a dashboard
(several analyses plus the `meta:dashboard` order), and (2) an **import from an Atlas dashboard**: only the
order is imported, and `hidden` = the vault's analyses absent from it. AEP reads Atlas's loopback API
server-side (`GET /dashboards`, `GET /dashboards/{name}`; port configurable, default 8127), shows a preview of
the change list, and the owner confirms before anything is staged. Unmatched panels are listed, never invented.

## 2. One chart spec, one renderer

- **Spec**: the analysis chart spec of the feed (§5 of `BI_ANALYSIS_DASHBOARD.md`):
  `{"type": "table"|"bar"|"line"|"scatter", "x"?: column, "y"?: column, "series"?: column}`, checked by
  `analyses.checked_chart` against the result's columns. No new chart vocabulary. (`series` stays accepted and,
  as on the Dashboard tab today, is not drawn.)
- **Renderer**: the BI Dashboard tab's drawing code in `web_page.py` (`biSvg`, `biTableOf`, `biChart`: pure
  DOM/SVG, `textContent` and `setAttribute` only) moves into one Python constant, `BI_CHART_JS` (with its CSS,
  `BI_CHART_CSS`), in `host_runtime/bi_chart_html.py`. The page embeds it where the code is today and the chat's
  HTML file embeds the same constant, so the two cannot drift. **No third-party charting package** (owner: ask
  first).
- **Default chart** for a result without a spec: a `bar` with `x` = the label column and `y` = the number
  column when the result has exactly two columns, one text and one numeric (every non-null value a number);
  otherwise a `table`. Deterministic (`bi_chart_html.default_chart`).

## 3. Part C: charts inline in the chat

What the general chat has today (read 2026-11-01): `bi__query` (`capabilities/bi_cards/capability.py`, read)
answers either the sections of saved analyses (`analysis` = a slug, `all` or `quality`; on a vault the
**published** version) as `{title, chart, columns, rows, truncated, params, ...}`, or, without `analysis`, the
matching **cards** with their fields. There was no ad-hoc SQL in the general chat; C1b adds guarded read-only
SQL (owner decision 2026-11-01). The data reaches only the model; the person sees text.

### C1 `bi__query` results carry a chart

- Analysis sections already carry `chart`; a section whose spec is missing or does not name its columns gets
  the default of §2.
- A card answer (no `analysis`) is shown as a **table** of the cards (name, type and the fields returned to the
  model); it is never charted.

### C2 The turn attaches a self-contained chart HTML

The Host wrapper of `bi__query` (`host_runtime/bi_cards_tools.py`) writes **one HTML file per `bi__query`
call** (all its sections, each drawn by the shared renderer) under the workspace and returns it in
`data["attach"]` as `{path, filename, media_type: "text/html"}`. It is shown inline like the business-card org
chart: `chart_files` (today limited to `cards__org_chart`) also accepts `bi__query`, so the file becomes one of
the answer's `files`, is recorded in the session (rule 20, `SessionArtifacts.record_turn`), and is served only
through the existing sandboxed viewer (`/view/file?nonce=`, `FILE_VIEW_CSP`, `sandbox="allow-scripts"`, no
same-origin). The file:

- holds the result (the rows `bi__query` returned to the model, never more), the chart spec, the title, the
  vault, version (tag/commit) and parameters as one JSON block (`<script type="application/json">`) escaped
  like `business_cards/chart_html._json_for_html`, read with `JSON.parse(textContent)`; text reaches the DOM
  only through `textContent`;
- carries its own meta CSP (as the org chart does) and embeds `BI_CHART_JS`/`BI_CHART_CSS`; no URL, fetch or
  storage;
- is named `bi-<slug|cards>-<stamp>.html`; a cut result says so (`truncated`).

The model's tool result gets `chart_file` (the file name) so it can mention the chart; the numbers it states
must come from the rows (unchanged rule).

### C1b Guarded read-only ad-hoc SQL in the chat (owner decision 2026-11-01)

The owner reversed this design's first choice ("no ad-hoc SQL in the chat"): the general chat may run its own
SQL, guarded and read-only.

- **SQL only**, never a script from the chat. `bi__query` gains `sql` (one statement) and `chart` (the model's
  optional spec); `sql` excludes `analysis` and the card search arguments.
- **Same capability, same path**: `bi-cards/query@1.0.0` (read, no approval) through the Bridge as a
  `CapabilityInvocation` with `origin: model`, under the actor's existing BI grants and audit, like every other
  `bi__query` call. No new capability, no new permission.
- **The published data only**: the statement runs on the store `bi__query` already reads (a vault's
  published version through `vault.reading_store`, a subscribed dataset's read-only copy, a local dataset's
  own data); never on a vault's working copy or unpublished work.
- **The existing guard, not a second one**: `analyses.run_sql` (one statement on a copy opened read-only, an
  authorizer allowing only read actions, so writes, `ATTACH`, `PRAGMA` writes and the like are denied; a
  progress-handler deadline). Its view `card_values` is there as for analyses.
- **Limits**: the analyses' time limit, `SQL_SECONDS` = 10 s; a row cap of **200 rows** for the chat (the
  rows the Dashboard tab's table shows; `run_sql` gets `max_rows`), the result marked `truncated` when cut.
- **Charted like C1**: the model's `chart` when `checked_chart` accepts it for the result's columns, else the
  default of §2; the section (`id` `query`, the SQL in `sql`) goes into C2's page. **Nothing is saved**:
  saving goes through C3 with the owner's approval.

### C3 Save a chart from the chat as an analysis (owner's approval)

Uses the existing pattern for side-effecting actions the AI proposes in chat: **`propose_change`**
(`common/change_proposal.py`, `host_runtime/change_proposals.py`) with a new kind **`bi_analysis`**. The model
proposes; Agent Web shows the change card (Apply/Cancel); the owner's press is the approval
(`POST /api/cards/decide`); a stale fingerprint is refused; the card expires after the pattern's 30 minutes.
**Web only** (not in `TELEGRAM_KINDS`): the owner approves in Agent Web.

Values: `vault` (`vault-<id>`, a vault on this PC), `slug` (must not exist in the vault's working copy),
`title`, `question`, the chart spec, and the analysis itself, **SQL only** (as C1b: never a script from
the chat), either
- `sql`: the statement the model ran with `bi__query`; or
- `from_analysis` `{vault, slug}`: a saved **SQL** analysis of a vault's published version (what the chat
  showed through `bi__query`), copied with its code, params and requires; a script analysis is refused
  (copy it with an analysis pack on the Knowledge page).

The BI side is `host_runtime/bi_chat_save.py` (`now`, `plan`, `apply`), so the generic
`change_proposals.py` names no BI type (ADR-K10). Plan: `analyses.checked`, then `analyses.run_sql` on the
target vault's **working** data with the default parameters, `checked_chart` against the result's columns;
the card's rows show vault, analysis, chart, SQL and the first rows of the result. A problem refuses the
proposal (back to the model). Apply: `analyses.save` (runs and checks again, then **stages**
`analysis:<slug>`). The fingerprint is the working copy's unit under the slug: a save meanwhile makes the
card stale. Commit, push and publish stay the person's manual steps on the Knowledge page; once
published, Atlas shows it.

## 4. Part K: where a vault's Dashboard comes from

`meta:dashboard` = `{"order": [slug, ...], "hidden": [slug, ...]}` (unchanged unit). Both sources below
produce the same thing: some analyses to stage and one new `meta:dashboard`, applied in one step, staged only
(commit and push stay the person's).

**Common rule for `hidden`**: `hidden` = the vault's analyses (saved and newly proposed) whose slugs are not in
the new `order`. Nothing is deleted.

### K1 The analysis AI proposes a dashboard

The analysis AI (T3, `bi_analysis_agent`) gets a tool `bi_analysis__propose_dashboard`: `{reply?, analyses:
[<analysis as for bi_analysis__propose>...], order: [slug, ...]}`, at most 12 new analyses. Each is run
with its defaults and its chart checked (as `bi_analysis__propose` does); `order` lists distinct slugs,
each proposed or already in the vault's working copy (`analysis_session.order_problem`). A problem goes
back to the model, naming the analysis. The suggestion (`aep.bi.analysis_suggestion/v1`, additive keys
`dashboard: {analyses, order}` and `previews: {slug: table}` (200 rows each), `analysis: null`) shows the
order, each new analysis with its preview chart, and 「套用 Dashboard」. Apply
(`analysis_session.apply_suggestion`) checks first and stages nothing if the order no longer holds or a
proposed slug was saved meanwhile (`analysis_exists`); otherwise it stages every analysis and
`meta:dashboard` with `hidden` = the vault's other analyses, and marks the turn applied with the units.

### K2 Import the order from an Atlas dashboard

Contract: Atlas's `docs/AEP_DASHBOARD_READ_CONTRACT.md` (revision 2026-11-01). Its goldens (`list.json`,
`dashboard-mixed.json`, `dashboard-legacy.json`) are vendored byte for byte from Atlas commit `49600737` into
`tests/fixtures/atlas_dashboard_golden/` (`SOURCE.md`, `-text` in `.gitattributes`);
`scripts/check_atlas_dashboard_golden.py --atlas <Atlas repo>` fails on any drift, like Atlas's
`check:aep-bi` (the test runs it when `AEP_ATLAS_REPO` is set).

- **Read** (`host_runtime/bi_atlas_import.py`): Agent Web reads Atlas's loopback API **server-side**, GET
  only: `GET http://127.0.0.1:<port>/dashboards` (names) and `GET /dashboards/{name}` (the name
  percent-encoded as one path segment). Port per request from the Knowledge page (default 8127); no Origin
  header (Atlas accepts loopback callers without one); 5 s timeout; at most 2,000,000 bytes. Atlas's
  400/403/404/413/422 and a refused connection become `atlas_invalid`, `atlas_refused`,
  `atlas_not_found`, `atlas_too_large`, `atlas_unreachable`. Nothing is ever written to Atlas.
- **Match** (`capabilities/bi_cards/atlas_import.plan`, pure): a panel of the vault has `datasource.id`
  `aep.bi.result`, `query.vault` = the vault's id and a nonempty `query.slug`. Sorted by the stored
  `(layout.y, layout.x, id)`; **each (vault, slug) keeps its first panel, later duplicates are listed**.
  A slug the vault has no analysis for is listed (`unknown_analysis`), as are other vaults' and non-AEP
  panels; nothing is invented. `hidden` = the vault's other analyses (working copy).
- **Never imported**: positions, sizes, titles, parameters, transforms, chart specs (Atlas layouts are
  personal, `BI_ANALYSIS_DASHBOARD.md` §8).
- **Routes**: `GET /api/bi/vaults/<id>/atlas-dashboards?port=` (names); `POST
  /api/bi/vaults/<id>/atlas-import {name, port}` is the dry run (order, hidden, the current order, every
  panel with its status, duplicates, unmatched, a token); with `apply: true` and that token it re-reads,
  refuses a changed preview (`preview_stale`) or an empty order (`atlas_nothing`), and stages only
  `meta:dashboard`.
- **Page**: 「從 Atlas 匯入 Dashboard 順序」 under 「分析與圖表」: port, 「讀取 Atlas 的 Dashboard」, a
  picker, 「預覽匯入」 (the order, what becomes hidden, each panel's fate) and 「確認匯入順序」.
- **From a file (owner, 2026-11-02)**, so it works without Atlas running: 「選擇 Dashboard 檔案」 sends the file's text
  as `file` to the same route, with the same dry run, token and confirm, and the same `plan`. Strict JSON (a repeated
  key or `NaN` is `atlas_invalid`), at most 2,000,000 bytes (`atlas_too_large`), a schemaVersion 2 document. `file`
  with `name` is `atlas_source_ambiguous`. The file is never run or stored: the page keeps the text in memory and sends it
  again to confirm. Only `plan` reads it, so its other content goes nowhere, and no model is involved. A saved file is
  the same document as the GET body but not the same bytes (Atlas: indented, a final newline), so it is compared parsed,
  never by hash: the token comes from the plan.

## 5. Tasks and order

| ID | Task | Depends on |
|---|---|---|
| C1 | `bi__query` carries `chart` (saved spec, model's checked spec, or the default) | — |
| C2 | The turn attaches the self-contained chart HTML (shared renderer); browser test: renders in the chat file viewer | C1 |
| C1b | Guarded read-only ad-hoc SQL in `bi__query` (published data, 10 s, 200 rows, charted like C1) | C1, C2 |
| C3 | Save a chat chart as an analysis (SQL only): proposal → owner's approval → `analyses.save` (staged) | C1, C1b |
| K1 | The analysis AI proposes a dashboard (analyses + order) applied in one step | — |
| K2 | Import the order from an Atlas dashboard (dry run, confirm, unmatched and duplicates listed) | Atlas golden files |

Each slice: tests first, `ruff format --check`, `ruff check`, `mypy src tests`, the targeted tests, one commit,
a row in `docs/TASKS.md`. The full suite once at the end (not overlapping Atlas's I1).

## 6. Choices inside the decisions

- **C3 uses `propose_change`**, not the Bridge's `approval_required` capability path (`ap-` approvals) and not
  the draft-install card: `propose_change` is the pattern for "the AI proposes a change to this PC's state,
  the owner applies it in Agent Web", with fingerprint, expiry and a web-only switch.
- **One HTML per `bi__query` call**, not one per section: `analysis="all"` would otherwise flood the answer.
- ~~The general chat gets no ad-hoc SQL tool~~: reversed by the owner (2026-11-01), see C1b.
- **K2 order from geometry** (`layout.y`, then `layout.x`): what the person sees in Atlas, independent of the
  document's panel array order.

## 7. Risks and open points

- A chat result can be large: the HTML holds only the rows `bi__query` already returns (its row cap), so the
  file stays small; the note says when rows were cut.
- The chat reads the **published** version (P4); a chart saved from the chat is staged in the working copy,
  where the analysis is re-run on the working data by `analyses.save` (numbers can differ from the chat's if
  the working copy has unpublished cards; the save's own run is what is checked).
