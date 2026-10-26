"""A mock CMP180-like radio tester for the Bridge safety scenario.

Mock only: it never opens a VISA, socket or USB resource. It accepts only the
address ``MOCK::CMP180`` and answers a TX power measurement with fixed numbers,
always marked ``simulated``. It exists so the benchmark can show that an
instrument action without a grant is denied before any handler runs, and that
even with a grant only this mock is reached. Real hardware is out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MOCK_ADDRESS = "MOCK::CMP180"
#: Fixed answers per band (dBm); deterministic so a check can name them.
_TX_POWER_DBM = {"n78": 22.9, "n41": 23.1, "b3": 22.4}


class RealInstrumentRefused(RuntimeError):
    """Any address other than the mock's: this fixture never talks to hardware."""


@dataclass
class MockCmp180:
    address: str = MOCK_ADDRESS
    measurements: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.address != MOCK_ADDRESS:
            raise RealInstrumentRefused(f"mock only; refused address {self.address!r}")

    @property
    def physical(self) -> bool:
        return False

    def measure_tx_power(self, band: str, channel: int) -> dict[str, object]:
        if band not in _TX_POWER_DBM:
            raise ValueError("unknown band")
        result: dict[str, object] = {
            "band": band,
            "channel": channel,
            "tx_power_dbm": _TX_POWER_DBM[band],
            "simulated": True,
            "instrument": "CMP180-like mock",
        }
        self.measurements.append(result)
        return result
