"""Read-only choice lists for the release form (forms v2, owner 2026-10-15).

The old dashboard offered the chipsets and the published versions of a
package as lists (`ref:chipsets`, `ref:packageVersions:<package>`). Here they
are `fn:` choice functions over the Workflow's own settings:

- `release_package.chipsets`: the readiness table (`/api/chipsets`, Workflow
  12's table), else the `rs-wmt-*` packages on the PEP 503 index root;
- `release_package.versions?package=<p>`: the versions of one package on the
  index, releases before dev builds, newest first.

Each request waits at most `CHOICE_TIMEOUT_SECONDS`, and every failure is an
error the host turns into "no list": the release fields allow a typed value,
so a slow or missing index never blocks the form or the run. Tokens come
from the host environment exactly as the prepare step reads them and are
never returned.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
from collections.abc import Mapping
from functools import partial
from typing import Any

from capabilities.release_package.versions import (
    _ANCHOR_RE,
    _TAG_RE,
    PACKAGE_PREFIX,
    Fetch,
    http_get,
    index_url,
    normalise_name,
    parse_simple_index,
)

CHIPSETS_FUNCTION = "release_package.chipsets"
VERSIONS_FUNCTION = "release_package.versions"
GENERAL_TESTCASE = "rs-wmt-general-testcase"
CHOICE_TIMEOUT_SECONDS = 5.0
MAX_CHOICES = 300
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")

Choice = tuple[str, str]


def _fetch(fetch: Fetch | None) -> Fetch:
    return fetch if fetch is not None else partial(http_get, timeout=CHOICE_TIMEOUT_SECONDS)


def _index_headers() -> dict[str, str]:
    token = os.environ.get("ARTIFACTORY_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _readiness(base_url: str, fetch: Fetch) -> list[Choice]:
    token = os.environ.get("OPS_TOKEN", "")
    query = urllib.parse.urlencode({"limit": 500})
    status, text = fetch(
        f"{base_url.strip().rstrip('/')}/api/chipsets?{query}",
        {"X-Ops-Token": token} if token else {},
    )
    if status >= 400:
        raise ValueError(f"the readiness table answered {status}")
    rows = ((json.loads(text).get("data") or {}).get("chipsets")) or []
    found: dict[str, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip().removeprefix(PACKAGE_PREFIX)
        if _NAME.match(name) and name not in found:
            tag = str(row.get("tag") or "").strip()
            found[name] = f"{name} ({tag})" if tag else name
    return sorted(found.items(), key=lambda item: item[0].casefold())


def _index_packages(base_url: str, fetch: Fetch) -> list[Choice]:
    status, text = fetch(f"{base_url.strip().rstrip('/')}/", _index_headers())
    if status >= 400:
        raise ValueError(f"the package index answered {status}")
    names: set[str] = set()
    for anchor in _ANCHOR_RE.findall(text or ""):
        name = normalise_name(urllib.parse.unquote(_TAG_RE.sub("", anchor)).strip().strip("/"))
        if name.startswith(PACKAGE_PREFIX) and name != GENERAL_TESTCASE:
            short = name.removeprefix(PACKAGE_PREFIX)
            if _NAME.match(short):
                names.add(short)
    return [(name, name) for name in sorted(names)]


def chipset_choices(
    settings: Mapping[str, Any],
    _arguments: Mapping[str, str],
    fetch: Fetch | None = None,
) -> list[Choice]:
    """Chipset ids, from the readiness table or else the package index."""
    getter = _fetch(fetch)
    readiness = str(settings.get("readiness_base_url") or "").strip()
    index = str(settings.get("artifactory_base_url") or "").strip()
    if not readiness and not index:
        raise ValueError("no readiness table or package index is configured")
    if readiness:
        try:
            found = _readiness(readiness, getter)
        except Exception:  # noqa: BLE001 - the index is the fallback
            found = []
        if found:
            return found[:MAX_CHOICES]
    if index:
        return _index_packages(index, getter)[:MAX_CHOICES]
    raise ValueError("the readiness table listed no chipsets")


def version_choices(
    settings: Mapping[str, Any],
    arguments: Mapping[str, str],
    fetch: Fetch | None = None,
) -> list[Choice]:
    """The versions of `package` on the index, releases first, newest first."""
    base = str(settings.get("artifactory_base_url") or "").strip()
    package = str(arguments.get("package") or "").strip()
    if not base or not _NAME.match(package):
        raise ValueError("no package index or package")
    if not normalise_name(package).startswith(PACKAGE_PREFIX):
        package = f"{PACKAGE_PREFIX}{package}"
    status, text = _fetch(fetch)(index_url(base, package), _index_headers())
    if status >= 400:
        raise ValueError(f"the package index answered {status}")
    return [
        (item.version, f"{item.version} (dev)" if item.is_dev else item.version)
        for item in parse_simple_index(text, package)[:MAX_CHOICES]
    ]
