"""A complete path from a declared requirement to an answer, with nothing
installed and nothing contacted.

This is the model layer's counterpart to `workflow.proof`: something a host
can copy rather than infer from contracts. It shows the whole chain and where
each decision is made.

- `SAMPLE_CATALOG` is plain data, the shape a host keeps in YAML or JSON. The
  platform chooses no format and no file location, so this is an example
  rather than a default.
- `clients_from` validates that data and wires it to a credential resolver and
  a transport. Both are supplied by the host: a secret is resolved by the
  execution environment, and a transport keeps tests off the network.
- `ask` states what the work needs, lets the catalog pick the alias that
  satisfies it, and sends one request to whatever that turns out to be. It
  names no provider, no model id and no URL, which is the point.

Nothing here is a default for production. A host builds its own catalog and
its own resolver; this exists so that the assembly is written down once and
exercised in CI.
"""

from typing import Any

from common.execution import Failure, TraceIdentifiers
from models.catalog import ModelCatalog
from models.clients import ModelClients
from models.contracts import ModelMessage, ModelRequest, ModelRequirements, ModelResponse
from models.credentials import CredentialResolver
from models.wire import Transport

SAMPLE_CATALOG: dict[str, Any] = {
    "endpoints": [
        # Order is meaningful: the first endpoint that satisfies a requirement
        # wins, so the cheap local model is offered before the company one.
        {
            "alias": "local_small",
            "provider": "ollama",
            "model": "qwen3:8b",
            "base_url": "http://localhost:11434",
            "capabilities": {
                "reasoning": "low",
                "tool_calling": True,
                "streaming": True,
                "local": True,
                "max_context_tokens": 32_000,
            },
        },
        {
            "alias": "company_reasoning",
            "provider": "openai_compatible",
            "model": "gpt-5.5",
            "base_url": "https://gateway.example.invalid/api",
            # A name, never a value. The host's resolver answers it.
            "credential": {"name": "company_gateway_token"},
            "capabilities": {
                "reasoning": "high",
                "tool_calling": True,
                "structured_output": True,
                "streaming": True,
                "vision": True,
                "max_context_tokens": 128_000,
            },
        },
    ],
    "routes": [{"name": "default", "alias": "company_reasoning"}],
}


def clients_from(
    data: dict[str, Any],
    *,
    resolver: CredentialResolver | None = None,
    transport: Transport | None = None,
) -> ModelClients:
    """A validated catalog wired to the host's resolver and transport. A
    mistake in the data is refused here rather than at the first request."""
    return ModelClients(ModelCatalog.model_validate(data), resolver=resolver, transport=transport)


def ask(
    clients: ModelClients,
    *,
    requirements: ModelRequirements,
    prompt: str,
    trace: TraceIdentifiers,
    max_output_tokens: int = 512,
) -> ModelResponse | Failure:
    """State what the work needs and send one request to whichever endpoint
    satisfies it. A `Failure` here is a routing problem, one on the response
    is a provider problem, and the two never become an exception."""
    chosen = clients.for_requirements(requirements)
    if isinstance(chosen, Failure):
        return chosen
    alias, client = chosen
    return client.generate(
        ModelRequest(
            trace=trace,
            model_alias=alias,
            messages=(ModelMessage(role="user", text=prompt),),
            requirements=requirements,
            max_output_tokens=max_output_tokens,
        )
    )
