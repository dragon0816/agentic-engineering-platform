# C4C Skill 1.0.4 evaluation and transfer

Date: 2026-11-11. Owner requested transfer to Claude Code; stop further testing.

## Installed and verified

Owner approved card `ap-20261111-050002-b78d8a` with「同意核淮」.
Normal API verified candidate `sk-20261110-155444-ab60a7`, revision 5, digest
`e3a8bce449022d0e07d9e27391b16b5e01d9eeb821e333e95d2f49ace02d91e2` before
approving. Idle-guarded installed-runtime restart preserved configuration and
source. Fresh installed bootstrap loaded navigation 1.0.4, 6,501 instruction
characters, SHA256 `0089a105cd6678e0d8ef6e13061e2556666b21ccc9bc91b56d9ad788d93c1b7e`.
SOP development Skill 1.0.0 remains installed; harness_guidance is None.
No harness, permission, source or package change was made in this slice.

## Actual novice test

Conversation `conversation-77223c69b5b24dc3aa6868789f440014`, internal Gateway.
Original request and original PDF were supplied once; Downloads workbook path
was supplied in the request. Request hash equals the previous exact novice
request: `a5fd494c97f7dae858b198131c3c166fca792c266977d4f22cd84b8bfb653a1f`.
No technical selector, old graph or business script was injected into the chat.

AEP asked one new business question: treatment of currencies absent from SOP
rates. Owner explicitly answered: preserve original currency amount, leave EUR
blank and list items needing confirmation. That actual answer was sent into the
same session. The question cleared; no invented extra rate was supplied.

Skill-level tool selection improved: 21 `browser__inspect` observations, 16
succeeded and 5 failed. Failures included missing/ambiguous scopes. No repeat of
round6's blind body-offset loop was observed. AEP also chose existing Host
`browser__operate` itself for several operations in one turn; the coding agent
did not dispatch these directly or change permissions.

Eleven normal `browser/operate` approval decisions executed: 9 succeeded,
2 failed (`web_wait_timeout` during navigation and `web_target_missing` when
selecting All). AEP inspected and revised its exploratory targets. Normal
navigation, view selection, advanced-search, date-fill/query and another
dropdown operation were exercised. This is not independent proof of the full
requested filters or date range. No full browser-phase replay was reached.

All eleven ordinary decisions returned without model continuation. Ten plain
「請繼續」messages were manually sent. The last approved operation is
`ap-20261111-055255-66ae4a`, saved as `result-22.json`; it succeeded, and no
continuation was sent afterwards. Client34048 closed normally. Final progress
was inactive, with no pending session approvals or business question.

No Workflow candidate was created, no full trial was consumed, and no Excel was
produced or independently validated. Autonomous-authoring acceptance failed;
functional development remains incomplete. Do not report this as an Excel test
failure or as proof that navigation replay is solved.

## Confirmed boundary and unresolved causes

`web.py::_decide_approval` schedules continuation for full trials and governed
repair preflights, not ordinary capability decisions. A selected Skill can
improve tool choice while a model turn is running, but cannot schedule another
turn after this controller returns. The live eleven-decision evidence confirms
that gap. Any fix is a harness change requiring new scoped owner consent.

`chat_authoring.py::approval_text` also clips generic capability data at 2,000
characters. This information-loss behavior is confirmed; its causal contribution
to this run's locator errors is not proven. Do not bundle an unapproved context
rewrite with a continuation repair.

Domain state/locator reliability still needs examination. Missing/ambiguous
scopes, exploratory generated IDs and successful fragments do not establish a
stable compiled Workflow. Do not assume continuation is the sole remaining issue.

## Evidence and next step

Local-only evidence: `.scratch/c4c-skill104-novice-20261111/` contains
`result-0.json` through `result-22.json`, `initial-request-proof.json`,
`evaluation.json`, `tool-observation-summary.json` and `session.json`.
Raw responses may contain enterprise data; expose statuses/counts only to coding
models. Dedicated approval/load/restart proofs are
`.scratch/c4c-skill104-{owner-approval,loaded,resident-update-proof}.json`.
Restart proof's legacy `installer: passed` key represents restart only; no
package reinstall occurred.

Claude Code should first read HANDOFF, AGENTS22 and these evidence summaries,
then independently narrow the next change. Do not start another unbounded
end-to-end novice loop. Skill/domain fixes remain allowed; before any new
harness edit present causal evidence, minimal scope and regression checks and
obtain explicit owner consent. Owner's transfer request is not harness consent.

Verification: Skill format check passed; installation/load/config/source guards
passed; initial-request proof passed. Runtime unchanged. Existing read-only
boundary/Knowledge checks previously passed 4 tests in 9.78s; this slice did not
rerun the full suite or produce a new build. Historical runtime full-suite
results and their two original failures remain in HANDOFF.
