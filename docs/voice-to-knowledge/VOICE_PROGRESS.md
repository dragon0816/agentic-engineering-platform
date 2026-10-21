# Phase 0 progress — 2026-10-21 UTC

**Partial implementation complete; Phase 0 acceptance incomplete.** Draft PR:
https://github.com/dragon0816/agentic-engineering-platform/pull/240
Branch: `feature/voice-to-knowledge`. No merge, main push or force push.

Baseline: remote default main `a7f72e3c057b5dfeae3fe39b8122e5a19e7efa7d`.
Origin `https://github.com/dragon0816/agentic-engineering-platform.git` verified.
Remote feature branch did not exist; local initial `work` branch was clean at baseline.
No prior feature work overwritten. Applicable root AGENTS/CLAUDE and repository workflow skills
read; no nested AGENTS/CLAUDE under new paths. #234–239 read including current implementation
correction; no issue was closed or decision approved by this work.

## Commits and completed scope

- `64d3ba58`: six docs only; Draft PR created while it was the sole branch commit.
- `4fc79142`: isolated provider, scorer, immutable evidence claims and in-memory Draft adapter.
- `5b5cf3f2`: offline CPU runner, bounded workers, JSON/CSV/manifests and aggregate metrics.
- Following evidence/handoff commit: locked dependencies, hardware/blocked evidence, final tests.

All code lives in `benchmarks/voice_to_knowledge`; no src, AEP Core/Harness/Bridge/Telegram,
production data, runtime dependency or deployed configuration changed. Mock Submission has no
publish/approve route and enforces trusted caller scope, actor/tenant ownership, immutable
source quotes/hash, exact replay/conflict and concurrent replay. Extraction is source-quoted
annotation only; no external LLM or automatic fact inference. No live API compatibility claim.

## Actual verification

[Exact commands/results](../../benchmarks/voice_to_knowledge/evidence/verification.md):
**30 new contract/fake tests**, also passed in a pytest-only venv. **77 total tests passed**
including 47 existing Telegram and Knowledge regressions. Focused ruff, formatting and strict
mypy pass. CLI help works. Full repo suite NOT_RUN because shared runtime was not changed.

## Benchmark and blockers

- Hardware: 5 visible CPUs / 4-CPU quota, 16 GiB cgroup RAM, CUDA count 0, FFmpeg 7.1.5.
- Python dependency install succeeded; CPU INT8 supported by installed CTranslate2.
- GET model metadata `https://huggingface.co/api/models/Systran/faster-whisper-small`:
  **denied**, proxy tunnel 403. FLEURS metadata GET also **denied**, same reason. No retries.
- Zero downloaded models or licensed audio; inference **NOT_RUN**, scores **null**. No selection.
- Authorized artifact access/delivery remains pending. No bypass attempted.
- Public zh/en/mixed human corpus, five-term coverage, speaker-disjoint reviewed splits,
  silence/non-speech corpus and reference provenance remain incomplete.
- No company PC measurement, no GPU run; cloud results cannot predict company hardware.

## Leo decisions / next action

1. #234/#236: interface owner, auth/tenant mapping, review/publication boundary, deployment and
   polling topology, retention/classification, byte/duration limits and rollback approval.
2. #237/#239: authorize model/corpus delivery in this environment, approve corpus scale and
   numerical quality/latency/RAM thresholds before evaluation/selection.
3. Then obtain licensed public artifacts, pin hashes/revisions, run CPU small/medium and review
   actual failures. Company terminology acceptance remains separate from general public pilot.

No formal OpenAPI/JSON Schema freeze, time-aligned claim mapping, production adapter, durable
review queue, GPU/throughput support or integration is claimed delivered. GitHub gh API was
Forbidden; connector issue reads and Draft PR creation succeeded. Git fetch/push succeeded.

## Final remote check

After implementation, `git ls-remote --symref origin HEAD refs/heads/feature/voice-to-knowledge`
and `git fetch origin main` found default main advanced to
`20351c96e58fbc906879a94eb2f46eeae1312dac` (10 concurrent commits since the pinned baseline).
Those include Agent Web and shared HANDOFF/TASKS edits. This branch was not rebased, force-pushed
or merged; tests above apply to the pinned starting baseline plus this feature, not the newer
main. Before review/merge, reconcile shared tracking documents with current main and rerun
relevant checks. No runtime integration or compatibility with the newer main is asserted.

## Authorized main synchronization (2026-10-21)

The subsequent user instruction explicitly authorizes a non-destructive main-to-feature merge.
Pre-merge: clean worktree; remote default main `20351c96e58fbc906879a94eb2f46eeae1312dac`;
feature `385d7ea0`. `git merge-tree --write-tree HEAD origin/main` predicted only HANDOFF/TASKS
conflicts; 77 related tests passed before merging. `git merge --no-ff --no-commit origin/main`
then confirmed those two conflicts. Resolution keeps each upstream document byte-for-byte as
its prefix, with feature records appended. Every src/.github file equals upstream main: no
runtime behavior was modified to resolve conflicts. No rebase, force push or PR merge.

Post-sync checks in `/tmp/aep-sync-venv` (`pip install -e '.[dev,office]'`):
- 134 passed, 1 skipped (no Chromium), with voice/Telegram/Knowledge plus affected upstream tests.
- Repository-wide ruff and format pass (992 files).
- `python -m mypy --platform win32`: passes, 734 source files (CI platform).
- Default Linux mypy: 26 Windows API/type errors in four unchanged upstream files; comparison
  with detached main is recorded in the sync verification evidence, not repaired in runtime.
- Focused strict mypy covers the isolated benchmark/test modules separately.

No network authorization changed. Real inference remains blocked/NOT_RUN; see
[exact hosts and required artifacts](VOICE_NETWORK_REQUIREMENTS.md).

Full post-sync Linux suite: **3690 passed, 130 skipped, 3 failed**. All three failures reproduce
on detached main 20351c96 with upstream src explicitly selected; no Voice regression identified.
Default Linux mypy's 26 diagnostics also exactly match detached main. Windows-target full mypy,
focused strict mypy, ruff, format, build and pip check pass. Details/commands:
`benchmarks/voice_to_knowledge/evidence/sync-verification.md`.
CI run 39535239198 on merge head was in progress at pytest when evidence was collected;
initial run 39533933211 was superseded/cancelled. No CI pass or completed failure asserted.

## Offline extraction increment (#243, 2026-10-21)

Starting head fd810f2c; parent verified its Windows run 39535790481 succeeded. That is historical
CI for the preceding increment, not a claim about new code. Remote main advanced to 59f81baf
(workspace retry/release, two commits beyond 20351c96); inspected and not merged for this isolated
increment. Existing feature branch clean; no other work overwritten.

Added injectable fake STT/extraction flow, local Skill descriptor, strict proposed JSON schema,
source-linked Markdown through the existing Mock Draft, and two explicitly synthetic visit
fixtures. Null customer stays null; no dates/contacts/owners invented. Typed immutable submission
retains raw text separately from canonical extraction JSON. No src/runtime/consumer changes.

Actual audio remains absent here: parent-reported 37.477s language unverified and 60.232563s
user-labeled Chinese, both mono PCM16 16kHz. No reference gold, model access still proxy-blocked;
no retries, audio copies, fabricated references, scores or winner. See VOICE_REVIEW_PROCEDURE.md.

Verification of #243: **21 new / 51 total isolated tests pass**, **98 with existing regressions**;
repo lint/format, Windows-target full mypy and focused strict mypy pass. Both fake demos return
draft/same_draft=true/NOT_RUN. Exact commands: benchmark evidence/extraction-verification.md.
New-head CI is separate from the previously successful fd810f2c run; no result assumed.

## CI failure follow-up (39555054382)

8f51982f Windows CI failed: 3795 passed/49 skipped/2 failed. One feature test read UTF-8 Chinese
JSON using Windows cp1252 default; fixed by explicit UTF-8 reads plus a locale regression that
fails before the fix and passes after. Existing Telegram edit-count timing failure (4 vs <=3)
and shared annotation-script Unicode output failure left unchanged; evidence and minimal separate
decision in `benchmarks/voice_to_knowledge/evidence/ci-39555054382.md`.
Verification: 59 tests pass (52 Voice + 7 Telegram), focused lint/format and strict mypy pass.
New CI remains separate; no claim of Windows success until terminal result. No actual STT scores.
