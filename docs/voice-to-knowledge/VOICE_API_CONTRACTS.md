# Proposed voice contracts (mock v0; not AEP Knowledge v0.1)

No HTTP route, auth token, service owner or production compatibility is claimed. #234 must
approve a formal JSON Schema/OpenAPI and review owner before a real adapter is connected.

STT provider consumes a local validated audio path and fixed decoding configuration, returns
immutable segments (start/end/text), detected language and model identity. Errors are explicit;
a partially consumed generator is not success. Audio never goes to an external STT/LLM.

Draft carries schema/skill/model versions, source ID, audio hash, original transcript/hash,
claims, source spans/times, verification status and generated Markdown. Each claim is fact,
observation, inference or uncertain; all require a verbatim source span. Inference additionally
requires its basis. Fact means asserted in the source, not independently verified. Unknown
fields remain absent. Raw transcript is never rewritten by normalization or extraction.

Mock identity is a trusted caller argument, never taken from transcript. Tenant+actor scoped
create/read permissions; no publish capability. A request key is scoped to tenant+actor;
identical canonical payload returns the same draft, changed payload conflicts. Replays still
check current permissions. Response: mock marker, draft_id, draft status, revision, request_id.
Errors: permission_denied, invalid_request, not_found, idempotency_conflict; non-retryable.

Mock review/publish is deliberately absent: it cannot assert human approval or write Knowledge.
No persistent multi-process authorization guarantee: the in-memory mock only demonstrates
consumer contract behavior. Production durability, concurrency, retention/deletion, ceilings,
byte/duration limits, actor mapping and approval audit ownership require Leo's decision.
