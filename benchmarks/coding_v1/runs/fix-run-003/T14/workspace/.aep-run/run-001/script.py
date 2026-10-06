from pathlib import Path
import csv
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

workspace = Path.cwd()
input_path = workspace / "input" / "large_results.csv"
output_dir = workspace / "output"
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "summary.xlsx"

if not input_path.exists():
    raise FileNotFoundError(f"Input file not found: {input_path}")

# Helpers to find expected columns even if minor naming variants exist.
def normalize(name: str) -> str:
    return ''.join(ch.lower() for ch in (name or '') if ch.isalnum())

with input_path.open("r", newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    fieldnames = reader.fieldnames
    norm_to_name = {normalize(n): n for n in fieldnames}

    def pick(*candidates):
        for c in candidates:
            key = normalize(c)
            if key in norm_to_name:
                return norm_to_name[key]
        return None

    model_col = pick("Device Model", "DeviceModel", "Model")
    result_col = pick("Result", "Status", "Test Result", "Outcome")
    duration_col = pick("DurationSeconds", "Duration Seconds", "Duration", "ElapsedSeconds", "Elapsed Seconds")

    missing = [label for label, col in [("Device Model", model_col), ("Result/Status", result_col), ("DurationSeconds", duration_col)] if col is None]
    if missing:
        raise ValueError(f"Missing required column(s): {missing}. Found columns: {fieldnames}")

    stats = defaultdict(lambda: {"total": 0, "pass": 0, "fail": 0, "duration_sum": 0.0})
    overall = {"total": 0, "pass": 0, "fail": 0, "duration_sum": 0.0}

    for row_num, row in enumerate(reader, start=2):
        model = (row.get(model_col) or "").strip() or "(blank)"
        result = (row.get(result_col) or "").strip().lower()
        duration_raw = (row.get(duration_col) or "").strip()
        try:
            duration = float(duration_raw) if duration_raw != "" else 0.0
        except ValueError:
            raise ValueError(f"Invalid duration at CSV row {row_num}: {duration_raw!r}")

        is_pass = result in {"pass", "passed", "true", "1", "ok", "success"}
        is_fail = result in {"fail", "failed", "false", "0", "ng", "error"}
        # For Total and average, include every row. For FailCount, count explicit fails;
        # if the dataset uses only pass/fail values, this equals non-passes.
        if not is_pass and not is_fail:
            # Treat any non-pass result as a fail for pass/fail summaries.
            is_fail = True

        for bucket in (stats[model], overall):
            bucket["total"] += 1
            bucket["pass"] += 1 if is_pass else 0
            bucket["fail"] += 1 if is_fail else 0
            bucket["duration_sum"] += duration

headers = ["Device Model", "Total", "PassCount", "FailCount", "PassRate", "AvgDurationSeconds"]
overall_headers = ["Total", "PassCount", "FailCount", "PassRate", "AvgDurationSeconds"]

wb = Workbook()
ws = wb.active
ws.title = "By Device Model"
ws.append(headers)

for model in sorted(stats):
    s = stats[model]
    total = s["total"]
    pass_rate = s["pass"] / total if total else 0
    avg_duration = s["duration_sum"] / total if total else 0
    ws.append([model, total, s["pass"], s["fail"], pass_rate, avg_duration])

ws_overall = wb.create_sheet("Overall")
ws_overall.append(overall_headers)
total = overall["total"]
ws_overall.append([
    total,
    overall["pass"],
    overall["fail"],
    overall["pass"] / total if total else 0,
    overall["duration_sum"] / total if total else 0,
])

for sheet in (ws, ws_overall):
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in sheet.iter_rows(min_row=2):
        # PassRate column is E in both sheets.
        row[4].number_format = "0.00%"
        row[5].number_format = "0.00"
    for col_idx, column_cells in enumerate(sheet.columns, start=1):
        max_len = 0
        for cell in column_cells:
            value = cell.value
            max_len = max(max_len, len(str(value)) if value is not None else 0)
        sheet.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 40)

wb.save(output_path)

print(f"Read: {input_path}")
print(f"Columns used: model={model_col!r}, result={result_col!r}, duration={duration_col!r}")
print(f"Device models summarized: {len(stats)}")
print(f"Overall rows: {overall['total']}, pass={overall['pass']}, fail={overall['fail']}")
print(f"Wrote: {output_path}")