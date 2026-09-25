"""DUT adapter protocols and the opt-in fixed-executable physical boundary."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path, PureWindowsPath
from typing import Literal, Protocol

from pydantic import Field, field_validator, model_validator

from common.assets import reject_embedded_secrets
from common.base import Contract, Text
from dut.contracts import DutCommand, DutObservation, DutValidationRequest


class DutAdapter(Protocol):
    @property
    def mode(self) -> Literal["simulator", "recording", "physical"]: ...

    def execute(self, request: DutValidationRequest, command: DutCommand) -> DutObservation: ...


class PhysicalDriverConfiguration(Contract):
    """Trusted host configuration; model output can never choose this command."""

    executable: Text
    arguments: tuple[Text, ...] = ()
    timeout_seconds: int = Field(default=120, ge=1, le=3600, strict=True)

    @field_validator("executable")
    @classmethod
    def absolute_executable(cls, value: str) -> str:
        if not (Path(value).is_absolute() or PureWindowsPath(value).is_absolute()):
            raise ValueError("physical DUT driver executable must be absolute")
        return value

    @model_validator(mode="after")
    def safe_fixed_arguments(self) -> PhysicalDriverConfiguration:
        forbidden = ("password", "passwd", "token", "secret", "api-key", "apikey")
        if any(any(word in argument.lower() for word in forbidden) for argument in self.arguments):
            raise ValueError("physical driver arguments cannot carry credential material")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class SubprocessDutAdapter:
    """Run one fixed local driver without a shell and exchange typed JSON."""

    mode: Literal["physical"] = "physical"

    def __init__(self, configuration: PhysicalDriverConfiguration) -> None:
        self.configuration = PhysicalDriverConfiguration.model_validate(configuration)

    def execute(self, request: DutValidationRequest, command: DutCommand) -> DutObservation:
        payload = json.dumps(
            {
                "target": request.target.model_dump(mode="json"),
                "instrument": (
                    request.instrument.model_dump(mode="json")
                    if request.instrument is not None
                    else None
                ),
                "command": command.model_dump(mode="json"),
            }
        )
        completed = subprocess.run(
            [self.configuration.executable, *self.configuration.arguments],
            input=payload,
            text=True,
            capture_output=True,
            shell=False,
            timeout=self.configuration.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError("physical_driver_failed")
        return DutObservation.model_validate_json(completed.stdout, strict=True)
