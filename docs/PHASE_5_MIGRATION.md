# Phase 5 source inspection and disposition

Source: `dragon0816/knowledge_management`, commit
`2f5e6d0431c5b6af8fbee05c6c0a5779e1a84bb9` (`main` at inspection, 2026-09-21,
read-only shallow clone) — the same repository Phase 4 drew the vault tooling
from, inspected this time for its gateway concern. `docs/SOURCE_REPOSITORIES.md`
records the strategy: split the mixed repository by responsibility rather than
copying it.

The gateway half of that repository is a **deployment**, not a library: a
LiteLLM proxy process in front of the company's internal Open WebUI
(`chatrs`), plus PowerShell operational tooling around it. Only one file in it
is platform-shaped code, the small OpenAI-wire client inside
`agent/agent.py`.

| Source | Observed behavior | Decision and preserved boundary |
| --- | --- | --- |
| `litellm-config.yaml` `model_list` | maps a client-facing `model_name` to an upstream `openai/<id>` at `https://chatrs.cloud.rsint.net/api` with `api_key: os.environ/CHATRS_TOKEN`; includes aliases (`claude-opus-5` → `gpt-5.5`) so Anthropic-format clients resolve | NOT MIGRATED as a component. The alias idea is the valuable part and becomes `models.catalog.ModelEndpoint` in-process (slice 1); the Anthropic aliases exist only for Claude Code, which the owner excluded from Phase 5 |
| `litellm-config.yaml` `litellm_settings` | `use_chat_completions_url_for_anthropic_messages` (Open WebUI has no Responses API), `drop_params` (chatrs returns a non-standard `usage.latency_checkpoint`), `suppress_debug_info` (no pricing data for an internal deployment) | NOT MIGRATED; all three are LiteLLM-specific compatibility settings. The underlying facts are kept as adapter requirements: talk to `/chat/completions`, tolerate unknown fields in `usage`, and never assume a price table |
| `gateway.py` | launches the LiteLLM proxy after monkey-patching `_CombinedChunkSplitter` so chunks with an empty `choices` list are skipped; chatrs emits one such usage-only chunk that otherwise raises `IndexError` mid-stream for every `/v1/messages` request | NOT MIGRATED. The patch exists only for LiteLLM's Anthropic streaming adapter. The underlying fact survives as an adapter requirement: **a streaming chunk with no `choices` is normal and must be skipped, not an error** |
| `start-gateway.ps1` | loads `.env` into the process, refuses to start without `CHATRS_TOKEN` and `LITELLM_MASTER_KEY`, decodes the JWT to warn before expiry | NOT MIGRATED into platform code; host/ops concern. The early-expiry check informs invariant 5: a credential problem should surface as a typed failure, not an opaque 401 much later |
| `refresh-token.ps1` | renews the chatrs JWT silently through Keycloak SPNEGO using the machine's Kerberos ticket, rewrites `.env`, optionally restarts the gateway; replaces a 28-day manual copy out of DevTools because the admin disabled personal API keys | NOT MIGRATED (Windows-domain specific, and credential acquisition belongs to the execution environment). **Load-bearing constraint:** the credential rotates, so an adapter must resolve it through the injected resolver rather than capture a token for the process lifetime |
| `check-model.ps1` | probes each configured model; documents that the `model` field in a response body echoes what the client asked for, not what ran, and that only asking the upstream directly yields a dated build id | NOT MIGRATED. **Load-bearing constraint:** `ModelResponse` reports the platform's own alias; a provider's echoed model name is never treated as evidence of what served the request |
| `test-gateway.ps1`, `verify-chatrs.ps1`, `claude-chatrs.ps1`, `obsidian-chatrs.ps1`, `gateway-build.ps1` | smoke tests and launchers for the proxy and for specific clients | NOT MIGRATED; client- and deployment-specific scripts with no platform contract behind them |
| `agent/agent.py` `Gateway` | standard-library POST to `{base}/v1/chat/completions` with a bearer key; accumulates `prompt_tokens`/`completion_tokens` on the client; on `HTTPError` raises `SystemExit` with up to 500 characters of the error body; on `URLError` raises `SystemExit` with a "is the gateway running" hint | **ADAPT in slice 2** into the `openai_compatible` adapter. Preserved: standard-library HTTP with no new dependency, bearer auth, usage read from the response. Replaced: `SystemExit` becomes a typed `Failure`, the error body is truncated **and redacted**, usage belongs to the response rather than the client, and a timeout is distinguished from a refusal |
| `agent/agent.py` `read_key` | reads `AGENT_KEY`, then `LITELLM_MASTER_KEY`, then scrapes `LITELLM_MASTER_KEY` out of `../.env`, else `SystemExit` | NOT MIGRATED. It violates AGENTS rule 17 (resolution belongs to the execution environment) and this repository's standing no-environment-defaults rule. The platform takes a resolved credential; an environment-backed resolver is a host's development convenience, outside the platform's import path |
| `agent/agent.py` tool loop, prompts, desktop control | a single-file coding agent with file and shell tools confined to `--workdir` | NOT MIGRATED in Phase 5; a coding agent is Phase 6, and it is a `CapabilitySpec` behind the Host Bridge, not a `ModelClient` |
| Ollama | **absent from the source repository** (`grep -i ollama` finds nothing) | New platform work in slice 3, not a migration. Nothing to characterize |

## Slice 1 source-first decision

Inspected `litellm-config.yaml` (87 lines), `gateway.py` (72),
`start-gateway.ps1` (~90), `refresh-token.ps1` (~200), `check-model.ps1` (~230)
and `agent/agent.py` (~440), plus the gateway entries of the source's
`docs/DECISIONS.md`.

Decision (2026-09-21): **ADAPT** the source's alias idea into an in-process,
typed `models.catalog`, and **do not migrate** the LiteLLM proxy as either a
platform component or a Phase 5 deployment artifact.

The source aliases models at the proxy: a client asks for `gpt-5.5` or
`claude-opus-5` and the proxy decides which upstream model id serves it. The
platform needs the same indirection — Architecture requires that "a
provider/model change should normally be configuration, not a code change" —
but it needs it *in front of* the provider adapters, because the platform, not
a proxy, is what declares `ModelRequirements` and must pick an endpoint that
satisfies them. Keeping both layers would mean two places to change when a
model changes, with only one of them able to reason about capabilities.

The proxy earned its place in the source for one reason the platform no longer
has: it terminates the Anthropic wire format so Claude Code can run against an
OpenAI-only backend, which is what `gateway.py`'s streaming patch and the
`claude-*` aliases exist for. With Codex and Claude Code excluded from Phase 5
by the owner, chatrs is already OpenAI-compatible and the `openai_compatible`
adapter can address it directly. Dropping the proxy removes a heavyweight
dependency, a monkey patch against a private LiteLLM class, a second alias
table and a second credential (`LITELLM_MASTER_KEY` in front of
`CHATRS_TOKEN`).

This is reversible by design and costs one configuration change: because an
endpoint is a base URL plus a `SecretRef`, pointing the platform at a LiteLLM
proxy instead of at chatrs is a catalog edit, not a code change. If Claude Code
or Codex is wanted later, the proxy returns as a `deploy/gateway/` artifact
with the pinned config and patch, and the platform is unaffected either way.

Why not WRAP the proxy: wrapping would make an external process a hard
dependency of every model call, including in tests, and would put the
platform's capability reasoning behind an opaque alias table it cannot inspect.
Why not REWRITE a proxy: the platform does not need a network hop to reach an
endpoint it can call directly.

Intentional differences from the source in this slice: an alias declares the
capabilities it actually has, so selection can be checked rather than trusted;
selection is deterministic and returns a typed `Failure` instead of failing at
the first request with a provider error; a catalog is validated where it is
built, so a duplicate alias or a route pointing at nothing is refused before
any request; and no configuration file format, location or environment
variable is chosen by the platform.

Rollback removes `src/models/catalog.py` and its tests; nothing else imports
them, and `models.contracts` is untouched.

## Slice 2 source-first decision

Re-inspected the `Gateway` class and `read_key` in `agent/agent.py`, and the
three compatibility facts recorded in the table above.

Decision (2026-09-21): **ADAPT** `Gateway.send` into
`models.openai_compatible.OpenAICompatible`. What is preserved: the standard
library as the transport, so the platform adds no dependency; bearer
authentication; `POST {base}/chat/completions`; and reading token counts from
the reply's `usage`.

What is deliberately replaced, each because the source's choice cannot hold
inside a platform contract:

- `SystemExit` on an HTTP or URL error becomes a typed `Failure` on the
  response. A library cannot end the host's process, and Phase 4 already
  established that a provider failure is a status rather than an exception.
- The error body, which the source pasted into its message up to 500
  characters, is truncated **and** redacted through the existing
  `SECRET_PATTERN`. An upstream that echoes a request header would otherwise
  print a token.
- Usage accumulated on the client object becomes per-response
  `input_tokens`/`output_tokens`, so a shared client cannot mix two callers'
  accounting.
- A timeout is distinguished from a refusal (`model_timeout` against
  `model_unreachable`), because only one of them suggests a different endpoint.
- The key is a callable resolved per request rather than a string captured at
  construction, because `refresh-token.ps1` rewrites the token on a schedule
  and a long-lived client would otherwise hold an expired one.
- `read_key`'s environment and `.env` fallbacks are not migrated at all; the
  host resolves the value and hands it in.

The two compatibility facts the source had to work around are preserved as
behavior rather than as settings: a streaming chunk with no `choices` is
skipped (the source patched LiteLLM's private `_CombinedChunkSplitter` for
exactly this), and unknown fields inside `usage` are ignored rather than
rejected (the source set `drop_params` for the same reason). The third,
`use_chat_completions_url_for_anthropic_messages`, has no analogue here
because this adapter speaks only the chat-completions format.

Not migrated in this slice: tool calling. `ModelTool.input_contract` is a
`Symbol` naming a platform contract, and rendering it as a provider function
schema needs a contract registry that does not exist. No caller in the
platform sends tools today, so the adapter refuses them with a typed
`tools_not_supported` rather than silently dropping them.

Rollback removes `src/models/openai_compatible.py` and its tests; nothing else
imports them.
