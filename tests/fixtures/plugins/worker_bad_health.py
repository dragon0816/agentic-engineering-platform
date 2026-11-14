"""Synthetic worker whose health declaration does not match its manifest:
it reports a capability the package never declared. Activation must fail."""

import json
import sys

for line in sys.stdin:
    if not line.strip():
        continue
    request = json.loads(line)
    reply = {"protocol": "aep-extension-jsonl/v1", "request_id": request["request_id"]}
    if request["operation"] == "health":
        reply.update(
            status="healthy",
            capabilities=[{"namespace": "undeclared-lab", "name": "ghost", "version": "1.0.0"}],
        )
    else:
        reply.update(status="refused", code="fixture_unhealthy")
    sys.stdout.write(json.dumps(reply) + "\n")
    sys.stdout.flush()
