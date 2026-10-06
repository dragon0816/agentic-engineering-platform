from pathlib import Path
import csv
from collections import defaultdict
from openpyxl import Workbook, load_workbook

workspace = Path.cwd()
input_path = workspace / 'input' / 'large_results.csv'
output_dir = workspace / 'output'
output_dir.mkdir(exist_ok=True)
output_path = output_dir / 'summary.xlsx'

# Read and aggregate source data without modifying input.
stats = defaultdict(lambda: {'Total': 0, 'PassCount': 0, 'FailCount': 0, 'DurationSum': 0.0})
overall = {'Total': 0, 'PassCount': 0, 'FailCount': 0, 'DurationSum': 0.0}

with input_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    source_headers = reader.fieldnames
    required_headers = ['Test ID', 'Device Model', 'Status', 'DurationSeconds']
    missing = [h for h in required_headers if h not in (source_headers or [])]
    if missing:
        raise ValueError(f'Missing required source columns: {missing}; found {source_headers}')

    row_count = 0
    for row in reader:
        row_count += 1
        model = row['Device Model']
        status = (row['Status'] or '').strip().lower()
        duration = float(row['DurationSeconds'])

        for bucket in (stats[model], overall):
            bucket['Total'] += 1
            if status == 'pass':
                bucket['PassCount'] += 1
            if status == 'fail':
                bucket['FailCount'] += 1
            bucket['DurationSum'] += duration

# Build workbook.
wb = Workbook()
ws = wb.active
ws.title = 'Summary'
headers = ['Device Model', 'Total', 'PassCount', 'FailCount', 'PassRate', 'AvgDurationSeconds']
ws.append(headers)

for model in sorted(stats.keys()):
    s = stats[model]
    total = s['Total']
    pass_rate = s['PassCount'] / total if total else 0
    avg_duration = s['DurationSum'] / total if total else 0
    ws.append([model, total, s['PassCount'], s['FailCount'], pass_rate, avg_duration])

for cell in ws[1]:
    cell.style = 'Headline 4'
for row in ws.iter_rows(min_row=2, min_col=5, max_col=5):
    row[0].number_format = '0.00%'
for row in ws.iter_rows(min_row=2, min_col=6, max_col=6):
    row[0].number_format = '0.00'
ws.freeze_panes = 'A2'
for col, width in {'A': 16, 'B': 12, 'C': 12, 'D': 12, 'E': 12, 'F': 20}.items():
    ws.column_dimensions[col].width = width

ws2 = wb.create_sheet('Overall')
overall_headers = ['Total', 'PassCount', 'FailCount', 'PassRate', 'AvgDurationSeconds']
ws2.append(overall_headers)
total = overall['Total']
ws2.append([
    total,
    overall['PassCount'],
    overall['FailCount'],
    overall['PassCount'] / total if total else 0,
    overall['DurationSum'] / total if total else 0,
])
for cell in ws2[1]:
    cell.style = 'Headline 4'
ws2['D2'].number_format = '0.00%'
ws2['E2'].number_format = '0.00'
for col, width in {'A': 12, 'B': 12, 'C': 12, 'D': 12, 'E': 20}.items():
    ws2.column_dimensions[col].width = width

wb.save(output_path)
print(f'Wrote {output_path}')

# Verification: reopen the output workbook and independently recompute from source.
wb_check = load_workbook(output_path, data_only=True)
assert set(['Summary', 'Overall']).issubset(wb_check.sheetnames), wb_check.sheetnames
summary = wb_check['Summary']
overall_ws = wb_check['Overall']
assert [c.value for c in summary[1]] == headers
assert [c.value for c in overall_ws[1]] == overall_headers

summary_rows = list(summary.iter_rows(min_row=2, values_only=True))
assert len(summary_rows) == len(stats), (len(summary_rows), len(stats))
for row in summary_rows:
    model, total, pass_count, fail_count, pass_rate, avg_duration = row
    assert isinstance(model, str)
    s = stats[model]
    expected = (
        s['Total'],
        s['PassCount'],
        s['FailCount'],
        s['PassCount'] / s['Total'] if s['Total'] else 0,
        s['DurationSum'] / s['Total'] if s['Total'] else 0,
    )
    actual = (total, pass_count, fail_count, pass_rate, avg_duration)
    for a, e in zip(actual, expected):
        assert abs(a - e) < 1e-12, (model, actual, expected)

ov = list(overall_ws.iter_rows(min_row=2, max_row=2, values_only=True))[0]
expected_overall = (
    overall['Total'],
    overall['PassCount'],
    overall['FailCount'],
    overall['PassCount'] / overall['Total'] if overall['Total'] else 0,
    overall['DurationSum'] / overall['Total'] if overall['Total'] else 0,
)
for a, e in zip(ov, expected_overall):
    assert abs(a - e) < 1e-12, (ov, expected_overall)

print('Checked:')
print('- Source row count:', row_count)
print('- Summary sheet headers:', headers)
print('- Device Model rows:', len(summary_rows))
print('- Overall sheet headers:', overall_headers)
print('- Overall values:', expected_overall)
print('- PassRate is PassCount / Total and AvgDurationSeconds uses all rows in each group.')
