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
   the stream. A 2xx reply carrying no events at all is an endpoint that
   ignored `stream: true`, and is `model_unparseable` rather than a silent
   empty success that throws the answer away. **A chunk carrying no `choices` is normal and is skipped**,
   which is the fact the source's `gateway.py` had to monkey-patch a private
   LiteLLM class to survive. A call that did not declare `streaming` in its
   requirements is refused with a single `failed` event, keeping declarations
   honest the way `ModelRequest` already couples tools to `tool_calling`.
5. Every failure is typed and nothing escapes the adapter: `model_timeout`
   and `model_unreachable` (both retryable), `credential_unavailable` when
   the resolver itself fails (retryable, and distinct because the endpoint was
   never asked), `model_http_error` (retryable for 408, 429 and 5xx, not
   otherwise), `model_unparseable` and `model_error`. `generate` returns them
   on `ModelResponse.failure`; `stream` yields a `failed` event and stops. A
   request carrying `tools`, or messages replaying `tool_calls`, is refused as
   `tools_not_supported` until a contract can be rendered as a provider
   schema, which needs a registry that does not exist yet; no caller in the
   platform sends tools today.
6. HTTP sits behind an injected `Transport` protocol returning a `Reply`
   (`status`, `chunks()`, `close()`), so the platform adds no dependency and
   no test opens a socket. A non-2xx status is an answer, not an exception.
   The default `UrllibTransport` uses the standard library through an opener
   that refuses redirects, because urllib would otherwise copy the
   `Authorization` header to the redirect target and drop the POST body; its
   request construction, its error mapping and its redirect refusal are tested
   with the opener replaced.
7. Tests: the full generate round trip including images, an `output_contract`,
   usage with unknown fields present and absent; the alias echoed rather than
   the provider's `model`; streaming with a `choices`-less prelude skipped, a
   malformed keepalive ignored, a stream that ends without `[DONE]`, and the
   undeclared-streaming refusal; every failure code including a redacted error
   body; the credential resolved once per request and absent when none is
   given; and the default transport's request construction and error mapping.

## Requirements and acceptance (slice 3 — Ollama adapter)

1. `models.wire` holds everything two HTTP adapters must agree on: the
   `Transport`/`Reply` protocols and the redirect-refusing `UrllibTransport`,
   the failure mapping and redaction, credential resolution, the tool and
   undeclared-streaming refusals, strict structured parsing, and the
   response/event builders. A provider module is then its own payload shape,
   its own reply shape and its own idea of a streaming chunk, so two adapters
   cannot drift on what a failure means.
2. `models.ollama.Ollama(endpoint, credential=, transport=, timeout_s=)`
   implements `ModelClient` against Ollama's own `/api/chat`, not its
   OpenAI-compatible shim. `base_url` is the server root, such as
   `http://localhost:11434`.
3. The wire differences are real and are handled here: images travel as bare
   base64, so Phase 4's `data:` URIs are stripped and an image reference the
   platform cannot inline is refused as `image_not_inline` before anything is
   sent; the token limit is `options.num_predict`; structured output is
   `format: "json"`; `stream` must be sent explicitly because Ollama streams
   by default; and usage is `prompt_eval_count`/`eval_count`.
4. `stream` reads newline-delimited JSON objects rather than server-sent
   events: one `text` event per non-empty `message.content`, stopping at the
   object whose `done` is true, then `done`. Lines are reassembled across
   chunk boundaries, blank and half-written lines are skipped, and a 2xx body
   with no JSON object in it at all is `model_unparseable`. An object carrying
   `error` is `provider_error` and stops the stream: once the status has been
   sent, a refusal can only arrive in the body, and reading past it would
   report an empty success and discard the server's explanation. The same
   holds for a 2xx reply to `generate`, in both adapters.
5. Nothing about locality is enforced. `local` is a claim an endpoint makes in
   the catalog and a host may run Ollama on another machine; this adapter
   needs only an address. A credential is supported because a reverse proxy
   in front of Ollama may want one, under the same rules as anywhere else.
6. Tests: the generate round trip against Ollama's own field names; images as
   base64 and the refusal of a reference; `format: "json"` and strict
   structured parsing; streaming including a line split across chunks, a
   blank line, the `done` flag ending it and a stream that stops without one;
   a server that is not Ollama; and the shared rules holding identically here
   (both tool shapes, undeclared streaming, per-request credential
   resolution, a resolver that fails, and the construction errors).

## Requirements and acceptance (slice 4 — credentials and client construction)

1. `models.credentials.CredentialResolver` is the boundary AGENTS rule 17
   describes: `resolve(ref: SecretRef) -> str`, supplied by the execution
   environment. A resolver that cannot produce a value raises, which both
   adapters already turn into `credential_unavailable`; nothing in the
   platform reads an environment variable on its own.
2. `credential_for(endpoint, resolver)` turns a `ModelEndpoint` and a resolver
   into the zero-argument callable the adapters take: `None` when the endpoint
   declares no credential, a `ValueError` when it declares one and no resolver
   was supplied, and otherwise a closure that resolves **per call**, so a
   rotating token is never captured.
3. `EnvironmentCredentials(names)` is a development-grade resolver mapping each
   `SecretRef` name to an environment variable name explicitly. There is no
   prefix convention and no default: a host says which variable holds which
   secret, or nothing is read. A resolved value is stripped, since a token
   read from a file carries a trailing newline. A secret nothing is mapped to,
   or whose value is missing or blank, raises `CredentialMisconfigured`, which
   the adapters report as a failure that will not fix itself; any other
   resolver error stays retryable. Neither resolver is a `Contract`, because a
   contract is serializable and a secret value must not be.
   `StaticCredentials(values)` is the same shape for a host that already holds
   its secrets, and for tests.
4. `models.clients.ModelClients(catalog, resolver=, transport=, timeout_s=,
   providers=)` builds the right `ModelClient` for an alias: `for_alias`,
   `for_route` and `for_requirements`, the last being the whole chain from
   declared `ModelRequirements` to a client that can answer. `providers` maps
   a provider symbol to a builder and is merged over the two built in, so a
   host can add one without changing core runtime code and can override a
   built-in by reusing its key. `options` carries per-alias keyword arguments
   for the adapter, which is where a wire detail of one endpoint belongs when
   the shared contract deliberately does not describe it.
5. Every way of failing is typed rather than raised: `unknown_alias`,
   `unknown_provider`, `endpoint_misconfigured` (the construction errors,
   including a declared credential with no resolver and an option the provider
   does not take) and `provider_build_failed` for anything else a
   host-registered builder raises, alongside the catalog's own
   `no_model_for_requirements` and `unknown_route`. An option naming no
   endpoint is refused where the wiring is written. A built client is
   cached per alias, so a host may call this per request without rebuilding a
   transport each time.
6. Tests: resolution per call rather than capture, a resolver that raises
   reaching the adapter as `credential_unavailable`, the environment resolver
   with an explicit mapping and its refusals, that no resolver or endpoint
   repr exposes a secret value, each typed construction failure, a host
   registering its own provider, caching, and the full requirements-to-client
   chain over a catalog holding both providers.

## Requirements and acceptance (slice 5 — observability and a worked example)

1. `ModelResponse.duration_ms` and `ModelStreamEvent.duration_ms` report how
   long the provider took, so evaluation can compare aliases on latency as
   well as on quality and usage, which `docs/ARCHITECTURE.md` requires of the
   model router. Both adapters measure from just before the call goes out to
   after the reply is read, using a monotonic clock so a clock adjustment
   cannot produce a negative latency. A stream reports on the event that ends
   it, whether `done` or `failed`. A request refused before any call reports
   zero rather than a misleading number.
2. `models.proof` is the model layer's counterpart to `workflow.proof`:
   something a host copies rather than infers. `SAMPLE_CATALOG` is plain data
   in the shape a host keeps in YAML or JSON, `clients_from` validates it and
   wires a resolver and a transport, and `ask` states what the work needs and
   sends one request to whichever endpoint satisfies it, naming no provider,
   model id or URL.
3. The example is inert. Nothing is installed, no socket is opened in a test,
   the sample catalog carries a `SecretRef` name rather than any value, and
   the repository's own `SECRET_PATTERN` guard finds nothing in it.
4. Tests: the sample catalog validating and carrying no credential material,
   the whole chain answering through both providers with the alias decided by
   requirements, a routing failure that stays a `Failure`, a resolver needed
   only where a secret is declared, measured durations on a successful and a
   failed call for each adapter with the clock replaced, and a stream
   reporting on its terminal event only.

## Phase 5 exit criteria

Met on 2026-09-22:

- **Local Ollama and the internal OpenAI-compatible gateway satisfy the same
  model client interface.** `models.ollama.Ollama` and
  `models.openai_compatible.OpenAICompatible` both implement `ModelClient`,
  each over its own wire format, sharing `models.wire` for everything a
  provider must not decide for itself.
- **Credentials are externalized.** A `ModelEndpoint` declares a `SecretRef`
  and never holds a value; `models.credentials` is the only place one is
  produced, per request, by a resolver the host supplies.
- **Provider-specific patches stay isolated.** Nothing outside `src/models/`
  names a provider, a wire format or a URL, and the platform's install is
  still `pydantic` alone.

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
