# Handoff

Date: 2026-10-04 (Asia/Taipei). Branch: main. Goal: a six-layer harness shared by Knowledge Asking, Workflow/Task execution and Coding. The owner tests Knowledge in Agent Web first and will guide the next iteration from observed answers.

## Current slice

- The private `company-agent/knowledge-query@1.2.0` Skill has an optional typed Knowledge procedure for natural intent, requested facets, bounded search queries and direct-link terms. The shared Skill manifest carries this as opaque JSON; the common plan and runner contain no Knowledge-specific logic. Exact commands retain routing precedence, and Bridge authorization is unchanged. The published 1.0.0 Skill was not changed.
- Knowledge retrieval now shares a corpus snapshot across per-facet searches and retries only missing facets. The Knowledge adapter records Raw candidates and direct-link observations. The Host independently requires cited Raw support for each requested facet, a connected direct relationship for combined questions and a conservative lexical claim/source check. Incomplete evidence returns a visible `needs_input` gap. Lexical overlap does not prove semantic entailment or product-market fit.
- `evaluation/knowledge/scenarios-v1.json` covers all 15 nonempty combinations of market trend, product/option/spec, technical knowledge and competitor facets. Controlled tests cover supported, missing and misleading co-mention data. A read-only RS_Knowledge retrieval probe found candidate Raw for every facet but a connected direct-link graph for only 5/15 selected questions. The other 10 are retrieval gaps for these queries, not proof that the Vault lacks those facts. No Vault source was edited.
- The private 1.2.0 file is installed in `%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\workspace\assets\skills`; 1.1.0 was moved to that directory's `disabled` backup. The Agent Web process was restarted on `http://127.0.0.1:53583/` with `--open`. Its bearer URL is in ignored `.scratch/agent-web-guided.out.log`; never print or commit it. The existing Gateway key was read from the owner's already configured `.env` without displaying or changing it.
- Two authenticated Web conversation smoke turns completed. `CMP180` product specs returned `answered`, `harness.phase=validated`, `facet_status=covered`, `claim_status=supported`. A combined wireless-market/CMP180 question returned `needs_input` with missing `product_option_spec` and direct-link evidence. The owner still needs to judge answer quality in the Web UI.

## Verification

- Focused Knowledge evidence, scenario and Agent Web tests: 143 passed under system Temp.
- Ruff: `ruff check .` passed. Mypy: `mypy src tests` passed for 352 files.
- Broader non-browser pytest under a short system Temp path: 1,837 passed, 5 skipped. An earlier workspace `.scratch` run had two Windows file-operation failures; each passed independently under system Temp before the clean broad run. The independent browser test file was excluded; the Agent Web test file passed in the focused run.
- `python -m build --no-isolation` produced both sdist and wheel. `git diff --check` passed.
- Local live Web checks above demonstrate routing and evidence behavior, not complete factual correctness across all 15 Vault combinations.

## Next actions

1. Have the owner test representative standalone and combination questions in the restarted Agent Web. Inspect each failure by route, Skill procedure, data coverage, retrieval, model synthesis or Host validation. Adjust the Skill or adapter only after evidence; do not weaken the Host checks to force answers.
2. Complete G4 by wrapping one exact Workflow/Task and one bounded Coding run in the same plan/state/validation envelope. Preserve deterministic execution and Bridge permissions. Then complete G5 negative validation and G6 Web proof. See `docs/phases/HARNESS_6_LAYER_INCREMENTAL.md` and `docs/TASKS.md`.
3. At the next merge checkpoint, run the full suite using a short system Temp `--basetemp` to avoid Windows rename failures under workspace `.scratch`; run lint, mypy and the build. Record any browser-specific environment failures separately.

The owner's RS_Knowledge copy is at `C:\Users\Chi_L\AppData\Local\AEP\rs-k`; the Host config is `%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\host.json`. The local LiteLLM Gateway is at port 4000. No secret values belong in this file.
