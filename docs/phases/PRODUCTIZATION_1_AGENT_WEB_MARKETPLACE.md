# Productization 1 — Personal Agent Web and Workflow Marketplace

Status: complete

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
control-plane transport. CI remains inert and uses fixture assets with both
the in-memory reference and a temporary SQLite Registry.

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
2. **Member selection** — add a member-authenticated control-plane entry point
   and generic Workflow selection page for selecting/revoking a Workflow for a
   bound Bridge. Do not reuse the Bridge token as an interactive user session.
   The provider-neutral session/HTTP proof is slice 2a; connecting a one-time
   invitation proof to invitation acceptance and session issuance is slice 2b.
3. **Shared Platform composition (slice 2c)** — run the Bridge API and Member Portal in
   one deployable process over shared enrollment, package, authorization and
   session state; give Personal Agent Web an explicit, non-secret Member Portal
   link without sending the Bridge credential there.
4. **Install/synchronize action** — expose the existing all-or-nothing sync as
   an explicit Web action, with before/after state and typed refusal.
5. **Workflow launch form** — render declared inputs and submit through the
   normal Agent/Gateway path; show progress, result and trace identifiers.
6. **Knowledge query** — browse exact installed Knowledge versions and ask one
   grounded question with citations.
7. **Durable shared catalog** — replace the in-memory Registry reference with a
   small persistent implementation after the user path and contracts are
   validated.

Skills and Knowledge use the same catalog contracts. The product may label
`Software` assets as **Apps** in the user interface later; no overlapping core
asset type is introduced.

The user interface keeps three extension/product categories explicit. An
**Agent Add-on** assembles governed Agent assets. A **Bridge Extension** adds
typed local executable capabilities behind Bridge policy. An **Application**
is an independent software product with its own process, UI and deployment
lifecycle; the catalog may present its governed `Software` metadata and
integration points, but does not load it into the Agent or Bridge. These
categories may share discovery and governance, not installer or runtime
contracts. Extension installation remains outside this productization slice.

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
- The member entry point accepts a short-lived session created only after a
  trusted sign-in adapter has produced an `AuthenticatedActor` with no Bridge
  identity. The request can name a Bridge and Workflow but cannot claim actor,
  groups, permission, policy or decision time. The first adapter remains out of
  scope for slice 2a; tests inject its already-authenticated result.
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

## Exit evidence for slice 2a

- a Bridge access token cannot be exchanged for a member browser session;
- a member session is short-lived, opaque and stored only as a secret-free
  fingerprint record;
- the member catalog lists only entitled Workflows for a Bridge bound to the
  authenticated actor;
- select/revoke requests cannot carry actor, membership, permission, policy or
  decision-time claims;
- selection and revocation cross the real member HTTP entry point and change
  no execution grant;
- plain HTTP is loopback-only; a network-exposed portal requires TLS;
- the generic page keeps the session in memory, removes its URL fragment and
  never persists it in browser storage.

## Exit evidence for slice 2b

- invitation metadata and stored proof grants contain no proof secret;
- a weak proof or invalid expiry leaves no invitation behind;
- unknown invitation ids and wrong proofs are indistinguishable;
- an accepted proof creates the named member and one short-lived direct-member
  session, then cannot be replayed;
- expired and revoked proofs cannot create sessions;
- the real HTTP sign-in endpoint accepts no actor, Bridge, membership,
  permission, policy or decision-time claim;
- a Bridge bearer cannot be used for direct member sign-in;
- sign-in changes no Bridge binding, asset selection or execution grant;
- the page removes the invitation fragment and stores neither invitation nor
  member bearer in browser storage.

## Exit evidence for slice 2c

- one application lifecycle starts and stops both the Bridge API and Member
  Portal while both use the same enrollment and authorization records;
- an invitation redeemed over the real member HTTP entry point creates the
  member later authenticated by the Bridge API after the separate device
  binding/token step;
- process configuration contains invitation metadata and TLS paths, never an
  invitation proof, Bridge token, member bearer or private-key value;
- generated invitation links are written once to an explicitly named local
  delivery file and are not printed as ordinary service status;
- a non-loopback listener is refused without TLS;
- `PlatformBinding.member_portal_url` is navigation metadata with the same
  origin/TLS checks as the Bridge endpoint and carries no credential;
- Personal Agent Web renders that Member Portal link but continues to use the
  Bridge endpoint and Bridge token only for catalog reads.

## Exit evidence for slice 3

- opening or refreshing the Shared Platform view performs catalog discovery
  only and writes no asset, inventory row or authorization bundle;
- synchronization requires the explicit Web button and a closed empty request;
- the Web adapter calls the existing verified, all-or-nothing
  `PlatformClient.synchronize` path and owns no installer logic;
- a successful response includes typed before/after projections and the exact
  installed identities and active selection count;
- missing configuration, unreachable platform and platform/local refusals are
  typed, visible results and do not turn publication into authorization;
- the loopback, Host-header and per-process bearer guards apply to the action;
- focused real-socket integration tests and the Windows/Python 3.12 verification
  baseline pass.

## Exit evidence for slice 4

- Personal Agent Web lists every installed Workflow by exact scoped identity
  and shows its declared input-contract name without workflow-specific UI code;
- one JSON object is submitted through a closed request that cannot claim the
  actor, Bridge, authorization, route or model;
- the resident Agent performs local membership admission, then the existing
  Gateway exact-target, Workflow engine and Bridge policy path executes it;
- retries carrying the same idempotency key join the same run;
- success, refusal and Workflow failure are shown with run, trace and request
  identifiers and the durable recent-run projection is refreshed;
- real-socket tests prove execution and authorization boundaries; the Windows
  Python 3.12 verification baseline passes.

## Exit evidence for slice 5

- Personal Agent Web lists each exact configured Knowledge version using its
  validated local manifest and never returns the local Vault path;
- one closed request names only the exact Knowledge identity and question and
  cannot claim actor, Bridge, model, route, Vault or authorization state;
- the local adapter invokes the existing `knowledge-query/ask@1.0.0`
  capability through `LocalAgent` admission and Bridge policy;
- the existing handler performs retrieval and synthesis and returns a
  `KnowledgeAnswerRecord`; the Web layer owns no retrieval or model logic;
- the answer, trace identifiers and every cited Raw passage retain their
  source/page/slide/section provenance;
- real-socket tests prove success, request closure, exact-version selection,
  citation preservation and permission refusal; the Windows Python 3.12
  verification baseline passes.

## Exit evidence for slice 6

- the deployable Shared Platform accepts an absolute SQLite Registry path and
  reopens published package metadata and artifact bytes after process restart;
- package identity remains the exact `namespace + name + version` tuple and a
  duplicate exact version is refused across restarts;
- artifact bytes are committed only after their declared SHA-256 digest is
  verified, and package plus artifact writes are atomic;
- existing catalog discovery, installation planning and synchronization use
  the durable implementation through the same contracts and wire format;
- an unknown schema or corrupt record fails closed instead of serving
  ambiguous Registry state;
- credentials, invitation proofs, member sessions, device selections, remote
  jobs and Bridge/local execution state are not stored in the catalog.
