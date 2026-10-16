"""Run the gateway: `python -m llm_gateway.launcher [--home DIR] [--port N]`.

What the owner's `start-gateway.ps1` + `gateway.py` did, in one process:
load the token file into this process only, refuse an expired token or a
configuration holding a secret, exit quietly when the port is already
served (a second logon, a manual start), apply the streaming patch, and
start LiteLLM's proxy on 127.0.0.1 only.

LiteLLM is configured offline: without `LITELLM_LOCAL_MODEL_COST_MAP` it
first fetches its model cost map from raw.githubusercontent.com, which fails
behind the company proxy only after a timeout, and the gateway took 9-12
minutes to start serving after a reboot (2026-10-16).
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import os
import socket
import sys
from collections.abc import Callable, MutableMapping, Sequence
from pathlib import Path

from llm_gateway import (
    LOOPBACK,
    PINNED_LITELLM_VERSION,
    patch,
    secrets_file,
    state,
    token_refresh,
)
from llm_gateway.config import (
    GatewayConfigError,
    GatewayPaths,
    default_home,
    load_settings,
    validate_config_text,
)

#: Remote fetches LiteLLM makes at import or startup, each replaced by the
#: copy it ships. Set only where the person has not set them.
OFFLINE_ENVIRONMENT = {
    "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    "LITELLM_LOCAL_ANTHROPIC_BETA_HEADERS": "True",
    "LITELLM_LOCAL_BLOG_POSTS": "True",
    "LITELLM_LOCAL_POLICY_TEMPLATES": "True",
    # No admin UI or Swagger page on a personal loopback gateway.
    "DISABLE_ADMIN_UI": "True",
    "NO_DOCS": "True",
}

EXIT_ALREADY_SERVED = 0
EXIT_NOT_READY = 2
EXIT_PATCH = 3


def offline_environment(environ: MutableMapping[str, str]) -> None:
    for name, value in OFFLINE_ENVIRONMENT.items():
        environ.setdefault(name, value)


def port_in_use(port: int, host: str = LOOPBACK, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def litellm_version() -> str | None:
    try:
        return importlib.metadata.version("litellm")
    except importlib.metadata.PackageNotFoundError:
        return None


def prepare(
    paths: GatewayPaths,
    port: int | None,
    environ: MutableMapping[str, str],
    say: Callable[[str], None],
) -> tuple[int, list[str]] | int:
    """Everything before LiteLLM starts. Returns (port, proxy arguments), or
    the exit code when the gateway must not start."""
    try:
        settings = load_settings(paths)
    except GatewayConfigError as error:
        say(f"gateway: {error}")
        return EXIT_NOT_READY
    chosen = port or settings.port
    try:
        text = paths.config.read_text(encoding="utf-8")
    except FileNotFoundError:
        say(f"gateway: no configuration at {paths.config}; run `aep-host gateway init`")
        return EXIT_NOT_READY
    problems = validate_config_text(text)
    if problems:
        say(f"gateway: {paths.config} is not usable: " + "; ".join(problems))
        return EXIT_NOT_READY
    missing = secrets_file.load_into(environ, settings.secrets_path(paths))
    if missing:
        say(
            "gateway: missing " + ", ".join(missing) + f" (token file "
            f"{settings.secrets_path(paths)}); run `aep-host gateway refresh-token`"
        )
        return EXIT_NOT_READY
    info = secrets_file.token_info(environ.get("CHATRS_TOKEN"))
    if info.expired():
        say("gateway: the upstream token has expired; run `aep-host gateway refresh-token`")
        return EXIT_NOT_READY
    if port_in_use(chosen):
        say(f"gateway: 127.0.0.1:{chosen} is already served; not starting a second one")
        return EXIT_ALREADY_SERVED
    offline_environment(environ)
    return chosen, ["--config", str(paths.config), "--port", str(chosen), "--host", LOOPBACK]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llm_gateway.launcher")
    parser.add_argument("--home", default=None, help="the gateway home folder")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--refresh-if-due",
        action="store_true",
        help="renew the upstream token first when it is close to expiry (autostart)",
    )
    args = parser.parse_args(argv)
    paths = GatewayPaths(default_home() if args.home is None else Path(args.home))

    def say(message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    if args.refresh_if_due:
        try:
            result = token_refresh.refresh(paths, load_settings(paths))
        except (GatewayConfigError, OSError) as error:
            say(f"gateway: token refresh skipped: {error}")
        else:
            say(f"gateway: token refresh: {result.code}: {result.message}")
    prepared = prepare(paths, args.port, os.environ, say)
    if isinstance(prepared, int):
        return prepared
    port, proxy_arguments = prepared
    version = litellm_version()
    if version is None:
        say("gateway: LiteLLM is not installed in this Python environment")
        return EXIT_NOT_READY
    if version != PINNED_LITELLM_VERSION:
        say(
            f"gateway: LiteLLM {version} is not the verified {PINNED_LITELLM_VERSION}; "
            "the streaming patch checks its target below"
        )
    try:
        patch.apply()
    except patch.GatewayPatchError as error:
        say(f"gateway: {error}")
        return EXIT_PATCH
    state.update(paths.state, pid=os.getpid(), started_at=state.now_text(), port=port)
    say(f"gateway: LiteLLM {version} starting on http://{LOOPBACK}:{port}")
    proxy_cli = importlib.import_module("litellm.proxy.proxy_cli")
    sys.argv = ["litellm", *proxy_arguments]
    proxy_cli.run_server()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
