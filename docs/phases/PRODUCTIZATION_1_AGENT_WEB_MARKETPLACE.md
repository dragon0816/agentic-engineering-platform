# Productization 1 — Personal Agent Web and Workflow Marketplace

Status: active

## User outcome

An enrolled member opens the Personal Agent Web interface on a Bridge and can
see the machine, its platform connection, locally installed assets and the
published assets that the signed-in platform member is entitled to discover.
The interface must keep three facts separate:

1. an asset is published and discoverable;
2. the member selected it for this Bridge and synchronized that decision;
3. the asset is installed locally and can be considered for execution.

Publication and installation still do not grant capability execution. A run
continues through the existing Agent, Gateway, Workflow engine and Bridge
policy, where the actor's capability grants are enforced.

## First acceptance scenario — shared Workflow discovery

Given a platform member whose Bridge has a valid platform binding, and a
published Workflow visible to that member:

1. the Bridge authenticates to the platform using its existing `SecretRef`;
2. the platform returns only published packages the authenticated member is
   entitled to discover;
3. the Personal Agent Web interface shows kind, scoped identity, owner,
   visibility, compatibility and dependency metadata;
4. before synchronization the Workflow is shown as published, not authorized
   on this Bridge and not installed;
5. after a separate platform selection and the existing synchronization path,
   the same Workflow is shown as authorized and installed;
6. catalog discovery performs no installation, authorization change or
   execution;
7. a platform outage produces a typed, visible unavailable state while local
   Agent use continues.

The green path is exercised over the real loopback Web API and the real HTTP
control-plane transport. CI remains inert and uses only in-memory Registry
state and fixture assets.

## Architecture

- `control_plane` remains the Registry/control plane and applies entitlement
  filtering from its trusted membership record.
- `host_runtime` remains the local Personal Agent and execution plane.
- A new read-only `catalog` operation extends the existing Bridge/platform
  wire. It returns provider-neutral published package metadata and no artifact
  bytes.
- The existing `sync` operation remains the only installation path in this
  slice. The existing authorization Registry remains the only source of device
  selections.
- The Web interface is an ingress and projection only. It owns no routing,
  installation, authorization or execution logic.

## Incremental slices

1. **Catalog read path and Web projection** — typed catalog contracts,
   entitlement-filtered control-plane operation, Bridge client, Marketplace
   table and integration tests.
2. **Member selection UI** — add a member-authenticated control-plane entry
   point for selecting/revoking a Workflow for a bound Bridge. Do not reuse the
   Bridge token as an interactive user session.
3. **Install/synchronize action** — expose the existing all-or-nothing sync as
   an explicit Web action, with before/after state and typed refusal.
4. **Workflow launch form** — render declared inputs and submit through the
   normal Agent/Gateway path; show progress, result and trace identifiers.
5. **Knowledge query** — browse exact installed Knowledge versions and ask one
   grounded question with citations.
6. **Durable shared catalog** — replace the in-memory Registry reference with a
   small persistent implementation after the user path and contracts are
   validated.

Skills and Knowledge use the same catalog contracts. The product may label
`Software` assets as **Apps** in the user interface later; no overlapping core
asset type is introduced.

## Out of scope for the first slice

- production multi-user Web authentication;
- publishing, approval or administration dashboards;
- direct installation from a discover response;
- execution permission changes;
- production database or object storage;
- remote control of company workstations;
- a new Telegram or GitHub coordination mechanism.

## Risks and trade-offs

- The Bridge access token authenticates the bound member for catalog reads, but
  is not suitable as a general browser login. Member selection therefore stays
  outside the first slice.
- The current Registry stores package metadata and artifact references. A
  short optional discovery description is added without embedding package
  content or secrets.
- Catalog availability is central, while already-installed assets remain
  local-first. An unavailable catalog must not disable local execution.

## Exit evidence for slice 1

- contract tests reject malformed/duplicate catalog filters and embedded
  secrets;
- private/team visibility is filtered from trusted platform membership;
- catalog transport is authenticated and read-only;
- the Web API distinguishes published, authorized and installed state;
- focused tests, full `pytest` on Windows/Python 3.12, Ruff, Mypy, build and
  `pip check` pass;
- `HANDOFF.md` records exact commands and the next slice.
