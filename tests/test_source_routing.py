"""Offline source characterization; production tools and models are never loaded."""

import asyncio
import hashlib
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CASES: list[dict[str, Any]] = json.loads(
    (FIXTURES / "routing_cases.json").read_text(encoding="utf-8")
)


def source_router() -> tuple[Any, AsyncMock]:
    source = (FIXTURES / "source_router.txt").read_text(encoding="utf-8")
    assert hashlib.sha256(source.encode()).hexdigest() == (
        "dcbd706da14d43a1168fb4eaa068aee794186f4e94de8c9c01cac8c94b514cb3"
    )
    module = ModuleType("pinned_source_router")
    exec(compile(source, "source_router.txt", "exec"), module.__dict__)
    definitions = {
        "run_testing": {"name": "run_testing", "commands": {"run": "run"}},
        "release_package": {"name": "release_package", "commands": {"publish": "release"}},
        "build_package": {"name": "build_package", "commands": {"build": "build"}},
    }
    model = AsyncMock(return_value={"direct_response": "fallback"})
    router = module.TaskRouter(
        SimpleNamespace(get_skill=definitions.get, list_skills=lambda: list(definitions.values())),
        SimpleNamespace(list_mcps=lambda: []),
        SimpleNamespace(parse_task=model),
        None,
        {},
    )
    router._execute_tool = AsyncMock(return_value="executed")
    router._dispatch_skill = AsyncMock(return_value="dispatched")
    return router, model


@pytest.mark.parametrize("case", CASES, ids=[case["message"] for case in CASES])
def test_source_precedence_and_aliases(case: dict[str, Any]) -> None:
    router, model = source_router()
    asyncio.run(router.route(case["message"]))
    if case["skill"] is None:
        model.assert_awaited_once()
    elif case["args"] is not None:
        model.assert_not_awaited()
        args = router._execute_tool.call_args.args
        assert args[0]["name"] == case["skill"]
        assert args[1] == case["command"]
        assert args[3]["args"] == case["args"]
    else:
        model.assert_not_awaited()
        assert router._dispatch_skill.call_args.args[1] == case["skill"]


def test_source_forwards_actor_and_files() -> None:
    router, model = source_router()
    asyncio.run(router.route("run_testing.run args", user_info={"id": "user"}, _files=["ref"]))
    parameters = router._execute_tool.call_args.args[3]
    assert parameters["_user"] == {"id": "user"}
    assert parameters["_files"] == ["ref"]
    model.assert_not_awaited()


def test_source_unknown_explicit_skill_falls_through() -> None:
    router, model = source_router()
    asyncio.run(router.route("unknown.command"))
    model.assert_awaited_once()
