# Product gate E2E-02 — SOP to deterministic Workflow

Status: implemented; local and PR #98 CI verification passed; merge pending

## User scenario

An engineer gives the Personal Agent a bounded SOP, representative input and
the expected observable output. The example normalizes category labels and then
counts records by normalized category. The Agent may use a model to create the
Workflow, but normal execution of the accepted Workflow is deterministic.

The committed case is `tests/fixtures/e2e_02/sop-workflow.json`. It keeps four
things explicit and separate:

- the SOP;
- exact installed capability identities required by the intended outcome;
- representative run arguments; and
- the independently expected final output.

## Minimum implementation

No new general agent framework was added. `host_runtime.workflow_author` is a
bounded application service over components already in the architecture:

```text
LocalAgentRequest
  -> resident LocalAgent admission
  -> normal Gateway route
  -> workflow-author.draft capability
  -> draft WorkflowManifest
  -> throwaway Gateway and WorkflowEngine
  -> existing Bridge, grants and approval policy
  -> observed/expected comparison
  -> validation evidence bound to manifest digest
```

The throwaway Workflow inventory prevents validation from installing or
publishing its candidate. A separate pure transition may apply human business
approval to a passing manifest. Technical policy and execution authorization
remain unchanged. A caller must explicitly install the published Workflow and
the Bridge must still authorize every capability step.

## Automated acceptance

`tests/test_product_e2e_02.py` proves the green path and the required negative
paths:

- the SOP enters through the resident Agent and normal Gateway route;
- a draft that omits a required outcome is rejected after bounded attempts;
- the fixture runs through Gateway, Workflow engine and Bridge with no external
  or write side effects;
- the expected output is compared outside the model;
- business approval can publish without changing pending technical policy;
- a published Workflow still fails when its capability grants are absent;
- a wrong observable output blocks publication; and
- two accepted replays produce the same result and dispatch order without any
  further model call.

Run the product gate with:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_product_e2e_02.py -q
```

The broader verification baseline remains `pytest`, Ruff, Mypy, `pip check`
and package build. CI stays inert: the case uses two pure in-memory
capabilities, a scripted model and a temporary SQLite host-state file.

## Architecture decisions

- REUSE the resident `LocalAgent`, `Gateway`, `WorkflowEngine`,
  `BridgeExecutor`, policy and `WorkflowManifest` contracts.
- EXTEND the existing bounded Workflow author with exact semantic capability
  requirements rather than creating a second authoring path.
- ADD validation evidence and one host use-case service because orchestration of
  draft plus fixture is an application concern, not a model or Workflow engine
  concern.
- KEEP publication, installation and execution authorization as separate
  operations.
- DEFER general code generation, workspace editing, self-repair and the rest of
  the Coding Harness to E2E-03.

## Gate

E2E-03 must not begin until this gate passes pull-request CI and merges. The
production-like company workstation is not needed for this case because every
fixture capability is intentionally side-effect-free; physical and enterprise
resource evidence remains part of later gates.
