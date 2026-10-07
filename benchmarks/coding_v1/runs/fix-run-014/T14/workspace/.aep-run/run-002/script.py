from pathlib import Path
import csv
from collections import defaultdict
from openpyxl import Workbook, load_workbook

ws = Path.cwd()
input_path = ws / 'input' / 'large_results.csv'
output_dir = ws / 'output'
output_dir.mkdir(exist_ok=True)
output_path = output_dir / 'summary.xlsx'

headers_required = ['Test ID', 'Device Model', 'Status', 'DurationSeconds']

stats = defaultdict(lambda: {'Total': 0, 'PassCount': 0, 'FailCount': 0, 'DurationSum': 0.0})
overall = {'Total': 0, 'PassCount': 0, 'FailCount': 0, 'DurationSum': 0.0}

with input_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    print('Input headers:', reader.fieldnames)
    missing = [h for h in headers_required if h not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f'Missing required columns: {missing}')
    for row_num, row in enumerate(reader, start=2):
        model = row['Device Model']
        status = row['Status']
        try:
            duration = float(row['DurationSeconds'])
        except Exception as e:
            raise ValueError(f'Invalid DurationSeconds at CSV row {row_num}: {row["DurationSeconds"]!r}') from e
        for bucket in (stats[model], overall):
            bucket['Total'] += 1
            if status == 'Pass':
                bucket['PassCount'] += 1
            elif status == 'Fail':
                bucket['FailCount'] += 1
            bucket['DurationSum'] += duration

wb = Workbook()
ws_summary = wb.active
ws_summary.title = 'Summary'
columns = ['Device Model', 'Total', 'PassCount', 'FailCount', 'PassRate', 'AvgDurationSeconds']
ws_summary.append(columns)
for model in sorted(stats):
    s = stats[model]
    total = s['Total']
    pass_rate = s['PassCount'] / total if total else 0
    avg_duration = s['DurationSum'] / total if total else 0
    ws_summary.append([model, total, s['PassCount'], s['FailCount'], pass_rate, avg_duration])

ws_overall = wb.create_sheet('Overall')
ws_overall.append(['Total', 'PassCount', 'FailCount', 'PassRate', 'AvgDurationSeconds'])
total = overall['Total']
pass_rate = overall['PassCount'] / total if total else 0
avg_duration = overall['DurationSum'] / total if total else 0
ws_overall.append([total, overall['PassCount'], overall['FailCount'], pass_rate, avg_duration])

for sheet in (ws_summary, ws_overall):
    for row in sheet.iter_rows(min_row=2):
        # PassRate column differs by sheet
        pass_rate_cell = row[4] if sheet.title == 'Summary' else row[3]
        pass_rate_cell.number_format = '0.00%'
        avg_cell = row[5] if sheet.title == 'Summary' else row[4]
        avg_cell.number_format = '0.00'

wb.save(output_path)
print('Wrote:', output_path)
print('models:', len(stats), 'input rows:', overall['Total'])

# Verification: reopen output and validate requirements
check_wb = load_workbook(output_path, data_only=True)
print('Workbook sheets:', check_wb.sheetnames)
assert 'Summary' in check_wb.sheetnames, 'Missing Summary sheet'
assert 'Overall' in check_wb.sheetnames, 'Missing Overall sheet'

sht = check_wb['Summary']
out_headers = [cell.value for cell in sht[1]]
assert out_headers == columns, f'Summary headers mismatch: {out_headers}'
summary_rows = list(sht.iter_rows(min_row=2, values_only=True))
assert len(summary_rows) == len(stats), f'Summary row count mismatch: {len(summary_rows)} vs {len(stats)}'
for row in summary_rows:
    model, total, pass_count, fail_count, pass_rate, avg_dur = row
    source = stats[model]
    assert isinstance(model, str), f'Model is not text: {model!r}'
    assert total == source['Total'], f'Total mismatch for {model}'
    assert pass_count == source['PassCount'], f'PassCount mismatch for {model}'
    assert fail_count == source['FailCount'], f'FailCount mismatch for {model}'
    assert abs(pass_rate - (source['PassCount'] / source['Total'])) < 1e-12, f'PassRate mismatch for {model}'
    assert abs(avg_dur - (source['DurationSum'] / source['Total'])) < 1e-12, f'AvgDurationSeconds mismatch for {model}'
    assert isinstance(total, int), f'Total not int for {model}'
    assert isinstance(pass_count, int), f'PassCount not int for {model}'
    assert isinstance(fail_count, int), f'FailCount not int for {model}'
    assert isinstance(pass_rate, (int, float)), f'PassRate not numeric for {model}'
    assert isinstance(avg_dur, (int, float)), f'AvgDurationSeconds not numeric for {model}'

oht = check_wb['Overall']
overall_headers = [cell.value for cell in oht[1]]
expected_overall_headers = ['Total', 'PassCount', 'FailCount', 'PassRate', 'AvgDurationSeconds']
assert overall_headers == expected_overall_headers, f'Overall headers mismatch: {overall_headers}'
overall_rows = list(oht.iter_rows(min_row=2, values_only=True))
assert len(overall_rows) == 1, f'Overall row count mismatch: {len(overall_rows)}'
orow = overall_rows[0]
assert orow[0] == overall['Total'], 'Overall Total mismatch'
assert orow[1] == overall['PassCount'], 'Overall PassCount mismatch'
assert orow[2] == overall['FailCount'], 'Overall FailCount mismatch'
assert abs(orow[3] - (overall['PassCount'] / overall['Total'])) < 1e-12, 'Overall PassRate mismatch'
assert abs(orow[4] - (overall['DurationSum'] / overall['Total'])) < 1e-12, 'Overall AvgDurationSeconds mismatch'
for value in orow:
    assert isinstance(value, (int, float)), f'Overall value not numeric: {value!r}'
print('Verification passed: output file reopened; sheet names, headers, row counts, numeric values, PassRate formulas/results, and averages match source data.')
