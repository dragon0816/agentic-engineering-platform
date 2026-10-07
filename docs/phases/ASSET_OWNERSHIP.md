# Asset ownership and versions

Owner request: 2026-10-07. Status: **step 1 done; step 2 items 1–4 and 6 done in the control plane (2026-10-07, not yet merged or live); item 5 (member publish route and UI) open.**

## Goal

Every Skill and Workflow name has an accountable owner. Only the owner and the co-editors the owner names may publish new versions of it. Published versions are immutable. Each person chooses the version they use and has exactly one active version of each name.

## Owner decisions (2026-10-07)

1. **Owner.** The first person to publish a name becomes its owner. The owner may be a person or a team, and ownership may be transferred so an asset is not orphaned when people move.
2. **Co-editors.** The owner names co-editors. A co-editor publishes new versions directly, without per-version owner approval. The platform's existing validation and review layers still apply. The owner may deprecate any version and remove co-editors at any time.
3. **Version numbers.** The platform assigns them by increasing the highest existing version, so two versions never collide. The publisher chooses whether a change is a patch (1.0.x), minor (1.x.0) or major (x.0.0) change.
4. **Use.** A user picks a version. Each person has one active version per `namespace/name`. References stay exact (`namespace/name@version`); nothing resolves to "latest".

## What already exists

These come from a code survey on 2026-10-07:

- Immutable versions: `(namespace, name, version)` is the registry key, and publishing a duplicate is refused.
- Exact references, with no implicit latest.
- An `owner` (user, team, organization or service), `visibility` and `contributors` on `AssetMetadata`. `contributors` currently grants use only.
- Per-member version selection, and `replace()` within one name family.
- The layered review contracts (business approval, technical policy).

## Step 1: chat-authored Workflows (done 2026-10-07)

`host_runtime/chat_authoring.py`:
- A draft of a name already installed on the Host continues from its highest version instead of restarting at 1.0.0.
- A name installed by another owner is refused with that owner's id, so the person can choose another name or ask for co-edit rights.

This step is Host-local. It reads the installed Workflow files and does not touch the shared Registry.

## Step 2: platform-wide (planned)

1. **Name ownership record** in the Registry: `(namespace, name) → owner, co_editors`, created by the first publish, plus a transfer operation.
2. **Publish check:** the Registry refuses a new version of a name unless the publisher is its owner or a co-editor, or a member of an owning team.
3. **Automatic versions:** publish takes a change level (patch/minor/major) and assigns the next version. A manually supplied version must be higher than every existing one.
4. **One active version per person:** `select()` replaces an active version of the same name instead of adding a second one, matching `replace()`. The Host inventory keeps older versions inert for rollback, as it does today.
5. **Member publish surface:** Agent Web lets the owner publish, manage co-editors, deprecate versions and transfer ownership. The review queue reuses `Review` and `TechnicalPolicy`.
6. **Contract and architecture updates** in `docs/ARCHITECTURE.md` and `docs/CONTRACTS.md`, with tests for each rule.

### Step 2 status (2026-10-07)

Done, with tests in `tests/test_asset_ownership.py` (contract and code in `docs/CONTRACTS.md`, "Asset name ownership and versions"):

- **1. Ownership record:** `common.ownership.AssetNameOwnership` in both Registries. SQLite keeps it in an additive `name_owners` table. `schema_version` stays `1`, so the previous code can still open the database. A name published before this change gets its owner from its earliest version.
- **2. Publish check:** `PackageRegistry.publish_as` refuses `publisher_not_authorized` and `owner_mismatch` inside the writing transaction. The platform's own `publish` (preview seed) keeps names with their owner and does not order versions.
- **3. Automatic versions:** `next_version` and `AssetOwnershipService.publish_next(change, build)`. An artifact carries its own version, so the platform assigns the version before the package is built and never renumbers one afterwards. A supplied version must be above every existing one (`version_not_above_highest`).
- **Owner operations:** add and remove co-editors, transfer, deprecate. A deprecation is recorded beside the name and does not change the package, because published packages are immutable and `PublishedAssetPackage` accepts only `lifecycle="published"`. A deprecated version is no longer offered or chosen anew. Existing selections and installs keep it for rollback.
- **4. One active version:** `select()` revokes the member's other active version of the name on that device.
- **5 (partly):** member portal routes for the owner operations, under `/v1/member/assets/`.
- **6.** `docs/ARCHITECTURE.md` and `docs/CONTRACTS.md` are updated.

Open:
- a member publish route. It needs artifact upload and a review queue reusing `Review` and `TechnicalPolicy`; today a member could otherwise assert their own reviews.
- the Agent Web publish and ownership UI.
- telling Hosts which versions are deprecated.
- reconciling Host-local chat authoring (step 1) with the Registry record.

Plan step 2 together with conversational authoring A1–A3 (`docs/phases/CONVERSATIONAL_AUTHORING.md`), since both decide how a person's edits become versions.
