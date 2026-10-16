"""Agents trust a shared platform with a self-signed certificate by pinning it.

Requirements: owner request 2026-10-16 (`docs/phases/BRIDGE_ENROLLMENT.md`
"TLS and certificate pinning"): the platform on the company network serves
https with a self-signed certificate; host.json `platform` and `publishing`
carry an optional SHA-256 pin (or a CA file); the Bridge client, the member
publisher (browser ticket, Library content, enrollment) and the enrollment
check use it; a missing or wrong pin fails with `certificate_untrusted`
before any request byte is sent; verification is never disabled globally.
Agent Web's "Shared platform" card fetches and shows the presented
fingerprint and trusts it. Everything runs against a real in-process
platform served over TLS with a certificate generated for the test.
"""

from __future__ import annotations

import json
import shutil
import socket
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_host_wiring import host_json, ready

from common.certificates import (
    CertificateUntrusted,
    PinnedHTTPSHandler,
    certificate_problem,
    normalize_fingerprint,
    pem_fingerprint,
    presented_certificate,
)
from common.enrollment import Invitation
from control_plane.app import SharedPlatformApplication
from control_plane.cli import main as platform_cli
from host_runtime.contracts import (
    CompanyHostConfiguration,
    PlatformBinding,
    PlatformPublishBinding,
)
from host_runtime.host import build_runtime
from host_runtime.platform_publish import MemberPortalPublisher, PublishError
from host_runtime.shared_platform import LOGIN_VARIABLE, TOKEN_VARIABLE
from host_runtime.sync import PlatformClient
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE
from integrations.browser import Browser, browser_path
from models.credentials import EnvironmentCredentials

WRONG_PIN = ":".join(["AB"] * 32)


def _openssl() -> str | None:
    found = shutil.which("openssl")
    if found:
        return found
    for candidate in (
        r"C:\Program Files\Git\usr\bin\openssl.exe",
        r"C:\Program Files\Git\mingw64\bin\openssl.exe",
        r"C:\Program Files\OpenSSL\bin\openssl.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    return None


OPENSSL = _openssl()
pytestmark = pytest.mark.skipif(OPENSSL is None, reason="openssl is needed to make a test cert")


def _self_signed(folder: Path, name: str) -> tuple[Path, Path]:
    """A throwaway self-signed certificate for 127.0.0.1, made for this test."""
    assert OPENSSL is not None
    folder.mkdir(parents=True, exist_ok=True)
    cert, key = folder / f"{name}.pem", folder / f"{name}-key.pem"
    subprocess.run(
        [
            OPENSSL,
            "req",
            "-x509",
            "-newkey",
            "ec",
            "-pkeyopt",
            "ec_paramgen_curve:prime256v1",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "2",
            "-subj",
            "/CN=127.0.0.1",
            "-addext",
            "subjectAltName=IP:127.0.0.1,DNS:localhost",
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    return cert, key


@pytest.fixture(scope="module")
def certificates(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    folder = tmp_path_factory.mktemp("tls")
    cert, key = _self_signed(folder, "platform")
    other, other_key = _self_signed(folder, "impostor")
    return {"cert": cert, "key": key, "other": other, "other_key": other_key}


def _server_context(cert: Path, key: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert, key)
    return context


@pytest.fixture
def app(tmp_path: Path, certificates: dict[str, Path]) -> Iterator[SharedPlatformApplication]:
    platform = SharedPlatformApplication.empty(
        administrators=("platform-admin",),
        registry_path=tmp_path / "registry.sqlite",
        ssl_context=_server_context(certificates["cert"], certificates["key"]),
    )
    with platform:
        yield platform


@pytest.fixture
def pin(certificates: dict[str, Path]) -> str:
    return pem_fingerprint(certificates["cert"].read_text(encoding="ascii"))


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (TOKEN_VARIABLE, LOGIN_VARIABLE):
        monkeypatch.delenv(name, raising=False)
    from host_runtime import platform_publish

    monkeypatch.setattr(platform_publish, "_saved_user_variable", lambda name: None)


def _post(url: str, pin: str, authorization: str, body: object | None = None) -> dict[str, Any]:
    """A member's call made the way a test trusts the platform: pinned."""
    opener = urllib.request.build_opener(PinnedHTTPSHandler(pin))
    raw = None if body is None else json.dumps(body).encode("utf-8")
    sent = urllib.request.Request(url, method="POST", data=raw)
    sent.add_header("Authorization", authorization)
    if raw is not None:
        sent.add_header("Content-Type", "application/json")
    with opener.open(sent, timeout=20) as answer:
        reply: dict[str, Any] = json.loads(answer.read())
    return reply


def _agent_login(app: SharedPlatformApplication, pin: str, actor: str = "engineer") -> str:
    proof = app.issue_invitation(
        Invitation(
            invitation_id=f"invite-{actor}",
            actor=actor,
            issued_by="platform-admin",
            groups=("engineering",),
            role="member",
        ),
        expires_at=app.member_service.now() + timedelta(days=1),
    )
    session = _post(app.member_base_url + "/v1/member/sign-in", pin, f"Invitation {proof.bearer}")[
        "session"
    ]
    issued = _post(
        app.member_base_url + "/v1/member/logins/issue-agent", pin, f"Bearer {session}", {}
    )
    return str(issued["login"])


# -- the pin itself -------------------------------------------------------------


def test_a_fingerprint_is_accepted_in_the_forms_people_paste() -> None:
    compact = "ab" * 32
    expected = ":".join(["AB"] * 32)
    for typed in (compact, compact.upper(), expected, expected.lower(), f"SHA256={compact}"):
        assert normalize_fingerprint(typed) == expected
    assert normalize_fingerprint(" ".join(["ab"] * 32)) == expected
    for bad in ("", "ab" * 31, "zz" * 32, "ab" * 33):
        with pytest.raises(ValueError):
            normalize_fingerprint(bad)


def test_bindings_carry_a_normalized_pin_or_a_ca_file_never_both() -> None:
    binding = PlatformBinding(
        base_url="https://172.25.228.141:8775",
        member_portal_url="https://172.25.228.141:8776",
        token_id="token-0000000000000000",
        credential={"name": "shared_platform_token"},
        certificate_sha256="ab" * 32,
    )
    assert binding.certificate_sha256 == WRONG_PIN
    publish = PlatformPublishBinding(
        member_portal_url="https://172.25.228.141:8776",
        credential={"name": "platform_member_login"},
        ca_file=r"C:\certs\platform.pem",
    )
    assert publish.ca_file == r"C:\certs\platform.pem" and publish.certificate_sha256 is None
    with pytest.raises(ValidationError, match="not both"):
        PlatformPublishBinding(
            member_portal_url="https://172.25.228.141:8776",
            credential={"name": "platform_member_login"},
            certificate_sha256=WRONG_PIN,
            ca_file=r"C:\certs\platform.pem",
        )
    with pytest.raises(ValidationError):
        PlatformPublishBinding(
            member_portal_url="https://172.25.228.141:8776",
            credential={"name": "platform_member_login"},
            certificate_sha256="not-a-fingerprint",
        )
    # Plain http beyond loopback stays refused, pin or not.
    with pytest.raises(ValidationError, match="https"):
        PlatformPublishBinding(
            member_portal_url="http://172.25.228.141:8776",
            credential={"name": "platform_member_login"},
            certificate_sha256=WRONG_PIN,
        )


def test_the_cli_prints_the_fingerprint_an_administrator_hands_out(
    tmp_path: Path, certificates: dict[str, Path], pin: str, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "platform.json"
    config.write_text(
        json.dumps(
            {
                "administrators": ["platform-admin"],
                "listen_host": "127.0.0.1",
                "tls_certificate_path": str(certificates["cert"]),
                "tls_private_key_path": str(certificates["key"]),
            }
        ),
        encoding="utf-8",
    )
    assert platform_cli(["certificate-fingerprint", "--config", str(config)]) == 0
    printed = capsys.readouterr().out
    assert f"SHA-256 fingerprint: {pin}" in printed
    assert "PRIVATE" not in printed


# -- the wire -------------------------------------------------------------------


class _RecordingTlsServer:
    """One TLS connection whose received bytes are kept, to prove a wrong
    pin sends nothing at all."""

    def __init__(self, cert: Path, key: Path) -> None:
        self.context = _server_context(cert, key)
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.received = b""
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        raw, _ = self.listener.accept()
        try:
            with self.context.wrap_socket(raw, server_side=True) as tls:
                tls.settimeout(1.5)
                try:
                    while chunk := tls.recv(4096):
                        self.received += chunk
                        if b"\r\n\r\n" in self.received:
                            tls.sendall(
                                b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n"
                                b'Connection: close\r\n\r\n{"ok":true}'
                            )
                            return
                except (OSError, ssl.SSLError):
                    return
        except (OSError, ssl.SSLError):
            return
        finally:
            self.listener.close()


def test_a_wrong_pin_fails_before_any_request_byte_and_a_right_one_connects(
    certificates: dict[str, Path], pin: str
) -> None:
    wrong = _RecordingTlsServer(certificates["cert"], certificates["key"])
    opener = urllib.request.build_opener(PinnedHTTPSHandler(WRONG_PIN))
    sent = urllib.request.Request(f"https://127.0.0.1:{wrong.port}/v1/probe", method="POST")
    sent.add_header("Authorization", "Bearer token-0000000000000000:never-sent-on-a-wrong-pin")
    with pytest.raises(urllib.error.URLError) as raised:
        opener.open(sent, timeout=10)
    problem = certificate_problem(raised.value)
    assert isinstance(problem, CertificateUntrusted)
    assert problem.presented == pin and problem.expected == WRONG_PIN
    wrong.thread.join(timeout=5)
    assert wrong.received == b""

    right = _RecordingTlsServer(certificates["cert"], certificates["key"])
    opener = urllib.request.build_opener(PinnedHTTPSHandler(pin))
    with opener.open(f"https://127.0.0.1:{right.port}/v1/health", timeout=10) as answer:
        assert json.loads(answer.read()) == {"ok": True}
    right.thread.join(timeout=5)
    assert right.received.startswith(b"GET /v1/health")


def test_verification_stays_on_for_everything_else(
    app: SharedPlatformApplication, certificates: dict[str, Path], pin: str
) -> None:
    assert ssl._create_default_https_context is ssl.create_default_context
    # The process-wide default still refuses the self-signed platform ...
    with pytest.raises(urllib.error.URLError) as raised:
        urllib.request.urlopen(app.control_base_url + "/v1/health", timeout=10)  # noqa: S310
    assert isinstance(certificate_problem(raised.value), ssl.SSLCertVerificationError)
    # ... after a pinned call has succeeded in the same process.
    opener = urllib.request.build_opener(PinnedHTTPSHandler(pin))
    with opener.open(app.control_base_url + "/v1/health", timeout=10) as answer:
        assert answer.status == 200
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(app.member_base_url + "/", timeout=10)  # noqa: S310
    presented = presented_certificate(app.member_base_url)
    assert presented.fingerprint == pin and presented.trusted_by_system is False
    assert "PRIVATE" not in presented.pem and presented.pem.startswith("-----BEGIN CERTIFICATE")


def test_the_bridge_client_and_the_publisher_use_the_pin_or_a_ca_file(
    app: SharedPlatformApplication, certificates: dict[str, Path], pin: str
) -> None:
    login = _agent_login(app, pin)
    environ = {"LOGIN": login, "TOKEN": "x" * 40}
    resolver = EnvironmentCredentials(
        {"platform_member_login": "LOGIN", "shared_platform_token": "TOKEN"}, environ
    )

    def publisher(**trust: Any) -> MemberPortalPublisher:
        binding = PlatformPublishBinding(
            member_portal_url=app.member_base_url,
            credential={"name": "platform_member_login"},
            timeout_seconds=10,
            **trust,
        )
        return MemberPortalPublisher(binding, resolver)

    def client(**trust: Any) -> PlatformClient:
        binding = PlatformBinding(
            base_url=app.control_base_url,
            token_id="token-0000000000000000",
            credential={"name": "shared_platform_token"},
            timeout_seconds=10,
            **trust,
        )
        return PlatformClient(binding, resolver)

    import asyncio

    # Pinned: the member's calls and the Bridge client reach the platform
    # (an unknown token is the platform's own answer, past TLS).
    assert publisher(certificate_sha256=pin).me() == "engineer"
    assert publisher(certificate_sha256=pin).browser_ticket().startswith("ticket-")
    probed = asyncio.run(client(certificate_sha256=pin).probe())
    assert probed.status == "rejected", probed

    # A CA file naming the certificate verifies chain and name the usual way.
    assert publisher(ca_file=str(certificates["cert"])).me() == "engineer"
    assert asyncio.run(client(ca_file=str(certificates["cert"])).probe()).status == "rejected"

    # No pin, a wrong pin, or a CA file of another certificate: refused as
    # certificate_untrusted, never retried as a moment to wait out.
    for trust in ({}, {"certificate_sha256": WRONG_PIN}, {"ca_file": str(certificates["other"])}):
        with pytest.raises(PublishError) as refused:
            publisher(**trust).me()
        assert refused.value.code == "certificate_untrusted"
        outcome = asyncio.run(client(**trust).probe())
        assert outcome.status == "unreachable" and outcome.failure is not None
        assert outcome.failure.code == "certificate_untrusted"
        assert outcome.failure.retryable is False
        assert login not in outcome.failure.message
    wrong = asyncio.run(client(certificate_sha256=WRONG_PIN).probe())
    assert wrong.failure is not None and pin in wrong.failure.message


def test_a_silent_client_does_not_stop_the_tls_platform(
    app: SharedPlatformApplication, pin: str
) -> None:
    host, port = app.member_server.server_address[:2]
    quiet = socket.create_connection((str(host), int(port)), timeout=5)
    try:
        started = time.monotonic()
        opener = urllib.request.build_opener(PinnedHTTPSHandler(pin))
        with opener.open(app.member_base_url + "/", timeout=8) as answer:
            assert answer.status == 200
        assert time.monotonic() - started < 5
    finally:
        quiet.close()


# -- Agent Web's "Shared platform" card ------------------------------------------


def _card(app: SharedPlatformApplication, **extra: Any) -> dict[str, Any]:
    return {
        "member_portal_url": app.member_base_url,
        "base_url": app.control_base_url,
        "code": "",
        "enroll": False,
        **extra,
    }


def test_the_card_shows_the_fingerprint_trusts_it_and_enrolls_over_https(
    app: SharedPlatformApplication, tmp_path: Path, pin: str
) -> None:
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    before = path.read_text(encoding="utf-8")
    login = _agent_login(app, pin)
    saved: dict[str, str] = {}
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime, config_path=path)
        web.user_environment = lambda name, value: saved.__setitem__(name, value)

        # Without trust the PC is not enrolled and nothing is written.
        untrusted = web.update_shared_platform(_card(app, code=login, enroll=True))
        assert untrusted["ok"] is False and untrusted["code"] == "certificate_untrusted"
        assert "Fetch & show fingerprint" in untrusted["message"]
        assert path.read_text(encoding="utf-8") == before and saved == {}

        # "Fetch & show fingerprint": both ports present the same certificate.
        shown = web.shared_platform_certificate(_card(app))
        assert shown["ok"] is True and shown["fingerprint"] == pin
        assert [item["fingerprint"] for item in shown["certificates"]] == [pin, pin]
        assert shown["trusted_by_system"] is False and shown["matches_pin"] is False
        assert "PRIVATE" not in json.dumps(shown)
        assert web.shared_platform_certificate({"member_portal_url": "http://127.0.0.1:9"})[
            "code"
        ] == ("certificate_needs_https")

        # "Trust this certificate", then enroll: the pin is in both bindings.
        trusted = web.update_shared_platform(
            _card(app, code=login, enroll=True, certificate_sha256=shown["fingerprint"])
        )
        assert trusted["ok"] is True and trusted["probe"] == "answered", trusted
        assert trusted["certificate_sha256"] == pin
        written = CompanyHostConfiguration.model_validate_json(path.read_text("utf-8"))
        assert written.platform is not None and written.publishing is not None
        assert written.platform.certificate_sha256 == pin
        assert written.publishing.certificate_sha256 == pin
        assert written.platform.base_url == app.control_base_url
        for secret in (login, saved[TOKEN_VARIABLE]):
            assert secret not in path.read_text("utf-8") and secret not in json.dumps(trusted)
        assert web.platform()["connection"] == "answered"
        assert web.shared_platform_certificate(_card(app))["matches_pin"] is True
        link = web.portal_link()
        assert link["signed_in"] is True and link["url"].startswith(app.member_base_url)

        # Saving the addresses again keeps the pin; a wrong pin is refused
        # with the fingerprints named, and "Forget" removes it.
        assert web.update_shared_platform(_card(app))["certificate_sha256"] == pin
        web.update_shared_platform(_card(app, certificate_sha256=WRONG_PIN))
        assert runtime.platform is not None
        import asyncio

        refused = asyncio.run(runtime.platform.probe())
        assert refused.failure is not None and refused.failure.code == "certificate_untrusted"
        assert pin in refused.failure.message and WRONG_PIN in refused.failure.message
        assert web.platform()["connection"] == "unreachable"
        forgot = web.update_shared_platform(_card(app, certificate_sha256=""))
        assert forgot["ok"] is True and forgot["certificate_sha256"] is None
        bad = web.update_shared_platform(_card(app, certificate_sha256="12:34"))
        assert bad["code"] == "certificate_pin_invalid"


def test_the_card_has_the_certificate_controls() -> None:
    for hook in (
        'id="shared-cert"',
        'id="shared-cert-fetch"',
        'id="shared-cert-trust"',
        'id="shared-cert-download"',
        'id="shared-cert-forget"',
        'id="shared-cert-fingerprint"',
        'id="shared-cert-pinned"',
        "/api/settings/shared-platform/certificate",
        "certificate_sha256: fingerprint",
        "Platform certificate",
    ):
        assert hook in PAGE
    card = PAGE[PAGE.index('id="shared-platform-card"') : PAGE.index("Laya decision acceleration")]
    assert 'id="shared-cert-fetch"' in card


@pytest.mark.skipif(browser_path() is None, reason="no Chromium browser is installed")
def test_fetch_and_trust_work_in_a_real_browser(
    app: SharedPlatformApplication, tmp_path: Path, pin: str
) -> None:
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        served = AgentWebServer(AgentWeb(runtime, config_path=path))
        thread = threading.Thread(target=served.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()
        try:
            browser.navigate(served.address)
            controls = {item.element_id: item for item in browser.look().elements}
            browser.click(controls["nav-settings"].index, expected=controls["nav-settings"])
            size = browser._evaluate(
                'JSON.stringify(["shared-cert","shared-cert-fetch","shared-cert-trust"].map('
                "(id) => { const r = document.getElementById(id).getBoundingClientRect();"
                " return [r.width, r.height]; }))"
            )
            box, fetch, trust = json.loads(str(size))
            assert box[0] > 300 and box[1] > 60, size
            assert fetch[0] > 40 and fetch[1] > 20 and trust[0] > 40, size
            # Typed by the person: settings that arrive later do not replace them.
            browser._evaluate(
                "for (const [id, v] of ["
                f'["shared-portal-url", "{app.member_base_url}"],'
                f'["shared-bridge-url", "{app.control_base_url}"]]) {{'
                " const f = document.getElementById(id); f.value = v;"
                ' f.dispatchEvent(new Event("input")); }'
                ' document.getElementById("shared-cert-fetch").click(); "ok"'
            )

            def text_of(element: str, wanted: str) -> str:
                deadline = time.monotonic() + 20
                seen = ""
                while wanted not in seen and time.monotonic() < deadline:
                    time.sleep(0.2)
                    seen = str(
                        browser._evaluate(f'document.getElementById("{element}").textContent')
                    )
                return seen

            assert pin in text_of("shared-cert-fingerprint", pin)
            assert "not trusted yet" in text_of("shared-cert-fingerprint", "not trusted yet")
            browser._evaluate('document.getElementById("shared-cert-trust").click(); "ok"')
            pinned = text_of("shared-cert-pinned", "Trusted certificate")
            status = browser._evaluate('document.getElementById("shared-status").textContent')
            assert pin in pinned, (pinned, status)
            written = CompanyHostConfiguration.model_validate_json(path.read_text("utf-8"))
            assert written.publishing is not None
            assert written.publishing.certificate_sha256 == pin
        finally:
            browser.close()
            browser.discard_profile()
            served.shutdown()
            served.server_close()
            thread.join(timeout=5)
