# C4C Skill 1.0.3 novice evaluation

Date: 2026-11-11. Result: failed novice acceptance; no Workflow or Excel produced.

The owner approved `ap-20261111-034133-58c53f` with
「同意套用 Skill 並重測」. Normal installation and a guarded installed-runtime
restart loaded navigation Skill 1.0.3 and SOP development Skill 1.0.0. Runtime
source remains `513784d01b8f463733ef40cb08e95a1a7ea26a75`; no harness edits.

## Actual test

New conversation `conversation-48e4ae52be9048b891d0d86892224807` received the
original simple request, original PDF and Downloads workbook path, through the
internal Gateway. No selectors, graph or business code were supplied by the
coding agent. Normal browser capability requests were approved under the owner's
standing read/export/local-output test authorization.

Eight capability decisions executed: two failed (`profile_in_use`, then
`web_origin_not_allowed`), six succeeded. Initial SAP authentication error later
cleared after AEP's ordinary reopen. A subsequent inspection contained Sales
Orders content; this does not prove the prescribed filters, list readiness,
source total or a repeatable navigation sequence. There was no coding-agent
browser close, profile reset, credential access or manual page preparation.

Each decision returned without automatic model continuation. Eight plain
continuation messages were required. Discovery then inspected body DOM offsets
0, 200, 400 and 600, and requested offset 0 again. The final repeated inspection
`ap-20261111-045721-17ffe7` was rejected through the normal API to stop this
unproductive cycle. Driver 76741 closed normally. Final progress was inactive,
with no pending session approvals or question. No candidate was created, no full
trial was consumed, and no workbook was validated or installed.

## Causal findings and limits

`web.py::_decide_approval` resumes full trials and governed repair preflights,
but does not schedule a model turn for ordinary capability decisions. Skill
instructions cannot schedule a turn after that handler returns. This establishes
the continuation gap, not permission to change the harness.

`chat_authoring.py::approval_text` limits generic capability data to the first
2,000 characters. Actual successful browser responses exceeded this limit.
Information clipping is established; its contribution to the inspection cycle
is a hypothesis, not an independently proven sole cause.

An existing authorized read-only `browser__inspect` Host tool exposes scoped
inspection with overview text, controls and table hints. The selected domain
Skill still chose its broad `operate` command for observations. A Skill-level
tool-selection improvement is therefore still available. Do not claim that
Skill changes have been exhausted or propose a harness fix as inevitable.

Independent fresh/retained-state replay, stable target compilation, source total,
dates, IDs, owner mapping, currency conversion and monthly totals were not
reached. The separate live factual Knowledge smoke answered without tools and
preserved the exhausted previous task bytes and trial counter.

Metadata-only evaluation, raw responses and initial-request proof are retained
locally in `.scratch/c4c-skill103-novice-20261111`; never publish enterprise rows
or authentication URLs. `evaluation.json` records statuses, response lengths,
operation types and the eight manual continuations.

## Small next Skill revision

Normal authoring check passed for navigation 1.0.4, same candidate
`sk-20261110-155444-ab60a7`, revision 5, digest
`e3a8bce449022d0e07d9e27391b16b5e01d9eeb821e333e95d2f49ace02d91e2`.
Install card `ap-20261111-050002-b78d8a` awaits owner approval. It is not installed
and its behavioral effect remains untested.

The only instruction addition prioritizes existing `browser__inspect` for fresh
observations, uses overview/controls before raw DOM, starts with a small scoped
limit, and stops blind scanning after two observations without new actionable
facts. Missing read-tool access is reported, never bypassed. Normal navigation
approvals, command contracts, alias, replay/Excel obligations and trial limits
remain unchanged. No `harness_guidance`, permission or runtime changes.

Before another live test: obtain exact installation consent under
`aep-skill-creator/SKILL.md` step 5; install normally; guarded restart only when
idle; verify loaded instructions. Measure actual tool choice and progress before
claiming success. A workaround may reduce observation stops but cannot fix the
generic continuation controller itself. Any later harness proposal needs a
separate Skill-first assessment and explicit scoped owner consent.

Focused existing regressions passed: 4 tests in 9.78 seconds. Command:
`.venv/Scripts/python.exe -m pytest -q`
with `tests/test_browser_session.py::test_read_only_inspection_alias_has_closed_schema_and_still_requires_bridge_grant`,
`tests/test_browser_session.py::test_read_only_inspection_alias_rejects_extra_keys_before_bridge_dispatch`
and `tests/test_authoring_knowledge_isolation.py::test_read_only_inspection_does_not_require_completion_or_create_task`.
These establish existing observation-tool boundaries, not the new Skill's live
effect. This slice modifies documentation only; the earlier runtime verification
and its two original full-suite failures remain recorded in HANDOFF.
