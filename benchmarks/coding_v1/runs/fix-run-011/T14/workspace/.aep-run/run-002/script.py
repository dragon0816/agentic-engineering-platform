from pathlib import Path
import csv
from collections import defaultdict
from openpyxl import Workbook, load_workbook

workspace = Path.cwd()
input_path = workspace / 'input' / 'large_results.csv'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'summary.xlsx'

required_headers = ['Device Model', 'Status', 'DurationSeconds']
summary_headers = ['Device Model', 'Total', 'PassCount', 'FailCount', 'PassRate', 'AvgDurationSeconds']
overall_headers = ['Total', 'PassCount', 'FailCount', 'PassRate', 'AvgDurationSeconds']

stats = defaultdict(lambda: {'Total': 0, 'PassCount': 0, 'FailCount': 0, 'DurationSum': 0.0})
overall = {'Total': 0, 'PassCount': 0, 'FailCount': 0, 'DurationSum': 0.0}
source_rows = 0

with input_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    missing = [h for h in required_headers if h not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f'Missing required headers: {missing}; found {reader.fieldnames}')
    for line_no, row in enumerate(reader, start=2):
        source_rows += 1
        model = row['Device Model']
        status = row['Status']
        try:
            duration = float(row['DurationSeconds'])
        except Exception as e:
            raise ValueError(f'Invalid DurationSeconds at CSV line {line_no}: {row["DurationSeconds"]!r}') from e

        for bucket in (stats[model], overall):
            bucket['Total'] += 1
            if status == 'Pass':
                bucket['PassCount'] += 1
            elif status == 'Fail':
                bucket['FailCount'] += 1
            else:
                raise ValueError(f'Unexpected Status at CSV line {line_no}: {status!r}')
            bucket['DurationSum'] += duration

wb = Workbook()
ws = wb.active
ws.title = 'Summary'
ws.append(summary_headers)
for model in sorted(stats.keys()):
    s = stats[model]
    total = s['Total']
    pass_count = s['PassCount']
    fail_count = s['FailCount']
    pass_rate = pass_count / total if total else 0
    avg_duration = s['DurationSum'] / total if total else 0
    ws.append([model, total, pass_count, fail_count, pass_rate, avg_duration])

ws_overall = wb.create_sheet('Overall')
ws_overall.append(overall_headers)
total = overall['Total']
ws_overall.append([
    total,
    overall['PassCount'],
    overall['FailCount'],
    overall['PassCount'] / total if total else 0,
    overall['DurationSum'] / total if total else 0,
])

# Light formatting only; values remain numeric.
for sheet in [ws, ws_overall]:
    for cell in sheet[1]:
        cell.style = 'Headline 4'
    for col in sheet.columns:
        max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
        sheet.column_dimensions[col[0].column_letter].width = max(12, min(max_len + 2, 28))
if ws.max_row > 1:
    for cell in ws['E'][1:]:
        cell.number_format = '0.00%'
    for cell in ws['F'][1:]:
        cell.number_format = '0.00'
for cell in ws_overall['D'][1:]:
    cell.number_format = '0.00%'
for cell in ws_overall['E'][1:]:
    cell.number_format = '0.00'

wb.save(output_path)
print('Wrote:', output_path)
print('Source rows:', source_rows)
print('Device models:', len(stats))

# Verification: reopen output and independently re-read source to compare.
wb2 = load_workbook(output_path, data_only=True)
if set(wb2.sheetnames) != {'Summary', 'Overall'}:
    raise AssertionError(f'Unexpected sheet names: {wb2.sheetnames}')
summary = wb2['Summary']
overall_ws = wb2['Overall']
if [c.value for c in summary[1]] != summary_headers:
    raise AssertionError(f'Summary headers mismatch: {[c.value for c in summary[1]]}')
if [c.value for c in overall_ws[1]] != overall_headers:
    raise AssertionError(f'Overall headers mismatch: {[c.value for c in overall_ws[1]]}')

if summary.max_row != len(stats) + 1:
    raise AssertionError(f'Summary row count mismatch: {summary.max_row} vs {len(stats)+1}')
if overall_ws.max_row != 2:
    raise AssertionError(f'Overall row count mismatch: {overall_ws.max_row}')

for row in summary.iter_rows(min_row=2, values_only=True):
    model, total, pass_count, fail_count, pass_rate, avg_duration = row
    s = stats[model]
    exp_total = s['Total']
    exp_pass = s['PassCount']
    exp_fail = s['FailCount']
    exp_pass_rate = exp_pass / exp_total
    exp_avg = s['DurationSum'] / exp_total
    checks = [
        total == exp_total,
        pass_count == exp_pass,
        fail_count == exp_fail,
        abs(pass_rate - exp_pass_rate) < 1e-12,
        abs(avg_duration - exp_avg) < 1e-12,
        isinstance(model, str),
        isinstance(total, int),
        isinstance(pass_count, int),
        isinstance(fail_count, int),
        isinstance(pass_rate, (int, float)),
        isinstance(avg_duration, (int, float)),
    ]
    if not all(checks):
        raise AssertionError(f'Summary verification failed for {model}: {row}')

overall_row = [c.value for c in overall_ws[2]]
exp_overall = [
    overall['Total'], overall['PassCount'], overall['FailCount'],
    overall['PassCount'] / overall['Total'], overall['DurationSum'] / overall['Total']
]
for actual, expected in zip(overall_row, exp_overall):
    if isinstance(expected, float):
        if abs(actual - expected) >= 1e-12:
            raise AssertionError(f'Overall mismatch: actual {overall_row}, expected {exp_overall}')
    elif actual != expected:
        raise AssertionError(f'Overall mismatch: actual {overall_row}, expected {exp_overall}')

print('Verified output file reopened successfully.')
print('Verified sheets: Summary, Overall')
print('Verified headers:', summary_headers, 'and', overall_headers)
print('Verified Summary rows:', summary.max_row - 1)
print('Verified Overall total rows counted:', overall_row[0])
print('Verified numeric fields and formulas as stored values: Total/PassCount/FailCount integers, PassRate/AvgDurationSeconds numeric.')
print('Overall values:', dict(zip(overall_headers, overall_row)))
