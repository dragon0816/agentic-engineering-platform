# Voice-to-Knowledge Phase 0 (isolated, mock only)

This directory is not an installed AEP capability. It imports no AEP runtime.
Design and acceptance: [six documents](../../docs/voice-to-knowledge/VOICE_PROGRESS.md), #234–239.

## Reproduce offline contract tests

From the repository root, Python 3.11+:

```sh
python -m venv /tmp/voice-tests
/tmp/voice-tests/bin/pip install pytest 'pydantic>=2.10,<3'
PYTHONPATH=.:src /tmp/voice-tests/bin/python -m pytest tests/test_voice_*.py -q
```

These tests use synthetic text/PCM and fake providers. They require no model, bot, STT service,
company data or credentials. They do not measure human speech accuracy.

## Real inference (currently blocked by artifact download policy)

Create a separate venv and install `requirements.lock` (tested Python 3.12/Linux).
Supply a licensed corpus and pre-downloaded CTranslate2 multilingual small/medium directory
from an authorized artifact source; the runner does not download or accept a model name as a URL.
Record the immutable upstream revision and all model file SHA256s (runner computes hashes).
Do not copy company audio into this environment. Model identity/revision is operator-attested;
file hashes detect byte changes, they do not verify an upstream signature.

```sh
python -m venv /tmp/voice-benchmark
/tmp/voice-benchmark/bin/pip install -r benchmarks/voice_to_knowledge/requirements.lock
/tmp/voice-benchmark/bin/python -m benchmarks.voice_to_knowledge.runner \
  --corpus /approved/public-corpus/corpus.json \
  --model /approved/models/faster-whisper-small \
  --model-id small --model-revision <40-character-upstream-commit> \
  --out /tmp/voice-small-run-001 --timeout 1800
```

Repeat with medium and its own revision. No GPU mode is implemented; CUDA is absent here.
The command is an instruction, **not an executed real inference run**.

Input format (`voice.corpus.v0`): an object with `samples`, a list of records:

```json
{
  "schema_version": "voice.corpus.v0",
  "samples": [{
    "id": "unique-source-id", "path": "relative.wav", "sha256": "<audio-sha256>",
    "reference": "<original reference, never normalized in storage>",
    "reference_sha256": "<utf8-reference-sha256>", "reference_version": "v1",
    "source_url": "<public source>", "source_revision": "<immutable revision>",
    "license": "<explicit license>", "license_url": "<license evidence>",
    "duration": 1.0, "speaker_id": null, "human_reviewed": false,
    "language": "en", "kind": "human", "split": "pilot"
  }]
}
```

This is a schema illustration, not corpus data. Only public non-sensitive sources with verified
licenses are permitted. Metadata validation cannot establish consent or truth of a license:
a corpus curator must verify these before execution. `language`: zh/en/mixed/none; `kind`:
human/non_speech/synthetic; `split`: pilot/dev/test/plumbing. Synthetic inputs must be plumbing.
Unknown speaker/unreviewed references are allowed only for an explicitly limited pilot, not
human dev/test. Speaker overlap across dev/test is refused. Empty reference is valid for silence.

Audio must be mono 16-bit PCM WAV at 16 kHz, <=32 MB and <=300 seconds. For public source
conversion, record original hash, command, tool version and converted hash; do not overwrite it:

```sh
ffmpeg -nostdin -i original.ogg -map 0:a:0 -ac 1 -ar 16000 -c:a pcm_s16le converted.wav
```

The runner validates hashes/PCM/duration before model loading. Existing result directories are
refused. Three fresh workers each perform two sequential corpus passes. Only the first sample
of the first pass is process-cold; all later samples are warm. Disk/OS caches are not flushed.
Each worker has one overall timeout; timeout kills that worker and preserves partial stdout.
No per-item timeout or automatic retry is claimed. RSS is sampled every 10 ms and may miss peaks;
VRAM is null because CPU is used. Repetitions are not independent speakers. Outputs:
manifest.json, worker-N.jsonl, samples.json, samples.csv, summary.json. Worker failures affect
run status; aggregate rates cover successful rows only, with failure counts alongside them.

## Mock Submission

`submission.py` accepts explicit source-quoted annotations: fact/observation/uncertain must
exactly match transcript offsets; inference must have an exact quoted basis. It does not use an
LLM or invent domain facts. Raw transcript/hash is immutable. All claims remain unverified;
Markdown is a text artifact and needs sanitization if a future UI renders it.

`MockSubmission.create(trusted_identity, key, submission, request_id)` returns a mock draft
receipt. `read` is owner-scoped. There is no approval or publication operation. Trusted identity
must come from the future approved adapter, never a transcript. This is not authentication,
durable storage, a service, or a replacement for AEP's actor/maintainer/human gates.
Current evidence references are character offsets; segment-to-claim time mapping and finalized
OpenAPI/JSON Schema are pending #234, not claimed implemented.


## Synthetic extraction-to-Draft increment (#243)

```sh
python -m benchmarks.voice_to_knowledge.demo --out /tmp/voice-demo-new
python -m benchmarks.voice_to_knowledge.demo --out /tmp/voice-demo-missing-new \
  --fixture visit_missing_customer
```

Both commands use fixed synthetic text and a temporary generated one-second silent WAV. The
fake STT ignores its waveform content; the fake extractor returns scripted JSON. Neither claims
STT accuracy, LLM reasoning, meaningful timestamps or real customer information. No audio or
model download occurs. Never substitute these fixtures for the two user recordings.

Outputs: `raw.json` (unchanged text/hash and explicit fake provenance), `extraction.json`,
`draft.md` (existing Mock renderer's source-ID/character-offset citations), `receipts.json`.
The existing Mock stores the schema-validated extraction JSON on `VisitSubmission`; its ordinary
canonical payload hashing includes that JSON for replay/conflict checks. No alternate Draft store.

`extraction.py` exposes `ExtractionProvider`, a local `ExtractionSkill` descriptor (no AEP Skill
registration), and `prepare`. Callers inject providers, validate once, then retain the immutable
prepared payload across submission retries. `prepare` does not submit or retry. Existing
`MockSubmission.create/read` enforce caller scopes and ownership, including on replay.
Errors identify STT/provider failure, schema rejection, bad sources, changed audio or invalid
transcript; no partial result is submitted. Schema/source failures are non-retryable until input
is corrected. Real transport timeout/backoff/persistence are outside this in-memory prototype.

`extraction.schema.json` is generated from the Pydantic models; strict runtime validation rejects
extra fields, unsupported categories/statuses and missing required nullable customer fields.
Cross-field checks additionally verify source ID/hash, exact quote/offset, customer text and
claim mapping. Non-inference statements must equal their quoted source. Inferences have an exact
quoted basis and remain unverified. These checks prove provenance consistency, **not semantic
truth or that a quoted name is really a customer**; human review remains necessary. Dates,
contacts and follow-up owners are not guessed or added to this small schema.

This proposed synthetic-only schema is not #234's approved production Submission API. See
[real-scoring and human-review prerequisites](../../docs/voice-to-knowledge/VOICE_REVIEW_PROCEDURE.md).
