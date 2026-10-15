"""Telegram bot settings entered on the Agent Web settings page.

The bot token is the one secret this page accepts (owner request 2026-10-05).
It is written only to this Windows user's environment (`HKCU\\Environment`,
the same place an operator would set it by hand) and to the running process;
no file gets it. `host.json` gains only the name mapping
`telegram_bot -> AEP_TELEGRAM_BOT_TOKEN`, and `telegram.json` only the
SecretRef name, the Bridge and the allowed senders. The token is never
returned to the page: it shows whether a value is present.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr

from channels.telegram import TelegramIngressConfig, TelegramSender
from common.base import Contract
from host_runtime.contracts import CompanyHostConfiguration, CredentialBinding, HostLayout
from host_runtime.workspace import write_atomically

TELEGRAM_SECRET = "telegram_bot"
TOKEN_VARIABLE = "AEP_TELEGRAM_BOT_TOKEN"
DISABLED_FILE = "telegram.disabled.json"
_TOKEN_SHAPE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")

#: Stores one variable in this user's persistent environment.
UserEnvironmentWriter = Callable[[str, str], None]


class TelegramSettingsError(Exception):
    """A stable code; the token never appears in it."""


class TelegramSettingsUpdate(Contract):
    enabled: bool
    # Write-only; empty keeps the value already stored.
    token: SecretStr | None = None
    senders: tuple[TelegramSender, ...] = ()


class TelegramSenderEntry(Contract):
    """One line of the settings form: a numeric Telegram user id, and the
    actor it acts as (empty: this host's own actor)."""

    sender_id: int = Field(gt=0, strict=True)
    actor: str = ""


class TelegramSettingsForm(Contract):
    """What the settings page sends; `to_update` fills in the defaults."""

    enabled: bool
    token: SecretStr | None = None
    senders: tuple[TelegramSenderEntry, ...] = ()

    def to_update(self, default_actor: str) -> TelegramSettingsUpdate:
        return TelegramSettingsUpdate(
            enabled=self.enabled,
            token=self.token,
            senders=tuple(
                TelegramSender(
                    sender_id=entry.sender_id,
                    actor=entry.actor.strip().lstrip("@") or default_actor,
                )
                for entry in self.senders
            ),
        )


def windows_user_environment(name: str, value: str) -> None:
    """Persist `name=value` for this Windows user and tell running programs."""
    if sys.platform != "win32":
        raise TelegramSettingsError("token_store_unavailable")
    import ctypes
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    hwnd_broadcast, wm_settingchange, smto_abortifhung = 0xFFFF, 0x001A, 0x0002
    result = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(
        hwnd_broadcast,
        wm_settingchange,
        0,
        "Environment",
        smto_abortifhung,
        2000,
        ctypes.byref(result),
    )


def _disabled(layout: HostLayout) -> Path:
    return layout.workspace_root / DISABLED_FILE


def _read(path: Path) -> TelegramIngressConfig | None:
    if not path.is_file():
        return None
    try:
        return TelegramIngressConfig.model_validate_json(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def telegram_status(config: CompanyHostConfiguration, layout: HostLayout) -> dict[str, Any]:
    enabled = _read(layout.telegram)
    current = enabled or _read(_disabled(layout))
    variable = (
        config.credential_environment().get(current.credential.name, "")
        if current is not None
        else config.credential_environment().get(TELEGRAM_SECRET, "")
    )
    return {
        "configured": current is not None,
        "enabled": enabled is not None,
        "environment_variable": variable or TOKEN_VARIABLE,
        "token_present": bool(os.environ.get(variable or TOKEN_VARIABLE, "")),
        "senders": []
        if current is None
        else [item.model_dump(mode="json") for item in current.senders],
    }


def apply_telegram_settings(
    config_path: Path,
    layout: HostLayout,
    request: TelegramSettingsUpdate,
    *,
    store: UserEnvironmentWriter = windows_user_environment,
) -> CompanyHostConfiguration:
    """Save the settings and return the updated host configuration.

    A token and senders given while the bot is off are kept (in the user's
    environment and `telegram.disabled.json`), so turning it on later needs
    only the switch; nothing typed is discarded."""
    checked = TelegramSettingsUpdate.model_validate(request)
    current = CompanyHostConfiguration.model_validate_json(
        config_path.read_text(encoding="utf-8-sig")
    )
    token = "" if checked.token is None else checked.token.get_secret_value().strip()
    if token.lower().startswith("bot") and token[3:4].isdigit():
        # Copied from a Bot API URL (`.../bot123:ABC/...`).
        token = token[3:]
    if token and not _TOKEN_SHAPE.fullmatch(token):
        raise TelegramSettingsError("telegram_token_invalid")
    variable = current.credential_environment().get(TELEGRAM_SECRET, TOKEN_VARIABLE)
    kept = _read(layout.telegram) or _read(_disabled(layout))
    senders = checked.senders or (() if kept is None else kept.senders)
    if checked.enabled:
        if not token and not os.environ.get(variable, ""):
            raise TelegramSettingsError("telegram_token_missing")
        # No senders yet is allowed: the bot runs, answers nobody, and lists
        # who messaged it on the settings page so the owner can allow them.
    elif not token and not checked.senders:
        # Only the switch: turn the bot off and keep what was configured.
        if layout.telegram.is_file():
            os.replace(layout.telegram, _disabled(layout))
        return current
    if token:
        store(variable, token)
        os.environ[variable] = token
    updated = current
    if TELEGRAM_SECRET not in current.credential_environment():
        candidate = current.model_dump(mode="json")
        candidate["credentials"] = [
            *candidate["credentials"],
            CredentialBinding(secret=TELEGRAM_SECRET, environment_variable=variable).model_dump(
                mode="json"
            ),
        ]
        updated = CompanyHostConfiguration.model_validate(candidate)
        write_atomically(config_path, updated.model_dump_json(indent=2).encode("utf-8") + b"\n")
    ingress = TelegramIngressConfig(
        credential={"name": TELEGRAM_SECRET},
        bridge_id=current.device.bridge_id,
        namespace=current.namespace,
        senders=senders,
    )
    payload = ingress.model_dump_json(indent=2).encode("utf-8") + b"\n"
    if checked.enabled:
        write_atomically(layout.telegram, payload)
        if _disabled(layout).is_file():
            _disabled(layout).unlink()
    else:
        write_atomically(_disabled(layout), payload)
        if layout.telegram.is_file():
            layout.telegram.unlink()
    return updated
