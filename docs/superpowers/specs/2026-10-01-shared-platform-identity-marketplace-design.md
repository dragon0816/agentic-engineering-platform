# Shared Platform identity and governed marketplace

Date: 2026-10-01  
Status: approved direction; pending written-spec review

## Problem

The reference Shared Platform already has one-time invitation proofs, member
sessions, group-derived entitlement and separate Bridge credentials. The
Marketplace does not expose those concepts as a complete user flow. Opening
the page without a fragment shows no useful sign-in action, a signed-in member
cannot see who they are, and an administrator cannot issue invitations. The
local bootstrap also constructs identity state in memory, so it does not yet
behave like an account-bearing service.

The Registry has no category metadata. An empty Registry therefore proves that
the process runs but does not let an evaluator exercise visibility, selection,
installation or extension governance.

## Scope and acceptance criteria

This slice will make the Shared Platform usable as an invitation-only,
multi-user local service:

1. An empty platform has one bootstrap invitation. The first person who
   redeems it becomes `platform_admin`.
2. A signed-out visitor sees a sign-in page that accepts an invitation link or
   invitation code. The first valid proof creates the account, a revocable
   browser login credential and a short-lived member session. The browser uses
   its login credential to obtain later sessions without reusing the one-time
   invitation.
3. A signed-in member sees their actor, role and trusted platform groups.
4. A platform administrator can issue and revoke one-time invitations, choose
   the invited actor, role (`member` or `platform_admin`), groups and expiry,
   and copy the generated invitation URL. A normal member cannot call or see
   these administration actions.
5. The catalog returns only published packages to which the authenticated
   member is entitled. The browser never supplies its own role or groups.
6. Skills and Workflows carry category metadata and can be filtered by kind,
   category and text. Older assets with no categories remain valid.
7. The local preview publishes two test Skills, two test Workflows and one
   test Bridge Extension with distinct ownership, visibility and categories so
   permission behavior can be observed.
8. Selecting an Agent Add-on records an exact device decision. Installation
   occurs only when that Bridge explicitly synchronizes. Discovery and
   selection do not grant runtime permission.
9. A Bridge Extension has a separate administrator-only deployment path. The
   administrator may stage an exact compatible, signed package; activation
   still requires the existing device and technical-policy approval evidence.

## Identity and invitation contracts

`Invitation` gains a backward-compatible role with `member` as its default.
The accepted `PlatformUser` records the same role. The configured bootstrap
invitation is the only way an empty platform creates its first administrator;
being the first HTTP request does not grant authority.

New member-facing contracts provide:

- `MemberIdentityReply`: actor, role, groups and session expiry;
- `MemberLoginGrant`: actor, fingerprint, issue/expiry time, browser label and
  revocation state;
- `AdminInvitationCreateRequest`: actor, role, groups and bounded expiry;
- `AdminInvitationReply`: secret-free invitation metadata plus the one moment
  an out-of-band invitation URL is returned;
- `AdminInvitationListReply`: pending, accepted, revoked and expired metadata
  without proof secrets;
- `AdminInvitationRevokeRequest`: one pending invitation identifier.

The service derives the requester from the member session. Administrator
operations check the accepted user's stored role and do not trust a role from
the request. Invitation proof and session secrets remain fingerprint-only in
platform storage. URLs carry proof material in the fragment so it is not sent
by the initial HTTP GET, and the page removes the fragment from browser
history immediately.

Invitation acceptance returns a browser login secret only once. The browser
stores it in local storage and presents it to a dedicated session endpoint;
the platform stores only its fingerprint. A member can sign out by deleting
the local value, and an administrator can revoke the corresponding login
grant. Losing every login credential requires an administrator to issue a new
sign-in invitation for that existing actor; an accepted enrollment invitation
is never reusable.

Identity, invitation status, login grants and session grants are persisted in
the same local SQLite service boundary as the Registry, using separate tables.
Restarting the Shared Platform must preserve members, roles, groups, pending
invitations and revocation state. No password or company directory is
introduced in this slice.

## Permission and catalog behavior

The existing `entitled` rule remains authoritative: owners, owning groups and
contributors can discover their packages; organization/public packages are
available to platform members; team/private packages do not widen beyond their
recorded ownership. The same entitlement decision gates catalog display,
selection and artifact delivery.

`AssetMetadata` gains `categories: tuple[Slug, ...] = ()`, with validation for
uniqueness. Categories are discovery metadata, not authorization claims. The
server returns categories on package metadata, and the Marketplace derives its
filter choices from the already-entitled result. Filtering in the browser
cannot reveal packages excluded by the server.

Agent Add-ons keep the existing lifecycle:

```text
published and entitled -> member selects exact version
                         -> Bridge synchronizes
                         -> package hash is verified and installed
                         -> runtime policy still authorizes every use
```

Bridge Extensions remain outside ordinary member Add-on selection. Their
admin-only staging endpoint accepts an exact package identity and Bridge ID,
checks administrator/device authority, compatibility, signature and approved
technical policy, then makes it available to the Bridge's existing extension
staging mechanism. Activation remains a distinct explicit operation with an
approval record.

## Marketplace experience

The page has three authenticated areas:

- **Account** shows actor, role, groups, session expiry and sign-out.
- **Agent Add-ons** shows entitled Skills, Workflows, Knowledge and Agent
  profiles with search, type and category filters. Buttons distinguish
  `Available`, `Selected`, `Installed after sync` and version replacement.
- **Extensions and Applications** distinguishes admin-governed Bridge
  Extension staging from external Application links.

Administrators also see **Invitations**, with an issue form and a table of
invitation states. A normal member receives `403` from the same APIs and the
administration panel is absent.

The seeded preview data is deliberately harmless:

- Skills: `incident-triage` (`support`, `analysis`) and `meeting-summary`
  (`productivity`, `documentation`);
- Workflows: `echo-request` (`testing`, `automation`) and `checklist-review`
  (`quality`, `automation`);
- Extension: `fixture-health` (`testing`, `extension`), an approved inert
  health responder whose package can be staged without external effects.

At least one package is organization-visible and one is engineering-team-only
so two invited users with different groups receive different catalogs.

## Failure and security behavior

Invalid, reused, revoked or expired invitation proofs and login credentials
return typed failures without saying which secret component was wrong. An
expired browser session is refreshed from the revocable browser login grant;
failure returns to the sign-in state without erasing local Bridge installation
state.
Invitation administration is serialized to prevent duplicate actors or IDs.
No secret, session bearer or invitation proof is written to configuration or
logs.

An unavailable Bridge can still be selected for later synchronization, but the
Marketplace must not claim installation. Extension compatibility, signature
or approval failure leaves the prior active extension unchanged.

## Verification

Contract and service tests will cover bootstrap-admin assignment, ordinary
member denial, invitation issue/revoke/redeem, login-grant issue/revoke,
restart persistence, session refresh/expiry and trusted group entitlement.
HTTP and browser tests will cover signed-out, admin and member experiences,
category filtering and catalog differences between groups.

End-to-end tests will select and synchronize a test Skill and Workflow, verify
their hashes and installed state, stage the test Extension as an administrator,
and prove it cannot activate without the separate approval. Existing package,
authorization, extension and Agent Web tests must continue to pass.

