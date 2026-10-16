# Suggested Skills from experience (design)

Owner request: 2026-10-16. Status: **design approved 2026-10-16 (decisions at the end); implementation queued.** Nothing in this
document is implemented. The owner wants it built next; the open questions at the end
need an answer first.

## 1. Why

Hermes nudges its agent to save a skill after repeated work (`creation_nudge_interval`)
and writes it itself. AEP deliberately never lets the Agent add or change a Skill or
Workflow on its own (AGENTS.md rules 13 and 15; `docs/phases/EXPERIENCE_REVIEW.md`
principle 1): a model may not install or approve what changes behaviour. The owner still
wants AEP to **notice reusable work and offer it** as a Skill or Workflow draft, which a
person then creates, refines and installs through the paths that already exist.

The rule this design keeps: **the Agent suggests and drafts; only a person's button
creates a draft, and only the Capabilities Install press installs it.**

## 2. What exists and what this reuses (code survey 2026-10-16)

| Piece | Where | Used for |
|---|---|---|
| Conversation history | `host_runtime/conversations.py` `ConversationRecord` (per `actor`, at most 100 messages, credential-shaped text redacted on save), stored in the Host state SQLite `conversations` table (`host_runtime/state.py`) | Mining requests: user message text, answer status, rating and note, `tool_summary` (one line per tool: name, status, failure code, Workflow files), `workflow_form`, `reply_to` |
| Run telemetry | `telemetry.sqlite` `runs` / `events` (`telemetry/store.py`, run kinds `conversation_turn`, `workflow_run`, `capability_call`, ...); metadata only, never content | Long runs: tool count, duration and outcome per turn |
| Experience cases and nightly review | `host_runtime/experience.py` (harvest from conversations, benchmarks, telemetry; `experience.sqlite`; retention setting), `experience_review.py` (`run_review`, one model call per group, structured output, `experience-reviews/review-*.json`), the nightly loop `AgentWeb.start_experience_nightly` (after 02:00, only with new cases) | The schedule, the store and the model-call pattern; suggestions are a second harvest and a second finding kind in the same nightly job |
| Review proposals | `host_runtime/experience_proposals.py` (`ProposalStore`, statuses proposed / accepted / rejected / snoozed / done, reject needs a reason, snooze 7 days), `review_routes.py`, Reviews tab in `web_page.py` (`rvCard`, tabs "To decide" / "Accepted" / "Snoozed" / "Rejected or done") | The card list, the decisions and their audit fields (`decided_by`, `decided_at`, `reason`). The store has no `actor` field today; suggestion records add one so each member sees only their own (principle 2) |
| Lexical tokens with CJK | `knowledge/query.py` `tokens` (lower-cased words; CJK runs give characters, bigrams and the run) | Similarity without a model call (section 4.1) |
| Draft and check | `host_runtime/skill_authoring.py` (`assemble_skill`: the host sets owner, `private`, `draft`, version 1.0.0; `check_skill`: no `rules` or `script_tools`, instructions required and secret-free, command targets installed, name and alias not taken), `chat_authoring.py` (`check` / `draft` / `draft_skill`, candidates under `workspace/authoring/chat/`, `source` field, `install_now` behind the Install button), `external_authoring.py` (`check_skill`, `check_workflow`) | The suggestion's draft is created as an ordinary candidate with `source: suggestion:<id>`; nothing new can install |
| Typed Workflow parameters | `common/assets.py` `WorkflowParameter` (kind, `scope` static/runtime, choices, defaults), `common/workflow_forms.py` `form_fields` | The run form a drafted Workflow would show, previewed on the card |
| Action card | `common/action_cards.py` `ActionCard` (buttons, preview, `link` to a tab, `web_only`, Telegram rendering) | The optional end-of-conversation suggestion card |

Missing: anything that looks *across* conversations for repeated or reusable work
(today's harvest only collects failures), a `skill_suggestion` proposal kind, and a
route from a proposal to a Skill or Workflow candidate.

## 3. Principles

1. **Suggest, never create on its own.** A suggestion is a card. The draft candidate
   exists only after the person presses **Create draft**; it is installed only by the
   Capabilities **Install** press, as every candidate today.
2. **Only the person's own work.** Mining reads only conversations and runs whose
   `actor` is the person the suggestion is for. On a shared test workstation (several
   members on one Host) each member's suggestions are mined and shown separately.
3. **Evidence first.** Every suggestion links the conversations it came from (session
   and message ids, dates, the request excerpts). No evidence, no card.
4. **Nothing secret in a draft.** Inputs are already redacted on save; the draft is
   checked again with `SECRET_PATTERN` and `reject_embedded_secrets`; concrete values
   seen in the evidence (paths, mail addresses, hosts, numbers) become typed parameters,
   not constants (section 6.3).
5. **Cheap by default.** Detection needs no model call. The model writes a draft only
   for a cluster that already passed the thresholds, inside the nightly job's budget.
6. **No duplicates.** A suggestion that overlaps an installed Skill or Workflow, a
   pending candidate or an open suggestion becomes an update proposal or is dropped.

## 4. Signals

All signals are computed in a new harvest `from_reuse(records, telemetry)` beside
`from_conversations` / `from_telemetry` in `host_runtime/experience.py`, over the
person's conversations in the retention window (default 30 days, the existing setting).

### 4.1 Repeated similar requests across sessions (main signal)

- **Unit.** One *request*: a user message that opened a piece of work (the first message
  of a session, or one not marked `reply_to` and not a short follow-up such as "ok",
  "thanks", "繼續"), together with the answer and its `tool_summary`.
- **Similarity without a model call (recommended).**
  - Text: token sets from `knowledge.query.tokens` (handles mixed Chinese and English),
    with stop words and pure numbers/dates removed; weighted Jaccard (IDF over the
    person's own requests) between two requests.
  - Tool shape: the ordered set of tool names in `tool_summary` (for example
    `files.read → excel.read → mail.draft`). Two requests with the same tool shape get a
    bonus; a Workflow run by name is a strong match on its own.
  - Score = 0.6 × text similarity + 0.4 × tool-shape similarity; requests are joined by
    single-link clustering above the threshold (section 5).
  - Deterministic, explainable on the card ("matched words: 週報, 2026_W, Excel; same
    tools"), unit-testable, runs in milliseconds for hundreds of requests.
- **LLM pass in the nightly review (optional, second stage).** For each cluster that
  passed the deterministic thresholds, the draft call (section 6) also returns
  `same_task: true/false` and a one-line task statement; `false` drops the cluster.
  This removes false joins without a model call per pair. A pure LLM clustering pass
  over all requests is rejected: cost grows with history, it sends more text to the
  endpoint, and it is not reproducible.

### 4.2 Long multi-step successful runs

- A turn whose answer is `answered`, not down-rated, with at least **5 tool calls**
  (from `tool_summary`, or `conversation_turn` telemetry) and no failed tool, or an
  agent-mode turn with at least 5 allowed steps.
- One such run alone is a *weak* candidate; it becomes a suggestion when it repeats
  (4.1) or when the person rated it up. Rationale: a long success that never recurs is
  not worth a Skill.
- When the tool sequence and values are fixed across runs, the suggestion is a
  **Workflow** draft; when the steps vary with judgement, a **Skill** draft (section 6.1).

### 4.3 Repeated corrections

- Pattern: an answer followed, in the same session, by a user message that corrects it
  ("不是這樣", "should be", "use X instead", "記得要...", a down-rating with a note), and
  then a successful answer. The correction text is the evidence.
- The same correction (similar by 4.1's text measure) in **at least 2 sessions** is a
  signal for a Skill draft whose instructions carry the correction as a rule, or for an
  **Update existing** proposal when the corrected work used an installed Skill.
- Corrections about Knowledge facts are not handled here: they stay with the existing
  experience review (gap list, rule edits in a sandbox).

## 5. Thresholds and sensitivity

One setting, **sensitivity**, picks a row (owner can tune after the live trial):

| Sensitivity | Repeated requests (4.1) | Similarity | Long runs (4.2) | Corrections (4.3) | Max new cards per night |
|---|---|---|---|---|---|
| Low | ≥ 4 requests in ≥ 3 sessions on ≥ 3 days | ≥ 0.6 | repeat ≥ 3 times | ≥ 3 sessions | 1 |
| **Normal (default)** | ≥ 3 requests in ≥ 3 sessions on ≥ 2 days | ≥ 0.5 | repeat ≥ 2 times, or 1 up-rated | ≥ 2 sessions | 3 |
| High | ≥ 2 requests in ≥ 2 sessions | ≥ 0.4 | any one up-rated run ≥ 5 steps | ≥ 2 sessions | 5 |

Always applied: requests inside one session never count as "repeated" on their own;
a cluster fully covered by an installed Skill's deterministic command or an installed
Workflow run by name is dropped (the person already has it); at most 2 model calls per
cluster and the existing review caps (`MAX_GROUPS`) per night.

## 6. The draft

### 6.1 Skill or Workflow

The nightly job decides the draft type deterministically, before the model call:

- **Workflow draft** when every run in the cluster used the same capabilities in the
  same order and only values differed (fixed steps). It runs the same every time and
  shows a form.
- **Skill draft** otherwise (judgement, varying tools, or a correction rule). The Skill's
  `instructions` say how to do the task; its `commands` may point at installed
  capabilities or Workflows, so a command that targets a Workflow still opens that
  Workflow's form.

### 6.2 Model call

One structured call per surviving cluster, through the same company endpoint and alias
the review already uses (`experience_review._ask` pattern; output contract
`skill_suggestion_draft`). Input: up to 8 request excerpts with their tool summaries
(already redacted), the installed catalog (`ExternalAuthoring.catalog`: capabilities,
Workflows, Skills with aliases), and the authoring formats (`skill_format` /
`workflow_format`). Output:

```json
{"same_task": true,
 "task": "one line: what the person keeps asking for",
 "why": "two sentences citing requests by number",
 "draft_kind": "skill | workflow",
 "draft": { "...the author's part, exactly what check-skill / check-workflow accept..." },
 "parameters": [{"name": "week", "kind": "text", "label": "Week (2026_31W)",
                 "from_examples": ["2026_30W", "2026_31W"]}],
 "overlaps": ["engineering/sde-weekly-report@1.0.0"]}
```

### 6.3 Typed parameters and no secrets

- Values that differ between the evidence requests (a week, a file path, a model name,
  a recipient) become **typed parameters** (`WorkflowParameter` kinds such as `text`, `number`,
  `date`, `file`, `folder`, `emails`, or `select` with the seen values when there are few), so the
  card can show the form and the person is asked at run time. A value that is the same
  in every request may become a `static` per-install setting, never a constant in the
  shared manifest.
- Concrete values seen in evidence are offered only as `examples`, never as `default`.
- The assembled draft is passed through `assemble_skill` / `chat_authoring.check`, then
  `check_skill` / `check_workflow`. A draft that fails the check is **retried once** with
  the problems given back to the model; if it still fails, the suggestion is shown
  without a draft ("Suggested, draft needs work: <problems>") and **Create draft** is
  replaced by **Draft it with Claude Code** (opens the creator-skill instructions with
  the evidence). Any `SECRET_PATTERN` hit discards the draft outright.

### 6.4 Dedupe

Before the model call, and again on the model's `overlaps`:

1. **Installed** Skills and Workflows (`installed_skills`, `installed_workflows`): same
   Workflow run by name in the evidence, or token similarity of the task statement with
   a Skill's `instructions` / `selector_hint` ≥ the sensitivity threshold → the card
   becomes **Update existing** (only if the person owns or co-edits it; otherwise it
   says which Skill already covers it and is shown only once).
2. **Pending candidates** in `authoring/chat/` (any source) → "a draft already exists",
   link to it; no new card.
3. **Open, snoozed or rejected suggestions** with overlapping evidence or a similar task
   statement → no new card; new evidence is added to the existing open one ("seen 2
   more times"). A rejected suggestion is not proposed again unless at least as many
   *new* requests as the threshold arrive after the rejection.

## 7. Where it shows

1. **Reviews tab (primary).** A new proposal kind `skill_suggestion` in the existing
   `ProposalStore`, labelled "Suggested Skill" or "Suggested Workflow" in `RV_KINDS`. The
   card shows: the task line; why (with the matched words and tool shape); the evidence
   list (each entry opens that conversation at the message); the draft (instructions or
   steps, read-only preview); the **run form preview** rendered with `form_fields` from the
   draft's parameters; overlaps; confidence. It appears under "To decide" with the other
   proposals and is counted in `rv-counts`.
2. **End-of-conversation suggestion card (optional, off by default).** When a turn just
   completed the 3rd (Normal) matching request, the answer may carry a small
   `ActionCard` (kind `skill_suggestion`, `web_only: true`): "You have asked for this 3
   times. Make it a Skill?" with **Show suggestion** (link to the Reviews card) and
   **Not now**. This uses the deterministic signal only, no model call in the turn;
   the draft is generated by the next nightly job or on demand when the person opens
   the suggestion. At most one such card per session and per suggestion.
3. **Telegram: link only.** If the end-of-conversation card is on and the turn came from
   Telegram, the reply gets one line: "A suggested Skill is waiting in Agent Web →
   Reviews" with the Agent Web address. No buttons, no draft text in Telegram.

## 8. Actions

| Button | Effect |
|---|---|
| **Create draft** | Creates a Skill or Workflow candidate through `ChatAuthoring.draft_skill` / `draft` with `source: suggestion:<proposal id>`, owner the person, `private`, lifecycle `draft`. The proposal becomes `accepted`, route `candidate:<id>`. The card then offers **Open in Capabilities** (the candidate, where **Install** lives) and a hint to refine it with Claude Code first (creator skills and the authoring MCP are installed by default). |
| **Update existing** | Shown instead of (or beside) Create draft when 6.4 found an installed Skill or Workflow the person may edit. Creates a candidate that is the existing manifest plus the proposed change (new instructions rule, new parameter, new command), with the diff on the card; installing it goes through the normal version bump. |
| **Ignore** | Maps to the existing `reject`; a short reason is asked but optional for suggestions ("not useful", "one-off", "wrong grouping" quick picks). Recorded so the same evidence is not suggested again. |
| **Snooze 7 days** | The existing `snooze`. |

The Agent never has a tool for these buttons: they are Agent Web routes
(`/api/reviews/decide` with new actions `create_draft`, `update_existing`), outside
the model's reach, exactly like today's proposal decisions and approvals.

## 9. Never self-install

- No code path from a suggestion to `install_skill` / `install_now`; tests assert that
  creating a draft leaves the skills and workflows folders unchanged.
- A candidate made from a suggestion is indistinguishable from any other candidate
  except for its `source`; Install, run approval for non-read-only Workflows and grants
  work as they do today.
- Publishing to the Shared Platform stays the separate "Publish to the shared platform"
  card.

## 10. Audit and telemetry

- The proposal record keeps the evidence ids, sensitivity in force, decision, actor,
  time and reason (existing fields), plus the candidate id it created.
- Each nightly run writes its suggestion findings into the same
  `experience-reviews/review-*.json` (a `suggestions` list beside `findings`), so the
  report shows what was considered and why it was dropped (dedupe, thresholds, check
  failure).
- Telemetry events under the existing `experience_review` run kind:
  `review.suggestion_detected`, `review.suggestion_drafted`,
  `review.suggestion_decided`; counts and ids only, never request text. Atlas can then
  show suggestions → drafts → installs.
- A Task row "Skill suggestions (nightly)" only when the job made a model call.

## 11. Settings

In Reviews → "Review settings and the latest report" (stored in
`experience-settings.json`, additive fields):

- **Suggest Skills from my repeated work**: on / off (default **on**, nightly only; the
  harvest costs no model call, drafts cost at most the per-night cap);
- **Sensitivity**: Low / Normal / High (default Normal);
- **Offer a suggestion card at the end of a conversation**: on / off (default off).

Turning suggestions off stops new detection; existing cards stay until decided.

## 12. Tests

- **Similarity:** Chinese, English and mixed requests; numbers and dates ignored;
  identical tool shape bonus; single-link clustering; the explanation words.
- **Signals:** repeated requests across sessions vs inside one session; long successful
  runs; corrections in 2 sessions; thresholds per sensitivity; only the actor's own
  conversations (a second actor's identical requests never join).
- **Dedupe:** installed Skill, installed Workflow run by name, pending candidate, open,
  snoozed and rejected suggestions; new evidence appended to an open card.
- **Draft:** fake model returns a valid Skill draft, a valid Workflow draft with typed
  parameters, an invalid draft (retry with problems, then "needs work"), a draft with a
  secret (discarded); examples never become defaults.
- **Actions:** Create draft makes a candidate with `source: suggestion:<id>` and installs
  nothing; Update existing diff; Ignore records the reason; Snooze returns after 7 days;
  the model's tools cannot reach any of them.
- **UI:** headless render of the Reviews card with evidence, draft and form preview;
  the end-of-conversation card (web) and the Telegram link line.
- **Budget:** at most the per-night cards and 2 model calls per cluster; no model call
  when suggestions are off.

## 13. Phased plan

| Slice | What | Done when |
|---|---|---|
| S1 | Deterministic detection: `from_reuse` harvest, similarity and clustering, thresholds, dedupe against installed and pending; findings written to the nightly report only (no cards) | A nightly run on this PC's last 30 days lists clusters the owner agrees with; tests |
| S2 | Reviews card without draft: `skill_suggestion` kind, evidence links, Ignore / Snooze, settings (on/off, sensitivity) | Cards appear and decisions are recorded |
| S3 | Draft generation: model call, Skill/Workflow choice, typed parameters, check-skill / check-workflow with one retry, form preview; **Create draft** to a candidate | A suggestion becomes a candidate that the owner installs with the Install button |
| S4 | **Update existing** proposals and corrections signal | One correction turned into an update candidate |
| S5 | End-of-conversation card and Telegram link line; telemetry events | Card shown on the 3rd matching request; Atlas counts |
| S6 | Two-week live trial, then decide default sensitivity and whether the end card is on by default | Owner review of suggestion quality |

## 14. Open questions for the owner

1. **Similarity method.** Deterministic lexical + tool-shape clustering, with the
   nightly draft call confirming `same_task` — or a model pass over all requests?
   *Recommended:* deterministic first, model only to confirm surviving clusters.
2. **Default thresholds.** Is "3 similar requests in 3 sessions on at least 2 days"
   (Normal) the right bar for a first suggestion? *Recommended:* yes, with at most 3 new
   cards a night.
3. **End-of-conversation card.** Off by default (Reviews only), or on?
   *Recommended:* off by default; turn it on after the S6 trial if the cards prove
   useful.
4. **Where suggestions are reviewed on a shared workstation.** Each member sees only
   their own (mined from their own conversations) — or the machine owner sees all?
   *Recommended:* each member only their own; nobody sees another person's requests.

## Owner decisions (2026-10-16)

1. **Similarity: the model judges** (overrides the recommendation in 4.1). The nightly job
   sends the person's own request excerpts (already redacted on save) with their tool
   shapes to the configured model through the internal gateway, in batches, and asks it to
   group requests that are the same task and to name each group. The deterministic
   score in 4.1 is kept only as a cheap pre-filter that drops obvious one-offs and caps
   the batch size, and as the explanation shown on the card; it never joins requests by
   itself. Budget: at most one grouping pass per night over requests new since the last
   pass plus the open groups, with a hard cap on requests per pass (setting).
2. Threshold for a first suggestion: **3 requests in 3 sessions over at least 2 days**,
   at most 3 new cards a night (Normal).
3. End-of-conversation card: **off** until after the trial (S6); Reviews tab only.
4. Shared workstation: **each member sees only their own suggestions.**
