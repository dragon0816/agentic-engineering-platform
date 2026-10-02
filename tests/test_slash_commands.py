"""Deterministic Personal Agent slash-command behavior."""

from host_runtime.slash_commands import SlashCommandError, parse_slash_command


def test_parser_recognizes_the_closed_command_set() -> None:
    assert parse_slash_command("hello") is None
    assert parse_slash_command("/help").name == "help"  # type: ignore[union-attr]
    run = parse_slash_command('/run workflow engineering/check@1.0.0 {"path":"notes.md"}')
    assert run is not None
    assert run.name == "run_workflow"
    assert run.argument.startswith("engineering/check@1.0.0")
    for shorthand in ('/run 11 {"week":"2026_40W"}', '/run workflow 11 {"week":"2026_40W"}'):
        selected = parse_slash_command(shorthand)
        assert selected is not None and selected.name == "run_workflow"
        assert selected.argument == '11 {"week":"2026_40W"}'
    query = parse_slash_command("/wiki-query where is the evidence?")
    assert query is not None and query.name == "wiki_query"
    assert query.argument == "where is the evidence?"


def test_parser_fails_closed_for_unknown_or_ambiguous_commands() -> None:
    for message, code in (
        ("/unknown", "unknown_slash_command"),
        ("/run task example", "run_requires_workflow"),
        ("/help extra", "help_accepts_no_arguments"),
    ):
        try:
            parse_slash_command(message)
        except SlashCommandError as error:
            assert error.code == code
        else:
            raise AssertionError("unknown command was accepted")
