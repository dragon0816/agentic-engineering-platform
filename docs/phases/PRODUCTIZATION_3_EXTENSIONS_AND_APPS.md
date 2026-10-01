# Productization 3 — Bridge Extensions and Application Catalog

Status: active; Productization 2 completed with PR #165.

## User outcome

The marketplace presents Bridge Extensions and independent Applications
without confusing their lifecycles:

- a Bridge Extension adds typed local capabilities behind Bridge policy;
- an Application is an independent governed Software product with its own
  process, UI, deployment and update lifecycle.

This enables the Bridge to gain future integrations without releasing a new
core Bridge for every capability, while preventing marketplace content from
becoming an unrestricted in-process code loader.

## Proposed acceptance scenarios

### Bridge Extension

An administrator selects one exact compatible extension. The Bridge downloads
and validates a package, stages it without activation, applies technical policy
and required approval, activates it through a bounded extension runner, then
advertises only the typed capabilities that passed health checks. Failed health
or rollback restores the previous active version. The extension cannot alter
core routing, authorization or another extension's workspace.

### Independent Application

A member discovers a governed Software asset with owner, external repository,
release, compatibility and integration interfaces. The marketplace may open
its UI or configure a declared API, MCP or Workflow integration. It does not
load the Application into the Agent or Bridge and does not copy its source into
the Registry.

## Proposed slices

1. **Category and metadata contracts** — define exact extension compatibility,
   capability declarations, lifecycle/health/rollback metadata and an App
   projection over the existing `SoftwareManifest`.
2. **Extension staging** — verify artifact identity, digest, supported runtime,
   path safety and policy before writing to an isolated version directory; no
   activation or code import.
3. **Bounded extension runner** — activate one approved version outside the
   core process, expose only declared typed capabilities and record health and
   rollback evidence.
4. **Application catalog** — discover independent Software versions and their
   declared integration points without installing them as Agent/Bridge code.
5. **Marketplace lifecycle UI** — make staged, active, unhealthy, rollback and
   external-application states visible and require the applicable human gate.

## Slice 2 implementation boundary

An extension package is an inert, closed envelope containing the exact
published manifest, `requirements.lock`, offline wheels, per-file SHA-256
digests, a canonical content digest and an Ed25519 signature. Canonical package
paths permit only the lock file and direct children of `wheels/`; absolute,
drive-qualified, backslash, traversal and publisher script paths are rejected.

Staging requires an injected Ed25519 verifier and a local trust policy with the
matching non-revoked public key. There is no permissive verifier. The host also
checks exact compatibility, derives the destination from scoped identity,
writes a sibling temporary directory, reopens and rechecks the complete
package and atomically exposes the exact version. Staging does not create a
virtual environment, install a wheel, import a module, start a process, approve
activation, advertise a capability or grant execution permission.

## Slice 3 implementation boundary

Activation requires an exact `ExtensionActivationApproval` bound to the local
device kind/id, extension identity and one approved manifest policy reference.
Only after that check may the Windows preview prepare an isolated environment
from the already verified wheel files with `--no-index --no-deps`. A digest
marker makes preparation repeatable; partial environments are removed.

The runner launches the manifest module with the prepared interpreter, `-I`, a
fixed argument vector, no shell, a minimal non-secret environment and
synchronized `aep-extension-jsonl/v1` requests on standard streams. Startup and
request timeouts come from the manifest. Health must return the exact ordered
capability identities declared by the manifest before any capability is
advertised.

An unhealthy or exited process immediately loses all advertisement. A failed
upgrade leaves the prior healthy process active. A running upgrade that fails
may restart the retained prior version under its existing approval; repeated
crashes within the declared window disable reactivation. These state changes do
not create a `LocalPolicy` capability grant. This Windows preview provides
process separation and secret minimization, not an OS security-sandbox claim;
trusted signature, technical policy and device activation approval remain
mandatory.

## Decisions for slices 2 and 3

- One exact extension version runs in one dedicated subprocess. The Bridge
  never imports publisher code. Requests and replies use the versioned
  line-delimited JSON protocol `aep-extension-jsonl/v1` over standard streams.
- Packages use Ed25519 signatures. Registry metadata names a public `key_id`;
  the local trust policy supplies trusted and revoked public keys. A missing,
  unknown or revoked key, invalid signature or unverifiable package is refused.
- The first runtime is Windows, Python 3.12, ABI `cp312-win_amd64`. Packages are
  offline wheelhouses installed into isolated exact-version environments after
  activation approval and before process start. No dependency download occurs.
- Company-workstation activation requires the registered device owner or
  delegated device administrator plus approved technical policy. Shared test
  computers require a device administrator/virtual member plus approved
  technical policy. An extension package or Registry publication supplies
  neither approval.
- Startup timeout is 15 seconds, request timeout is 30 seconds and three
  crashes within 300 seconds disable the version. At least two verified
  versions are retained; startup, health or crash-limit failure may restore the
  last healthy approved version and records typed evidence.

These are narrow Windows-preview defaults rather than a general plug-in
platform. The shared catalog may show categories, but Agent Add-on, Bridge
Extension and Application packages/installers remain different as required by
`docs/ARCHITECTURE.md`.
