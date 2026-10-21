# Local STT benchmark protocol

Status: NOT_RUN at the initial docs commit. No model selected.

Environment: Linux x86_64 AMD EPYC 9V74; 5 visible CPUs, cgroup quota 4 CPU;
16 GiB cgroup RAM limit, no swap, ~30 GiB disk free. Python 3.12.14;
FFmpeg 7.1.5-0+deb13u1. No nvidia-smi detected; GPU inference NOT_RUN.
Dependency installation and artifact download feasibility are checked separately.

Candidates: multilingual small and medium CPU INT8; large-v3/turbo only with available GPU.
Record exact package lock, model revision and file hashes. No runtime network fallback.
Fixed parameters: CPU threads 4, workers 1, beam 5, temperature 0, language per manifest,
condition_on_previous_text false, VAD false, no initial prompt. Dev-only ablations may compare
VAD and a fixed vocabulary list; never derive a prompt from holdout references.

Three repetitions, fresh process/model for each cold run, repeated files on the same model for
warm. Report load time separately and cold total including load; latency includes exhausting
segments. Single-request latency and RTF = elapsed/audio seconds, concurrency 1. Throughput
is not latency. Record process peak RSS and VRAM (null with explicit CPU reason), hardware,
load, parameters, sample counts by language/kind/split, failures, original hypotheses,
JSON and CSV rows and run manifest. Cache-cold disk is not implied by process-cold.

Report raw and normalized CER/WER/MER with edit counts/denominators. Normalization is NFKC,
casefold and punctuation removal; no vocabulary autocorrection, number rewriting, or Chinese
script conversion. CER excludes whitespace; WER uses whitespace tokens (poor for unsegmented
Chinese); MER uses Han characters plus Latin/number words. Empty reference rate is null;
insertions remain recorded and silence hallucination is nonempty normalized hypothesis.
Term precision/recall count occurrences from CMP180, Wi-Fi 8, UWB, Qualcomm, LitePoint;
zero denominator is null, never a perfect score. Numbers/negations need separate diagnostics.

Corpus policy: only explicitly licensed public non-sensitive human speech, with source URL,
license URL, revision, audio SHA256, original reference/hash, duration, language, speaker,
split and human-review state. Missing speaker disjointness blocks holdout claims. Synthetic
silence/TTS may exercise plumbing but never human accuracy. No company/customer recordings.
FLEURS (Google, CC-BY-4.0) is a candidate for general zh/en pilot; it does not establish mixed
speech or company terminology coverage. Insufficient coverage means blocked, not fabricated scores.

Upstream research (2026-10-21):
- https://github.com/SYSTRAN/faster-whisper — CTranslate2 backend; PyAV decoding; transcribe
  returns lazy segments which must be fully consumed; CPU INT8 supported.
- https://opennmt.net/CTranslate2/quantization.html — supported compute types depend on hardware.
- https://ffmpeg.org/ffmpeg.html — explicit audio stream/resampling options for reproducible input.
- https://huggingface.co/datasets/google/fleurs — public CC-BY-4.0 general multilingual speech.

Do not extrapolate cloud CPU measurements to a company Windows PC. Thresholds and final
corpus scale are pending Leo; absent those, selection remains pending even if a pilot runs.
