"""The installed-plugin ledger, `<workspace>/plugins/ledger.json`.

One record per plugin: the exact current version and digest, whether it is
switched on, who installed it through which channel, and the bundled asset
files it owns. `pending` is written before an install or update changes any
binding or asset file, so a start after an interruption can undo exactly
what that install may have written. The ledger is absent until the first
install; reading an absent ledger creates nothing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, StrictBool, ValidationError

from common.assets import AssetIdentity
from common.base import Contract, Sha256
from common.plugins import PluginErrorCode, PluginId, PluginOrigin
from host_runtime.workspace import write_atomically

LEDGER_FORMAT = "aep-plugin-ledger/1"


class OwnedAsset(Contract):
    """A bundled Skill/Workflow file this plugin wrote and nobody changed since."""

    kind: Literal["skill", "workflow"]
    identity: AssetIdentity
    file: str
    sha256: Sha256
    switched_on: StrictBool

    @property
    def key(self) -> tuple[str, str]:
        return self.kind, self.file


class PendingInstall(Contract):
    version: str
    content_sha256: Sha256
    new_record: StrictBool
    assets: tuple[OwnedAsset, ...] = ()


class PluginRecord(Contract):
    plugin_id: PluginId
    identity: AssetIdentity
    content_sha256: Sha256
    enabled: StrictBool
    installed_by: PluginOrigin
    assets: tuple[OwnedAsset, ...] = ()
    pending: PendingInstall | None = None
    #: Files of the previous version still to remove after a committed update;
    #: a start after an interruption finishes the removal.
    retiring: tuple[OwnedAsset, ...] = ()


class PluginLedger(Contract):
    format: Literal["aep-plugin-ledger/1"] = "aep-plugin-ledger/1"
    plugins: tuple[PluginRecord, ...] = Field(default=())

    def get(self, plugin_id: str) -> PluginRecord | None:
        return next((item for item in self.plugins if item.plugin_id == plugin_id), None)

    def put(self, record: PluginRecord) -> PluginLedger:
        others = [item for item in self.plugins if item.plugin_id != record.plugin_id]
        return PluginLedger(plugins=tuple(sorted([*others, record], key=lambda r: r.plugin_id)))

    def drop(self, plugin_id: str) -> PluginLedger:
        return PluginLedger(plugins=tuple(i for i in self.plugins if i.plugin_id != plugin_id))


class LedgerUnreadable(Exception):
    """The ledger cannot be used: invalid (`plugin_environment_failed`) or its
    folder is redirected (`plugin_path_invalid`). Nothing overwrites it."""

    def __init__(self, code: PluginErrorCode = "plugin_environment_failed") -> None:
        self.code: PluginErrorCode = code
        super().__init__(code)


def read_ledger(path: Path) -> PluginLedger:
    if not path.is_file():
        return PluginLedger()
    try:
        return PluginLedger.model_validate_json(path.read_bytes())
    except (OSError, ValidationError, ValueError):
        raise LedgerUnreadable() from None


def write_ledger(path: Path, ledger: PluginLedger) -> None:
    document = ledger.model_dump(mode="json")
    write_atomically(path, (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode())
