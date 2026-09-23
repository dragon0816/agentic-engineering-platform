"""Command line interface for the company-workstation host.

What an operator does: inspect the machine, export an enrollment request, ask
the resident Agent to do something, leave the Telegram ingress running, and,
once this host holds a platform token, probe the shared platform, synchronize
what its member decided, and leave the job loop running. Every command reads
one `host.json` and the files beside it in the workspace; only the last three
open a socket, and only to the platform named there.
"""

import argparse
import asyncio
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from agent.skills import SkillManifest
from channels.telegram import TelegramIngress
from common.assets import WorkflowManifest
from common.base import Contract
from common.execution import Failure, TraceIdentifiers
from common.local_agent import LocalAgentRequest
from host_runtime.agent import LocalAgentOutcome
from host_runtime.assets import export_assets
from host_runtime.contracts import CompanyHostConfiguration, HostDoctorReport, HostLayout
from host_runtime.host import HostError, HostRuntime, build_runtime, host_report
from host_runtime.runtime import enrollment_request
from host_runtime.sync import PlatformClient, advertisement
from host_runtime.workspace import documents


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
    ask.add_argument(
        "--output",
        type=Path,
        help="write the answer to this file as UTF-8, rather than to the screen",
    )
    ask.add_argument("message", help="a skill command such as release.package, or a description")
    status = commands.add_parser("status", help="what this Bridge has installed and has run")
    status.add_argument("--config", required=True, type=Path)
    status.add_argument("--json", action="store_true")
    telegram = commands.add_parser("telegram", help="poll Telegram until interrupted")
    telegram.add_argument("--config", required=True, type=Path)
    telegram.add_argument("--once", action="store_true", help="poll a single time and stop")
    probe = commands.add_parser("probe", help="ask the shared platform whether it knows this host")
    probe.add_argument("--config", required=True, type=Path)
    probe.add_argument("--json", action="store_true")
    sync = commands.add_parser("sync", help="install what this host's member decided it may run")
    sync.add_argument("--config", required=True, type=Path)
    sync.add_argument("--json", action="store_true")
    jobs = commands.add_parser("jobs", help="run the shared platform's jobs until interrupted")
    jobs.add_argument("--config", required=True, type=Path)
    jobs.add_argument("--once", action="store_true", help="poll a single time and stop")
    jobs.add_argument("--interval", type=float, default=5.0, help="seconds between polls")
    export = commands.add_parser(
        "export-assets", help="write the shipped Skill and Workflow manifests as JSON files"
    )
    export.add_argument(
        "--out", required=True, type=Path, help="a directory; assets/ of a workspace"
    )
    commands.add_parser("version", help="show the installed package version")
    return parser


def _load(path: Path) -> CompanyHostConfiguration:
    return CompanyHostConfiguration.model_validate_json(path.read_text(encoding="utf-8-sig"))


def _why_unusable(path: Path, invalid: Exception) -> list[str]:
    """What is wrong with a host configuration, without saying what is in it.

    The file names a board, a workbook, and which environment variable holds
    which secret, so no value from it is ever printed. The field that is
    wrong is not a value, though, and refusing to name it left an operator to
    guess which of a hundred lines to look at.

    The installed version is named with it, because a field this host has
    never heard of reads exactly like a typo and is usually an installation
    older than the configuration written for it.
    """
    lines = [
        f"{path} cannot be used by this host ({_package_version()}), so nothing ran. "
        "No value from it is shown."
    ]
    if isinstance(invalid, ValidationError):
        for error in invalid.errors():
            where = ".".join(str(part) for part in error.get("loc", ())) or "(the whole file)"
            lines.append(f"  {where}: {error.get('msg', 'is not valid')}")
    else:
        # A file that is not JSON at all. The position is not a value.
        lines.append(f"  it is not valid JSON: {_json_position(invalid)}")
    return lines


def _json_position(invalid: Exception) -> str:
    line = getattr(invalid, "lineno", None)
    column = getattr(invalid, "colno", None)
    if line is None:
        return "the text could not be parsed"
    return f"line {line}, column {column}"


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


def _outcome_text(outcome: LocalAgentOutcome) -> str:
    """What happened, in the words a person reads. Rendered rather than
    printed, so the screen and a file say the same thing."""
    if outcome.refusal is not None:
        return f"refused: {outcome.refusal}"
    lines: list[str] = []
    decision = outcome.decision
    if decision is not None:
        target = decision.target
        named = f" {target.namespace}/{target.name}@{target.version}" if target else ""
        lines.append(f"route: {decision.kind}{named} ({decision.reason})")
    if outcome.capability is not None:
        lines.append(f"capability: {outcome.capability.status}")
    if outcome.workflow is not None:
        run = outcome.workflow.run
        lines.append(f"run {run.run_id}: {run.status}, {run.completed_steps} step(s) completed")
        if run.failure is not None:
            lines.append(f"failure: {run.failure.code}")
    if outcome.unrecorded is not None:
        lines.append(f"the run record could not be written: {outcome.unrecorded}")
    return chr(10).join(lines)


ContractT = TypeVar("ContractT", bound=Contract)


def _installed_namespaces(runtime: HostRuntime) -> str:
    """Which namespaces this host's installed Skills and Workflows are in."""
    found: set[str] = set()
    for skill in _manifests(runtime.layout.skills, SkillManifest):
        found.add(skill.metadata.identity.namespace)
    for workflow in _manifests(runtime.layout.workflows, WorkflowManifest):
        found.add(workflow.metadata.identity.namespace)
    names = sorted(found)
    if not names:
        return " Nothing is installed here yet; `export-assets` writes the shipped ones."
    if len(names) == 1:
        return f" Everything installed here is in `{names[0]}`."
    return " The assets installed here are in " + ", ".join(f"`{n}`" for n in names) + "."


def _manifests(directory: Path, model: type[ContractT]) -> tuple[ContractT, ...]:
    """Whatever reads cleanly. This is a message, not a gate: a manifest that
    does not parse is reported by `doctor`, and refusing to name the others
    because of it would help nobody."""
    if not directory.is_dir():
        return ()
    found: list[ContractT] = []
    for path in sorted(directory.glob("*.json")):
        try:
            found.extend(model.model_validate(item) for item in documents(path))
        except (OSError, ValidationError, ValueError):
            continue
    return tuple(found)


def _ask(
    runtime: HostRuntime,
    message: str,
    actor: str | None,
    namespace: str | None,
    as_json: bool,
    output: Path | None,
) -> int:
    chosen = namespace if namespace is not None else runtime.config.namespace
    if chosen is None:
        # The host knows which namespaces its own installed assets are in, so
        # it says them rather than leaving the reader to find out: a request
        # addresses a namespace, and there is no sensible default to guess.
        print(
            "no namespace is configured; pass --namespace or set `namespace` in host.json."
            + _installed_namespaces(runtime),
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
    rendered = outcome.model_dump_json(indent=2) if as_json else _outcome_text(outcome)
    if output is not None:
        # Written here, in UTF-8, rather than redirected by the shell.
        # Windows PowerShell's `>` writes UTF-16, so what lands in the file
        # is then not the JSON anybody asked for, and the answer carries the
        # team's own data: it has to arrive as itself.
        output.write_text(rendered + "\n", encoding="utf-8")
        print(f"wrote {output}")
    else:
        print(rendered)
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


def _platform(runtime: HostRuntime) -> PlatformClient | None:
    if runtime.platform is None:
        print("no shared platform is configured on this host", file=sys.stderr)
    return runtime.platform


def _explain(status: str, failure: Failure | None) -> str:
    """One line an operator can act on. Unreachable is said to be exactly
    that, never dressed up as a revocation."""
    if status == "answered":
        return "answered"
    if status == "unreachable":
        return "the platform could not be reached; nothing on this host changed"
    if status == "withdrawn":
        return "the platform no longer admits this host's token; nothing on this host changed"
    if status == "rejected":
        return "the platform does not recognise this host's token; check the configuration"
    code = failure.code if failure is not None else "refused"
    return f"declined: {code}"


def _probe(runtime: HostRuntime, as_json: bool) -> int:
    client = _platform(runtime)
    if client is None:
        return 2
    outcome = asyncio.run(client.probe())
    if as_json:
        print(outcome.model_dump_json(indent=2))
    elif outcome.reply is not None:
        who = outcome.reply.identity
        print(f"the platform knows this host as {who.actor} on {who.bridge_id}")
        print(f"session until {who.expires_at.isoformat()}")
    else:
        print(_explain(outcome.status, outcome.failure))
    return 0 if outcome.status == "answered" else 1


def _sync(runtime: HostRuntime, as_json: bool) -> int:
    client = _platform(runtime)
    if client is None:
        return 2
    outcome = asyncio.run(client.synchronize(runtime.layout, runtime.state))
    if as_json:
        print(outcome.model_dump_json(indent=2))
    elif outcome.status == "answered":
        print(f"{len(outcome.installed)} asset(s) installed, {outcome.selections} decision(s)")
        for item in outcome.installed:
            print(f"  {item.namespace}/{item.name}@{item.version}")
    else:
        print(_explain(outcome.status, outcome.failure))
    if outcome.status != "answered":
        return 1
    # What this host can run and what it holds, so the platform's view is
    # current. Best effort: the sync itself is done.
    advertised = asyncio.run(client.advertise(advertisement(runtime.agent, _trace().trace_id)))
    reported = asyncio.run(client.report(runtime.agent.snapshot(observed_at=datetime.now(UTC))))
    if not as_json:
        print(f"advertised: {advertised.status}; reported: {reported.status}")
    return 0


def _jobs(runtime: HostRuntime, once: bool, interval: float) -> int:
    client = _platform(runtime)
    if client is None:
        return 2
    if once:
        outcome = asyncio.run(client.poll_jobs(runtime.agent))
        for delivery in outcome.deliveries:
            settled = "settled" if delivery.settled else "not settled"
            print(f"{delivery.job_id}: {delivery.disposition}, {settled}")
        if outcome.status != "answered":
            print(_explain(outcome.status, outcome.failure), file=sys.stderr)
            return 1
        return 0

    async def loop() -> int:
        stop = asyncio.Event()
        failure = await client.run_jobs(runtime.agent, stop, interval_s=interval)
        if failure is not None:
            print(f"the job loop stopped: {failure.code}", file=sys.stderr)
            return 1
        return 0

    try:
        return asyncio.run(loop())
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("stopped")
        return 0


def _write_in_utf8() -> None:
    """Say what happened in UTF-8, whatever code page this console has.

    A Windows console outside the English-speaking world is not UTF-8, and
    what this prints is the team's own data: a project board's titles and
    comments. Printing them through a legacy code page raises
    `UnicodeEncodeError` part way through, which is a crash in place of an
    answer, and it happens on the machines this platform is for and on none
    of the machines it is written on.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):  # pragma: no cover - a stream that will not
            continue


def main(argv: Sequence[str] | None = None) -> int:
    _write_in_utf8()
    args = _parser().parse_args(argv)
    if args.command == "version":
        print(_package_version())
        return 0
    if args.command == "export-assets":
        for written in export_assets(args.out):
            print(f"wrote {written}")
        return 0
    try:
        config = _load(args.config)
    except OSError:
        print(f"cannot read {args.config}", file=sys.stderr)
        return 2
    except (ValidationError, ValueError) as invalid:
        for line in _why_unusable(args.config, invalid):
            print(line, file=sys.stderr)
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
            return _ask(runtime, args.message, args.actor, args.namespace, args.json, args.output)
        if args.command == "status":
            return _status(runtime, args.json)
        if args.command == "probe":
            return _probe(runtime, args.json)
        if args.command == "sync":
            return _sync(runtime, args.json)
        if args.command == "jobs":
            return _jobs(runtime, args.once, args.interval)
        return _telegram(runtime, args.once)


if __name__ == "__main__":
    raise SystemExit(main())
