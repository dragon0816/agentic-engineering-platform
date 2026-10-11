"""Publish a merged Knowledge candidate as a new version (K3.4, owner 2026-10-11).

`docs/phases/KNOWLEDGE_K3.md` section 4. One person's confirm click publishes
(owner decision 3); it is an Agent Web action, never a capability the model can
call. The candidate vault written by `knowledge-pipeline/merge` moves beside
its base as `<base>-<version>`; when a Knowledge binding serves that base, a new
manifest is written with the candidate's digests and the binding switches to it.
`host.json` is backed up first, the previous version's vault and manifest stay
for rollback, and the change takes effect when the Agent restarts.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from common.base import Contract
from host_runtime.contracts import CompanyHostConfiguration, HostLayout
from host_runtime.workspace import write_atomically
from knowledge.evolution import decision_digest, knowledge_digest, raw_digest
from knowledge.vault import Vault, VaultError

CANDIDATES = "candidates"


class PublishError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PublishResult(Contract):
    base: str
    vault_root: str
    version: str | None = None  # the new Knowledge version, when a binding serves the base
    backup: str
    restart_required: bool = True


def _next_version(version: str) -> str:
    major, minor = (int(part) for part in re.split(r"[.+-]", version)[:2])
    return f"{major}.{minor + 1}.0"


def publish_candidate(config_path: Path, layout: HostLayout, base: str, candidate_root: str,
                      actor: str, *, now: datetime | None = None) -> PublishResult:
    config = CompanyHostConfiguration.model_validate_json(
        config_path.read_text(encoding="utf-8-sig"))
    pipeline = config.knowledge_pipeline
    vault_entry = next((v for v in pipeline.vaults if v.name == base), None) if pipeline else None
    if pipeline is None or vault_entry is None:
        raise PublishError("unknown_base_vault")
    sandboxes = (Path(pipeline.sandbox_root) if pipeline.sandbox_root
                 else layout.workspace_root / "knowledge-sandboxes")
    candidate = Path(candidate_root).resolve()
    if candidate.parent != (sandboxes / CANDIDATES).resolve() or \
            not candidate.name.startswith(f"{base}-"):
        raise PublishError("not_a_candidate")
    try:
        Vault(candidate)
    except VaultError:
        raise PublishError("not_a_candidate") from None
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    old_root = Path(vault_entry.root).resolve()
    data = json.loads(config.model_dump_json())
    binding = next((item for item in data["knowledge"]
                    if Path(item["vault_root"]).resolve() == old_root), None)
    version = _next_version(binding["asset"]["version"]) if binding else None
    stem = re.sub(r"-v\d[\w.-]*$", "", old_root.name)  # rs-k-v1.1.0 -> rs-k
    target = old_root.parent / f"{stem}-v{version or stamp}"
    manifest_path = None
    if binding is not None:
        asset = binding["asset"]
        stem_name = f"{asset['namespace']}__{asset['name']}"
        old_manifest = layout.knowledge / f"{stem_name}__{asset['version']}.json"
        manifest_path = layout.knowledge / f"{stem_name}__{version}.json"
        if not old_manifest.is_file() or manifest_path.exists():
            raise PublishError("manifest_unavailable")
    if target.exists():
        raise PublishError("version_exists")
    backup = config_path.with_name(f"{config_path.name}.bak-{stamp}-before-knowledge-publish")
    shutil.copy2(config_path, backup)
    shutil.move(str(candidate), str(target))
    if binding is not None and manifest_path is not None:
        manifest = json.loads(old_manifest.read_text(encoding="utf-8"))
        day = stamp[:8]
        vault = Vault(target)
        manifest["metadata"]["identity"]["version"] = version
        manifest["metadata"]["validation_refs"] = [f"merged-candidate-{target.name}-{day}"]
        manifest["metadata"]["business_approval"] = {
            "status": "approved", "reviewer": actor, "evidence": f"published-by-{actor}-{day}"}
        manifest.update(vault_ref=str(target), raw_sha256=raw_digest(vault),
                        decisions_sha256=decision_digest(vault),
                        content_sha256=knowledge_digest(vault))
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
        binding["asset"]["version"] = version
        binding["vault_root"] = str(target)
    for item in data["knowledge_pipeline"]["vaults"]:
        if item["name"] == base:
            item["root"] = str(target)
    updated = CompanyHostConfiguration.model_validate(data)
    write_atomically(config_path, updated.model_dump_json(indent=2).encode("utf-8") + b"\n")
    return PublishResult(base=base, vault_root=str(target), version=version, backup=str(backup))
