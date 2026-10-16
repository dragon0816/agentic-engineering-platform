"""Command line interface for the company-workstation host.

What an operator does: inspect the machine, export an enrollment request, ask
the resident Agent to do something, execute an explicit task, leave the Telegram
ingress running, and, once this host holds a platform token, probe the shared
platform, synchronize what its member decided, and leave the job loop running.
Every runtime command reads one `host.json` and the files beside it in the
workspace. Model requests use the configured Gateway; platform operations use
the separately configured platform endpoint.
"""

import argparse
import asyncio
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from agent.skills import SkillManifest
from agent.task_contract import CompletionCheck, ExpectedOutput, TaskContract
from agent.task_execution import TaskScopeError
from capabilities.dut_engineering.handlers import DUT_PHYSICAL_VALIDATE_SPEC
from channels.telegram import TelegramIngress
from common.assets import WorkflowManifest
from common.base import Contract
from common.distribution import LocalStateError
from common.execution import Failure, TraceIdentifiers
from common.local_agent import LocalAgentRequest, LocalCapabilityRequest
from common.scheduling import ScheduleDefinition, ScheduledRun, ScheduleRecord
from dut.contracts import DutPhysicalValidationRequest, DutValidationEvidence
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
    task = commands.add_parser("run-task", help="execute one explicit Gateway TaskContract")
    task.add_argument("--config", required=True, type=Path)
    task_input = task.add_mutually_exclusive_group(required=True)
    task_input.add_argument("--task", type=Path, help="an exact TaskContract JSON file")
    task_input.add_argument("--prompt", help="create a text-only answer task from this question")
    task.add_argument("--namespace", help="the namespace for --prompt; this host's by default")
    task.add_argument("--json", action="store_true")
    chat = commands.add_parser("chat", help="open a window and talk to the resident Agent")
    chat.add_argument("--config", required=True, type=Path)
    chat.add_argument("--actor", help="the platform actor to act as; the device owner by default")
    chat.add_argument("--namespace", help="the namespace to address; this host's by default")
    web = commands.add_parser(
        "web", help="serve this machine's Agent to a browser on this machine only"
    )
    web.add_argument("--config", required=True, type=Path)
    web.add_argument("--namespace", help="the namespace to address; this host's by default")
    web.add_argument(
        "--port", type=int, default=0, help="a fixed port; by default the system picks a free one"
    )
    web.add_argument("--open", action="store_true", help="open the address in a browser")
    web.add_argument(
        "--schedules",
        action="store_true",
        help="also run due scheduled tasks in this process (host.json schedules.resident_loop)",
    )
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
    schedules = commands.add_parser("schedules", help="manage this host's local schedules")
    schedules.add_argument("--config", required=True, type=Path)
    schedule_actions = schedules.add_subparsers(dest="schedule_action", required=True)
    schedule_create = schedule_actions.add_parser(
        "create", help="save an exact installed Workflow or Agent Task (intent only)"
    )
    schedule_create.add_argument("--definition", required=True, type=Path)
    schedule_actions.add_parser("list", help="list this member's schedules")
    for action in ("pause", "resume", "history", "revoke"):
        target = schedule_actions.add_parser(action)
        target.add_argument("schedule_id")
        if action == "history":
            target.add_argument("--limit", type=int, default=50)
    schedule_grant = schedule_actions.add_parser(
        "grant", help="let one schedule run unattended up to an effect class"
    )
    schedule_grant.add_argument("schedule_id")
    schedule_grant.add_argument(
        "--max-effect",
        required=True,
        choices=("read", "write", "execute", "external_side_effect"),
        help="the highest effect class this schedule may reach; sending always asks per run",
    )
    schedule_grant.add_argument("--days", type=int, help="expire the grant after this many days")
    schedule_actions.add_parser("pending", help="runs waiting for approval and open claims")
    for action in ("approve", "deny"):
        decide = schedule_actions.add_parser(action, help=f"{action} one waiting run")
        decide.add_argument("idempotency_key")
        decide.add_argument("--note")
    schedule_resolve = schedule_actions.add_parser(
        "resolve", help="record what happened to an uncertain claim; runs nothing"
    )
    schedule_resolve.add_argument("idempotency_key")
    schedule_resolve.add_argument(
        "--outcome", required=True, choices=("succeeded", "failed", "not_run")
    )
    schedule_resolve.add_argument("--note")
    schedule_actions.add_parser("tick", help="run one schedule poll now, then stop")
    schedule_actions.add_parser("run", help="keep polling due schedules until interrupted")
    dut = commands.add_parser(
        "dut-validate",
        help="run an approved physical DUT request and retain its evidence as JSON",
    )
    dut.add_argument("--config", required=True, type=Path)
    dut.add_argument("--request", required=True, type=Path)
    dut.add_argument("--output", required=True, type=Path)
    export = commands.add_parser(
        "export-assets", help="write the shipped Skill and Workflow manifests as JSON files"
    )
    export.add_argument(
        "--out", required=True, type=Path, help="a directory; assets/ of a workspace"
    )
    commands.add_parser("version", help="show the installed package version")
    # External authoring (docs/phases/EXTERNAL_AUTHORING.md): Claude Code, Codex
    # or Copilot build Skills and Workflows; the owner approves in Agent Web.
    assets = commands.add_parser(
        "assets", help="let a coding agent check, submit and test Skills and Workflows"
    )
    assets.add_argument("--config", required=True, type=Path)
    assets.add_argument("--agent", default="cli", help="who is submitting, e.g. claude-code")
    asset_actions = assets.add_subparsers(dest="asset_action", required=True)
    asset_actions.add_parser("catalog", help="compact: capabilities, Workflows and Skills")
    asset_capability = asset_actions.add_parser(
        "capability", help="one capability's description and input schema"
    )
    asset_capability.add_argument("--target", required=True, help="namespace/name@version")
    asset_actions.add_parser("workflow-format", help="the full Workflow format with examples")
    asset_actions.add_parser("skill-format", help="the full Skill format")
    asset_actions.add_parser("list", help="your candidates and their last approval")
    for action in ("check-workflow", "submit-workflow", "check-skill", "submit-skill"):
        drafted = asset_actions.add_parser(action)
        drafted.add_argument("--file", required=True, type=Path, help="the JSON draft")
        if action.startswith("submit"):
            drafted.add_argument("--title", default="")
            drafted.add_argument("--candidate", help="revise this candidate")
    for action in ("get", "run-workflow", "install-workflow", "install-skill"):
        chosen = asset_actions.add_parser(action)
        chosen.add_argument("--candidate", required=True)
        if action == "run-workflow":
            chosen.add_argument("--arguments", default="{}", help="run values as JSON")
    asset_status = asset_actions.add_parser("status", help="an approval's outcome")
    asset_status.add_argument("--approval", required=True)
    # Member publish to the shared platform (owner 2026-10-15): the submission
    # waits for an administrator's review there; nothing is approved here.
    publish = asset_actions.add_parser(
        "publish", help="submit an installed Skill or Workflow to the shared platform"
    )
    publish.add_argument("--kind", required=True, choices=("skill", "workflow"))
    source = publish.add_mutually_exclusive_group(required=True)
    source.add_argument("--asset", help="namespace/name@version as installed")
    source.add_argument(
        "--file",
        dest="manifest_file",
        type=Path,
        help="a manifest JSON file instead of an installed asset",
    )
    publish.add_argument("--change", default="minor", choices=("patch", "minor", "major"))
    publish.add_argument("--note", default="")
    publish.add_argument(
        "--visibility",
        choices=("private", "team", "organization", "public"),
        help="who may use it once approved (default: what the manifest says)",
    )
    asset_actions.add_parser("submissions", help="your submissions to the shared platform")
    withdraw = asset_actions.add_parser("withdraw", help="withdraw a pending submission")
    withdraw.add_argument("--submission", required=True)
    connect = asset_actions.add_parser(
        "connect", help="install AEP's skills and MCP servers for a coding agent"
    )
    connect.add_argument(
        "--for", dest="target", required=True, choices=("claude-code", "codex", "copilot", "all")
    )
    where = connect.add_mutually_exclusive_group(required=True)
    where.add_argument("--project", type=Path, help="the folder the agent works in")
    where.add_argument(
        "--user", action="store_true", help="for every folder: the agent's own user configuration"
    )
    connect.add_argument(
        "--remove", action="store_true", help="with --user: take out what AEP put in"
    )
    connect.add_argument(
        "--status", action="store_true", help="with --user: show what is installed, change nothing"
    )
    # Bundled Skills (owner 2026-10-15/16, docs/phases/HERMES_SKILL_PACK.md):
    # install.ps1 installs AEP's in-use Skills switched on and the skill packs
    # switched off, never overwriting or switching on what is already here.
    bundled = asset_actions.add_parser(
        "install-bundled",
        help="install the bundle's Skills: in-use ones on, skill packs off; keeps your choices",
    )
    bundled.add_argument("--bundle", type=Path, help="the unpacked Windows bundle")
    bundled.add_argument(
        "--off",
        type=Path,
        action="append",
        default=[],
        help="a folder of Skill manifests to install switched off (repeatable)",
    )
    bundled.add_argument(
        "--agent-skills",
        type=Path,
        action="append",
        default=[],
        help="a folder of coding-agent skill folders for AEP's store (repeatable)",
    )
    bundled.add_argument(
        "--agent-pack",
        default="hermes",
        help="the pack name recorded for --agent-skills folders (default: hermes)",
    )
    bundled.add_argument(
        "--no-shipped", action="store_true", help="leave out the manifests AEP ships"
    )
    bundled.add_argument(
        "--no-agent-skills",
        action="store_true",
        help="leave Claude Code and Copilot skills folders as they are",
    )
    # One-click Agent Web (owner 2026-10-08): the running server keeps its
    # address in the workspace; `open` starts it when needed and opens it.
    opened = commands.add_parser(
        "open", help="open Agent Web in the browser, starting it first if it is not running"
    )
    opened.add_argument("--config", required=True, type=Path)
    opened.add_argument("--port", type=int, default=53583)
    opened.add_argument(
        "--no-schedules",
        action="store_true",
        help="when starting it, do not run scheduled tasks in it",
    )
    shortcut = commands.add_parser(
        "shortcut", help="put an 'AEP Agent' shortcut on the desktop and in the Start menu"
    )
    shortcut.add_argument("--config", required=True, type=Path)
    shortcut.add_argument("--port", type=int, default=53583)
    # Harness telemetry (telemetry contract v0.2, owner 2026-10-08).
    tele = commands.add_parser("telemetry", help="list or export harness telemetry")
    tele.add_argument("--config", required=True, type=Path)
    tele_actions = tele.add_subparsers(dest="telemetry_action", required=True)
    tele_runs = tele_actions.add_parser("runs", help="the newest runs")
    tele_runs.add_argument("--limit", type=int, default=20)
    tele_export = tele_actions.add_parser("export", help="events as JSON Lines")
    tele_export.add_argument("--out", type=Path, help="a .jsonl file; the screen by default")
    tele_export.add_argument("--since", help="RFC3339 time; only events from then on")
    tele_export.add_argument("--run", help="only this run")
    tele_compare = tele_actions.add_parser(
        "compare", help="success, latency and loops per strategy (and run kind)"
    )
    tele_compare.add_argument(
        "--by",
        default="strategy_id,run_kind",
        help="comma-separated: strategy_id, run_kind, skill_id",
    )
    tele_compare.add_argument("--since", help="RFC3339 start")
    tele_compare.add_argument("--until", help="RFC3339 end")
    tele_compare.add_argument("--json", action="store_true")
    mcp = commands.add_parser("mcp", help="serve authoring tools to a coding agent over stdio")
    mcp.add_argument("--config", required=True, type=Path)
    mcp.add_argument("--agent", default="mcp", help="who is connecting, e.g. codex")
    assistant = commands.add_parser(
        "assistant-mcp",
        help="serve AEP's Knowledge and Workflow tools over stdio, through the running Agent Web",
    )
    assistant.add_argument("--config", required=True, type=Path)
    return parser


def _assets(args: argparse.Namespace) -> int:
    import json

    from host_runtime.external_authoring import build, connect
    from host_runtime.mcp_server import dispatch

    if args.asset_action in ("publish", "submissions", "withdraw"):
        return _publish(args)
    if args.asset_action == "connect" and args.user:
        return _connect_user(args)
    if args.asset_action == "install-bundled":
        return _install_bundled(args)
    if args.asset_action == "connect":
        if args.target == "all" or args.remove or args.status:
            print("--for all, --remove and --status go with --user", file=sys.stderr)
            return 2
        try:
            lines = connect(args.target, args.project, args.config, sys.executable)
        except (OSError, ValueError) as error:
            print(f"cannot connect: {type(error).__name__}", file=sys.stderr)
            return 2
        print("\n".join(lines))
        return 0
    try:
        authoring = build(args.config, args.agent)
    except HostError as error:
        print(json.dumps({"ok": False, "code": f"host_unavailable:{error.code}"}))
        return 2
    action = args.asset_action
    call: dict[str, object] = {}
    if hasattr(args, "file"):
        try:
            call["workflow" if "workflow" in action else "skill"] = json.loads(
                args.file.read_text(encoding="utf-8-sig")
            )
        except (OSError, ValueError):
            print(json.dumps({"ok": False, "code": "draft_unreadable"}))
            return 2
        call["title"] = getattr(args, "title", "")
    if action == "capability":
        call["target"] = args.target
    for name in ("candidate", "approval"):
        if getattr(args, name, None):
            call[f"{name}_id"] = getattr(args, name)
    if action == "run-workflow":
        call["arguments"] = args.arguments
    outcome = dispatch(authoring, "aep_" + action.replace("-", "_"), call)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 1 if outcome.get("ok") is False else 0


def _publish(args: argparse.Namespace) -> int:
    import json

    from host_runtime.platform_publish import (
        PublishError,
        explain,
        installed_manifest,
        manifest_file,
        publisher_for,
    )

    try:
        config = _load(args.config)
    except (OSError, ValueError):
        print(json.dumps({"ok": False, "code": "host_unavailable"}))
        return 2
    publisher = publisher_for(config.publishing, config.credential_environment())
    if publisher is None:
        print(
            json.dumps(
                {
                    "ok": False,
                    "code": "publishing_not_configured",
                    "message": "Add `publishing` to host.json.",
                }
            )
        )
        return 2
    try:
        if args.asset_action == "publish":
            manifest = (
                manifest_file(args.manifest_file)
                if args.manifest_file is not None
                else installed_manifest(
                    HostLayout.under(config.workspace_root), args.kind, args.asset
                )
            )
            outcome: object = publisher.submit(
                args.kind, manifest, args.change, args.note, args.visibility
            )
        elif args.asset_action == "withdraw":
            outcome = publisher.withdraw(args.submission)
        else:
            outcome = publisher.submissions()
    except PublishError as error:
        print(
            json.dumps(
                {"ok": False, "code": error.code, "message": explain(error.code)},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps({"ok": True, "result": outcome}, ensure_ascii=False, indent=2))
    return 0


def _connect_user(args: argparse.Namespace) -> int:
    """`assets connect --user`: AEP's skills and MCP servers in each coding
    agent's own configuration (owner 2026-10-15)."""
    import json

    from host_runtime import agent_setup
    from host_runtime.launcher import console_python

    environment = agent_setup.Environment.current()
    targets = agent_setup.AGENT_NAMES if args.target == "all" else (args.target,)
    if args.status:
        print(json.dumps([agent_setup.status(a, environment) for a in targets], indent=2))
        return 0
    launch = agent_setup.Launch(console_python(), args.config)
    lines = agent_setup.apply(
        "remove" if args.remove else "install",
        targets,
        environment,
        launch,
        only_detected=args.target == "all",
    )
    print("\n".join(lines))
    return 1 if any(": not changed (" in line for line in lines) else 0


def _install_bundled(args: argparse.Namespace) -> int:
    """`assets install-bundled`: what install.ps1 and update.ps1 run."""
    from host_runtime import agent_setup, skill_packs
    from host_runtime.assets import shipped

    try:
        layout = HostLayout.under(_load(args.config).workspace_root)
    except (OSError, ValueError) as error:
        print(f"cannot read {args.config}: {type(error).__name__}", file=sys.stderr)
        return 2
    try:
        report = skill_packs.install_bundle(
            layout,
            args.bundle,
            shipped=() if args.no_shipped else shipped(),
            extra_off=args.off,
            extra_agent_skills=args.agent_skills,
            extra_pack=args.agent_pack,
            environment=None if args.no_agent_skills else agent_setup.Environment.current(),
        )
    except (OSError, ValueError) as error:
        print(f"bundled Skills not installed: {error}", file=sys.stderr)
        return 1
    print("\n".join(report.summary()))
    return 0


def _assistant_mcp(args: argparse.Namespace) -> int:
    from host_runtime.assistant_bridge import Bridge

    workspace = None
    problem = ""
    try:
        workspace = HostLayout.under(_load(args.config).workspace_root).workspace_root
    except (OSError, ValueError):
        problem = (
            f"The AEP configuration {args.config} cannot be read, so AEP's Knowledge "
            "and Workflows are not reachable. Reinstall or update AEP, or use Agent Web "
            "Settings > Coding agents to set this agent up again."
        )
    Bridge(workspace, _package_version(), problem=problem).serve(
        sys.stdin.buffer, sys.stdout.buffer
    )
    return 0


def _mcp(args: argparse.Namespace) -> int:
    from host_runtime.external_authoring import build
    from host_runtime.mcp_server import Server

    Server(lambda: build(args.config, args.agent), _package_version()).serve(
        sys.stdin.buffer, sys.stdout.buffer
    )
    return 0


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


def _namespace(runtime: HostRuntime, namespace: str | None) -> str | None:
    """Which namespace a request addresses, or None having said why not.

    The host knows which namespaces its own installed assets are in, so it
    says them rather than leaving the reader to find out: a request addresses
    a namespace, and there is no sensible default to guess."""
    chosen = namespace if namespace is not None else runtime.config.namespace
    if chosen is None:
        print(
            "no namespace is configured; pass --namespace or set `namespace` in host.json."
            + _installed_namespaces(runtime),
            file=sys.stderr,
        )
    return chosen


def _ask(
    runtime: HostRuntime,
    message: str,
    actor: str | None,
    namespace: str | None,
    as_json: bool,
    output: Path | None,
) -> int:
    chosen = _namespace(runtime, namespace)
    if chosen is None:
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
    if outcome.refusal is not None or outcome.unrecorded is not None:
        return 1
    if outcome.capability is not None:
        return 0 if outcome.capability.status == "succeeded" else 1
    if outcome.workflow is not None:
        return 0 if outcome.workflow.run.status == "succeeded" else 1
    return 1 if outcome.decision is not None and outcome.decision.kind == "needs_input" else 0


def _prompt_task(runtime: HostRuntime, prompt: str, namespace: str | None) -> TaskContract | None:
    chosen = _namespace(runtime, namespace)
    if chosen is None:
        return None
    value = uuid.uuid4().hex
    try:
        return TaskContract(
            task_id=f"task-{value}",
            trace=_trace(),
            actor=runtime.actor,
            namespace=chosen,
            objective=prompt,
            expected_outputs=(ExpectedOutput(output_id="answer", artifact_ref=f"answer-{value}"),),
            checks=(
                CompletionCheck(check_id="answer-present", output_id="answer", kind="nonempty"),
            ),
        )
    except (ValidationError, ValueError):
        print("the prompt is invalid, so nothing ran", file=sys.stderr)
        return None


def _run_task(
    runtime: HostRuntime,
    task_path: Path | None,
    prompt: str | None,
    namespace: str | None,
    as_json: bool,
) -> int:
    if prompt is not None:
        task = _prompt_task(runtime, prompt, namespace)
        if task is None:
            return 2
    else:
        if task_path is None:
            raise ValueError("run-task requires a prompt or task file")
        try:
            task = TaskContract.model_validate_json(task_path.read_text(encoding="utf-8-sig"))
        except OSError:
            print(f"cannot read {task_path}", file=sys.stderr)
            return 2
        except (ValidationError, ValueError):
            print("the task contract is invalid, so nothing ran", file=sys.stderr)
            return 2
    try:
        outcome = asyncio.run(
            runtime.agent.run_task(task, bridge_id=runtime.config.device.bridge_id)
        )
    except TaskScopeError as error:
        print(f"task scope refused: {error.code}; nothing ran", file=sys.stderr)
        return 2
    except LocalStateError as error:
        print(f"task state refused: {error.code}", file=sys.stderr)
        return 1
    if as_json:
        print(outcome.model_dump_json(indent=2))
    elif outcome.refusal is not None:
        print(f"task refused: {outcome.refusal}")
    elif outcome.execution is not None:
        execution = outcome.execution
        print(f"task {outcome.task_id}: {execution.status}")
        if execution.code is not None:
            print(f"reason: {execution.code}")
        if execution.status == "validated" and execution.conversation is not None:
            print(execution.conversation.text)
            artifact = (
                runtime.layout.workspace_root
                / "task-artifacts"
                / task.expected_outputs[0].artifact_ref
            )
            print(f"answer artifact: {artifact}")
    return 0 if outcome.execution is not None and outcome.execution.status == "validated" else 1


def _chat(runtime: HostRuntime, actor: str | None, namespace: str | None) -> int:
    """Open the window, or say plainly why this machine cannot.

    Tk is in the standard library but not in every build of it -- a Python
    compiled without Tcl/Tk, or a server with no display, has none. That is
    worth one sentence naming the command that does the same work without a
    window, not a traceback."""
    chosen = _namespace(runtime, namespace)
    if chosen is None:
        return 2
    try:
        import tkinter  # noqa: F401 - asked for its absence, not its contents
    except ImportError:
        print(
            "this Python has no Tk, so no window can be opened here; "
            "`aep-host ask` does the same work on the command line",
            file=sys.stderr,
        )
        return 2
    from host_runtime.window import AgentWindow

    return AgentWindow(runtime, chosen, actor=actor).run()


def _web(
    runtime: HostRuntime,
    namespace: str | None,
    port: int,
    open_it: bool,
    config_path: Path,
    schedules: bool = False,
) -> int:
    """Serve the page until interrupted.

    The address carries the token, so it is printed and not logged, and the
    token is new every run: one left behind would be a standing key to this
    machine's Agent. The schedule loop runs here only when the owner opted in.
    """
    from host_runtime.schedule_loop import resident_schedule_loop
    from host_runtime.web import AgentWeb, AgentWebServer

    web = AgentWeb(runtime, namespace=namespace, config_path=config_path)
    server = AgentWebServer(web, port=port)
    loop = resident_schedule_loop(runtime, lock=web.request_lock, requested=schedules)
    web.schedule_loop = loop
    from host_runtime.launcher import clear_record, write_record

    with server:
        # Where `aep-host open` finds the address; removed when this stops.
        write_record(runtime.layout.workspace_root, server.address, server.server_address[1])
        if loop is not None:
            loop.start()
            print(
                f"Scheduled tasks are checked every {loop.interval_seconds:g} seconds "
                "while this runs."
            )
        web.start_telegram()
        if web.telegram_loop is not None:
            print("Telegram messages are answered while this runs.")
        web.start_feedback_sync()
        web.start_experience_nightly()
        web.start_laya_tunnel()
        web.start_mcp()
        print("This machine's Agent is at:")
        print(f"  {server.address}")
        print(
            "Only this computer can reach it, and only with that address. "
            "The token changes every time this starts."
        )
        print("Ctrl+C stops it.")
        if open_it:  # pragma: no cover - a browser needs a person
            import webbrowser

            webbrowser.open(server.address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:  # pragma: no cover - interactive only
            print("stopped")
        finally:
            clear_record(runtime.layout.workspace_root)
            if web.feedback_sync is not None:
                web.feedback_sync.stop()
            if loop is not None:
                loop.stop()
            if web.telegram_loop is not None:
                web.telegram_loop.stop(timeout=2)
            tunnel = getattr(web, "laya_tunnel", None)
            if tunnel is not None:
                tunnel.stop()
    return 0


def _telemetry(args: argparse.Namespace, workspace_root: Path) -> int:
    import json

    from host_runtime.telemetry_setup import STORE_FILE
    from telemetry.store import TelemetryStore

    path = workspace_root / STORE_FILE
    if not path.is_file():
        print(f"no telemetry recorded yet ({path})", file=sys.stderr)
        return 1
    if args.telemetry_action == "compare":
        from telemetry.report import compare, markdown

        by = tuple(item.strip() for item in args.by.split(",") if item.strip())
        rows = compare(path, by=by, since=args.since, until=args.until)
        print(json.dumps(rows, ensure_ascii=False, indent=2) if args.json else markdown(rows, by))
        return 0
    store = TelemetryStore(path)
    try:
        if args.telemetry_action == "runs":
            for run in store.runs(limit=args.limit):
                print(json.dumps(run, ensure_ascii=False))
            return 0
        lines = store.export(since=args.since, run_id=args.run)
        if args.out is None:
            for line in lines:
                print(line)
        else:
            with args.out.open("w", encoding="utf-8", newline="\n") as handle:
                count = 0
                for line in lines:
                    handle.write(line + "\n")
                    count += 1
            print(f"wrote {count} events to {args.out}")
        return 0
    finally:
        store.close()


def _launch(args: argparse.Namespace, workspace_root: Path) -> int:
    from host_runtime.launcher import LauncherError, create_shortcuts, open_agent

    try:
        if args.command == "shortcut":
            for made in create_shortcuts(args.config, args.port):
                print(f"made {made}")
            return 0
        outcome = open_agent(
            workspace_root, args.config, port=args.port, schedules=not args.no_schedules
        )
    except LauncherError as error:
        print(str(error), file=sys.stderr)
        return 1
    print("opened Agent Web" if outcome == "opened" else "started and opened Agent Web")
    return 0


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


def _dut_validate(runtime: HostRuntime, request_path: Path, output: Path) -> int:
    """Run one exact physical capability through Agent admission and Bridge policy."""
    try:
        request = DutPhysicalValidationRequest.model_validate_json(
            request_path.read_text(encoding="utf-8-sig"), strict=True
        )
    except OSError:
        print(f"cannot read {request_path}", file=sys.stderr)
        return 2
    except (ValidationError, ValueError):
        print("the DUT validation request is invalid, so nothing ran", file=sys.stderr)
        return 2
    direct = LocalCapabilityRequest(
        ingress="local",
        actor=runtime.actor,
        bridge_id=runtime.config.device.bridge_id,
        target=DUT_PHYSICAL_VALIDATE_SPEC.identity,
        arguments=request.model_dump(mode="json"),
        trace=_trace(),
    )
    outcome = asyncio.run(runtime.agent.execute_capability(direct))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(outcome.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if outcome.refusal is not None:
        print(f"refused: {outcome.refusal}; evidence written to {output}", file=sys.stderr)
        return 1
    capability = outcome.capability
    if capability is None or capability.status != "succeeded":
        code = capability.failure.code if capability and capability.failure else "not_run"
        print(f"physical validation failed: {code}; evidence written to {output}", file=sys.stderr)
        return 1
    evidence = DutValidationEvidence.model_validate(capability.data)
    if evidence.evidence_level != "production_like":
        print(
            f"recorded validation {evidence.status}; the production-like gate is still pending; "
            f"evidence written to {output}"
        )
        return 1
    print(f"physical validation {evidence.status}; evidence written to {output}")
    return 0 if evidence.status == "passed" else 1


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


def _schedule_line(record: ScheduleRecord) -> str:
    definition = record.definition
    identity = definition.target
    return (
        f"{definition.schedule_id}: {record.status}; "
        f"{definition.target_kind} {identity.namespace}/{identity.name}@{identity.version}; "
        f"next {record.next_due_at.isoformat()}"
    )


def _run_line(run: ScheduledRun) -> str:
    effect = f" [{run.side_effect}]" if run.side_effect is not None else ""
    return (
        f"{run.schedule_id} {run.due_at.isoformat()}: {run.status} "
        f"({run.result_code or 'pending'}){effect}; {run.idempotency_key}"
    )


def _schedule_run(runtime: HostRuntime) -> int:
    """The resident loop without a page, until interrupted."""
    import threading

    from host_runtime.schedule_loop import resident_schedule_loop

    loop = resident_schedule_loop(runtime, lock=None, requested=True)
    assert loop is not None
    loop.start()
    print(f"Checking scheduled tasks every {loop.interval_seconds:g} seconds; Ctrl+C stops.")
    idle = threading.Event()
    try:
        while loop.running:
            idle.wait(1.0)
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("stopped")
    finally:
        loop.stop()
    return 0


_SCHEDULE_REFUSALS = {
    "not_admitted": "this host member is not admitted",
    "definition_owner_mismatch": "schedule owner must be this host's bound member",
    "workflow_not_installed": "the exact Workflow is not installed on this host",
    "task_not_installed": (
        "scheduled Agent Tasks need a trusted installed template in assets/agent-tasks"
    ),
    "task_input_unsupported": "this Agent Task template declares no runtime inputs",
    "workflow_parameters_invalid": "the inputs do not match the Workflow's declared fields",
}


def _schedules(runtime: HostRuntime, args: argparse.Namespace) -> int:
    """The owner's schedule controls; only `tick` and `approve` dispatch work."""
    from host_runtime.schedule_control import ScheduleControl, ScheduleControlError

    control = ScheduleControl(runtime)
    action = args.schedule_action
    try:
        if action == "create":
            try:
                definition = ScheduleDefinition.model_validate_json(
                    args.definition.read_text(encoding="utf-8-sig")
                )
            except (OSError, ValidationError, ValueError):
                print("schedule definition is unreadable or invalid", file=sys.stderr)
                return 2
            print(_schedule_line(control.create(definition)))
        elif action == "list":
            for record in control.schedules():
                print(_schedule_line(record))
        elif action in {"pause", "resume"}:
            print(_schedule_line(control.set_active(args.schedule_id, active=action == "resume")))
        elif action == "history":
            for run in control.history(args.schedule_id, limit=args.limit):
                print(
                    f"{run.due_at.isoformat()}: {run.status} "
                    f"({run.result_code or 'pending'}); {run.idempotency_key}"
                )
        elif action == "grant":
            expires = (
                None
                if args.days is None
                else datetime.now(UTC) + timedelta(days=max(1, min(args.days, 3650)))
            )
            item = control.grant(
                args.schedule_id, max_side_effect=args.max_effect, expires_at=expires
            ).grant
            print(
                f"{item.schedule_id}: granted up to {item.max_side_effect} by "
                f"{item.approved_by}"
                + (f" until {item.expires_at.isoformat()}" if item.expires_at else "")
            )
            if item.max_side_effect == "external_side_effect":
                print("every run that can send still waits for your approval")
        elif action == "revoke":
            revoked = control.revoke(args.schedule_id)
            print(f"{revoked.grant.schedule_id}: grant revoked")
        elif action == "pending":
            overview = control.overview()
            for run in overview["awaiting_approval"]:
                print(_run_line(ScheduledRun.model_validate(run)))
            for schedule in overview["schedules"]:
                if schedule["blocked_by"] is not None:
                    print(
                        f"{schedule['schedule_id']}: blocked by unresolved claim "
                        f"{schedule['blocked_by']}"
                    )
        elif action == "approve":
            print(_run_line(control.approve(args.idempotency_key, note=args.note)))
        elif action == "deny":
            print(_run_line(control.deny(args.idempotency_key, note=args.note)))
        elif action == "resolve":
            print(
                _run_line(
                    control.resolve(args.idempotency_key, outcome=args.outcome, note=args.note)
                )
            )
        elif action == "run":
            return _schedule_run(runtime)
        elif action == "tick":
            results = control.tick()
            for run in results:
                print(_run_line(run))
            if not results:
                print("nothing was due")
    except ScheduleControlError as error:
        message = _SCHEDULE_REFUSALS.get(error.code)
        print(message or f"schedule control failed: {error.code}", file=sys.stderr)
        return 1
    except (OSError, ValueError, ValidationError):
        print("schedule control failed: invalid_request", file=sys.stderr)
        return 1
    return 0


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
    if args.command == "assets":
        return _assets(args)
    if args.command == "mcp":
        return _mcp(args)
    if args.command == "assistant-mcp":
        return _assistant_mcp(args)
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
    if args.command in ("open", "shortcut"):
        return _launch(args, layout.workspace_root)
    if args.command == "telemetry":
        return _telemetry(args, layout.workspace_root)
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
        if args.command in ("ask", "run-task", "chat", "web", "telegram", "jobs", "schedules"):
            from host_runtime import telemetry_setup

            telemetry_setup.start(runtime)
        if args.command == "ask":
            return _ask(runtime, args.message, args.actor, args.namespace, args.json, args.output)
        if args.command == "run-task":
            return _run_task(runtime, args.task, args.prompt, args.namespace, args.json)
        if args.command == "chat":
            return _chat(runtime, args.actor, args.namespace)
        if args.command == "web":
            return _web(runtime, args.namespace, args.port, args.open, args.config, args.schedules)
        if args.command == "status":
            return _status(runtime, args.json)
        if args.command == "probe":
            return _probe(runtime, args.json)
        if args.command == "sync":
            return _sync(runtime, args.json)
        if args.command == "jobs":
            return _jobs(runtime, args.once, args.interval)
        if args.command == "schedules":
            return _schedules(runtime, args)
        if args.command == "dut-validate":
            return _dut_validate(runtime, args.request, args.output)
        return _telegram(runtime, args.once)


if __name__ == "__main__":
    raise SystemExit(main())
