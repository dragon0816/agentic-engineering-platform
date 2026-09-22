"""Ingress adapters: the ways a request reaches the resident local Agent.

An adapter maps a channel's sender to exactly one platform actor and hands the
Agent a `LocalAgentRequest`; it adds no authority, and the Agent admits or
refuses by the same membership rule whatever the channel.
"""
