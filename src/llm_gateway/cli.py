"""`aep-host gateway ...` (phase B wires it into host_runtime.cli; until then
`python -m llm_gateway.cli ...`).

    init [--force]              write gateway.json + litellm-config.yaml, make
                                the local key when there is none
    status [--json]             running / starting / stopped, token expiry,
                                config, LiteLLM version, autostart
    start [--wait N] | stop | restart
    test [--model M ...]        list models, ask each for "OK"
    refresh-token [--force]     renew the upstream token (Windows sign-in)
    autostart --on | --off      logon start for the current user

No command prints a token or key value.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from llm_gateway import control, secrets_file, token_refresh
from llm_gateway.config import (
    GatewayConfigError,
    GatewayPaths,
    default_home,
    init_home,
    load_settings,
)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--home", default=None, help="the gateway home folder")
    actions = parser.add_subparsers(dest="gateway_action", required=True)
    init = actions.add_parser("init", help="write the gateway's settings and configuration")
    init.add_argument("--force", action="store_true", help="render the configuration again")
    status = actions.add_parser("status", help="whether the gateway runs, token expiry")
    status.add_argument("--json", action="store_true")
    for name in ("start", "restart"):
        started = actions.add_parser(name, help=f"{name} the gateway in the background")
        started.add_argument("--wait", type=float, default=0.0, help="seconds to wait")
    actions.add_parser("stop", help="stop the gateway AEP started")
    test = actions.add_parser("test", help="ask the gateway's models for an answer")
    test.add_argument("--model", action="append", default=None)
    test.add_argument("--json", action="store_true")
    refresh = actions.add_parser("refresh-token", help="renew the upstream token")
    refresh.add_argument("--force", action="store_true", help="renew even when not due")
    refresh.add_argument("--restart", action="store_true", help="restart a running gateway")
    autostart = actions.add_parser("autostart", help="start the gateway at logon")
    switch = autostart.add_mutually_exclusive_group(required=True)
    switch.add_argument("--on", dest="on", action="store_true")
    switch.add_argument("--off", dest="on", action="store_false")


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def describe(status: control.GatewayStatus) -> list[str]:
    data = status.to_json()
    token = status.token
    lines = [
        f"gateway: {status.state} on {data['address']}"
        + ("" if status.ours or status.state == "stopped" else " (not started by AEP)")
    ]
    if token.get("present"):
        if token.get("expires_at"):
            state = "EXPIRED" if token.get("expired") else f"{token.get('days_left')} days left"
            lines.append(f"token: expires {token['expires_at']} ({state})")
        else:
            lines.append("token: present, expiry unreadable")
    else:
        lines.append("token: missing; run `aep-host gateway refresh-token`")
    lines.append("local key: " + ("present" if status.key_present else "missing; run init"))
    lines.append(
        "config: ok"
        if not status.config_problems
        else "config: " + "; ".join(status.config_problems)
    )
    lines.append(
        f"LiteLLM: {status.litellm_version or 'not installed'} (pinned {data['litellm_pinned']})"
    )
    if status.last_refresh_at or status.last_refresh_error:
        lines.append(
            f"last refresh: {status.last_refresh_at or '-'}"
            + (f" (last error: {status.last_refresh_error})" if status.last_refresh_error else "")
        )
    if status.autostart:
        lines.append("autostart: " + ("on" if status.autostart.get("on") else "off"))
    return lines


def run(args: argparse.Namespace) -> int:
    paths = GatewayPaths(Path(args.home) if args.home else default_home())
    action = args.gateway_action
    try:
        if action == "init":
            written = init_home(paths, force=args.force)
            settings = load_settings(paths)
            _key, made = secrets_file.ensure_master_key(settings.secrets_path(paths), os.environ)
            for path in written:
                print(f"wrote {path}")
            print("local key: " + ("generated into the token file" if made else "kept"))
            return 0
        if action == "status":
            query = control.autostart_query if sys.platform == "win32" else None
            current = control.status(paths, autostart_query=query)
            if args.json:
                _print(current.to_json())
            else:
                print("\n".join(describe(current)))
            return 0
        if action in ("start", "restart"):
            if action == "restart":
                control.stop(paths)
            current = control.start(paths, wait_seconds=args.wait)
            print("\n".join(describe(current)))
            return 0 if current.state in ("serving", "starting") else 1
        if action == "stop":
            print("\n".join(describe(control.stop(paths))))
            return 0
        if action == "test":
            results = control.test(paths, models=args.model)
            if args.json:
                _print([item.to_json() for item in results])
            else:
                for item in results:
                    mark = "ok  " if item.ok else "FAIL"
                    print(f"{mark} {item.model}: {item.code} {item.detail}".rstrip())
            return 0 if all(item.ok for item in results) else 1
        if action == "refresh-token":
            result = token_refresh.refresh(paths, load_settings(paths), force=args.force)
            print(f"{result.code}: {result.message}")
            if result.expires_at:
                print(f"token expires {result.expires_at.isoformat(timespec='seconds')}")
            if result.ok and result.code == "renewed":
                current = control.status(paths)
                if current.ours and args.restart:
                    control.stop(paths)
                    control.start(paths)
                    print("gateway restarted with the new token")
                elif current.state != "stopped":
                    print("the running gateway still has the old token: restart it")
            return 0 if result.ok else 1
        if action == "autostart":
            outcome = control.set_autostart(paths, args.on)
            print("autostart: " + ("on" if outcome.get("on") else "off"))
            if outcome.get("note"):
                print(str(outcome["note"]))
            return 0
    except (GatewayConfigError, control.GatewayControlError) as error:
        print(f"gateway: {error}", file=sys.stderr)
        return 2
    raise AssertionError(action)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aep-host gateway")
    add_arguments(parser)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
