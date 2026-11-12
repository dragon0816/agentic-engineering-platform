"""Simulate a real unavailable execution dependency, never an application grant gate."""

from collections.abc import Callable

from capabilities.runtime import InstalledCapabilities
from common.assets import AssetIdentity, ExecutionDependencies


def unavailable_dependency(
    installed: InstalledCapabilities, target: AssetIdentity
) -> Callable[[], None]:
    original = installed.get(target)
    assert original is not None and "fixture.unavailable" not in installed.names

    def replace(dependencies: ExecutionDependencies) -> None:
        installed.unregister(target)
        installed.register(
            original.spec,
            original.handler,
            original.input_model,
            original.output_model,
            dependencies,
            original.secrets,
            timeout_seconds=original.timeout_seconds,
        )

    replace(
        original.dependencies.model_copy(
            update={
                "local_capabilities": (
                    *original.dependencies.local_capabilities,
                    "fixture.unavailable",
                )
            }
        )
    )
    return lambda: replace(original.dependencies)
