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
