"""Checking a drafted Workflow against the machine that would run it.

Pure, and the reason this whole capability is worth building. A model that
writes a Workflow writes JSON; whether that JSON *runs* is a question with a
definite answer, and this asks it here rather than discovering it when
somebody presses go.

Three kinds of wrong, and all three are caught before anybody sees a draft:

1. It is not a Workflow. The contract says so, and says where.
2. It names a capability this machine does not have. The model is told which,
   and what this machine does have.
3. It feeds a capability something that capability has no field for, or
   leaves out a field it cannot run without. This is the check that turns a
   plausible draft into a runnable one, and it is possible only because an
   installed capability carries its own input contract.

Every problem comes back as a sentence, because the next thing that happens
to it is that a model is asked to fix it. A pydantic error dump is a bad
prompt and a worse thing to show a person.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from capabilities.runtime import InstalledCapabilities
from common.assets import AssetIdentity, StepInput, WorkflowManifest, WorkflowStep
from common.base import Contract


def field_names(model: type[Contract]) -> tuple[tuple[str, bool, str], ...]:
    """Each field of a capability's input: its name, whether it is required,
    and how its type reads. What a model needs to fill one in."""
    described: list[tuple[str, bool, str]] = []
    for name, field in model.model_fields.items():
        annotation = field.annotation
        shown = getattr(annotation, "__name__", None) or str(annotation)
        described.append((name, field.is_required(), shown))
    return tuple(described)


def _where(error: Mapping[str, Any]) -> str:
    location = ".".join(str(part) for part in error.get("loc", ()))
    return location or "the document"


def contract_problems(invalid: ValidationError) -> tuple[str, ...]:
    """A validation error as sentences. Each names one place and one fault,
    which is what a reader and a model can both act on."""
    return tuple(
        f"{_where(error)}: {error.get('msg', 'is not valid')}" for error in invalid.errors()
    )


def _step_problems(index: int, step: WorkflowStep, installed: InstalledCapabilities) -> list[str]:
    identity = step.capability
    named = f"{identity.namespace}/{identity.name}@{identity.version}"
    binding = installed.get(identity)
    if binding is None:
        return [f"step {index} uses {named}, which is not installed on this machine"]
    fields = {name: required for name, required, _type in field_names(binding.input_model)}
    problems: list[str] = []
    for given in sorted(step.inputs):
        if given not in fields:
            known = ", ".join(sorted(fields)) or "nothing"
            problems.append(
                f"step {index} gives {named} an input called {given!r}, which it does "
                f"not take; it takes: {known}"
            )
    for name, required in sorted(fields.items()):
        if required and name not in step.inputs:
            problems.append(f"step {index} leaves out {name!r}, which {named} cannot run without")
    return problems


def unusable(
    manifest: WorkflowManifest, installed: InstalledCapabilities, *, namespace: str
) -> tuple[str, ...]:
    """Every reason this drafted Workflow would not run here, in order.

    An empty result means it would run: every step is installed, every input
    is one that step takes, and nothing required is missing. It does not mean
    the Workflow does what the SOP asked -- no check can say that, and this
    one does not pretend to.
    """
    problems: list[str] = []
    identity = manifest.metadata.identity
    if identity.namespace != namespace:
        problems.append(
            f"the workflow is in namespace {identity.namespace!r}; it was asked for in "
            f"{namespace!r}"
        )
    if manifest.metadata.lifecycle != "draft":
        problems.append(
            f"the workflow calls itself {manifest.metadata.lifecycle!r}; a drafted one is "
            "a draft until somebody validates it"
        )
    for index, step in enumerate(manifest.steps):
        if isinstance(step, AssetIdentity):
            problems.append(
                f"step {index} names a workflow to run whole; draft each step's capability "
                "instead, so every step can be checked"
            )
            continue
        problems.extend(_step_problems(index, step, installed))
    declared = set(manifest.dependencies.local_capabilities)
    needed: set[str] = set()
    for step in manifest.steps:
        if not isinstance(step, WorkflowStep):
            continue
        binding = installed.get(step.capability)
        if binding is not None:
            needed.add(binding.spec.name)
    missing = sorted(needed - declared)
    if missing:
        problems.append(
            "dependencies.local_capabilities must name every capability the steps use, "
            f"and leaves out: {', '.join(missing)}"
        )
    return tuple(problems)


def review(
    data: object, installed: InstalledCapabilities, *, namespace: str
) -> tuple[WorkflowManifest | None, tuple[str, ...]]:
    """Parse and check one drafted Workflow.

    Returns the manifest when it would run here, otherwise nothing and the
    reasons. The two are never both empty and never both filled.
    """
    try:
        manifest = WorkflowManifest.model_validate(data)
    except ValidationError as invalid:
        return None, contract_problems(invalid)
    problems = unusable(manifest, installed, namespace=namespace)
    if problems:
        return None, problems
    return manifest, ()


def rendered(manifest: WorkflowManifest, installed: InstalledCapabilities) -> str:
    """The draft in words, for somebody deciding whether to keep it.

    The same job the weekly report's plan does: a person should be able to
    read what a thing would do without reading its JSON.
    """
    identity = manifest.metadata.identity
    lines = [
        f"{identity.namespace}/{identity.name}@{identity.version}  ({manifest.metadata.lifecycle})",
        manifest.description,
        "",
        f"{len(manifest.steps)} step(s):",
    ]
    for index, step in enumerate(manifest.steps):
        if not isinstance(step, WorkflowStep):
            lines.append(f"  {index}. {step.namespace}/{step.name}@{step.version} (whole workflow)")
            continue
        binding = installed.get(step.capability)
        what = binding.spec.description if binding is not None else "not installed"
        lines.append(f"  {index}. {step.capability.name} -- {what}")
        for name in sorted(step.inputs):
            source = step.inputs[name]
            if isinstance(source, StepInput):
                path = "".join(f"[{part!r}]" for part in source.path)
                lines.append(f"       {name} <- step {source.step_index}{path}")
            else:
                path = "".join(f"[{part!r}]" for part in source.path)
                lines.append(f"       {name} <- what the run was asked for{path}")
    lines.append("")
    lines.append("Nothing is installed by drafting this. Read it, then install it deliberately.")
    return "\n".join(lines)


def catalogue(installed: InstalledCapabilities) -> tuple[dict[str, Any], ...]:
    """Everything this machine can actually run, described for a drafter.

    Only what is installed here. A drafter shown the whole Registry would
    write Workflows this machine cannot run, which is the failure this
    capability exists to prevent.
    """
    described: list[dict[str, Any]] = []
    for spec in installed.discover():
        binding = installed.get(spec.identity)
        if binding is None:  # pragma: no cover - discover lists what get finds
            continue
        described.append(
            {
                "capability": spec.identity.model_dump(mode="json"),
                "name": spec.name,
                "description": spec.description,
                "side_effect": spec.side_effect,
                "inputs": [
                    {"name": name, "required": required, "type": shown}
                    for name, required, shown in field_names(binding.input_model)
                ],
                "outputs": [name for name, _required, _type in field_names(binding.output_model)],
            }
        )
    return tuple(described)


def names(installed: InstalledCapabilities) -> tuple[str, ...]:
    return tuple(spec.name for spec in installed.discover())


def steps_of(manifest: WorkflowManifest) -> Sequence[WorkflowStep]:
    return [step for step in manifest.steps if isinstance(step, WorkflowStep)]
