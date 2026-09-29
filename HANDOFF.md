# Handoff

Date: 2026-09-29 (Asia/Taipei)
Branch: `codex/dynamic-loopback-port`
Base: `origin/main` at `2c3fe68c363d31e1d4e6836313054f26ca6bb7d1`
Pull request: pending

## Goal

Remove the machine-wide fixed-port assumption that blocked Company Agent
deployment Issue #130 before any functional acceptance criterion could run.

## Completed

- Added a typed `LoopbackPortBinding` contract. It permits only
  `127.0.0.1`, `/v1`, non-privileged ports, `first_available` selection and a
  range of at most 128 ports.
- Evolved the existing profile compatibly: fixed credential-free loopback URLs
  still validate, while the shipped Company Agent profile now leaves
  `endpoint.base_url` unset and declares ports `18765..18864`.
- Added negative contract tests for remote hosts, credentials, privileged or
  reversed ranges, oversized ranges and simultaneous fixed/dynamic endpoints.
- Documented that Hermes skips existing listeners, starts and stops only its
  own fixture process, injects the selected URL into the isolated proof host
  config and returns BLOCKED only when setup cannot own a declared port.
- Preserved every PR #129 boundary: exact artifact identity, fixed profile,
  three least-privilege grants, immutable Knowledge evidence and four existing
  acceptance criteria.

## In Progress

- The implementation is locally verified but its PR has not yet been opened.

## Remaining

1. Commit, push and open the narrow PR.
2. Hermes must update only its allowlisted
   `aep-company-agent-integration-v1` runner to implement the new binding
   policy. It must not kill or reuse PID 36208 or any unknown listener.
3. After the PR is merged and main CI creates a new artifact/request, Hermes
   should consume the new dynamic Issue. Issue #130 remains correct historical
   BLOCKED evidence for the old artifact and should not be rewritten as PASS.
4. Collect actual SOP draft, Knowledge answer, Personal Proof and out-of-root
   refusal evidence from the new request.

## Architecture decisions made

- The collision is environment setup, not a repository implementation failure;
  #130 correctly did not receive `codex-fix`.
- Port choice belongs to the deterministic Hermes execution profile. GitHub
  remains the control plane and the application still receives an ordinary
  concrete OpenAI-compatible `base_url` in its isolated host configuration.
- Existing listeners are outside this validation profile's ownership. A runner
  may skip them but never terminate, attach to or replace them.
- This proof remains credential-free and does not claim a production company
  model endpoint works.

## Verification

Supported target: Windows, Python 3.12. Browser tests remain excluded by owner
instruction.

```text
python -m pytest tests/test_validation_contracts.py \
  tests/test_company_agent_validation_profile.py \
  tests/test_deployment_validation_loop.py tests/test_windows_preview_bundle.py
30 passed

python -m pytest --ignore=tests/test_browser.py
1341 passed, 4 skipped

python -m ruff check .
All checks passed

python -m ruff format --check .
288 files already formatted

python -m mypy src tests
Success: no issues found in 224 source files
```

The local managed worktree could not use the default pytest cache/temp roots,
so verification used `-p no:cacheprovider` and a writable explicit
`--basetemp`; the test results themselves were green.

## Known issues

- Issue #130's artifact contains the old fixed `127.0.0.1:8765` profile and
  cannot prove this change. A new successful main artifact is required.
- PID 36208 owns the existing `uvicorn` listener on port 8765. Its purpose is
  unknown and this change intentionally leaves it alone.
- No production company model credential or endpoint was tested.

## Next Recommended Action

Open and review the narrow PR, then give Hermes the bounded-port runner prompt.
Merge only after Hermes confirms it can consume the new policy. The next
successful main artifact should create a fresh dynamic deployment Issue and
run the four functional criteria automatically.
