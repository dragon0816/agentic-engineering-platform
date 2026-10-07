# Asset ownership and versions (planned)

Owner request: 2026-10-07. Status: **step 1 done; step 2 planned for after the business workflow lab stage.**

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

Plan step 2 together with conversational authoring A1–A3 (`docs/phases/CONVERSATIONAL_AUTHORING.md`), since both decide how a person's edits become versions.
