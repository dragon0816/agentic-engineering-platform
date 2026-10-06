from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

workspace = Path.cwd()
input_path = workspace / "input" / "testplan.json"
output_dir = workspace / "output"
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "testplan.json"
warnings_path = output_dir / "warnings.txt"

warnings: list[str] = []

# Match a whole frequency string with a numeric value followed by MHz or GHz.
# Spaces between number and unit are allowed; unit matching is case-insensitive.
KNOWN_FREQ_RE = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(GHz|MHz)\s*$", re.IGNORECASE)
# Detect strings that look like a numeric value followed by some unit, but not MHz/GHz.
UNKNOWN_UNIT_RE = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-z]+)\s*$")


def decimal_to_json_number(value: Decimal) -> int | float:
    """Return an int when exact/integral, otherwise a JSON-compatible float."""
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def path_to_text(parts: list[str]) -> str:
    if not parts:
        return "$"
    out = "$"
    for part in parts:
        if part.startswith("["):
            out += part
        else:
            out += "." + part
    return out


def transform(node: Any, path: list[str] | None = None) -> Any:
    if path is None:
        path = []

    if isinstance(node, list):
        # Preserve array order exactly.
        return [transform(item, path + [f"[{idx}]"]) for idx, item in enumerate(node)]

    if isinstance(node, dict):
        # Build a new dict in original insertion order. Add frequency_unit immediately
        # after a converted frequency field, which keeps all existing fields in order.
        new_obj: dict[str, Any] = {}
        for key, value in node.items():
            current_path = path + [key]
            if key == "frequency":
                if isinstance(value, str):
                    match = KNOWN_FREQ_RE.match(value)
                    if match:
                        number_text, unit = match.groups()
                        try:
                            mhz_value = Decimal(number_text)
                            if unit.lower() == "ghz":
                                mhz_value *= Decimal("1000")
                            new_obj[key] = decimal_to_json_number(mhz_value)
                            new_obj["frequency_unit"] = "MHz"
                            continue
                        except (InvalidOperation, ValueError) as exc:
                            # Extremely unlikely due to regex, but keep input value if parsing fails.
                            warnings.append(f"{path_to_text(current_path)}: could not parse frequency {value!r}: {exc}")
                            new_obj[key] = value
                            continue
                    unknown = UNKNOWN_UNIT_RE.match(value)
                    if unknown:
                        warnings.append(
                            f"{path_to_text(current_path)}: unknown frequency unit in {value!r}; value left unchanged"
                        )
                    new_obj[key] = value
                else:
                    # Numeric or any non-string frequency value is preserved unchanged.
                    new_obj[key] = value
            else:
                new_obj[key] = transform(value, current_path)
        return new_obj

    # Preserve all scalar values unchanged.
    return node


with input_path.open("r", encoding="utf-8") as f:
    data = json.load(f)

result = transform(data)

with output_path.open("w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write("\n")

with warnings_path.open("w", encoding="utf-8") as f:
    if warnings:
        f.write("\n".join(warnings))
        f.write("\n")

print(f"Read: {input_path}")
print(f"Wrote transformed JSON: {output_path}")
print(f"Wrote warnings: {warnings_path}")
print(f"Warnings: {len(warnings)}")
for warning in warnings:
    print("WARNING", warning)
