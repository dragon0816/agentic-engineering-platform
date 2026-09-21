# Phase 5 — Model gateway

Implementation scope derived from the approved Roadmap (Phase 5) and
Architecture ("Model interface", "Model router", "Provider adapters / model
gateway", rule 6: platform code must not depend on a concrete provider SDK).
The layer to reach:

```text
declared ModelRequirements
  -> ModelSelector          (deterministic alias selection, no model call)
     -> ModelEndpoint       (alias -> provider, model id, capabilities, SecretRef)
        -> provider adapter (ModelClient over one wire format)
           -> Ollama | any OpenAI-compatible endpoint
```

The source is the gateway tooling in `dragon0816/knowledge_management`
(`gateway.py`, `litellm-config.yaml`, `start-gateway.ps1`, `refresh-token.ps1`,
`check-model.ps1`, `agent/agent.py`), pinned at
`2f5e6d0431c5b6af8fbee05c6c0a5779e1a84bb9`. Source decisions are recorded in
`docs/PHASE_5_MIGRATION.md`. Exit criteria from the Roadmap:

- at least local Ollama and the internal OpenAI-compatible gateway satisfy the
  same model client interface;
- credentials are externalized.

## Invariants

These hold for every slice and are enforced in code, never by convention:

1. **One provider-neutral contract.** Agent, Knowledge, Workflow and Skill
   code depends only on `models.contracts`. No provider SDK, wire object or
   base URL reaches them. This is already true after Phase 4: every model call
   in the platform goes through `ModelClient`.
2. **A provider or model change is configuration, not code.** Callers name a
   stable alias; the catalog maps the alias to a provider, a model id and the
   capabilities that endpoint actually has.
3. **Selection is deterministic.** The router matches declared requirements
   against declared capabilities and returns the same alias for the same
   inputs. No model is called to choose a model.
4. **Secrets are references in contracts and values only at the edge.** A
   `ModelEndpoint` declares a `SecretRef`; the value is resolved by the
   execution environment and handed to an adapter. No adapter reads an
   environment variable, and no contract ever carries a token.
5. **Credentials never reach a message, a log or a `Failure`.** Provider error
   bodies are truncated and redacted before they become a `Failure.message`.
6. **Every provider failure is a typed status.** A transport error, a timeout,
   an HTTP error, an unparseable body and a refused request all become
   `ModelResponse.failure` or a `failed` stream event. Nothing escapes an
   adapter as an exception, as in Phase 4's knowledge code.
7. **The platform never starts a provider process.** The LiteLLM proxy, Ollama
   and the company gateway are deployments the host runs. The platform is
   given a base URL and a resolved credential, so "started next to the agent"
   and "deployed elsewhere" are the same code path.
8. **No new runtime dependency.** Adapters speak HTTP through an injected
   transport whose default implementation is the standard library, so the
   platform's install stays `pydantic` alone and every test runs without a
   network.

## Requirements and acceptance (slice 1 — model catalog and selection)

1. `models.catalog.ModelCapabilities` declares what one endpoint can do:
   `reasoning`, `tool_calling`, `structured_output`, `streaming`, `vision`,
   `local` (the model runs on the caller's machine) and a required
   `max_context_tokens`, required because a context window cannot be guessed.
   `satisfies(requirements)` is true when every declared `ModelRequirements`
   field is met: an ordered comparison for `reasoning`, implication for each
   flag, `local` for a `local_only` request, and `max_context_tokens` at
   least `min_context_tokens`. Every requirement field has a rule, pinned by a
   test against `ModelRequirements.model_fields` so a field added there cannot
   be silently ignored.
2. `models.catalog.ModelEndpoint` binds a stable `alias` to a `provider`, the
   provider's own `model` id, its `ModelCapabilities`, an optional `base_url`
   and an optional `credential` (`SecretRef`, a name only). It is serializable
   and carries no secret value: a credential that is not a `SecretRef` is a
   validation error, and so is one smuggled into the URL, whether as userinfo
   or as a recognizable key in a query string. A `base_url` must be http or
   https (case-insensitively), name a host and contain no whitespace.
3. `models.catalog.ModelCatalog` holds the endpoints and optional named
   `routes` (a purpose such as `default` or `knowledge` pointing at one
   alias). A duplicate alias, a route naming an unknown alias and an empty
   catalog are validation errors, so a misconfigured catalog fails where it is
   built rather than at the first request.
4. `ModelCatalog.select(requirements)` implements the existing
   `ModelSelector` protocol: it returns the first alias in catalog order whose
   capabilities satisfy the requirements, or a `Failure`
   (`no_model_for_requirements`, not retryable) naming how many endpoints were
   considered, which one came closest and what that one lacked.
   `select_route(name)` returns a route's alias or a `Failure`
   (`unknown_route`). Neither calls a model, reads a file or touches the
   network.
5. The catalog is loadable from plain data (`ModelCatalog.model_validate`), so
   a host can keep it in YAML or JSON without the platform choosing a
   configuration format or a file location in this slice.
6. Tests: capability satisfaction on every field including the ordered
   `reasoning` comparison and the inverted `local_only` case, the pinned
   requirement-field mirror, selection determinism across repeated calls,
   catalog-order tie-breaking, the closest-endpoint failure naming a real
   candidate, both failures, every validation error, a round trip through
   `model_dump_json`/`model_validate_json`, loading from plain data, and that
   no endpoint contract can hold a secret value in a field or in a URL.

## Requirements and acceptance (slice 2 — OpenAI-compatible adapter)

1. `models.openai_compatible.OpenAICompatible(endpoint, credential=, transport=,
   timeout_s=)` implements `ModelClient` for any endpoint speaking the OpenAI
   chat-completions format: the internal company gateway, a LiteLLM proxy or a
   public OpenAI-shaped API. `ModelEndpoint.base_url` is the API root and the
   adapter appends `/chat/completions`; an endpoint without one is a
   programming error (`ValueError` at construction), not a runtime failure.
2. The credential is a zero-argument callable resolved **per request**, never
   captured at construction, because the source's token rotates on a schedule
   (`refresh-token.ps1`, `docs/PHASE_5_MIGRATION.md`). No credential reaches a
   contract, a log or a `Failure`: an error body is truncated and passed
   through the repository's existing `SECRET_PATTERN` redaction before it
   becomes a message, and headers never appear in one.
3. `generate` maps a `ModelRequest` to one call and back: roles and text,
   `images` as image-url content parts so Phase 4's `data:` URIs work
   unchanged, `max_output_tokens`, and `response_format: json_object` when an
   `output_contract` is declared. The reply always fills `text`, and
   `structured_output` when that text parses strictly as JSON; a contract name
   is a platform identifier and is never sent to the provider, and lenient
   salvage stays with the caller that wants it. `input_tokens` and
   `output_tokens` come from `usage`, whose unknown fields are ignored because
   the internal deployment adds its own. `trace` and `model_alias` are echoed
   from the request: a provider's echoed `model` is never treated as evidence
   of what served it.
4. `stream` yields `ModelStreamEvent`s over server-sent events: one `text`
   event per non-empty content delta, then `done` at `[DONE]` or at the end of
   the stream. **A chunk carrying no `choices` is normal and is skipped**,
   which is the fact the source's `gateway.py` had to monkey-patch a private
   LiteLLM class to survive. A call that did not declare `streaming` in its
   requirements is refused with a single `failed` event, keeping declarations
   honest the way `ModelRequest` already couples tools to `tool_calling`.
5. Every failure is typed and nothing escapes the adapter: `model_timeout` and
   `model_unreachable` (both retryable), `model_http_error` (retryable for
   408, 429 and 5xx, not otherwise), `model_unparseable` (not retryable) and
   `model_error` for anything else raised. `generate` returns them on
   `ModelResponse.failure`; `stream` yields a `failed` event and stops.
   Requests carrying `tools` are refused as `tools_not_supported` until a
   contract can be rendered as a provider schema, which needs a registry that
   does not exist yet; no caller in the platform sends tools today.
6. HTTP sits behind an injected `Transport` protocol returning a `Reply`
   (`status`, `chunks()`, `close()`), so the platform adds no dependency and
   no test opens a socket. A non-2xx status is an answer, not an exception.
   The default `UrllibTransport` uses the standard library; its request
   construction and its error mapping are tested with `urlopen` replaced.
7. Tests: the full generate round trip including images, an `output_contract`,
   usage with unknown fields present and absent; the alias echoed rather than
   the provider's `model`; streaming with a `choices`-less prelude skipped, a
   malformed keepalive ignored, a stream that ends without `[DONE]`, and the
   undeclared-streaming refusal; every failure code including a redacted error
   body; the credential resolved once per request and absent when none is
   given; and the default transport's request construction and error mapping.

## Later slices (each needs its own requirements section before work starts)

- Slice 3 — `ollama` adapter: the local provider, satisfying `local_only`.
  New platform work; the source repository contains no Ollama integration.
- Slice 4 — credential resolution boundary: a `CredentialResolver` the host
  supplies, with an environment-backed development implementation that lives
  outside the platform's import path, plus redaction coverage.
- Slice 5 — observability and a complete inert example: usage and latency on
  every response, an alias-labelled trace, and a requirements-to-response
  chain a host can copy, with no network in tests.

## Out of scope for Phase 5

Codex and Claude Code, in either direction: neither as a provider behind
`ModelClient` (they are agent harnesses with their own multi-turn,
file-mutating sessions, not one-request-one-response endpoints) nor as a
capability the platform invokes. The owner excluded them on 2026-09-21; if the
second form is wanted later it belongs to Phase 6's coding agent and goes
through a `CapabilitySpec` and the Host Bridge, never through the model
interface.

Also out of scope: deploying the LiteLLM proxy (see `docs/PHASE_5_MIGRATION.md`
for why it is no longer required once Claude Code is excluded), the evaluation
harness that compares aliases (Phase 6), an async or connection-pooled
transport, response caching, cost accounting against a price table, and any
production credential backend. `SecretRef` resolution stays an injected
boundary with no backend chosen here.
