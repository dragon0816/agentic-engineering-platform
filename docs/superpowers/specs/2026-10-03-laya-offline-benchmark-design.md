# Laya offline decision benchmark

Approved by the owner on 2026-10-03. This evaluates
[`NandhaKishorM/laya`](https://github.com/NandhaKishorM/laya), the local
System One decision model, rather than the unrelated notification application
with the same name. It replaces the pending TypeSafe JEV comparison test; it
does not activate an accelerator in Agent Web.

## Boundary

Use the existing pinned 16-case PUBLIC synthetic decision corpus and scoring
contract. Run Laya in-process on the computer doing the measurement, with
Hugging Face and Transformers in offline mode after a checkpoint has been
downloaded separately. The benchmark imports Laya lazily, so AEP does not gain
a runtime dependency. It never reads conversations, installed assets,
RS_Knowledge, credentials, or a network endpoint. The model makes no execution
or authorization decision.

## Mapping and evidence

Every case becomes one Laya `choice` question over its declared candidate
labels. A `skill_selection` question also has a `preserve_catalog` choice;
that choice maps to the complete installed-candidate set for the catalog case.
The question instructions and label descriptions are fixed before inference.
Malformed, truncated, unknown or low-confidence answers become abstentions; exceptions
record only a generic failure code. Measure all four decision types against
the unchanged AEP `NONE` baseline with the existing exact-match, coverage,
latency and confidence scoring. Record Laya package version, checkpoint name
and loaded revision alongside aggregate metrics, without prompt text or
individual answers.

The initial checkpoint is English because the reviewed corpus is English.
Keep `max_loaded=1`; do not preload other checkpoints. One trial checks the
wire and mapping; repeated warm trials are needed before a performance claim.
Model warm-up and download time are excluded from per-case latency and must be
reported separately. No threshold for production activation is inferred from
this small synthetic corpus.

## Execution location

The current workstation has 31.13 GiB installed RAM and 14 logical CPUs, but
only about 2 GiB available during the 2026-10-03 check. Laya's English
checkpoint has 421 million parameters. Running its full PyTorch checkpoint
under this load is likely to page heavily, so this workstation prepares and
verifies the benchmark mapping only. The owner will run full inference on a
machine with more free memory. A separate optional environment installs pinned
`laya==0.3.24`; AEP's normal environment and Agent Web stay unchanged.
