# Development plan

Acceptance source: Epic #235, P0-A #236, P0-B #237, P0-C #238, P0-D #239 and #234.

1. Pin baseline, inspect current implementation and applicable instructions (done).
2. Commit these six design documents only and open a Draft PR (first delivery).
3. Define isolated provider/scoring/submission contracts and failing contract tests.
4. Implement bounded local benchmark runner and in-memory Mock Submission in small commits.
5. Verify fake tests separately from local real inference; record raw results and limitations.
6. Update progress/tasks/handoff; Leo reviews, no merge or issue closure by this work.

Planned paths: docs/voice-to-knowledge/*.md, benchmarks/voice_to_knowledge/*.py,
benchmarks/voice_to_knowledge/requirements.lock, tests/test_voice_*.py.
No new package dependency in the production pyproject. Optional benchmark venv only.

Tests first: edit-distance oracle; raw/normalized Chinese/English/mixed tokenization; empty
reference; term insertions/omissions; generator exhaustion and late errors; corrupt/oversize
media; timeout; immutable transcript; missing source; scope/tenant/actor refusal; exact replay
and payload conflict; unpublished drafts. Real-model scores are never inferred from fake tests.

Proposed (not approved) sizes: 30 pilot, then 120 human speech + 20 non-speech with speaker-disjoint
dev/test. Leo must set quality, latency, RAM and safety thresholds before model selection.
Public general-speech pilot cannot satisfy company terminology or company PC acceptance.
