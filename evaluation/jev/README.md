# Bounded decision benchmark v1

`golden-v1.json` has 16 **PUBLIC, synthetic** cases: four each for intent,
installed Skill candidates, retrieval routing and failure classification.
The labels are a reviewable benchmark target, not an execution permission,
data classification decision or real customer corpus. No case contains a
company document, credential or private endpoint.

From an editable AEP environment, run:

```powershell
$env:PYTHONPATH = 'src'
& .venv/Scripts/python.exe -m evaluation.jev_benchmark --cases evaluation/jev/golden-v1.json
```

This default mode invokes the real `NONE` Skill candidate baseline, which
returns **all installed commands** in catalog order and makes no model call.
It does not invent baseline implementations for intent, retrieval or failure
classification. Those types appear with zero coverage and unavailable counts.
The current Skill baseline has 4/4 coverage and 1/4 exact-match accuracy on
this intentionally small corpus because three cases have one relevant command
but the baseline preserves all three. Its latency values are measured locally
per run; do not copy them into a performance claim. Rule-only cost is exactly
zero, while unknown provider cost remains `null`, never assumed zero.

For another provider, save a JSON array of observations and pass
`--observations observations.json`. An observation identifies `case_id`,
`provider_id`, optional nonnegative `trial`, `status` (`answered`, `abstained`
or `unavailable`), `selected` labels, and optional measured `confidence`,
`latency_ms`, `fallback_reason` and `cost_usd`. Example:

```json
[{"case_id":"skill-file","provider_id":"candidate","trial":0,"status":"answered","selected":["read-file"],"confidence":0.93,"latency_ms":18.4,"cost_usd":null}]
```

Supply one observation per case and trial. Missing observations reduce
coverage and exact accuracy; unknown cases, duplicate observations, invented
labels and multi-label classifications fail validation. A single observation
file can hold multiple providers and repeated trials. `p50` and `p95` use the
nearest-rank method over measured, available samples. Confidence Brier score
uses answered samples with a known confidence. `total_cost_usd` is `null` if
any available sample lacks cost evidence. Reports contain only case counts,
provider IDs, decision types and metrics, never request text.

This is a benchmark substrate, not evidence that an optional JEV provider is
ready for live use. A benchmark candidate still requires the same full-payload
egress authorization, PUBLIC-only data policy, output validation and
approval boundary as the product runtime. Separate reviewer labels and a
larger representative corpus are required before a provider can be selected
for production traffic.

## Local Laya comparison

The owner chose [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya)
0.3.24 for the next comparison instead of a live TypeSafe request. The
`evaluation.laya_offline` diagnostic uses this same pinned PUBLIC corpus for
all four decision types. It imports Laya only when explicitly run and forces
Hugging Face offline mode before that import. It does not connect Laya to the
Agent Web, read RS_Knowledge, or change the `NONE` baseline. The synthetic
cases are too small to justify production routing on their own.

On a computer with enough free memory, create an isolated Python environment
inside a checkout of this repository:

```powershell
py -3.12 -m venv .scratch/laya-venv
$LayaPython = Join-Path (Resolve-Path .scratch/laya-venv) 'Scripts/python.exe'
& $LayaPython -m pip install -e . 'laya==0.3.24'
```

The English checkpoint has about 421 million parameters. Its first use needs
an Internet connection to download from Hugging Face; prepare its cache once
outside the timed benchmark:

```powershell
& $LayaPython -c 'from laya import Router; Router(max_loaded=1, device="cpu").predict("A synthetic sample request", {"selection": {"type": "choice", "instructions": "Choose a sample label", "criteria": {"a": "alpha", "b": "beta"}}}, model="english")'
```

Then disconnect the model download path and run the local diagnostic. The
command enforces offline mode itself, warms the checkpoint separately from
measured requests, and records its loaded revision, package version,
per-decision aggregate scores, and warm-up duration:

```powershell
& $LayaPython -m evaluation.laya_offline --trials 3 --device cpu
```

Use `--device cuda` only on a host with an appropriate GPU and PyTorch build.
`--min-confidence` is optional; leave it unset for raw accuracy, then try
explicit thresholds as separate runs. Laya's `answer_confidence`, rather than
its entropy-based `confidence`, is used for gating and calibration. The report
does not include prompt text or individual answers. `known_cost_usd=0` means
no metered provider call; it does not include electricity or hardware cost.

The current development workstation has 31.13 GiB installed RAM but only about
2 GiB available at the time of assessment. A full 421-million-parameter
PyTorch run under that load could page and distort latency, so it is not a
useful performance baseline. The local mapping/schema tests can run here
without installing Laya or downloading a checkpoint.

An explicit TypeSafe diagnostic is available for this exact reviewed corpus:

```powershell
$env:AEP_JEV_API_KEY = ([System.Net.NetworkCredential]::new('', (Read-Host 'TypeSafe JEV API key' -AsSecureString))).Password
& .venv/Scripts/python.exe -m evaluation.jev_live --model jev-latest
```

It checks the corpus SHA-256 before reading the key and can send only its four
synthetic PUBLIC Skill cases to the fixed TypeSafe SystemOne endpoint. It does
not connect JEV to Agent Web or RS Knowledge. The key stays in the current
PowerShell process; do not paste it into `host.json` or a repository file.
TypeSafe's authenticated `/v1/models` gives the model name for your account.
Provider cost is reported as unknown until a verified price is available.
