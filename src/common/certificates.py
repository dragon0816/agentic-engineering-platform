"""Trust for a shared platform served with a self-signed certificate
(owner 2026-10-16, `docs/phases/BRIDGE_ENROLLMENT.md` "TLS and certificate
pinning").

A company platform on a test machine has no certificate a Windows PC already
trusts. Verification is never switched off for that: a host either

- pins the exact certificate by its SHA-256 fingerprint, which the platform's
  administrator hands out and the member compares before trusting it (the SSH
  "known host" model), or
- names a CA file (PEM) to verify the chain and the host name against, or
- relies on the system's trust store, as for any public site.

Only the pinned connection skips the chain and name checks, and only because
it compares the whole certificate instead, before a single request byte (an
`Authorization` header included) is sent. Every other HTTPS connection in the
process keeps the default context; nothing here is global.

Standard library only, so the platform and the Agent install stay `pydantic`
alone.
"""

from __future__ import annotations

import functools
import hashlib
import http.client
import re
import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

# What a member types or pastes: 32 hex pairs, with or without separators.
_SEPARATORS = re.compile(r"[\s:\-]")
_HEX64 = re.compile(r"[0-9A-Fa-f]{64}")
PEM_BLOCK = re.compile(r"-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\s]+?-----END CERTIFICATE-----")


def normalize_fingerprint(value: str) -> str:
    """`AB:CD:...` (upper case, colon-separated), the form browsers and
    Windows' certificate dialog show; ValueError when it is not a SHA-256."""
    compact = _SEPARATORS.sub("", value.strip())
    if compact.lower().startswith("sha256"):
        compact = compact[6:].lstrip("=")
    if not _HEX64.fullmatch(compact):
        raise ValueError("a certificate fingerprint is a SHA-256: 64 hexadecimal digits")
    upper = compact.upper()
    return ":".join(upper[index : index + 2] for index in range(0, 64, 2))


def fingerprint(der: bytes) -> str:
    """The SHA-256 fingerprint of a DER certificate, normalized."""
    return normalize_fingerprint(hashlib.sha256(der).hexdigest())


def pem_fingerprint(pem: str) -> str:
    """The fingerprint of the first certificate in a PEM text (a file the
    platform serves with, so an administrator can hand the value out)."""
    found = PEM_BLOCK.search(pem)
    if found is None:
        raise ValueError("no PEM certificate found")
    return fingerprint(ssl.PEM_cert_to_DER_cert(found.group(0)))


class CertificateUntrusted(OSError):
    """The platform's certificate is not one this host trusts. Carries
    fingerprints only, which are public."""

    def __init__(self, presented: str | None, expected: str | None) -> None:
        self.presented = presented
        self.expected = expected
        if expected is None:
            detail = "the certificate is not trusted by this PC"
        else:
            detail = f"presented {presented}, pinned {expected}"
        super().__init__(f"certificate_untrusted: {detail}")


def certificate_problem(error: BaseException | None) -> BaseException | None:
    """The certificate failure inside `error` (urllib wraps it in URLError),
    or None when the error is about something else."""
    seen = 0
    while error is not None and seen < 5:
        if isinstance(error, (CertificateUntrusted, ssl.SSLCertVerificationError)):
            return error
        reason = getattr(error, "reason", None)
        if isinstance(error, urllib.error.URLError) and isinstance(reason, BaseException):
            error = reason
        else:
            error = error.__cause__ or error.__context__
        seen += 1
    return None


def describe_problem(problem: BaseException) -> str:
    """One sentence for a person; fingerprints only, never anything else."""
    if isinstance(problem, CertificateUntrusted) and problem.expected is not None:
        return (
            f"The platform presented certificate {problem.presented}, but this PC trusts "
            f"{problem.expected}. If the administrator replaced the certificate, compare the "
            "new fingerprint with the one they gave you and trust it again in Settings > "
            "Shared platform; otherwise do not connect."
        )
    return (
        "The platform's certificate is not trusted by this PC (self-signed or from an unknown "
        "authority). In Settings > Shared platform press 'Fetch & show fingerprint', compare it "
        "with the one your administrator gave you and press 'Trust this certificate'."
    )


def _pinned_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    # The pin compares the whole certificate right after the handshake and
    # before anything is sent, which is stronger than a chain and a name; the
    # two checks are off for this one connection only.
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """An HTTPS connection that accepts exactly one certificate."""

    def __init__(self, host: str, *, pin: str, **kwargs: Any) -> None:
        kwargs.pop("context", None)
        kwargs.pop("check_hostname", None)
        super().__init__(host, context=_pinned_context(), **kwargs)
        self._pin = normalize_fingerprint(pin)

    def connect(self) -> None:
        super().connect()
        der = self.sock.getpeercert(binary_form=True) if self.sock is not None else None
        presented = fingerprint(der) if der else None
        if presented != self._pin:
            if self.sock is not None:
                self.sock.close()
            self.sock = None
            raise CertificateUntrusted(presented, self._pin)


class PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    """urllib's HTTPS handler for a pinned platform."""

    def __init__(self, pin: str) -> None:
        super().__init__()
        self.pin = normalize_fingerprint(pin)

    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(
            functools.partial(PinnedHTTPSConnection, pin=self.pin),
            req,
        )


def https_handler(
    certificate_sha256: str | None = None, ca_file: str | None = None
) -> urllib.request.HTTPSHandler:
    """The HTTPS handler for one platform binding: pinned, a CA file, or the
    system's trust store (the default, verified as always)."""
    if certificate_sha256:
        return PinnedHTTPSHandler(certificate_sha256)
    if ca_file:
        return urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca_file))
    return urllib.request.HTTPSHandler(context=ssl.create_default_context())


@dataclass(frozen=True)
class PresentedCertificate:
    """What a server presented: public facts only."""

    fingerprint: str
    pem: str
    trusted_by_system: bool


def _address(url: str) -> tuple[str, int]:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("only an https address presents a certificate")
    return parts.hostname, parts.port or 443


def presented_certificate(url: str, timeout: float = 8.0) -> PresentedCertificate:
    """Read the certificate an https origin presents, to show its
    fingerprint to the member before they decide to trust it. Nothing is
    sent but the TLS handshake; the result is not trusted by this call."""
    host, port = _address(url)
    with socket.create_connection((host, port), timeout=timeout) as raw:
        with _pinned_context().wrap_socket(raw, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    if not der:
        raise CertificateUntrusted(None, None)
    trusted = True
    try:
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with ssl.create_default_context().wrap_socket(raw, server_hostname=host):
                pass
    except ssl.SSLError:
        trusted = False
    return PresentedCertificate(
        fingerprint=fingerprint(der),
        pem=ssl.DER_cert_to_PEM_cert(der),
        trusted_by_system=trusted,
    )
