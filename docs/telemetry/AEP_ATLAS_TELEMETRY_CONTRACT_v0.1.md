# AEP → Atlas Harness Telemetry Contract (Draft v0.1)

Status: **proposal, not yet implemented or approved**. Owner: AEP. Consumer: Atlas. Date: 2026-10-08.

## 1. Responsibilities
- **AEP** defines the versioned event schema, instruments the Harness, owns authoritative local traces, enforces redaction/access control, and exposes read-only retrieval or a secure exporter.
- **Atlas** ingests and stores a derived copy, supports filters, aggregation, timelines, transition graphs and heatmaps. It must not reinterpret or mutate source events.
- **Both** run consumer-driven contract tests against the same fixtures.

Existing AEP code: `src/common/trace.py` defines `ExecutionTrace` with route/dispatch/outcome, ordered events, total duration, model calls and token counts; `src/common/evaluation.py` defines `ObservedRun`. These are foundations, **not** the fine-grained loop/span telemetry described here.

## 2. Event envelope (JSON Lines, one JSON object per line)
Required:
- `schema_version`: `"aep.telemetry.v1"`
- `event_id`: globally unique UUID; deduplication key
- `run_id`: logical Harness run
- `trace_id`: cross-component correlation identifier
- `span_id`: operation instance
- `parent_span_id`: nullable parent operation
- `sequence`: monotonic integer **per run** (allocated at the event source)
- `timestamp`: UTC RFC3339 with timezone
- `event_type`: e.g. `state.entered`, `state.exited`, `llm.completed`, `tool.completed`, `verification.completed`, `run.completed`
- `state`: open string, not a hardcoded enum
- `status`: `started|succeeded|failed|skipped|cancelled`
- `attributes`: safe structured metadata; no raw prompts, retrieved documents, credentials or tool payloads by default

Recommended `attributes`: `strategy_id`, `skill_id`, `tool_id`, `model_alias`, `loop_index`, `duration_ms`, `input_tokens`, `output_tokens`, `context_tokens`, `context_limit_tokens`, `failure_code`, `retry_reason`, `progress_signal`. Token usage may be null/omitted when unavailable; do not treat missing as zero.

Event `span_id` connects start/end of an operation; `parent_span_id` supports nesting. A sequence number preserves ordering even if network delivery is out of order. State transitions can be derived from adjacent `state.entered` events within a run; optionally emit `state.transitioned` with `from_state` and `to_state` when explicitly observed. Never infer causality from timestamps alone.

## 3. Minimum event vocabulary
`run.started`, `run.completed`, `state.entered`, `state.exited`, `routing.completed`, `skill.selected`, `llm.completed`, `tool.completed`, `verification.completed`, `retry.scheduled`.
`run.completed` includes final outcome; a run may be incomplete when interrupted. `verification.completed` records validator identity and pass/fail, not an unsupported assertion of correctness.

## 4. API contract (proposal)
AEP local read-only endpoints (or equivalent authenticated export):
- `GET /api/v1/telemetry/runs?limit=50&cursor=...` → run summaries + pagination cursor.
- `GET /api/v1/telemetry/runs/{run_id}/events?after_sequence=N&limit=500` → ordered event array + `next_cursor` or `next_sequence`.
- `GET /api/v1/telemetry/stream?after_sequence=...` → optional authenticated WebSocket stream; messages use the **same** event objects.

For an initial MVP, **JSONL export/import is sufficient**; do not require a network server. Atlas can own a read-only collector and WebSocket-to-browser service later. Avoid making AEP execution depend on Atlas availability. Support reconnect and backfill, idempotent ingest by `event_id`, and per-run ordering by `sequence`.

Security: private-by-default; actor/device/tenant authorization on reads and streams; TLS for remote transport; redact before persistence/export; bound event size, retention and queue; telemetry failure must not fail Harness. Prefer local append-only SQLite or JSONL with asynchronous bounded writer.

## 5. Dashboard acceptance criteria
1. Load supplied JSONL and show run list + filtering by strategy, status, model, skill and time.
2. Render timeline with nested spans and durations.
3. Render state-transition graph showing path, repeated edges and failure reasons.
4. Render loop-efficiency heatmap grouped by state and strategy.
5. Reproduce same panels for streamed events without schema translation.
6. Handle out-of-order delivery, duplicate events, missing token usage and interrupted runs.
7. Never display secrets/raw confidential payloads.

## 6. Metrics (computed, not claimed)
- End-to-end latency: `run.completed.timestamp - run.started.timestamp` or monotonic duration when measured at source.
- LLM call count; summed available tokens; coverage of token reporting.
- Loop count; repeated state/edge count; retry count; per-state dwell time.
- Benchmark success rate only when independently validated.
- `progress_signal` is an optional evidence-backed signal, **not** a correctness label.
Compare strategies on the same benchmark cases and environment. Show p50/p95 latency and failure rate, not only averages.

## 7. Implementation handoff
**AEP / Codex**: add versioned Pydantic contracts; safe emission hooks around routing, conversation model calls, tool execution, validation and run lifecycle; local bounded writer; JSONL export; tests for redaction, event ordering, dedupe and no-blocking behavior. Preserve existing `ExecutionTrace` and Bridge authorization. Do not change routing strategy as part of instrumentation.

**Atlas / 鐵柱**: consume the attached fixture and this contract; implement schema validation, JSONL upload, event indexing, filters, run timeline, state graph and heatmap. WebSocket support can follow after offline import passes. Do not invent missing events or assume every run completes.

## 8. Verification and versioning
Contract tests: parse valid fixture; reject missing `event_id`; tolerate unknown `event_type` and extra `attributes`; idempotently ingest duplicates; reorder by `(run_id, sequence)`; keep incomplete run visible; block unredacted secret fields. Breaking changes require a new `schema_version`. No live AEP data has been verified against this proposal.
