# Deployment validation loop v1

This is the first reproducible path between the development computer and an
enrolled company computer. It validates one deliberately harmless capability
before SOP authoring, Knowledge, real workflows, or hardware access are added.

```text
Codex PR -> human merge -> Platform verification succeeds on main
  -> exact Windows preview artifact
  -> GitHub creates fixed Hermes deployment request
  -> Hermes installs that exact artifact on the enrolled Bridge
  -> personal.proof runs against a controlled local fixture
  -> Hermes posts evidence and a terminal result
```

## Fixed profile

The only profile in this first loop is `aep-deployment-personal-proof-v1`.
It runs `company-agent/personal-proof@1.0.0`, which reads one controlled local
fixture through `filesystem.read`. It has no model routing, Knowledge lookup,
network request, write operation, DUT control, browser automation, email, Git
write, or production side effect.

The profile must produce the installed revision, `artifact_id`, artifact name,
Bridge/agent readiness, exported scoped asset identity, run ID, trace
identifiers, and a sanitized output summary. A test may pass only when the
installed bundle revision and `package_commit` match exactly.

## GitHub handoff

After `Platform verification` succeeds for `main`,
`.github/workflows/hermes-deployment-personal-proof.yml` locates only the
artifact named `aep-windows-preview-<package_commit>` from that exact workflow
run. It creates a GitHub Issue, writes a machine-readable
`hermes-validation/v1` JSON **comment**, and only then applies the queue
labels. The marker contains the bounded profile, Bridge and actor configured
by repository variables, and immutable deployment artifact identity.

The workflow does not check out code, download an artifact, contact a Bridge,
and does not execute Issue text. It does not grant a permission, configure a model, or merge a pull
request. GitHub is the control-plane handoff; Hermes performs the local
execution-plane work through fixed profile-owned code.

## Required GitHub variables

Set these repository **Actions variables**, never secrets, before merging a
change intended to trigger the loop:

- `HERMES_DEPLOYMENT_BRIDGE=bridge-tp401555`
- `HERMES_DEPLOYMENT_ACTOR=leo.chi`

They identify the enrolled target only. They are not credentials and do not
authorize that actor. The Bridge membership and local authorization remain the
enforcement point.

## Hermes requirements

Hermes accepts a deployment request only when all of the following hold:

1. The JSON marker is in a GitHub Actions comment and schema is
   `hermes-validation/v1`. GitHub's API currently reports this author as
   `github-actions`; Hermes may also accept the equivalent displayed form
   `github-actions[bot]`, but no other account.
2. `action` is exactly `install_and_personal_proof` and `test_profile` is
   exactly `aep-deployment-personal-proof-v1`.
3. Repository, `package_commit`, workflow run, artifact name and `artifact_id`
   agree. Hermes downloads the artifact through authenticated GitHub API/CLI,
   not an Issue-provided URL.
4. The artifact manifest's source revision equals `package_commit`.
5. The local Bridge ID and bound actor equal the supplied execution identity.

Hermes must reject any other profile or instruction and must not execute Issue
text. It reports a structured blocked result when the artifact, membership,
profile implementation, or controlled fixture is unavailable.

## Terminal results

Hermes appends evidence to the generated Issue and adds exactly one terminal
label:

- `hermes-validation-passed` after the fixed profile succeeds.
- `hermes-validation-failed` when the fixed profile ran and failed.

An environmental failure before execution is recorded as `blocked` evidence;
Hermes must not claim a functional failure. A terminal result never merges
code. A human continues to decide whether a successful PR should merge.
