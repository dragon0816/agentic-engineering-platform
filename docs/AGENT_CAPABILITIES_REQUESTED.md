# What the owner wants the Agent to do

Stated by the owner on 2026-09-24. This file records the request and what it
costs against the platform as it stands today; it decides nothing. Each item
that becomes work gets a slice in `docs/TASKS.md` and, where it changes the
architecture, an amendment to `docs/ARCHITECTURE.md` **before** any code.

It is written down here because a requirement that lives only in a
conversation is a requirement the next person cannot read.

## The five capabilities asked for

1. **Coding, with a harness**, in three directions:
   - given a workflow's SOP, produce a Workflow that runs on this platform;
   - log reformatting and test-plan conversion;
   - chipset DUT program development, with engineers supplying a Skill per
     chipset.
2. **Running Workflows and driving the computer's own tools** (email, Excel).
3. **Answering technical, market and product questions from the Knowledge
   wiki.**
4. **Several agents on one machine**, each configured with its own skills,
   model and memory.
5. **A web interface** to all of it (decided separately; being built).

## What already exists, honestly

Two of these are largely built already, and saying so matters more than
restating the request.

**(2) Running Workflows and driving Excel and Outlook is built.** It is what
the weekly report does today: a typed Workflow of steps, each a capability
the Bridge policy authorizes per actor, over a real Excel through COM
(`integrations/excel_writer.py`) and a real Outlook through COM
(`integrations/outlook_draft.py`). The pattern generalises: another tool is
another adapter behind another protocol, and it costs no new architecture.

**(3) The Knowledge wiki exists but is wired to nothing.** `src/knowledge/`
is a full vault -- an immutable `drop/` and `raw/`, a writable `wiki/`, a
query layer that cites provenance, linting, conflict detection and
migration. No module under `host_runtime/`, `agent/`, `channels/` or
`capabilities/` imports it. Connecting it means writing knowledge capabilities
over the query layer and installing them like any other; that is ordinary
work inside the existing architecture, not a redesign.

**(1) and (4) are blocked on the same missing thing**, below.

## The gate: no model is configured on a company host

`build_gateway` constructs the router without one, and says so in its own
docstring: *"Routing is deterministic only: no model is configured on a
company host in this slice, so an unrecognized message is `needs_input`
rather than a guess."* `CompanyHostConfiguration` has no model, catalog,
alias or provider field at all.

So today the Agent matches commands and runs Workflows. It does not reason,
because nothing gave it anything to reason with.

Everything in (1) needs a model. So does the interesting half of (3) --
answering a question rather than retrieving a page. So does (4)'s per-agent
LLM. **Putting a model on a company host is the first slice of all of it.**

### It is a smaller gate than it looks

The owner said on 2026-09-24 that the team runs a LiteLLM gateway in front of
the company's internal LLM. That is the gateway Phase 5 already migrated
*from*, and the model layer built for it is complete and exercised in CI:

- `models/openai_compatible.py` speaks exactly what a LiteLLM proxy serves.
- `models/catalog.py` selects an endpoint by declared capability against a
  declared requirement, and returns a typed `Failure` naming what was missing
  rather than an exception from inside a request.
- `models/clients.py` wires a catalog to the host's credential resolver and
  transport, one client per alias.
- `models/proof.py` runs the whole chain in CI, and its sample catalog already
  carries a `company_reasoning` endpoint: `openai_compatible`, a company
  gateway URL, a credential named rather than held.

`docs/PHASE_5_MIGRATION.md` also already records how that gateway behaves,
including the one that cost the source a patch to LiteLLM itself: **a
streaming chunk with an empty `choices` list is normal and must be skipped,
not treated as an error.**

So what is actually missing is one slice of wiring:

1. A `models` field on `CompanyHostConfiguration` -- a catalog, and which
   alias routing uses. The credential needs nothing new: it resolves through
   the same host mapping `AEP_GITHUB_TOKEN` already uses.
2. `build_gateway` building `ModelClients` from it and passing a client to
   `RequestRouter`.

### The one thing for the owner to decide

`RequestRouter` takes `local_only=True` by default, and an endpoint's `local`
flag says where the model *runs*. A company-internal gateway runs inside the
company but not on this machine, so it is `local: false`, and routing will
refuse it until the host says `local_only: false`.

That should stay a visible line in the configuration rather than become a
default. It is the line that says an engineer's words leave this machine for
the company's gateway, and whether that is acceptable is not a decision this
repository should make silently.

What a model may *do* once it is there -- as opposed to read -- remains open,
and is the same question as the coding harness's, below.

## The order this implies

1. **A model on a company host.** Configuration, credential, catalog binding,
   and the offline answer. Until this exists, items 1 and 4 cannot start.
2. **Knowledge capabilities** over the existing vault. These are useful with
   or without a model: retrieval with citations is worth having on its own,
   and it is what a model would read from afterwards.
3. **SOP to Workflow.** The best-shaped of the three coding directions **by
   a distance**, and it should be first. Its output is a `WorkflowManifest`,
   which is a typed contract this repository already validates, runs and
   refuses. An agent that emits one is producing *data that is checked before
   anything happens*, not code that is run to find out. Everything the
   platform already does -- contract validation, capability grants, approval
   on side effects, the dry run -- applies to it unchanged.
4. **Log reformatting and test-plan conversion.** A transformation with a
   known input and a known output is the case where a model's work can be
   checked automatically, by running it and comparing. Decide deliberately
   whether the agent writes a transformation *or* performs one: the first is
   reviewable and reusable, the second is not.
5. **Chipset DUT development** last of the three. It is the one that ends in
   code that runs against instruments, so it is the one where being wrong is
   expensive, and it depends on a Skill format for chipset knowledge that
   engineers have not been asked to write yet.
6. **Several agents on one machine**, once there is more than one thing for
   them to be.

## What (1) and (4) need decided in the architecture first

`docs/ARCHITECTURE.md` already anticipates part of this and not the rest.

It **has**: `AgentProfile` (`src/agent/contracts.py`), carrying `skills`,
`allowed_capabilities`, `knowledge`, `model_requirements`, `may_delegate_to`
and `policy_constraints`; the statement that the platform is *"one agent
runtime architecture with N agent profiles"* (ARCHITECTURE.md:337); a worked
example naming a `coding` profile beside `engineering` (:377-398); and
delegation between agents (:400-405). The `coding` agent the owner asked for
is a profile the architecture already named as an extension point.

It **does not have**, and these must be written before code:

- **Anything instantiating an `AgentProfile`.** `agents/engineering.json`
  says outright: *"no runtime is instantiated"*. The contract is imported
  nowhere in `src/` outside its own module.
- **Several agents on one machine.** The architecture says one Personal
  Engineering Agent per engineer per plane (:210, :253), one resident Agent
  that every ingress converges on (:308), and every machine bound to exactly
  one member (:301). Several agents on one Bridge is not forbidden; it is
  absent. It needs an agent identity, and it needs an answer to how skills
  and grants narrow per agent, because grants are per *actor* today and a
  machine has one member.
- **Per-agent memory.** No document associates memory with an agent. A
  profile has a `knowledge` scope and nothing reads it.
- **What a coding harness may do.** This is the largest unanswered question
  by far. Every side effect in this repository is a declared capability with
  a policy and an approval; "write files and run commands" is not one of
  those and must not be smuggled in as one. Whether an agent may edit a
  repository, what it may run, in what directory, and what it needs an
  approval for, is a policy decision the owner has to make before there is
  anything to build.
