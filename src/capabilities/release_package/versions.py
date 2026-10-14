"""Which chipset version a release pins when the person did not choose one.

Ported from `host-bridge/jobs/_artifactory.py` and `release_package.py`
(`lookup_published_version`, `lookup_chipset_version`) at
rs_workflow_system@896046e8. The newest *published* release on the PEP 503
index comes first, because `requirements.txt` pins `rs-wmt-<chipset>==<v>` and
pip must resolve it. The readiness table is the fallback. Dev builds are never
chosen by default. The parsing is pure; `fetch` is the only network call and
can be replaced in tests.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

PACKAGE_PREFIX = "rs-wmt-"
_ANCHOR_RE = re.compile(r"<a\b[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_SDIST_SUFFIXES = (".tar.gz", ".zip", ".tar.bz2")
_WHEEL_SUFFIX = ".whl"
_RELEASE_RE = re.compile(r"^v?\d+(?:\.\d+)*(?:\.post\d+)?$", re.IGNORECASE)
_PAD = 6

Fetch = Callable[[str, dict[str, str]], tuple[int, str]]
LogFn = Callable[[str], None]


class VersionLookupError(Exception):
    """No version can be pinned without guessing."""


@dataclass(frozen=True)
class PackageVersion:
    version: str
    is_dev: bool


def normalise_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", (name or "").strip()).lower()


def _filename_of(anchor_html: str) -> str:
    text = urllib.parse.unquote(_TAG_RE.sub("", anchor_html)).strip()
    if "/" in text:
        text = urllib.parse.urlsplit(text).path.rsplit("/", 1)[-1]
    return text.split("#", 1)[0].strip()


def version_of(filename: str, package: str) -> str:
    wanted = normalise_name(package)
    name = (filename or "").strip()
    if name.endswith(_WHEEL_SUFFIX):
        parts = name[: -len(_WHEEL_SUFFIX)].split("-")
        if len(parts) < 5:
            return ""
        stem, version = parts[0], parts[1]
    else:
        for suffix in _SDIST_SUFFIXES:
            if name.endswith(suffix):
                stem_version = name[: -len(suffix)]
                break
        else:
            return ""
        if "-" not in stem_version:
            return ""
        stem, version = stem_version.rsplit("-", 1)
    if normalise_name(stem) != wanted:
        return ""
    return version.strip()


def is_dev(version: str) -> bool:
    base = (version or "").split("+", 1)[0].strip()
    if not base:
        return False
    return not _RELEASE_RE.match(base)


def sort_key(version: str) -> str:
    head = re.split(r"[^0-9.]", (version or "").strip(), maxsplit=1)[0]
    parts = [p for p in head.split(".") if p != ""]
    padded = ".".join(p.rjust(_PAD, "0")[-_PAD:] for p in parts[:4]) or "0" * _PAD
    return f"{'0' if is_dev(version) else '1'}|{padded}"


def parse_simple_index(html: str, package: str) -> list[PackageVersion]:
    seen: dict[str, PackageVersion] = {}
    for anchor in _ANCHOR_RE.findall(html or ""):
        version = version_of(_filename_of(anchor), package)
        if version and version not in seen:
            seen[version] = PackageVersion(version=version, is_dev=is_dev(version))
    return sorted(seen.values(), key=lambda v: sort_key(v.version), reverse=True)


def newest_release(versions: list[PackageVersion]) -> str:
    for item in sorted(versions, key=lambda x: sort_key(x.version), reverse=True):
        if not item.is_dev:
            return item.version
    return ""


def index_url(base_url: str, package: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError("artifactory baseUrl is empty")
    return f"{base}/{normalise_name(package)}/"


def http_get(url: str, headers: dict[str, str], timeout: float = 60) -> tuple[int, str]:
    """GET with the machine's own proxy settings; status and text only."""
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured URL
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, ""


def lookup_published_version(
    chipset_id: str, base_url: str, token: str, log: LogFn, fetch: Fetch = http_get
) -> str:
    """The newest published release, or "" so the readiness table is asked.
    Never raises: an unreachable index falls back, as in the source."""
    if not base_url.strip():
        return ""
    package = (chipset_id if chipset_id.startswith(PACKAGE_PREFIX)
               else f"{PACKAGE_PREFIX}{chipset_id}")
    try:
        status, text = fetch(index_url(base_url, package),
                             {"Authorization": f"Bearer {token}"} if token else {})
        if status == 404:
            raise LookupError("no such package")
        if status >= 400:
            raise RuntimeError(f"index answered {status}")
        versions = parse_simple_index(text, package)
    except Exception as error:  # noqa: BLE001 - falling back is the point
        log(f"WARN could not read published versions of {package} "
            f"({type(error).__name__}); falling back to the readiness table")
        return ""
    newest = newest_release(versions)
    if not newest:
        log(f"WARN {package} has no published release "
            f"({len(versions)} version(s), all pre-release); falling back")
        return ""
    log(f"chipsetVersion {newest} (newest published release of {package})")
    return newest


def lookup_readiness_version(
    chipset_id: str, base_url: str, token: str, log: LogFn, fetch: Fetch = http_get
) -> str:
    """The newest tag the readiness scan saw (Workflow 12's table)."""
    base = base_url.strip().rstrip("/")
    if not base:
        raise VersionLookupError(
            "chipsetVersion was not given and no readiness table is configured, so it "
            "cannot be looked up. Give chipsetVersion, or configure the lookup.")
    query = urllib.parse.urlencode({"q": chipset_id, "limit": 50})
    try:
        status, text = fetch(f"{base}/api/chipsets?{query}",
                             {"X-Ops-Token": token} if token else {})
    except OSError as error:
        raise VersionLookupError(
            f"could not reach the readiness table ({type(error).__name__})") from None
    if status >= 400:
        raise VersionLookupError(f"the readiness table refused the lookup ({status})")
    try:
        rows = ((json.loads(text).get("data") or {}).get("chipsets")) or []
    except (ValueError, AttributeError):
        raise VersionLookupError("the readiness table answered something unreadable") from None
    wanted = chipset_id.strip().lower().removeprefix(PACKAGE_PREFIX)
    exact = [r for r in rows
             if str(r.get("name", "")).lower().removeprefix(PACKAGE_PREFIX) == wanted]
    if not exact:
        raise VersionLookupError(
            f"{chipset_id!r} is not in the chipset readiness table. Either its pipeline "
            "is not passing, or workflow 12 has not run since it was added. Pass "
            "chipsetVersion explicitly to go ahead anyway.")
    tag = exact[0].get("tag")
    if not tag:
        raise VersionLookupError(
            f"{chipset_id!r} is in the readiness table but has no tag, so there is no "
            "version to pin. Tag the chipset repository, or pass chipsetVersion.")
    log(f"chipsetVersion {tag} (from the readiness table, scanned {exact[0].get('scanned_at')})")
    return str(tag)
