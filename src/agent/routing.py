"""Deterministic-first selection. Selection never invokes capabilities or grants access."""

import json
import re
from typing import Literal, Self

from pydantic import Field, JsonValue, ValidationError, model_validator

from agent.skills import CommandBinding, SkillRegistry
from common.assets import AssetIdentity
from common.base import Contract
from common.execution import Failure, RequestContext, RouteDecision, TraceIdentifiers
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

DOT_COMMAND = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+(.*))?$")


class RouteProposal(Contract):
    kind: Literal["capability", "workflow"]
    target: AssetIdentity
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class RoutingOutcome(Contract):
    trace: TraceIdentifiers
    decision: RouteDecision
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    origin: Literal["deterministic", "model", "needs_input"]
    failure: Failure | None = None

    @model_validator(mode="after")
    def consistent_outcome(self) -> Self:
        unresolved = self.decision.kind == "needs_input"
        if unresolved != (self.origin == "needs_input") or unresolved != (self.failure is not None):
            raise ValueError("route failure, origin and decision must agree")
        if unresolved and self.arguments:
            raise ValueError("unresolved routes cannot carry invocation arguments")
        if self.decision.kind == "agent":
            raise ValueError("agent delegation is not supported by this routing layer")
        return self


def needs_input(request: RequestContext, code: str) -> RoutingOutcome:
    return RoutingOutcome(
        trace=request.trace,
        origin="needs_input",
        decision=RouteDecision(kind="needs_input", reason=code),
        failure=Failure(code=code, message="No safe route could be selected"),
    )


def selected(
    request: RequestContext, binding: CommandBinding, arguments: dict[str, JsonValue]
) -> RoutingOutcome:
    return RoutingOutcome(
        trace=request.trace,
        origin="deterministic",
        arguments=arguments,
        decision=RouteDecision(
            kind=binding.kind, target=binding.target, reason="Known installed route"
        ),
    )


class CommandRouter:
    def __init__(self, skills: SkillRegistry) -> None:
        self.skills = skills

    def resolve(self, request: RequestContext) -> RouteDecision | None:
        result = self.match(request)
        return result.decision if result is not None else None

    def direct(self, request: RequestContext, alias: str) -> RoutingOutcome:
        """Explicit Skill selection: ordered keyword rules, then its declared default."""
        context = RequestContext.model_validate(request)
        skill = self.skills.get(context.namespace, alias)
        if skill is None:
            return needs_input(context, "unknown_skill")
        name = next(
            (
                rule.command
                for rule in skill.rules
                if re.search(rule.pattern, context.message, re.IGNORECASE)
            ),
            skill.default_command,
        )
        if name is None:
            return needs_input(context, "no_default_command")
        # Manifest validation guarantees rules and default_command reference declared commands.
        command = next(item for item in skill.commands if item.name == name)
        return selected(context, command, {})

    def candidates(self, namespace: str) -> tuple[CommandBinding, ...]:
        return tuple(
            command for skill in self.skills.discover(namespace) for command in skill.commands
        )

    def match(self, request: RequestContext) -> RoutingOutcome | None:
        context = RequestContext.model_validate(request)
        match = DOT_COMMAND.match(context.message.strip())
        if match:
            skill = self.skills.get(context.namespace, match.group(1))
            if skill is None:
                return needs_input(context, "unknown_skill")
            command = next((item for item in skill.commands if item.name == match.group(2)), None)
            if command is None:
                return needs_input(context, "unknown_command")
            raw_args = (match.group(3) or "").strip()
            return selected(context, command, {"args": raw_args} if raw_args else {})
        for skill in self.skills.discover(context.namespace):
            for rule in skill.rules:
                if re.search(rule.pattern, context.message, re.IGNORECASE):
                    command = next(item for item in skill.commands if item.name == rule.command)
                    return selected(context, command, {})
        return None


class RequestRouter:
    """At most one provider-neutral selection. Model transport owns its I/O deadline."""

    def __init__(
        self,
        commands: CommandRouter,
        model: ModelClient | None = None,
        model_alias: str = "routing",
        *,
        local_only: bool = True,
    ) -> None:
        self.commands = commands
        self.model = model
        self.model_alias = model_alias
        self.local_only = local_only

    def route(self, request: RequestContext) -> RoutingOutcome:
        context = RequestContext.model_validate(request)
        deterministic = self.commands.match(context)
        if deterministic is not None:
            return deterministic
        candidates = self.commands.candidates(context.namespace)
        if self.model is None or not candidates:
            return needs_input(context, "no_known_route")
        catalog = [
            {
                "skill": skill.alias,
                "instructions": skill.instructions,
                "commands": [command.model_dump() for command in skill.commands],
            }
            for skill in self.commands.skills.discover(context.namespace)
        ]
        prompt = "Select one installed route as {kind,target,arguments}; otherwise return null. "
        prompt += "Do not invent targets or permissions. Candidates: " + json.dumps(catalog)
        model_request = ModelRequest(
            trace=context.trace,
            model_alias=self.model_alias,
            messages=(
                ModelMessage(role="system", text=prompt),
                ModelMessage(role="user", text=context.message),
            ),
            requirements=ModelRequirements(structured_output=True, local_only=self.local_only),
            output_contract="platform.route-proposal.v1",
            max_output_tokens=512,
        )
        try:
            response = self.model.generate(model_request)
            if response.failure is not None:
                return needs_input(context, "model_unavailable")
            if response.trace != context.trace or response.model_alias != self.model_alias:
                return needs_input(context, "model_context_mismatch")
            proposal = RouteProposal.model_validate(response.structured_output)
        except ValidationError:
            return needs_input(context, "invalid_model_route")
        except Exception:
            # Never include provider exception text, prompts or credentials in errors.
            return needs_input(context, "model_unavailable")
        if not any(
            item.kind == proposal.kind and item.target == proposal.target for item in candidates
        ):
            return needs_input(context, "uninstalled_model_target")
        return RoutingOutcome(
            trace=context.trace,
            origin="model",
            arguments=proposal.arguments,
            decision=RouteDecision(
                kind=proposal.kind,
                target=proposal.target,
                reason="Model selected an installed route",
            ),
        )
