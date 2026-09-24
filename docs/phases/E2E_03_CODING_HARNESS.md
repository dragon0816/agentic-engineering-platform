# Product gate E2E-03 — bounded parser/transformation development

Status: complete; merged in PR #99 after Windows/Python 3.12 CI passed

## User scenario

An engineer supplies a bounded record-transformation requirement, a workspace,
a representative new case and an existing regression case. The Personal Agent
routes the request through the normal Gateway and Bridge to the installed Coding
Harness. The first candidate deliberately mishandles a numeric conversion. The
external validator rejects it, the author receives structured failure evidence,
and one repair produces a transformation that passes both cases.

The committed inputs are under `tests/fixtures/e2e_03/`. They include the
starting workspace, requirement, initial incorrect candidate, repaired candidate
and expected outputs. No live model, network endpoint or production resource is
required.

## Minimum implementation

```text
LocalAgentRequest
  -> resident LocalAgent admission
  -> model-selected installed Skill route
  -> Gateway
  -> Bridge write authorization and approval
  -> coding-harness.run
  -> pinned BoundedWorkspace
  -> HarnessPlan
  -> CandidateChange
  -> injected json_transform.validate
  -> structured ValidationFailure
  -> bounded repair
  -> new + regression cases pass
  -> CodingHarnessResult
```

The author is a provider-neutral protocol. The product test uses a scripted
author so CI is inert and deterministic. Completion belongs to the declared
validator, never to the author or routing model.

The validator executes a typed JSON transformation program. This is the
smallest safe parser/transformation proof. It demonstrates the Harness lifecycle
without claiming that an ordinary subprocess is a sandbox. General generated
Python execution remains deferred until a real isolation adapter can implement
the same declared-command boundary.

## Automated acceptance

`tests/test_product_e2e_03.py` proves:

- explicit absolute workspace root and starting content revision;
- plan evidence precedes every recorded mutation;
- actual before/after hashes and unified patches are separate from the plan;
- path traversal and undeclared validation commands are refused;
- Bridge policy and explicit approval gate the workspace write;
- the wrong first candidate fails its independent golden output;
- structured failure reaches one bounded repair;
- the final candidate passes the new and committed regression cases;
- a regression failure blocks completion even when the new case passes;
- exhausted repair budget returns a typed failure;
- the result records artifact digest, commands/outcomes, Skill versions, trace
  and ordered events; and
- the Harness cannot mark a result committed or published.

Run the gate on the supported development target:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_product_e2e_03.py -q -p no:cacheprovider --basetemp .scratch\pytest-e2e03
```

CI runs only on `windows-latest` with Python 3.12 by owner decision. The package
compatibility declaration remains Python 3.11+; this slice did not change it.

## Architecture and migration decisions

- **REUSE** `LocalAgent`, `Gateway`, `BridgeExecutor`, `LocalPolicy`, installed
  Skills and the capability contracts.
- **ADD** the provider-neutral Harness contracts/runtime at the Personal
  Engineering execution boundary and one Bridge-installed `write` capability.
- **ADAPT** the `knowledge_management` benchmark's strongest proven invariant:
  every grader must reject a deliberately wrong output.
- **DO NOT MIGRATE** its live-model plus arbitrary-subprocess runner. The source
  explicitly is not a sandbox, depends on a live endpoint, and cannot satisfy
  the inert CI or governed command boundary.
- **DEFER** Git commit/push/publish and general-purpose code execution. A
  validated change remains a candidate for a separate governed transition.

## Gate

E2E-05 must not begin until this gate passes pull-request CI and merges. E2E-05
will reuse the Harness validation pattern for a Knowledge candidate while
keeping Raw immutable and domain approval separate from technical validation.
