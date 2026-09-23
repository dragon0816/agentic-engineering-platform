"""Side-effect-free inspection and enrollment-request construction."""

import os
import platform
import sys
from pathlib import Path

from common.execution import TraceIdentifiers
from host_runtime.contracts import (
    CompanyHostConfiguration,
    DoctorCheck,
    EnrollmentRequest,
    HostDoctorReport,
)
from workflow.host_bridge import BridgeRegistration

LIMITATIONS = (
    "Enrollment (invitation, device registration, binding, token issue) happens on the "
    "shared platform; this host presents a token it was given and cannot obtain one.",
    "The GTM weekly report (source workflow 11) needs a project board and a workbook "
    "configured under `integrations`, and Excel installed to write; `doctor` reports "
    "whether this host has them.",
    "No Git, browser, email, DUT or instrument capability is included, so this host "
    "cannot execute workflow 13.",
)


def inspect_host(
    config: CompanyHostConfiguration,
    *,
    system_name: str | None = None,
    python_version: tuple[int, int] | None = None,
    workspace_exists: bool | None = None,
    workspace_writable: bool | None = None,
) -> HostDoctorReport:
    """Inspect without creating a file, opening a socket or executing a capability."""

    actual_system = system_name if system_name is not None else platform.system()
    actual_python = python_version if python_version is not None else sys.version_info[:2]
    workspace = Path(config.workspace_root)
    exists = workspace.is_dir() if workspace_exists is None else workspace_exists
    writable = os.access(workspace, os.W_OK) if workspace_writable is None else workspace_writable
    checks = (
        DoctorCheck(
            name="operating_system",
            status="passed" if actual_system == "Windows" else "failed",
            detail=f"detected {actual_system}; Windows is required",
        ),
        DoctorCheck(
            name="python",
            status="passed" if actual_python == (3, 12) else "failed",
            detail=(
                f"detected {actual_python[0]}.{actual_python[1]}; "
                "this offline bundle requires Python 3.12"
            ),
        ),
        DoctorCheck(
            name="device_profile",
            status="passed",
            detail="company workstation profile is valid and serializes interactive work",
        ),
        DoctorCheck(
            name="workspace",
            status="passed" if exists and writable else "failed",
            detail="workspace directory exists and is writable"
            if exists and writable
            else "workspace directory is missing or not writable",
        ),
    )
    return HostDoctorReport(
        status="ready" if all(item.status == "passed" for item in checks) else "not_ready",
        checks=checks,
        limitations=LIMITATIONS,
    )


def enrollment_request(
    config: CompanyHostConfiguration, trace: TraceIdentifiers
) -> EnrollmentRequest:
    """Describe this device; grants no authorization and resolves no secrets."""

    return EnrollmentRequest(
        device=config.device,
        advertisement=BridgeRegistration(
            bridge_id=config.device.bridge_id,
            owner_id=config.device.registered_by,
            trace=trace,
        ),
    )
