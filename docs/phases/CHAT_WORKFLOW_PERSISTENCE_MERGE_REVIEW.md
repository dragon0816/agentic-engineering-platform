# Chat Workflow persistence: separate merge assessment

Date: 2026-11-12. Status: assessed only; NOT merged or newly authorized.
Source commit: origin/main e564e1ad. Current integrated slice excludes it.

## Problem and causal boundary

The remote change keeps an installed Workflow's inline chat form execution and
parameters across conversation switches, refreshes and process restarts. It
prevents a second press on the same completed/running form from starting another
execution, and permits an explicit retry of the exact failed/interrupted attempt.

The affected path is deterministic: web_page.py renders an existing workflow_form
and calls /api/workflows/run; web.py launches the installed manifest. It does not
select or consult a Skill to render/persist a form or claim an idempotency key.
A Skill procedure cannot make those DOM/server state guarantees. This is causal
justification for a harness proposal, not authorization to implement it.

## Smallest proposed scope, if separately approved

- Add optional form_message_id and retry_of to WorkflowLaunchRequest.
- Persist only run state/arguments on the actor-owned assistant form message.
- Claim each form attempt before execution; replay running/success outcomes;
  explicit retries reference the failed attempt and use a new execution key.
- Project prior-process running state as interrupted without automatically
  restarting the Workflow or rewriting transcript text.
- Keep form edits and focus across chat redraws; show durable status and
  retained parameters, and revalidate upload references on retry.
- Include active form launch/waiting time in the existing restart activity guard.
- Preserve installed-only dispatch, Bridge permissions, approvals and Knowledge
  routing/context/completion rules. No C4C procedure or Knowledge answer logic.

Expected source boundary: contracts.py, state.py, web.py, web_page.py and new
workflow_form_runs.py. Existing tests in the remote commit are a starting point,
not evidence that its integration with the current C4C branch passes.

## Knowledge and compatibility gate

No direct Knowledge route or model prompt change was found in the remote patch.
Shared conversation projection/rendering and execution state still create a
regression risk, especially Knowledge questions in sessions containing prior
Workflow forms. Therefore require the current complete Knowledge regression set,
authoring isolation and plain/unfinished/verified workflow-session inquiries,
plus exact model request/evidence/citation assertions. Do not claim universal
real-model answer quality from deterministic test results alone.

Also require form navigation/refresh/focus tests, duplicate-click and retry
idempotency, cross-actor/session refusal, restart interruption, argument/upload
continuity, existing authoring/card/approval/continuation tests, full suite,
Ruff/format/mypy/build and normal guarded deployment checks if later deploying.

## Integration and release impact

The dry merge has no source text conflict, but adds stateful execution behavior;
textual success is not behavioral verification. HANDOFF, DECISIONS and TASKS have
content conflicts and must preserve cumulative decisions while presenting one
current handoff. The currently accepted C4C run is not an acceptance run for this
future merged code. Require explicit owner scoped consent before editing or
merging this harness feature, then verify before push/deployment.
