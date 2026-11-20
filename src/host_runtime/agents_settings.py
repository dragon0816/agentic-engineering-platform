"""Settings → Agents (owner consent 2026-11-20, docs/DECISIONS.md "Sidebar sections
and agents bound to Telegram bots").

One page for every agent and every extra Telegram bot of this Host: the main agent
(fixed; its bot is the conversation bot of Settings → Telegram), the persistent
sub-agents (`persistent_agents`) with their bot binding, and the BI collection bots
(`TelegramIngressConfig.collection_bots`, purpose 「BI 收集→<領域>」). It replaces
hand edits of `telegram.json` and `host.json`.

A bot is bound by the *name* of the environment variable that holds its token,
never the token: a value shaped like a token in the name field is refused
(`bot_token_value_refused`). A token pasted into the bot's own token field (owner
decision 2026-11-20) is written only to this Windows user's environment
(`HKCU\\Environment` through `telegram_settings.windows_user_environment`, never a
command line) and to the running process, so the reload uses it at once; no file,
response or error carries it. Deleting a bot leaves its variable in place.
`host.json` gains the mapping `<secret> -> <variable>`; `telegram.json` (or
`telegram.disabled.json` while the conversation bot is off) gains the bot record.
Every write is atomic, edits only the keys it owns and keeps every other field;
the result is validated by the file's own contract before it is written.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr

from channels.telegram import TelegramIngressConfig, TelegramSender
from common.base import Contract
from host_runtime.contracts import CompanyHostConfiguration, HostLayout
from host_runtime.persistent_agents import (
    MAIN_AGENT,
    AgentStore,
    AgentStoreError,
    PersistentAgent,
    installed_profiles,
    installed_skills,
)
from host_runtime.telegram_settings import (
    DISABLED_FILE,
    TelegramSenderEntry,
    TelegramSettingsError,
    UserEnvironmentWriter,
    windows_user_environment,
)
from host_runtime.workspace import write_atomically

_VARIABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,99}$")
#: A Bot API token (`123456:ABC…`), anywhere in what was typed.
_TOKEN_LIKE = re.compile(r"\d{5,}:[A-Za-z0-9_-]{20,}")
#: What the token field accepts: a whole Bot API token.
_TOKEN_SHAPE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{35,}$")
AGENT_SECRET_PREFIX = "telegram_agent_"
COLLECT_SECRET_PREFIX = "telegram_collect_"
BI_FEATURE = "bi-knowledge"


class AgentSettingsError(Exception):
    """A stable code; never a token."""


class BotForm(Contract):
    """A bot binding as the page sends it: the token's environment variable name."""

    # Empty: the default name for this bot (`default_variable`).
    variable: str = Field(default="", max_length=200)
    # Write-only; empty keeps whatever the variable already holds.
    token: SecretStr | None = None
    senders: tuple[TelegramSenderEntry, ...] = Field(default=(), max_length=50)
    enabled: bool = True


class AgentForm(Contract):
    """An agent as the page sends it; `id` empty creates one."""

    id: str = Field(default="", max_length=40)
    name: str = Field(max_length=60)
    purpose: str = Field(default="", max_length=500)
    skills: tuple[str, ...] = Field(default=(), max_length=40)
    # The installed AgentProfile it is created from (`namespace/name@version`).
    profile: str | None = Field(default=None, max_length=200)
    # None: no bot (an existing binding is removed).
    bot: BotForm | None = None


class CollectionBotForm(Contract):
    """A BI collection bot: one per domain (`target`)."""

    name: str = Field(max_length=60)
    target: str = Field(max_length=200)
    feature: str = Field(default=BI_FEATURE, max_length=60)
    bot: BotForm


def checked_variable(value: str) -> str:
    """The environment variable name, or a refusal; a pasted token is never kept."""
    text = value.strip()
    if _TOKEN_LIKE.search(text) or ":" in text:
        raise AgentSettingsError("bot_token_value_refused")
    if not _VARIABLE.fullmatch(text):
        raise AgentSettingsError("bot_variable_invalid")
    return text


def default_variable(kind: str, name: str) -> str:
    """`AEP_TG_<AGENT ID>` or `AEP_TG_BI_<BOT NAME>`, upper case, a valid name."""
    suffix = re.sub(r"[^A-Za-z0-9_]", "_", name).upper()
    return f"AEP_TG_{kind}{suffix}"[:100]


def checked_token(value: SecretStr | None) -> str:
    """The pasted token ('' when none), or `bot_token_invalid`; never echoed."""
    token = "" if value is None else value.get_secret_value().strip()
    if token.lower().startswith("bot") and token[3:4].isdigit():
        token = token[3:]  # copied from a Bot API URL (`.../bot123:ABC/...`)
    if token and not _TOKEN_SHAPE.fullmatch(token):
        raise AgentSettingsError("bot_token_invalid")
    return token


def _check_variable_free(config_path: Path, secret: str, variable: str, token: str) -> None:
    """Refuse a token that would silently retarget another credential or overwrite
    a variable that is not a bot token (`bot_variable_in_use`)."""
    if not token:
        return
    current = os.environ.get(variable, "")
    if current == token:
        return
    for item in _read_json(config_path).get("credentials", []):
        if (
            isinstance(item, dict)
            and item.get("environment_variable") == variable
            and item.get("secret") != secret
        ):
            raise AgentSettingsError("bot_variable_in_use")
    if current and not _TOKEN_SHAPE.fullmatch(current):
        raise AgentSettingsError("bot_variable_in_use")


def _store_token(store: UserEnvironmentWriter | None, variable: str, token: str) -> None:
    """Persist the token in this user's environment and the running process."""
    if not token:
        return
    try:
        (store or windows_user_environment)(variable, token)
    except TelegramSettingsError:
        raise AgentSettingsError("bot_token_store_unsupported") from None
    except OSError:
        raise AgentSettingsError("bot_token_store_failed") from None
    os.environ[variable] = token


def _senders(entries: tuple[TelegramSenderEntry, ...], default_actor: str) -> list[dict[str, Any]]:
    try:
        return [
            TelegramSender(
                sender_id=entry.sender_id, actor=entry.actor.strip().lstrip("@") or default_actor
            ).model_dump(mode="json")
            for entry in entries
        ]
    except ValueError:
        raise AgentSettingsError("bot_sender_invalid") from None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise AgentSettingsError("settings_file_unreadable") from None
    if not isinstance(data, dict):
        raise AgentSettingsError("settings_file_unreadable")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    write_atomically(path, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")


def telegram_file(layout: HostLayout) -> Path | None:
    """Where the bots are kept: `telegram.json`, else `telegram.disabled.json`."""
    disabled = layout.workspace_root / DISABLED_FILE
    if layout.telegram.is_file():
        return layout.telegram
    if disabled.is_file():
        return disabled
    return None


def _edit_telegram(layout: HostLayout, change: Callable[[dict[str, Any]], None]) -> None:
    path = telegram_file(layout)
    if path is None:
        raise AgentSettingsError("telegram_not_configured")
    raw = _read_json(path)
    change(raw)
    for key in ("agent_bots", "collection_bots"):
        if key in raw and not raw[key]:
            del raw[key]
    try:
        TelegramIngressConfig.model_validate(raw)
    except ValueError:
        raise AgentSettingsError("telegram_bots_invalid") from None
    _write_json(path, raw)


def _bind(config_path: Path, secret: str, variable: str) -> CompanyHostConfiguration:
    """Map `secret` to `variable` in host.json, every other field kept."""
    raw = _read_json(config_path)
    credentials = [
        c
        for c in raw.get("credentials", [])
        if not (isinstance(c, dict) and c.get("secret") == secret)
    ]
    raw["credentials"] = [*credentials, {"secret": secret, "environment_variable": variable}]
    try:
        updated = CompanyHostConfiguration.model_validate(raw)
    except ValueError:
        raise AgentSettingsError("host_settings_invalid") from None
    _write_json(config_path, raw)
    return updated


def _bot_record(entries: list[Any], name: str, values: dict[str, Any]) -> list[Any]:
    """`entries` with the record `name` replaced (its unknown fields kept) or added."""
    out: list[Any] = []
    found = False
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == name:
            out.append({**entry, **values})
            found = True
        else:
            out.append(entry)
    if not found:
        out.append(values)
    return out


def _new_agent_id(store: AgentStore) -> str:
    known = {item.id for item in store.agents()}
    while True:
        candidate = f"agent-{uuid.uuid4().hex[:6]}"
        if candidate not in known:
            return candidate


def save_agent(
    config_path: Path,
    layout: HostLayout,
    form: AgentForm,
    *,
    default_actor: str,
    token_store: UserEnvironmentWriter | None = None,
) -> tuple[PersistentAgent, CompanyHostConfiguration | None]:
    """Create or update an agent and its bot binding; the host configuration when
    host.json changed. A pasted token is stored (`token_store`) before any file is
    written, so a refusal leaves every file as it was."""
    item = AgentForm.model_validate(form)
    store = AgentStore(layout.workspace_root)
    agent_id = item.id.strip() or _new_agent_id(store)
    if agent_id == MAIN_AGENT:
        raise AgentSettingsError("agent_main_fixed")
    try:
        agent = PersistentAgent(
            id=agent_id,
            name=item.name.strip(),
            purpose=item.purpose.strip(),
            skills=item.skills,
            profile=(item.profile or "").strip() or None,
        )
    except ValueError:
        raise AgentSettingsError("agent_invalid") from None
    variable = (
        None
        if item.bot is None
        else checked_variable(item.bot.variable.strip() or default_variable("", agent_id))
    )
    token = "" if item.bot is None else checked_token(item.bot.token)
    senders = None if item.bot is None else _senders(item.bot.senders, default_actor)
    bot_name = f"agent-{agent_id}"
    secret = f"{AGENT_SECRET_PREFIX}{agent_id}"
    updated: CompanyHostConfiguration | None = None
    if item.bot is not None and telegram_file(layout) is None:
        raise AgentSettingsError("telegram_not_configured")
    if variable is not None:
        _check_variable_free(config_path, secret, variable, token)
        _store_token(token_store, variable, token)
    try:
        store.save(agent)
    except AgentStoreError as error:
        raise AgentSettingsError(str(error)) from None
    if item.bot is not None:
        assert variable is not None and senders is not None
        updated = _bind(config_path, secret, variable)
        values = {
            "name": bot_name,
            "credential": {"name": secret},
            "agent": agent_id,
            "senders": senders,
            "enabled": item.bot.enabled,
        }
        _edit_telegram(
            layout,
            lambda raw: raw.__setitem__(
                "agent_bots", _bot_record(list(raw.get("agent_bots", [])), bot_name, values)
            ),
        )
    elif telegram_file(layout) is not None:
        _edit_telegram(layout, lambda raw: _drop(raw, "agent_bots", bot_name))
    return agent, updated


def _drop(raw: dict[str, Any], key: str, name: str) -> None:
    if key in raw:
        raw[key] = [e for e in raw[key] if not (isinstance(e, dict) and e.get("name") == name)]


def delete_agent(layout: HostLayout, agent_id: str) -> bool:
    store = AgentStore(layout.workspace_root)
    try:
        deleted = store.delete(agent_id)
    except AgentStoreError as error:
        raise AgentSettingsError(str(error)) from None
    if deleted and telegram_file(layout) is not None:
        _edit_telegram(layout, lambda raw: _drop(raw, "agent_bots", f"agent-{agent_id}"))
    return deleted


def save_collection_bot(
    config_path: Path,
    layout: HostLayout,
    form: CollectionBotForm,
    *,
    default_actor: str,
    token_store: UserEnvironmentWriter | None = None,
) -> CompanyHostConfiguration:
    """Create or update a BI collection bot (its record keeps any other field)."""
    item = CollectionBotForm.model_validate(form)
    name = item.name.strip()
    target = item.target.strip()
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_.-]*", name):
        raise AgentSettingsError("bot_name_invalid")
    if not target:
        raise AgentSettingsError("bot_target_missing")
    variable = checked_variable(item.bot.variable.strip() or default_variable("BI_", name))
    token = checked_token(item.bot.token)
    senders = _senders(item.bot.senders, default_actor)
    path = telegram_file(layout)
    if path is None:
        raise AgentSettingsError("telegram_not_configured")
    existing = next(
        (
            entry
            for entry in _read_json(path).get("collection_bots", [])
            if isinstance(entry, dict) and entry.get("name") == name
        ),
        None,
    )
    # An existing bot keeps its secret name; only the variable it maps to changes.
    credential = existing.get("credential") if isinstance(existing, dict) else None
    secret = (
        str(credential["name"])
        if isinstance(credential, dict) and isinstance(credential.get("name"), str)
        else f"{COLLECT_SECRET_PREFIX}{name}"
    )
    _check_variable_free(config_path, secret, variable, token)
    _store_token(token_store, variable, token)
    updated = _bind(config_path, secret, variable)
    values = {
        "name": name,
        "credential": {"name": secret},
        "feature": item.feature.strip() or BI_FEATURE,
        "target": target,
        "senders": senders,
        "enabled": item.bot.enabled,
    }
    _edit_telegram(
        layout,
        lambda raw: raw.__setitem__(
            "collection_bots", _bot_record(list(raw.get("collection_bots", [])), name, values)
        ),
    )
    return updated


def delete_collection_bot(layout: HostLayout, name: str) -> bool:
    path = telegram_file(layout)
    if path is None:
        return False
    before = [e for e in _read_json(path).get("collection_bots", []) if isinstance(e, dict)]
    if not any(e.get("name") == name for e in before):
        return False
    _edit_telegram(layout, lambda raw: _drop(raw, "collection_bots", name))
    return True


def purpose_of(feature: str, target: str) -> str:
    return f"BI 收集→{target}" if feature == BI_FEATURE else f"{feature} 收集→{target}"


def agents_view(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    *,
    running: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """What Settings → Agents shows: never a token, only whether its variable is set.
    `running(bot name)` adds the live state of a polled bot."""
    environment = config.credential_environment()
    path = telegram_file(layout)
    try:
        telegram = TelegramIngressConfig.model_validate(_read_json(path)) if path else None
    except (AgentSettingsError, ValueError):
        telegram = None

    def bot_view(name: str, secret: str, senders: Any, enabled: bool) -> dict[str, Any]:
        variable = environment.get(secret, "")
        view = {
            "name": name,
            "variable": variable,
            "token_present": bool(variable and os.environ.get(variable, "")),
            "senders": [item.model_dump(mode="json") for item in senders],
            "enabled": enabled,
        }
        if running is not None:
            view.update(running(name))
        return view

    agent_bots = {} if telegram is None else {bot.agent: bot for bot in telegram.agent_bots}
    agents = []
    for agent in AgentStore(layout.workspace_root).agents():
        bot = agent_bots.get(agent.id)
        agents.append(
            {
                **agent.model_dump(mode="json"),
                "bot": None
                if bot is None
                else bot_view(bot.name, bot.credential.name, bot.senders, bot.enabled),
            }
        )
    collection = (
        []
        if telegram is None
        else [
            {
                "feature": bot.feature,
                "target": bot.target,
                "purpose": purpose_of(bot.feature, bot.target),
                **bot_view(bot.name, bot.credential.name, bot.senders, bot.enabled),
            }
            for bot in telegram.collection_bots
        ]
    )
    return {
        "ok": True,
        "telegram_configured": telegram is not None,
        "telegram_enabled": layout.telegram.is_file(),
        "main": {
            "id": MAIN_AGENT,
            "bot": None
            if telegram is None
            else {
                "variable": environment.get(telegram.credential.name, ""),
                "senders": [item.model_dump(mode="json") for item in telegram.senders],
                "enabled": layout.telegram.is_file(),
            },
        },
        "agents": agents,
        "collection_bots": collection,
        "skills": list(installed_skills(layout.skills)),
        "profiles": installed_profiles(layout.agents),
    }
