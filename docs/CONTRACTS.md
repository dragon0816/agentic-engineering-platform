# Foundation contracts (0.1)

All boundary models reject unknown fields, validate defaults, and serialize with
Pydantic `model_dump_json` / `model_validate_json`. Metadata is frozen; Registry
ingress revalidates and stores serialized snapshots so caller mutations cannot alter
registered assets. Pydantic is a validation dependency, not a provider contract.

- `AssetIdentity`: namespace/name/full SemVer tuple, exact and case-sensitive.
  Namespace and name use lowercase slugs. Versions include prerelease/build metadata;
  no implicit latest-version resolution. Owner and visibility are independent fields.
- `AssetMetadata`: identity, owner, contributors, lifecycle, provenance, package
  dependencies, compatibility, separate business review and technical policy,
  evaluation/validation references, and optional deprecation/replacement metadata.
  Review records are descriptive claims, not verified signatures or permission grants.
- `ExecutionDependencies`: local capability names, central services with explicit
  required flags, and required `central_required`, equal to whether any service is
  required. Local execution may still require a central service. No resolver exists.
- `SecretRef`: symbolic name only. No values, credentials or backend configuration.
  Closed schemas reject secret-bearing extra fields; Registry assets recursively reject
  common credential assignments, bearer tokens and private-key markers in text.
  This is practical validation, not a guarantee of detecting arbitrary secrets hidden
  in prose. Callers must never submit secrets; errors should not be logged with inputs.
- `TaskManifest` and `WorkflowManifest`: metadata plus execution requirements,
  schema references and scoped capability/step identities. No embedded scripts.
- `CapabilitySpec`: scoped identity, input/output contract references and explicit
  read/write/execute/external_side_effect classification with policy requirements.
- `RequestContext`, `RouteDecision`, `CapabilityResult`, `WorkflowRun`,
  `ApprovalRequest`: traced typed boundary messages. Runtime execution authorization
  is a separate default-deny `ExecutionAuthorization`, never inferred from publication.
- `KnowledgeSource`: immutable source reference/checksum and page/slide provenance.
- `AgentProfile`: governed profile with allowed capabilities, Skills, Knowledge,
  delegation extension points, policy constraints and bounded model requirements.
  Only an engineering profile is supplied; no runtime loop or specialist is built.
- Model requests/responses use logical aliases, typed messages, tool calls and image
  references. Generation, selection and streaming are protocols without adapters.
- Evaluation cases declare requests, expected routes and forbidden side effects.
- Bridge registration advertises installed Tasks/capabilities and local resources;
  it neither downloads assets nor authorizes or executes them.

`TaskRegistry` stores validated/published Task manifests and supports exact get and
explicit discovery filters. The in-memory adapter only exposes published records to
discovery, rejects duplicate identities, and returns stable ordering. Visibility is
filter metadata, **not access enforcement**: this fixture must not be exposed as a
multi-user service. Authentication, review verification, transition workflows, RBAC,
availability checks and compatibility resolution are deferred.

`DeterministicRouter.resolve` returns a known route or `None`; callers must try it
before model selection. It has no model dependency. A route is intent, not authority.
No source command parser or runtime is migrated in Phase 1.
