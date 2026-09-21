# Handoff — Phase 5 model gateway, slice 2 (OpenAI-compatible adapter)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-5/openai-adapter`, based on `main` after PR #34 merged.

## Goal

Phase 5 slice 2: the first provider adapter. One `ModelClient` over the OpenAI
chat-completions format, serving the internal company gateway, a LiteLLM proxy
or any other OpenAI-shaped API. Requirements:
`docs/phases/PHASE_5_GATEWAY.md` (slice 2); decisions:
`docs/PHASE_5_MIGRATION.md` (slice 2); contracts: `docs/CONTRACTS.md`
("OpenAI-compatible adapter").

## Owner decisions still in force (taken 2026-09-21)

1. Provider adapters are in-process code under `src/models/`; a proxy, if ever
   deployed, is a host artifact. The platform never starts a provider process
   and takes no new runtime dependency.
2. Providers are Ollama and the internal OpenAI-compatible gateway. Codex and
   Claude Code are out of scope in both senses, which is why the source's
   LiteLLM proxy is not migrated at all.

## Completed

- `src/models/openai_compatible.py`: `OpenAICompatible` implementing
  `ModelClient`, plus the injected `Transport`/`Reply` protocols and the
  standard-library `UrllibTransport`.
  - `generate` maps roles, text, images as content parts, `max_tokens` and
    `response_format: json_object` for a declared `output_contract`; fills
    `text` always and `structured_output` only on strict JSON; reads usage,
    ignoring the internal deployment's extra fields.
  - `stream` yields a `text` event per non-empty delta then `done`,
    reassembling lines across chunk boundaries and skipping a `choices`-less
    prelude, comments and unparseable payloads.
  - Every failure is typed: `model_timeout`, `model_unreachable`,
    `model_http_error` (retryable on 408, 429 and 5xx), `model_unparseable`,
    `model_error`, `streaming_not_declared`, `tools_not_supported`. Messages
    are truncated and redacted through the existing `SECRET_PATTERN`.
  - The credential is a callable resolved per request, because the source's
    token is rewritten on a schedule.
- 13 tests (`tests/test_openai_compatible.py`), none opening a socket: the
  round trip, images and an output contract, per-request credential
  resolution and its own failure, streaming including a split line, a
  non-stream reply and the undeclared-streaming refusal, every transport
  failure, every HTTP status class with a redacted body, unparseable replies,
  both tool refusals, the configurable token field, construction errors, and
  the default transport's request construction, error mapping and redirect
  refusal.
- Docs: slice 2 requirements in the phase spec, the slice 2 source-first
  decision (ADAPT `Gateway.send`, with each replacement and its reason), and
  the contract section.
- PR #35 review (6 findings) applied: the default opener **refuses
  redirects**, because urllib copies `Authorization` to wherever a 3xx points
  and drops the POST body, which would have leaked the internal token; a
  replayed exchange carrying `tool_calls` on its messages is refused like a
  tool request rather than sent without them; a 2xx reply carrying no
  server-sent events is `model_unparseable` instead of a silent empty success
  that discards the answer; the token limit field is configurable
  (`max_tokens_field`) for providers that dropped `max_tokens`; resolving the
  credential is its own `credential_unavailable` rather than an unreachable
  endpoint; and an endpoint declaring a credential with no resolver supplied
  is refused at construction.

## In Progress

- Nothing; the PR is open with the review applied.

## Remaining

- Slice 3: `ollama` adapter, satisfying `local_only`. New platform work; the
  source repository contains no Ollama integration, so there is nothing to
  characterize. Its wire format is not OpenAI's, so it is a separate adapter
  rather than a base URL change.
- Slice 4: the credential resolution boundary (`SecretRef` to value), with an
  environment-backed development resolver outside the platform's import path.
  The adapter already takes a callable, so this slice supplies it rather than
  changing the adapter.
- Slice 5: observability and a complete inert requirements-to-response example.
- Deferred from Phase 3: a payload sweep, process-liveness or lease-based
  suspension, and the earlier deferred reviews.
- Deferred from Phase 4: a retrieval cache, host wiring that plans from an
  adopted document, a size-and-mtime shortcut for adopted-file drift checks,
  and image description for legacy `raw/`.

## Architecture decisions made

- A non-2xx status is an answer the transport reports, not an exception, so
  the adapter decides retryability rather than the transport.
- A timeout is distinguished from a refusal, because only one of them suggests
  trying a different endpoint.
- The `Transport` arguments are plain values, never a contract, so an
  `Authorization` header cannot land in something serializable.
- An `output_contract`'s name is never sent to a provider; the provider is
  asked for JSON and the caller validates the shape it already knows.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 591 passed, 3 skipped (link privileges)
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

No model, gateway, network, real vault, job or n8n instance was invoked. Every
test in this slice injects a transport or replaces `urlopen`; nothing opens a
socket.

## Known issues / limitations

- Tool calling is refused rather than mapped. `ModelTool.input_contract` names
  a platform contract and there is no registry that can render it as a
  provider function schema. No caller in the platform sends tools today.
- `max_tokens` is the default token-limit field, which the internal
  deployment and LiteLLM both accept; a provider that dropped it needs
  `max_tokens_field="max_completion_tokens"` passed per client. Nothing reads
  this from the catalog yet, because it is adapter knowledge rather than a
  platform capability.
- A response's `tool_calls` are not read back, for the same reason tools are
  not sent.
- Retryability is reported but nothing retries yet; a caller decides.
- `model_error` stays retryable, because a custom transport may raise its own
  transient exception types. An adapter bug therefore reads as retryable.
- `UrllibTransport` opens one connection per request with no pooling, matching
  the source. An async or pooled transport is an alternative implementation of
  the same protocol, not a change here.

## Next Recommended Action

Merge PR #35 on green CI. Then write the slice 3 requirements section and
implement the `ollama` adapter against its own wire format, reusing the
`Transport` protocol introduced here.
