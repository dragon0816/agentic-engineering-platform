# Platform overview and the tabbed Member Portal

Owner requests: 2026-10-15 (several, in one session). Status: **implemented
2026-10-15 on main (not pushed); live check on 172.25.228.141 pending (owner
deploys).**

## Goal

The Member Portal (`http://127.0.0.1:8776/` on the Shared Platform) is the
platform's management page. An administrator must see there the publication
status of everything: registered computers, Skills, Workflows, Knowledge,
Agent profiles, Extensions, Applications, submissions and members. Follow-ups
of the same day:

1. The owner of a name could not let another account publish new versions:
   the portal had no UI for co-editors or transfer. Administrators also set a
   member's role and groups, so team ownership works.
2. Every asset card must have the same size (like atcyrus.com/skills); opening
   one shows the full details.
3. Administrators adjust the sharing of any published asset, not only their own.
4. Opening a card shows the asset's actual content (like
   atcyrus.com/skills/baseline-ui), not only metadata.
5. The page was one long scroll: put it in tabs, kept in the URL.

## What was built

### Platform (control plane)

- `admin/overview` (administrators only, `not_administrator` otherwise):
  counts, Bridges, every published name of the five kinds with all versions,
  submissions, Applications and members. Built by `control_plane/overview.py`
  from the existing stores; nothing is filtered by the administrator's own
  entitlement. No reply carries a token, fingerprint, invitation proof,
  session or login.
- Last seen: `control_plane/activity.py` `BridgeActivity` records each Bridge
  API call a token proved (operation and time) in `ControlPlaneService._who`;
  kept in memory, written to the additive `bridge_activity` table at most
  once a minute per Bridge. `AdminBridgeEntry` gained `last_seen_at`,
  `last_seen_operation` and `selections`.
- `admin/members/update`: role and groups of a member, audited as a
  `PlatformUserChange` (additive `identity_user_changes` table). The last
  active platform administrator keeps the role (`last_administrator` 409).
- Administrators manage any name: co-editors, transfer and deprecation
  (`AssetOwnershipService._managed`), as they already could decide who may use
  it. Publishing stays with the owner, owning team and co-editors. Decision in
  `docs/DECISIONS.md` (2026-10-15 "Administrators manage the sharing of any
  published name").
- `assets/manifest`: one exact version's published content for a member it is
  shared with (administrators always); `asset_not_published` otherwise, 512 KiB
  cap. Contract in `docs/CONTRACTS.md` "Asset content"; Agent Web will reuse it.

### Portal page (`control_plane/member_page.py`)

- Tabs (`role=tablist/tab/tabpanel`, `aria-selected`, roving tab index, arrow,
  Home and End keys), one panel visible, `#tab=<name>` in the URL (reload and
  back keep it). Members: Marketplace, My published assets, My submissions,
  Applications. Administrators also: Overview (default), Review queue (waiting
  count on the tab), Registrations (Bridges), All published assets (kind
  filter, cards or sortable table), Members & invitations.
- One card component for every asset: equal grid rows, one-line title,
  namespace and version line, three-line clamped description, chips on one
  line, status and the action button at the bottom. Marketplace cards group
  the versions of a name.
- The detail view opens inside the current tab: the version's content from
  `assets/manifest` (Workflow: description, steps, run parameters, checks,
  risk, permissions, side effects; Skill: instructions as Markdown, commands
  and their targets, keyword rules, selector hint, script tools; other kinds:
  description and the full manifest JSON), metadata (owner, versions, who can
  use it, categories, provenance, reviews, dependencies, published date,
  deprecation, artifact hash) and the actions (Select for install / Remove
  selection; for administrators Who can use it, Owner and co-editors,
  Deprecate). Markdown is escaped first; only fixed tags and http(s) links are
  added. Everything else is set as text.
- Owner tools: "Owner and co-editors" (list, add, remove, transfer with a
  confirmation naming the new owner); every asset row says who may publish
  new versions, with readable refusal texts.

## Tests

- `tests/test_platform_overview.py`: admin and member access to each new
  route, counts and rows across kinds (Knowledge included), access override,
  invitation states, last seen (and its throttled durable write), no secret in
  replies, member role and groups (audit, last administrator), co-editor and
  transfer refusals, administrator management, `assets/manifest` (entitled,
  not entitled, administrator, unknown, too large).
- `tests/test_member_portal_tabs.py`: page hooks and a real-browser check:
  every administrator tab measured with only its panel visible and its hash,
  keyboard, reload and back, equal card heights (admin and member), Workflow
  and Skill content inside the tab, Markdown escaping, co-editor add with a
  refusal, the member's four tabs and a selection from the detail view.

## Not in scope

- Installs per Bridge (the platform records selections, not what a Bridge has
  installed).
- A publish date for versions seeded by the platform itself (only approvals
  through the review queue carry one).

## One-click sign-in from Agent Web (owner request 2026-10-15)

Status: **implemented 2026-10-15 on main (not pushed); live check pending
(owner deploys the platform and restarts Agent Web).** Decision in
`docs/DECISIONS.md` (2026-10-15 "Agent Web opens the Member Portal signed in
with a single-use browser ticket"); contract in `docs/CONTRACTS.md` "Browser
sign-in ticket".

Goal: "Open Marketplace" in Agent Web (Capabilities > Share Platform Library,
the Library card links for Extensions and Applications, and the Applications
empty state) opens the portal already signed in as this PC's member, with
nothing to type.

Hand-off:

1. Agent Web's page calls `POST /api/platform/portal-link` (its own token)
   with an optional `tab` (`[a-z]{1,20}`) and `asset`
   (`namespace/name@version`). It opens `about:blank` inside the click (so no
   popup blocker stops it) and drops `opener`.
2. Agent Web, server side, uses `MemberPortalPublisher` (the member's
   `Personal Agent` login from `UserEnvironment`, traded for a one-hour session
   held in memory) to call the platform's `POST /v1/member/browser-ticket`
   (member session, body `{}`). The platform answers `ticket`
   (`ticket-<16 hex>:<32-byte urlsafe secret>`) and `expires_at`.
3. Agent Web returns `<portal>/#ticket=<id:secret>&bridge=<bridge id>&tab=...&asset=...`.
   The ticket is only ever in the URL **fragment**, which the browser does not
   send in a request, never in a query string; the Personal Agent login never
   leaves the Agent. Nothing is logged or written to the task list.
4. The portal page removes the fragment from the address bar and history
   before anything else runs (as for `#session`/`#invitation`), then calls
   `POST /v1/member/sign-in/ticket` with `Authorization: Ticket <id:secret>`,
   empty body. The reply is the same as a password sign-in: `session`,
   `login`, `expires_at`; the page stores the login like any browser login and
   opens the asked tab, then the asked asset's detail in Marketplace.

Ticket rules (`control_plane/member_ticket.py`, `BrowserTickets`):

- Issued only for a valid member session of an active member
  (`actor_disabled` 403 otherwise); bound to that actor.
- At most 60 seconds (`TICKET_TTL`; a longer one cannot be configured).
- Single use: the first redemption with the right secret uses it up, whatever
  happens next. Unknown or wrong secret `authentication_failed` (401), used
  `ticket_used` (409), too old `ticket_expired` (401), member disabled since
  `actor_disabled` (403).
- Stored as a SHA-256 fingerprint of the secret, in memory only (a restart
  drops open tickets, harmless for something that lives a minute); at most
  five open tickets per member.
- The session's method is `agent-ticket`; the browser login's label is
  `Agent Web sign-in`. A new ticket sign-in revokes the member's earlier
  `Agent Web sign-in` login, so repeated clicks do not pile up 30-day logins
  (the Personal Agent's login and password-sign-in browsers are untouched). A
  member who opens the portal from Agent Web in two different browsers keeps
  only the latest one signed in through it.
- No new rate limit: guessing a 256-bit secret within a minute is not
  practical, and every guess is one HTTP request.

Fallback: with no Personal Agent code saved (or when the platform refuses or
does not answer), `portal-link` answers `signed_in: false` and the plain
portal address with the same `tab`/`asset`/`bridge` fragment; Agent Web shows
"save your Personal Agent code in Settings > Shared platform" (or the
platform's reason). After a normal sign-in the portal still opens the asked
asset.

## Library card content in Agent Web (owner request 2026-10-15)

Status: implemented with the hand-off above; same decision entry.

Opening a card in Agent Web's Share Platform Library shows the version's
published content, like the portal's detail view (and
atcyrus.com/skills/baseline-ui):

- Agent Web `POST /api/platform/asset-content` (`kind`, `asset`) reads
  `assets/manifest` (CONTRACTS "Asset content") with the member's session,
  server side. Errors: `content_not_shared` (the platform's
  `asset_not_published`: not shared with this member or not published),
  `login_missing`, `platform_unreachable`, `platform_not_configured`,
  `publishing_not_configured`, `bad_reference`, each with a sentence.
- The card keeps its layout: uniform closed cards; the open card spans the
  row and expands in place. Inside, the content is on the left and an aside on
  the right with the facts and the existing "+ Add to this Agent" / "Remove
  selection" actions; where the open card is narrower than 640 px (container
  query) the aside comes first and the content below.
- Skill: instructions as Markdown, command (alias), default command, selector
  hint, commands with what they run, keyword rules, script tools, harness
  guidance. Workflow: description, ordered steps (with step inputs), run
  parameters (label, name, kind, required, default, choices or choices
  source), checks after the run, risk, required permissions, approval, side
  effect (occupies the machine), local capabilities, secret names. Other
  kinds: description.
- Facts: version and other versions, owner, co-editors, who can use it,
  categories, provenance, business and technical reviewers, published date,
  dependencies, deprecation.
- Safety: every value is set as a text node. Markdown goes through the page's
  `renderMarkdown` (no `innerHTML`; links only via `safeMarkdownHref`, which
  allows http(s) and mailto), and card content additionally unwraps every link
  that is not http(s), so `mailto:` and `javascript:` become text. A
  `<script>` in instructions shows as text.
- Cache: content is kept per exact version for the page's lifetime (a
  refusal is asked again the next time the card opens). Nothing is cached on
  the Agent, so a withdrawn share takes effect on the next page load.

Tests: `tests/test_browser_ticket.py` (issue needs a member session, single
use, expiry at 60 s, disabled member at issue and redemption, fingerprint-only
in-memory storage, never accepted from a query string and never in output,
one Agent Web login per member, page hooks, real browser: signed in on the
asked tab and asset, fragment gone, a reused ticket explained);
`tests/test_library_content_web.py` (ticket URL in the fragment and redeemable
once, no Personal Agent login in it, fallback without a code / disabled /
unreachable, content entitled and not shared, routes need the page token,
page hooks, real browser at 1400 px: content and facts measured side by side,
narrow card stacks, uniform closed cards, malicious `<script>`, `<img>`,
`javascript:` and `mailto:` shown as text or dropped, Workflow content, Open
Marketplace opens a ticket URL).

## TLS on the company network (owner request 2026-10-16)

Status: **implemented 2026-10-16 on main (not pushed); 172.25.228.141 serves both ports
over https.** Decision in `docs/DECISIONS.md` (2026-10-16 "A self-signed Shared Platform is
trusted by a pinned SHA-256 fingerprint"); Agent side in
`docs/phases/BRIDGE_ENROLLMENT.md` "TLS and certificate pinning".

- The portal and the Bridge API listen on the machine's address with one self-signed
  certificate (`platform.json` `listen_host`, `tls_certificate_path`,
  `tls_private_key_path`); a non-loopback listener without TLS is still refused.
- Members' Agents pin the certificate's SHA-256 (Settings > Shared platform > "Platform
  certificate"); every call of the Bridge client and of the member publisher (browser
  ticket, Library content, enrollment, publishing) checks it before sending anything.
- Browsers show a warning for the self-signed portal; the guide (chapter 10) explains
  comparing the fingerprint or importing the public `.cer` that Agent Web downloads, and
  the risk of the latter.
- `aep-platform certificate-fingerprint --config platform.json` prints the value an
  administrator hands out; `serve` prints it at start.
- The TLS handshake runs on each request's thread with a 10-second limit, so a silent
  client cannot stop the platform.
- Administrator procedure (issuing the certificate on the platform machine, firewall rules,
  autostart): `deploy/shared-platform-preview/START-HERE.md` and the guide's chapter 15.
