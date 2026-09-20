# Agentic Engineering Platform

Unified engineering automation platform for agentic reasoning, deterministic workflows, enterprise knowledge, tools/MCP capabilities, and evaluation.

Phase 1 provides validated contracts and an in-memory Task discovery / Bridge
advertisement proof. It contains no production executor, provider integration or service.

## Development

Python 3.11 or newer:

```sh
python -m venv .venv
# Activate .venv (Windows: .venv\Scripts\Activate.ps1; POSIX: source .venv/bin/activate)
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m build
python -m pip check
```

CI verifies on Windows and Linux with Python 3.11 and 3.12. The pure proof is in
`workflow.proof.advertise_sample`; `tests/test_registry.py::test_vertical_proof`
loads the sample manifest and Bridge fixture and exercises the complete chain.

See [contract semantics](docs/CONTRACTS.md), [implementation/source decisions](docs/PHASE_1_PLAN.md),
[Phase 1 requirements](docs/phases/PHASE_1_FOUNDATION.md) and [handoff](HANDOFF.md).
Profiles and sample assets remain outside package code so contributions do not
require runtime edits. Future package distribution is outside this slice.
