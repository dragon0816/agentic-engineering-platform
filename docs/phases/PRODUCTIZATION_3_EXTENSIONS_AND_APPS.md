# Productization 3 — Bridge Extensions and Application Catalog

Status: planned; runtime implementation begins after Productization 2 has a
reproducible passing exit path.

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

## Required decisions before slice 2

- extension process isolation and IPC contract;
- signature/trust root and revocation policy;
- supported language/runtime and offline dependency format;
- who may approve activation on company and shared test computers;
- health timeout, crash policy and retained rollback versions.

These decisions are intentionally deferred from Productization 2. The shared
catalog shell may show categories, but their packages and installers remain
different as required by `docs/ARCHITECTURE.md`.
