# AEP → Atlas Harness Telemetry Contract, v0.2

**Status:** the AEP side is implemented (2026-10-08). The Atlas side is not built yet. **Owner:** AEP. **Consumer:** Atlas.

This version replaces the v0.1 draft (`AEP_ATLAS_TELEMETRY_CONTRACT_v0.1.md`, supplied by the owner). The event envelope is unchanged and stays `schema_version: "aep.telemetry.v1"`. Everything below that differs from v0.1 is marked **v0.2**.

## 1. What v0.1 got wrong, and how v0.2 settles it

| # | v0.1 issue | v0.2 decision |
|---|---|---|
| 1 | It assumed Atlas has a collector, an event-level stream merge and replay. The Atlas repo today has none of these. Its WebSocket replaces a whole snapshot per message (20,000 rows, 8 MiB), and its REST sources are plain GETs. | The owner chose to build the AEP side only. AEP is the store, the history and the stream. The work Atlas needs is listed in §8. |
| 2 | It required authenticated reads, but a browser data source in Atlas cannot send an `Authorization` header and rejects tokens in URLs. | The owner decided Atlas reads without a token. The read routes are GET only, on loopback only, and allow cross-origin reads only from pages on this machine (`127.0.0.1`, `localhost`, `[::1]`). Any other `Origin` is refused, which keeps a web site in the same browser out. Events are redacted metadata (§4). Every other Agent Web route still needs its token. |
| 3 | `sequence` is per run, yet the stream cursor `after_sequence` has to span runs. | `sequence` stays per run. Each stored event also gets **`ingest_seq`**: host-wide and monotonic, assigned by the store. It is the cursor for the stream and for backfill. It is returned beside the event object and is not part of it. |
| 4 | It did not say what a "Harness run" is. | **`attributes.run_kind`**: `conversation_turn`, `workflow_run`, `knowledge_query`, `coding_change` or `capability_call`. **`attributes.parent_run_id`**, together with the run's `parent_span_id`, nests one run inside another; a Workflow started by a conversation tool is an example. |
| 5 | Nothing in AEP produced `strategy_id`. | `strategy_id` = `st-` + a 12-hex hash of: `build` (git commit, plus `+dirty`), `model_alias`, `accelerator`, `limits`, `skills_digest` (the installed Skill versions) and an optional `strategy_label`, which the owner sets in `<workspace>/telemetry.json`. Each component is repeated on `run.started`, so a change can be explained, not only detected. |
| 6 | `context_tokens` is not available. | AEP model responses report only input and output tokens, so `context_tokens` is omitted rather than estimated. A call whose usage was not reported has `input_tokens: null`. `run.completed` carries `token_reports`, the number of calls that did report usage. |
| 7 | `state` was open with no vocabulary, so state graphs would not compare. | The recommended states are listed in §3. `state` is still an open string. |

## 2. Envelope (unchanged from v0.1)

The fields are `schema_version`, `event_id` (UUID hex), `run_id`, `trace_id`, `span_id`, `parent_span_id`, `sequence` (per run, starting at 0, contiguous), `timestamp` (UTC RFC3339), `event_type`, `state` and `status` (`started|succeeded|failed|skipped|cancelled`). `attributes` holds safe metadata.

**Spans.** The run has its own span (`run.started` and `run.completed`). Two kinds of operation sit under it:
- **State spans:** a `state.entered`/`state.exited` pair, or `state.entered` followed by `tool.completed`, sharing one `span_id`.
- **Point events:** `llm.completed`, `skill.selected`, `routing.completed`, `verification.completed` and `retry.scheduled`. Each has its own `span_id`, and its parent is the enclosing span.

**Durations.** `duration_ms` is measured at the source with a monotonic clock.

## 3. Event vocabulary and where AEP emits it

| run_kind | Emitted |
|---|---|
| conversation_turn | `run.started`, `routing.completed` (Agent Web `route`: `command`, `command_rule`, `knowledge_direct`, `market_matrix` or `converse`; or the request router's `origin`), `skill.selected` (offered and selected counts, `skill_ids`, provider, fallback), the state `model` with `llm.completed` inside it, the state `tool` that ends in `tool.completed` (`tool_id`, `loop_index`, `failure_code`), `retry.scheduled` (`model_output_truncated`), and `run.completed` (`outcome`, `llm_calls`, `tool_calls`, tokens, `duration_ms`) |
| any | `tool.completed` with `layer: "bridge"` for every Bridge capability call (`tool_id` = `namespace/name@version`) |
| workflow_run | Uses the Workflow `run_id`. The state `step` (`step_index`, `tool_id`) and `retry.scheduled` (`transient_failure`) |
| knowledge_query | `state.entered` for `collecting`, `executing` and `validating`, then the terminal phase; `verification.completed` (`validator` = the check id); `retry.scheduled` (`validation_failed`) |
| coding_change (inside its tool span) | `state.entered` for `plan`, `change` and `validate`; `verification.completed` (`validator: declared_commands`); `retry.scheduled` (`repair`) |

Every model call the host makes produces an `llm.completed` event. That covers routing, Knowledge synthesis, coding authoring and conversation turns. The fields are `model_alias`, `duration_ms`, `input_tokens`, `output_tokens`, `max_output_tokens`, `tools_offered`, `tool_calls` and `failure_code`.

## 4. Redaction

`telemetry.events.sanitize` runs before an event is stored:
- Values may only be scalars, short lists and shallow objects. Strings are cut to 300 characters.
- Keys that name content are dropped: prompt, message, text, content, answer, question, document, payload, body, script, password, secret, token (except the token-count keys), api_key, authorization and credential.
- Any string that looks like a credential is replaced by `[redacted]`.

No prompt, answer, retrieved passage, file or tool payload is ever an attribute.

## 5. Read API (Agent Web, loopback)

```
GET /api/v1/telemetry/health
GET /api/v1/telemetry/runs?limit=50&cursor=<started_at|run_id>&kind=&status=&since=&until=
    → {runs:[{run_id, run_kind, parent_run_id, trace_id, started_at, ended_at, status,
              strategy_id, skill_id, model_alias, duration_ms, llm_calls, tool_calls,
              input_tokens, output_tokens, failure_code, outcome, complete}], next_cursor}
GET /api/v1/telemetry/runs/{run_id}/events?after_sequence=N&limit=500
    → {events:[event + ingest_seq], next_sequence}
GET /api/v1/telemetry/events?after_ingest_seq=N&limit=1000&since=&until=
    → {events:[...], next_ingest_seq}           # history replay over a time window
GET /api/v1/telemetry/stream?after_ingest_seq=N  # WebSocket, one event (+ ingest_seq) per text message
```

- **The stream:** `after_ingest_seq=-1` starts live. Any other value backfills first, then continues live. To reconnect, pass the last `ingest_seq` seen.
- **Run status:** a run without `run.completed` stays `started` with `complete: false`.

**JSONL export:**
```
aep-host telemetry export --config <host.json> [--since RFC3339] [--run ID] [--out file.jsonl]
```
It writes the §2 event objects only, without `ingest_seq`.

**Sample:** `docs/telemetry/aep-telemetry-v1-sample.jsonl` was produced by the real code paths. It holds a conversation turn with a truncation retry, a tool call and token usage; a Workflow run; and an interrupted Knowledge run.

## 6. Storage, retention and performance

- **Store:** `<workspace>/telemetry.sqlite` (WAL), separate from the Agent's state file. `event_id` is unique, so ingest is idempotent.
- **Retention** (owner): whole runs are dropped once older than 30 days, then the oldest beyond 500 MB.
- **Emission:** `put_nowait` onto a bounded queue (20,000). One writer thread batches the inserts. A full queue drops the event and counts it in `health.dropped`; telemetry never raises into the harness. Measured on the owner's machine: about 8 µs per event and 19 µs per state span.
- **Off switch:** `{"enabled": false}` in `telemetry.json` turns recording off.

## 7. Metrics Atlas computes (unchanged from v0.1)

- Latency: `run.completed.duration_ms`, or the timestamp difference.
- LLM calls and token sums, with token coverage = `token_reports / llm_calls`.
- Loop count: the highest `loop_index`. Repeated states and edges come from adjacent `state.entered` events. Retries are `retry.scheduled`. Dwell time is the state span's `duration_ms`.
- Compare strategies by `strategy_id`, together with `skill_id` and `run_kind`, on the same benchmark cases. Report p50, p95 and the failure rate.

## 8. Atlas work this contract needs (not done; owner: Atlas)

1. **A `custom` provider, or server routes, that consume the event stream.**
   - Keep an event index keyed by `event_id`, ordered by `(run_id, sequence)`, and persist `ingest_seq` to resume from.
   - Today's WebSocket source replaces a whole snapshot, so it cannot consume per-event messages.
2. **Views:**
   - the run list from `/runs`;
   - a timeline from one run's events, using the span tree;
   - a state graph built from adjacent `state.entered` events in each run;
   - a heatmap of state × strategy with dwell time and loops.
3. **REST sources** can already poll `/runs` (`refresh`) for a live run list without any new code. Their rows are the flat run summaries above.
4. **Tolerance:** accept unknown `event_type` values and extra attributes, keep incomplete runs visible, and never invent missing events.

## 9. Versioning

- The envelope stays `aep.telemetry.v1`. The v0.2 additions are optional attributes (`run_kind`, `parent_run_id` and the strategy components) and the out-of-band `ingest_seq`, so v0.1 consumers still parse every event.
- A breaking change needs `aep.telemetry.v2`.
- AEP's tests (`tests/test_telemetry.py`) cover:
  - ordering, nesting and per-run sequences;
  - null usage when it was not reported;
  - redaction, deduplication and retention;
  - emission that never blocks;
  - Workflow runs;
  - the read API, its origin rule and the WebSocket backfill-then-live stream.
