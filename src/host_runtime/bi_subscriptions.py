"""`/api/bi/subscriptions*`: subscribing to BI datasets shared through the
Shared Platform, the update badge, the manual update and unsubscribing
(BI dataset sharing slice 1, owner 2026-10-22; contract in
`docs/CONTRACTS.md` "BI dataset sharing" → "Agent subscriptions API").

Subscribing and updating are the member's own decisions, made the way the
Library's "+ Add to this Agent" makes them: the member's Personal Agent
login selects one exact version for this computer's Bridge, then the
existing verified sync installs it. A new version is never installed by
itself. The platform not answering changes nothing but the `offline` status.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from capabilities.bi_cards import subscriptions
from capabilities.bi_cards.store import subscribed_datasets
from capabilities.bi_cards.subscriptions import (
    KIND,
    Offer,
    PreparedInstall,
    SubscriptionError,
    prepare,
)

# What the Bridge's sync uses to install a `bi_dataset` package
# (`host_runtime.sync`), so the harness never names the BI package itself.
__all__ = ["KIND", "PreparedInstall", "SubscriptionError", "prepare", "route"]

Answer = tuple[int, dict[str, Any]]


class SubscriptionPlatform(Protocol):
    """What the routes need from the platform; Agent Web provides it."""

    def offers(self) -> list[Offer] | None:
        """Every `bi_dataset` version this member may use; None when the
        platform did not answer."""

    def select(self, namespace: str, name: str, version: str) -> None:
        """Select one exact version for this Bridge; raises SubscriptionError."""

    def revoke(self, namespace: str, name: str, version: str) -> None:
        """Take back the selection of one exact version; raises SubscriptionError."""

    def synchronize(self) -> dict[str, Any]:
        """Run the verified sync; `{"status", "failure"}`."""

    def forget(self, namespace: str, name: str, version: str) -> None:
        """Drop the installed-inventory row of a version no longer on disk."""


def _error(status: int, code: str, message: str) -> Answer:
    return status, {"ok": False, "code": code, "message": message}


NOT_CONFIGURED = "這台電腦還沒有設定 Shared Platform（Settings → Shared platform）"
UNREACHABLE = "無法連線 Shared Platform；已訂閱的資料集照常可讀"


def _offers(workspace: Path, platform: SubscriptionPlatform | None) -> list[Offer] | None:
    if platform is None:
        return None
    offers = platform.offers()
    subscriptions.observe(workspace, offers)
    return offers


def _newest(offers: list[Offer], dataset: str) -> Offer | None:
    found = [offer for offer in offers if offer.dataset == dataset]
    return max(found, key=lambda o: subscriptions.version_key(o.version), default=None)


def _available(workspace: Path, offers: list[Offer]) -> list[dict[str, Any]]:
    mine = {item["name"] for item in subscriptions.listing(workspace)}
    newest: dict[str, Offer] = {}
    for offer in offers:
        if offer.dataset in mine:
            continue
        held = newest.get(offer.dataset)
        if held is None or subscriptions.version_key(offer.version) > subscriptions.version_key(
            held.version
        ):
            newest[offer.dataset] = offer
    return [
        {
            "name": offer.dataset,
            "version": offer.version,
            "description": offer.description,
            "owner": offer.owner,
        }
        for _, offer in sorted(newest.items())
    ]


def _install(
    workspace: Path, platform: SubscriptionPlatform, offer: Offer, previous: str | None
) -> Answer:
    """Select `offer` and sync; the answer says what is installed now."""
    try:
        platform.select(offer.namespace, offer.name, offer.version)
    except SubscriptionError as error:
        if error.code != "duplicate_selection":
            return _error(
                409 if error.code.startswith("asset_not") else 502, error.code, error.message
            )
    synchronized = platform.synchronize()
    now = subscriptions.entry(workspace, offer.dataset)
    if now is None or now["version"] != offer.version:
        failure = synchronized.get("failure") or {}
        code = str(failure.get("code") or synchronized.get("status") or "sync_failed")
        return _error(
            502,
            code,
            f"已在平台上選取 {offer.dataset} {offer.version}，但這台電腦沒有裝上（{code}）；"
            "原本的版本照常可讀",
        )
    if previous and previous != offer.version:
        platform.forget(offer.namespace, offer.name, previous)
    return 200, {"ok": True, "subscription": now}


def route(
    workspace: Path,
    platform: SubscriptionPlatform | None,
    method: str,
    path: str,
    query: Mapping[str, str],
    given: dict[str, Any],
) -> Answer:
    if method == "GET" and path == "/api/bi/subscriptions":
        reply: dict[str, Any] = {"ok": True, "configured": platform is not None}
        if query.get("refresh") in ("1", "true") and platform is not None:
            offers = _offers(workspace, platform)
            reply["connection"] = "answered" if offers is not None else "unreachable"
            reply["available"] = _available(workspace, offers) if offers is not None else []
        reply["subscriptions"] = subscriptions.listing(workspace)
        return 200, reply
    if method != "POST":
        return _error(405, "method_not_allowed", "只接受 GET 與 POST")
    dataset = str(given.get("dataset") or "")
    try:
        namespace, name = subscriptions.split(dataset)
    except SubscriptionError as error:
        return _error(400, error.code, error.message)
    current = subscriptions.entry(workspace, dataset)
    if path == "/api/bi/subscriptions/unsubscribe":
        if current is None:
            return _error(404, "subscription_unknown", f"沒有訂閱 {dataset}")
        deselected = False
        if platform is not None:
            try:
                platform.revoke(namespace, name, current["version"])
                deselected = True
            except SubscriptionError:
                deselected = False  # the local copy goes either way
        subscriptions.remove(workspace, dataset)
        if platform is not None:
            platform.forget(namespace, name, current["version"])
        return 200, {"ok": True, "removed": dataset, "deselected": deselected}
    if path not in ("/api/bi/subscriptions/update", "/api/bi/subscriptions/subscribe"):
        return _error(404, "route_unknown", "沒有這個 BI 路徑")
    if platform is None:
        return _error(409, "platform_not_configured", NOT_CONFIGURED)
    if path == "/api/bi/subscriptions/update" and current is None:
        return _error(404, "subscription_unknown", f"沒有訂閱 {dataset}")
    offers = _offers(workspace, platform)
    if offers is None:
        return _error(503, "platform_unreachable", UNREACHABLE)
    offer = _newest(offers, dataset)
    if offer is None:
        return _error(
            403,
            "dataset_no_access",
            f"你目前沒有 {dataset} 的使用權限"
            + ("；本機副本保留，已停止更新" if current is not None else ""),
        )
    if current is not None and subscriptions.version_key(
        current["version"]
    ) >= subscriptions.version_key(offer.version):
        return 200, {"ok": True, "already": True, "subscription": current}
    return _install(workspace, platform, offer, current["version"] if current else None)


def offers_from(packages: Any) -> list[Offer]:
    """The `bi_dataset` versions in a catalog reply's packages."""
    found = []
    for package in packages or ():
        if package.kind != subscriptions.KIND:
            continue
        metadata = package.metadata
        identity = metadata.identity
        found.append(
            Offer(
                namespace=identity.namespace,
                name=identity.name,
                version=identity.version,
                description=package.description or "",
                owner=f"{metadata.owner.type}:{metadata.owner.id}",
            )
        )
    return found


def catalog_offers(client: Any) -> list[Offer] | None:
    """The `bi_dataset` versions the Bridge API `catalog` lists for this
    member (`{"kinds": ["bi_dataset"]}`); None when it did not answer. A held
    name missing from an answer is no longer entitled (contract)."""
    import asyncio

    outcome = asyncio.run(client.catalog(kinds=(subscriptions.KIND,)))
    if outcome.status != "answered" or outcome.reply is None:
        return None
    return offers_from(outcome.reply.packages)


def observe_catalog(workspace: Path, client: Any, outcome: Any) -> None:
    """After Agent Web read the catalog (`outcome`): record access, newest
    versions or `offline` on every subscription. Asks the platform once more
    for the `bi_dataset` kind only when something is subscribed and the first
    call answered. Never raises: the Settings page must not fail on this."""
    try:
        if not subscribed_datasets(workspace):
            return
        if outcome.status != "answered":
            subscriptions.observe(workspace, None)
            return
        subscriptions.observe(workspace, catalog_offers(client))
    except Exception:  # noqa: BLE001 - a status note, never a reason to fail the page
        return


class WebPlatform:
    """`SubscriptionPlatform` over Agent Web: the member's Personal Agent
    login selects, the Bridge's verified sync installs."""

    def __init__(self, web: Any) -> None:
        self.web = web

    def offers(self) -> list[Offer] | None:
        return catalog_offers(self.web.runtime.platform)

    def _member(self, operation: str, namespace: str, name: str, version: str) -> None:
        from host_runtime.platform_publish import PublishError, explain

        publisher = self.web._publisher()
        if publisher is None:
            raise SubscriptionError(
                "publishing_not_configured",
                "Settings → Shared platform 還沒有 Member Portal 網址與 Personal Agent code",
            )
        asset = {"namespace": namespace, "name": name, "version": version}
        bridge_id = self.web.runtime.config.device.bridge_id
        try:
            getattr(publisher, operation)(bridge_id, asset)
        except PublishError as error:
            raise SubscriptionError(error.code, explain(error.code)) from None

    def select(self, namespace: str, name: str, version: str) -> None:
        self._member("select", namespace, name, version)

    def revoke(self, namespace: str, name: str, version: str) -> None:
        self._member("revoke", namespace, name, version)

    def synchronize(self) -> dict[str, Any]:
        result: dict[str, Any] = self.web.synchronize()
        return result

    def forget(self, namespace: str, name: str, version: str) -> None:
        from common.assets import AssetIdentity

        try:
            self.web.runtime.state.forget(
                AssetIdentity(namespace=namespace, name=name, version=version)
            )
        except Exception:  # noqa: BLE001 - the inventory row is bookkeeping only
            return
