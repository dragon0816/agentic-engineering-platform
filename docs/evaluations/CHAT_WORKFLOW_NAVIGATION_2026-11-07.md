# Chat Workflow execution survives navigation (2026-11-07)

## Requirement and boundary

Once a person starts an inline Workflow form, leaving the page or reloading the
document must not cancel execution or produce a fresh actionable Run offer.
Returning shows running, succeeded, failed or interrupted. A failed/interrupted
attempt offers an explicit retry with a warning to inspect already completed
writes. It is never retried automatically.

The Web adapter owns only presentation/admission state. LocalAgent, Gateway,
Workflow engine, Harness and Bridge retain execution, policy, approval and
idempotency. There is no new executor, provider integration or capability grant.
A restart remains a separate guarded operation.

## Contracts

`WorkflowLaunchRequest` adds optional `form_message_id` and `retry_of`. New chat
clients bind the exact assistant message. The server verifies the actor owns the
conversation, it is not Telegram, and the form names the exact requested Workflow.
Old clients without a message id bind the newest matching form; existing non-form
launches retain their original path.

The form's existing JSON metadata has a `run` entry: status, attempt key, start
instant and an internal AgentWeb instance identifier, followed by the answer when
finished. A short per-session record lock atomically claims it before waiting for
the execution lock. A second request replays its saved state even if the browser
sent a different key. Retrying requires the exact failed/interrupted attempt key
and a different new key; delayed duplicate retry requests replay too. A succeeded
form cannot be retried. A new intentional run starts from a new form offer.

`SqliteLocalState.set_workflow_form_run` is a narrow actor-scoped transaction over
one assistant form's execution metadata. It does not weaken save_conversation's
append-only transcript invariant or change any message text. The run/result pair
still appends through the existing recorder. A different AgentWeb instance
projects an unfinished marker as interrupted and never starts it. Internal owner
identifiers do not go to the browser.

Old inline-run transcript pairs are recognized only by the exact generated user
prefix and adjacent assistant result, with one exact identity for that Workflow
name in the session. They project terminal consumed state without rewriting old
records. Ambiguous identities remain untouched.

## UI and restart behavior

The form heading shows its persisted state. Running/completed forms have no Run
button. An open running form refreshes the selected conversation every 1.5 s;
detached or different-session views stop refreshing. Failed/interrupted forms
show their result and an explicit retry. Whole-document reload disconnects the
request socket, while the resident request handler continues and saves the
outcome before attempting to write its HTTP response.

`/api/activity` also counts a launch waiting for the execution lock, covering the
period before Workflow telemetry creates its task record. `/api/tasks` continues
to use normal Workflow telemetry for execution outcome; no second executor or
parallel task lifecycle is introduced.

## Verification record

- Baseline durable-start regression: failed because the reloaded form had no run status.
- Baseline page b9d96ac7 loaded into the temporary test host: browser return-to-session running predicate failed; private log `.scratch/nav-browser-red.log`.
- Real slow read-only stub capability through Workflow/Bridge, success and failure: 2 passed, 45.72 s. Both switch to Tasks and back, reload the whole document while blocked, verify one handler invocation, then release and observe final state. No owner host used.
- Initial combined navigation/forms group: 11 passed, 100.37 s.
- Navigation/activity/state/mail affected group: 39 passed, 17.88 s.
- Navigation plus legacy compatibility group: 6 passed, 13.23 s.
- Final Ruff format/check passed (1099 files); mypy src tests passed (1053 files). Final source build and pip check passed.

## Owner's SDE incident

2026-11-07 19:34:40 +08 Workflow start; `weekly-report/apply` succeeded;
`weekly-report/mail` then failed after 392164.4 ms; run finished at 19:43:03.
Local run `run-ba011f34976f4392a29080dda5cc1850`, telemetry run
`run-61b986ea3fd24c99`. Thus navigation did not stop this run. Report write was
reported successful; mail draft was not reported successful. A failed COM Save
or receipt read cannot prove no draft exists, so retry must not be automatic.

Old code discarded all draft exceptions into `draft_failed`; saved telemetry and
stderr do not identify the COM operation/HRESULT. No evidence can now distinguish
an Outlook environmental error from an adapter defect for that historical call.
Commit ae1becf3 fixes this diagnostic gap with fixed-stage/numeric-only logging,
not a speculative COM behavior change. No real Workflow/draft/restart was run.

## Full-suite finding during release preparation (2026-11-08)

First complete source run: **1 failed, 6017 passed, 13 skipped in 7272.78 s**.
All26 Workflow tests passed, as did the two tests that failed remote b9d96ac7 CI
(version-link geometry and Member Portal tabs). Failure: early-send queued notice
was replaced by the delayed backend-check notice. The old1500ms callback was
unconditional, so this pre-existing UI race was reproduced on the unchanged
b9d96ac7 page using explicit backend-start/release coordination and Enter followed
by the late notice (baseline10.90s, failed exact promise assertion).

`sendWait(true)` now leaves a queued notice intact. Cleanup/readiness/exactly-once
behavior unchanged. Test uses an Event gate instead of4-second timing assumption;
all original assertions retained. Early-send + turn-group files:9 passed20.01s.
Read-only review approved. Corrected source completed the second full suite:
**6018 passed, 13 skipped in 7707.83 s (2:08:27), exit 0**.
Command: `python -u -m pytest -vv -x --tb=short --junitxml=.scratch/codex-lead-full-verified.xml --basetemp C:/Temp/codex-lead-full-verified`, with `PYTHONPATH=src`, GUI/live Outlook disabled. Browser cases ran serially on temporary hosts.
Final diff/architecture review preserved the original execution/approval path; no
provider, Registry, Bridge authorization or dependency change. AST-only graphify
update completed (45185 nodes, 139675 edges); three existing benchmark-generated
script syntax warnings do not affect production sources.
