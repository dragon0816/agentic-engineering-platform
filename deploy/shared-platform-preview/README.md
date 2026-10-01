# Shared Platform Windows preview

Start with `START-HERE.md`. This package installs the repository's existing
`aep-platform serve` reference process as a separate Windows role. It does not
install or run a Personal Agent or Bridge.

The process provides two entry points over one shared state:

- the Bridge API for device enrollment, package synchronization and remote jobs;
- the Member Portal for invitation sign-in, Agent Add-on selection and independent
  Application discovery.

The SQLite Registry preserves published package metadata and verified artifact
bytes across restarts. Members, invitations, sessions, authorizations and remote
jobs are still in-memory reference state in this preview. It is therefore suitable
for integration testing and product validation, not production deployment.

The installed `platform.json` starts loopback-only. A non-loopback listener is
rejected unless both TLS certificate and private-key paths are configured. Secret
values never belong in this package or its configuration.

See the repository's `docs/shared-platform-preview.md` for configuration semantics
and invitation delivery behavior.
