# Experience review: learning from use, under governance (design, for owner review)

Owner request, 2026-10-12. Hermes accumulates experience with conditional memory and a
background Skill review. AEP should learn from use too, but through its own governance:
the system proposes, people decide, every change is versioned, measured and reversible.

## 1. What exists today and what is missing

| Already in AEP | Missing |
|---|---|
| Ratings on answers. They are stored locally and sent to the Shared Platform (`feedback_outbox`, DECISIONS 2026-10-08). | Nothing reads them back to improve anything. |
| Harness outcomes on every run: phase, failure code, retries. These are in `telemetry.sqlite`, with run kinds `conversation_turn`, `knowledge_query`, `coding_change` and `workflow_run`. | No job looks across runs for repeated failures. |
| Versioned improvement paths, each with approval: Skill candidates (`skill_authoring.py`), Workflow drafts (`chat_authoring.py`), Knowledge rule edits in sandboxes with a benchmark-gated push (`KNOWLEDGE_COLLAB.md`). | Nothing turns failures into proposals for these paths. |
| The Skill assistant, which proposes a whole rule file as a diff for a person to save. | It only works when a person asks. |

Cross-session learned memory was deferred by the owner (DECISIONS, context controls).
This design keeps that: what is learned lands in versioned assets (Skills, vault rules,
question sets, Workflows), never in a hidden memory store that changes prompts unseen.

## 2. Principles

1. **Propose, never apply.** A review produces proposals. Nothing changes in a running
   system until a person accepts it, and then it goes through the asset's normal path
   (sandbox push, Skill candidate, Workflow revision).
2. **Evidence first.** Every proposal names the cases it comes from: question, answer,
   trace, failure code, rating and reason. A proposal without cases is not shown.
3. **Measured before it counts.** An accepted change passes its path's gate:
   - question-set benchmark and push gate for vault rules;
   - a knowledge_v1 or coding_v1 run for platform Skills;
   - output checks for Workflows.
4. **Scoped.** Proposals respect the authoring limits that already exist. A proposal
   cannot grant a capability, add a script tool or widen a Skill beyond what a person
   could author.
5. **Local by default.** Conversation text stays on the Host. The review model is the
   company endpoint that already answers the questions.

## 3. Signals: what becomes an experience case

| Signal | Source | Example |
|---|---|---|
| Negative rating, with reason | local feedback | 👎 "漏了 FSWX" |
| Harness gave up | telemetry: `needs_input`, `failed`, retries exhausted | Knowledge `knowledge_not_validated`, coding repair budget used up |
| Evidence gap | Knowledge `knowledge_insufficient_evidence` | the vault lacks a product-option mapping |
| Benchmark or question-set failure | benchmark telemetry, push records | a must-mention term missing; a regression that blocked a push |
| Workflow failure | Workflow journal and output checks | a declared output file missing |

Each case is stored in a local `experience_cases` table:

- id, domain, signal, time;
- the question or task and a short answer excerpt;
- trace and run references;
- the Skill and rule versions in force;
- the failure code, and the rating and reason if any.

Cases are grouped by domain, governing rule and failure code, so ten failures with one
cause become one proposal.

## 4. The review job

- **When:** a native Host schedule (the schedule loop, not n8n). Default nightly, and
  only when there are new cases since the last review. It can also be run by hand from
  Agent Web.
- **What it reads, per group of cases:**
  - the cases themselves;
  - the rule files that governed them: the vault's `ask-*` / `ingest-*` skills, and the
    platform Skill's instructions and procedure;
  - for Knowledge, the evidence the answer had.
- **What the model returns** (a structured contract):
  1. **Cause**, one of:
     - `rule_missing` — no rule covers the situation;
     - `rule_unclear` — a rule exists but is ambiguous;
     - `retrieval_missed` — the evidence exists but was not found;
     - `data_missing` — the knowledge base lacks the information;
     - `model_error` — the model ignored a clear rule;
     - `harness_defect` — a bug in the platform.
  2. **Diagnosis:** two or three sentences that cite the cases.
  3. **Proposal**, depending on the cause:
     - a complete revised rule file, shown as a diff;
     - a list of missing knowledge (what to add, and to which drop folder);
     - a test question with must-mention terms (left blank for an expert to fill, never
       invented from the model's own knowledge);
     - an issue note.
  4. **Confidence**, and what would confirm the diagnosis.
- **Limits:** a cap on groups per run, a cap on model calls, and no re-proposing what a
  person already rejected for the same cases.

## 5. Where proposals go

| Cause | Route | Who decides |
|---|---|---|
| Vault rule (`ask-*`, `ingest-*`) | A **review sandbox** is opened from the project vault with the proposed rule edit. The domain owner compares it, edits it (the Skill assistant can help), runs the benchmark and pushes. The push gate applies. | Domain owner (maintainers) |
| Missing knowledge | Added to a **gap list** per category on the Knowledge page, with the questions that needed it. | Domain owner adds sources to `drop/<category>` |
| Missing test question | Drafted into the sandbox's `checks/questions/<folder>/`, terms left for the expert. | Domain owner |
| Platform Knowledge Skill (procedure, answer guidance) | A **Skill candidate** through the existing candidate path. It is installed only after approval and a benchmark run. | Owner |
| Workflow | A **Workflow revision draft** through the conversation authoring path. Revisions that drop steps need explicit acknowledgement. | Workflow owner |
| Harness defect, model error | An **issue note** in the review list. No automatic change. | Engineering |

## 6. The Reviews page

A "Reviews" section in Agent Web, also linked from the Knowledge tab. Each proposal shows:

- the cause, the diagnosis, and the evidence cases (each case opens the question, the
  answer and the trace);
- the proposed change as a diff, or the gap and test items;
- actions:
  - **Open in sandbox / candidate** — goes to the normal path;
  - **Reject** — the reason is recorded so it is not proposed again;
  - **Snooze.**

  *As built (labels in `web_page.py`):* the accept button names its route: "Accept:
  open a review sandbox" (rule change), "Accept: draft it in a review sandbox" (test
  question), "Accept: add to the gap list" (missing knowledge), "Accept: track as an
  issue" (platform issue). Then **Reject** (asks for a reason, required) and
  **Snooze 7 days**. An accepted proposal offers "Open in Knowledge" (when it went to
  a sandbox), "Mark done" and "Reject"; a rejected or done one offers "Reopen". The
  page tabs are "To decide", "Accepted", "Snoozed" and "Rejected or done". Platform
  Skill candidates and Workflow revision drafts (E4 routes) are not built: proposal
  kinds are only `rule_edit`, `knowledge_gap`, `test_question` and `issue`, and a rule
  edit that does not name a vault rule is tracked as an issue note
  (`host_runtime/review_routes.py`).

Each proposal is tracked as proposed, accepted, pushed or installed, measured, rejected,
or regressed. These counts show whether the review is worth its cost.

## 7. Telemetry

- A new run kind `experience_review`, with events `review.case_grouped`,
  `review.proposal_created`, `review.proposal_decided` and `review.change_measured`.
- Atlas can then show the loop end to end: failures, then proposals, then accepted
  changes and their benchmark effect.

## 8. What this does not do

- No automatic memory injected into prompts, and no per-user memory. That stays
  deferred until the owner asks for it.
- No self-modifying Skills, rules or Workflows. Every change waits for a person and
  passes its gate.
- No proposals built from the model's own knowledge. Missing facts become gap items for
  experts, not invented content.

## 9. Slices

| Slice | What | Done when |
|---|---|---|
| E1 | Case store and signal capture: ratings, harness outcomes, evidence gaps, benchmark failures | Cases appear for real failures; tests |
| E2 | Review job, report only: grouping, diagnosis, proposals stored, no routing | A nightly run on this Host's last week of cases, read by the owner |
| E3 | Vault-rule route: review sandbox with the proposed edit, gap list, draft test questions; Reviews page | A proposal accepted end to end through a sandbox push |
| E4 | Platform Skill and Workflow routes through existing candidates | One Skill candidate measured with knowledge_v1 |
| E5 | Telemetry and Atlas; proposal outcome tracking | The review loop visible in Atlas |
| E6 | Live trial for two weeks, then a decision on defaults | Owner review of the proposal quality |

## 10. Owner decisions (2026-10-12)

1. Signals: all of them (ratings, harness failures, evidence gaps, benchmark and
   question-set failures, Workflow failures).
2. Schedule: nightly, only when there are new cases; also runnable by hand.
3. Review model input: conversation excerpts may go to the company model endpoint,
   excerpts only, with secrets redacted.
4. Reviewers: domain owners review vault-rule proposals; the owner reviews platform
   Skill proposals.
5. Retention: a setting people can change on the page, default 30 days.

## 11. As built (E1-E2)

- Cases are harvested, not hooked: the review reads the Host's own records. Each case
  has a stable id, so a harvest can run again without creating duplicates. The sources
  are:
  - conversation answers that were down-rated, failed, needed input, or whose tool
    summary shows a failure code;
  - sandbox question-set benchmarks;
  - failed coding and Workflow runs in telemetry.
- Settings live in `<workspace>/experience-settings.json` (retention days, nightly on
  or off). Cases are in `<workspace>/experience.sqlite`. Review reports are in
  `<workspace>/experience-reviews/`.
