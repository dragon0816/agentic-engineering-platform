# sample-001: findings

**Setup.**
- Agent Web was started at 15:11 on build `967249b` with coding Skill 1.7.0. The repository commit recorded in `metadata.json` (`ab9cb3e`) has the same Knowledge and Gateway code.
- The installed Knowledge Skill is `company-agent/knowledge-query@1.4.0`, and the Vault is `engineering/rs-knowledge@1.0.1`.
- The run was graded with grader 1.0, then regraded with grader 1.1 (partial answers that have citations are reviewed). The reviewer re-reads every answer on a regrade.
- The reviewer verdicts were spot-checked (2 PASS, 2 FAIL) and are consistent with the cited passages.

This is the baseline before the 2026-10-07 Knowledge fixes:
- synthesis limit 4000 tokens with a retry on truncation;
- "say when Knowledge gave no answer";
- vault purpose 1.0.2;
- ownership step 1.

The fixes take effect at the next Agent Web restart, and sample-002 measures them.

## Result

**64 of 110 acceptable:** PASS 31, INSUFFICIENT_KNOWLEDGE 33. FAIL 38, SYSTEM_ERROR 8.

| Route | Questions | PASS | INSUFFICIENT | FAIL | SYSTEM_ERROR |
|---|---|---|---|---|---|
| direct: the Skill harness answered | 34 | **22** (8 of them partial answers) | 10 | 2 | 0 |
| tool: the conversation model called `knowledge__rs-knowledge` | 58 | 9 | 23 | 18 | 8 |
| none: Knowledge not used | 18 | 0 | 0 | 18 | 0 |

By question type, competitive questions passed 17 of 17. Application (0/16) and cross-domain (0/17) failed most.

## Causes, largest first

1. **The tool route answers far worse than the direct route** (16% PASS against 65%).
   - On the tool route the Knowledge call has no Skill procedure. That means raw-only citations, no facets, no wiki-first retrieval, and a synthesis limit of 800 tokens.
   - The conversation model then writes its own answer around thin evidence. As a result, 23 answers were INSUFFICIENT (`knowledge_insufficient_evidence`), and 18 were judged unsupported because detailed workflows came from general knowledge.
   - Whether a question goes direct or by tool depends on the Knowledge Skill's intent patterns.
2. **Knowledge not used** (18 questions, `EXECUTION_GAP`). The vault's purpose text (1.0.1) names spectrum and signal analyzers, signal generators and CMP180, but not oscilloscopes, VNAs, Wi‑Fi 7, radar or the five markets, although the Vault holds 38–142 files on each. Fix: purpose 1.0.2 (owner approved).
3. **Synthesis cut off** (8 questions, `knowledge_model_failed`). The tool route's 800-token limit truncated the reasoning model; an offline repro of Q0046 confirmed it. After each failure, the model answered from memory without saying so. Fixed in `8e25b8b` (4000 tokens, one retry, and the new prompt rule).
4. **The direct harness discards answers.** When retrieval covered a facet but the answer did not cite it, the harness replaces the whole answer with "The retrieved Raw evidence does not validate the complete answer. Missing: …" (Q0071, Q0121). The "Raw" wording is wrong under the Skill's `wiki_primary` policy. A proposal is being prepared, for owner approval.

## Next

- sample-002 on the fixed build, to compare by route and status.
- **Proposal to the owner:** give the tool route the installed Knowledge Skill's procedure, or route Knowledge questions to the direct harness. Combine this with cause 4.
