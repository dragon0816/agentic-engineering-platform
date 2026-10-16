"""AEP's built-in LLM gateway (docs/phases/LLM_GATEWAY.md).

A LiteLLM proxy on 127.0.0.1 in front of the company chat service, so the
Agent (OpenAI format) and coding agents (Anthropic format) reach a model with
one local key. Everything here except `launcher` and `patch` uses only the
standard library: the gateway runs in its own virtual environment, and the
`aep-host gateway` commands run in AEP's, where LiteLLM is not installed.
"""

#: The LiteLLM release the streaming patch was verified with (owner's working
#: gateway, 2026-10-16). `patch.apply` refuses to guess on any other version's
#: internals, and the bundle pins exactly this one.
PINNED_LITELLM_VERSION = "1.94.1"
DEFAULT_PORT = 4000
#: The gateway only ever listens on loopback.
LOOPBACK = "127.0.0.1"
