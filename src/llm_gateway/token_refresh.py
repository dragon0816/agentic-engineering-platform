"""Renew the upstream token with Windows integrated authentication.

Ported from the owner's `refresh-token.ps1`. chatrs signs in through
Keycloak, which answers the OIDC authorisation request with
`WWW-Authenticate: Negotiate` (SPNEGO). On a domain-joined computer Windows
already holds a Kerberos ticket from logon, so `UseDefaultCredentials`
completes the handshake silently: no password is stored, no browser is
driven, no MFA prompt. A personal API key would be cleaner but is not
available (the service has ENABLE_API_KEY=false, still 403 when checked).

Needs a live Kerberos ticket (`klist` shows krbtgt/...): off the domain or
over a VPN without one it fails, and says so.

The PowerShell part only obtains the token and hands it back on its standard
output (a pipe this process reads, never a console or a log); this module
checks it is a readable, unexpired, new JWT before writing it to the token
file (with a .bak of the previous file). Redirects are followed one hop at a
time because .NET drops credentials on a cross-host redirect (chatrs ->
Keycloak came back 401 otherwise).
"""

from __future__ import annotations

import base64
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from llm_gateway import secrets_file, state
from llm_gateway.config import TOKEN_VARIABLE, GatewayPaths, GatewaySettings

DEFAULT_SERVICE = "https://chatrs.cloud.rsint.net"
RENEW_WHEN_DAYS_LEFT = 7
TOKEN_PREFIX = "AEP-TOKEN:"

EXIT_NO_TICKET = 10
EXIT_REJECTED = 11
EXIT_NO_COOKIE = 12

#: Exit codes of the script, in the words the person sees.
SCRIPT_FAILURES = {
    EXIT_NO_TICKET: (
        "no_kerberos_ticket",
        "No Kerberos ticket (klist shows no krbtgt). Sign in to the company domain, "
        "or connect the VPN, then refresh again.",
    ),
    EXIT_REJECTED: (
        "kerberos_rejected",
        "The sign-in service rejected the Windows ticket (401). Check the site is in "
        "the Local intranet zone, then `klist purge`, sign out and in again.",
    ),
    EXIT_NO_COOKIE: (
        "no_token_issued",
        "The sign-in completed but no token was issued.",
    ),
}

# The script takes the service address as its only input and prints
# `AEP-TOKEN:<jwt>` once. Everything else goes to standard error.
REFRESH_SCRIPT = r"""
param([Parameter(Mandatory = $true)][string]$Base)
$ErrorActionPreference = 'Stop'
$klist = (klist 2>&1 | Out-String)
if ($klist -notmatch 'krbtgt/') { [Console]::Error.WriteLine('no Kerberos ticket'); exit 10 }
Add-Type -AssemblyName System.Net.Http
$jar = New-Object System.Net.CookieContainer
$handler = New-Object System.Net.Http.HttpClientHandler
$handler.UseDefaultCredentials = $true
$handler.AllowAutoRedirect = $false
$handler.CookieContainer = $jar
$client = New-Object System.Net.Http.HttpClient($handler)
$client.Timeout = [TimeSpan]::FromSeconds(90)
$url = "$Base/oauth/oidc/login"
$token = $null
try {
    for ($hop = 1; $hop -le 10; $hop++) {
        try { $response = $client.GetAsync($url).GetAwaiter().GetResult() } catch { break }
        $found = $jar.GetCookies([Uri]$Base) | Where-Object { $_.Name -eq 'token' } |
            Select-Object -First 1
        if ($found) { $token = $found.Value; break }
        if ([int]$response.StatusCode -eq 401) {
            [Console]::Error.WriteLine("401 at hop $hop"); exit 11
        }
        if (-not $response.Headers.Location) { break }
        $location = $response.Headers.Location.ToString()
        $url = if ($location -match '^https?://') { $location }
               else { ([Uri]::new([Uri]$url, $location)).AbsoluteUri }
    }
} finally { $client.Dispose() }
if (-not $token) { [Console]::Error.WriteLine('no token cookie'); exit 12 }
[Console]::Out.WriteLine('AEP-TOKEN:' + $token)
exit 0
"""


@dataclass(frozen=True)
class RefreshResult:
    ok: bool
    code: str
    message: str
    expires_at: datetime | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "code": self.code,
            "message": self.message,
            "expires_at": self.expires_at.isoformat(timespec="seconds")
            if self.expires_at
            else None,
        }


Runner = Callable[[Sequence[str], float], "subprocess.CompletedProcess[str]"]


def run_powershell(arguments: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(arguments),
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )


def script_command(service: str) -> list[str]:
    encoded = base64.b64encode(
        ("& {" + REFRESH_SCRIPT + "} -Base '" + service.replace("'", "''") + "'").encode(
            "utf-16-le"
        )
    ).decode("ascii")
    return [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        encoded,
    ]


def service_of(settings: GatewaySettings) -> str:
    """The sign-in site of the upstream: its scheme and host."""
    scheme, _, rest = settings.upstream.partition("://")
    return f"{scheme}://{rest.split('/', 1)[0]}" if rest else DEFAULT_SERVICE


def refresh(
    paths: GatewayPaths,
    settings: GatewaySettings,
    *,
    force: bool = False,
    renew_when_days_left: float = RENEW_WHEN_DAYS_LEFT,
    runner: Runner = run_powershell,
    platform: str = sys.platform,
    now: datetime | None = None,
) -> RefreshResult:
    if not settings.managed:
        # Someone else's gateway and token file (gateway.json managed=false):
        # renewing would rewrite a file AEP does not own.
        return RefreshResult(
            False,
            "not_managed",
            "This gateway's token file is managed outside AEP; renew it there.",
        )
    current_time = now or datetime.now(UTC)
    target = settings.secrets_path(paths)
    current = secrets_file.read(target).get(TOKEN_VARIABLE, "")
    info = secrets_file.token_info(current)
    left = info.days_left(current_time)
    if not force and left is not None and left > renew_when_days_left:
        return RefreshResult(
            True,
            "not_due",
            f"The token is valid for {left:.0f} more days; it renews at "
            f"{renew_when_days_left:.0f}.",
            info.expires_at,
        )
    if platform != "win32":
        return _failed(paths, "not_windows", "Token refresh uses Windows sign-in; not Windows.")
    try:
        completed = runner(script_command(service_of(settings)), 120.0)
    except (OSError, subprocess.TimeoutExpired) as error:
        return _failed(paths, "script_failed", f"The sign-in script did not finish: {error}")
    if completed.returncode != 0:
        code, message = SCRIPT_FAILURES.get(
            completed.returncode,
            ("script_failed", f"The sign-in script failed (exit {completed.returncode})."),
        )
        return _failed(paths, code, message)
    received = next(
        (
            line[len(TOKEN_PREFIX) :].strip()
            for line in completed.stdout.splitlines()
            if line.startswith(TOKEN_PREFIX)
        ),
        "",
    )
    new = secrets_file.token_info(received)
    if not new.readable or new.expires_at is None:
        return _failed(paths, "unreadable_token", "The value received is not a readable JWT.")
    if new.expired(current_time):
        return _failed(paths, "expired_token", "The token received has already expired.")
    if received == current:
        state.update(paths.state, last_refresh_at=state.now_text(), last_refresh_error=None)
        return RefreshResult(
            True, "unchanged", "The service returned the same token.", new.expires_at
        )
    secrets_file.set_value(target, TOKEN_VARIABLE, received)
    state.update(paths.state, last_refresh_at=state.now_text(), last_refresh_error=None)
    return RefreshResult(True, "renewed", "The token was renewed.", new.expires_at)


def _failed(paths: GatewayPaths, code: str, message: str) -> RefreshResult:
    state.update(paths.state, last_refresh_error=code, last_refresh_failed_at=state.now_text())
    return RefreshResult(False, code, message)
