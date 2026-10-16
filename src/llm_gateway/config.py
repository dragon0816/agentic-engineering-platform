"""Where the gateway keeps its files, and the LiteLLM configuration it runs.

Nothing secret is ever written by `render_config`: the upstream token and the
local key are referenced as `os.environ/<NAME>` and the launcher loads them
from the person's token file (`secrets_file`) into its own process only.

Layout under the gateway home (default `%LOCALAPPDATA%\\AgenticEngineering
Platform\\gateway`, or `AEP_GATEWAY_HOME`), all inside the Windows user's
profile and none of it in the repository or the bundle:

    gateway.json          settings: port, upstream, models (editable)
    litellm-config.yaml   rendered from gateway.json; kept on update
    gateway.env           CHATRS_TOKEN / LITELLM_MASTER_KEY (secrets_file)
    state.json            pid, last token refresh, last test (no values)
    logs/gateway.log      the gateway's own output
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from llm_gateway import DEFAULT_PORT, LOOPBACK

HOME_VARIABLE = "AEP_GATEWAY_HOME"
SETTINGS_FILE = "gateway.json"
CONFIG_FILE = "litellm-config.yaml"
SECRETS_FILE = "gateway.env"
STATE_FILE = "state.json"
TOKEN_VARIABLE = "CHATRS_TOKEN"
MASTER_KEY_VARIABLE = "LITELLM_MASTER_KEY"
DEFAULT_UPSTREAM = "https://chatrs.cloud.rsint.net/api"
DEFAULT_MODEL = "gpt-5.5"


@dataclass(frozen=True)
class GatewayModel:
    """One name clients ask for, and the upstream model that answers it."""

    name: str
    upstream: str
    note: str = ""


#: The owner's working model list (rs_llm_gateway/litellm-config.yaml,
#: 2026-09-23). Upstream ids are not guessable from the chat UI ("gpt-5.6" is
#: `gpt-5.6-luna`): check the service's /api/models before adding one.
DEFAULT_MODELS: tuple[GatewayModel, ...] = (
    GatewayModel("gpt-5.6", "gpt-5.6-luna", "frontier"),
    GatewayModel("gpt-5.5", "gpt-5.5", "frontier, AEP's default"),
    GatewayModel("gpt-5.4", "gpt-5.4"),
    GatewayModel("gpt-5.2", "gpt-5.2"),
    GatewayModel("gpt-5-mini", "gpt-5-mini", "cheap/fast"),
    GatewayModel("gpt-5.4-mini", "gpt-5.4-mini", "cheap/fast"),
    GatewayModel("qwen-36-27b", "qwen-36-27b", "open weights"),
    GatewayModel("gemma-4-31b", "gemma-4-31B-it", "open weights"),
    # Anthropic-format clients (Claude Code) that hardcode Claude names.
    GatewayModel("claude-opus-5", "gpt-5.5", "alias for Claude Code"),
    GatewayModel("claude-sonnet-5", "gpt-5.4", "alias for Claude Code"),
    GatewayModel("claude-haiku-4-5-20251001", "gpt-5-mini", "alias for Claude Code"),
)

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class GatewayConfigError(ValueError):
    """The settings or the rendered configuration are not usable."""


def default_home(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    explicit = env.get(HOME_VARIABLE, "").strip()
    if explicit:
        return Path(explicit)
    if sys.platform == "win32" and env.get("LOCALAPPDATA"):
        return Path(env["LOCALAPPDATA"]) / "AgenticEngineeringPlatform" / "gateway"
    return Path.home() / ".aep" / "gateway"


@dataclass(frozen=True)
class GatewayPaths:
    home: Path

    @property
    def settings(self) -> Path:
        return self.home / SETTINGS_FILE

    @property
    def config(self) -> Path:
        return self.home / CONFIG_FILE

    @property
    def secrets(self) -> Path:
        return self.home / SECRETS_FILE

    @property
    def state(self) -> Path:
        return self.home / STATE_FILE

    @property
    def logs(self) -> Path:
        return self.home / "logs"

    @property
    def log(self) -> Path:
        return self.logs / "gateway.log"


@dataclass(frozen=True)
class GatewaySettings:
    port: int = DEFAULT_PORT
    upstream: str = DEFAULT_UPSTREAM
    default_model: str = DEFAULT_MODEL
    models: tuple[GatewayModel, ...] = field(default=DEFAULT_MODELS)
    #: A token file somewhere else (e.g. an existing gateway's `.env`) to read
    #: instead of `gateway.env`. Empty: the one in the gateway home.
    secrets_file: str = ""
    #: The Python of the gateway's own virtual environment (where LiteLLM is).
    #: Empty: `AEP_GATEWAY_PYTHON`, else the Python running AEP.
    python: str = ""

    def __post_init__(self) -> None:
        if not 1024 <= self.port <= 65535:
            raise GatewayConfigError("the gateway port must be between 1024 and 65535")
        # Plain http only to this computer itself (a test double); a real
        # upstream carries the person's token and is https.
        if not self.upstream.startswith(("https://", "http://127.0.0.1:", "http://localhost:")):
            raise GatewayConfigError("the upstream must be an https:// address")
        if any(c in self.upstream for c in " \"'\n\r\t#"):
            raise GatewayConfigError("the upstream address contains unexpected characters")
        if not self.models:
            raise GatewayConfigError("the gateway needs at least one model")
        names = [model.name for model in self.models]
        if len(names) != len(set(names)):
            raise GatewayConfigError("each model name may appear once")
        for model in self.models:
            if not _NAME.match(model.name) or not _NAME.match(model.upstream):
                raise GatewayConfigError(f"model name not accepted: {model.name!r}")
        if self.default_model not in names:
            raise GatewayConfigError("the default model must be one of the models")

    def to_json(self) -> dict[str, object]:
        return {
            "port": self.port,
            "upstream": self.upstream,
            "default_model": self.default_model,
            "secrets_file": self.secrets_file,
            "python": self.python,
            "models": [
                {"name": m.name, "upstream": m.upstream, "note": m.note} for m in self.models
            ],
        }

    @classmethod
    def from_json(cls, data: Mapping[str, object]) -> GatewaySettings:
        raw_models = data.get("models")
        models = DEFAULT_MODELS
        if raw_models is not None:
            if not isinstance(raw_models, Sequence) or isinstance(raw_models, str):
                raise GatewayConfigError("models must be a list")
            parsed = []
            for item in raw_models:
                if not isinstance(item, Mapping):
                    raise GatewayConfigError("each model is an object with name and upstream")
                name, upstream = item.get("name"), item.get("upstream")
                note = item.get("note", "")
                if not isinstance(name, str) or not isinstance(upstream, str):
                    raise GatewayConfigError("each model needs a name and an upstream")
                parsed.append(GatewayModel(name, upstream, note if isinstance(note, str) else ""))
            models = tuple(parsed)
        port = data.get("port", DEFAULT_PORT)
        upstream = data.get("upstream", DEFAULT_UPSTREAM)
        default_model = data.get("default_model", DEFAULT_MODEL)
        secrets_file = data.get("secrets_file", "")
        python = data.get("python", "")
        if not isinstance(port, int) or isinstance(port, bool):
            raise GatewayConfigError("port must be a number")
        if not isinstance(upstream, str) or not isinstance(default_model, str):
            raise GatewayConfigError("upstream and default_model must be text")
        if not isinstance(secrets_file, str) or not isinstance(python, str):
            raise GatewayConfigError("secrets_file and python must be text")
        return cls(
            port=port,
            upstream=upstream,
            default_model=default_model,
            models=models,
            secrets_file=secrets_file,
            python=python,
        )

    def secrets_path(self, paths: GatewayPaths) -> Path:
        return Path(self.secrets_file) if self.secrets_file else paths.secrets


def load_settings(paths: GatewayPaths) -> GatewaySettings:
    """The settings in the gateway home, or the defaults when there are none."""
    try:
        text = paths.settings.read_text(encoding="utf-8")
    except FileNotFoundError:
        return GatewaySettings()
    try:
        data = json.loads(text)
    except ValueError as error:
        raise GatewayConfigError(f"{paths.settings} is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise GatewayConfigError(f"{paths.settings} must hold an object")
    return GatewaySettings.from_json(data)


def write_atomically(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def render_config(settings: GatewaySettings) -> str:
    """The LiteLLM proxy configuration, with secrets only as references."""
    lines = [
        "# Written by `aep-host gateway init` from gateway.json. Edits here are kept",
        "# by AEP updates; `aep-host gateway init --force` writes it again.",
        "#",
        "# Provider prefix is hosted_vllm/, NOT openai/: for openai/ LiteLLM routes",
        "# gpt-5.4+ requests carrying tools and reasoning_effort to the Responses",
        "# API, which chatrs (Open WebUI) does not have -> 405 Method Not Allowed.",
        "# Secrets are never in this file: the launcher loads them from the token",
        "# file into its own process.",
        "",
        "model_list:",
    ]
    for model in settings.models:
        if model.note:
            lines.append(f"  # {model.note}")
        lines += [
            f"  - model_name: {model.name}",
            "    litellm_params:",
            f"      model: hosted_vllm/{model.upstream}",
            f"      api_base: {settings.upstream}",
            f"      api_key: os.environ/{TOKEN_VARIABLE}",
            "",
        ]
    lines += [
        "general_settings:",
        "  # Clients authenticate to THIS proxy with the local key; the upstream",
        "  # token never leaves this computer.",
        f"  master_key: os.environ/{MASTER_KEY_VARIABLE}",
        "",
        "litellm_settings:",
        "  # Required: makes /v1/messages (Claude Code) use chat/completions upstream.",
        "  use_chat_completions_url_for_anthropic_messages: true",
        "  # chatrs returns a non-standard usage.latency_checkpoint object.",
        "  drop_params: true",
        "  # No public pricing for the internal deployment.",
        "  suppress_debug_info: true",
        "",
    ]
    return "\n".join(lines)


#: Text that looks like a credential value rather than a reference to one.
_SECRET_VALUES = (
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),  # a JWT
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),  # an API / master key
)
#: A YAML credential setting given a literal instead of `os.environ/<NAME>`.
_SECRET_SETTING = re.compile(
    r"(?i)^\s*(api_key|master_key|token|password|secret)\s*:\s*(?!os\.environ/)\S+"
)


def find_secret_values(text: str) -> list[str]:
    """The lines of any text holding something shaped like a token or key."""
    return [
        f"line {number}"
        for number, line in enumerate(text.splitlines(), start=1)
        if any(pattern.search(line) for pattern in _SECRET_VALUES)
    ]


def find_secrets(text: str) -> list[str]:
    """The lines of a gateway configuration that hold a credential."""
    return [
        f"line {number}"
        for number, line in enumerate(text.splitlines(), start=1)
        if _SECRET_SETTING.search(line) or any(p.search(line) for p in _SECRET_VALUES)
    ]


def validate_config_text(text: str) -> list[str]:
    """Problems with a configuration file; empty when it is usable.

    Checked without a YAML parser, which AEP's own environment does not
    carry: the markers the gateway depends on, and that no secret is in it.
    """
    problems = [f"looks like a credential value at {where}" for where in find_secrets(text)]
    if not re.search(r"(?m)^model_list:\s*$", text):
        problems.append("no model_list")
    if not re.search(r"(?m)^\s*-\s*model_name:\s*\S+", text):
        problems.append("no model in model_list")
    if f"master_key: os.environ/{MASTER_KEY_VARIABLE}" not in text:
        problems.append(f"master_key must be os.environ/{MASTER_KEY_VARIABLE}")
    if "use_chat_completions_url_for_anthropic_messages: true" not in text:
        problems.append("use_chat_completions_url_for_anthropic_messages must be true")
    if re.search(r"(?m)^\s*model:\s*openai/", text):
        problems.append("a model uses openai/ (405 on chatrs); use hosted_vllm/")
    return problems


def init_home(paths: GatewayPaths, *, force: bool = False) -> list[Path]:
    """Write gateway.json and litellm-config.yaml where they are missing.

    Existing files are the person's and are kept; `force` renders the
    configuration again from gateway.json (which is never reset). Returns
    the files written.
    """
    written: list[Path] = []
    if not paths.settings.exists():
        write_atomically(paths.settings, json.dumps(GatewaySettings().to_json(), indent=2) + "\n")
        written.append(paths.settings)
    settings = load_settings(paths)
    if force or not paths.config.exists():
        write_atomically(paths.config, render_config(settings))
        written.append(paths.config)
    paths.logs.mkdir(parents=True, exist_ok=True)
    return written


__all__ = [
    "DEFAULT_MODELS",
    "LOOPBACK",
    "DEFAULT_PORT",
    "GatewayConfigError",
    "GatewayModel",
    "GatewayPaths",
    "GatewaySettings",
    "default_home",
    "find_secret_values",
    "find_secrets",
    "init_home",
    "load_settings",
    "render_config",
    "validate_config_text",
]
