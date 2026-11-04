# Why one source gives different card counts: measured

Status: measurement, 2026-11-04, by Claude Code (worker D). **Nothing here is built.** 31 calls to gpt-5.5 through the gateway, in a temp workspace, using copies of `market-intel`'s cards and of run `20a0b9376dd7`'s skill, profile and instructions. Raw per-run lists are in `.scratch/variance/` (git-ignored; they hold real report content).

## Results

**The model alone, with identical request bytes** (one body hash per chunk), 5 runs:

| `compute.md` chunk | Candidates per run | Card identities in every run / in any run | `SupplyLink` per run |
|---|---|---|---|
| 7 | 23, 25, 23, 24, 23 | 18 / 30 (60%) | 3 each |
| 12 (densest) | 31, 19, 30, 24, 23 | 15 / 39 (38%) | 16, 6, 16, 14, 10 |
| 5 | 12, 12, 13, 12, 12 | 11 / 14 (79%) | none |

Three things vary:

- **Which rows it covers,** on dense tables: 6 to 16 supply links from one table.
- **How it names a card:** `台積電→NVIDIA-晶圓代工` or `…-晶圓代工與CoWoS-L封裝`. Chunk 12 gave 22 names for 16 supplier-customer pairs; chunk 7, 5 names for 3.
- **Field values on cards every run named.** `summary`, `usage` and `scope` differ on every card. Among structured fields, 38 of 149 values differ on chunk 7 and 46 of 133 on chunk 12, led by `confidence`, then `period`, `product`, `not_confirmed` and `segment`.

Basis mix over the 5 runs (fact / inference / unknown): chunk 7, 787 / 486 / 47; chunk 12, 699 / 525 / 199; chunk 5, 416 / 260 / 37.

**What AEP changes: the known-cards list has the largest effect measured.** Chunk 7, empty list against the vault's list:

| Known cards | Candidates | `Ecosystem` | `RevenueFact` names |
|---|---|---|---|
| Vault's list | 23–25 | 3 | `台積電-2026 Q2-segment-晶圓代工`, the seeds' form |
| Empty | 39–45 | 18 | `台積電 2026 Q2 晶圓代工營收市占` |

So the list both removes candidates, since companies already known mostly get no card from this chunk, and teaches the naming form. It changes whenever cards are accepted, so a later run sends a different prompt even for the same source. A skill or profile revision also changes the prompt; not run. `extract.chunks` takes only the text and the limit, so it adds no variation on its own; not run separately.

**Temperature and seed reach the model.** `drop_params` does not remove them here: `temperature: 3` and `seed: "not-a-number"` both came back with the upstream's own error.

- **`temperature: 0` is refused:** only the default 1 is supported, so it is not an option on gpt-5.5.
- **`seed` is accepted and does not make it deterministic.** Three runs with one seed, identical bytes:

| Chunk | Candidates | Identities in every / any run | Same measure, any 3 of the 5 runs with no seed |
|---|---|---|---|
| 7 | 25, 24, 25 | 96% | 60%–96%, mean 73% |
| 12 | 24, 25, 27 | 56% | 41%–67%, mean 50% |

Counts on chunk 12 spread less (3, against 5–12), but 3 runs cannot show that is the seed. Treat it as unproven.

**The call path.** Extraction calls `model.generate` directly (`extract.extract_chunk`), with no Agent harness. Session B's conversation goes through the harness (`Gateway.converse`), and the extraction it triggers is the same direct call.

## Correction to an earlier finding

The supply-link rule was reported as fixing the table: 7 of 16 without it, 16 of 16 with it. That was one run each. With the rule in the prompt, five runs gave 6 to 16. It may help, but it does not guarantee anything.

## Fixes, ranked by this evidence

1. **Reuse an answer for an identical prompt** (hash of request body and model, kept per PC). Exact repeat, no cost, small. It only helps while the prompt is unchanged, so it needs fix 2 to survive a vault change. It does not improve a first run.
2. **Send only the known names the chunk mentions, and say a known company still gets its update.** This addresses the largest effect, and it shrinks the prompt. **Not tested:** needs a few calls before building.
3. **Match `SupplyLink` by supplier and customer, with product a value of the card.** On saved runs, chunk 7's identities go from 60% to about 90%, and the real run's roughly 32 repeats would merge. A pair with two real products would then share one card; the owner should decide.

**Not recommended from this data:**

- **A key for `RevenueFact` from company, period and layer.** It made chunk 5 worse, 79% to 42%, because the model's `period` itself varies.
- **Relying on a seed.** Cheap, but its effect is unproven.

**Not fixed by any of these:** which rows the model covers on a first run, chunk 12's 6 to 16. A real fix would read tables deterministically, or check coverage in a second pass. Both are larger work.

**Accepted cards do not change:** this variation is between runs. Once a person accepts a run, the cards stay as accepted.
