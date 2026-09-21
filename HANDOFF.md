# Handoff — Phase 5 model gateway, slice 1 (catalog and selection)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-5/catalog`, based on `main` after PR #33 merged.

## Goal

Phase 5 slice 1: the alias layer. Callers name a stable alias; a catalog maps
it to a provider, a model id and the capabilities that endpoint actually has,
and deterministic selection matches declared `ModelRequirements` against them.
No provider adapter in this slice. Requirements:
`docs/phases/PHASE_5_GATEWAY.md` (slice 1); decisions:
`docs/PHASE_5_MIGRATION.md`; contracts: `docs/CONTRACTS.md` ("Model catalog
and selection").

## Owner decisions taken on 2026-09-21

Both were asked and answered before this slice started:

1. **Where the gateway lives.** Two artifacts, not one. Provider adapters are
   in-process code under `src/models/`, shipped with the platform. A proxy, if
   one is ever deployed, is a deployment artifact the host runs; the platform
   only ever receives a base URL and a resolved credential, so "started beside
   the agent" and "deployed elsewhere" are the same code path. The platform
   never starts a provider process, and gains no new runtime dependency.
2. **Providers.** Ollama and the internal OpenAI-compatible gateway. **Codex
   and Claude Code are excluded from Phase 5** in both possible senses, as
   clients of a gateway and as something the platform invokes.

Consequence of (2), recorded in `docs/PHASE_5_MIGRATION.md`: the source's
LiteLLM proxy is no longer needed at all. It existed to terminate the Anthropic
wire format for Claude Code; chatrs is already OpenAI-compatible, so the
`openai_compatible` adapter can address it directly. This drops a heavyweight
dependency, a monkey patch against a private LiteLLM class, a second alias
table and a second credential. It is reversible by one catalog edit.

## Completed

- `docs/phases/PHASE_5_GATEWAY.md`: phase scope, eight invariants, slice 1
  requirements, later slices, and an explicit out-of-scope section naming the
  Codex and Claude Code exclusion.
- `docs/PHASE_5_MIGRATION.md`: source inspection of the gateway half of
  `knowledge_management` at the pinned commit, a disposition row per artifact,
  and the slice 1 source-first decision (ADAPT the alias idea in-process; do
  not migrate the proxy). Three load-bearing constraints were extracted from
  the source for later slices: the credential rotates, so it is resolved per
  use rather than captured; a streaming chunk with no `choices` is normal and
  must be skipped; a provider's echoed model name is not evidence of what
  served the request.
- `src/models/catalog.py`: `ModelCapabilities` (with `unmet`/`satisfies`),
  `ModelEndpoint`, `ModelRoute`, `ModelCatalog` (`select`, `select_route`,
  `endpoint`), implementing the existing `ModelSelector` protocol.
- 5 tests (`tests/test_catalog.py`): the pinned requirement-field mirror,
  capability checks field by field, deterministic selection with catalog-order
  tie-breaking and both typed failures, every construction-time validation,
  and that an endpoint carries no credential in a field or in its URL.
- `CLAUDE.md` and `docs/ROADMAP.md` now point at Phase 5 as the active phase.
- PR #34 review (6 findings) applied: `max_context_tokens` is required rather
  than defaulting to an absurd ceiling of 1; the selection `Failure` names the
  endpoint that came closest and what that one lacked instead of a union no
  single endpoint was blocked by; a test pins the `ModelRequirements` mirror so
  a field added there cannot be silently ignored; `ModelEndpoint` is a
  `RegistryContract` and refuses userinfo in a `base_url`, so a credential
  cannot be smuggled through the URL; the scheme check is case-insensitive and
  a host is required; and the `Reasoning` literal now lives once in
  `models.contracts`, with the comparison order derived from it.

## In Progress

- Nothing; the PR is open with the review applied.

## Remaining

- Slice 2: `openai_compatible` adapter (`generate` and `stream`), injected
  transport with a standard-library default, resolved credential, typed
  failures, usage accounting, redaction.
- Slice 3: `ollama` adapter. New platform work; the source repository contains
  no Ollama integration, so there is nothing to characterize.
- Slice 4: the credential resolution boundary (`SecretRef` to value), with an
  environment-backed development resolver outside the platform's import path.
- Slice 5: observability and a complete inert requirements-to-response example.
- Deferred from Phase 3: a payload sweep, process-liveness or lease-based
  suspension, and the earlier deferred reviews.
- Deferred from Phase 4: a retrieval cache, host wiring that plans from an
  adopted document, a size-and-mtime shortcut for adopted-file drift checks,
  and image description for legacy `raw/`.

## Architecture decisions made

- An endpoint declares its capabilities, so a requirement is checked rather
  than trusted; the source's proxy alias table could not reason about them.
- Selection is deterministic and ties break by catalog order, the same promise
  Phase 4's retrieval makes.
- A misconfigured catalog fails where it is built, not at the first request.
- The flat module layout of `src/models/` follows `src/knowledge/` rather than
  the nested `interface/router/providers/` tree sketched in
  `docs/ARCHITECTURE.md` section 6, which the repository already departs from.
  A separate `company_gateway` adapter is not planned either: the company
  gateway is `openai_compatible` with a different base URL and credential.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 569 passed, 3 skipped (link privileges)
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

No model, gateway, network, real vault, job or n8n instance was invoked. This
slice opens no socket at all.

## Known issues / limitations

- `SecretRef.name` is a `Symbol`, and a JWT happens to match that pattern, so
  the type system refuses a raw string credential but cannot prove a name is
  not itself a secret. Resolution arrives in slice 4; the invariant is
  documented and tested as far as the contract allows.
- The catalog has no notion of availability, latency, cost or evaluation
  results, which `docs/ARCHITECTURE.md` lists as later routing inputs. Only
  declared capability is matched today.
- Declared capabilities are trusted as configuration. Nothing verifies that an
  endpoint really has vision or the context length it claims; the source's
  `check-model.ps1` showed a provider's own echo cannot be that evidence.

## Next Recommended Action

Merge PR #34 on green CI. Then write the slice 2 requirements section and implement
the `openai_compatible` adapter, starting from the `Gateway` class in the
pinned `agent/agent.py` and the three load-bearing constraints recorded in
`docs/PHASE_5_MIGRATION.md`.
