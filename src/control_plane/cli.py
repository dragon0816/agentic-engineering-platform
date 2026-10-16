"""Operator entry point for the shared-platform reference host."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import threading
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from common.identity import IssuedInvitationProof
from control_plane.app import (
    SharedPlatformConfiguration,
    application_from_config,
)
from control_plane.registry_sqlite import RegistryStoreError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aep-platform")
    subcommands = parser.add_subparsers(dest="command", required=True)
    serve = subcommands.add_parser("serve", help="run the Bridge API and member portal")
    serve.add_argument("--config", type=Path, required=True)
    serve.add_argument(
        "--invitation-output",
        type=Path,
        help="new file receiving generated invitation links; required when config has invitations",
    )
    # Conversation feedback the Bridges uploaded (owner 2026-10-08), as JSON
    # lines, newest first, for whoever improves Skills and Workflows.
    feedback = subcommands.add_parser("feedback", help="print uploaded conversation feedback")
    feedback.add_argument("--config", type=Path, required=True)
    feedback.add_argument("--limit", type=int, default=1000)
    # The SHA-256 an administrator hands to members, who pin it in Agent Web
    # (owner 2026-10-16). Reads the public certificate only.
    pin = subcommands.add_parser(
        "certificate-fingerprint", help="print the SHA-256 of the configured TLS certificate"
    )
    pin.add_argument("--config", type=Path, required=True)
    return parser


def _certificate_fingerprint(path: Path | str) -> str:
    from common.certificates import pem_fingerprint

    return pem_fingerprint(Path(path).read_text(encoding="ascii"))


def _fingerprint_command(config: Path) -> int:
    try:
        configuration = _load(config)
        if configuration.tls_certificate_path is None:
            print(
                "this platform is configured without TLS (no tls_certificate_path)", file=sys.stderr
            )
            return 2
        print(
            f"SHA-256 fingerprint: {_certificate_fingerprint(configuration.tls_certificate_path)}"
        )
    except (OSError, ValidationError, ValueError) as error:
        print(f"certificate unreadable: {error}", file=sys.stderr)
        return 2
    return 0


def _load(path: Path) -> SharedPlatformConfiguration:
    return SharedPlatformConfiguration.model_validate_json(path.read_text(encoding="utf-8-sig"))


def _write_invitations(
    path: Path, member_url: str, invitations: tuple[IssuedInvitationProof, ...]
) -> None:
    rows = []
    for issued in invitations:
        grant = issued.grant
        rows.append(
            {
                "invitation_id": grant.invitation_id,
                "actor": grant.actor,
                "expires_at": grant.expires_at.isoformat(),
                "url": f"{member_url}/#invitation={issued.bearer}",
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        json.dump({"member_portal_url": member_url, "invitations": rows}, output, indent=2)
        output.write("\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _feedback(config: Path, limit: int) -> int:
    from control_plane.feedback import FeedbackStore

    configuration = _load(config)
    if configuration.registry_path is None:
        print("this platform keeps feedback in memory only (no registry_path)", file=sys.stderr)
        return 2
    store = FeedbackStore(configuration.registry_path)
    try:
        for item in store.list(limit):
            print(item.model_dump_json())
    finally:
        store.close()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "feedback":
        return _feedback(args.config, args.limit)
    if args.command == "certificate-fingerprint":
        return _fingerprint_command(args.config)
    try:
        configuration = _load(args.config)
        if configuration.invitations and args.invitation_output is None:
            print(
                "--invitation-output is required when the config creates invitations",
                file=sys.stderr,
            )
            return 2
        application, invitations = application_from_config(configuration)
    except (OSError, ValidationError, ValueError, ssl.SSLError, RegistryStoreError) as error:
        print(f"shared platform configuration is unusable: {error}", file=sys.stderr)
        return 2

    try:
        if args.invitation_output is not None:
            _write_invitations(args.invitation_output, application.member_base_url, invitations)
            print(f"wrote invitation links to {args.invitation_output}")
        with application:
            print(f"Bridge API: {application.control_base_url}")
            print(f"Member portal: {application.member_base_url}")
            if configuration.tls_certificate_path is not None:
                try:
                    shown = _certificate_fingerprint(configuration.tls_certificate_path)
                    print(f"Certificate SHA-256: {shown}")
                except (OSError, ValueError):
                    pass  # served already; the fingerprint is a convenience
            print("Ctrl+C stops both entry points.")
            try:
                threading.Event().wait()
            except KeyboardInterrupt:  # pragma: no cover - interactive only
                print("stopped")
    except OSError as error:
        application.stop()
        print(f"shared platform could not start: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
