# Handoff — Phase 5 model gateway, slice 3 (Ollama adapter)

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-5/ollama`, based on `main` after PR #35 merged.

## Goal

Phase 5 slice 3: the local provider, and the shared surface a second adapter
revealed. Requirements: `docs/phases/PHASE_5_GATEWAY.md` (slice 3); decisions:
`docs/PHASE_5_MIGRATION.md` (slice 3); contracts: `docs/CONTRACTS.md`
("Shared adapter rules and the Ollama adapter").

## Owner decisions still in force (taken 2026-09-21)

1. Provider adapters are in-process code under `src/models/`; a proxy, if ever
   deployed, is a host artifact. The platform never starts a provider process
   and takes no new runtime dependency.
2. Providers are Ollama and the internal OpenAI-compatible gateway. Codex and
   Claude Code are out of scope in both senses, which is why the source's
   LiteLLM proxy is not migrated at all.
3. Remaining Phase 5 slices are to be completed without check-ins unless
   something cannot be decided (owner, 2026-09-22).

## Completed

- `src/models/wire.py`, extracted from `openai_compatible.py`: the
  `Transport`/`Reply` protocols, the redirect-refusing `UrllibTransport`,
  failure mapping and redaction, per-request credential resolution, the tool
  and undeclared-streaming refusals, strict structured parsing, and the
  response/event builders. The extraction is pure movement; the slice 2 tests
  pass unchanged apart from their import line.
- `src/models/ollama.py`: `Ollama` implementing `ModelClient` against the
  native `/api/chat`. Images as bare base64 with `image_not_inline` for a
  reference that cannot be inlined, `options.num_predict`, `format: "json"`,
  an explicit `stream` flag, usage from `prompt_eval_count`/`eval_count`, and
  newline-delimited JSON streaming that stops at `done`.
- 6 tests (`tests/test_ollama.py`), none opening a socket: the round trip
  against Ollama's own field names, images and the refusal, structured
  output, streaming including a split line and a stream with no `done`, a
  server that is not Ollama, and the shared rules holding identically here.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available.

## Remaining

- Slice 4: the credential resolution boundary (`SecretRef` to value), with an
  environment-backed development resolver outside the platform's import path.
  Both adapters already take a callable, so this slice supplies it rather than
  changing either adapter.
- Slice 5: observability and a complete inert requirements-to-response
  example, then the Phase 5 closure change (Roadmap status, README, the
  `CLAUDE.md` active-phase pointer).
- Deferred from Phase 3: a payload sweep, process-liveness or lease-based
  suspension, and the earlier deferred reviews.
- Deferred from Phase 4: a retrieval cache, host wiring that plans from an
  adopted document, a size-and-mtime shortcut for adopted-file drift checks,
  and image description for legacy `raw/`.

## Architecture decisions made

- Ollama's native `/api/chat` rather than its OpenAI-compatible shim, because
  the shim is documented as experimental, the differences are real, and the
  local path should not depend on a compatibility layer that may lag.
  Reversing it is a catalog change, not a rewrite.
- The shared surface was extracted only once a second consumer existed. With
  one consumer it would have been a guess; with two it is the set of rules
  that must not differ between providers.
- Locality is not enforced by the adapter. `local` is a claim the catalog
  makes, and a host may run Ollama on another machine.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 597 passed, 3 skipped (link privileges)
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

No model, gateway, network, real vault, job or n8n instance was invoked.

## Known issues / limitations

- **The Ollama adapter has never been run against a live Ollama server.** It
  is written to the documented native chat API and covered by tests with an
  injected transport. Before anyone relies on it, run one real request against
  a local Ollama and confirm the field names, particularly
  `prompt_eval_count`/`eval_count` and the streaming `done` flag.
- Ollama's tool calling is not used, for the same reason as the other adapter:
  a `ModelTool` names a platform contract and no registry can render it as a
  provider schema.
- `keep_alive`, `think`, `num_ctx` and the rest of Ollama's options are not
  exposed. Only `num_predict` is set, from the request's `max_output_tokens`.
- A response's `tool_calls` are not read back by either adapter.
- `model_error` stays retryable in the shared mapping, because a custom
  transport may raise its own transient exception types.

## Next Recommended Action

Open the PR for `phase-5/ollama`, run the review, apply confirmed findings and
merge on green CI. Then write the slice 4 requirements section and implement
the credential resolution boundary.
