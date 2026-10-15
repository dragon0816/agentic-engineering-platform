# Account and password sign-in for the Member Portal

Owner request: 2026-10-15 ("signing in only by invitation link is too
cumbersome"). Status: **implemented 2026-10-15 on main (not pushed); live check
on the Shared Platform pending (owner deploys).** Decision in
`docs/DECISIONS.md` (2026-10-15 "Members sign in to the Member Portal with an
account and a password").

## Goal

A member signs in to the Shared Platform Member Portal with their account name
and a password. Invitations stay the only way to become a member: the first
sign-in with an invitation sets the password in the same step. The browser
gets the same revocable login and one-hour session as an invitation sign-in
gives today, so everything after sign-in is unchanged.

Out of scope here: one-click sign-in from Agent Web (a later task), a
production identity provider, self-service "forgot password" by e-mail.

## Owner decisions (2026-10-15)

1. **First sign-in.** Opening an invitation link shows "Set your password" for
   the invited account; the password is set and the person is signed in in one
   step. A member who already joined without a password sets one from the
   portal while signed in ("Password" in the header).
2. **Later sign-in.** The sign-in screen offers account + password first.
   Invitation (and password reset) links stay available below it.
3. **Storage.** Only a slow salted hash: `hashlib.scrypt`, per-user random
   16-byte salt, cost recorded with each hash so it can be raised later;
   constant-time comparison. Never logged, echoed or returned.
4. **Policy.** At least 12 characters (passphrases welcome, at most 256);
   refused when it contains the account name, is a very common password
   (small built-in list) or is one character repeated.
5. **Rate limit.** Failed attempts are counted per account and per client
   address; too many lock that key for 15 minutes. Every failure, including an
   unknown account, a member without a password, a disabled member and a
   locked key, answers the same `authentication_failed`.
6. **Forgot password.** An administrator issues a password reset link from
   Members & invitations: single use, short expiry, delivered like an
   invitation. Opening it lets the member set a new password; all their
   browser logins and sessions are revoked, and the browser that reset it is
   signed in. An administrator can also "Force sign-out" a member.
7. **Change password** while signed in needs the current password; the other
   browser logins and all sessions are revoked, this browser gets a new login.
8. **Transport** unchanged: loopback HTTP is allowed; beyond loopback the
   portal refuses to start without TLS.

## Design

### Storage (`control_plane/member_password.py`)

- `PasswordRecord` per account in the additive identity table
  `identity_passwords` (`schema_version` unchanged): algorithm `scrypt`, `n`,
  `r`, `p`, salt and digest (hex), `set_at`, `set_by`
  (`invitation`/`self`/`change`/`reset`). Default cost `n=2**15, r=8, p=1`
  (32 MiB, about 0.1-0.3 s per check on a busy office PC; `p=3`, the full
  OWASP-equivalent setting, took over a second there). Verification uses the
  record's own cost, so the default can be raised later without a migration.
- `PasswordResetGrant` per link in `identity_password_resets`: id, account,
  SHA-256 fingerprint of the 32-byte random secret (as invitations), issuer,
  times, status `active`/`used`/`revoked`. Issuing a new link for an account
  revokes its earlier active link.
- Attempt counters (`FailureLimiter`) are in memory: a restart clears them.
  Account: 5 failures in 15 minutes lock it for 15 minutes. Address: 20
  failures in 15 minutes lock it for 15 minutes. The address limit is higher
  because the live platform is reached through an SSH tunnel or relay, so
  every member arrives from `127.0.0.1`; 5 there would let one person lock
  everybody out. A success clears the account's counter.
- An unknown account or one without a password is verified against a fixed
  dummy hash, so the answer takes about as long as a real check. A locked key
  is refused without hashing (the lock says nothing about whether the account
  exists, and hashing for a locked key would only spend CPU).

### Routes (`POST /v1/member/...`)

| Operation | Credential | Body | Reply |
|---|---|---|---|
| `sign-in` | `Invitation id:secret` | empty, or `{"password"}` | `session`, `login`, `expires_at`; with a password it is set first (policy checked before the invitation is used) |
| `sign-in/check` | `Invitation` or `Reset id:secret` | empty | `purpose` (`invitation`/`reset`), `actor`, `expires_at`, `password_set`; nothing is used up |
| `sign-in/password` | none | `{"account","password"}` | `session`, `login`, `expires_at`; any failure `authentication_failed` (401) |
| `password/reset` | `Reset id:secret` | `{"password"}` | `session`, `login`, `expires_at`; revokes the member's browser logins and sessions |
| `password/status` | member session | `{}` | `password_set`, `set_at` |
| `password/set` | member session | `{"password"}` | `password_set: true`; `password_already_set` (409) if one exists |
| `password/change` | member session | `{"current_password","new_password"}` | `session`, `login`, `expires_at`; wrong current → `authentication_failed`, counted like a sign-in |
| `admin/members/password-reset` | administrator session | `{"actor","valid_for_minutes"?}` (default 60, at most 1440) | `url` (`/#reset=…`), `reset_id`, `actor`, `expires_at` |
| `admin/members/sign-out` | administrator session | `{"actor"}` | `logins_revoked`, `sessions_revoked` |
| `admin/members/credentials` | administrator session | `{}` | per member `password_set`, `password_set_at`, `active_logins`, `reset_link_expires_at` |

- A rejected password answers `password_rejected` (400) with `reason`
  (`too_short`, `too_long`, `contains_account`, `too_common`, `repeated`) and
  a message; the password itself is never in it.
- A reset link answers `authentication_failed` (unknown or wrong),
  `reset_link_used`, `reset_link_expired` or `reset_link_revoked`; a disabled
  member's link answers `authentication_failed` without being used up.
- Password bodies are parsed by hand, not as a `Contract`, so a validation
  error can never carry the value. Request bodies stay within 256 KiB.
- "Browser logins" are logins not labelled `Personal Agent`. Reset and change
  revoke browser logins (the password guards the browser, the Agent login is a
  separate credential the member issued); **Force sign-out revokes every
  login, the Personal Agent's included**, and all sessions.
- A disabled member cannot sign in with a password, use a reset link, or renew
  a session from a stored login (`session` answers `actor_disabled`).
- Sign-in by password creates an `AuthenticatedActor` with method `password`.

### Portal page

- Sign-in screen: "Sign in" form (Account `autocomplete="username"`,
  Password `autocomplete="current-password"`), and below it "Have an
  invitation or a password reset link?" with the link field.
- Opening `#invitation=…` or `#reset=…` (or pasting one) checks the link and
  shows "Set your password" / "Choose a new password" with the account name,
  New password and Confirm (`autocomplete="new-password"`) and the rule; it
  signs in when done. The fragment is removed from the address bar at once,
  as before.
- Header "Password" button: set a password (no current one needed) or change
  it (current + new + confirm). A member without a password sees a notice
  inviting them to set one.
- Members & invitations: a Password column (set / not set / reset link
  pending until …), and per member "Password reset link" (shows the link with
  Copy, like an invitation) and "Force sign-out" (with a confirmation).

## Tests

`tests/test_member_password.py`: hashing and verify (salt, cost, constant-time
compare, record never holds the password), policy, lockout per account and per
address with uniform errors and time-based release, invitation + set password
(policy checked before the invitation is used), check route, reset link single
use, expiry, re-issue revokes the earlier one, reset revokes browser logins and
sessions but keeps the Agent login, change password (current required,
revokes other logins), set only once, disabled member, admin-only routes,
force sign-out, durable records across a restart, no password in any reply or
stored record, page hooks, and a headless browser render of the sign-in screen
and the set-password step measured by size.

## Risks and limits

- Counters are per process and in memory; a restart clears them.
- A single platform administrator who forgets their password and has no
  remaining browser login needs a new bootstrap invitation for another
  administrator account (`platform.json` `invitations`), who then issues a
  reset link.
- Behind one tunnel every member shares one address; the per-address limit is
  therefore 20, and a determined guesser is still stopped per account at 5.
