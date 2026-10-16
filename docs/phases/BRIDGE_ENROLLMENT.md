# Enroll a Personal Agent's Bridge on the Shared Platform

Owner request: 2026-10-15. Status: **approved 2026-10-15 with option (a); implemented 2026-10-15 (platform route, portal Bridges list, Agent Web card, assets-only sync). Live test on 172.25.228.141 pending.** TLS with a pinned self-signed certificate: 2026-10-16, see "TLS and certificate pinning".

## Goal

A member's PC gets the Shared Platform's catalog in "Share Platform Library" and installs
what the member selected ("Synchronize selected"). That needs a Bridge token. Today the
platform can only issue one through in-process calls (tests); no route or command exists.

This follows `docs/phases/MEMBER_PUBLISH.md`, which closed the publish half
(PC → platform) on 2026-10-15 with a live test on 172.25.228.141. This closes the
install half (platform → PC).

## Owner decisions (2026-10-15)

1. Build Bridge enrollment to the Shared Platform.
2. The Member Portal address that "Open Marketplace" uses is set by the user in their
   own settings, not fixed by us.
3. A PC with a hand-written `grants.json` uses option (a), **assets-only sync** (see
   section 3): sync installs the selected files and leaves authorization to
   `grants.json`, and the Library says so.

## What exists

- Platform:
  - `InMemoryEnrollmentRegistry.register_device(device, advertisement)`;
  - `bind(requested_by, BridgeBinding)` (one active member per device; a
    `device_admin` binding only for the member who registered it);
  - `InMemoryAccessTokens.issue(requested_by, actor, bridge_id)` (refuses
    `actor_not_admitted`, `duplicate_token` while one still works).

  All are durable in the Registry's SQLite file.
- Agent:
  - `aep-host enrollment-request` already describes this device (`EnrollmentRequest`:
    `config.device` + a `BridgeRegistration`) without secrets;
  - `PlatformBinding` (host.json `platform`: `base_url`, `member_portal_url`,
    `token_id`, `credential`);
  - `PlatformClient` (probe, catalog, advertise, sync, report, poll, settle, feedback).
- The Agent already holds the member's `Personal Agent` login (publishing).
- **This PC today:**
  - `platform` points at an old local test platform (`127.0.0.1:18765/18766`, not
    running), hence `platform_unreachable` and an empty "Open Marketplace".
  - A hand-written `workspace\grants.json` exists, and sync refuses
    (`sync_grants_conflict`) whenever it is present: the file and the platform must
    never give two answers about what this PC may run.

## Design

### 1. Self-enrollment as the member

New Member Portal operation `bridges/enroll`. The member's session is required: the
Agent uses its `Personal Agent` login, so there is nothing new to paste.

- **Body:** the existing `EnrollmentRequest` (device facts and advertisement, built
  by the Agent).
- **Checks:**
  - `device.registered_by` and `advertisement.owner_id` must be the signed-in member
    (`device_owner_mismatch`);
  - self-enrollment is limited to `company_workstation` devices (a shared test
    workstation stays an administrator's act: `administrator_required`).
- **Effect:**
  - registers the device, or reuses it when this member registered it before;
  - binds the member as `device_admin`, unless already bound;
  - issues a token. A still-working token for the same pair is revoked first, so
    re-enrolling rotates it.
- **Reply, shown once:** `bridge_id`, `token_id`, the token bearer and `expires_at`.
- **Administrators:** a "Bridges" list in the portal (device, member, enrolled at,
  token expiry) with "Disable", so an administrator can withdraw a PC.

### 2. Agent Web "Shared platform" settings card

One card in Settings, writing host.json like the Laya card does (backup first, then
validated):

- **Member Portal URL**, used by "Open Marketplace" and by publishing. One field,
  owner decision 2: the user sets it. It replaces `publishing.member_portal_url` and
  `platform.member_portal_url`, which stay as one value.
- **Bridge API URL** (`platform.base_url`).
- **Personal Agent code**: the paste box moves here from Capabilities.
- **"Enroll this PC"** sends the enrollment, then:
  - saves the token for this Windows user (as with the Telegram token, never in a
    file), under its own variable (`AEP_SHARED_PLATFORM_TOKEN`, so the old local
    platform's token is untouched);
  - writes `platform` (`base_url`, `token_id`, credential name) into host.json;
  - switches the running Agent to the new client without a restart.
- **Status:** enrolled as `<bridge_id>`, token expiry, last catalog read.

Over the SSH tunnel, both URLs are loopback HTTP (`127.0.0.1:28775/28776`). Beyond
loopback HTTPS stays required; a self-signed platform is trusted by its pinned
fingerprint (2026-10-16, "TLS and certificate pinning").

### 3. Local grants and platform sync

A PC with a hand-written `grants.json` cannot sync, by design. Options for this PC:

- **(a) Recommended: assets-only sync while `grants.json` exists.**
  - Sync installs the selected Skill and Workflow files.
  - It leaves authorization to `grants.json`, so nothing this PC may run changes
    silently.
  - Library shows "installed; permissions come from this PC's grants.json".
- **(b)** Move this PC to platform-managed authorization. Rename `grants.json` away
  (kept as a backup); the platform's authorization bundle then decides what runs.
  This is the intended end state for colleagues, but it changes what this PC may run
  today.
- **(c)** Keep the refusal; sync only on PCs without `grants.json`.

### 4. Security

- **Separate credentials.** The Bridge token is issued only to the member's own
  session, for their own company workstation. It never goes to the portal again, and
  the member login never goes to the Bridge API.
- **Shown once, stored by Windows.** The token is shown once, kept in the Windows
  user's environment and never logged.
- **Revocation.** Re-enrolling rotates the token; an administrator can disable a device.
- **Enrollment grants nothing.** Every run is still authorized by the Bridge policy.

## Tests

- **Platform:**
  - enroll (new device, re-enroll rotates, wrong owner, shared device refused,
    disabled member);
  - the Bridges list and disable;
  - a token issued by `bridges/enroll` works for `probe` / `catalog`.
- **Agent:**
  - the settings card writes a valid host.json and keeps a backup;
  - the token is saved and never echoed;
  - the client switches without a restart;
  - assets-only sync (if (a)).
- **End to end in process:** a member publishes, an administrator approves, another
  member's PC enrolls, sees it in the catalog, selects it and synchronizes it.

## Live test on 172.25.228.141

1. Redeploy the platform.
2. In Agent Web Settings, set both URLs (tunnel) and press "Enroll this PC".
3. Library lists the two assets published on 2026-10-15 (`company-agent/knowledge-query`,
   `company-agent/personal-proof`).
4. Select them in the portal, then "Synchronize selected" here.
5. Both are installed. Under (a), permissions stay with `grants.json`.

## Owner answer (2026-10-15)

Option (a), assets-only sync. Recorded in `docs/DECISIONS.md`.

## As built (2026-10-15)

- **Platform.** `bridges/enroll` (member session; body `BridgeEnrollRequest`, the
  `EnrollmentRequest` shape) in `control_plane/member_http.py`, logic in
  `MemberService.enroll_bridge`. Codes: `device_owner_mismatch` 403,
  `administrator_required` 403, `actor_disabled` 403, `device_disabled` 409,
  `device_in_use` 409. The token lasts 90 days (`BRIDGE_TOKEN_LIFETIME`). The reply is
  `bridge_id`, `token_id`, `secret`, `issued_at`, `expires_at`.
- **Administrators.** `admin/bridges/list` and `admin/bridges/disable` and a "Bridges"
  panel in the portal. Disable marks the device disabled and revokes its tokens; the
  member then gets `device_disabled` when enrolling again.
- **Portal link.** "Open Marketplace" opens `<portal>/#bridge=<bridge_id>`, so the
  portal's Bridge ID field is already filled.
- **Agent.** `host_runtime/shared_platform.py` and `AgentWeb.update_shared_platform`
  (`GET`/`POST /api/settings/shared-platform`). The card:
  - checks the login's account (`me`) against `device.registered_by` first;
  - saves the token in `AEP_SHARED_PLATFORM_TOKEN` (Windows user environment and the
    running process), maps `shared_platform_token` to it in `credentials`, and
    leaves the old platform's mapping alone;
  - backs host.json up as `host.json.bak-<stamp>-before-shared-platform`, then writes
    it validated;
  - replaces `runtime.platform` at once. A host built later also reads the saved token
    from the user's environment (`UserEnvironment`).
  - Non-secret enrollment facts are kept in `workspace\shared-platform.json`.
- **Assets-only sync.** With `grants.json` present, `PlatformClient.synchronize`
  installs the files and records the inventory, but writes the device bundle to
  `platform-selections.json` (display only) instead of `authorization.json`.
  `SyncOutcome.assets_only`, `PlatformSyncResult.assets_only` and
  `PlatformProjection.assets_only` say so.

## TLS and certificate pinning (owner request 2026-10-16)

Status: **implemented 2026-10-16 on main (not pushed); deployed on 172.25.228.141.**
Decision in `docs/DECISIONS.md` (2026-10-16 "A self-signed Shared Platform is trusted by a
pinned SHA-256 fingerprint").

The Shared Platform on 172.25.228.141 is reached directly over the company network with a
self-signed certificate (no SSH tunnel). The platform already served TLS
(`tls_certificate_path` / `tls_private_key_path`, both ports one context); what was missing
was the Agent's trust.

- **Trust per binding, never global.** host.json `platform` and `publishing` gained
  `certificate_sha256` (the exact certificate's SHA-256, stored as `AB:CD:...`; hex with or
  without colons is accepted) and `ca_file` (a PEM file to verify chain and host name
  against). Not both. Without either, Windows' trust store decides, as before.
- **Where it applies.** `PlatformClient` (probe, catalog, sync, poll, report, feedback),
  `MemberPortalPublisher` (publish, enroll, `me`, select/revoke, browser ticket for "Open
  Marketplace", Library content) and the enrollment check of the Bridge API. The
  assistant and authoring paths reach the platform only through these two clients, so they
  follow the same binding. Code: `common/certificates.py`.
- **How a pin is checked.** `PinnedHTTPSConnection` completes the TLS handshake, compares
  the presented certificate's SHA-256 with the pin and closes the connection on a
  mismatch, **before any request byte (the `Authorization` header included) is sent**.
  Only this connection skips chain and name checks, because it compares the whole
  certificate instead. `ssl`'s process default and every other HTTPS call are untouched.
- **Failure.** A missing pin with an untrusted certificate, a wrong pin, or a CA file of
  another certificate is `certificate_untrusted` (not retryable; the Bridge client reports
  it as `unreachable` with that code, the publisher raises it, enrollment refuses it before
  anything is saved). A wrong pin's message names both fingerprints (public).
- **Agent Web.** Settings > Shared platform > "Platform certificate":
  - **Fetch & show fingerprint** (`POST /api/settings/shared-platform/certificate`) reads
    the certificate each https address presents (a handshake, nothing sent) and shows its
    SHA-256, whether Windows already trusts it and whether it matches the pin; a portal and
    Bridge API that present different certificates are refused (`certificate_mismatch`);
  - **Trust this certificate** saves exactly the fingerprint the member compared
    (`certificate_sha256` in the card's save) into both bindings, backup first; the running
    Agent switches at once;
  - **Forget** removes the pin; **Download .cer** saves the public certificate for the
    browser (below).
- **Browsers.** Agent Web's links open the portal in the member's browser, which warns about
  a self-signed certificate. Either accept the warning once per browser after comparing the
  fingerprint in the certificate viewer, or import the downloaded `.cer` into the Windows
  user's "Trusted Root Certification Authorities" (`certutil -user -addstore Root
  shared-platform.cer`). Risk of importing: whoever holds the platform's private key could
  then impersonate any https site to that Windows user. The key is generated on the
  platform machine, readable only by its service account and never copied off; remove the
  certificate (`certmgr.msc`) when the platform gets a company-issued certificate.
- **Platform side.** `aep-platform certificate-fingerprint --config platform.json` prints
  the fingerprint to hand out; `serve` prints it at start. The TLS handshake now runs on
  each request's thread with a 10-second limit (`control_plane.http.tls_listener` /
  `finish_tls`): before, `accept()` did it on the one accepting thread, so a client that
  connected and sent nothing (a port scan, a browser that rejected the certificate) stopped
  the platform for everybody.

Tests: `tests/test_platform_certificate_pinning.py` (pin forms, bindings, the CLI
fingerprint, a wrong pin sends no byte and a right one connects against a recording TLS
server, verification stays on for everything else, Bridge client and publisher with pin /
CA file / none / wrong pin, a silent client does not stop the TLS platform, the card
fetches, trusts, enrolls over https, keeps, replaces and forgets the pin, page hooks, and a
real browser pressing Fetch and Trust). Each test run makes its own self-signed certificate
with `openssl`.

## Not in scope

- Shared test workstations (administrator enrollment).
- A company-issued (CA-signed) certificate; `ca_file` and the system store already cover it.
- Deprecation notices to Hosts.
