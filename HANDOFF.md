# Handoff — Phase 5 model gateway, slice 4 (credentials and client construction)

Updated: 2026-09-22 (Asia/Taipei).
Branch: `phase-5/credentials`, based on `main` after PR #36 merged.

## Goal

Phase 5 slice 4: where a `SecretRef` becomes a value, and the last link from a
declared requirement to something that can answer it. Requirements:
`docs/phases/PHASE_5_GATEWAY.md` (slice 4); contracts: `docs/CONTRACTS.md`
("Credentials and client construction"). This slice adapts nothing: the source
repository resolves its key by reading environment variables and scraping a
`.env` file, which `docs/PHASE_5_MIGRATION.md` already recorded as not
migrated.

## Owner decisions still in force

1. Provider adapters are in-process code under `src/models/`; a proxy, if ever
   deployed, is a host artifact. The platform never starts a provider process
   and takes no new runtime dependency (2026-09-21).
2. Providers are Ollama and the internal OpenAI-compatible gateway. Codex and
   Claude Code are out of scope in both senses (2026-09-21).
3. Remaining Phase 5 slices are to be completed without check-ins unless
   something cannot be decided (2026-09-22).

## Completed

- `src/models/credentials.py`: the `CredentialResolver` protocol,
  `credential_for` (per-call resolution, `None` when nothing is declared, a
  `ValueError` when something is declared and no resolver was supplied),
  `EnvironmentCredentials` (explicit name-to-variable mapping, no convention
  and no default, refusing a missing or blank value) and `StaticCredentials`.
  Nothing here is a `Contract`, so a value cannot be serialized or logged.
- `src/models/clients.py`: `ModelClients` with `for_alias`, `for_route` and
  `for_requirements`, a `ClientBuilder` protocol and a provider registry
  defaulting to the two built-in adapters. Typed failures: `unknown_alias`,
  `unknown_provider`, `endpoint_misconfigured`. Clients are cached per alias.
- 6 tests (`tests/test_clients.py`), none opening a socket: resolution where
  the host says and nowhere else, per-call rather than captured resolution,
  the whole requirements-to-answer chain over a catalog holding both
  providers, every typed construction failure, a resolver that fails reaching
  the caller as `credential_unavailable` with the endpoint never contacted,
  and a host registering its own provider.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available.

## Remaining

- Slice 5: observability (per-response duration beside the token counts, so
  evaluation can compare aliases on latency as `docs/ARCHITECTURE.md`
  requires) and a worked inert example, then the Phase 5 closure change
  (Roadmap status, README, the `CLAUDE.md` active-phase pointer).
- Deferred from Phase 3: a payload sweep, process-liveness or lease-based
  suspension, and the earlier deferred reviews.
- Deferred from Phase 4: a retrieval cache, host wiring that plans from an
  adopted document, a size-and-mtime shortcut for adopted-file drift checks,
  and image description for legacy `raw/`.

## Architecture decisions made

- The platform ships a development resolver but no production backend, and it
  reads nothing unless a host states which variable holds which secret. A
  prefix convention was rejected: a convention that guesses is a convention
  that reads the wrong thing in silence.
- Registering providers replaces the default map rather than merging with it,
  so a host that means to restrict the platform to one provider can.
- Construction failures are typed rather than raised, because a misconfigured
  catalog should read like an unavailable model to the caller rather than an
  exception from the middle of a request.

## Exact verification commands and results

Windows, Python 3.12.14, repository root, with the `office` extra installed:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 605 passed, 3 skipped (link privileges)
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

- `SecretRef.name` is a `Symbol` and a JWT matches that pattern, so the type
  system still cannot prove a name is not itself a secret. The resolver
  boundary makes this less likely to matter, since a name is now looked up
  rather than used.
- No production credential backend: an OS keychain or enterprise vault
  resolver is a host concern and remains out of scope for Phase 5.
- A cached client holds the catalog's endpoint as it was built. A host that
  edits its catalog builds a new `ModelClients`.
- The Ollama adapter still has never been run against a live server; see the
  slice 3 note, which stands.

## Next Recommended Action

Open the PR for `phase-5/credentials`, run the review, apply confirmed
findings and merge on green CI. Then write the slice 5 requirements section,
implement per-response duration and the worked example, and close Phase 5.
