# Synthetic extraction increment verification — 2026-10-21

Scope: Issue #243, Draft PR #240. Starting feature fd810f2c (includes main 20351c96).
New upstream main 59f81baf inspected, not merged; unrelated workspace retry/release work.

Executed in `/workspace/agentic-engineering-platform`, venv `/tmp/aep-sync-venv`:

```sh
/tmp/aep-sync-venv/bin/python -m pytest tests/test_voice_*.py -q
```

**51 passed in 0.76s**, including **21 new extraction/orchestration cases**. Tests were first
run before implementation and failed collection with the missing extraction module as expected.

```sh
/tmp/aep-sync-venv/bin/python -m pytest tests/test_voice_*.py \
  tests/test_telegram_ingress.py tests/test_telegram_attachments.py \
  tests/test_knowledge_pipeline.py tests/test_knowledge_publish.py tests/test_knowledge_push.py -q
```

**98 passed in 9.25s** (51 isolated + 47 existing regressions).

```sh
/tmp/aep-sync-venv/bin/ruff check .
/tmp/aep-sync-venv/bin/ruff format --check .
/tmp/aep-sync-venv/bin/mypy --platform win32
/tmp/aep-sync-venv/bin/mypy --explicit-package-bases --follow-imports=silent \
  benchmarks/voice_to_knowledge tests/test_voice_*.py
```

Repo lint/format pass (997 files). Windows-target full mypy: **735 files pass**.
Focused strict mypy: **13 files pass**. Full pytest not repeated in this isolated increment;
prior full Linux run and baseline failures remain documented in sync-verification.md.

## Executed demo (fake only)

```sh
/tmp/aep-sync-venv/bin/python -m benchmarks.voice_to_knowledge.demo --out /tmp/voice-demo-visit-243
/tmp/aep-sync-venv/bin/python -m benchmarks.voice_to_knowledge.demo \
  --out /tmp/voice-demo-missing-243 --fixture visit_missing_customer
```

Both exit 0 and emit:

```json
{"synthetic": true, "status": "draft", "same_draft": true, "actual_benchmark": "NOT_RUN"}
```

Each directory contains raw.json, extraction.json, draft.md and receipts.json. The first example
has four claim kinds and a sourced synthetic customer. The second customer is null. Replay has a
new request ID and the same draft ID; no publish route. Both use temporary generated one-second
silence, not either supplied recording; that temporary WAV is deleted, not committed.

The JSON Schema equals the runtime-generated strict model schema. Invalid schema, source/hash/
quote/offset/customer references, schema-to-submission claim mismatch, provider failure, audio
mutation, attempted approval fields, permission refusal and idempotency conflict are tested.
Source checks are lexical, not proof of semantic correctness or LLM extraction quality.

Historical Windows CI 39535790481 succeeded for fd810f2c (parent-confirmed); new increment CI
must be checked separately after push and is not claimed passed here. No real STT/LLM inference,
model/audio download, company data, supplied recording or gold transcript was used. Actual
benchmark stays NOT_RUN/BLOCKED. No runtime integration requiring #234/#236 was introduced.
