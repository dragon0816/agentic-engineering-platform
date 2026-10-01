# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/personal-agent-feedback`
Base: `main` at `0614562be0b79faff5f9e898dd395c1c1daf608a`
PR: pending

## Goal

Complete Productization 4 slice 5 and therefore Productization 4: let a member
turn a durable Personal Agent conversation into a reviewable local improvement
or new-capability draft without granting approval, publication or execution.

## Completed

- Added closed `ContributionDraftCreateRequest`, `ConversationExcerpt` and
  `ContributionDraft` contracts.
- An improvement names one exact installed Skill, Workflow or Knowledge
  version. The Host derives its kind, namespace and manifest owner.
- A new-capability proposal is limited to a Skill or Workflow. The Host derives
  the configured namespace and current actor; browser input cannot claim
  identity, ownership, lifecycle, approval or publication fields.
- Each draft copies up to twenty recent conversation messages with message ids,
  roles, text and assistant trace identifiers. It records expected/actual
  behavior and one to ten acceptance criteria.
- Upgraded Bridge-local state schema from 3 to 4 with an additive immutable
  contribution-draft table. Version 1–3 files migrate on writable open.
- Added an **Improve** page to Personal Agent Web for exact installed-target
  improvements, new Skill/Workflow proposals and actor-filtered draft listing.
- Every captured item remains local, `draft`, `publishable=false`, with separate
  pending business approval and technical policy. Capture executes no
  capability, installs nothing and writes to no external system.
- Marked all five Productization 4 slices complete and updated Architecture,
  Contracts, Roadmap, Tasks and Windows operator documentation.

## In Progress

- Commit, open the slice 5 PR, wait for exact-head CI and merge it after green.

## Remaining

1. Let the merged-main CI produce the Windows preview and deployment request;
   Hermes/company-Bridge validation is the next production-like evidence path.
2. Productization 2 (Agent Add-ons) and Productization 3 (Bridge Extensions and
   Applications) are already complete; do not reimplement them.
3. The active unfinished roadmap work is Phase 7 physical/source parity and the
   E2E-01 production-like DUT run. Those require the enrolled company Bridge or
   test rig; CI on this development machine must remain inert.
4. A later governed path may route a local contribution draft into validation,
   review and publication. This slice deliberately does not create GitHub
   Issues or shared Registry assets automatically.

## Architecture decisions made

- Feedback capture is a local evidence boundary, separate from Agent execution
  and shared-platform publication.
- Exact installed manifests, rather than browser claims, supply the target kind
  and owner for improvements.
- A proposal envelope is not a Skill or Workflow manifest. It must go through
  later validation, business review and technical policy before publication.
- Conversation excerpts are copied into the draft so later review does not
  depend on the mutable tail of an ongoing conversation.
- Business approval and technical policy remain distinct pending reviews.

## Verification

Supported target: Windows, Python 3.12 only. Browser automation was not run.

```text
python -m pytest --ignore=tests/test_browser.py -q
1465 passed, 4 skipped in 66.29s

python -m pytest tests/test_agent_web.py tests/test_host_wiring.py -q
68 passed in 27.35s

python -m ruff check .
All checks passed!

python -m ruff format --check .
325 files already formatted

python -m mypy
Success: no issues found in 256 source files

python -m build --no-isolation --outdir <scratch>/build-feedback
Successfully built sdist and wheel

python -m pip check
No broken requirements found.

git diff --check
PASS
```

## Known issues

- Drafts remain only on the Bridge that captured them. Cross-device submission
  is intentionally deferred until a governed validation/review boundary exists.
- The UI copies the most recent twenty messages; it does not yet let a user
  select individual excerpts.
- Ollama tool calling and streaming provider deltas remain deferred from slice 4.
- The company Gateway URL is fixed at `http://127.0.0.1:4000/v1`, but its served
  model id must still be configured explicitly.

## Next Recommended Action

Merge the exact-head-green slice 5 PR. Then use the normal merged-main Windows
artifact and trusted deployment lifecycle for real company-Bridge validation;
do not start another speculative Personal Agent Web architecture rewrite.
