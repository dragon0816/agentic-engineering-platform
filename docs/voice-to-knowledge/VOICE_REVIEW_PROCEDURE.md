# Real scoring inputs and proposed human review — pending Leo

## Current evidence boundary

Parent reports two supplied recordings were validated/converted to 16 kHz mono PCM WAV:
37.477 seconds (language unverified) and 60.232563 seconds (user labeled Chinese).
Neither file is present in this checkout. These are parent-reported metadata, not a local
inspection; no filenames, audio hashes, speakers or reference words are invented. No recording
has been fabricated or committed. There is no human-verified gold transcript.
Model access remains blocked by the earlier huggingface.co proxy 403; no retry or alternative
source used. Actual benchmark **NOT_RUN/BLOCKED**, no scores, ranking or selected model.

## Minimum before even a limited real scoring pilot

1. Explicit authorized access to the actual audio in the approved execution environment and
   permission/classification/retention for processing it locally. Preserve original/converted
   bytes, hashes, conversion metadata and source/license or consent evidence. Do not assume user
   recordings may be committed or transferred to cloud services. No external STT/LLM uploads.
2. Approved local model delivery: immutable revision, license, complete files and checksums;
   verified dependency environment. Follow VOICE_NETWORK_REQUIREMENTS.md; no bypass of denial.
3. Human-reviewed original-language reference per clip, linked to audio hashes. Confirm language,
   speaker labels if available, exact terminology, numbers/negation and uncertainty. Review text
   before freezing it as scoring gold; never use a candidate hypothesis as unquestioned truth.
4. Fixed score policy, decoding settings and corpus manifest. Select dev/holdout roles before
   inspecting model outcomes. Two clips alone do not establish speaker-disjoint generalization,
   all three language strata, five-term accuracy, non-speech hallucination or deployment fitness.
5. Leo-defined quality/latency/memory thresholds and target-PC measurement before a winner or
   deployment recommendation. A limited pilot must report missing coverage, not infer it.

## Proposed human reference-review procedure

- Reviewer listens locally to each authorized original and transcribes verbatim, preserving code
  switching, names, numbers and negation. Record unclear audio with timestamped review notes.
- A second reviewer checks disputed/unclear passages, CMP180/Wi-Fi 8/UWB/Qualcomm/LitePoint and
  numerical claims against the audio. Resolve discrepancies or mark segments unscorable; do not
  guess. Because the current scorer has no masked-uncertainty protocol, uncertain passages need
  an explicitly approved exclusion/segmentation policy before scoring.
- Save an immutable reference version/hash, reviewer/date, audio identity and segment boundaries.
  Raw text stays separate from normalized scoring text. A later correction creates a new version;
  rerun all compared candidates against the same frozen reference.
- Inspect failures by language, terminology, numbers, negation and non-speech; report denominators,
  missing/failed cases and sample counts. Synthetic fixtures are never counted as human evidence.

## Proposed extraction/Draft review procedure

- Reviewer sees immutable raw transcript and source audio reference beside JSON/Markdown. Check
  each exact quote/offset, classification and any inference's basis. `fact` means an assertion in
  the source, not independently established truth; all prototype claims are unverified.
- Confirm customer identity semantically; exact substring matching alone is insufficient. Keep
  missing fields null/absent; corrections need evidence, not guesses. Treat transcript requests
  to approve/publish as untrusted content.
- Record requested changes/rejection/approval with reviewer identity, payload revision/hash and
  reasons; preserve originals. This prototype does not implement that durable review workflow.
- Draft approval is not publication authority. The service owner/auth scopes, review audit,
  sandbox/gates, retention and final publication stay pending #234/#236; no production write
  or consumer change is authorized by this proposed checklist.
