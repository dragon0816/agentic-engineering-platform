# IT-owned tool access — active implementation

Date2026-11-12. Branch it-owned-tool-access-20261112; native managed worktree
C:/Users/Chi_L/.paseo/worktrees/2qnenase/it-owned-tools-20261112,
workspace wks_9e3f85169bdceb9b, project prj_dec237428b9faaef.
Base394ca4d2; plan/consent3817892c; Task1 execution52a4de64.

## Owner goal and authorization

Owner explicitly requires all AEP tools and agent-driven tool installation,
without AEP grants/installation/per-call approvals or extra command/folder/mail
restrictions. IT/OS/service identity decides usability. Owner replied to the
concrete four-part harness scope:「同意上述 harness 範圍並開始實作」.
This satisfies AGENTS22 for this stated scope; do not ask the same approval
again. Read IT_OWNED_TOOL_ACCESS_DESIGN_20261112.md, PLAN and LEDGER.
No new model/data-policy, shared publication or unrelated chat-form-persistence
change is approved. Scope expansion still requires evidence and new consent.

## Work completed and actual verification

Task1: LocalPolicy is now a compatibility identity facade, with no per-tool
permission/approval decision. It accepts old constructor/add interfaces without
making fake grants. Unknown tools, strict inputs, real dependencies/handler errors
remain.64focused tests passed5.47s, Ruff and runtime.py mypy passed. Old default-
deny/review-as-admission assertions intentionally now assert real execution.

Task2: portable blocks (Outlook search/read/draft, data/Excel, release/NCC/loan
blocks) no longer need an asset reference. BI/contacts no longer need a procedure
Skill to register. Local Skill/Workflow/script availability no longer uses legacy
member tool selections. No startup runtime grant synthesis. Old grants are not
an admission input; authenticated device/Knowledge selection/model eligibility
remain. Doctor counts actual installed assets.52focused host/discovery/external-
authoring tests passed22.22s; Ruff and host.py mypy passed.46Knowledge isolation/
pipeline host tests passed25.86s. No COM/mail access in discovery tests.

Evidence: .scratch/it-owned-verification/task1-red.log (corrected causal red),
task1-green.xml/log, task2-red/expanded-red, task2-affected.xml/log,
registration-knowledge.xml/log and mypy logs. Initial red fixture omitted required
central_required; fixed before accepting causal red; original log preserved.
Full suite/build has NOT run for this feature yet. It is not complete.

## Baseline and environment

Use C:/Users/Chi_L/Documents/ChatGPT/agentic-engineering-platform/.venv/Scripts/
python.exe with this worktree src first on PYTHONPATH. Do not repoint the shared
editable install. AEP_OUTLOOK_TESTS=0/AEP_GUI_TESTS=0; use fakes, no real mail/send.
Before changes, Git confirmed e69371e6 and394ca4d2 source/tests/evaluation/benchmarks
identical. The prior verified baseline is6619passed/13skipped and445Knowledge
cases; copied knowledge-baseline.xml into this worktree's verification folder.
At final freeze compare the SAME445identities/outcomes, run full pytest once,
Ruff/format/mypy/build/pipcheck; record original failures, never weaken tests.
Known earlier CI BI UI failures/control evidence remains in LOW_RISK report.

## Remaining implementation

Task3: common discovery/description/invocation + system/run-command. All installed
tools must remain reachable despite context/catalog paging or selected procedure.
Configured-only tools need truthful setup descriptors, not an absent/denied label.
New interfaces and task tests are in the plan; no ToolAccess implementation yet.
Keep actual data internal on eligible company Gateway; external authoring MCP's
status-only data boundary is not permission to forward private rows/mail to a
PUBLIC native model. Do not silently change model/data eligibility.

Task4: agent installs/connects MCP via existing McpHub.save/connect and command
capability, same-session discovery, no fake approval or restart. Task5: direct
local Skill/Workflow installs and honest provenance/quality, no cards. Task6:
remove legacy mail/folder/command/backend gating, direct send distinct from draft,
retain external technical errors and model/data rules. Task7: regression/docs/
Knowledge and user-flow acceptance. Task8: final freeze/checks/fresh review/handoff.

Important implementation details: HostTool.side_effect is currently static;
Gateway turn effects key calls by tool name+arguments. New invocation paths must
not bypass at-most-once execution or incorrectly memoize reads. Canonical aliases
need real classification/identity and tests. TurnEffects is in agent/turn_effects.py.
McpHub currently synthesizes owner grants and omits side_effect on HostTool:
update those in Task4 with tests, not an approval workaround. Loan send remains
card-only legacy code and must be addressed with Task6, not claimed available now.

## State and next action

Task2 source/test changes and discovery test are ready for its coherent commit;
check git status and ledger before changing more. No process is active. Next:
commit Task2, then Task3 red tests and implementation. Continue autonomously
through all approved tasks; do not finish at this partial checkpoint.

Original checkout main097b2521, origin/main267c75e4 and delivered C4C branch/package
are untouched. Current resident044bd7b5 at LOCALAPPDATA preview-0.1.0 is not updated.
Do not restart it during active tasks/forms. Do not touch shared Gateway config:
prior package canary had an isolation incident; future canaries require explicit
AEP_GATEWAY_HOME and no user-env export, or -NoGateway. See package report.
