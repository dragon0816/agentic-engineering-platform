# Voice-to-Knowledge Phase 0 architecture

Status: proposed isolated prototype; NOT an approved production integration.
Baseline: remote default main, a7f72e3c057b5dfeae3fe39b8122e5a19e7efa7d, verified 2026-10-21 UTC.
Scope/acceptance: #235–239; decisions #234/#236 remain Leo-owned and open.
The user's feature-branch-only instruction supersedes the general main workflow.

## Implementation inventory

| State | Evidence | Meaning |
|---|---|---|
| implemented | [TelegramIngress, _files, poll_once](https://github.com/dragon0816/agentic-engineering-platform/blob/a7f72e3c057b5dfeae3fe39b8122e5a19e7efa7d/src/channels/telegram.py) | resident host outbound Telegram polling; document/photo only; allowed sender mapping precedes work |
| implemented | [SkillManifest/SkillRegistry](https://github.com/dragon0816/agentic-engineering-platform/blob/a7f72e3c057b5dfeae3fe39b8122e5a19e7efa7d/src/agent/skills.py) | versioned installed Skills, not a new voice service |
| implemented | [HostRuntime](https://github.com/dragon0816/agentic-engineering-platform/blob/a7f72e3c057b5dfeae3fe39b8122e5a19e7efa7d/src/host_runtime/host.py), [LocalAgent](https://github.com/dragon0816/agentic-engineering-platform/blob/a7f72e3c057b5dfeae3fe39b8122e5a19e7efa7d/src/host_runtime/agent.py), [sync](https://github.com/dragon0816/agentic-engineering-platform/blob/a7f72e3c057b5dfeae3fe39b8122e5a19e7efa7d/src/host_runtime/sync.py) | local reasoning/execution and outbound remote-job polling remain authoritative |
| implemented | [KnowledgePipeline](https://github.com/dragon0816/agentic-engineering-platform/blob/a7f72e3c057b5dfeae3fe39b8122e5a19e7efa7d/src/knowledge/pipeline.py) | add_drop (no overwrite), convert, plan_ingest, apply_ingest, merge already write to sandboxes |
| implemented | [AgentWeb](https://github.com/dragon0816/agentic-engineering-platform/blob/a7f72e3c057b5dfeae3fe39b8122e5a19e7efa7d/src/host_runtime/web.py#L5002) | pipeline_call supplies runtime actor; publish is human-only; start_push checks may_push/maintainer |
| contract-only | [Knowledge API v0.1](https://github.com/dragon0816/agentic-engineering-platform/blob/a7f72e3c057b5dfeae3fe39b8122e5a19e7efa7d/docs/contracts/knowledge-api/README.md) | 15 GET operations, no serving route; writes/review deferred, not proof AEP lacks writes |
| proposed | this folder and isolated benchmark package | STT provider, extraction evidence contract, Mock Submission; no live routes or registration |

## Network and trust boundary

```text
Telegram service <-- outbound polling -- existing resident TelegramIngress
                                           | trusted sender -> platform actor
                                           v
                                     LocalAgent / Bridge
                                           | (future approved audio hook)
immutable audio -> local STT -> immutable transcript -> evidence-bearing Draft
                                           | (future approved adapter)
                              existing sandbox -> review/gate -> human publish
```

No second consumer of the same bot token. No inbound route to an internal Bridge is assumed.
A server bot + outbound job queue could support central ingress, but requires queue identity,
delivery/replay semantics, payload retention and a planned single-consumer cutover. Reusing the
resident poller is the smaller proposal; neither topology is implemented in Phase 0.

Prototype code stays under benchmarks/voice_to_knowledge, outside src and installed runtime.
No AEP Core, Harness, Bridge, Telegram, manifest or production configuration change is authorized.
Local STT executes; corpus reads are read-only; result files and mock drafts are isolated writes.
Publication and any future message/network side effect require existing policy and separate review.
