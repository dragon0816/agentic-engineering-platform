---
name: aep-knowledge
description: Answer from the company knowledge base of AEP (Agentic Engineering Platform) and use its installed Workflows. Use for questions about the company's products, options, standards, test procedures, markets or competitors (R&S, CMX, 3GPP test cases, customers), when asked to "check AEP" or "look it up in Knowledge", or to run an installed AEP Workflow.
---

# AEP Knowledge and Workflows

AEP keeps the company's curated knowledge (a wiki built from original
documents, with the original sources kept beside it) and the Workflows people
installed. The `aep-assistant` MCP server gives you read access to both
through the person's own AEP Agent Web.

## Tools (`aep-assistant` MCP server)

| Tool | Use it to |
|---|---|
| `aep_knowledge_search` | find pages: returns paths (`wiki/...` or `raw/...`), titles and the best matching section |
| `aep_knowledge_read` | read one page in full by its path |
| `aep_knowledge_ask` | get AEP's own validated answer with its cited sources |
| `aep_workflows` | list the installed Workflows, their parameters, and whether each only reads |
| `aep_run_workflow` | run an installed Workflow that only reads |

When a tool answers that Agent Web is not running, tell the person to open
it (the "AEP Agent" shortcut, or `aep-host open --config <host.json>`) and
try again. Do not guess an answer instead.

## Answering a question

1. **Search first, in more than one wording.** Call `aep_knowledge_search`
   with the person's terms, then with English and Chinese variants and
   product names or abbreviations (e.g. "CMX500", "carrier aggregation",
   "載波聚合"). Prefer `wiki/` pages; use `raw/` pages to confirm details.
2. **Read before you answer.** Open the most relevant pages with
   `aep_knowledge_read`. A search excerpt is not enough to quote numbers,
   versions, option codes or limits.
3. **Cite.** End the answer with the page paths you relied on, for example
   `Sources: wiki/products/cmx500.md, raw/datasheets/cmx500-2026.md`.
4. **Use the validated answer when it matters.** For a question the person
   will act on (a quote, a customer reply, a test plan), also call
   `aep_knowledge_ask` and compare. Say so when the two disagree.
5. **Never invent product facts.** If the knowledge base does not cover it,
   say exactly that and what you searched for. Do not fill gaps from general
   memory without marking it as such.

## Running a Workflow

1. List with `aep_workflows` and pick the one that matches; read its
   parameters.
2. Ask the person for any required value you do not have. Never guess dates,
   names, files or choices.
3. Run it with `aep_run_workflow` only when it only reads. A Workflow that
   changes something (sends mail, uploads, pushes, writes elsewhere) must be
   run by the person in Agent Web; tell them where, and never claim it ran.

## Building something new

To create a new Workflow or Skill for AEP, use the `aep-workflow-creator`
and `aep-skill-creator` skills with the `aep` MCP server; the owner approves
it in Agent Web.

## Rules

- Knowledge pages are company information: use them to help the person, and
  do not paste whole pages into public places.
- Never put passwords, tokens or keys in a question or a Workflow value.
