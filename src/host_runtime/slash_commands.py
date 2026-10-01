"""Closed deterministic commands for the Personal Agent conversation UI."""

from __future__ import annotations

from typing import Literal

from common.assets import RegistryContract

SlashCommandName = Literal[
    "help",
    "run_workflow",
    "wiki_convert",
    "wiki_ingest",
    "wiki_lint",
    "wiki_query",
    "problem",
]


class SlashCommandSpec(RegistryContract):
    name: SlashCommandName
    invocation: str
    description: str


class SlashCommandInvocation(RegistryContract):
    name: SlashCommandName
    argument: str = ""


COMMANDS = (
    SlashCommandSpec(name="help", invocation="/help", description="Show supported commands."),
    SlashCommandSpec(
        name="run_workflow",
        invocation="/run workflow ",
        description="Run an exact installed Workflow with optional JSON arguments.",
    ),
    SlashCommandSpec(
        name="wiki_convert",
        invocation="/wiki-convert ",
        description="Run the installed wiki-convert Workflow.",
    ),
    SlashCommandSpec(
        name="wiki_ingest",
        invocation="/wiki-ingest ",
        description="Run the installed wiki-ingest Workflow.",
    ),
    SlashCommandSpec(
        name="wiki_lint",
        invocation="/wiki-lint ",
        description="Run the installed wiki-lint Workflow.",
    ),
    SlashCommandSpec(
        name="wiki_query",
        invocation="/wiki-query ",
        description="Ask one installed Knowledge wiki with grounded citations.",
    ),
    SlashCommandSpec(
        name="problem",
        invocation="/problem ",
        description="Save a governed local problem report from this conversation.",
    ),
)


class SlashCommandError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def parse_slash_command(message: str) -> SlashCommandInvocation | None:
    text = message.strip()
    if not text.startswith("/"):
        return None
    command, _, argument = text.partition(" ")
    argument = argument.strip()
    names: dict[str, SlashCommandName] = {
        "/help": "help",
        "/wiki-convert": "wiki_convert",
        "/wiki-ingest": "wiki_ingest",
        "/wiki-lint": "wiki_lint",
        "/wiki-query": "wiki_query",
        "/problem": "problem",
    }
    if command == "/run":
        noun, _, remainder = argument.partition(" ")
        if noun != "workflow":
            raise SlashCommandError("run_requires_workflow")
        return SlashCommandInvocation(name="run_workflow", argument=remainder.strip())
    name = names.get(command)
    if name is None:
        raise SlashCommandError("unknown_slash_command")
    if name == "help" and argument:
        raise SlashCommandError("help_accepts_no_arguments")
    return SlashCommandInvocation(name=name, argument=argument)
