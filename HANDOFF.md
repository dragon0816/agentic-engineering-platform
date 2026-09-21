# Handoff — Phase 5 complete; next is the Phase 6 specification

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-5/observability`, based on `main` after PR #37 merged.

## Goal

Phase 5 slice 5: per-call latency beside the token counts, and a complete
inert example a host can copy. With it the Phase 5 exit criteria are met, so
this branch also closes the phase in the status documents. Requirements:
`docs/phases/PHASE_5_GATEWAY.md` (slice 5); contracts: `docs/CONTRACTS.md`
("Model observability and the worked example").

## Phase 5 summary (PRs #34–#38, all merged to `main`)

| Slice | PR | What landed |
|---|---|---|
| 1 catalog and selection | #34 | `ModelCapabilities`/`ModelEndpoint`/`ModelCatalog`, deterministic selection against declared requirements, typed misses, validation at construction |
| 2 OpenAI-compatible adapter | #35 | `ModelClient` over chat-completions, injected transport, per-request credential, typed failures, redaction, no redirect with a token attached |
| 3 Ollama adapter | #36 | `ModelClient` over Ollama's native `/api/chat`, and `models.wire` extracted as the rules two adapters must not differ on |
| 4 credentials and construction | #37 | `CredentialResolver`, `credential_for`, `EnvironmentCredentials`/`StaticCredentials`, `ModelClients` with a provider registry and per-alias options |
| 5 observability and example | #38 | `duration_ms` on responses and terminal stream events, `models.proof` |

Exit criteria (Roadmap Phase 5): local Ollama and the internal
OpenAI-compatible gateway satisfy the same `ModelClient`; credentials are
externalized; provider-specific handling stays isolated in `src/models/`, and
the runtime install is still `pydantic` alone.

## Owner decisions that shaped the phase

1. Provider adapters are in-process code; a proxy, if ever deployed, is a host
   artifact, and the platform never starts a provider process (2026-09-21).
2. Providers are Ollama and the internal OpenAI-compatible gateway. Codex and
   Claude Code are out of scope in both senses (2026-09-21). Consequently the
   source's LiteLLM proxy was not migrated at all: it existed to terminate the
   Anthropic wire format for Claude Code, and the company gateway is already
   OpenAI-compatible.
3. Remaining Phase 5 slices were to be completed without check-ins unless
   something could not be decided (2026-09-22).

## Completed in this slice

- `duration_ms` on `ModelResponse` and `ModelStreamEvent`, measured by both
  adapters with `wire.Elapsed` on a monotonic clock, from just before the call
  to after the reply is read. A stream reports on its terminal event; a
  request refused before any call reports zero.
- `src/models/proof.py`: `SAMPLE_CATALOG` as plain data, `clients_from` and
  `ask`, the whole chain from declared requirements to an answer without
  naming a provider, a model id or a URL.
- 5 tests (`tests/test_models_proof.py`), none opening a socket: the sample
  catalog validating and passing the repository's own secret guard, the chain
  answering through both providers, a routing failure staying a `Failure`, a
  resolver needed only where a secret is declared, measured durations with the
  clock replaced, and a stream timing only its terminal event.
- Phase 5 closed in `docs/ROADMAP.md`, `docs/ARCHITECTURE.md` and `README.md`.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available.

## Remaining

- **Phase 6 specification** (`docs/phases/PHASE_6_EVALUATION.md`) before any
  Phase 6 code, then repoint `CLAUDE.md`, which still names
  `docs/phases/PHASE_5_GATEWAY.md` as the active phase. Decisions to take with
  the owner first: whether the coding agent (Codex and Claude Code, excluded
  from Phase 5 as model providers) enters Phase 6 as a `CapabilitySpec` behind
  the Host Bridge, and which of the three evaluation categories the first
  slice covers.
- Deferred from Phase 3: a payload sweep, process-liveness or lease-based
  suspension, and the earlier deferred reviews.
- Deferred from Phase 4: a retrieval cache, host wiring that plans from an
  adopted document, a size-and-mtime shortcut for adopted-file drift checks,
  and image description for legacy `raw/`.
- Deferred from Phase 5: tool calling in either adapter (it needs a registry
  that can render a contract as a provider schema), reading `tool_calls` back
  off a response, retry behaviour (retryability is reported, nothing retries),
  a pooled or async transport, and a production credential backend.

## Architecture decisions made

- Latency belongs on the response beside usage, because evaluation compares
  aliases on both and a separate observation channel would have to be
  correlated back.
- A stream is timed on its terminal event rather than per delta: the question
  is how long the provider took, not how far apart its tokens were.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 612 passed, 3 skipped (link privileges)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

No model, gateway, network, real vault, job or n8n instance was invoked
anywhere in Phase 5.

## Known issues / limitations

- **The Ollama adapter has never been run against a live Ollama server.** It
  is written to the documented native chat API and covered by tests with an
  injected transport. Before anyone relies on it, run one real request and
  confirm the field names, particularly `prompt_eval_count`/`eval_count` and
  the streaming `done` flag. The same caution applies to the company gateway:
  no real endpoint was contacted in this phase.
- `duration_ms` measures the adapter's view, which includes transport and
  parsing. It is not the provider's own reported latency.
- Credential resolution is not counted in `duration_ms`, deliberately, since
  it is not the provider's time.
- `SecretRef.name` is a `Symbol` and a JWT matches that pattern, so the type
  system still cannot prove a name is not itself a secret.

## Next Recommended Action

Open the PR for `phase-5/observability`, run the review, apply confirmed
findings and merge on green CI. Then agree the two Phase 6 decisions above
with the owner, write `docs/phases/PHASE_6_EVALUATION.md`, repoint `CLAUDE.md`
at it, and start the first Phase 6 slice on a `phase-6/...` branch.
