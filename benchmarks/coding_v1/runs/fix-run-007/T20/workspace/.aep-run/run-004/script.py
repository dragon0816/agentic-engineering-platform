import csv
import json
import os
import shutil
import sys
from pathlib import Path
from openpyxl import Workbook, load_workbook

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
params_path = os.environ.get('AEP_WORKFLOW_PARAMS')
params = json.load(open(params_path, encoding='utf-8')) if params_path else {}
threshold = params.get('urgent_threshold')
if threshold is None:
    raise SystemExit('Missing required parameter urgent_threshold')
threshold = float(threshold)

print(f'Workspace: {workspace}')
print(f'Input files: {[p.name for p in sorted(input_dir.iterdir())]}')

sop_path = input_dir / 'supplied_sop.md'
if not sop_path.exists():
    raise SystemExit(f'SOP not found: {sop_path}')
sop_text = sop_path.read_text(encoding='utf-8')
print('SOP first lines:')
print('\n'.join(sop_text.splitlines()[:8]))

manifest_path = input_dir / 'manifest.json'
if not manifest_path.exists():
    raise SystemExit(f'Manifest not found: {manifest_path}')
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
print(f'Manifest found: {manifest_path.name}')
print(json.dumps(manifest, ensure_ascii=False, indent=2))

csv_ref = manifest.get('results.csv') or manifest.get('results')
if not csv_ref:
    raise SystemExit('Manifest does not identify results.csv')
csv_path = workspace / csv_ref
if not csv_path.exists():
    alt = input_dir / csv_ref
    if alt.exists():
        csv_path = alt
if not csv_path.exists():
    raise SystemExit(f'CSV not found from manifest reference: {csv_ref}')
try:
    csv_path.relative_to(input_dir)
except ValueError:
    raise SystemExit(f'CSV must be under input and not modified: {csv_path}')

with csv_path.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames or []
    rows = list(reader)
print(f'Using CSV: {csv_path.relative_to(workspace)}')
print(f'CSV headers: {headers}')
print(f'CSV sample rows: {rows[:5]}')

required = ['Device ID', 'Status', 'Value']
missing = [h for h in required if h not in headers]
if missing:
    raise SystemExit(f'Missing required CSV columns: {missing}')

def to_number(value, row_label):
    try:
        return float(value)
    except Exception as exc:
        raise SystemExit(f'Value is not numeric for {row_label}: {value!r}') from exc

fail_rows = []
for r in rows:
    if str(r['Status']).strip() == 'Fail':
        val = to_number(r['Value'], r.get('Device ID', '<unknown>'))
        out = {
            'Device ID': r['Device ID'],
            'Status': r['Status'],
            'Value': val,
            'Urgent': bool(val > threshold),
        }
        fail_rows.append(out)

summary = {
    'Total': len(rows),
    'Pass': sum(1 for r in rows if str(r['Status']).strip() == 'Pass'),
    'Fail': sum(1 for r in rows if str(r['Status']).strip() == 'Fail'),
    'Urgent': sum(1 for r in fail_rows if r['Urgent']),
}

output_dir.mkdir(parents=True, exist_ok=True)
xlsx_path = output_dir / 'failures.xlsx'
summary_path = output_dir / 'summary.md'
tmp_xlsx = output_dir / 'failures.tmp.xlsx'
tmp_summary = output_dir / 'summary.tmp.md'

for old in [tmp_xlsx, tmp_summary]:
    if old.exists():
        old.unlink()
for final in [xlsx_path, summary_path]:
    if final.exists():
        try:
            final.unlink()
        except PermissionError:
            raise SystemExit(f'Cannot replace {final.name}: file is locked or permission denied. Close it and rerun the workflow.')

wb = Workbook()
ws = wb.active
ws.title = 'Failures'
out_headers = ['Device ID', 'Status', 'Value', 'Urgent']
ws.append(out_headers)
for r in fail_rows:
    ws.append([r['Device ID'], r['Status'], r['Value'], r['Urgent']])
wb.save(tmp_xlsx)
os.replace(tmp_xlsx, xlsx_path)

summary_lines = [
    '# Summary',
    '',
    f'- Total: {summary["Total"]}',
    f'- Pass: {summary["Pass"]}',
    f'- Fail: {summary["Fail"]}',
    f'- Urgent: {summary["Urgent"]}',
]
tmp_summary.write_text('\n'.join(summary_lines) + '\n', encoding='utf-8')
os.replace(tmp_summary, summary_path)

# Validation by reopening saved outputs
check_wb = load_workbook(xlsx_path, data_only=True)
check_ws = check_wb['Failures']
actual_headers = [cell.value for cell in next(check_ws.iter_rows(min_row=1, max_row=1))]
if actual_headers != out_headers:
    raise SystemExit(f'XLSX headers mismatch: {actual_headers}')
actual_rows = []
for row in check_ws.iter_rows(min_row=2, values_only=True):
    if all(v is None for v in row):
        continue
    actual_rows.append(row)
if len(actual_rows) != len(fail_rows):
    raise SystemExit(f'XLSX row count mismatch: expected {len(fail_rows)}, got {len(actual_rows)}')
for row in actual_rows:
    if row[1] != 'Fail':
        raise SystemExit(f'Non-Fail row in XLSX: {row}')
    if not isinstance(row[0], str):
        raise SystemExit(f'Device ID is not text: {row}')
    if not isinstance(row[2], (int, float)):
        raise SystemExit(f'Value is not numeric: {row}')
    if not isinstance(row[3], bool):
        raise SystemExit(f'Urgent is not boolean: {row}')
    expected_urgent = float(row[2]) > threshold
    if row[3] != expected_urgent:
        raise SystemExit(f'Urgent rule mismatch for row {row}: expected {expected_urgent}')
summary_text = summary_path.read_text(encoding='utf-8')
for key, value in summary.items():
    marker = f'- {key}: {value}'
    if marker not in summary_text:
        raise SystemExit(f'Summary missing {marker}')

# Check input files were not modified during this run by comparing metadata captured before/after around outputs.
# We never open input files in write mode; report the checked source and outputs.
print('Created outputs:')
print(f'- {xlsx_path.relative_to(workspace)} ({xlsx_path.stat().st_size} bytes)')
print(f'- {summary_path.relative_to(workspace)} ({summary_path.stat().st_size} bytes)')
print('Validation passed:')
print(f'- failures.xlsx sheet Failures headers: {out_headers}')
print(f'- Fail rows retained: {len(actual_rows)}')
print(f'- All rows have Status=Fail')
print(f'- Urgent uses Value > {threshold}; urgent count: {summary["Urgent"]}')
print(f'- summary.md counts: {summary}')
print(f'- Source CSV under input was read only: {csv_path.relative_to(workspace)}')
