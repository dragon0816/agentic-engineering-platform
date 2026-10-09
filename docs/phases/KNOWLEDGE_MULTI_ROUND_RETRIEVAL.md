# Knowledge multi-round retrieval (design, 2026-10-10)

Owner request (2026-10-10): after Skill 1.8.0 fixed overreach but not coverage,
try model-driven multi-round retrieval, as Claude Code and NousResearch
hermes-agent search.

## Problem

knowledge_v1 core-003: on the 22 questions the Vault can answer, answers cover
about 28% of the Claude Code reference key points. Retrieval is the limit: one
pass (question + bilingual rewrite queries, BM25 over Wiki sections) finds 26%
of the files the references cite. Claude Code reached them by searching,
reading what came back, and searching again with the words the Vault uses,
often Traditional Chinese page names.

## Design

Only the evidence-gathering step of the wiki-primary Knowledge capability
changes. Synthesis, citation rules, Host checks and the Harness state machine
stay the same. The Bridge still runs the capability; the model never reads
files directly.

1. **Round 0.** The current bilingual retrieval: the question, rewrite queries
   and facet queries.
2. **Search results, not passages.** Each round, the Host shows the model a
   compact list of the pages its searches found: the page title, the matching
   section heading, and a short snippet. This is the "grep result" Claude Code
   reads before opening a file.
3. **Model decides.** The Gateway model replies with JSON:
   `{"relevant_pages": [titles], "queries": [new searches], "done": bool}`.
   It may only name pages that were shown, and its queries are keywords.
4. **More rounds.** The Host runs the new queries and shows only the new pages.
   It stops when the model says `done`, the queries are empty, or the round
   budget is spent.
5. **Evidence set.** The pages the model marked relevant lead, each with up to
   three of its best sections for the question. The round-0 passages fill the
   rest, up to the same 36-section and 40,000-character limits.

## Bounds

- Round budget: the Skill sets it (`retrieval_rounds`, 0-3). 0 keeps today's
  behaviour, and Skill 1.9.0 would turn it on.
- At most 6 queries per round, 30 pages shown per round, 12 relevant pages.
- A failed or unparseable planner reply ends the loop, and the evidence
  gathered so far is used. Retrieval never fails because of the planner.
- Every planner call is an `llm.completed` telemetry event like the others.

## What does not change

- The answer must cite passages from the evidence set, and the Host checks
  every citation (claim overlap, facet coverage, subject).
- The model cannot add text to the evidence. It only chooses which Vault
  pages to read.
- The PUBLIC rule is unchanged. The planner is the company Gateway model,
  which already receives these passages for synthesis.

## Measurement

1. Offline first: recall of the reference files over the 22 answerable core
   questions, against 0.26 today. Implement only if it rises clearly.
2. Then `runs/core-004` with `reference_grade.py`, against core-003. Compare
   PASS/FAIL, coverage, contradictions and latency. Each round adds about one
   model call.
