"""Independent Application projection over governed Software metadata."""

from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import model_validator

from common.assets import AssetIdentity, RegistryContract
from common.base import Slug, Symbol, Text
from software.evolution import SoftwareManifest


class ApplicationIntegration(RegistryContract):
    name: Symbol
    kind: Literal["web_ui", "api", "mcp", "workflow"]
    interface: Symbol | None = None
    url: Text | None = None
    workflow: AssetIdentity | None = None

    @model_validator(mode="after")
    def one_external_integration(self) -> Self:
        if self.kind == "workflow":
            if self.workflow is None or self.url is not None or self.interface is not None:
                raise ValueError("Workflow integration names only an exact Workflow")
            return self
        if self.url is None or self.workflow is not None:
            raise ValueError("Application network integrations require only a URL")
        parts = urlsplit(self.url)
        if parts.scheme not in ("https", "http") or not parts.hostname:
            raise ValueError("Application integration URL must be HTTP or HTTPS")
        if parts.scheme == "http" and parts.hostname not in ("127.0.0.1", "::1", "localhost"):
            raise ValueError("Application integration beyond loopback requires HTTPS")
        if self.kind in ("api", "mcp") and self.interface is None:
            raise ValueError("API and MCP integrations name a Software interface")
        if self.kind == "web_ui" and self.interface is not None:
            raise ValueError("a Web UI is navigation, not a callable interface")
        return self


class ApplicationCatalogEntry(RegistryContract):
    """A Software product shown as an App, never an Agent/Bridge package."""

    kind: Literal["application"] = "application"
    software: SoftwareManifest
    integrations: tuple[ApplicationIntegration, ...]

    @model_validator(mode="after")
    def published_external_product(self) -> Self:
        if self.software.metadata.lifecycle != "published":
            raise ValueError("only published Software is presented as an Application")
        names = [item.name for item in self.integrations]
        if not names or len(names) != len(set(names)):
            raise ValueError("an Application has unique integration names")
        declared = {item.name for item in self.software.interfaces}
        if any(
            item.interface is not None and item.interface not in declared
            for item in self.integrations
        ):
            raise ValueError("Application integration must name a declared Software interface")
        return self


class ApplicationProjection(RegistryContract):
    kind: Literal["application"] = "application"
    identity: AssetIdentity
    owner: Text
    repository_provider: Symbol
    repository_locator: Text
    release_ref: Text
    integrations: tuple[ApplicationIntegration, ...]


class ApplicationCatalogRequest(RegistryContract):
    namespace: Slug | None = None


class ApplicationCatalogReply(RegistryContract):
    applications: tuple[ApplicationProjection, ...]


class ApplicationCatalog:
    """Exact Application metadata; it owns no process, package or deployment."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], ApplicationCatalogEntry] = {}

    def register(self, entry: ApplicationCatalogEntry) -> None:
        checked = ApplicationCatalogEntry.model_validate(entry)
        key = checked.software.metadata.identity.key
        if key in self._entries:
            raise ValueError("Application version already registered")
        self._entries[key] = checked

    def discover(self, namespace: str | None = None) -> tuple[ApplicationCatalogEntry, ...]:
        return tuple(
            entry
            for key, entry in sorted(self._entries.items())
            if namespace is None or key[0] == namespace
        )


def project_application(entry: ApplicationCatalogEntry) -> ApplicationProjection:
    checked = ApplicationCatalogEntry.model_validate(entry)
    software = checked.software
    return ApplicationProjection(
        identity=software.metadata.identity,
        owner=f"{software.metadata.owner.type}:{software.metadata.owner.id}",
        repository_provider=software.repository.provider,
        repository_locator=software.repository.locator,
        release_ref=software.release.release_ref,
        integrations=checked.integrations,
    )
