# Laya acceleration: where a fast decision can save time

Status: **design only, on hold** (owner, 2026-10-13). Collect one week of shadow
data, review it with the owner, then decide what (if anything) is built. Nothing in
this document is implemented yet.

Owner goal: faster answers **without losing accuracy**.

## 1. Why the current placement cannot speed things up

Laya is wired at `skill_selection` (`src/agent/gateway.py`, `DecisionService` with
`decision_accelerator` in host.json, shadow mode, threshold 0.9, at most 3 tools). It
narrows the tool list *before* the large model runs; the model still runs the whole
loop (read, choose a tool, call it, write the answer). The saving is a few hundred
prompt tokens for six Skills, while every turn waits 0.3-0.5 s for Laya (up to the
1.5 s timeout when it is down). A wrongly narrowed list hides the right tool.

A fast decision speeds the Agent up only where it **replaces** a large-model call or a
retrieval round.

## 2. Candidate decision points

`ACCELERABLE_TYPES` (`src/agent/decisions.py`) already allows four types. Final
execution routing, completion, planning and result evaluation stay with the model
(DECISIONS 2026-10-02).

| # | Decision | What a confident answer would replace | Expected saving | Cost of a wrong accept |
|---|---|---|---|---|
| A | `skill_selection` (today) | nothing; shortens the tool list | very small | right tool hidden |
| B | `intent_classification`: "is this a Knowledge question?" | the model's first tool-choosing turn; go straight to the Knowledge harness, as `_skill_intended_knowledge` already does for the rule-based case | one LLM round trip (seconds) per Knowledge question | a task answered as a question |
| C | `retrieval_routing`: "does this question need more search rounds?" (and, later, which domain) | the `_plan` model calls of `search_rounds` when the first retrieval already suffices | the largest; multi-round retrieval added about 60 s median (core-004) | thinner evidence, lower coverage |
| D | `failure_classification`: retry, ask the person, or give up after a tool failure | one model turn after a failure | small, failures only | a pointless retry or an early stop |

B changes which harness runs and is an architecture decision for the owner (Laya
would become authoritative for routing between Knowledge and the general loop). It
must keep a safety net: if the Knowledge harness returns `insufficient` or fails, the
turn falls back to the full loop.

## 3. Thresholds: per decision, from data, on the right number

- **Measure the right confidence.** Today's `confidence` is the summed probability of
  the kept list (0.956 = 0.68 + 0.17 + 0.10). For a decision Laya takes alone, use the
  top choice's probability and its margin over the second. On 2026-10-13 one turn had
  `confidence` 0.92 while its top choice (0.52) was wrong.
- **One threshold per decision point**, because calibration and the cost of a wrong
  accept differ (C can fall back cheaply; B gives a wrong answer).
- **Acceptance rule ("no accuracy loss"):** the lowest threshold at which at least 100
  accepted decisions were recorded and the 95 % upper bound of their error rate is
  below 1 %. Below that, the decision stays in shadow.

Evidence so far is too thin to set any threshold: 64 answered shadow decisions since
2026-10-05 (1,492 tunnel errors); at 0.9, 3 of 15 narrowed tool-using turns would have
hidden the model's tool. The 2026-10-05 benchmark admitted 100 % correct at 0.9 but
only 11 % of cases.

## 4. Data collection week (shadow only)

1. Keep the Laya connection up (the owner chooses: the loopback relay, plaintext on
   the LAN, or a fixed SSH tunnel) and `mode: shadow`. Nothing reaches the person.
2. Record for each shadow decision: top probability, margin, kept list, latency and
   what the model actually did (already logged for A).
3. Proposed additions for review (not built): shadow records for B and C, with the
   outcome the full path produced (did the turn use the Knowledge tool; did round 2
   add a cited page), so each threshold can be read off the log.
4. Probes must never use requests that run Workflows; installed Skill Workflows run
   without a per-run approval (incident 2026-10-13, `docs/JEV_ADAPTER_READINESS.md`).

## 5. Decision after the week

Report per decision point: decisions answered, accept rate and error bound per
threshold, seconds saved per accepted decision, added latency. The owner then decides
which points (if any) move to `active`, starting with the one that saves most at the
lowest risk.
