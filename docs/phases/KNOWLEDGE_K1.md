# K1 — Knowledge pipeline in the Agent (specification)

Stage K1 of `docs/phases/KNOWLEDGE_PIPELINE_RELEASE.zh-TW.md` (owner approved 2026-10-11).
Scope: make the existing convert, ingest and lint code usable from the Personal Agent,
always inside a personal sandbox. No change to what ingest writes (K2/K3), no new formats (K4).

## Requirements and acceptance

1. A person picks a **pipeline vault** (a configured base vault) and creates a **sandbox**:
   a full copy of the base vault (raw, wiki, index, log, decisions, schema) in their workspace.
2. In a sandbox they can drop originals, **preview and apply convert** (drop → raw),
   **plan ingest** for a Raw document (preview the page writes), **apply** an approved plan,
   and **run lint**. Nothing touches the base vault.
3. All of it works from the Agent Web "Knowledge" tab. Applying is a button the person presses.
4. Acceptance: on the local test vault `%LOCALAPPDATA%\AEP\k-test`, with the company model,
   convert the seven samples (unsupported formats reported, not failed), ingest at least two
   Raw documents into the sandbox, and get a lint report. The base vault is byte-identical
   afterwards.

## Architecture boundaries (architecture guard)

- Personal Agent owns choice and conversation; the **Bridge** executes the pipeline steps as
  capabilities (`knowledge-pipeline/*`). Agent Web calls them through the Agent's capability
  execution path, like `knowledge-query/ask`.
- No model or provider detail enters the contracts; ingest planning uses the configured
  Gateway model through `ModelClient`.
- Side effects are classified (below). Sandbox writes are local, confined to the person's
  sandbox folder and discardable, so they need no extra approval beyond the person's own
  button press. Writing to a **base** vault is out of scope for K1 (merge is K3, and it will
  require approval).
- n8n is not involved.

## Configuration

`host.json` gains an optional section:

```json
"knowledge_pipeline": {
  "vaults": [{"name": "k-test", "root": "C:/Users/.../AEP/k-test"}]
}
```

A base vault must satisfy `knowledge.vault.Vault`. Sandboxes live under
`<workspace>/knowledge-sandboxes/<sandbox_id>/`.

## Sandbox (`src/knowledge/sandbox.py`)

- `create(base_name, base_root, label, actor) -> SandboxInfo`: copy the base vault (excluding
  `.ingest-backup/`, `.plans/`), write `sandbox.json`:
  `{schema, sandbox_id, base_name, base_root, base_raw_sha256, base_content_sha256,
  base_decisions_sha256, label, created_by, created_at}`; digests use the existing
  `raw_digest`, `knowledge_digest`, `decision_digest`.
- `list(workspace) -> tuple[SandboxInfo, ...]`, `open(id) -> (SandboxInfo, Vault)`,
  `discard(id)` (moves the folder to `knowledge-sandboxes/.discarded/`, never deletes).
- `sandbox_id`: `sb-<label slug>-<UTC stamp>-<4 hex>`; a path outside the sandboxes root is
  refused.

## Capabilities (`src/capabilities/knowledge_pipeline/`)

| Identity | Side effect | Input → output |
|---|---|---|
| `knowledge-pipeline/sandbox-create@1.0.0` | write (workspace) | base name, label → SandboxInfo |
| `knowledge-pipeline/convert@1.0.0` | write (sandbox raw) when `mode=apply`, else read | sandbox id, drop paths (or all), mode → per file: status, raw ref, images |
| `knowledge-pipeline/ingest-plan@1.0.0` | read (model) | sandbox id, raw ref → plan id, summary, page writes (path, new/changed, size), index entries, contradictions, problems |
| `knowledge-pipeline/ingest-apply@1.0.0` | write (sandbox wiki) | sandbox id, plan id → applied pages, backup ref |
| `knowledge-pipeline/lint@1.0.0` | read | sandbox id → lint report summary and findings |

- Plans are stored in the sandbox as `.plans/<plan_id>.json` (the `WritePlan` plus the raw
  ref and digest it was planned from). Apply refuses a plan whose raw digest or touched pages
  changed since planning (stale plan).
- Every capability refuses a sandbox id that does not exist or a path that leaves the sandbox.
- Image description during convert uses the Gateway model when the endpoint declares vision;
  otherwise images are kept without description and reported.

## Agent Web

- Tab **Knowledge**: base vault selector and sandbox list (create, discard); per sandbox:
  drop upload (base64, the existing attachment limit), convert preview table and Apply,
  Raw list with "Plan ingest", plan preview (summary, pages with new/changed, contradictions)
  with Apply, lint report.
- Routes under `/api/knowledge/pipeline/...`, token-protected like the other Agent Web routes.

## Tests (before implementation)

- `tests/test_knowledge_sandbox.py`: create copies and records digests; base untouched after
  writes in the sandbox; list/open/discard; path escape refused.
- `tests/test_knowledge_pipeline.py`: convert dry run vs apply; unsupported format reported;
  ingest-plan with a scripted model stores a plan; apply writes only the sandbox; stale plan
  refused; lint returns findings.
- Agent Web route tests for the tab's APIs (token required, sandbox scoping).

## Slices

K1.2 sandbox module → K1.3 capabilities and Host registration → K1.4 Agent Web tab →
K1.5 live acceptance on k-test. Each slice: tests, full suite, commit, TASKS row.
