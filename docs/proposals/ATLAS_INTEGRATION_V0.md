# Atlas integration: an agent conversation that builds dashboards (v0, proposal)

> **Status.** Proposal, owner decisions recorded (2026-10-27). Nothing here is implemented. The `/v1`
> contract and the Atlas tool list need review before code.
>
> **Scope.** The Atlas analysis dashboard (`atlas-analysis-dashboard`, Python standard-library server
> plus a web client) gets an embedded agent conversation. The user asks in plain language; the agent
> connects sources, runs the computations, and returns a dashboard layout that Atlas renders.

## 1. Owner decisions (2026-10-27)

| # | Question | Decision |
|---|---|---|
| D1 | Is AEP a separate service or embedded? | **AEP is a separate external service.** Atlas calls it over HTTP. |
| D2 | Whose model and data permissions? | **Atlas and AEP share one integration account.** Every Atlas user's turn runs as that account. |
| D3 | Can the first version save a dashboard? | **No.** The first version is read-only with respect to saved state: it previews, it does not save. |

Consequences of D2 that the rest of this document depends on:

- AEP cannot tell Atlas users apart. Every turn has the integration account's grants, model policy and
  data-classification rules, whoever typed the question.
- **Atlas must enforce per-user limits itself**: which sources a user may query, and which of their turns
  may run. AEP's approvals and grants do not do this for them.
- The audit trail has two layers: AEP records the turn under the integration account; Atlas records the
  Atlas user, the request and the turn id. Neither alone answers "who asked".
- Data classification applies to the integration account. If a source is more sensitive than the
  account is allowed to send to the model gateway, that source must not be reachable from the chat
  (Atlas refuses it in the tool, not the prompt).

Consequences of D3:

- No tool writes to a dashboard store. The agent's output is a **dashboard spec** that the browser
  renders as a preview. Leaving the page loses it, as it does today for an unsaved edit.
- Save, share and publish are out of scope. They come later, as a side-effecting tool behind an AEP
  approval, after a separate design.

## 2. Architecture

```
Browser (Atlas web client: chat box + dashboard preview)
   │  same-origin requests only
Atlas server (Python standard library)
   │  holds the AEP integration credential; never sent to the browser
   │  enforces the Atlas user's source access before forwarding anything
AEP /v1 (external API, new)
   │  session → turn → agent run
   │  the agent calls Atlas tools through a registered external tool endpoint
Atlas tool endpoint (new, narrow, read-only)
   │  list sources · test source · preview · run pipeline (no save) · validate spec
```

- The browser never talks to AEP. This keeps the credential server-side and lets Atlas apply its own
  access checks before anything reaches the model.
- AEP calls back into Atlas for data. Data stays where the source is; AEP sees results only as tool
  output that it is allowed to send to the model.

## 3. AEP `/v1` contract (draft)

Authentication: `Authorization: Bearer <integration credential>`. The credential is scoped to the
integration account, has an expiry, and is revocable. Its value is never printed or logged.

| Method and path | Purpose |
|---|---|
| `POST /v1/sessions` | Create a conversation for one Atlas user. Body: `external_user_ref` (Atlas's opaque id, for audit only), `client: "atlas"`. |
| `POST /v1/sessions/{id}/turns` | Send one user message. Body: `text`, `context` (current dashboard spec id, selected source refs, optional), `idempotency_key`. Returns `turn_id`. |
| `GET /v1/turns/{turn_id}` | Status and, when finished, the result (below). |
| `GET /v1/turns/{turn_id}/events` | Server-sent events for progress: `status`, `tool_started`, `tool_finished`, `text_delta`, `done`. |
| `POST /v1/turns/{turn_id}/cancel` | Stop a running turn. |

Turn result:

```json
{
  "turn_id": "…",
  "status": "succeeded | failed | cancelled | refused",
  "text": "Markdown answer for the chat",
  "citations": [{"source_ref": "…", "locator": "…"}],
  "dashboard_spec": {"schema": "atlas.dashboard_spec/v1", "…": "…"},
  "errors": [{"code": "…", "message": "…"}],
  "trace_id": "…"
}
```

Rules:

- `dashboard_spec` is validated by Atlas against its own schema before it is shown. AEP does not
  interpret panels. If validation fails, the turn is still returned, with the errors, so the chat can
  say what went wrong.
- `refused` means policy blocked the turn (for example a source the integration account may not send
  to the model). The reason is a stable code, not free text.
- `idempotency_key` makes a retried POST safe: the same key returns the same turn, so a side effect
  cannot run twice (AGENTS.md rule 21).
- Versioned under `/v1`. Breaking changes need `/v2`. Unknown fields are ignored by clients.

## 4. Atlas tools the agent may call (first version)

All read-only. Each tool is called with the Atlas user's identity, and Atlas checks that user's source
access before doing anything.

| Tool | What it does | Notes |
|---|---|---|
| `atlas.list_sources` | Lists the sources this user may use. | Returns refs and names, never connection secrets. |
| `atlas.test_source` | Checks that a source responds and returns its shape. | Bounded by the existing size and timeout limits. |
| `atlas.preview_data` | Returns a bounded sample of a dataset. | Row and byte caps; truncation is marked. |
| `atlas.run_pipeline` | Runs an existing pipeline (filter, join, aggregate, …) and returns the result in memory. | Writes nothing. Uses the same engine as the dashboard. |
| `atlas.validate_spec` | Checks a candidate `dashboard_spec` against the schema and lists errors. | Lets the agent fix its own output before returning. |

Excluded from the first version: saving or sharing a dashboard, creating or editing sources, storing
credentials, and anything that writes to disk or to a remote system.

Each tool has a stable name and an input/output schema in Atlas. Atlas marks all five as read-only, so
AEP does not ask for approval for them.

## 5. What AEP has to add

1. An external integration credential type with scope, expiry and revocation.
2. The `/v1` session, turn, status, event stream and cancel endpoints above.
3. A structured turn result with the `dashboard_spec` field (AEP passes the spec through; it does not
   validate its panels).
4. Registration of external tools (the five Atlas tools) with a read-only flag and a per-tool input
   schema. Today AEP's tools come from its own Bridge and MCP paths; this is a new source.
5. An `external_user_ref` field on sessions, kept for audit and not used for authorization.
6. Turn idempotency keys.

## 6. What Atlas has to add

1. A server-side proxy for `/v1` with the credential in server configuration, never in the browser.
2. Per-user source access, checked in the tool endpoint for every call.
3. The five read-only tools, using the existing pipeline engine.
4. `atlas.dashboard_spec/v1` with a validator and a renderer for the chat preview.
5. The chat panel: streaming progress, the answer, the preview, and "start over".
6. A sign-in model. Atlas is loopback-only today; it must not be exposed to more than one user until
   there is authentication (open question O1).

## 7. Risks

- **Shared credential**: one leaked credential gives every Atlas user the integration account's reach.
  Mitigation: scope, expiry, rotation, and server-side storage only.
- **Model egress**: the chat sends tool output to the model gateway. Data classification must be
  checked against that gateway for each source (AEP `data_policy`).
- **Latency**: several tool calls plus model turns can take tens of seconds. The progress stream is
  required, not optional.
- **Spec drift**: Atlas's renderer and the agent's spec can diverge. The schema version and
  `validate_spec` are the guard.

## 8. Open questions and owner answers (2026-10-27)

- **O1. Sign-in.** Owner: 「好的」, read as agreeing that sign-in is deferred. Atlas is used only on this
  computer today, so the first version needs no sign-in. **Blocker before any second user** (see §6.6).
- **O2. Sources that may reach the model.** Owner: Atlas and AEP run on one computer, so any data this
  computer can read may be used. Recorded as the owner's decision. The data-classification check (§7)
  still applies to the integration account; this answer decides *which* data, not *whether* the check
  runs.
- **O3. Repository.** Owner: the repository and local folder named in this document,
  `atlas-analysis-dashboard`. Local copy: `Documents/claude/atlas-analysis-dashboard`.
- **O4. Scope of `/v1`.** Owner: general, not Atlas-only. The session, turn, event and cancel parts are
  AEP-wide; the Atlas tools (§4) are one registered tool set.

## 9. Proposed slices

1. **AEP `/v1` skeleton**: credential, session, turn, status, cancel, a fake agent that returns a fixed
   spec. Tests with fake clients only.
2. **Atlas tool endpoint**: the five read-only tools against demo data, with per-user checks.
3. **Atlas proxy and chat panel**: streaming progress, answer and preview, against the fake AEP from
   slice 1.
4. **Live integration** on a throwaway AEP and Atlas, then with the real integration account.

Each slice ends with lint, type check and tests, and a handoff entry. No slice saves dashboards.
