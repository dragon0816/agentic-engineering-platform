"""The one tool a model has for changing this Agent's settings (owner 2026-10-15).

`propose_change(kind, values, reason)` changes nothing: the host validates
the values with the Settings card's own contract and shows a proposal card;
the person presses Apply. See docs/phases/AI_PROPOSED_CHANGES.md.

Pure: the tool's name, its prompt guidance, the kinds and which of them
Telegram may apply, and the check that refuses credential-shaped values.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from common.assets import SECRET_FIELD, SECRET_PATTERN

PROPOSE_TOOL = "propose_change"
PROPOSE_GUIDANCE = (
    "When the person asks to change this Agent's settings or Capabilities (Laya, the shared "
    "platform, the model, Telegram, a Workflow's settings, switching, removing, installing, "
    "adding or publishing a Skill or Workflow), call " + PROPOSE_TOOL + " with only the "
    "values they want changed; the person sees a card and presses Apply. Never ask for or "
    "pass a secret value (token, password, Personal Agent code, API key): say where in "
    "Settings to paste it."
)
#: Version 1 kinds, in the order the design's table lists them.
KINDS = ("laya", "shared_platform", "model", "telegram", "workflow_settings", "capability",
         "platform_add", "publish")
#: Kinds Telegram may apply (owner decision 2026-10-15); capability only for
#: switching on or off.
TELEGRAM_KINDS = frozenset({"laya", "workflow_settings"})
TELEGRAM_CAPABILITY_ACTIONS = frozenset({"switch_on", "switch_off"})
#: How long a proposal waits for a press.
EXPIRY_MINUTES = 30

# Field names that hold a secret's value, beyond the shared asset rule.
_SECRET_NAME = re.compile(
    r"(?:^|_)(?:token|password|passwd|passphrase|secret|api_?key|apikey|private_?key|cookie)$"
    r"|^(?:code|pin|login|login_code|agent_code|personal_agent_code)$",
    re.IGNORECASE,
)
# Names a model may give: of a secret or of a variable, never its value.
NAME_FIELDS = frozenset({"credential_secret", "credential_environment"})
_SHAPES = (
    re.compile(r"login-[0-9a-f]{16}:[A-Za-z0-9_-]{16,}"),          # Personal Agent code
    re.compile(r"\d{5,}:[A-Za-z0-9_-]{30,}"),                       # Telegram bot token
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),       # JWT
    re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}"),               # API keys
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),                    # GitHub tokens
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),                  # Slack tokens
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                            # AWS access key
    re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}"),                      # GitLab token
    re.compile(r"://[^/\s:@]+:[^/\s@]+@"),                          # password in a URL
    re.compile(r"[?&](?:token|key|secret|password|code|sig|signature)=", re.IGNORECASE),
)
_OPAQUE = re.compile(r"^[A-Za-z0-9_\-+=/]{32,}$")


def looks_like_credential(value: str) -> bool:
    """Whether a proposed text value has the shape of a secret."""
    text = value.strip()
    if not text:
        return False
    if SECRET_PATTERN.search(text) or any(shape.search(text) for shape in _SHAPES):
        return True
    # A long opaque string with mixed letters and digits and no path in it.
    return bool(
        _OPAQUE.fullmatch(text) and "/" not in text.strip("/")
        and re.search(r"\d", text) and re.search(r"[a-z]", text) and re.search(r"[A-Z]", text)
    )


def _walk(value: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
    else:
        yield path, value


def secret_problem(values: Any) -> str | None:
    """The field that holds (or is named for) a secret value, or None.

    The answer names the field, never the value."""
    if isinstance(values, dict):
        stack: list[tuple[str, Any]] = [("", values)]
        while stack:
            prefix, current = stack.pop()
            for key, item in current.items():
                name = str(key)
                where = f"{prefix}.{name}" if prefix else name
                if name not in NAME_FIELDS and (
                        SECRET_FIELD.fullmatch(name) or _SECRET_NAME.search(name)):
                    return where
                if isinstance(item, dict):
                    stack.append((where, item))
    for where, item in _walk(values):
        if isinstance(item, str) and looks_like_credential(item):
            return where or "value"
    return None
