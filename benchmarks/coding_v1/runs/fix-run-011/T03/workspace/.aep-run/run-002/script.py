from pathlib import Path
from collections import OrderedDict
import re
from openpyxl import load_workbook, Workbook

workspace = Path.cwd()
input_file = workspace / 'input' / 'tasks.xlsx'
output_dir = workspace / 'output'
output_file = output_dir / 'owners.xlsx'
output_dir.mkdir(parents=True, exist_ok=True)

INVALID_SHEET_CHARS = r'[]:*?/\\'

def is_blank(value):
    return value is None or (isinstance(value, str) and value.strip() == '')

def group_key(owner):
    return 'Unassigned' if is_blank(owner) else owner

def sanitize_sheet_name(owner_key, used_names):
    # Excel worksheet names cannot contain: [ ] : * ? / \\ and must be <= 31 chars.
    raw = str(owner_key)
    name = ''.join('_' if ch in INVALID_SHEET_CHARS else ch for ch in raw).strip()
    if not name:
        name = 'Unassigned'
    # Excel also dislikes leading/trailing apostrophes in UI; make them safe.
    name = name.strip("'") or 'Sheet'
    if name.lower() == 'summary':
        name = 'Summary_1'
    base = name[:31]
    candidate = base
    counter = 1
    lowered_used = {n.lower() for n in used_names}
    while candidate.lower() in lowered_used:
        suffix = f'_{counter}'
        candidate = base[:31-len(suffix)] + suffix
        counter += 1
    used_names.add(candidate)
    return candidate

# Read source workbook and rows.
source_wb = load_workbook(input_file, data_only=False)
if 'tasks' not in source_wb.sheetnames:
    raise ValueError("Input workbook does not contain a 'tasks' worksheet")
source_ws = source_wb['tasks']
headers = [cell.value for cell in source_ws[1]]
if 'Owner' not in headers or 'Status' not in headers:
    raise ValueError(f"Required columns Owner and Status not found in headers: {headers}")
owner_idx = headers.index('Owner')
status_idx = headers.index('Status')

rows = []
for row in source_ws.iter_rows(min_row=2, max_row=source_ws.max_row, max_col=source_ws.max_column, values_only=True):
    # Keep all source rows including blank-ish rows only if any value exists.
    if not any(value is not None for value in row):
        continue
    row_values = list(row)
    rows.append(row_values)
source_wb.close()

groups = OrderedDict()
for row in rows:
    key = group_key(row[owner_idx])
    if key not in groups:
        groups[key] = []
    groups[key].append(row)

# Create output workbook.
out_wb = Workbook()
default_ws = out_wb.active
out_wb.remove(default_ws)

used_sheet_names = {'Summary'}
summary_records = []

for owner_key, owner_rows in groups.items():
    sheet_name = sanitize_sheet_name(owner_key, used_sheet_names)
    ws = out_wb.create_sheet(title=sheet_name)
    ws.append(headers)
    for row in owner_rows:
        ws.append(row)
    pass_count = sum(1 for row in owner_rows if row[status_idx] == 'Pass')
    fail_count = sum(1 for row in owner_rows if row[status_idx] == 'Fail')
    summary_records.append({
        'Owner': owner_key,
        'Total': len(owner_rows),
        'Pass': pass_count,
        'Fail': fail_count,
        'SheetName': sheet_name,
    })

summary_ws = out_wb.create_sheet(title='Summary', index=0)
summary_headers = ['Owner', 'Total', 'Pass', 'Fail', 'SheetName']
summary_ws.append(summary_headers)
for rec in summary_records:
    summary_ws.append([rec[h] for h in summary_headers])

out_wb.save(output_file)
out_wb.close()

# Verification: reopen input and output and confirm requirements.
check_wb = load_workbook(output_file, data_only=False)
print('created:', output_file)
print('output sheets:', check_wb.sheetnames)
assert check_wb.sheetnames[0] == 'Summary', 'Summary must be first worksheet'
assert 'Summary' in check_wb.sheetnames, 'Missing Summary worksheet'

summary = check_wb['Summary']
actual_summary_headers = [cell.value for cell in summary[1]]
print('Summary headers:', actual_summary_headers)
assert actual_summary_headers == summary_headers, f'Summary headers mismatch: {actual_summary_headers}'

summary_rows = []
for row in summary.iter_rows(min_row=2, values_only=True):
    if not any(value is not None for value in row):
        continue
    summary_rows.append(dict(zip(summary_headers, row)))
print('Summary rows:')
for rec in summary_rows:
    print(rec)

assert len(summary_rows) == len(groups), f'Summary row count {len(summary_rows)} != group count {len(groups)}'
assert len(set(check_wb.sheetnames)) == len(check_wb.sheetnames), 'Duplicate worksheet names found'
for name in check_wb.sheetnames:
    assert len(name) <= 31, f'Worksheet name too long: {name}'
    assert not any(ch in INVALID_SHEET_CHARS for ch in name), f'Illegal char in worksheet name: {name}'

summary_by_owner = {rec['Owner']: rec for rec in summary_rows}
assert set(summary_by_owner.keys()) == set(groups.keys()), f'Summary owners mismatch: {summary_by_owner.keys()} vs {groups.keys()}'

for owner_key, owner_rows in groups.items():
    rec = summary_by_owner[owner_key]
    sheet_name = rec['SheetName']
    assert sheet_name in check_wb.sheetnames, f'Missing owner worksheet: {sheet_name}'
    ws = check_wb[sheet_name]
    ws_headers = [cell.value for cell in ws[1]]
    assert ws_headers == headers, f'Headers changed in {sheet_name}: {ws_headers} != {headers}'
    actual_rows = []
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=len(headers), values_only=True):
        if not any(value is not None for value in row):
            continue
        actual_rows.append(list(row))
    assert actual_rows == owner_rows, f'Rows changed for owner {owner_key!r}'
    actual_pass = sum(1 for row in actual_rows if row[status_idx] == 'Pass')
    actual_fail = sum(1 for row in actual_rows if row[status_idx] == 'Fail')
    assert rec['Total'] == len(actual_rows), f'Total mismatch for {owner_key!r}'
    assert rec['Pass'] == actual_pass, f'Pass mismatch for {owner_key!r}'
    assert rec['Fail'] == actual_fail, f'Fail mismatch for {owner_key!r}'
    assert rec['Pass'] + rec['Fail'] == rec['Total'], f'Pass+Fail != Total for {owner_key!r}'
    # Owner original values are preserved in owner sheets, including blank Owner in Unassigned.
    assert [r[owner_idx] for r in actual_rows] == [r[owner_idx] for r in owner_rows], f'Owner values not preserved for {owner_key!r}'

print('validated group count:', len(groups))
print('validated source row count:', len(rows))
print('validated output owner rows:', sum(rec['Total'] for rec in summary_rows))
print('validation passed')
check_wb.close()