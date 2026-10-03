"""Read-only source-change plan for Workflow 10 project-list workbooks.

Adapted from the pinned host-bridge ``jobs/_source_snapshot.py``. Planning
reads the last committed baseline and computes a candidate; it never advances
that baseline. A later successful apply must explicitly persist the candidate.
"""

import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from capabilities.chipset_report.rules import SourceRow

FIELDS: tuple[str, ...] = (
    "brand",
    "mfg",
    "project_name",
    "chipset_models",
    "end_products",
    "purpose",
    "units",
    "schedule",
    "priority",
    "status",
)
CRITICAL_FIELDS = frozenset({"chipset_models", "end_products", "purpose"})
DEFAULT_KEEP = 20
_WS = re.compile(r"\s+")
Snapshot = dict[str, dict[str, Any]]


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return _WS.sub(" ", str(value)).strip().casefold()


def row_key(row: SourceRow) -> str:
    """Use OPP ID across renames; otherwise use the brand/MFG/project triple."""
    opp = _norm(row.opp_id)
    if opp and opp not in {"n/a", "na", "tbd", "tbc", "-"}:
        return f"opp:{opp}"
    return "row:" + "|".join(_norm(getattr(row, name)) for name in ("brand", "mfg", "project_name"))


@dataclass(frozen=True)
class FieldChange:
    key: str
    label: str
    fiscalYear: str
    rowNumber: int
    field: str
    before: str
    after: str

    @property
    def critical(self) -> bool:
        return self.field in CRITICAL_FIELDS

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "fiscalYear": self.fiscalYear,
            "rowNumber": self.rowNumber,
            "field": self.field,
            "before": self.before,
            "after": self.after,
            "critical": self.critical,
        }


@dataclass
class SourceDiff:
    baseline: str | None = None
    added: list[dict[str, Any]] = field(default_factory=list)
    removed: list[dict[str, Any]] = field(default_factory=list)
    changed: list[FieldChange] = field(default_factory=list)

    @property
    def is_first_run(self) -> bool:
        return self.baseline is None

    @property
    def critical_changes(self) -> list[FieldChange]:
        return [item for item in self.changed if item.critical]

    def as_dict(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline,
            "firstRun": self.is_first_run,
            "added": self.added,
            "removed": self.removed,
            "changed": [item.as_dict() for item in self.changed],
            "criticalChangeCount": len(self.critical_changes),
        }

    def summary(self) -> str:
        if self.is_first_run:
            # Planning has no write path; a preview cannot claim persistence.
            return "no previous snapshot; baseline pending successful apply"
        if not (self.added or self.removed or self.changed):
            return f"no source changes since {self.baseline}"
        bits = []
        if self.added:
            bits.append(f"{len(self.added)} added")
        if self.removed:
            bits.append(f"{len(self.removed)} removed")
        if self.changed:
            critical = len(self.critical_changes)
            bits.append(
                f"{len(self.changed)} field change(s)"
                + (f", {critical} CRITICAL" if critical else "")
            )
        return f"since {self.baseline}: " + ", ".join(bits)


def build(rows: Iterable[SourceRow]) -> Snapshot:
    """Normalize source rows, retaining the first entry for duplicate keys."""
    snapshot: Snapshot = {}
    for row in rows:
        entry: dict[str, Any] = {
            name: "" if getattr(row, name) is None else str(getattr(row, name)) for name in FIELDS
        }
        entry["_fiscalYear"] = str(row.fiscal_year)
        entry["_rowNumber"] = int(row.row_number or 0)
        key = row_key(row)
        if key in snapshot:
            snapshot[key]["_duplicate"] = int(snapshot[key].get("_duplicate", 1)) + 1
            continue
        snapshot[key] = entry
    return snapshot


def _label(entry: Mapping[str, Any]) -> str:
    parts = (entry.get("project_name") or "", entry.get("brand") or "", entry.get("mfg") or "")
    return " / ".join(str(part) for part in parts if part) or "(unnamed)"


def diff(
    previous: Mapping[str, Mapping[str, Any]] | None,
    current: Mapping[str, Mapping[str, Any]],
    baseline: str | None,
) -> SourceDiff:
    result = SourceDiff(baseline=baseline)
    if previous is None:
        return result
    prev_keys, cur_keys = set(previous), set(current)
    for key in sorted(cur_keys - prev_keys):
        entry = current[key]
        result.added.append(
            {
                "key": key,
                "label": _label(entry),
                "chipsets": entry.get("chipset_models", ""),
                "rowNumber": entry.get("_rowNumber"),
            }
        )
    for key in sorted(prev_keys - cur_keys):
        entry = previous[key]
        result.removed.append(
            {
                "key": key,
                "label": _label(entry),
                "chipsets": entry.get("chipset_models", ""),
                "rowNumber": entry.get("_rowNumber"),
            }
        )
    for key in sorted(prev_keys & cur_keys):
        before_entry, after_entry = previous[key], current[key]
        for name in FIELDS:
            before, after = before_entry.get(name, ""), after_entry.get(name, "")
            if _norm(before) == _norm(after):
                continue
            result.changed.append(
                FieldChange(
                    key=key,
                    label=_label(after_entry),
                    fiscalYear=str(after_entry.get("_fiscalYear", "")),
                    rowNumber=int(after_entry.get("_rowNumber") or 0),
                    field=name,
                    before=str(before),
                    after=str(after),
                )
            )
    return result


def _snapshot_dir(state_dir: Path, workbook: str | Path) -> Path:
    stem = re.sub(r"[^\w.-]+", "_", Path(workbook).stem)[:80]
    return Path(state_dir) / "w1-snapshots" / stem


def load_latest(state_dir: Path, workbook: str | Path) -> tuple[Snapshot | None, str | None]:
    """Read the newest committed baseline without creating a directory."""
    files = sorted(_snapshot_dir(state_dir, workbook).glob("*.json"))
    if not files:
        return None, None
    newest = files[-1]
    try:
        payload = json.loads(newest.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    rows = payload.get("rows")
    if not isinstance(rows, dict) or any(
        not isinstance(key, str) or not isinstance(entry, dict) for key, entry in rows.items()
    ):
        return None, None
    taken_at = payload.get("takenAt")
    return cast(Snapshot, rows), taken_at if isinstance(taken_at, str) and taken_at else newest.stem


def prepare_diff(
    state_dir: Path, workbook: str | Path, rows: Iterable[SourceRow]
) -> tuple[SourceDiff, Snapshot]:
    """Compute the next baseline candidate; caller must not persist it on preview."""
    previous, baseline = load_latest(state_dir, workbook)
    current = build(rows)
    return diff(previous, current, baseline), current


def commit_candidate(
    state_dir: Path,
    workbook: str | Path,
    candidate: Mapping[str, Mapping[str, Any]],
    *,
    taken_at: datetime,
    verified_copyback: bool,
    keep: int = DEFAULT_KEEP,
) -> Path:
    """Persist a prepared baseline only after the caller verified target copyback.

    This API performs no workbook write or verification itself. Its required
    flag makes the apply boundary explicit, and a false flag touches no file.
    An interrupted write cannot leave a partial ``*.json`` baseline.
    """
    if verified_copyback is not True:
        raise ValueError("verified target copyback is required")
    if taken_at.tzinfo is None or taken_at.utcoffset() is None:
        raise ValueError("taken_at must be timezone aware")
    if type(keep) is not int or keep < 1:
        raise ValueError("keep must be positive")
    point = taken_at.astimezone(UTC)
    payload = json.dumps(
        {
            "workbook": str(workbook),
            "takenAt": point.isoformat(timespec="seconds"),
            "rows": candidate,
        },
        ensure_ascii=False,
        indent=2,
    )
    directory = _snapshot_dir(state_dir, workbook)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{point:%Y%m%d_%H%M%S_%f}_{uuid4().hex[:8]}.json"
    temporary = directory / f".{target.name}.tmp"
    try:
        with temporary.open("x", encoding="utf-8") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    # The committed baseline remains valid even if old files cannot be pruned.
    for old in sorted(directory.glob("*.json"))[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass
    return target


def render_report(diffs: Sequence[tuple[str, SourceDiff]]) -> str:
    """Render source-compatible human-readable diff for a preview artifact."""
    lines: list[str] = ["# W1 source change report", ""]
    for workbook, source_diff in diffs:
        lines += [f"## {Path(workbook).name}", f"    {source_diff.summary()}", ""]
        if source_diff.is_first_run:
            lines += ["    (first run — nothing to compare against yet)", ""]
            continue
        if source_diff.critical_changes:
            lines.append("    !! CHIPSET-AFFECTING CHANGES")
            for change in source_diff.critical_changes:
                lines += [
                    f"       {change.label}  "
                    f"[{change.fiscalYear} R{change.rowNumber}]  {change.field}",
                    f"         before: {change.before!r}",
                    f"         after : {change.after!r}",
                ]
            lines.append("")
        other = [change for change in source_diff.changed if not change.critical]
        if other:
            lines.append("    other field changes")
            for change in other:
                lines.append(
                    f"       {change.label}  {change.field}: {change.before!r} -> {change.after!r}"
                )
            lines.append("")
        for bucket, title in (
            (source_diff.added, "new project rows"),
            (source_diff.removed, "project rows gone"),
        ):
            if bucket:
                lines.append(f"    {title}")
                lines += [
                    f"       {entry['label']}  chipsets={entry['chipsets']!r}" for entry in bucket
                ]
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"
