# GitHub Copilot as an AEP agent mode (design)

Owner decisions, 2026-10-12:

- Integrate GitHub Copilot, a company-approved agent each user can apply for, so users
  get a mature agent while AEP's own harness matures.
- All data may be sent to GitHub Copilot.
- Each user signs in with their own Copilot account.
- Agent Web keeps the AEP harness as the default; a user may choose the Copilot mode.

## 1. Shape: Copilot thinks, AEP provides governed tools

```
User (Agent Web conversation, or VS Code)
  └─ GitHub Copilot CLI / agent mode (its own harness, the user's own account)
       └─ AEP assistant tools over MCP (read-only knowledge, installed Workflows)
```

- **Agent Web.** A new conversation backend, "GitHub Copilot (agent)". It runs the
  user's signed-in `copilot` CLI with:
  - the AEP assistant tools as its only tools: `--additional-mcp-config`,
    `--allow-tool aep`;
  - file writes and shell denied: `--deny-tool shell`, `--deny-tool write`;
  - built-in MCP servers disabled.

  The existing "GitHub Copilot" backend (text only, no tools) stays.
- **The tools are served by the running Agent Web** at `POST /mcp` (MCP over HTTP,
  JSON-RPC). The tools use the Host's loaded Knowledge and models, and requests use
  Agent Web's bearer token. A stdio server would rebuild the Host on every turn, which
  takes tens of seconds.
- **VS Code Copilot** can use the same endpoint while Agent Web runs. The stdio
  `aep-host mcp` stays for authoring.

## 2. The assistant tools

| Tool | What it returns |
|---|---|
| `aep_knowledge_search` | Pages of the published Knowledge that match a query: path, title, best section text |
| `aep_knowledge_read` | One wiki or Raw page of the published Knowledge, up to 40,000 characters |
| `aep_knowledge_ask` | The AEP Knowledge Harness's answer: validated, with its sources |
| `aep_workflows` | Installed Workflows: id, description, parameters |
| `aep_run_workflow_installed` | Runs an installed Workflow. A read-only one runs now; one that changes something waits for the person's approval in Agent Web, as in the AEP conversation |

- **Read only.** No tool writes Knowledge, files or settings. Workflow side effects keep
  their approval rule.
- **Data boundary.** Unlike the authoring tools, which return only statuses and codes
  (EXTERNAL_AUTHORING), the assistant tools return content, because the owner approved
  sending all data to Copilot.
- Every call is recorded in telemetry as a `capability_call`.

## 3. Answers and measurement

- **Labelling.** A Copilot answer is shown as "GitHub Copilot (agent)". It is not
  validated by AEP, except where Copilot quoted `aep_knowledge_ask`, whose answer is.
- **Benchmark.** The 36 knowledge_v1 questions run through the Copilot mode
  (`run.py --backend copilot_agent`), graded the same way. The result is compared with
  the AEP harness (core-015: answerable coverage 0.503), and the comparison decides
  later defaults.

## 4. Sign-in

- Copilot is per user: `copilot login` through GitHub's browser flow (company SSO). The
  alternative is `COPILOT_GITHUB_TOKEN`.
- The company LLM gateway is different: one host API key.
- Agent Web's existing backend sign-in flow handles the Copilot login.

## 5. Slices

| Slice | What |
|---|---|
| CP1 | Assistant tools and the `/mcp` endpoint on Agent Web |
| CP2 | The "GitHub Copilot (agent)" conversation backend with the tool restrictions |
| CP3 | Live check after the owner installs the Copilot CLI and signs in; adjust flags to the installed version |
| CP4 | knowledge_v1 through the Copilot mode; comparison with the AEP harness |
