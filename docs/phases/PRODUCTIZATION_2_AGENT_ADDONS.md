# Productization 2 — Agent Add-on Marketplace

Status: active

## User outcome

An enrolled member uses the Shared Platform and Personal Agent Web surfaces to
discover, select, synchronize and use governed Agent Add-ons. Agent Add-ons are
exact-version Workflows, Skills, Knowledge and Agent profiles. Installing an
add-on changes no capability grant and never loads arbitrary executable code.

Productization 1 already completed the Workflow path and grounded queries for
locally configured Knowledge. This milestone extends the same contracts rather
than adding another marketplace or execution plane.

## First acceptance scenario — install and inherit a Skill

Given an entitled published Skill and a member bound to one Bridge:

1. the member portal lists the exact Skill beside published Workflows;
2. the member selects the Skill using only its scoped identity and Bridge id;
3. the platform derives `kind=skill` from trusted package metadata;
4. the separate Bridge synchronization installs the validated Skill manifest;
5. rebuilding the local host loads that Skill into the existing
   `SkillRegistry`;
6. the Personal Agent resolves the Skill's deterministic command and executes
   its already-authorized Workflow;
7. selection and installation add no capability grant or approval.

The green path crosses the real member HTTP entry point, control-plane HTTP
transport, Bridge synchronization, host rebuild, Local Agent, Gateway,
Workflow engine and Bridge policy. CI uses fixtures and no external side
effect.

## Architecture boundary

- Reuse `PublishedAssetPackage`, `DeviceAssetSelection`, `PlatformClient`, the
  all-or-nothing installer and `SkillRegistry`.
- Member requests continue to name no actor, group, kind, permission, policy
  or decision time. The authenticated platform derives all of them.
- A Skill remains procedure/routing data. Its command targets an installed
  Workflow or capability and creates no executable import boundary.
- Workflow and Skill selection may share a member UI because both use the same
  existing install path. Knowledge and Agent profiles need their own validated
  package and activation rules before they join it.
- Publication, selection, installation and execution authorization remain
  independent states.

## Incremental slices

1. **Skill selection and activation** — generalize the member catalog to
   Workflows and Skills, derive kind from Registry metadata, synchronize an
   exact Skill and prove the rebuilt Agent uses it.
2. **Portable Knowledge package** — define a path-safe package for one exact
   Knowledge manifest plus immutable Raw and curated Wiki content; install it
   without accepting a publisher-controlled local Vault path.
3. **Knowledge marketplace activation** — member selection, synchronization,
   exact local binding and grounded Personal Agent Web query for the installed
   Knowledge version.
4. **Agent profile package and activation** — install a validated
   `AgentProfile`, explicitly choose the local active profile and narrow its
   Skills, Knowledge, capabilities and model requirements. Do not add
   specialist delegation or several concurrent Agents in this milestone.
5. **Version change and rollback** — make update/removal explicit and preserve
   a usable previous version without turning publication into authorization.

## Exit criteria

- Personal Agent Web can show and use exact installed Workflow, Skill,
  Knowledge and Agent-profile add-ons through their existing runtime owners.
- Every portable package rejects path traversal, embedded credentials, identity
  mismatch, digest mismatch and incompatible runtime metadata before writing.
- A synchronized authorization decision is still separate from local
  capability grants and technical approval.
- Failed synchronization is all-or-nothing and local installed assets continue
  to work while the platform is unavailable.
- The Windows/Python 3.12 baseline and inert E2E tests pass.

## Exit evidence for slice 1

- the real member HTTP catalog lists exact entitled Workflows and Skills and
  reports selection separately from publication;
- select/revoke requests remain closed and cannot claim actor, kind,
  permission, policy, approval or decision time;
- the platform derives Skill kind from its Registry package, while Knowledge
  and other not-yet-installable kinds are refused;
- the real control-plane HTTP and Bridge synchronization install the selected
  Skill and Workflow manifests all-or-nothing;
- rebuilding the host loads the synchronized Skill and its deterministic
  command completes through Local Agent, Gateway, Workflow and Bridge policy;
- selecting the Skill does not add or widen any capability grant.

## Explicit exclusions

- executable Bridge plug-in loading;
- independent Application install or process management;
- production identity/RBAC;
- specialist delegation or multiple simultaneous Agents;
- arbitrary package scripts, post-install commands or publisher-provided paths.
