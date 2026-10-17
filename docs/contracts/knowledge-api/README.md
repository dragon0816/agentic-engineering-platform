# AEP Knowledge API, contract v0.1 (for the Atlas Coding Agent)

**Status:** draft of 2026-10-17, part of Knowledge Strategy v1.2 (`docs/proposals/KNOWLEDGE_STRATEGY_v1.2.md`
§6, ADR-K7). Awaiting owner confirmation. **No AEP route serves this API yet**: AEP-K09 builds it after the
owner approves v1.2. Atlas can build against the mock files now, without PostgreSQL, a vault or a
running AEP Knowledge Service. **Owner:** AEP. **Consumer:** Atlas.

| File | What it is |
|---|---|
| `openapi.yaml` | OpenAPI 3.1: 14 GET operations in five groups, scopes, error responses, mock examples |
| `schemas/*.schema.json` | JSON Schema 2020-12 for the envelope, the error and every `data` shape |
| `mock/*.json` | Synthetic responses: complete envelopes, as AEP would return them |
| `mock/index.json` | For each mock: method, path, query, scope, HTTP status and the schema of its `data` |

AEP's own consistency check is `tests/test_knowledge_strategy_docs.py`. It validates every mock against its
schema, and checks the mock graph against BI Schema v0 and the benchmark draft.

## 1. Conventions (same as the telemetry contract)

These follow `docs/telemetry/AEP_ATLAS_TELEMETRY_CONTRACT.md` v0.3, which Atlas already consumes.

- **Envelope:** every response has the form `{schema_version, contract_version, request_id, generated_at,
  source, data, pagination, warnings, error}`. `schema_version` is `"aep.knowledge.v1"`; `contract_version` is
  `"0.1"`. Exactly one of `data` and `error` is non-null.
- **Versioning:**
  - A new optional field raises only `contract_version` (to `0.2` and so on).
  - Removing a field or changing its meaning needs `aep.knowledge.v2`.
  - **Atlas must ignore unknown fields and unknown enum values.** AEP validates its own output strictly
    (`additionalProperties: false`), but the schemas describe the producer, not a consumer contract.
- **Format:** fields are snake_case. Timestamps are UTC RFC3339 with `Z`. Ids are strings.
- **Pagination:** cursor based. `limit` defaults to 50 and is at most 500; `pagination.next_cursor: null` ends
  the list. Single-object responses have `pagination: null`.
- **Read only:** GET only, with no write routes. Only **published** content is returned; drafts are never
  searchable.
- **Provenance and data source:**
  - `source` on every envelope: `producer` (`aep-agent-web` / `aep-knowledge-service` / `mock`), `backend`,
    `vault`, `vault_version` (a digest), `schema_id` and `synthetic`.
  - Each entity and relationship carries `provenance`: `document_ids`, `evidence_ids`, `strategy_id`,
    `strategy_run_id`, `extracted_by` (Skill `namespace/name@version`), `extracted_at` and `schema_id`.
  - A strategy run carries `workflow_run_id` and `trace_id`. `GET /api/v1/telemetry/runs?trace_id=<trace_id>`
    returns its Harness runs.
- **Errors:**
  - The error object is `{code, message, retryable, http_status, details}`; `code`, `message` and
    `retryable` are the fields of AEP's `Failure` (`src/common/execution.py:92`).
  - Codes: `invalid_request` (400), `scope_required` / `origin_refused` (403), `not_found` (404),
    `conflict` (409), `backend_unavailable` (503), `unsupported_version` (400) and `internal_error` (500).
  - Examples: `mock/error_not_found.json`, `mock/error_scope_required.json`.
- **Warnings:**
  - `content_withheld`: fields were nulled for lack of scope, with a count.
  - `classification_filtered`: records above the caller's ceiling were left out, with a count only.
  - `synthetic_data`: the data is synthetic (every mock carries it).
  - `partial_backend`: one backend failed.
  - `truncated`: the result was cut at a limit.

## 2. Endpoints (five groups)

| Group | Operation | Default scope |
|---|---|---|
| Entity Query | `GET /api/v1/knowledge/entities` (`entity_type`, `q`, `market_segment`, `review_status`) | metadata |
| | `GET /api/v1/knowledge/entities/{entity_id}`: entity, claims, relationship counts | metadata; claim statements need content |
| Relationship / Graph Query | `GET /api/v1/knowledge/relationships` (`relationship_type`, `subject_entity_id`, `object_entity_id`, `graph_state`) | metadata |
| | `GET /api/v1/knowledge/graph` (`seed`, `depth` 1–3, filters): `{nodes, edges}` | metadata; sensitive labels need content |
| Evidence Query | `GET /api/v1/knowledge/evidence` (exactly one of `document_id`, `entity_id`, `relationship_id`, `claim_id`) | metadata; `text` needs content |
| | `GET /api/v1/knowledge/evidence/{evidence_id}` | metadata; `text` needs content |
| | `GET /api/v1/knowledge/documents`, `/documents/{document_id}` | metadata; title and paths need content |
| Knowledge Quality Metrics | `GET /api/v1/knowledge/quality/summary` | metadata |
| | `GET /api/v1/knowledge/quality/benchmark-runs` (`suite`, `retrieval_mode`) | metadata |
| Strategy Run Status | `GET /api/v1/knowledge/strategies` | metadata |
| | `GET /api/v1/knowledge/strategy-runs` (`strategy_id`, `status`), `/strategy-runs/{strategy_run_id}` | metadata |
| (service) | `GET /api/v1/knowledge/health` | metadata |

Deferred to contract v0.2 or later:
- `POST /query` (question answering): it calls a model, so it would need its own scope,
  `knowledge.query`.
- Conflicts, feedback and review-queue routes.
- Any write.

## 3. Scopes and the token question (Q10): recommendation, pending owner confirmation

| Scope | Returns | Phase 1 access (recommended) |
|---|---|---|
| `knowledge.read.metadata` | Ids, types, canonical keys, statuses, counts, metrics, run status, evidence locators, and the labels of non-sensitive types | Like telemetry: GET, loopback only, **no token**, cross-origin only for pages on this machine (`127.0.0.1`, `localhost`, `[::1]`) |
| `knowledge.read.content` | Evidence `text`, claim `statement`, document `title` / `original_ref` / `raw_ref`, and `display_name` / `aliases` of Account, CustomerProduct and Opportunity or of any CONFIDENTIAL / RESTRICTED record | A **bearer token** issued in Agent Web settings that names this scope |

Why the split:
- Passage text and customer names are content. The telemetry API never returns content (its §4), and its
  token-free rule was decided for redacted metadata only.
- Splitting by scope keeps that rule for the metadata Atlas needs most (graph shape, states, metrics, run
  status) and puts content behind a token.

Without the content scope, AEP returns the record with those fields set to `null` and sets
`display_name_redacted`, `statement_redacted`, `text_redacted`, `content_redacted` or `label_redacted` to
`true`. Graph nodes get the label `"<Type> (redacted)"`. A `content_withheld` warning counts the records.

Separately from scope, a **classification ceiling** applies:
- AEP never returns a record above the caller's ceiling.
- In Phase 1 the ceiling for loopback callers follows the vault's `privacy` setting. CONFIDENTIAL is
  never served to Atlas until ADR-K8 is decided.
- The mock includes CONFIDENTIAL synthetic records only so that the redaction UI can be built.

Atlas work this implies, not in AEP:
- Today's AEP provider in Atlas sends no credentials (Atlas `docs/AEP_TELEMETRY_INTEGRATION.md`). Content
  views therefore need either a token setting in the trusted custom provider or a mock-only mode until the
  owner decides.
- A metadata-only Atlas view works with no change to the provider's credential handling.

## 4. Mapping to what Atlas already reads

The mapping is checked against the Atlas repository's `applications/rs_knowledge/` (read only):

- **Graph:**
  - `data` of `/graph` is `{nodes: [...], edges: [...]}`, the shape `web/src/platform/dataset.ts`
    `normalizeGraph` requires. Node ids are non-empty unique strings; edges carry `source`, `target`, `type`,
    `state` and `weight`.
  - Node and edge `state` use the `graph_states` vocabulary of `schemas/quality-model.yaml`: `covered`, `weak`,
    `missing/inferred`, `conflict/disputed` and `stale`. AEP derives it from claim modality:
    - verified → covered;
    - assumed → weak;
    - inference → missing/inferred;
    - disputed → conflict/disputed.
  - A node is `stale` when its card's `updated` date is more than 90 days old. This is the BI Knowledge Base
    rule; the entity carries `updated` and `stale`.
  - Atlas's `graph_path` (Market → Application → Technology → Requirement → Measurement → Product → Competitor)
    maps onto BI Schema v0 like this:
    - Market becomes `market_segments` properties and the `market_segment` filter;
    - Requirement and Measurement are Application;
    - Product is TestSolution or CustomerProduct.
    - The BI analysis chain (Trend → Technology → Node → Ecosystem → CustomerProduct → Application →
      TestSolution → Opportunity) is a better default path for a BI view.
- **Gaps:** `quality/summary.gaps[].gap_type` uses Atlas's `gap_taxonomy` (`SOURCE_GAP` … `SYSTEM_ERROR`).
- **Filters:**
  - Atlas's `market` binding corresponds to `market_segment`; the values are `src/knowledge/market_matrix.py`
    `TargetMarket`.
  - `technology` corresponds to entity ids of type Technology.
  - `benchmark_version` and `run_id` correspond to `benchmark-runs` fields.
- **Envelope:** as with telemetry, a generic REST source cannot unwrap the envelope. Use a dedicated custom
  provider, the way `web/src/platform/aep/provider.ts` does for telemetry.

## 5. Mock data

- Everything is **synthetic**:
  - accounts Alpha, Beta, Gamma, Delta, Epsilon, Sigma and Tau;
  - Ecosystem supplier companies Kappa, Lambda, Mu, Nu, Xi, Omicron and Pi;
  - competitors "Competitor A" and "Competitor B";
  - documents titled `合成：…`;
  - evidence text starting `（合成段落）`.
- No real customer, supplier, product or market claim is included. Technology names (Wi-Fi 7/8, 5G-RedCap,
  5G FWA, CPO, 800G, GaN, 800V DC, 77 GHz radar, 6G, NTN) are public vocabulary.
- Types and relationship names follow BI Schema v0 (`docs/proposals/bi_schema_v0/`), which carries the
  types and link fields of the owner's BI Knowledge Base document, such as `related_tech`, `affects_nodes`,
  `node`, `technologies`, `applications`, `competing_solutions` and `vendor`.
  - In that document, Ecosystem cards are supplier or partner companies.
  - Account cards are customers.
  - Node is a fixed set of value-chain positions.
- Size: 91 entities (all 12 types), 163 relationships (all 14 relationship names), 163 claims, 167 evidence
  passages and 10 documents.
- The mock exercises:
  - two stale cards;
  - one disputed claim;
  - inference-only Opportunity links;
  - one Application with no solution;
  - Technologies without a Concept.
- The mock graph is the gold graph of the benchmark draft (`docs/proposals/knowledge_benchmark_v0/`). Every
  expected entity and triple of the 25 questions exists in it, and the test enforces this.
- Scope variants: `entities.json` vs `entities.metadata.json`, `documents.content.json` vs `documents.json`,
  `evidence_detail.json` vs `evidence_detail.metadata.json`, and `graph_seed.json` (content) vs `graph.json`
  (metadata).
- The benchmark-run numbers in `quality_benchmark_runs.json` are **made up** to exercise the UI. They are
  flagged `synthetic: true`, `ground_truth_status: draft-unreviewed` and `indicative: true`. They are not
  results.

## 6. Change process

- AEP owns this contract and changes it here, in the AEP repository.
- Atlas records its consumer work in the Atlas repository, as it does for telemetry.
- A field Atlas needs becomes an additive `contract_version` bump.
- Freezing v0.1 jointly before AEP-K09 starts is recommended in v1.2 §6.
