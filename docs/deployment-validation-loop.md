# Deployment validation loop v1

This is the reproducible path between the development computer and the enrolled
company computer.

```text
Codex PR -> human merge -> Platform verification succeeds on main
  -> exact Windows preview artifact
  -> GitHub creates one fixed Hermes deployment request
  -> Hermes installs that exact artifact on the enrolled Bridge
  -> workflow.draft + knowledge.ask + personal.proof
  -> Hermes posts evidence and a terminal result
```

## Fixed profile

The allowlisted profile is `aep-company-agent-integration-v1`. Its definition,
fixtures and expected model responses ship under
`validation/company-agent-integration-v1` in the hash-verified Windows
artifact. It proves three independent routes:

1. `workflow.draft` reads the shipped SOP PDF and returns a draft Workflow.
   It does not install, publish or execute the candidate.
2. `knowledge.ask` queries the exact published
   `validation/company-agent-guide@1.0.0` fixture and must cite immutable Raw
   evidence.
3. `personal.proof` reads only its controlled fixture and must refuse an
   out-of-root read.

The model binding uses the production OpenAI-compatible adapter against a
credential-free loopback server owned by the Hermes fixed profile. The checked
responses make the proof deterministic and free of API cost. This validates
host configuration, adapter wiring, routing and grounded result handling. It
does not claim that a real company model gateway or its credential works.

The artifact does not assume port `8765` is free. Its typed binding policy
allows only `127.0.0.1`, the `/v1` path, and ports `18765` through `18864`.
Hermes chooses the first candidate it can bind, starts and later stops only its
own fixture process, and injects the selected URL into the isolated proof
workspace. A listener owned by another process is skipped without being
terminated. Exhausting the range is setup BLOCKED, not `codex-fix`.

The profile declares exactly three local grants for the requested actor:
`workflow-author/draft@1.0.0`, `knowledge-query/ask@1.0.0`, and
`company-agent/personal-proof-fixture-read@1.0.0`. The last capability is
wired only to the profile fixture directory. No general
`filesystem/read-file` grant is permitted.

## GitHub handoff

After `Platform verification` succeeds for `main`,
`.github/workflows/hermes-deployment-company-agent.yml` locates only the
artifact named `aep-windows-preview-<package_commit>` from that exact run.
It creates a new GitHub Issue, posts a bot-authored
`hermes-validation/v1` JSON comment, and only then applies the queue labels.
The payload has a dynamic `source_issue`; no Issue number is hardcoded.

The workflow does not execute Issue text. It does not check out code, download the artifact, contact a Bridge,
grant permission, configure a production model, execute Issue text, or merge a
pull request. GitHub is the control plane. Hermes performs the fixed local
execution profile.

## Required GitHub variables

Repository Actions variables:

- `HERMES_DEPLOYMENT_BRIDGE=bridge-tp401555`
- `HERMES_DEPLOYMENT_ACTOR=leo.chi`

These values identify the enrolled target. They are not credentials and do not
authorize the actor.

## Hermes requirements

Hermes accepts a request only when:

1. The JSON marker is a GitHub Actions bot comment with schema
   `hermes-validation/v1`.
2. `action` is `install_and_company_agent_integration`,
   `test_profile` is `aep-company-agent-integration-v1`, and
   `profile_path` is the fixed artifact path.
3. Repository, `package_commit`, workflow run, artifact name and
   `artifact_id` agree.
4. The artifact manifest source revision equals `package_commit`, and the
   shipped profile/files match that manifest.
5. Local Bridge ID and actor equal the payload.
6. Setup occurs in an isolated proof workspace. Hermes structurally renders
   the Knowledge manifest's vault path, selects a free port only from the
   profile's loopback range, starts only the loopback fixture model, injects
   its concrete URL, installs only the declared grants, exports assets, runs
   doctor, and then invokes the three explicit commands.
7. Evidence records the exact command outcome, run/trace IDs, Knowledge asset
   version and Raw citations. A preflight problem is `blocked`, not a
   functional FAIL.

Hermes must reject every other action/profile/path and never execute Issue
prose.

## Terminal results

Hermes appends evidence to the generated Issue and adds exactly one terminal
label:

- `hermes-validation-passed` after all four acceptance criteria pass.
- `hermes-validation-failed` only after the functions ran and produced an
  implementation failure.

An environmental failure remains blocked. Terminal results never merge code;
the human remains the merge gate.
