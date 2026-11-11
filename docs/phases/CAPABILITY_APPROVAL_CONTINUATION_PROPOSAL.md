# Capability approval continuation — harness proposal (NOT approved)

Date: 2026-11-11. Author: Claude Code, after taking over C4C from Codex.
Status: owner approved on 2026-11-11 (「同意提案的範圍，但要確保knowledge
asking不會有問題」) and implemented in `web.py::_continue_after_capability`.
See "As implemented" at the end. The secondary finding remains unapproved.

## Problem

In C4C novice rounds 6 and 7, AEP explored C4C through ordinary
`browser/operate@1.0.0` capability approvals. Every approval ended the model
turn and nothing resumed it: round 6 had 8/8 decisions without continuation,
round 7 had 11/11. A coding agent sent 18 manual「請繼續」messages in total.
A novice owner would see AEP stop after every button press, so autonomous
authoring cannot pass acceptance however good the Skill is.

## Root cause (code evidence)

`src/host_runtime/web.py::_decide_approval` appends the decision and result to
the conversation, then calls `_resume_failed_authoring` only when the decided
item is a full trial (`kind == "run"`) or a governed browser preflight. An
ordinary `kind == "capability"` decision returns without scheduling a model
turn. `_resume_failed_authoring` additionally requires an existing candidate,
so the exploration phase, before any candidate exists, has no continuation
path at all.

## Why a Skill cannot fix it

Skill instructions act only while a model turn is running. The decision
handler runs after the turn has ended, from the owner's button, and no model
tool can schedule a later turn. Round 7 shows the Skill already improved what
it can (tool choice: 21 scoped `browser__inspect`, no blind body scanning),
yet continuation stayed at 0/11. A Skill can reduce the number of stops by
batching actions per approval, but cannot remove them.

## Separate, secondary finding (not part of this proposal)

`chat_authoring.py::approval_text`:

- Failed capability: the model receives only `【未執行】… 原因：<code>`. Both
  round 7 failures carried `failed_action_index`, action kind, `diagnostics`
  and `overview` in the stored result, none of which is shown. In the
  `web_target_missing` failure the failed action was index 1, so action 0 did
  execute and change the page although the text says "not executed".
- Succeeded capability: data is clipped to 2,000 characters. All 11 round 7
  results (including the failed ones' stored data) were 2,650–72,390 characters; `items` started at offset 408–57,257,
  so the controls were never visible from the result itself.

Round 7's in-turn `browser__inspect` calls partly compensate, so the causal
contribution is unproven. It is listed for a possible later, separate request
and is NOT included here.

## Smallest proposed change

In `_decide_approval`, after an approved ordinary capability decision
(`kind == "capability"`, not the preflight source, status succeeded or failed)
for a Gateway conversation, run one model continuation for the same session:

- same turn lock and `_one_at_a_time` as the existing repair continuation;
- at most once per approval ID, recorded durably, so retries or duplicate
  button presses cannot start a second turn;
- no continuation for rejections, non-Gateway conversations, or when another
  turn is active for the session;
- a short Host note saying the approved result is in the conversation and the
  agent should continue the person's task, stopping when it needs another
  approval or business input; tools are the normal conversation tools; no new
  permission, tool, budget or Knowledge change;
- existing full-trial and preflight paths unchanged; full-trial limit 3
  unchanged.

Each further browser action still needs its own owner approval, so the loop
stays bounded by the owner's button.

## Regression checks

- New tests: approved capability → exactly one continuation; duplicate
  decision → none; rejection → none; active turn → none; non-Gateway → none;
  preflight and run decisions still follow their existing paths.
- Existing focused approval/preflight/authoring tests, Ruff, format, mypy,
  full suite compared against the recorded 6610/2/10 baseline, build and
  resident update under the idle guard.
- One bounded live check: resume the preserved round 7 conversation and
  confirm a single approval leads to an automatic next turn. Not a new
  unbounded novice loop.

## As implemented (2026-11-11)

- Trigger: approved `kind == "capability"`, not preflight, result status
  succeeded/failed, Gateway conversation.
- Knowledge condition (owner's requirement): continue only when the session's
  authoring task has planned requirements, no verified digest and no open
  question. Knowledge and ordinary conversations have no planned requirements
  and keep exact current behavior; Knowledge routing of the person's messages
  is untouched because the continuation calls the model directly.
- Locking: per-session turn lock, non-blocking (active turn → no
  continuation). Unlike the repair path it does not hold `_one_at_a_time`,
  mirroring the ordinary user turn whose normal tools it offers.
- Activity: an `authoring_continuation` Agent Web task while it runs, so the
  idle guard defers restarts.
- At most once per approval: `decide` refuses an already decided approval.
- The existing completion check still applies: a text-only end on an
  unfinished task is re-asked once and then held as needs_input.
- Tests: `tests/test_capability_approval_continuation.py` (7 cases).
