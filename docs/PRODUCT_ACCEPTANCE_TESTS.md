# Agentic Engineering Platform — Product Acceptance Tests

Status: product-level acceptance source of truth.

`PRODUCT_VISION.md` defines the product direction. This document defines the
observable evidence required to claim that direction works. `ARCHITECTURE.md`
describes the current implementation and may evolve incrementally to satisfy
these tests; it should not be rewritten when existing components can be reused.

## Required implementation order

```text
E2E-02 -> E2E-03 -> E2E-05 -> E2E-04 -> E2E-01

SOP -> deterministic Workflow
    -> coding / transformation capability
    -> Knowledge continuous evolution
    -> Software continuous evolution
    -> physical DUT / chipset engineering capability
```

This order is a product gate. Work on the next E2E may be analyzed, but its
runtime implementation does not begin until the current E2E has a reproducible
passing path.

## Rules common to every E2E

An E2E passes only when all of the following are true:

1. The test begins with a user-level request and ends with a result the user can
   inspect; calling an internal class directly is not the complete E2E.
2. Inputs, expected result and validation method are explicit before execution.
3. Completion is decided by an external validator or observable evidence, never
   by a model's statement that it succeeded.
4. The green path is reproducible from committed fixtures and exact commands.
5. At least one negative case proves that a plausible but wrong result fails.
6. Every action passes through the normal Agent, Gateway, Workflow or Bridge
   boundaries that production will use. A test-only path cannot be the only
   evidence.
7. Side effects, permissions, approvals and execution environment are visible in
   the evidence. Publication never grants execution permission.
8. Shared assets contain `SecretRef` requirements only. No credential value may
   appear in a fixture, asset, trace, log or result.
9. The result records the relevant asset versions, inputs, validator outcome and
   trace identifiers so another person can explain what ran.
10. CI remains inert: no real company system, email, browser account, Git write,
    DUT, instrument or production credential is used.
11. When production-like evidence is required, it is collected separately on an
    enrolled Bridge and linked to the acceptance record. CI does not pretend to
    provide that evidence.
12. Architecture and phase documentation are updated only after the green path
    has been demonstrated and the implementation boundary is known.

Each E2E therefore has two possible evidence layers:

- **Automated gate:** committed fixtures, integration/E2E tests and CI-safe
  substitutes that must pass on every supported platform.
- **Production-like gate:** an explicit run on an enrolled Bridge when real
  software, company access or hardware is part of the product claim.

## E2E-02 — SOP to deterministic Workflow

### User scenario

A user provides a bounded SOP, representative inputs and observable expected
outputs. The Personal Agent creates a reviewable Workflow candidate from the
capabilities installed on the user's Bridge. The platform validates and executes
the candidate against fixtures. After human approval and publication, the same
Workflow runs deterministically without asking a model to reinterpret the SOP.

The reference fixture should be small and side-effect-free, for example:

```text
Read a supplied text dataset
  -> normalize the records
  -> count records by category
  -> produce a structured summary
```

### Automated acceptance criteria

1. The request enters through a supported Personal Agent ingress and reaches the
   existing Gateway rather than a test-only authoring API.
2. The SOP, installed capability catalogue, representative input and acceptance
   expectations are preserved as distinct inputs.
3. The resulting candidate validates as the provider-neutral
   `WorkflowManifest` contract and remains in `draft` lifecycle.
4. Every step names an exact installed capability identity and version. Invented
   capabilities are rejected.
5. Step inputs, required fields, result references, ordering and declared local
   or central dependencies are valid.
6. The candidate represents every required SOP outcome. If a required operation
   cannot be provided by installed capabilities, the result is a structured
   `needs_input` or refusal; silently omitting it is a failure.
7. Static review catches at least: an unknown capability, an invalid input, a
   missing required input, an invalid dependency and a future-step reference.
8. The draft neither installs nor publishes itself and receives no execution
   permission merely by existing.
9. Fixture execution follows the normal Gateway -> Workflow engine -> Bridge
   path and produces the declared output contract.
10. An independent validator compares the observed output with committed
    expectations. A structurally valid but semantically wrong result fails.
11. A human approval action is represented separately from technical/policy
    authorization before the candidate becomes publishable.
12. The approved Workflow runs at least twice with the model disabled. The
    normalized output and ordered capability dispatches are identical.
13. The trace records request, route, Workflow identity/version, step dispatches,
    approvals, validation result and final outcome without secret values.
14. The entire automated scenario passes in CI without network or production
    side effects.

### Required negative demonstrations

- A drafter that omits an SOP-required transformation is rejected even when its
  manifest is structurally valid.
- A Workflow that has been published but not authorized cannot execute.
- A Workflow whose output violates the expected result is not reported as
  complete.
- A deterministic replay that reaches the model fails the test.

### Reproducible green path

The phase is complete when one documented command executes the committed E2E-02
case from user request through validated fixture result, and the same case runs
in the repository's Windows/Linux CI matrix. The command and observed result are
recorded in `HANDOFF.md` after they exist.

### Phase gate

E2E-03 implementation may begin only after all automated E2E-02 criteria pass.
A live model may be exercised as additional evidence, but CI uses a scripted
provider response so model availability cannot weaken the product gate.

## E2E-03 — Bounded coding and transformation capability

### User scenario

A user supplies a bounded transformation requirement, representative input,
expected output and a workspace. The Personal Agent understands the workspace,
plans a change, modifies or creates the transformation, executes it, observes a
deliberately exposed failure, repairs it within a fixed iteration budget and
returns the validated result plus the change set.

The first reference case should be a parser or format conversion with golden
files. It requires neither company credentials nor physical hardware.

### Automated acceptance criteria

1. The workspace root and starting revision are explicit and immutable in the
   run record.
2. Read, write and command capabilities are limited to the declared workspace;
   traversal or an undeclared command is refused.
3. The Agent produces an inspectable plan before the first mutation.
4. The Harness records the actual change set separately from the proposed plan.
5. Execution uses declared commands and bounded resources; generated code is not
   executed through an ungoverned shell path.
6. Golden or property-based validation rejects a deliberately incorrect first
   implementation.
7. The structured validator failure is the input to a bounded repair iteration.
8. A repaired implementation passes the new case and a committed regression
   corpus.
9. Exceeding the iteration, time or command budget returns a structured failure
   or `needs_input`, never an unbounded loop.
10. Completion includes the change set, produced artifact, exact validation
    commands, outcomes, Skill versions and execution trace.
11. No change is committed, pushed or published automatically by the E2E.

### Required negative demonstrations

- A path outside the workspace is refused.
- A validation command that was not declared cannot decide completion.
- A model's success statement with a failing golden comparison remains failed.
- A regression failure prevents completion even when the new example passes.

### Reproducible green path and phase gate

One committed parser/transformation fixture must demonstrate plan -> change ->
failure -> bounded repair -> regression -> validated result in CI. E2E-05
implementation begins only after that command passes reproducibly.

## E2E-05 — Knowledge continuous evolution

### User scenario

A user asks a question through the Personal Agent and receives a cited Knowledge
answer. The user reports that the answer is incomplete. The Agent captures the
question, answer, citations, feedback and expected information as a standardized
improvement request. An approved change creates a Knowledge candidate, adds the
question to the domain evaluation set, runs regressions and publishes a new
version after domain-owner review.

### Automated acceptance criteria

1. The initial answer cites the Raw evidence from which every relevant claim was
   derived.
2. Feedback is linked to the exact Knowledge asset/version, answer, trace and
   cited passages.
3. The Agent creates a structured improvement request with reproduction and
   acceptance criteria; it does not mutate published Knowledge directly.
4. Raw source evidence remains byte-for-byte unchanged throughout the change.
5. Curation decisions and rejected claims remain persisted so re-ingestion cannot
   silently restore them.
6. The user question becomes a new evaluation case with an expected grounded
   answer or required facts.
7. The candidate passes both the new case and the existing domain regression set.
8. A domain owner approval is separate from technical validation and publication.
9. Publishing creates a new version; the previous version remains identifiable
   and usable for rollback.
10. Querying the new version produces the corrected cited answer.

### Required negative demonstrations

- Unsupported content without Raw evidence cannot become a grounded answer.
- User feedback alone cannot change published Knowledge.
- Passing the new question while regressing an existing question blocks publish.
- Re-ingestion cannot reintroduce a claim covered by a persisted human decision.

### Reproducible green path and phase gate

A committed miniature vault must demonstrate question -> feedback -> improvement
request -> candidate -> regression -> approval -> versioned republish -> improved
answer without changing Raw. E2E-04 begins only after this passes in CI.

## E2E-04 — Software continuous evolution

### User scenario

A user reports through the Personal Agent that a published Software capability
fails on a supplied example. The platform identifies its external repository and
version, produces a reproducible improvement request, obtains owner approval,
uses the Coding Harness to prepare a validated change and presents a reviewable
PR/MR candidate. Human review and the source-control/release process remain the
authority for merge and release. The Share Platform then represents the new
Software version.

### Automated acceptance criteria

1. A `Software` asset identifies owner, version, external repository/revision,
   interfaces, compatibility and release metadata without copying its source
   into the Registry.
2. The issue records expected/actual behavior, evidence, example input,
   reproduction environment and acceptance criteria.
3. Routing to the repository and owner is derived from the Software asset; the
   user need not supply repository details.
4. Business approval to pursue the change is distinct from technical execution
   policy and later source-control review.
5. The Harness reproduces the failure before changing code.
6. The resulting change passes the issue acceptance case and repository
   regression suite.
7. Output is a reviewable change set and PR/MR preparation artifact. CI uses an
   inert source-control adapter and performs no external Git write.
8. A failed validation cannot produce a release-ready result.
9. Merge, release and republish require explicit human-controlled transitions.
10. The new platform version links to release evidence and preserves rollback to
    the previous version.

### Required negative demonstrations

- An unreproduced issue cannot be marked fixed.
- Harness completion cannot merge or release the change.
- A repository regression blocks the candidate.
- Publishing Software metadata does not authorize running the Software.

### Reproducible green path and phase gate

A local fixture repository and inert PR adapter must demonstrate report -> route
-> reproduce -> approved development -> change -> regression -> reviewable
candidate -> simulated release metadata. E2E-01 begins only after it passes.

## E2E-01 — Physical DUT and chipset engineering capability

### User scenario

An engineer asks the Personal Agent to add or modify a bounded device/chipset
control behavior in an existing workspace. The Agent loads the exact vendor/domain
Skill, changes the implementation, validates pure and simulated behavior, then
runs an explicitly approved physical validation through an enrolled Bridge with
the required DUT or instrument. The engineer receives the implementation and
evidence that the real device behaved as expected.

### Automated acceptance criteria

1. Vendor-specific procedures live in versioned Skills, not hardcoded in the
   core Agent or Harness.
2. Device and instrument operations are typed capabilities with explicit input,
   output, side-effect, permission, approval and dependency contracts.
3. CI executes the same high-level case through a simulator/recording adapter and
   cannot reach physical hardware.
4. The Harness demonstrates workspace understanding, a planned change, test
   execution, a failing case, bounded repair and simulated regression.
5. An unauthorized, wrong-device or unavailable-device request is refused before
   any physical command runs.
6. Physical execution occurs only on an enrolled Bridge whose declared local
   capabilities match the request.
7. Company-workstation ownership and shared-test-workstation virtual-member rules
   remain enforced for the real run.
8. The production-like result records Bridge, device, firmware, instrument,
   workspace revision, Skill version, commands, measurements and validator
   outcome without credentials.
9. A hardware validator, measurement limit or explicit observed state decides
   success; the model cannot grade its own device result.
10. Human review accepts the implementation and physical evidence before the
    capability or Skill is republished.

### Required negative demonstrations

- CI cannot connect to a DUT even if a model requests it.
- A Skill cannot grant device permission.
- Simulated success alone cannot satisfy the physical production-like gate.
- A measurement outside the declared limit remains failed regardless of the
  Agent's explanation.

### Reproducible green path

The automated simulator path must pass in CI. The full product acceptance then
requires a separately documented run on an enrolled company or shared-test
Bridge with retained, reviewable hardware evidence. E2E-01 is complete only when
both layers pass.

## Product milestone completion

The initial product milestone is complete when all five E2Es pass in the required
order, their green-path commands and evidence are recorded, and the final
architecture documentation describes the implementation that was actually
validated. Passing lower-level unit tests, having the relevant classes, or
demonstrating only a model conversation does not satisfy an E2E.
