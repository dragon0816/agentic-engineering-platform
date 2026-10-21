# Executed verification — 2026-10-21 UTC

Working directory: `/workspace/agentic-engineering-platform`.
Environment: `environment.json`. Dependencies: `../requirements.lock`.

```sh
PYTHONPATH=.:src /tmp/aep-voice-venv/bin/python -m pytest \
  tests/test_voice_*.py tests/test_telegram_ingress.py tests/test_telegram_attachments.py \
  tests/test_knowledge_pipeline.py tests/test_knowledge_publish.py tests/test_knowledge_push.py -q
```

**77 passed in 8.77s**: 30 new fake/contract cases + 47 existing behavior regressions.

```sh
python -m venv /tmp/aep-voice-tests-only
/tmp/aep-voice-tests-only/bin/pip install -q pytest
PYTHONPATH=. /tmp/aep-voice-tests-only/bin/python -m pytest tests/test_voice_*.py -q
```

**30 passed in 0.37s** with no faster-whisper/CTranslate2/PyAV/psutil installed.

```sh
/tmp/aep-voice-venv/bin/ruff check benchmarks/voice_to_knowledge tests/test_voice_*.py
/tmp/aep-voice-venv/bin/ruff format --check benchmarks/voice_to_knowledge tests/test_voice_*.py
/tmp/aep-voice-venv/bin/mypy --explicit-package-bases --follow-imports=silent \
  benchmarks/voice_to_knowledge tests/test_voice_*.py
/tmp/aep-voice-venv/bin/python -m benchmarks.voice_to_knowledge.runner --help
```

All checks passed; format clean; mypy: no issues in 10 source files; CLI help exits 0.
Initial tests ran before implementation and failed with three missing modules as expected.
Subsequent implementation/test fixture and formatting/type issues were corrected before final checks.
Full repository pytest/lint/type check NOT_RUN: no shared src/runtime/contracts changed.

Real inference **NOT_RUN**. No model bytes or licensed human audio were obtained.
The Hugging Face metadata probes (Python urllib.request.urlopen with timeout=20) were denied by
network proxy: `URLError: Tunnel connection failed: 403 Forbidden`. See `blocked.json`.
No denied download was retried; no alternate endpoint or machine was used to bypass policy.
GitHub issue reads via gh GraphQL and REST also returned Forbidden; the authorized GitHub
connector successfully read #234–239 and created Draft PR #240.

No human-accuracy, latency, RTF, RSS-under-inference, VRAM or model-selection score exists.
The environment inventory is not benchmark data. Synthetic test timings are not STT performance.
