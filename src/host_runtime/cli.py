"""Command line interface for the company-workstation host.

Four things an operator does: inspect the machine, export an enrollment
request, ask the resident Agent to do something, and leave the Telegram
ingress running. Every command reads one `host.json` and the files beside it
in the workspace; none of them contacts the shared platform, which does not
have an authenticated transport yet.
"""

import argparse
import asyncio
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantic import ValidationError

from channels.telegram import TelegramIngress
from common.execution import TraceIdentifiers
from common.local_agent import LocalAgentRequest
from host_runtime.agent import LocalAgentOutcome
from host_runtime.contracts import CompanyHostConfiguration, HostDoctorReport
from host_runtime.host import HostError, HostLayout, HostRuntime, build_runtime, host_report
from host_runtime.runtime import enrollment_request


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aep-host")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="inspect this machine and what it has been given")
    doctor.add_argument("--config", required=True, type=Path)
    doctor.add_argument("--json", action="store_true")
    request = commands.add_parser(
        "enrollment-request", help="write an inspectable credential-free request"
    )
    request.add_argument("--config", required=True, type=Path)
    request.add_argument("--output", type=Path)
    ask = commands.add_parser("ask", help="send one request to the resident Agent")
    ask.add_argument("--config", required=True, type=Path)
    ask.add_argument("--actor", help="the platform actor to act as; the device owner by default")
    ask.add_argument("--namespace", help="the namespace to address; this host's by default")
    ask.add_argument("--json", action="store_true")
    ask.add_argument("message", help="a skill command such as release.package, or a description")
    status = commands.add_parser("status", help="what this Bridge has installed and has run")
    status.add_argument("--config", required=True, type=Path)
    status.add_argument("--json", action="store_true")
    telegram = commands.add_parser("telegram", help="poll Telegram until interrupted")
    telegram.add_argument("--config", required=True, type=Path)
    telegram.add_argument("--once", action="store_true", help="poll a single time and stop")
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


def _print_report(report: HostDoctorReport) -> None:
    print(f"host status: {report.status}")
    print(f"resident agent: {report.runtime}")
    for check in report.checks:
        print(f"[{check.status}] {check.name}: {check.detail}")
    for limitation in report.limitations:
        print(f"LIMITATION: {limitation}")


def _print_outcome(outcome: LocalAgentOutcome) -> None:
    if outcome.refusal is not None:
        print(f"refused: {outcome.refusal}")
        return
    decision = outcome.decision
    if decision is not None:
        target = decision.target
        named = f" {target.namespace}/{target.name}@{target.version}" if target else ""
        print(f"route: {decision.kind}{named} ({decision.reason})")
    if outcome.capability is not None:
        print(f"capability: {outcome.capability.status}")
    if outcome.workflow is not None:
        run = outcome.workflow.run
        print(f"run {run.run_id}: {run.status}, {run.completed_steps} step(s) completed")
        if run.failure is not None:
            print(f"failure: {run.failure.code}")
    if outcome.unrecorded is not None:
        print(f"the run record could not be written: {outcome.unrecorded}")


def _ask(
    runtime: HostRuntime, message: str, actor: str | None, namespace: str | None, as_json: bool
) -> int:
    chosen = namespace if namespace is not None else runtime.config.namespace
    if chosen is None:
        print(
            "no namespace is configured; pass --namespace or set it in host.json",
            file=sys.stderr,
        )
        return 2
    try:
        request = LocalAgentRequest(
            ingress="local",
            actor=actor if actor is not None else runtime.actor,
            bridge_id=runtime.config.device.bridge_id,
            namespace=chosen,
            message=message,
            trace=_trace(),
        )
    except ValidationError:
        print("that request was refused before it was routed", file=sys.stderr)
        return 2
    outcome = asyncio.run(runtime.agent.handle(request))
    if as_json:
        print(outcome.model_dump_json(indent=2))
    else:
        _print_outcome(outcome)
    return 0 if outcome.refusal is None else 1


def _status(runtime: HostRuntime, as_json: bool) -> int:
    snapshot = runtime.agent.snapshot(observed_at=datetime.now(UTC))
    if as_json:
        print(snapshot.model_dump_json(indent=2))
        return 0
    print(f"bridge {snapshot.device.bridge_id} observed at {snapshot.observed_at.isoformat()}")
    print(f"installed: {len(snapshot.installed)} asset(s)")
    for asset in snapshot.installed:
        print(f"  {asset.identity.namespace}/{asset.identity.name}@{asset.identity.version}")
    print(f"runs: {len(snapshot.runs)}")
    for run in snapshot.runs[-10:]:
        print(f"  {run.run_id} {run.workflow.name}: {run.status} ({run.actor})")
    return 0


def _telegram(runtime: HostRuntime, once: bool) -> int:
    ingress: TelegramIngress | None = runtime.telegram
    if ingress is None:
        print("no Telegram ingress is configured on this host", file=sys.stderr)
        return 2
    if once:
        result = asyncio.run(ingress.poll_once())
        for delivery in result.deliveries:
            print(f"{delivery.update_id}: {delivery.disposition}")
        if result.failure is not None:
            print(f"failure: {result.failure.code}", file=sys.stderr)
            return 1
        return 0

    async def loop() -> int:
        stop = asyncio.Event()
        try:
            failure = await ingress.run(stop)
        except KeyboardInterrupt:  # pragma: no cover - interactive only
            stop.set()
            return 0
        if failure is not None:
            print(f"the Telegram ingress stopped: {failure.code}", file=sys.stderr)
            return 1
        return 0

    try:
        return asyncio.run(loop())
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("stopped")
        return 0


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
    layout = HostLayout.under(config.workspace_root)
    if args.command == "doctor":
        report = host_report(config, layout)
        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            _print_report(report)
        return 0 if report.status == "ready" else 1
    if args.command == "enrollment-request":
        request = enrollment_request(config, _trace())
        payload = request.model_dump_json(indent=2) + "\n"
        if args.output is None:
            print(payload, end="")
        else:
            args.output.write_text(payload, encoding="utf-8")
            print(f"wrote {args.output}")
        return 0
    try:
        runtime = build_runtime(config, layout=layout)
    except HostError as error:
        print(f"this host is not ready: {error.code} ({error.path})", file=sys.stderr)
        return 2
    with runtime:
        if args.command == "ask":
            return _ask(runtime, args.message, args.actor, args.namespace, args.json)
        if args.command == "status":
            return _status(runtime, args.json)
        return _telegram(runtime, args.once)


if __name__ == "__main__":
    raise SystemExit(main())
