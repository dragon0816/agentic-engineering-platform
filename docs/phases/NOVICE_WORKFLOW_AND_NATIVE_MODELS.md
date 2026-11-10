# Novice SOP authoring and native backend model selection

Owner requests (2026-11-10): replace the assisted C4C demonstration with a new,
ordinary-user conversation; also show supported models when selecting Claude
Code or Codex. The owner's supplied interaction is the approved product design.
Routine implementation choices do not require another design approval. The owner's
later explicit harness-change rule overrides this for every new harness change:
prove that Skill improvement cannot solve it and obtain specific consent first.

## Acceptance contracts

1. Remove the prior C4C report from the resident installed/draft catalog through
   existing recoverable asset APIs, cancelling its pending installation. Preserve
   run history, original files and prior evidence outside the new conversation.
2. Start a fresh resident conversation with exactly the simple request and the
   original SOP plus the specified Downloads workbook. No previous workflow,
   scripts, selectors, JSON references, technical hints or private candidate IDs
   enter this conversation. Retained audit history is not an authoring source.
3. AEP reads the supplied files, identifies their actual role, and asks only
   necessary missing business questions. It retains provided answers; optional
   values use defaults. It must not request selectors, schema paths or Python.
4. After collecting required information, AEP plans, builds, tests, repairs and
   validates the workbook itself through existing governed tools. AEP must
   compare the final workbook to the agreed fields/layout and source count,
   date range, amounts/currencies, mapping and aggregates as applicable.
   Root's independent read-only check is an oracle, not feedback or a substitute
   for the Agent's own validation. Report every intervention or unmet condition.
5. Query/export and local Excel remain authorized; no C4C order changes or mail.
   Technical policy and final owner installation approval remain separate.

## Model selection contract

The current composer intentionally hides model selection for non-Gateway
backends. Extend selection using fixed, bounded, read-only local CLI discovery.
Use official metadata/protocols, not invented model names or extracted tokens.
Choices must be scoped by backend and conversation (including stored defaults),
validated against that backend's reported catalog, and forwarded to the actual
CLI with fixed argument construction for both text and supported agent modes.
Gateway behavior and existing saved choices remain compatible.

Discovery has a deadline/output cap, no user prompt or inference turn, no login
launch, no tools/commands from the browser and no credential/account output.
Unavailable discovery produces an explicit state and provider-default fallback;
it must not show Gateway models under a native backend. Native model visibility
does not loosen data classification, capabilities or permission relay. Selection
is locked during a running turn. Ignore stale async replies after backend/session
switches. Model catalogs are not promises of account entitlement.

## Implementation sequence and ownership

1. Root: archive/remove the old asset through normal APIs; run the clean novice
   conversation, record questions, answers, tool traces and self-validation.
2. Native-model implementer: investigate actual CLI discovery; add typed bounded
   discovery and backend-scoped selection/argument forwarding, tests first.
   Own a new helper module plus conversation_backends.py, conversation_models.py,
   web.py model-selection methods and web_page.py model-control region only.
3. Root: evaluate reproducible authoring gaps through Skill selection/content
   first. Every harness change requires causal evidence that Skills cannot solve
   it and separate explicit owner consent before implementation. The owner
   approved only the Knowledge intake/state/completion isolation correction.
   No business-specific runtime code or technical coaching in the clean replay.
4. Independent review, focused checks, then one final normal full suite after
   both slices and actual acceptance are stable. No build concurrent with pytest.
   Ruff/format/mypy/build/pipcheck, local commits, offline canary and fresh-idle
   resident update. Never interrupt an active turn/question/approval flow.

Architecture review: Personal Agent owns reasoning/clarification; deterministic
execution stays in Bridge workflows. Backend discovery is a local adapter concern,
not a new shared asset/provider contract. No n8n, new dependency, permission
bypass, external-company-data inference or unrelated refactor.

## Initial evidence and rulings

- Downloads/Sales name and Dept.xlsx exists. Let AEP inspect its actual role;
  the filename alone does not establish an export template.
- available_models currently lists only configured Gateway; renderModelControl
  explicitly hides the picker for every non-Gateway backend. Native adapters
  currently accept no model choice: UI-only changes would be incomplete.
- Use project .venv/Scripts/python.exe for every verification (system Python's
  NumPy/Matplotlib ABI mismatch remains unrelated and must not be reintroduced).
- User explicitly authorizes removal/retest; use recoverable removal and preserve
  history. The old pending install request is withdrawn, not approved.

## Verification plan

## SOP procedure guidance requested during this work

The owner's follow-up asks whether Skills can help. Inspect actual AEP Skill
loading and extend existing workflow creation guidance with document intake and
spreadsheet verification. The procedure reads attachments before questions,
clarifies workbook roles and genuinely missing business decisions, retains
answers, and records output comparison with its sources. Runtime routing,
file access, execution and model discovery remain enforced by their contracts.
Confirm the Agent actually receives and follows the procedure during acceptance.

## Verification cases

Backend discovery protocol fixtures: bounded success/pagination, malformed/huge
output, timeout/cleanup, missing/signed-out CLI, no inference/tool/login request,
no credential leakage. Selection: backend isolation, migration of Gateway choices,
stale/disappeared IDs, running-turn lock, read-only sessions, validated CLI argv.
UI: switch each backend, refreshed catalog/current/default, stale response ignored,
loading/failure state and persistence. Real installed CLI metadata smoke tests.
Novice acceptance: exact initial prompt, genuine business clarification, no old
asset reuse, independent artifact validation and durable final draft.

## Owner-approved Knowledge isolation correction

The owner asked whether preceding harness changes hurt Knowledge asking. Causal
fake-client comparison shows a new regression: with SOP history, a workflow/Skill
definition question creates an authoring task and gets an unfinished-trial warning;
the callback-disabled baseline does not. `TaskStore.observe` also mutates question
and repair budget before any Skill/model runs. Knowledge retrieval/citation code
is unchanged; the older context-blind Knowledge matcher is a distinct issue.

After requesting a Skill-first/explicit-consent rule, the owner specifically
authorized removing this interference. Only generic read-only question isolation
in authoring_task.py/chat_authoring.py is approved, retaining real authoring gates.
Skill procedures cannot prevent those deterministic pre/post-model side effects;
no business procedure or new orchestration is added. Conservative question
recognition is not a universal intent router. Final focused160 tests passed and
independent review cleared the update/change regression.

## Delivered state and remaining acceptance (2026-11-11)

Native models and the owner-approved Knowledge isolation are committed separately
as8cde171f/47f28a6b, packaged by the official builder, checked in a clean canary
and installed with preserved config. All559 Python source bytes matched.
Live model UI showed14 Claude Code and8 Codex IDs without inference. Live
Knowledge querying preserved the actual pending business question byteexact.
Focused groups167/20/171 and lint/format/typecheck/pipcheck/build passed. Initial
full result6572passed/5failed/10skipped; all4 failing whole modules rechecked
unchanged78passed. This is not an initially clean full-suite result.

Novice acceptance remains open: round1 produced only11orders without independent
source verification; round2 selected generic SOP guidance but failed3 navigation
trials. The owner explicitly approved domain Skill card ap-20261110-184948-7b7722;
sap-c4c-workflow-navigation1.0.1 is installed and selected alongside the generic
Skill in fresh round3. That round also failed3full navigation trials after2
autonomous repairs; it did not reach Excel acceptance. Proposed Skill1.0.2
passes format validation and awaits separate owner approval under creator step5;
its behavioral retest has not run. No domain harness changes are authorized.
Follow exact evidence/card IDs in HANDOFF/TASKS; do not confuse Skill installation
with passing workflow or workbook acceptance.
