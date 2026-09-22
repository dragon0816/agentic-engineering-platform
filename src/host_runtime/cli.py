"""Command line interface for the local-only Windows technical preview."""

import argparse
import sys
import uuid
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantic import ValidationError

from common.execution import TraceIdentifiers
from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.runtime import enrollment_request, inspect_host


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aep-host")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="inspect the local preview host")
    doctor.add_argument("--config", required=True, type=Path)
    doctor.add_argument("--json", action="store_true")
    request = commands.add_parser(
        "enrollment-request", help="write an inspectable credential-free request"
    )
    request.add_argument("--config", required=True, type=Path)
    request.add_argument("--output", type=Path)
    commands.add_parser("version", help="show the installed package version")
    return parser


def _load(path: Path) -> CompanyHostConfiguration:
    return CompanyHostConfiguration.model_validate_json(path.read_text(encoding="utf-8-sig"))


def _trace() -> TraceIdentifiers:
    value = uuid.uuid4().hex
    return TraceIdentifiers(
        trace_id=f"trace-{value}", request_id=f"request-{value}", span_id=f"span-{value}"
    )


def _package_version() -> str:
    try:
        return version("agentic-engineering-platform")
    except PackageNotFoundError:
        return "uninstalled"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "version":
        print(_package_version())
        return 0
    try:
        config = _load(args.config)
    except (OSError, ValidationError, ValueError):
        print(
            "configuration is missing or invalid; no input values were displayed",
            file=sys.stderr,
        )
        return 2
    if args.command == "doctor":
        report = inspect_host(config)
        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print(f"host status: {report.status}")
            for check in report.checks:
                print(f"[{check.status}] {check.name}: {check.detail}")
            for limitation in report.limitations:
                print(f"LIMITATION: {limitation}")
        return 0 if report.status == "ready" else 1
    request = enrollment_request(config, _trace())
    payload = request.model_dump_json(indent=2) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
