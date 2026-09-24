"""Drafting a Workflow from a written procedure.

The architecture's own lifecycle is

    experience -> candidate -> **draft** -> validation/evaluation
               -> human review -> published

and this stops at `draft`. So the tests are mostly about the check between
the model and the draft: a model that writes JSON writes plausible JSON, and
whether it *runs on this machine* is a question with a definite answer.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import InstalledCapabilities
from capabilities.workflow_author import review
from capabilities.workflow_author.contracts import DraftWorkflowRequest, WorkflowDraft
from capabilities.workflow_author.draft import draft_workflow
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext, TraceIdentifiers
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

TRACE = TraceIdentifiers(trace_id="t-1", request_id="r-1", span_id="s-1")


class ReadInput(Contract):
    path: str
    encoding: str = "utf-8"


class ReadOutput(Contract):
    content: str = ""


class CountInput(Contract):
    content: str


class CountOutput(Contract):
    lines: int = 0


def spec(name: str, capability: str, effect: str = "read") -> CapabilitySpec:
    policy: dict[str, Any] = {
        "required_permissions": [f"{capability}.use"],
        "policy_refs": [f"{capability}-policy"],
    }
    if effect != "read":
        policy["approval_required"] = True
    return CapabilitySpec.model_validate(
        {
            "identity": {"namespace": "demo", "name": capability, "version": "1.0.0"},
            "name": name,
            "description": f"the {capability} capability",
            "input_contract": f"demo.{capability}.input.v1",
            "output_contract": f"demo.{capability}.output.v1",
            "side_effect": effect,
            "policy": policy,
        }
    )


async def _nothing(context: RequestContext, inputs: Contract) -> Contract:
    return ReadOutput()


def machine() -> InstalledCapabilities:
    """A machine with two capabilities, the second taking the first's output."""
    installed = InstalledCapabilities()
    installed.register(
        spec("demo.read", "read-file"),
        _nothing,
        ReadInput,
        ReadOutput,
        ExecutionDependencies(central_required=False),
    )
    installed.register(
        spec("demo.count", "count-lines"),
        _nothing,
        CountInput,
        CountOutput,
        ExecutionDependencies(central_required=False),
    )
    return installed


def manifest(**changes: Any) -> dict[str, Any]:
    """A draft that would run: both steps installed, inputs real, the second
    fed from the first."""
    document: dict[str, Any] = {
        "metadata": {
            "identity": {"namespace": "engineering", "name": "count-a-file", "version": "1.0.0"},
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "team",
            "lifecycle": "draft",
        },
        "kind": "workflow",
        "description": "Read a file and count its lines",
        "execution": {"mode": "local"},
        "dependencies": {
            "central_required": False,
            "local_capabilities": ["demo.read", "demo.count"],
        },
        "input_contract": "engineering.count-a-file.request.v1",
        "output_contract": "demo.count-lines.output.v1",
        "steps": [
            {
                "capability": {"namespace": "demo", "name": "read-file", "version": "1.0.0"},
                "inputs": {"path": {"source": "run", "path": ["path"]}},
            },
            {
                "capability": {"namespace": "demo", "name": "count-lines", "version": "1.0.0"},
                "inputs": {"content": {"source": "step", "step_index": 0, "path": ["content"]}},
            },
        ],
    }
    document.update(changes)
    return document


def checked(
    document: dict[str, Any], namespace: str = "engineering"
) -> tuple[Any, tuple[str, ...]]:
    return review.review(document, machine(), namespace=namespace)


# -- the check ------------------------------------------------------------


def test_a_draft_that_would_run_comes_back_whole() -> None:
    drafted, problems = checked(manifest())
    assert problems == ()
    assert drafted is not None
    assert drafted.metadata.identity.name == "count-a-file"
    assert len(drafted.steps) == 2


def test_a_step_naming_something_not_installed_is_caught_here() -> None:
    """The failure this whole capability exists to prevent: a Workflow that
    reads well and cannot run on the machine it was written for."""
    document = manifest()
    document["steps"][0]["capability"]["name"] = "invented-capability"
    drafted, problems = checked(document)
    assert drafted is None
    assert any("not installed on this machine" in problem for problem in problems)
    assert any("invented-capability" in problem for problem in problems)


def test_an_input_a_capability_does_not_take_is_caught_and_the_real_ones_named() -> None:
    """The check that turns a plausible draft into a runnable one. It is
    possible only because an installed capability carries its own contract."""
    document = manifest()
    document["steps"][0]["inputs"]["filename"] = {"source": "run", "path": []}
    drafted, problems = checked(document)
    assert drafted is None
    named = " ".join(problems)
    assert "'filename'" in named and "does not take" in named
    assert "encoding, path" in named, "it says what the capability does take"


def test_a_required_input_left_out_is_caught() -> None:
    document = manifest()
    document["steps"][1]["inputs"] = {}
    drafted, problems = checked(document)
    assert drafted is None
    assert any("'content'" in problem and "cannot run without" in problem for problem in problems)


def test_an_optional_input_left_out_is_fine() -> None:
    """`encoding` has a default, so leaving it out is not a defect."""
    document = manifest()
    assert "encoding" not in document["steps"][0]["inputs"]
    assert checked(document)[1] == ()


def test_a_step_reaching_forward_is_refused_by_the_contract_itself() -> None:
    """Already a rule of `WorkflowManifest`; this pins that the drafter gets
    it as a sentence rather than as a crash."""
    document = manifest()
    document["steps"][0]["inputs"]["path"] = {"source": "step", "step_index": 1, "path": []}
    drafted, problems = checked(document)
    assert drafted is None
    assert any("earlier steps" in problem for problem in problems)


def test_a_draft_that_calls_itself_published_is_refused() -> None:
    """The architecture's line: a candidate does not become trusted because
    an LLM generated it."""
    document = manifest()
    document["metadata"]["lifecycle"] = "published"
    drafted, problems = checked(document)
    assert drafted is None
    assert any("a draft until somebody validates it" in problem for problem in problems)


def test_a_draft_in_the_wrong_namespace_is_refused() -> None:
    drafted, problems = checked(manifest(), namespace="somewhere-else")
    assert drafted is None
    assert any("it was asked for in" in problem for problem in problems)


def test_undeclared_dependencies_are_caught() -> None:
    """The engine refuses a run whose host lacks a declared capability, so a
    manifest that declares none would pass that gate by saying nothing."""
    document = manifest()
    document["dependencies"]["local_capabilities"] = ["demo.read"]
    drafted, problems = checked(document)
    assert drafted is None
    assert any("leaves out: demo.count" in problem for problem in problems)


def test_a_step_that_is_a_whole_workflow_is_refused() -> None:
    """Valid in the contract, but nothing here could check what it would do."""
    document = manifest()
    document["steps"][1] = {"namespace": "demo", "name": "other", "version": "1.0.0"}
    drafted, problems = checked(document)
    assert drafted is None
    assert any("draft each step's capability" in problem for problem in problems)


def test_something_that_is_not_a_workflow_at_all_says_where() -> None:
    drafted, problems = checked({"steps": []})
    assert drafted is None
    assert problems, "a shapeless document is refused with its reasons"
    assert all(": " in problem for problem in problems), "each names a place and a fault"


# -- what the drafter is shown --------------------------------------------


def test_the_drafter_is_shown_only_what_this_machine_has() -> None:
    """A drafter shown the whole Registry writes Workflows this machine
    cannot run."""
    described = review.catalogue(machine())
    assert [item["name"] for item in described] == ["demo.count", "demo.read"]
    read = next(item for item in described if item["name"] == "demo.read")
    assert {"name": "path", "required": True, "type": "str"} in read["inputs"]
    assert {"name": "encoding", "required": False, "type": "str"} in read["inputs"]
    assert read["outputs"] == ["content"]
    assert read["side_effect"] == "read"


def test_the_catalogue_says_which_capabilities_change_things() -> None:
    """So a procedure that asks for a write is drafted onto one."""
    installed = machine()
    installed.register(
        spec("demo.write", "write-file", effect="write"),
        _nothing,
        ReadInput,
        ReadOutput,
        ExecutionDependencies(central_required=False),
    )
    effects = {item["name"]: item["side_effect"] for item in review.catalogue(installed)}
    assert effects["demo.write"] == "write"
    assert effects["demo.read"] == "read"


def test_the_draft_reads_as_words_not_json() -> None:
    drafted, _problems = checked(manifest())
    assert drafted is not None
    shown = review.rendered(drafted, machine())
    assert "2 step(s):" in shown
    assert "0. read-file -- the read-file capability" in shown
    assert "content <- step 0['content']" in shown
    assert "path <- what the run was asked for['path']" in shown
    assert "Nothing is installed by drafting this" in shown


# -- the bounded loop -----------------------------------------------------


class Model:
    """A stand-in gateway that answers with whatever it was given, in turn."""

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.asked: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.asked.append(request)
        answer = self.answers.pop(0) if self.answers else None
        return ModelResponse(
            trace=request.trace, model_alias=request.model_alias, structured_output=answer
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        """Never used: drafting asks once and reads the whole answer. It is
        here because `ModelClient` has it, and a stand-in that did not would
        not be one."""
        raise NotImplementedError("drafting does not stream")


def ask(model: Any, **changes: Any) -> WorkflowDraft:
    values: dict[str, Any] = {
        "sop": "Read the file the run names, then count its lines.",
        "namespace": "engineering",
    }
    values.update(changes)
    return draft_workflow(
        DraftWorkflowRequest(**values),
        machine(),
        model=model,
        model_alias="company",
        trace=TRACE,
    )


def test_a_good_first_answer_is_taken_and_nothing_else_is_asked() -> None:
    model = Model(manifest())
    drafted = ask(model)
    assert drafted.refusal is None
    assert drafted.manifest is not None
    assert len(model.asked) == 1
    assert drafted.attempts[0].accepted is True


def test_a_bad_answer_is_handed_its_own_problems_and_tried_again() -> None:
    """The loop is small and the check between the turns is what works."""
    wrong = manifest()
    wrong["steps"][0]["capability"]["name"] = "invented-capability"
    model = Model(wrong, manifest())
    drafted = ask(model)
    assert drafted.manifest is not None, "the second attempt was accepted"
    assert len(model.asked) == 2
    second = model.asked[1].messages[-1].text
    assert "would not run here" in second
    assert "invented-capability" in second, "it was told exactly what was wrong"
    assert [attempt.accepted for attempt in drafted.attempts] == [False, True]


def test_the_loop_stops_where_it_was_told_to(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rule 15: bounded, and a structured failure rather than spinning."""
    wrong = manifest()
    wrong["steps"][0]["capability"]["name"] = "invented-capability"
    model = Model(wrong, wrong, wrong, wrong, wrong)
    drafted = ask(model, max_attempts=2)
    assert drafted.refusal == "draft_unusable"
    assert drafted.manifest is None
    assert len(model.asked) == 2
    assert len(drafted.attempts) == 2


def test_failing_every_time_says_what_this_machine_actually_has() -> None:
    """The usual reason a draft keeps failing is that the procedure needs
    something nobody installed, and that is worth saying outright."""
    wrong = manifest()
    wrong["steps"][0]["capability"]["name"] = "invented-capability"
    drafted = ask(Model(wrong, wrong, wrong))
    assert "Installed here: demo.count, demo.read" in drafted.preview
    assert "has to be built and installed first" in drafted.preview


def test_a_machine_with_no_model_says_so_rather_than_having_no_command() -> None:
    drafted = ask(None)
    assert drafted.refusal == "model_not_configured"
    assert "host.json" in drafted.preview


def test_a_gateway_that_fails_is_a_refusal_not_an_exception() -> None:
    class Angry:
        def generate(self, request: ModelRequest) -> ModelResponse:
            raise RuntimeError("the gateway is down")

    drafted = ask(Angry())
    assert drafted.refusal == "model_unavailable"


def test_an_answer_with_no_document_is_a_refusal() -> None:
    drafted = ask(Model(None))
    assert drafted.refusal == "model_unavailable"


def test_the_request_asks_for_structured_output_and_says_nothing_of_a_provider() -> None:
    model = Model(manifest())
    ask(model)
    asked = model.asked[0]
    assert asked.requirements.structured_output is True
    assert asked.output_contract == "platform.workflow-manifest.v1"
    assert asked.model_alias == "company"
    assert asked.tools == (), "drafting offers no tool; it is not a harness"


def test_the_procedure_reaches_the_drafter_as_written() -> None:
    """Turning a procedure into steps is the judgement this exists to apply.
    A platform that pre-chewed it would be deciding the answer."""
    model = Model(manifest())
    ask(model, sop="First open the log.\nThen count how many lines it has.")
    sent = model.asked[0].messages[-1].text
    assert "First open the log." in sent
    assert "Then count how many lines it has." in sent
    assert "demo.read" in sent, "and what the machine can do"


def test_a_draft_is_returned_and_nothing_is_installed() -> None:
    """Nothing here installs, publishes or runs. The registry the drafter
    read is the same one afterwards."""
    installed = machine()
    before = {spec.identity.key for spec in installed.discover()}
    draft_workflow(
        DraftWorkflowRequest(sop="anything", namespace="engineering"),
        installed,
        model=Model(manifest()),
        model_alias="company",
        trace=TRACE,
    )
    assert {spec.identity.key for spec in installed.discover()} == before


def test_the_handler_runs_the_same_thing_off_the_event_loop() -> None:
    from capabilities.workflow_author.handlers import DRAFT_SPEC, DraftWorkflowHandler

    assert DRAFT_SPEC.side_effect == "read", "drafting changes nothing on this machine"
    # Granted like every other capability here: the default is that a member
    # is given a thing deliberately, and reaching a paid gateway is a thing
    # worth giving deliberately even though it writes nothing.
    assert DRAFT_SPEC.policy.approval_required is True
    handler = DraftWorkflowHandler(machine(), model=Model(manifest()), model_alias="company")
    context = RequestContext(
        trace=TRACE, actor="engineer", namespace="engineering", message="draft it", channel="local"
    )
    answer = asyncio.run(
        handler(context, DraftWorkflowRequest(sop="read then count", namespace="engineering"))
    )
    assert isinstance(answer, WorkflowDraft)
    assert answer.manifest is not None
