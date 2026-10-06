from pathlib import Path
import csv, os, tempfile
from openpyxl import Workbook, load_workbook

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

# Inspect actual inputs before processing
print('Workspace:', workspace)
print('Input files:')
for p in sorted(input_dir.rglob('*')):
    print(' -', p.relative_to(workspace), 'dir' if p.is_dir() else f'{p.stat().st_size} bytes')

sop_path = input_dir / 'supplied_sop.md'
csv_path = input_dir / 'data' / 'test_results.csv'
print('SOP exists:', sop_path.exists(), sop_path)
print('CSV exists:', csv_path.exists(), csv_path)
with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    print('CSV sample:')
    for i, row in zip(range(6), reader):
        print(' ', row)

threshold = 20
xlsx_path = output_dir / 'failures.xlsx'
summary_path = output_dir / 'summary.md'

# Read source CSV without modifying input
with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames
    if headers != ['Device ID', 'Status', 'Value']:
        raise ValueError(f'Unexpected CSV headers: {headers!r}')
    rows = []
    for row in reader:
        # Preserve original column names and normalize only for logic
        row['Value'] = int(row['Value'])
        rows.append(row)

fail_rows = [r for r in rows if r['Status'] == 'Fail']
for r in fail_rows:
    r['Urgent'] = bool(r['Value'] > threshold)

# Write failures.xlsx atomically enough to avoid leaving a broken workbook.
# If a stale zero-byte output exists, remove it first. If Excel has it open,
# this will raise a clear PermissionError.
if xlsx_path.exists():
    try:
        xlsx_path.unlink()
        print('Removed existing output/failures.xlsx before rewrite')
    except PermissionError as e:
        raise PermissionError(f'Cannot replace {xlsx_path}; please close any application holding it open') from e

wb = Workbook()
ws = wb.active
ws.title = 'Failures'
output_headers = ['Device ID', 'Status', 'Value', 'Urgent']
ws.append(output_headers)
for r in fail_rows:
    ws.append([r['Device ID'], r['Status'], r['Value'], r['Urgent']])
wb.save(xlsx_path)

# Summary counts
summary = {
    'Total': len(rows),
    'Pass': sum(1 for r in rows if r['Status'] == 'Pass'),
    'Fail': len(fail_rows),
    'Urgent': sum(1 for r in fail_rows if r['Urgent']),
}
summary_text = '\n'.join([
    '# Summary',
    '',
    f'- Total: {summary["Total"]}',
    f'- Pass: {summary["Pass"]}',
    f'- Fail: {summary["Fail"]}',
    f'- Urgent: {summary["Urgent"]}',
    '',
])
summary_path.write_text(summary_text, encoding='utf-8')

# Validation: reopen every output file and confirm requirements
wb2 = load_workbook(xlsx_path, data_only=True)
ws2 = wb2['Failures']
read_rows = list(ws2.iter_rows(values_only=True))
assert read_rows[0] == tuple(output_headers), f'Bad XLSX headers: {read_rows[0]}'
assert len(read_rows) == len(fail_rows) + 1, f'Bad XLSX row count: {len(read_rows)}'
expected = [
    ('D01', 'Fail', 10, False),
    ('D03', 'Fail', 20, False),
    ('D05', 'Fail', 30, True),
]
actual = read_rows[1:]
assert actual == expected, f'Unexpected XLSX rows: {actual!r}'
for row in actual:
    assert isinstance(row[0], str), f'Device ID not text: {row[0]!r}'
    assert isinstance(row[1], str), f'Status not text: {row[1]!r}'
    assert isinstance(row[2], int), f'Value not numeric int: {row[2]!r}'
    assert isinstance(row[3], bool), f'Urgent not boolean: {row[3]!r}'

summary_read = summary_path.read_text(encoding='utf-8')
for key, val in summary.items():
    needle = f'- {key}: {val}'
    assert needle in summary_read, f'Missing summary line: {needle}'

print('Created outputs:')
for p in [xlsx_path, summary_path]:
    print(' -', p.relative_to(workspace), p.stat().st_size, 'bytes')
print('Validation passed: failures.xlsx has headers Device ID/Status/Value/Urgent, 3 Fail rows, numeric Values, boolean Urgent values with Value > 20 rule; summary.md has Total=5, Pass=2, Fail=3, Urgent=1.')
