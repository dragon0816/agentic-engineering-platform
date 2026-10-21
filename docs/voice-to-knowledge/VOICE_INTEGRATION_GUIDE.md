# Integration guide — proposal awaiting #236/#234

Phase 0 runs only an isolated local benchmark/prototype. There is no deployed bot, API,
background service or production Knowledge write. Never supply a formal Telegram token.

Possible future minimum files (NOT changed): channels/telegram.py for voice/audio metadata
and an explicit hook after actor authorization; host_runtime/host.py for optional provider
injection/lifecycle; a new adapter to existing Knowledge sandbox operations after contract
approval. Existing document/photo behavior, poll offset, allowed users, attachment bounds and
failure semantics must remain compatible. Core/Harness routing changes require a separate
approved proposal, not a Phase 0 shortcut.

Reuse versus server queue: resident polling avoids inbound firewall access and a second bot
consumer; central ingress requires secure queue ownership, tenant routing, idempotency,
retention and a single-consumer migration. Leo selects topology/deployment owner first.

Future regression list: tests/test_telegram*.py, tests/test_host*.py,
tests/test_knowledge_pipeline*.py, tests/test_knowledge*publish*.py,
tests/test_knowledge*push*.py, actor/sandbox/attachment authorization tests, full suite when
shared runtime/contracts change. Exact names must be checked at integration time.
Rollback: remove/disable the future optional hook and provider; preserve originals and review
records. Phase 0 rollback is deleting the new benchmark/docs files; existing behavior is untouched.

Leo decisions: actor/tenant mapping and scopes; Draft service owner/route/version; review and
publication responsibility; queue versus resident polling; approved limits, storage/classification,
retention/deletion; corpus coverage/thresholds; target PC resources; model distribution/license.
