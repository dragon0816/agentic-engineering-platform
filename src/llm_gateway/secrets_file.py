"""The person's token file: `NAME=value` lines in their own profile.

Same format as the owner's working gateway `.env` (so an existing one can be
pointed at with `secrets_file`). Values are read into the gateway process and
written back with a `.bak` copy; they are never printed, logged or returned
by anything that reports status — only a token's expiry is.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import secrets
import shutil
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from llm_gateway.config import MASTER_KEY_VARIABLE, TOKEN_VARIABLE

MASTER_KEY_PREFIX = "sk-aep-"


def parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or not name.strip():
            continue
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def read(path: Path) -> dict[str, str]:
    try:
        return parse(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}


def set_value(path: Path, name: str, value: str) -> None:
    """Set one value, keeping every other line and a `.bak` of the old file."""
    if "\n" in value or "\r" in value or not name.isidentifier():
        raise ValueError("a token file value is one line under a plain name")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.strip().partition("=")[0].strip() == name and "=" in line:
            lines[index] = f"{name}={value}"
            replaced = True
    if not replaced:
        lines.append(f"{name}={value}")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def jwt_claims(token: str) -> dict[str, object]:
    """The payload of a JWT, unverified (only its expiry is ever used)."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("not a JWT")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except (binascii.Error, UnicodeError, ValueError) as error:
        raise ValueError("not a readable JWT") from error
    if not isinstance(data, dict):
        raise ValueError("not a readable JWT")
    return data


@dataclass(frozen=True)
class TokenInfo:
    """What may be shown about the upstream token: never its value."""

    present: bool
    readable: bool = False
    expires_at: datetime | None = None

    def days_left(self, now: datetime | None = None) -> float | None:
        if self.expires_at is None:
            return None
        current = now or datetime.now(UTC)
        return (self.expires_at - current).total_seconds() / 86400

    def expired(self, now: datetime | None = None) -> bool:
        left = self.days_left(now)
        return left is not None and left <= 0

    def to_json(self, now: datetime | None = None) -> dict[str, object]:
        left = self.days_left(now)
        return {
            "present": self.present,
            "readable": self.readable,
            "expires_at": self.expires_at.isoformat(timespec="seconds")
            if self.expires_at
            else None,
            "days_left": None if left is None else round(left, 1),
            "expired": self.expired(now),
        }


def token_info(token: str | None) -> TokenInfo:
    if not token:
        return TokenInfo(present=False)
    try:
        expiry = jwt_claims(token).get("exp")
    except ValueError:
        return TokenInfo(present=True)
    if not isinstance(expiry, int | float) or isinstance(expiry, bool):
        return TokenInfo(present=True)
    return TokenInfo(present=True, readable=True, expires_at=datetime.fromtimestamp(expiry, UTC))


def new_master_key() -> str:
    """A local password for the gateway on this computer, not a company
    credential; generated so nobody has to invent one."""
    return MASTER_KEY_PREFIX + secrets.token_hex(16)


def resolve_master_key(file_values: Mapping[str, str], environ: Mapping[str, str]) -> str:
    """The key clients use: the environment's (what AEP's credential mapping
    reads) wins over the token file's, so both always agree with AEP."""
    return environ.get(MASTER_KEY_VARIABLE, "").strip() or file_values.get(MASTER_KEY_VARIABLE, "")


def ensure_master_key(path: Path, environ: Mapping[str, str]) -> tuple[str, bool]:
    """The key, generating one into the token file when there is none
    anywhere. An existing key is never changed: every client holds a copy."""
    current = resolve_master_key(read(path), environ)
    if current:
        return current, False
    generated = new_master_key()
    set_value(path, MASTER_KEY_VARIABLE, generated)
    return generated, True


def load_into(environ: MutableMapping[str, str], path: Path) -> list[str]:
    """Put the token file's two gateway values into `environ` (the gateway
    process's own). A value already in the environment wins for the key;
    the upstream token always comes from the file unless only the
    environment has one. Returns the names that are still missing."""
    values = read(path)
    key = resolve_master_key(values, environ)
    if key:
        environ[MASTER_KEY_VARIABLE] = key
    token = values.get(TOKEN_VARIABLE) or environ.get(TOKEN_VARIABLE, "")
    if token:
        environ[TOKEN_VARIABLE] = token
    return [name for name in (TOKEN_VARIABLE, MASTER_KEY_VARIABLE) if not environ.get(name)]
