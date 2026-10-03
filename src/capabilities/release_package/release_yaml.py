"""Render `release.yaml` for the software release repository.

Text templating rather than a YAML round-trip, for two reasons:

* **The file is half comments, and they matter.** They tell the next person
  which parameters belong to KT161 and which to KT160, and how the installer
  name is assembled. Every YAML library in Python drops comments on write, so
  loading and dumping would quietly delete the documentation.
* **PyYAML is not in `host-bridge/requirements.txt`.** Adding it would mean
  rebuilding and redistributing the offline bundle every team member installs
  from (see the skill's dependency rule). A format this small does not justify
  that.

So the template below is the file, verbatim, with `{placeholders}`. Nothing
here parses YAML; it produces it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

#: What CMP_KT_OPTION may be. The first two are what a person is offered
#: (2026-09-02); `KP161` stays accepted because a file somebody already has may
#: carry it, and refusing to render one would break that file for no gain.
OFFERED_CMP_OPTIONS = ("KT160", "KT161")
VALID_CMP_OPTIONS = OFFERED_CMP_OPTIONS + ("KP161",)

TEMPLATE = """\
CMP_KT_OPTION: {cmp_kt_option}   # KT161 or KT160

# ---------------------------------------------------------------------------
# Common parameters (both KT161 and KT160)
# ---------------------------------------------------------------------------

VERSION: {version}
OS: {os}
PY: {py}
ARCH: {arch}
INCLUDE:
{include}
SOURCE: {source}
CYTHON: {cython}
DOCS: {docs}
NOTES: {notes}

# Enter version-specific release notes
# These notes are displayed on our internal release portal and not included in the release package.

# ---------------------------------------------------------------------------
# KT161-specific parameters (used when CMP_KT_OPTION is KT161)
# ---------------------------------------------------------------------------

# Installer name arch 32= "RS-WMT-${{NAME}}-KT161-${{VERSION}}"
# Installer name arch 64 = "RS-WMT-${{NAME}}-x64-KT161-${{VERSION}}"
NAME: {name}

# ---------------------------------------------------------------------------
# KT160-specific parameters (used when CMP_KT_OPTION  is KT160)
# ---------------------------------------------------------------------------

# Installer name = "RS-WMT-${{CUSTOMER_NAME}}-${{SUFFIX}}-${{KT_OPTION}}-${{VERSION}}"
CUSTOMER_NAME: {customer_name}    #Mandatory
SUFFIX: {suffix}               #Optional
KT_OPTION: {kt_option}         #Mandatory
"""


class ReleaseYamlError(ValueError):
    """The inputs cannot produce a valid release.yaml."""


#: Every chipset package and repository carries it. See `normalise_chipset`.
PACKAGE_PREFIX = "rs-wmt-"


def normalise_chipset(chipset_id: str) -> str:
    """The bare id, whichever of the three names somebody arrived with.

    The GitLab repository is `rs-wmt-kt326`, the readiness table stores that,
    the package in requirements.txt is that, and the thing people say is
    `kt326`. Left unnormalised, `rs-wmt-kt326` would produce
    `rs-wmt-rs-wmt-kt326==...` in requirements.txt and -- worse, because it is
    silent -- would fail `startswith("KT")` and pick the wrong CMP_KT_OPTION.
    """
    bare = chipset_id.strip()
    if bare.lower().startswith(PACKAGE_PREFIX):
        bare = bare[len(PACKAGE_PREFIX):]
    return bare


def check_cmp_option(value: str) -> str:
    """Validate the compiler option somebody chose.

    No longer derived from the chipset id. It was, and that derivation was a
    rule standing in for a decision -- the decision is now asked for directly,
    so inferring it would be second-guessing an answer that is right there.

    Case is normalised, because "kt160" from a command line means the same
    thing as the button.
    """
    picked = (value or "").strip().upper()
    if not picked:
        raise ReleaseYamlError(
            "cmpKtOption is required: release.yaml's CMP_KT_OPTION decides which "
            f"half of the file the build reads ({' or '.join(OFFERED_CMP_OPTIONS)})."
        )
    if picked not in VALID_CMP_OPTIONS:
        raise ReleaseYamlError(
            f"CMP_KT_OPTION {value!r} is not one the build accepts "
            f"({', '.join(VALID_CMP_OPTIONS)})."
        )
    return picked


#: Each component of VERSION counts 0..15 and then carries. Not semver: the
#: rule is the build's, and writing it down here is what stops somebody
#: "fixing" it into semver later.
VERSION_RADIX = 16
VERSION_PARTS = 3

_VERSION_LINE = re.compile(r"^VERSION:\s*[\"']?([0-9]+(?:\.[0-9]+)*)[\"']?\s*$", re.MULTILINE)


def parse_version(release_yaml: str) -> str | None:
    """The VERSION currently in a release.yaml, or None if there is not one.

    Read from the file rather than tracked separately: the branch is what the
    last release was cut from, so it is the one thing that cannot disagree with
    itself. Anything kept alongside would drift the first time somebody edited
    the file by hand.
    """
    match = _VERSION_LINE.search(release_yaml or "")
    return match.group(1) if match else None


def next_version(current: str | None) -> str:
    """The next version after `current`, carrying at 15.

    `0.0.15` -> `0.1.0`, `0.15.15` -> `1.0.0`. A missing or unreadable current
    version starts the count at `0.0.1` -- the first packaging of a branch is
    release one, not release zero.
    """
    if not (current or "").strip():
        return "0.0.1"

    try:
        parts = [int(p) for p in str(current).strip().split(".")]
    except ValueError:
        raise ReleaseYamlError(
            f"VERSION {current!r} is not a dotted number, so the next one cannot be "
            "worked out. Fix it in release.yaml, or pass releaseVersion explicitly."
        ) from None

    if len(parts) != VERSION_PARTS:
        raise ReleaseYamlError(
            f"VERSION {current!r} has {len(parts)} part(s); this scheme has "
            f"{VERSION_PARTS}. Pass releaseVersion explicitly to set it by hand."
        )
    if any(p < 0 or p >= VERSION_RADIX for p in parts):
        raise ReleaseYamlError(
            f"VERSION {current!r} has a component outside 0..{VERSION_RADIX - 1}, "
            "which this scheme cannot carry from."
        )

    for i in range(VERSION_PARTS - 1, -1, -1):
        parts[i] += 1
        if parts[i] < VERSION_RADIX:
            return ".".join(str(p) for p in parts)
        parts[i] = 0

    # Every component carried. Wrapping to 0.0.0 would make two different
    # releases share a version, which is worse than stopping.
    raise ReleaseYamlError(
        f"VERSION {current!r} is the last one this scheme can express "
        f"({VERSION_RADIX - 1} in every part). Set releaseVersion by hand."
    )


def _yaml_str(value: str | None) -> str:
    """Quote only when leaving it bare would change the meaning.

    An unquoted empty value is how the template writes SUFFIX and NOTES, and
    matching that keeps a generated file diffable against a hand-written one.
    """
    text = "" if value is None else str(value)
    if text == "":
        return '""'
    if any(ch in text for ch in ':#{}[],&*?|<>=!%@`"\'\\') or text.strip() != text:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def _yaml_list(items: Iterable[str]) -> str:
    rows = [f'  - "{i}"' for i in items]
    return "\n".join(rows) if rows else "  []"


def render(
    *,
    chipset_id: str,
    branch_name: str,
    customer_name: str,
    version: str,
    include: Iterable[str],
    cmp_option: str,
    suffix: str = "",
    notes: str = "",
    os_name: str = "win",
    py: str = "3.13",
    arch: str = "64",
    docs: bool = False,
) -> str:
    """Produce the file. Every field the caller can get wrong is validated here."""
    chipset = normalise_chipset(chipset_id)
    if not chipset:
        raise ReleaseYamlError("chipsetId is required to write release.yaml")
    if not branch_name.strip():
        raise ReleaseYamlError("branch name is required: it becomes NAME in release.yaml")
    if not customer_name.strip():
        raise ReleaseYamlError(
            "companyName is required: it becomes CUSTOMER_NAME, which the KT160 "
            "installer name is built from and which the template marks Mandatory"
        )

    return TEMPLATE.format(
        cmp_kt_option=check_cmp_option(cmp_option),
        version=_yaml_str(version),
        os=_yaml_str(os_name),
        py=_yaml_str(py),
        arch=_yaml_str(arch),
        include=_yaml_list(include),
        source="[]",
        cython="[]",
        docs="True" if docs else "False",
        notes=_yaml_str(notes) if notes else "",
        name=_yaml_str(branch_name.strip()),
        customer_name=_yaml_str(customer_name.strip()),
        suffix=_yaml_str(suffix),
        kt_option=_yaml_str(chipset),
    )


def requirements_lines(chipset_id: str, chipset_version: str,
                       general_testcase_version: str,
                       prefix: str = PACKAGE_PREFIX) -> list[str]:
    """The two pinned requirements, in the order the example shows them.

    `rs-wmt-kt326==2.0.18` / `rs-wmt-general-testcase==2.1.2`. Exact pins, not
    ranges: a release package that resolves differently tomorrow is not a
    release.
    """
    chipset = normalise_chipset(chipset_id).lower()
    if not chipset:
        raise ReleaseYamlError("chipsetId is required")
    for label, ver in (
        ("chipset", chipset_version),
        ("general testcase", general_testcase_version),
    ):
        if not str(ver).strip():
            raise ReleaseYamlError(
                f"a {label} version is required; refusing to write an unpinned requirement"
            )
    return [
        f"{prefix}{chipset}=={str(chipset_version).strip().lstrip('vV')}",
        f"{prefix}general-testcase=={str(general_testcase_version).strip().lstrip('vV')}",
    ]
