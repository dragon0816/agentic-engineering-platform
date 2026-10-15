# Workflow run forms in the chat (owner finding 2026-10-15)

## Finding

- Agent Web: "我要執行rs-wmt-package-release" was answered in prose: the model
  listed static settings (`release_repo_url`, `work_root`, `inbox_path`,
  `allowed_root`) and runtime fields and asked the person to type them. The
  generated form existed only under Capabilities > Workflow > "Run this
  Workflow".
- Telegram: "我要執行rs-wmt-package-release workflow" got only the status line
  "✅ Done after 12 s / Skills used: /authoring list_workflows — done". Only
  `/run X` started the question flow (`channels/telegram_flow.py`).

## Root cause

1. No route for a person's run request. Agent Web `conversation_turn` and
   Telegram `_deliver` send free text to the Gateway conversation unless it is
   a dot/slash command, a Skill rule or a Knowledge request. An installed
   Workflow is a model tool only when a Skill command names it; a Workflow
   installed from a chat draft is reachable only through the authoring tools
   (`authoring__list_workflows`, `authoring__get_workflow`,
   `authoring__run_workflow`), whose output is the raw parameter declaration.
   So the model read the declaration and asked for every value in prose,
   including settings, which are never run values.
2. A Telegram turn could end with no visible answer. A reply Telegram refused
   (`sendMessage` not 200, e.g. a 429 right after the progress edits, or an
   empty text) was recorded as `replied=False` and nothing else was sent, while
   the progress line already said "Done". An answered turn with blank text had
   no fallback either. Which of these happened live is not visible from the
   code; both are closed below.

## Design

Authors still declare only parameters; every interface is drawn from them.

- `common/workflow_run_form.py` (pure):
  - `run_intent(text, manifests)`: a run verb (執行/跑/啟動/run/start/launch/
    execute/...) and exactly one installed Workflow named. A distinctive name
    (contains `-`, `_`, `/` or a digit, or 12+ characters) may be anywhere; a
    plain word (`push`) must follow the verb. A name inside another matched
    name does not count. Questions (怎麼/為什麼/what/how ...), refusals
    (不要/cancel ...), messages over 400 characters and two candidates are left
    to the model.
  - Prefill: `name=value` / `name: value` pairs typed with the request
    (`person_prefill`: runtime fields on a person's channel, valid, never an
    upload, never credential-shaped). A model's values go through
    `agent_prefill`: only agent-channel, non-`confirm` fields. Settings are
    never prefill.
  - `form_offer(...)`: `{kind: "workflow_form", workflow, title, description,
    prefill, missing_settings, origin, message}`. `missing_settings` lists
    required `scope: static` fields with neither a stored value nor a default
    (from the engine's settings provider; an unreadable store counts as not
    set).
- Gateway hand-off (a person's conversation only, `session_id` set; tasks and
  schedules keep the old behaviour):
  - Host tool `workflows__run_form` (`host_runtime/workflow_form_tool.py`):
    the model names the Workflow and the values the person stated; the system
    prompt says to call it instead of asking in prose.
  - A Skill-bound Workflow tool call whose values are incomplete or refused,
    and `authoring__run_workflow` on an installed, unchanged Workflow with
    incomplete values, return the same offer instead of a failure. A complete,
    valid call still runs (the Agent-tool path for orchestration stays).
  - A host outcome carrying an offer ends the turn; the answer text is the
    offer's message.
- Agent Web: the explicit intent is checked before Skill rules and Knowledge
  routing (after dot commands); `/run <name>` opens the form too (`/run 11`
  and `/run workflow ns/name@v {json}` are unchanged). The assistant message
  stores `workflow_form`; the page draws it under the answer with the shared
  `renderParameterForm` (combo boxes with Refresh list, dependent `fn:` lists,
  uploads, "Use last values", prefill set before lists load). Only the newest
  answer's form starts open; older ones fold into `<details>`. Missing settings
  show a notice with "Open <name> settings" (Capabilities > Workflows > that
  Workflow) and Run stays disabled. Run posts `/api/workflows/run` with
  `session_id`; the host adds the run and its result to that conversation as a
  pair ("▶ Run X from the form: ..." then the result), so the Agent sees it.
- Telegram: the explicit intent, and a model's offer, start the same
  `telegram_flow` as `/run X` (same as last time, buttons, multi-select,
  uploads). Prefilled values are answers already given: not asked again and
  always shown in the Run/Cancel confirmation. Missing settings are named with
  a pointer to Agent Web (also for `/run X`). Never silent: blank model text
  becomes "The Agent gave no answer after using ...", a 429 is retried once
  after `retry_after` (at most 5 s), a 400 with a keyboard is retried without
  it, and an answer that still cannot be sent is followed by "The answer could
  not be delivered here ...".

Side-effect confirmation is unchanged: Web runs on the person's Run click
(privileged fields still ask), Telegram confirms every non-read run with a tap.

## Out of scope

Choosing between two matching Workflows by asking; prefill from free prose
without a model; editing a form after its run; the schedule form.
