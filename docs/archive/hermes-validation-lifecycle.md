# Hermes validation lifecycle

This control-plane loop turns one bounded validation request into deterministic
Hermes preflight/test work, a governed repair loop when necessary, and one
explicit terminal result. It does not execute a Bridge capability, grant access,
install assets, or merge code.

```text
Validation Request
  -> preflight_and_test
  -> passed -> validated
  -> failed -> Codex repair loop
               -> evidence collection -> retry
               -> Draft PR -> CI -> retest
               -> owner decision -> resume or reject
```

## Contract

`validation.contracts.ValidationRequest` is the source schema for the request
manifest in the `Hermes validation request` Issue template. It pins the scoped
capability identity, package commit, build, deterministic Hermes test profile,
Bridge, actor, declared grants, optional model routing and Knowledge versions,
acceptance criteria, and bounded repair/retest counts.

The request declares what Hermes must verify; it does not grant any listed
permission. Hermes preflight reads the local configuration and returns a
structured failure when the actor, asset, routing or Knowledge prerequisite is
absent.

`OwnerDecision` records one of three decisions: `authorize_test_actor`,
`configure_model_routing`, or `enable_knowledge_integration`. Approval means
that an owner has made a decision. It does not itself change any grant or host
configuration. Hermes always re-runs preflight after an approval.

## GitHub state machine

| Event label | Required labeler | Result |
|---|---|---|
| `hermes-validation-requested` | `HERMES_GITHUB_BOT_USER` | GitHub creates a `preflight_and_test` payload and adds `hermes-preflight-requested`. |
| `hermes-owner-decision-approved` | `HERMES_MERGE_REVIEWER` | GitHub creates a `resume_validation` payload and adds `hermes-preflight-requested`. |
| `hermes-owner-decision-rejected` | `HERMES_MERGE_REVIEWER` | GitHub creates a `terminal_rejected` payload and adds `hermes-validation-failed`. |
| `hermes-validation-passed` | `HERMES_GITHUB_BOT_USER` | GitHub records a terminal `validated` payload and notifies the reviewer. |
| `hermes-validation-failed` | `HERMES_GITHUB_BOT_USER` | GitHub records a terminal failure payload and notifies the reviewer. |

Every queue/result comment contains a JSON marker with schema
`hermes-validation/v1`. Hermes accepts only comments from
`github-actions[bot]`, validates the repository and source Issue, and records
each payload `id` before it performs any work. Labels alone never authorize an
operation.

The existing Codex workflow maps `manual_review` to
`owner_decision_required`, adds `hermes-owner-decision-requested`, and writes
the existing `hermes-next-action/v1` payload. Hermes should notify the owner
from that payload and wait for an approved or rejected owner-decision label;
it must not change authorization, model routing, or Knowledge wiring itself.

## Required labels

Create these labels once in GitHub:

```text
hermes-validation-requested
hermes-preflight-requested
hermes-owner-decision-requested
hermes-owner-decision-approved
hermes-owner-decision-rejected
hermes-validation-passed
hermes-validation-failed
```

`codex-fix`, `hermes-evidence-requested`, `hermes-retest-requested`, and
`hermes-retest-passed` remain part of the repair loop.

## Terminal conditions

A request ends only when Hermes applies `hermes-validation-passed`, applies
`hermes-validation-failed` after the declared attempt limit, or the owner adds
`hermes-owner-decision-rejected`. A passing repair PR still requires the human
merge decision; validation success never merges it.
