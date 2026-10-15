"""AI proposes, the person applies (owner 2026-10-15).

A model in Agent Web or Telegram may call one tool, `propose_change(kind,
values, reason)`. It never reaches a writer. This module validates the
values with the same contracts the Settings and Capabilities cards use,
stores a proposal (the before -> after of only the fields that change, the
reason, the conversation, a fingerprint of the settings it was based on, a
30-minute expiry) and draws it as an action card. Apply runs the very writer
the matching card runs (`AgentWeb.update_laya`, `update_shared_platform`,
`update_model_settings`, `update_telegram_settings`, `save_workflow_settings`,
`switch_asset`, `remove_asset`, `draft_action`, `add_to_agent`,
`publish_asset`), so backups, live switches and messages are the same.

Never proposed: secret values (refused, with where to paste them),
permissions and approvals, platform administration, running a Workflow,
restarting Agent Web. Every proposal and its outcome is a Task (kind
`proposal`). See docs/phases/AI_PROPOSED_CHANGES.md.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, JsonValue, ValidationError

from agent.gateway import HostTool, HostToolOutcome
from common.action_cards import CARD_KEY, ActionCard, CardButton, CardLink, CardRow
from common.assets import AssetIdentity, WorkflowManifest
from common.change_proposal import (
    EXPIRY_MINUTES,
    KINDS,
    PROPOSE_TOOL,
    TELEGRAM_CAPABILITY_ACTIONS,
    secret_problem,
)
from common.execution import Failure, RequestContext
from host_runtime.card_store import CardStore, PendingRecord, new_card_id
from models.contracts import ModelTool

ProposalKind = Literal["laya", "shared_platform", "model", "telegram", "workflow_settings",
                       "capability", "platform_add", "publish"]
PROPOSALS_FILE = Path("proposals") / "change-proposals.json"
#: Values that are permissions or approvals: never from chat.
PERMISSION_FIELDS = frozenset({"approval_ref", "grants", "grant", "permissions", "permission",
                               "data_approval", "egress_approval", "require_local_model"})
STATUS_LABELS = {
    "pending": "Waiting for Apply",
    "applied": "Applied",
    "cancelled": "Cancelled",
    "expired": "Expired: ask the Agent again",
    "stale": "The setting changed since this was proposed: ask the Agent again",
    "failed": "Not applied",
}
PASTE_WHERE = {
    "laya": "Settings > Laya decision acceleration",
    "shared_platform": "Settings > Shared platform (Personal Agent code)",
    "model": "the Windows user environment variable named in Settings > Natural-language model",
    "telegram": "Settings > Telegram bot (Bot token)",
    "workflow_settings": "the Workflow's settings under Capabilities > Workflows",
    "capability": "Capabilities",
    "platform_add": "Settings > Shared platform",
    "publish": "Settings > Shared platform",
}


class ProposalRefused(Exception):
    """Why a proposal cannot be made; said to the model, never a value."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ChangeProposal(PendingRecord):
    """One proposed change; holds no secret value."""

    kind: ProposalKind
    title: str = Field(max_length=160)
    # What Apply hands the writer, besides the current values it merges with.
    values: dict[str, JsonValue] = Field(default_factory=dict)
    rows: tuple[CardRow, ...] = ()
    reason: str = Field(default="", max_length=1_000)
    effects: tuple[str, ...] = ()
    link: CardLink | None = None
    session_id: str = Field(default="", max_length=200)
    actor: str = Field(default="", max_length=120)
    channel: str = Field(default="local", max_length=40)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    telegram_ok: bool = False
    task_id: str = ""
    outcome: str = Field(default="", max_length=2_000)
    outcome_ok: bool | None = None


@dataclass
class Plan:
    """A validated proposal before it is stored."""

    title: str
    values: dict[str, Any]
    rows: list[CardRow]
    effects: list[str] = field(default_factory=list)
    link: CardLink | None = None
    telegram_ok: bool = False


def fingerprint(snapshot: Mapping[str, Any]) -> str:
    text = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shown(value: Any) -> str:
    if value is None or value == "":
        return "(empty)"
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)[:400]
    return str(value)[:400]


def _errors(error: ValidationError) -> str:
    """Field names and rules only: pydantic is told to hide inputs."""
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or 'value'}: {item['msg']}"
        for item in error.errors()[:5])


def _only(kind: str, values: Mapping[str, Any], allowed: Mapping[str, str]) -> dict[str, Any]:
    """`values` by the writer's field names; aliases accepted, others refused."""
    picked: dict[str, Any] = {}
    for key, value in values.items():
        name = allowed.get(key)
        if name is None:
            if key in PERMISSION_FIELDS:
                raise ProposalRefused(
                    f"{key} is a permission or an approval; it is never changed from a chat. "
                    "The owner sets it on the card itself.")
            names = sorted(set(allowed.values()))
            raise ProposalRefused(f"{kind} has no value {key!r}; it takes {', '.join(names)}.")
        picked[name] = value
    return picked


class ChangeProposals:
    """Proposals for one Agent Web: the model's tool, the cards and Apply."""

    def __init__(self, web: Any, *, clock: Callable[[], Any] | None = None) -> None:
        self.web = web
        self.store: CardStore[ChangeProposal] = CardStore(
            web.runtime.layout.workspace_root / PROPOSALS_FILE, ChangeProposal, clock=clock)

    # -- the model's tool ----------------------------------------------------

    def tools(self) -> tuple[HostTool, ...]:
        async def handler(context: RequestContext, args: dict[str, Any]) -> HostToolOutcome:
            if context.session_id is None:
                return HostToolOutcome(status="failed", failure=Failure(
                    code="proposal_needs_a_person", message="Only a person's chat can apply."))
            values = args.get("values")
            try:
                card = await asyncio.to_thread(
                    self.propose, str(args.get("kind") or ""),
                    values if isinstance(values, dict) else {},
                    str(args.get("reason") or ""), session_id=context.session_id,
                    actor=context.actor, channel=context.channel)
            except ProposalRefused as refused:
                return HostToolOutcome(status="failed", failure=Failure(
                    code="proposal_refused", message=refused.message[:1_000]))
            return HostToolOutcome(status="succeeded",
                                   data={CARD_KEY: card.model_dump(mode="json")})

        return (HostTool(ModelTool(
            name=PROPOSE_TOOL,
            description=(
                "Propose a change to this Agent's settings or Capabilities. Nothing changes: "
                "the person sees a card with the before and after and presses Apply. Give "
                "only the values that should change. Kinds and their values: "
                "laya {ssh_host, ssh_port, ssh_user, remote_port, local_port, "
                "mode: off|shadow|active, confidence_threshold 0-1, timeout_ms, auto_tunnel}; "
                "shared_platform {member_portal_url, base_url (Bridge API URL), enroll: true}; "
                "model {provider: openai_compatible|ollama, alias, base_url (Gateway URL), "
                "model, credential_secret (a name), credential_environment (a variable "
                "name)}; telegram {enabled, senders: [{sender_id, actor}]}; "
                "workflow_settings {workflow, settings: {name: value}}; "
                "capability {action: switch_on|switch_off|remove|install, kind: "
                "skill|workflow, asset: namespace/name@version or name; install takes "
                "draft: the draft's name}; platform_add {kind, asset: "
                "namespace/name@version}; publish {kind, asset, change: patch|minor|major, "
                "visibility: private|team|organization|public, note}. Never a secret "
                "value, a permission or an approval."
            ),
            input_contract="host.change-proposal.v1",
            input_schema={
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "values": {"type": "object",
                               "description": "Only the values that should change."},
                    "reason": {"type": "string",
                               "description": "Why, in the person's terms, one sentence."},
                },
                "required": ["kind", "values", "reason"],
            },
        ), handler),)

    def propose(self, kind: str, values: dict[str, Any], reason: str, *, session_id: str,
                actor: str, channel: str) -> ActionCard:
        """Validate and store a proposal, or raise `ProposalRefused`.

        Every proposal, refused ones too, is a Task."""
        title = f"Proposed {kind or 'change'}"
        try:
            if kind not in KINDS:
                raise ProposalRefused(f"Unknown kind {kind!r}; use one of {', '.join(KINDS)}.")
            title = f"Proposed {kind.replace('_', ' ')} change"
            where = secret_problem(values)
            if where is not None:
                raise ProposalRefused(
                    f"{where} looks like a secret value; secrets are never passed through a "
                    f"chat. Ask the person to paste it in {PASTE_WHERE[kind]}.")
            if self.web.config_path is None and kind in ("laya", "shared_platform", "model",
                                                         "telegram"):
                raise ProposalRefused("This Agent Web was started without a writable "
                                      "host.json, so its settings cannot change here.")
            snapshot = self._snapshot(kind, values)
            plan = getattr(self, f"_plan_{kind}")(values, snapshot)
            if not plan.rows:
                raise ProposalRefused("Nothing would change: those are the current values.")
        except ProposalRefused as refused:
            tasks = self.web.tasks()
            task = tasks.start("proposal", title, session_id)
            tasks.finish(task, "failed", f"Refused: {refused.message}")
            raise
        now = self.store.now()
        proposal = ChangeProposal(
            card_id=new_card_id("cp"), kind=kind,
            created_at=now, expires_at=now + timedelta(minutes=EXPIRY_MINUTES),
            title=plan.title, values=plan.values, rows=tuple(plan.rows),
            reason=reason.strip()[:1_000], effects=tuple(plan.effects), link=plan.link,
            session_id=session_id, actor=actor, channel=channel,
            fingerprint=fingerprint(snapshot), telegram_ok=plan.telegram_ok)
        tasks = self.web.tasks()
        task = tasks.start("proposal", plan.title, session_id)
        tasks.finish(task, "needs_input", "Waiting for Apply: " + diff_summary(proposal.rows))
        self.store.put(proposal.model_copy(update={"task_id": task}))
        return self.card(proposal.card_id)  # type: ignore[return-value]

    # -- cards and decisions -------------------------------------------------

    def _settle(self, proposal: ChangeProposal, status: str, outcome: str,
                ok: bool | None) -> ChangeProposal:
        settled = proposal.model_copy(update={
            "status": status, "outcome": outcome[:2_000], "outcome_ok": ok,
            "decided_at": self.store.now()})
        self.store.put(settled)
        task_status = {"applied": "succeeded", "failed": "failed"}.get(status, "stopped")
        if proposal.task_id:
            self.web.tasks().finish(proposal.task_id, task_status,
                                    f"{STATUS_LABELS.get(status, status)}: "
                                    f"{diff_summary(proposal.rows)}"
                                    + (f" ({outcome})" if outcome else ""))
        return settled

    def _current(self, card_id: str) -> ChangeProposal | None:
        proposal = self.store.get(card_id)
        if proposal is not None and self.store.expired(proposal):
            proposal = self._settle(proposal, "expired", "", None)
        return proposal

    def card(self, card_id: str) -> ActionCard | None:
        with self.store.lock:
            proposal = self._current(card_id)
        return None if proposal is None else draw(proposal)

    def open_cards(self) -> list[ActionCard]:
        with self.store.lock:
            found = [self._current(item.card_id) for item in self.store.records()
                     if item.status == "pending"]
        return [draw(item) for item in found if item is not None and item.status == "pending"]

    def decide(self, card_id: str, action: str, *, channel: str = "local") -> dict[str, Any]:
        """Apply or Cancel. Telegram may apply only the low-risk kinds."""
        with self.store.lock:
            proposal = self._current(card_id)
            if proposal is None:
                return {"ok": False, "code": "card_unknown",
                        "message": "That proposal is unknown here."}
            if proposal.status != "pending":
                return {"ok": False, "code": f"proposal_{proposal.status}",
                        "message": STATUS_LABELS.get(proposal.status, proposal.status),
                        "card": draw(proposal).model_dump(mode="json")}
            if action == "cancel":
                proposal = self._settle(proposal, "cancelled", "Nothing was changed.", None)
                return {"ok": True, "code": "cancelled", "message": "Cancelled.",
                        "card": draw(proposal).model_dump(mode="json")}
            if action != "apply":
                return {"ok": False, "code": "card_action_unknown",
                        "message": "The card has Apply and Cancel."}
            if channel == "telegram" and not proposal.telegram_ok:
                return {"ok": False, "code": "web_only",
                        "message": "This change is applied in Agent Web only.",
                        "card": draw(proposal).model_dump(mode="json")}
            try:
                now_snapshot = self._snapshot(proposal.kind, self._target(proposal))
            except ProposalRefused as refused:
                now_snapshot = {"refused": refused.message}
            if fingerprint(now_snapshot) != proposal.fingerprint:
                proposal = self._settle(proposal, "stale", "Nothing was changed.", None)
                return {"ok": False, "code": "proposal_stale",
                        "message": STATUS_LABELS["stale"],
                        "card": draw(proposal).model_dump(mode="json")}
            try:
                ok, message = getattr(self, f"_apply_{proposal.kind}")(proposal)
            except Exception as failure:  # noqa: BLE001 - the card must show it ended
                ok, message = False, f"The change could not be applied ({type(failure).__name__})."
            proposal = self._settle(proposal, "applied" if ok else "failed", message, ok)
            return {"ok": ok, "code": "applied" if ok else "apply_failed", "message": message,
                    "card": draw(proposal).model_dump(mode="json")}

    # -- what is current -----------------------------------------------------

    def _target(self, proposal: ChangeProposal) -> dict[str, Any]:
        """The values the snapshot depends on, as the proposal stored them."""
        return dict(proposal.values)

    def _snapshot(self, kind: str, values: Mapping[str, Any]) -> dict[str, Any]:
        return getattr(self, f"_now_{kind}")(values)  # type: ignore[no-any-return]

    def _host_json(self) -> Any:
        from host_runtime.contracts import CompanyHostConfiguration

        try:
            return CompanyHostConfiguration.model_validate_json(
                Path(self.web.config_path).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise ProposalRefused("host.json cannot be read; nothing can change.") from None

    # laya ---------------------------------------------------------------------

    LAYA_FIELDS = {
        "ssh_host": "ssh_host", "host": "ssh_host", "ssh_port": "ssh_port",
        "ssh_user": "ssh_user", "user": "ssh_user", "remote_port": "remote_port",
        "local_port": "local_port", "mode": "mode",
        "confidence_threshold": "confidence_threshold", "threshold": "confidence_threshold",
        "timeout_ms": "timeout_ms", "timeout": "timeout_ms", "auto_tunnel": "auto_tunnel",
    }
    LAYA_LABELS = {
        "ssh_host": "Remote host", "ssh_port": "SSH port", "ssh_user": "Account",
        "remote_port": "Remote port (Laya)", "local_port": "Local port", "mode": "Mode",
        "confidence_threshold": "Confidence threshold", "timeout_ms": "Timeout (ms)",
        "auto_tunnel": "Agent Web keeps the SSH tunnel open",
    }

    def _now_laya(self, _values: Mapping[str, Any]) -> dict[str, Any]:
        from host_runtime.laya import current_settings

        config = self._host_json()
        return {"laya": current_settings(config, Path.home() / ".ssh" / "config")
                .model_dump(mode="json")}

    def _plan_laya(self, values: Mapping[str, Any], snapshot: dict[str, Any]) -> Plan:
        from host_runtime.contracts import LayaSettings
        from host_runtime.laya import LayaError, accelerator_for

        changes = _only("laya", values, self.LAYA_FIELDS)
        threshold = changes.get("confidence_threshold")
        if isinstance(threshold, (int, float)) and not isinstance(threshold, bool) \
                and 1 < threshold <= 100:
            changes["confidence_threshold"] = threshold / 100  # given as a percentage
        before = snapshot["laya"]
        try:
            settings = LayaSettings.model_validate({**before, **changes})
        except ValidationError as error:
            raise ProposalRefused(f"Those Laya values are not valid: {_errors(error)}.") from None
        config = self._host_json()
        try:
            accelerator_for(settings, config.decision_accelerator,
                            config.credential_environment())
        except LayaError as error:
            raise ProposalRefused({
                "egress_approval_missing": "Shadow and active need the owner's approval "
                "reference, which is set only on Settings > Laya decision acceleration; it "
                "is an approval, so it is never proposed from a chat.",
                "credential_unmapped": "host.json does not map the Laya API key's name to "
                "a variable yet; set Laya up on its Settings card first.",
            }.get(error.code, error.code)) from None
        after = settings.model_dump(mode="json")
        rows = [CardRow(label=self.LAYA_LABELS[name], before=shown(before.get(name)),
                        after=shown(after[name]))
                for name in self.LAYA_FIELDS.values() if before.get(name) != after[name]]
        rows = list({row.label: row for row in rows}.values())
        effects = []
        if before.get("mode") != after["mode"]:
            effects.append("The mode takes effect after Agent Web restarts.")
        if after["auto_tunnel"] and not before.get("auto_tunnel"):
            effects.append(f"Agent Web opens an SSH tunnel to {after['ssh_host']} and "
                           "reopens it when it drops.")
        return Plan(title="Change Laya decision acceleration",
                    values={name: after[name] for name in set(self.LAYA_FIELDS.values())},
                    rows=rows, effects=effects, telegram_ok=True,
                    link=CardLink(label="Open Settings > Laya", view="settings",
                                  anchor="laya-settings"))

    def _apply_laya(self, proposal: ChangeProposal) -> tuple[bool, str]:
        current = self._now_laya({})["laya"]
        reply = self.web.update_laya({**current, **proposal.values})
        if not reply.get("ok"):
            return False, f"Not saved ({reply.get('code')})."
        return True, "Saved to host.json." + (
            " The mode applies after Agent Web restarts." if reply.get("restart_required")
            else "")

    # shared platform ------------------------------------------------------------

    SHARED_FIELDS = {"member_portal_url": "member_portal_url", "portal_url": "member_portal_url",
                     "base_url": "base_url", "bridge_url": "base_url",
                     "bridge_api_url": "base_url", "enroll": "enroll"}

    def _now_shared_platform(self, _values: Mapping[str, Any]) -> dict[str, Any]:
        settings = self.web.shared_platform_settings()
        return {"member_portal_url": settings["member_portal_url"],
                "base_url": settings["base_url"], "enrolled": bool(settings["enrolled"]),
                "login_saved": bool(settings["login_saved"])}

    def _plan_shared_platform(self, values: Mapping[str, Any],
                              snapshot: dict[str, Any]) -> Plan:
        from host_runtime.shared_platform import SharedPlatformError, bridge_url, portal_url

        changes = _only("shared_platform", values, self.SHARED_FIELDS)
        enroll = changes.pop("enroll", False)
        if not isinstance(enroll, bool):
            raise ProposalRefused("enroll is true or false.")
        after = {"member_portal_url": snapshot["member_portal_url"],
                 "base_url": snapshot["base_url"]}
        try:
            for name, check in (("member_portal_url", portal_url), ("base_url", bridge_url)):
                if name in changes:
                    after[name] = check(str(changes[name] or ""))
            if not after["member_portal_url"]:
                portal_url("")
        except SharedPlatformError as error:
            raise ProposalRefused(self.web._shared_problem(error.code)["message"]) from None
        if enroll and not after["base_url"]:
            raise ProposalRefused("Enrolling needs the Bridge API URL.")
        if enroll and not snapshot["login_saved"]:
            raise ProposalRefused(
                "Enrolling needs this member's Personal Agent code, which is never passed "
                f"through a chat: paste it in {PASTE_WHERE['shared_platform']} first.")
        rows = [CardRow(label=label, before=shown(snapshot[name]), after=shown(after[name]))
                for name, label in (("member_portal_url", "Member Portal URL"),
                                    ("base_url", "Bridge API URL"))
                if snapshot[name] != after[name]]
        effects = ["host.json is backed up before it changes."]
        if enroll:
            rows.append(CardRow(label="This PC enrolled",
                                before="yes" if snapshot["enrolled"] else "no",
                                after="yes (enrolled again)" if snapshot["enrolled"]
                                else "yes"))
            effects.insert(0, "This enrolls this PC; a Bridge token is saved for your Windows "
                              "user.")
        return Plan(title="Enroll this PC on the shared platform" if enroll
                    else "Change the shared platform addresses",
                    values={**after, "enroll": enroll}, rows=rows, effects=effects,
                    link=CardLink(label="Open Settings > Shared platform", view="settings",
                                  anchor="shared-platform-card"))

    def _apply_shared_platform(self, proposal: ChangeProposal) -> tuple[bool, str]:
        reply = self.web.update_shared_platform(dict(proposal.values))
        if not reply.get("ok"):
            return False, str(reply.get("message") or reply.get("code"))
        return True, "Saved; the previous host.json was backed up." + (
            " This PC is enrolled." if reply.get("just_enrolled") else "")

    # model -----------------------------------------------------------------------

    MODEL_FIELDS = {"provider": "provider", "alias": "alias", "base_url": "base_url",
                    "gateway_url": "base_url", "model": "model", "model_name": "model",
                    "credential_secret": "credential_secret",
                    "secret_name": "credential_secret",
                    "credential_environment": "credential_environment",
                    "variable": "credential_environment",
                    "environment_variable": "credential_environment"}
    MODEL_LABELS = {"provider": "Provider", "alias": "Alias", "base_url": "Gateway URL",
                    "model": "Model", "credential_secret": "Secret name",
                    "credential_environment": "Environment variable name"}

    def _now_model(self, _values: Mapping[str, Any]) -> dict[str, Any]:
        config = self._host_json()
        binding = config.models
        endpoint = (None if binding is None or binding.routing_alias is None
                    else binding.catalog.endpoint(binding.routing_alias))
        if endpoint is None:
            return {"endpoint": None, "require_local_model": False}
        credential = endpoint.credential
        return {
            "endpoint": {
                "alias": endpoint.alias, "provider": endpoint.provider,
                "model": endpoint.model, "base_url": endpoint.base_url or "",
                "credential_secret": None if credential is None else credential.name,
                "credential_environment": None if credential is None
                else config.credential_environment().get(credential.name),
                **endpoint.capabilities.model_dump(mode="json"),
            },
            "require_local_model": binding.require_local_model if binding else False,
        }

    def _plan_model(self, values: Mapping[str, Any], snapshot: dict[str, Any]) -> Plan:
        import os

        from host_runtime.contracts import ModelSettingsUpdateRequest

        changes = _only("model", values, self.MODEL_FIELDS)
        current = snapshot["endpoint"] or {}
        fields = ModelSettingsUpdateRequest.model_fields
        merged = {name: value for name, value in current.items() if name in fields}
        merged.update(changes)
        merged["require_local_model"] = snapshot["require_local_model"]
        try:
            request = ModelSettingsUpdateRequest.model_validate(merged)
        except ValidationError as error:
            raise ProposalRefused(f"Those model values are not valid: {_errors(error)}.") from None
        after = request.model_dump(mode="json")
        rows = [CardRow(label=label, before=shown(current.get(name)), after=shown(after[name]))
                for name, label in self.MODEL_LABELS.items() if current.get(name) != after[name]]
        effects = ["Agent Web must restart before the new model answers."]
        if any(current.get(name) != after[name] for name in
               ("provider", "base_url", "credential_secret", "credential_environment")):
            effects.append("A changed provider, Gateway URL or credential needs a fresh data "
                           "approval in host.json; the old one does not carry over.")
        variable = after.get("credential_environment")
        if variable and not os.environ.get(str(variable)):
            effects.append(f"Save the key yourself as the Windows user environment variable "
                           f"{variable}; it is never passed through a chat.")
        return Plan(title="Change the natural-language model", values=after, rows=rows,
                    effects=effects,
                    link=CardLink(label="Open Settings > Natural-language model",
                                  view="settings", anchor="model-settings"))

    def _apply_model(self, proposal: ChangeProposal) -> tuple[bool, str]:
        from host_runtime.contracts import ModelSettingsUpdateRequest

        reply = self.web.update_model_settings(
            ModelSettingsUpdateRequest.model_validate(proposal.values))
        if not reply.get("ok"):
            return False, f"Not saved ({reply.get('code')})."
        return True, "Saved to host.json. Restart Agent Web to use the new model."

    # telegram ---------------------------------------------------------------------

    TELEGRAM_FIELDS = {"enabled": "enabled", "enable": "enabled", "senders": "senders",
                       "allowed_senders": "senders", "allowed_chats": "senders"}

    def _now_telegram(self, _values: Mapping[str, Any]) -> dict[str, Any]:
        from host_runtime.telegram_settings import telegram_status

        status = telegram_status(self.web.runtime.config, self.web.runtime.layout)
        return {"enabled": status["enabled"], "senders": status["senders"],
                "token_present": status["token_present"]}

    def _plan_telegram(self, values: Mapping[str, Any], snapshot: dict[str, Any]) -> Plan:
        from host_runtime.telegram_settings import TelegramSettingsForm

        changes = _only("telegram", values, self.TELEGRAM_FIELDS)
        merged = {"enabled": snapshot["enabled"], "senders": snapshot["senders"], **changes}
        try:
            form = TelegramSettingsForm.model_validate(
                {"enabled": merged["enabled"], "senders": merged["senders"]})
            update = form.to_update(self.web.runtime.actor)
        except (ValidationError, ValueError) as error:
            detail = _errors(error) if isinstance(error, ValidationError) else "invalid"
            raise ProposalRefused(f"Those Telegram values are not valid: {detail}.") from None
        if update.enabled and not snapshot["token_present"]:
            raise ProposalRefused("The bot token is not saved yet and is never passed through "
                                  f"a chat: paste it in {PASTE_WHERE['telegram']} first.")
        senders = [item.model_dump(mode="json") for item in update.senders]

        def listed(items: list[dict[str, Any]]) -> str:
            return ", ".join(f"{item['sender_id']} as {item['actor']}" for item in items) \
                or "(nobody)"

        rows = []
        if snapshot["enabled"] != update.enabled:
            rows.append(CardRow(label="Answer Telegram messages",
                                before=shown(snapshot["enabled"]), after=shown(update.enabled)))
        if snapshot["senders"] != senders:
            rows.append(CardRow(label="Allowed senders", before=listed(snapshot["senders"]),
                                after=listed(senders)))
        effects = ["The bot's polling restarts with the new settings."]
        if snapshot["senders"] != senders:
            effects.append("Each allowed sender uses this Agent as the actor named here.")
        return Plan(title="Change the Telegram bot", values={"enabled": update.enabled,
                                                             "senders": senders},
                    rows=rows, effects=effects,
                    link=CardLink(label="Open Settings > Telegram bot", view="settings",
                                  anchor="telegram-settings"))

    def _apply_telegram(self, proposal: ChangeProposal) -> tuple[bool, str]:
        from host_runtime.telegram_settings import TelegramSettingsForm

        reply = self.web.update_telegram_settings(TelegramSettingsForm.model_validate(
            {"enabled": proposal.values["enabled"], "senders": proposal.values["senders"]}))
        if not reply.get("ok"):
            return False, f"Not saved ({reply.get('code')})."
        return True, "Saved; the bot restarted its polling."

    # workflow settings ---------------------------------------------------------------

    def _workflow(self, name: str) -> WorkflowManifest:
        from host_runtime.web import manifests
        from host_runtime.workflow_form_tool import resolve

        found = resolve(tuple(manifests(self.web.runtime.layout.workflows, WorkflowManifest)),
                        name)
        if isinstance(found, str):
            raise ProposalRefused(
                "Name one installed Workflow exactly." if found == "workflow_not_installed"
                else "That name matches more than one Workflow; use namespace/name.")
        return found

    def _now_workflow_settings(self, values: Mapping[str, Any]) -> dict[str, Any]:
        manifest = self._workflow(str(values.get("workflow") or ""))
        identity = manifest.metadata.identity
        return {"workflow": identity.model_dump(mode="json"),
                "values": self.web.workflow_settings_store.for_manifest(manifest)}

    def _plan_workflow_settings(self, values: Mapping[str, Any],
                                snapshot: dict[str, Any]) -> Plan:
        from common.workflow_parameters import (
            WorkflowParameterError,
            static_fields,
            validate_static_settings,
        )

        _only("workflow_settings", values,
              {"workflow": "workflow", "settings": "settings", "values": "settings"})
        settings = values.get("settings", values.get("values"))
        if not isinstance(settings, dict) or not settings:
            raise ProposalRefused("Give settings: {name: value} for the Workflow.")
        manifest = self._workflow(str(values.get("workflow") or ""))
        declared = {item.name: item for item in static_fields(manifest)}
        if not declared:
            raise ProposalRefused("That Workflow has no settings.")
        before = snapshot["values"]
        merged = {**before, **settings}
        try:
            validate_static_settings(manifest, merged, complete=False)
        except WorkflowParameterError as error:
            raise ProposalRefused(f"Those settings are not valid: {error}.") from None
        identity = manifest.metadata.identity
        reference = f"{identity.namespace}/{identity.name}@{identity.version}"
        rows = [CardRow(label=declared[name].label or name, before=shown(before.get(name)),
                        after=shown(merged[name]))
                for name in declared if name in settings and before.get(name) != merged[name]]
        return Plan(title=f"Change the settings of {identity.name}",
                    values={"workflow": reference, "settings": merged}, rows=rows,
                    effects=["The next run uses them."], telegram_ok=True,
                    link=CardLink(label=f"Open {identity.name} settings", view="installed",
                                  capability_kind="workflows", asset=reference))

    def _apply_workflow_settings(self, proposal: ChangeProposal) -> tuple[bool, str]:
        from host_runtime.contracts import WorkflowSettingsUpdateRequest

        manifest = self._workflow(str(proposal.values["workflow"]))
        reply = self.web.save_workflow_settings(WorkflowSettingsUpdateRequest(
            workflow=manifest.metadata.identity,
            values=dict(proposal.values["settings"])))  # type: ignore[arg-type]
        if not reply.get("ok"):
            return False, str(reply.get("message") or reply.get("code"))
        return True, "Saved; the next run uses them."

    # capability -------------------------------------------------------------------

    def _asset(self, kind: str, name: str) -> tuple[str, AssetIdentity, str]:
        """(kind, identity, state: on/off) of one installed or switched-off asset."""
        from agent.skills import SkillManifest
        from host_runtime.asset_shelf import DISABLED
        from host_runtime.web import manifests

        layout = self.web.runtime.layout
        target = name.strip()
        found: list[tuple[str, AssetIdentity, str]] = []
        for each_kind, folder, model in (("skill", layout.skills, SkillManifest),
                                         ("workflow", layout.workflows, WorkflowManifest)):
            if kind and kind != each_kind:
                continue
            for state, place in (("on", folder), ("off", folder / DISABLED)):
                for manifest in manifests(place, model):
                    identity = manifest.metadata.identity
                    if target in (identity.name, f"{identity.namespace}/{identity.name}",
                                  f"{identity.namespace}/{identity.name}@{identity.version}"):
                        found.append((each_kind, identity, state))
        if not found:
            raise ProposalRefused(f"No installed or switched-off Skill or Workflow is called "
                                  f"{target!r}.")
        if len(found) > 1:
            raise ProposalRefused("That name matches more than one; give kind and "
                                  "namespace/name@version.")
        return found[0]

    def _draft(self, name: str) -> dict[str, Any]:
        target = name.strip()
        found = [item for item in self.web.drafts()["drafts"]
                 if target in (item["candidate_id"], item["title"], item["asset"],
                               item["asset"].split("@", 1)[0],
                               item["asset"].split("@", 1)[0].split("/", 1)[-1])]
        if len(found) != 1:
            raise ProposalRefused("No single draft waiting to be installed is called "
                                  f"{target!r}." if not found
                                  else "That name matches more than one draft.")
        return dict(found[0])

    def _now_capability(self, values: Mapping[str, Any]) -> dict[str, Any]:
        if values.get("action") == "install":
            draft = self._draft(str(values.get("draft") or values.get("asset") or ""))
            return {"draft": draft["candidate_id"], "updated_at": str(draft["updated_at"])}
        try:
            kind, identity, state = self._asset(str(values.get("kind") or ""),
                                                str(values.get("asset") or ""))
        except ProposalRefused:
            return {"asset": str(values.get("asset") or ""), "state": "absent"}
        return {"kind": kind, "asset": identity.model_dump(mode="json"), "state": state}

    def _plan_capability(self, values: Mapping[str, Any], snapshot: dict[str, Any]) -> Plan:
        from host_runtime.asset_shelf import is_shipped

        _only("capability", values, {"action": "action", "kind": "kind", "asset": "asset",
                                     "draft": "draft"})
        action = values.get("action")
        if action not in ("switch_on", "switch_off", "remove", "install"):
            raise ProposalRefused("action is switch_on, switch_off, remove or install.")
        if action == "install":
            draft = self._draft(str(values.get("draft") or values.get("asset") or ""))
            plural = "workflows" if draft["kind"] == "workflow" else "skills"
            return Plan(
                title=f"Install the draft {draft['title']}",
                values={"action": "install", "draft": draft["candidate_id"]},
                rows=[CardRow(label=f"{draft['kind'].title()} {draft['asset']}",
                              before="draft", after="installed")],
                effects=["Your Apply is the owner's approval of this draft, as the Install "
                         "button under Capabilities is."],
                link=CardLink(label="Open Capabilities", view="installed",
                              capability_kind=plural, asset=draft["asset"]))
        kind, identity, state = self._asset(str(values.get("kind") or ""),
                                            str(values.get("asset") or ""))
        reference = f"{identity.namespace}/{identity.name}@{identity.version}"
        plural = "workflows" if kind == "workflow" else "skills"
        effects: list[str] = []
        if action == "switch_off":
            if state == "off":
                raise ProposalRefused("It is already switched off.")
            after, title = "off", f"Switch off {identity.name}"
            effects.append("The Agent stops offering it; the file is kept and can be switched "
                           "on again.")
        elif action == "switch_on":
            if state == "on":
                raise ProposalRefused("It is already switched on.")
            after, title = "on", f"Switch on {identity.name}"
            if kind == "skill":
                effects.append("The Agent offers this Skill after Agent Web restarts.")
        else:
            if is_shipped(kind, identity):
                raise ProposalRefused("This ships with AEP, so removing it would not last; "
                                      "propose switching it off instead.")
            after, title = "removed", f"Remove {identity.name} from this Agent"
            effects.append("The file moves to workspace\\removed\\<date>; move it back to "
                           "restore it.")
            if self.web._selected_here(kind, identity):
                effects.append("It is still selected for this PC on the shared platform, so "
                               "the next synchronization installs it again.")
        return Plan(title=title,
                    values={"action": action, "kind": kind, "asset": reference},
                    rows=[CardRow(label=f"{kind.title()} {reference}", before=state,
                                  after=after)],
                    effects=effects, telegram_ok=action in TELEGRAM_CAPABILITY_ACTIONS,
                    link=CardLink(label="Open Capabilities", view="installed",
                                  capability_kind=plural, asset=reference))

    def _apply_capability(self, proposal: ChangeProposal) -> tuple[bool, str]:
        values = proposal.values
        if values["action"] == "install":
            reply = self.web.draft_action("install", str(values["draft"]))
            if not reply.get("ok"):
                return False, f"Not installed ({reply.get('code')})."
            return True, str(reply.get("text") or f"Installed as {reply.get('installed_as')}.")
        kind, asset = str(values["kind"]), str(values["asset"])
        if values["action"] == "remove":
            reply = self.web.remove_asset(kind, asset)
        else:
            reply = self.web.switch_asset(kind, asset, values["action"] == "switch_on")
        return bool(reply.get("ok")), str(reply.get("message") or reply.get("code"))

    # platform add ------------------------------------------------------------------

    def _parsed(self, values: Mapping[str, Any]) -> tuple[str, AssetIdentity]:
        from host_runtime import asset_shelf

        try:
            return asset_shelf.parse(str(values.get("kind") or ""),
                                     str(values.get("asset") or ""))
        except asset_shelf.ShelfError as error:
            raise ProposalRefused(
                "Name kind (skill or workflow) and asset as namespace/name@version."
                if error.code == "bad_reference" else "kind is skill or workflow.") from None

    def _now_platform_add(self, values: Mapping[str, Any]) -> dict[str, Any]:
        kind, identity = self._parsed(values)
        layout = self.web.runtime.layout
        folder = layout.skills if kind == "skill" else layout.workflows
        installed = (folder / f"{identity.namespace}__{identity.name}__{identity.version}"
                     ".json").is_file()
        return {"selected": self.web._selected_here(kind, identity), "installed": installed}

    def _plan_platform_add(self, values: Mapping[str, Any], snapshot: dict[str, Any]) -> Plan:
        _only("platform_add", values, {"kind": "kind", "asset": "asset"})
        kind, identity = self._parsed(values)
        if self.web.runtime.platform is None or self.web._publisher() is None:
            raise ProposalRefused("This PC is not set up for the shared platform: see "
                                  f"{PASTE_WHERE['platform_add']}.")
        if snapshot["selected"] and snapshot["installed"]:
            raise ProposalRefused("It is already selected and installed on this PC.")
        reference = f"{identity.namespace}/{identity.name}@{identity.version}"
        return Plan(
            title=f"Add {identity.name} to this Agent",
            values={"kind": kind, "asset": reference},
            rows=[CardRow(label=f"{kind.title()} {reference} on this PC",
                          before="selected" if snapshot["selected"] else "not selected",
                          after="selected and installed")],
            effects=["This selects it for this PC on the shared platform and synchronizes; "
                     "the files are installed, and what this PC may run still comes from "
                     "its grants."],
            link=CardLink(label="Open Capabilities", view="installed",
                          capability_kind="workflows" if kind == "workflow" else "skills",
                          asset=reference))

    def _apply_platform_add(self, proposal: ChangeProposal) -> tuple[bool, str]:
        reply = self.web.add_to_agent(str(proposal.values["kind"]),
                                      str(proposal.values["asset"]))
        return bool(reply.get("ok")), str(reply.get("message") or reply.get("code"))

    # publish -----------------------------------------------------------------------

    def _now_publish(self, values: Mapping[str, Any]) -> dict[str, Any]:
        from host_runtime.platform_publish import PublishError, installed_manifest

        kind, identity = self._parsed(values)
        reference = f"{identity.namespace}/{identity.name}@{identity.version}"
        try:
            manifest = installed_manifest(self.web.runtime.layout, kind,  # type: ignore[arg-type]
                                          reference)
        except PublishError:
            return {"installed": None}
        return {"installed": fingerprint(manifest)}

    def _plan_publish(self, values: Mapping[str, Any], snapshot: dict[str, Any]) -> Plan:
        from host_runtime.platform_publish import CHANGES, VISIBILITIES

        _only("publish", values, {"kind": "kind", "asset": "asset", "change": "change",
                                  "visibility": "visibility", "note": "note"})
        kind, identity = self._parsed(values)
        if snapshot["installed"] is None:
            raise ProposalRefused("Only an installed Skill or Workflow of this exact version "
                                  "can be published.")
        change = str(values.get("change") or "")
        visibility = str(values.get("visibility") or "")
        note = str(values.get("note") or "").strip()
        if change not in CHANGES:
            raise ProposalRefused(f"change is one of {', '.join(CHANGES)}.")
        if visibility and visibility not in VISIBILITIES:
            raise ProposalRefused(f"visibility is one of {', '.join(VISIBILITIES)}.")
        if len(note) > 500:
            raise ProposalRefused("Keep the note under 500 characters.")
        if self.web._publisher() is None:
            raise ProposalRefused("Publishing is not set up: see "
                                  f"{PASTE_WHERE['publish']}.")
        reference = f"{identity.namespace}/{identity.name}@{identity.version}"
        rows = [CardRow(label=f"Submit {kind} {reference}", before="not submitted",
                        after=f"{change} change for review"),
                CardRow(label="Who can use it", before="", after=visibility or "the default")]
        if note:
            rows.append(CardRow(label="Note to reviewers", before="", after=note[:400]))
        return Plan(title=f"Publish {identity.name} to the shared platform",
                    values={"kind": kind, "asset": reference, "change": change,
                            "visibility": visibility, "note": note},
                    rows=rows,
                    effects=["Reviewers on the shared platform see it; nobody else gets it "
                             "until they approve it."],
                    link=CardLink(label="Open Capabilities", view="installed",
                                  capability_kind="workflows" if kind == "workflow"
                                  else "skills", asset=reference))

    def _apply_publish(self, proposal: ChangeProposal) -> tuple[bool, str]:
        values = proposal.values
        reply = self.web.publish_asset(str(values["kind"]), str(values["asset"]),
                                       str(values["change"]), str(values["note"]),
                                       str(values["visibility"]))
        if not reply.get("ok"):
            return False, str(reply.get("message") or reply.get("code"))
        return True, "Submitted; it is waiting for review."


def diff_summary(rows: tuple[CardRow, ...] | list[CardRow]) -> str:
    return "; ".join(f"{row.label}: {row.before or '(empty)'} → {row.after or '(empty)'}"
                     for row in rows)[:240]


def draw(proposal: ChangeProposal) -> ActionCard:
    """The card a proposal is shown as, in Agent Web and Telegram alike."""
    pending = proposal.status == "pending"
    return ActionCard(
        card_id=proposal.card_id, kind="change_proposal", title=proposal.title,
        rows=proposal.rows, reason=proposal.reason, effects=proposal.effects,
        buttons=(CardButton(action="apply", label="Apply", style="primary"),
                 CardButton(action="cancel", label="Cancel")) if pending else (),
        status=proposal.status, status_label=STATUS_LABELS.get(proposal.status, ""),
        outcome=proposal.outcome, outcome_ok=proposal.outcome_ok, link=proposal.link,
        expires_at=proposal.expires_at, web_only=not proposal.telegram_ok,
        message=(f"{proposal.title}: nothing changes until you press Apply on the card "
                 f"(it expires in {EXPIRY_MINUTES} minutes)."))
