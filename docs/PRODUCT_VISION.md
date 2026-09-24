# Agentic Engineering Platform — Product Vision

Status: product-level design constraint. This document defines product intent
and priorities. It does not replace `ARCHITECTURE.md` or authorize an
architecture change by itself.

## 1. Vision

The platform is a shared environment where people's working Skills,
organizational Knowledge, deterministic Workflows and internal Software improve
through everyday use. Every team member has a Personal Agent that helps perform
work, reuse organizational capabilities, report problems and contribute
improvements without requiring the user to understand repositories, ownership,
issue formats, implementation agents or deployment details.

> Everyday work continuously improves the organization's shared capabilities.

```text
Use -> Feedback -> Standardize -> Develop / Improve -> Validate
    -> Review / Approve -> Republish -> Reuse -> Use
```

## 2. Product model

```text
People
  -> Personal Agent
  -> Continuous Evolution Engine + human governance
  -> Share Platform: Skills | Workflows | Knowledge | Software
  -> better versioned capabilities
  -> People
```

The Personal Agent is the primary interface. The platform coordinates where an
asset lives, who owns it, how an issue is structured, which worker implements a
change and how the result is deployed.

## 3. Personal Agent

The initial Personal Agent targets reliable bounded engineering and business
automation tasks, including device control, small engineering utilities, log
parsing, report generation, test-plan and data conversion, Excel processing,
web-data extraction, existing-system integration and SOP-to-Workflow creation.

The intended experience is: describe a bounded task, supply its inputs, and
receive a working result with external validation evidence.

## 4. V1 benchmarks

### 4.1 Device and chipset development

Representative tasks include Qualcomm, MediaTek, Broadcom and Realtek DUT
control, instrument integration and small RF automation utilities. The Agent
must understand an existing workspace, load domain Skills, modify or generate
code, execute it through an authorized Bridge, observe failures, repair the
implementation and validate the result. Vendor knowledge belongs in reusable
Skills, not in the core Harness.

### 4.2 SOP to deterministic Workflow

A user supplies a known business or engineering SOP such as downloading data,
processing and merging Excel files, generating a report and uploading or
delivering the result. Reasoning may create or modify a Workflow. Once reviewed,
validated and published, normal execution is deterministic.

> Reasoning creates the Workflow. Deterministic execution runs the Workflow.

### 4.3 Parser and transformation development

Representative tasks include Test Plan A to Test Plan B, raw log to structured
data, structured data to report, Excel schema conversion, CSV/XML/JSON
transformation and result extraction. The Harness executes representative
inputs, compares outputs with explicit expectations and repairs failures within
a bounded loop.

These three categories are the V1 acceptance benchmarks for the Coding Harness.

## 5. Coding Harness

The Harness is designed backward from the V1 benchmarks:

```text
Requirement -> Workspace understanding -> Plan -> Code change
            -> Execution -> Validation -> Error analysis -> Repair
            -> Re-execution -> Validated result
```

It needs workspace and dependency understanding, scoped file modification,
controlled shell and tool execution, Git integration, tests, structured errors,
bounded repair, regression validation, exact Skill versions and human
escalation. The Harness must not accept a model's claim of completion as proof;
declared acceptance checks and external evidence determine completion.

## 6. Shared capability types

- **Skills** explain how to perform work. They carry evolving procedures,
  strategies, domain knowledge, constraints, examples and tool guidance. They
  require ownership, versioning, review, publication, discovery, evaluation and
  improvement.
- **Workflows** are defined, validated procedures. Reasoning can create or
  change them; routine execution should be deterministic.
- **Knowledge** is curated organizational context with provenance. Real
  questions and feedback should improve both content and its evaluation set.
- **Software** is a maintained internal product or tool. Source remains in the
  appropriate GitHub or GitLab repository. The Share Platform records the
  capability, metadata, ownership, versions, interfaces and integration points.

## 7. One governed evolution mechanism

All four asset types share this lifecycle:

```text
Shared capability -> actual use -> feedback / problem / idea
  -> Personal Agent understands, clarifies, classifies and gathers evidence
  -> standardized Improvement Request -> governance / triage
  -> approved automated development -> test -> validation -> regression
  -> human review and approval -> publish -> improved shared capability
```

Feedback never changes a production capability directly. It becomes a
structured request that can include the target capability and version, expected
and actual behavior, evidence, example input, reproduction environment, expected
output and acceptance criteria. The user does not need to know the responsible
repository or owner.

For Software, the approved path produces a reviewed PR/MR and release. For
Knowledge, real questions and feedback become an evaluation corpus before a new
Knowledge version is published. For Skills, domain changes such as a new chipset
require real DUT or instrument validation and regression evidence.

## 8. Human and Agent responsibilities

Humans own business intent, domain correctness, product direction, approval,
governance, security decisions, exceptional cases and final responsibility.
Agents collect information, classify and route work, create issues, implement
approved changes, run tests and regressions, prepare documentation and publishing
artifacts, and coordinate routine steps.

> Humans decide what should happen and whether it is acceptable. Agents automate
> how approved work gets completed.

## 9. Share Platform and flywheel

The Share Platform is the discovery and governance surface for Skills,
Workflows, Knowledge and Software. It does not need to physically store every
asset. In particular, Software source remains in source control.

```text
Use -> real work -> problem or idea -> Agent capture
    -> standardized request -> human governance -> Agent development
    -> automated validation -> human approval -> republish
    -> better capability -> more use
```

This flywheel applies across engineering, application engineering, product,
finance and operations. Shared capability value grows through both use and
contribution.

## 10. Product principles

1. **Useful Agent first.** The first milestone is a reliable Personal Agent and
   Harness that completes the V1 benchmarks.
2. **Bounded autonomy.** Start with clear inputs, outputs, tools and acceptance
   criteria.
3. **Validation over confidence.** Executable evidence decides completion.
4. **Separate reasoning from deterministic execution.** Use reasoning to
   understand, plan, create and adapt; use deterministic execution for stable
   production Workflows.
5. **Make knowledge reusable.** Useful experience becomes a Skill, Workflow,
   Knowledge asset or Software capability.
6. **Make feedback actionable.** Convert it into reproducible, testable requests.
7. **Govern improvement.** Require review, validation, approval, versioning and
   publishing before production change.
8. **Let real usage drive evolution.** Questions, failures and feedback become
   evaluation evidence.
9. **Keep human judgment central.** Automation reduces implementation and
   coordination cost while humans retain ownership.

## 11. Development priority

Do not implement the whole vision at once. First prove the Personal Engineering
Agent and Coding Harness against device/chipset development, SOP-to-Workflow and
parser/transformation development. Then add Skill and Workflow publishing,
capability discovery, Knowledge integration, feedback capture, standardized
issues, maintenance automation, continuous evaluation and the complete
Continuous Evolution Engine in measured slices.

## 12. Relationship to the architecture

Before changing architecture, read this document and `ARCHITECTURE.md`, inspect
the implementation, identify gaps and propose which components remain, extend,
are replaced or are introduced. Prefer incremental evolution, keep complexity
appropriate for the current team and prioritize the three V1 benchmarks. Large
architecture changes require review of an explicit proposal first.
