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
