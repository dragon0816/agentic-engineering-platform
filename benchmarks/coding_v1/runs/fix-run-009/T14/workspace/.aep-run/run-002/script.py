from pathlib import Path
import csv
from collections import defaultdict
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

workspace = Path.cwd()
input_path = workspace / 'input' / 'large_results.csv'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'summary.xlsx'

required_headers = ['Test ID', 'Device Model', 'Status', 'DurationSeconds']
summary_headers = ['Device Model', 'Total', 'PassCount', 'FailCount', 'PassRate', 'AvgDurationSeconds']
overall_headers = ['Total', 'PassCount', 'FailCount', 'PassRate', 'AvgDurationSeconds']

stats = defaultdict(lambda: {'total': 0, 'pass': 0, 'fail': 0, 'duration_sum': 0.0})
overall = {'total': 0, 'pass': 0, 'fail': 0, 'duration_sum': 0.0}

with input_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    if reader.fieldnames != required_headers:
        raise ValueError(f'Unexpected headers: {reader.fieldnames!r}')
    for line_no, row in enumerate(reader, start=2):
        model = row['Device Model']
        status = row['Status']
        try:
            duration = float(row['DurationSeconds'])
        except Exception as exc:
            raise ValueError(f'Invalid DurationSeconds at line {line_no}: {row["DurationSeconds"]!r}') from exc
        rec = stats[model]
        rec['total'] += 1
        rec['duration_sum'] += duration
        if status == 'Pass':
            rec['pass'] += 1
        elif status == 'Fail':
            rec['fail'] += 1
        else:
            # Total and duration include every row; unknown statuses are neither Pass nor Fail.
            pass
        overall['total'] += 1
        overall['duration_sum'] += duration
        if status == 'Pass':
            overall['pass'] += 1
        elif status == 'Fail':
            overall['fail'] += 1

wb = Workbook()
ws = wb.active
ws.title = 'Summary'
ws.append(summary_headers)
for cell in ws[1]:
    cell.font = Font(bold=True)

for model in sorted(stats.keys()):
    rec = stats[model]
    total = rec['total']
    pass_count = rec['pass']
    fail_count = rec['fail']
    pass_rate = pass_count / total if total else 0
    avg_duration = rec['duration_sum'] / total if total else 0
    ws.append([model, total, pass_count, fail_count, pass_rate, avg_duration])

for row in ws.iter_rows(min_row=2, min_col=5, max_col=5):
    for cell in row:
        cell.number_format = '0.00%'
for row in ws.iter_rows(min_row=2, min_col=6, max_col=6):
    for cell in row:
        cell.number_format = '0.00'

ows = wb.create_sheet('Overall')
ows.append(overall_headers)
for cell in ows[1]:
    cell.font = Font(bold=True)
total = overall['total']
pass_count = overall['pass']
fail_count = overall['fail']
ows.append([
    total,
    pass_count,
    fail_count,
    pass_count / total if total else 0,
    overall['duration_sum'] / total if total else 0,
])
ows['D2'].number_format = '0.00%'
ows['E2'].number_format = '0.00'

for sheet in [ws, ows]:
    for col_idx, col_cells in enumerate(sheet.columns, start=1):
        max_len = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells)
        sheet.column_dimensions[get_column_letter(col_idx)].width = max(12, min(max_len + 2, 24))

wb.save(output_path)
print('Wrote:', output_path)
print('Models:', len(stats))
print('Overall total rows:', overall['total'])

# Verification: reopen output and independently recompute expectations from source.
check_wb = load_workbook(output_path, data_only=True)
if set(check_wb.sheetnames) != {'Summary', 'Overall'}:
    raise AssertionError(f'Unexpected sheets: {check_wb.sheetnames}')
check_ws = check_wb['Summary']
check_ows = check_wb['Overall']
if [c.value for c in check_ws[1]] != summary_headers:
    raise AssertionError('Summary headers mismatch: ' + repr([c.value for c in check_ws[1]]))
if [c.value for c in check_ows[1]] != overall_headers:
    raise AssertionError('Overall headers mismatch: ' + repr([c.value for c in check_ows[1]]))
if check_ws.max_row != len(stats) + 1:
    raise AssertionError(f'Summary row count mismatch: {check_ws.max_row} vs {len(stats)+1}')
if check_ows.max_row != 2:
    raise AssertionError(f'Overall row count mismatch: {check_ows.max_row}')

for row in check_ws.iter_rows(min_row=2, values_only=True):
    model, total_v, pass_v, fail_v, rate_v, avg_v = row
    rec = stats[model]
    exp_total = rec['total']
    exp_pass = rec['pass']
    exp_fail = rec['fail']
    exp_rate = exp_pass / exp_total if exp_total else 0
    exp_avg = rec['duration_sum'] / exp_total if exp_total else 0
    if not isinstance(model, str):
        raise AssertionError(f'Device Model is not text: {model!r}')
    if (total_v, pass_v, fail_v) != (exp_total, exp_pass, exp_fail):
        raise AssertionError(f'Counts mismatch for {model}: {(total_v, pass_v, fail_v)} vs {(exp_total, exp_pass, exp_fail)}')
    if abs(rate_v - exp_rate) > 1e-12:
        raise AssertionError(f'PassRate mismatch for {model}: {rate_v} vs {exp_rate}')
    if abs(avg_v - exp_avg) > 1e-12:
        raise AssertionError(f'AvgDurationSeconds mismatch for {model}: {avg_v} vs {exp_avg}')

orow = [c.value for c in check_ows[2]]
exp_overall = [
    overall['total'],
    overall['pass'],
    overall['fail'],
    overall['pass'] / overall['total'] if overall['total'] else 0,
    overall['duration_sum'] / overall['total'] if overall['total'] else 0,
]
for got, exp in zip(orow, exp_overall):
    if isinstance(exp, float):
        if abs(got - exp) > 1e-12:
            raise AssertionError(f'Overall mismatch: {orow} vs {exp_overall}')
    elif got != exp:
        raise AssertionError(f'Overall mismatch: {orow} vs {exp_overall}')

print('Verification passed:')
print(' - output file exists and was reopened')
print(' - sheets: Summary, Overall')
print(' - Summary headers:', summary_headers)
print(' - Overall headers:', overall_headers)
print(' - Summary data rows:', check_ws.max_row - 1)
print(' - Overall values:', orow)
print(' - all per-model totals, PassCount, FailCount, PassRate, AvgDurationSeconds match source')
