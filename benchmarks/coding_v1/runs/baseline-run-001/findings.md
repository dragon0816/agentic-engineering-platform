# baseline-run-001 — findings

Observed facts only, from `T??/trace.json` (the Agent Web reply, including the
Gateway's record of every tool call) and the validators. No task produced an
output file. No reply claimed a completion that did not happen.

## Platform gaps and defects

| Code | Kind | What happens | Minimal reproduction | Tasks |
|---|---|---|---|---|
| G1 | capability gap | The conversation Agent has no tool to read a local file, write a file, run a program or fetch a URL. It says so and offers code for a person to run. | Agent Web chat, new session: send `prompts/T01.md` filled with any workspace path. | T01 T02 T04 T05 T09 T14 T15 T16 T17 T18 T19 (and underneath every other task) |
| G2 | capability gap | The only coding tool, `coding/change`, edits one file in a repository configured in host.json (`practice`) and is judged by existing pytest tests. A workspace that is not a configured repository is refused with `workflow_choice_unavailable`, and an unrelated task cannot supply tests without handing the Agent its validators. | Send `prompts/T06.md`; the trace shows `coding__change` → `workflow_choice_unavailable`. | T06 T08 T20 |
| D1 | defect | A chat message whose wording matches the installed Knowledge candidate Skill's intent rules (product, price, spec words) is sent straight to the Knowledge harness (`knowledge-query/ask`, skill `company-agent/knowledge-query@1.4.0`); the model never sees it, and the answer is `knowledge_insufficient_evidence`. Code: `AgentWeb._skill_intended_knowledge` in `src/host_runtime/web.py`. | Send `prompts/T10.md`: reply "The Knowledge query did not produce a validated answer"; `outcome.decision.target` is `knowledge-query/ask`; the fixture server receives no request. | T07 T10 T11 T12 T13 |
| D3 | defect (not yet reproduced) | The Gateway model returned an empty answer (`empty_model_answer`); the turn failed. | Send `prompts/T03.md` or `prompts/T08.md`. Whether it repeats is not known (each task ran once). | T03 T08 |

Further observations:

- T20: the Agent did not ask for the missing threshold. It went straight to
  `coding__change`, which was refused (G2). The scripted clarification was
  never sent (0 interventions). The fault-injection sub-check is BLOCKED by
  design: no runtime write operation exists to inject into.
- T09 and T20 need a Workflow built and run in the platform runtime. From
  chat, the Agent has no tool that installs or runs a drafted Workflow
  (SOP to Workflow authoring exists only as `/api/authoring/*`, not as a chat
  tool; see `docs/phases/CONVERSATIONAL_AUTHORING.md`).
- Web tasks: the fixture server logged no request in any task (`fixture_requests` in each trace).

## Telemetry limitations

- Tool calls: exact, from the Gateway trace (`answer.outcome.conversation.tools`).
- Repair loops and first-attempt success: not observable (the trace has no
  program edits or reruns); `null` for every task.
- Attachments were given as workspace paths in the prompt: Agent Web chat has
  no upload entry.
- One attempt per task (first-round setting); a formal comparison needs ≥3.

## Improvement priorities (by tasks unblocked)

1. G1: give the conversation Agent a governed coding tool: read the task's
   workspace, write files, run Python under the restricted runner, observe and
   repair (the restricted runner and worktree pieces exist from the coding
   work). This unblocks all twenty tasks.
2. D1: route to the Knowledge harness only when the model or an explicit
   command selects Knowledge, not by keyword intent alone (5 tasks).
3. Chat-side Workflow authoring and runs (planned A4-A6) for T09 and T20.
4. D3: reproduce `empty_model_answer` and handle it with a retry or a clearer failure.

Fixes are evaluated under a new run ID; `baseline-run-001` stays as recorded.
