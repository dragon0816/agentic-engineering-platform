"""Source-derived pure Workflow 13 git-status and dry-run wording rules."""

from __future__ import annotations

from collections.abc import Sequence

#: How a changed path is described to somebody who did not write the job.
#: Longest prefix wins, so "testplans/x" beats the bare-file fallback.
_FILE_GROUPS: tuple[tuple[str, str], ...] = (
    ("testplans/", "test plans"),
    ("configurations/", "configurations"),
    ("overlay/", "overlay files"),
    ("release.yaml", "release.yaml"),
    ("requirements.txt", "requirements.txt"),
)


def _describe_change(path: str) -> str:
    """Which bucket a changed path belongs in. Unknown paths keep their folder."""
    clean = path.strip().replace("\\", "/").lstrip("./")
    for prefix, label in _FILE_GROUPS:
        if clean == prefix or clean.startswith(prefix):
            return label
    head = clean.split("/", 1)[0]
    return head if "/" in clean else "other files"


def parse_status(changed: Sequence[str]) -> list[tuple[str, int]]:
    """`git status --porcelain` lines -> [(what it is, how many)], biggest first.

    The raw lines are the wrong thing to show anybody: `?? testplans/a.xml` is
    two pieces of git trivia in front of the only part that matters. Ties break
    on the label so the output is stable enough to diff between runs.
    """
    counts: dict[str, int] = {}
    for line in changed:
        # porcelain is "XY <path>", and a rename is "XY <old> -> <new>".
        body = line[3:] if len(line) > 3 else line.strip()
        path = body.split(" -> ")[-1].strip().strip('"')
        if not path:
            continue
        label = _describe_change(path)
        counts[label] = counts.get(label, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def dry_run_plan(
    *,
    company: str,
    chipset: str,
    chipset_version: str,
    branch: str,
    branch_state: str,
    template: str,
    release_version: str,
    previous_version: str,
    testcase: str,
    changed: Sequence[str],
    project_path: str,
    will_push: bool,
) -> list[str]:
    """What a real run would do, for somebody who cannot read the diff.

    A pure function returning lines, so it is testable without a git repo and
    without the Bridge -- and so the wording can be argued about on its own.

    The existing dry-run line ("N file(s) changed in the working copy, nothing
    committed") is true and answers none of the questions the person starting a
    release actually has: which branch, which version, what goes in, and what
    happens after the push.
    """
    total = sum(n for _, n in parse_status(changed))
    branch_note = (
        f"{branch}  (new; created from {template})"
        if branch_state == "created"
        else f"{branch}  (already exists; would be updated)"
    )
    version_note = (
        f"{previous_version} -> {release_version}"
        if previous_version
        else f"{release_version}  (first release on this branch)"
    )

    lines = [
        "",
        "-- If you run this for real ------------------------------------",
        f"  Customer / chipset   {company} - {chipset} {chipset_version}".rstrip(),
        f"  Branch               {branch_note}",
        f"  Version              {version_note}",
        f"  General testcase     {testcase}",
        "",
    ]

    groups = parse_status(changed)
    if groups:
        lines.append(f"  Files it would add or change ({total})")
        lines += [f"    {label:<18} {count}" for label, count in groups]
    else:
        # Not an error, and worth saying plainly: re-running an unchanged
        # release is a normal thing to do by accident.
        lines.append("  No files would change -- this release is already in place.")
    lines.append("")

    steps: list[str] = []
    if groups:
        if branch_state == "created":
            steps.append(f"create the branch {branch} from {template}")
        steps.append(f"commit {total} file(s)")
        if will_push:
            steps.append(f"push to {project_path or 'the release repository'}")
            steps.append("CI then takes about 15-20 minutes to build the package")
        else:
            steps.append("stop there -- pushing is switched off for this run")
    if steps:
        lines.append("  What would happen")
        lines += [f"    {i}. {step}" for i, step in enumerate(steps, 1)]
        lines.append("")

    lines += [
        "  Nothing has been committed and nothing has been pushed.",
        "  Run it again without --dry-run to do it for real.",
        "----------------------------------------------------------------",
        "",
    ]
    return lines
