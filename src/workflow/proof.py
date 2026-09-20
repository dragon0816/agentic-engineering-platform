"""Pure metadata proof: manifest -> Registry -> discovery -> Bridge advertisement."""

from agent.registry import TaskRegistry
from common.assets import TaskManifest
from workflow.host_bridge import BridgeRegistration


def advertise_sample(
    manifest: TaskManifest,
    registry: TaskRegistry,
    bridge: BridgeRegistration,
) -> BridgeRegistration:
    """Advertise a discovered Task backed by an already installed read capability.

    Mutates only the provided in-memory Registry. Does not install or execute a Task.
    The caller supplies the Bridge's installed capabilities explicitly.
    """
    checked = TaskManifest.model_validate(manifest)
    installed = BridgeRegistration.model_validate(bridge)
    capability = next(
        (cap for cap in installed.capabilities if cap.identity == checked.capability),
        None,
    )
    if capability is None or capability.side_effect != "read":
        raise ValueError("sample requires an installed capability classified read")
    names = {cap.name for cap in installed.capabilities}
    if not set(checked.dependencies.local_capabilities).issubset(names):
        raise ValueError("sample is missing a declared local capability")
    if checked.dependencies.central_required or checked.secrets:
        raise ValueError("sample proof supports no required central services or secrets")
    if (checked.input_contract, checked.output_contract) != (
        capability.input_contract,
        capability.output_contract,
    ):
        raise ValueError("sample Task and installed capability contracts must match")
    if checked.metadata.lifecycle != "published":
        raise ValueError("sample requires published metadata for discovery")
    registry.register(checked)
    discovered = registry.discover(namespace=checked.metadata.identity.namespace)
    task = next(task for task in discovered if task.metadata.identity == checked.metadata.identity)
    tasks = tuple(dict.fromkeys((*installed.installed_tasks, task.metadata.identity)))
    return BridgeRegistration.model_validate({**installed.model_dump(), "installed_tasks": tasks})
