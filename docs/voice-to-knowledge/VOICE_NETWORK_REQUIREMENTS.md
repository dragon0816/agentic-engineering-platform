# Artifact access request — pending Leo, no retry performed

## Observed denial (exact targets)

Host: **huggingface.co**, HTTPS TCP 443.

- `GET https://huggingface.co/api/models/Systran/faster-whisper-small`
- `GET https://huggingface.co/api/datasets/google/fleurs`

Both failed before metadata retrieval: `URLError: Tunnel connection failed: 403 Forbidden`.
The proxy's own hostname was not recorded in the failure; no credentials/environment secrets
are needed to diagnose this. No model, corpus file or redirect was reached. Medium was not
attempted. No new request to either denied endpoint or alternative download source was made.

## Proposed minimal retrieval scope after approval

1. `huggingface.co/api/models/Systran/faster-whisper-small` and the corresponding
   `Systran/faster-whisper-medium` metadata: obtain immutable revision and file inventory.
2. Each approved model's `/Systran/faster-whisper-{small,medium}/resolve/<commit>/<file>`:
   `model.bin`, `config.json`, `tokenizer.json`, `preprocessor_config.json` when supplied,
   and `vocabulary.*` files present in that pinned repository. Also preserve README/model card
   and LICENSE/license evidence, upstream revision, sizes and SHA256 for all delivered files.
   Required download patterns are from installed faster-whisper 1.2.1 `utils.download_model`;
   these are patterns, not a claim that every repository contains every optional file.
   Ship tokenizer.json locally so no implicit tokenizer lookup is needed.
3. `huggingface.co/api/datasets/google/fleurs`: resolve an immutable dataset revision and
   inventory for **en_us and cmn_hans**. Obtain README/card, CC-BY-4.0 license/attribution,
   selected original human audio plus original references, IDs, durations and available speaker
   metadata. If distributed as Parquet/archive, the selected source shard(s), index and original
   rows are required. Exact shard names/sizes are **unknown until approved metadata access**;
   no fabricated filename or completed corpus manifest is supplied.
4. Preserve original bytes and converted mono PCM16/16kHz WAVs, original/converted hashes,
   conversion command/version, reference hashes/version, review state and split assignment.
   A curator must check non-sensitive/public licensing; dataset membership alone is not enough.

Only huggingface.co was observed as a denied destination. Model/dataset binaries may redirect
to storage/CDN/Xet hosts, but **no redirect hostname was observed or probed**. Do not request a
blind wildcard or treat potential storage hosts as approved. After metadata access is explicitly
approved, inspect actual redirect destinations without following unapproved hosts; submit exact
additional hosts if needed. No STT/LLM upload endpoint is needed: inference stays offline.
An owner-approved artifact package delivered into this environment is another possible process,
not something attempted to bypass the current proxy denial.

FLEURS does not establish mixed-language/five-term coverage or reliable speaker-disjoint holdout
by itself. Licensed human CMP180/Wi-Fi 8/UWB/Qualcomm/LitePoint and mixed-language material,
reviewed references, non-speech samples and thresholds remain separate decisions. No company or
customer audio, official bot token, GPU model or external STT/LLM transmission is requested.
