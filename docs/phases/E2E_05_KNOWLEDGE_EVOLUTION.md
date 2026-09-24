# Product gate E2E-05 — governed Knowledge continuous evolution

Status: implemented with a reproducible local Windows/Python 3.12 green path;
pull-request CI and merge pending

## User scenario

An engineer asks the Personal Agent a question against an exact published
Knowledge version. The answer cites immutable Raw evidence but omits a required
fact. The engineer reports the omission conversationally. The system preserves
the exact version, trace, answer and cited passages in a structured improvement
request without changing the published vault.

A maintainer approves development. The normal Agent/Gateway route invokes a
Bridge-installed and explicitly approved write capability, which copies the
published vault to a candidate root and applies a typed curation plan. The new
question becomes an evaluation case beside the existing regression. Both must
produce Raw-grounded answers before a domain owner separately approves and
publishes vNext. The old exact version remains available for rollback.

The committed miniature vault is under `tests/fixtures/e2e_05/`. It includes a
Raw source, source/entity Wiki pages, a persisted rejection decision and one
existing evaluation behavior. No live model, network, database or production
resource is required.

## Minimum implementation

```text
LocalAgentRequest
  -> Gateway -> Bridge -> knowledge-query.ask
  -> Raw-grounded KnowledgeAnswerRecord
  -> KnowledgeImprovementRequest (published vault unchanged)
  -> maintainer triage approval
  -> Gateway -> Bridge approved write -> Knowledge candidate vault
  -> feedback case + existing regression validation
  -> domain-owner business approval
  -> published KnowledgeManifest vNext
  -> corrected exact-version query; vPrevious still queryable
```

## Automated acceptance

`tests/test_product_e2e_05.py` proves:

- every claim in the initial and corrected answers cites an exact Raw passage;
- feedback retains the exact asset/version, answer, trace and cited passages;
- feedback alone cannot mutate published Knowledge or create a candidate;
- candidate creation follows the installed Bridge write capability and approval;
- the Bridge confines candidate roots to its configured workspace;
- Raw stays byte-identical and decision records survive candidate creation;
- the user's question becomes the new case beside an existing regression;
- passing the new case cannot hide a failing regression;
- content drift after validation makes the evidence unusable;
- domain approval is distinct from validation and runtime authorization;
- publication creates a new semantic version and preserves exact rollback;
- Wiki-only unsupported content is refused as ungrounded; and
- a persisted rejected claim cannot be restored by a later curation plan.

Run the gate on the supported development target:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_product_e2e_05.py -q -p no:cacheprovider --basetemp .scratch\pytest-e2e05
```

CI runs only on `windows-latest` with Python 3.12 by owner decision. The package
compatibility declaration remains Python 3.11+.

## Architecture and migration decisions

- **REUSE** the resident `LocalAgent`, `Gateway`, `BridgeExecutor`, installed
  Skills and `LocalPolicy`; query and candidate creation use no alternate path.
- **REUSE** the Phase 4 `Vault`, `QueryEngine`, Raw provenance, `WritePlan`,
  static decision record and immutable-Raw behavior.
- **WRAP** exact-version query and candidate workspace creation as installed
  Bridge capabilities. The latter is a `write` with required execution approval.
- **ADD** versioned Knowledge manifests/catalog entries, grounded answer records,
  improvement requests, evaluation cases and validation evidence.
- **DO NOT MIGRATE** a second source implementation. This slice composes already
  migrated platform behavior and adds only the missing governed lifecycle.
- **DEFER** production Registry/database, remote vault storage, real model
  evaluation and automatic issue/repository integration.

## Gate

E2E-04 must not begin until this gate passes pull-request CI and merges. The
next phase may reuse these improvement/evidence/approval transitions for
Software, but it must not turn Knowledge publication into execution permission
or weaken exact-version rollback.
