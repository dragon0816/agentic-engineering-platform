# Shared Platform reference process

The Windows CI artifact `aep-shared-platform-windows-<main commit SHA>` packages
this process as a separate offline role. After extraction, follow its bundled
`START-HERE.md`; it installs under
`%LOCALAPPDATA%\AgenticEngineeringPlatform\shared-platform-preview-0.1.0` and
does not expose the Personal Agent/Bridge launcher. The Agent + Bridge uses the
separate `aep-windows-preview-<same SHA>` artifact.

`aep-platform serve` starts the Bridge API and the interactive Member Portal
in one process. Both entry points use the same enrollment, package,
authorization and member-session state while keeping their credentials
separate:

- the Bridge API accepts a device-bound Bridge access token;
- the Member Portal accepts a one-time invitation proof and then a short-lived
  member session;
- neither credential can be used at the other boundary.

The checked-in [`examples/shared-platform.json`](../examples/shared-platform.json)
contains only non-secret bootstrap metadata and an absolute local Registry
path. Start the loopback reference host from PowerShell with an invitation
output outside source control:

```powershell
$InviteOut = Join-Path $env:LOCALAPPDATA "AgenticEngineeringPlatform\invitation-links.json"
aep-platform serve `
  --config examples/shared-platform.json `
  --invitation-output $InviteOut
```

The output file contains one-time invitation links and must be delivered only
to the named members, then removed when no longer needed. The command creates
the file exclusively and refuses to overwrite an existing delivery file. No
proof is written to the configuration or a Registry asset.

The example listens only on loopback. For an internal-network deployment,
choose the machine's specific DNS name or IP and configure both
`tls_certificate_path` and `tls_private_key_path` (PEM files); a non-loopback
listener is rejected without TLS. Both ports use the same TLS context. The
private-key file remains deployment-local, readable only by the account that
runs the platform, and must not be committed or copied off the machine.

A self-signed certificate is fine (owner 2026-10-16): members' Agents pin its
SHA-256 fingerprint instead of trusting it through Windows. Print the value to
hand out with

```powershell
aep-platform certificate-fingerprint --config platform.json
```

(`serve` prints it at start too). How to issue the certificate on the platform
machine, open the firewall and start the platform at boot is in the bundle's
`START-HERE.md`; the Agent side is in `docs/phases/BRIDGE_ENROLLMENT.md` "TLS
and certificate pinning".

The Personal Agent Web link is configured independently from the Bridge API:

```json
{
  "platform": {
    "base_url": "https://platform.internal:8765",
    "member_portal_url": "https://platform.internal:8766",
    "token_id": "token-issued-for-this-bridge",
    "credential": {"name": "platform_token"},
    "certificate_sha256": "83:95:B0:...:BA:8B"
  }
}
```

`base_url` is used only by the Bridge client. `member_portal_url` is
non-secret navigation metadata rendered by Personal Agent Web; the Bridge
token is never sent to it. `certificate_sha256` (optional, also on
`publishing`) pins the platform's exact certificate; `ca_file` (a PEM path)
verifies against a CA instead; without either the Windows trust store decides.
Agent Web's Settings > Shared platform > "Platform certificate" fills it after
the member compares the fingerprint. Verification is never switched off.

Published package metadata and verified artifact bytes survive a restart in
the configured SQLite Registry. Members, sessions, invitations, device
selections and remote jobs remain in-memory reference state. The process does
not yet expose an administration UI or production identity provider; the
durable catalog does not move Bridge or Personal Agent execution into the
shared platform.
