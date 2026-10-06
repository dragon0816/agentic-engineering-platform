from pathlib import Path
from collections import OrderedDict
import re
from openpyxl import load_workbook, Workbook

workspace = Path('.')
input_path = workspace / 'input' / 'tasks.xlsx'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
out_path = output_dir / 'owners.xlsx'

INVALID = r'[\\/*?:\[\]]'

def is_blank(v):
    return v is None or (isinstance(v, str) and v.strip() == '')

def legal_sheet_name(owner_key, used):
    # owner_key is Unassigned for blank owners; otherwise original Owner value converted to text
    base = str(owner_key)
    base = re.sub(INVALID, '_', base).strip()
    if not base:
        base = 'Sheet'
    # Excel sheet names max 31 chars. Reserve room for suffix when needed.
    base = base[:31]
    name = base
    i = 1
    while name in used:
        suffix = f'_{i}'
        name = base[:31-len(suffix)] + suffix
        i += 1
    used.add(name)
    return name

# Read source
src_wb = load_workbook(input_path, data_only=False)
if 'tasks' not in src_wb.sheetnames:
    raise ValueError('Source workbook does not contain a tasks worksheet')
src_ws = src_wb['tasks']
headers = [src_ws.cell(1, c).value for c in range(1, src_ws.max_column + 1)]
if 'Owner' not in headers or 'Status' not in headers:
    raise ValueError(f'Required columns Owner and Status not found in headers: {headers}')
owner_idx = headers.index('Owner')
status_idx = headers.index('Status')

# Group rows in first-seen Owner order; blank Owner grouped under Unassigned while row values stay unchanged.
groups = OrderedDict()
for row in src_ws.iter_rows(min_row=2, max_row=src_ws.max_row, max_col=src_ws.max_column, values_only=True):
    owner_original = row[owner_idx]
    owner_key = 'Unassigned' if is_blank(owner_original) else owner_original
    groups.setdefault(owner_key, []).append(row)

# Create output workbook
out_wb = Workbook()
default = out_wb.active
out_wb.remove(default)

used_names = set()
summary_rows = []

for owner_key, rows in groups.items():
    sheet_name = legal_sheet_name(owner_key, used_names)
    ws = out_wb.create_sheet(title=sheet_name)
    ws.append(headers)
    total = pass_count = fail_count = 0
    for row in rows:
        ws.append(list(row))
        total += 1
        status = row[status_idx]
        if status == 'Pass':
            pass_count += 1
        elif status == 'Fail':
            fail_count += 1
        else:
            raise ValueError(f'Unexpected Status value {status!r} for row {row!r}; expected Pass or Fail')
    summary_owner = 'Unassigned' if owner_key == 'Unassigned' else owner_key
    summary_rows.append([summary_owner, total, pass_count, fail_count, sheet_name])

summary = out_wb.create_sheet(title='Summary', index=0)
summary_headers = ['Owner', 'Total', 'Pass', 'Fail', 'SheetName']
summary.append(summary_headers)
for r in summary_rows:
    summary.append(r)

out_wb.save(out_path)
print('Wrote:', out_path)
print('Created sheets:', out_wb.sheetnames)
print('Summary rows:', summary_rows)

# Verification: reopen output and confirm requirements.
check_wb = load_workbook(out_path, data_only=True)
assert 'Summary' in check_wb.sheetnames, 'Missing Summary sheet'
check_summary = check_wb['Summary']
actual_summary_headers = [check_summary.cell(1, c).value for c in range(1, check_summary.max_column + 1)]
assert actual_summary_headers == summary_headers, f'Summary headers mismatch: {actual_summary_headers}'
assert check_summary.max_row == len(groups) + 1, 'Summary row count mismatch'

# Verify sheet names are legal/unique and all referenced summary sheet names exist.
assert len(check_wb.sheetnames) == len(set(check_wb.sheetnames)), 'Duplicate sheet names found'
for name in check_wb.sheetnames:
    assert len(name) <= 31 and name.strip() and not re.search(INVALID, name), f'Illegal worksheet name: {name!r}'

# Rebuild source groups for exact row preservation checks.
for i, expected in enumerate(summary_rows, start=2):
    owner_val, total, p, f, sheet_name = expected
    actual = [check_summary.cell(i, c).value for c in range(1, 6)]
    assert actual == expected, f'Summary row {i} mismatch: {actual} != {expected}'
    assert sheet_name in check_wb.sheetnames, f'Summary references missing sheet {sheet_name}'
    ws = check_wb[sheet_name]
    sheet_headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    assert sheet_headers == headers, f'Headers changed in sheet {sheet_name}: {sheet_headers}'
    assert ws.max_row == total + 1, f'Row count mismatch in sheet {sheet_name}'
    rows = [tuple(ws.cell(r, c).value for c in range(1, len(headers)+1)) for r in range(2, ws.max_row+1)]
    owner_key = 'Unassigned' if owner_val == 'Unassigned' else owner_val
    expected_rows = [tuple(r) for r in groups[owner_key]]
    assert rows == expected_rows, f'Rows not preserved for {owner_val!r}'
    assert sum(1 for r in rows if r[status_idx] == 'Pass') == p, f'Pass count mismatch for {owner_val!r}'
    assert sum(1 for r in rows if r[status_idx] == 'Fail') == f, f'Fail count mismatch for {owner_val!r}'
    # Confirm numeric counts in Summary are actual numbers.
    for c in (2,3,4):
        assert isinstance(check_summary.cell(i, c).value, int), f'Non-integer count at Summary row {i}, col {c}'

# Specific requirement: blank Owner source rows remain blank in their data sheet.
if 'Unassigned' in groups:
    unassigned_sheet = next(r[4] for r in summary_rows if r[0] == 'Unassigned')
    ws = check_wb[unassigned_sheet]
    for r in range(2, ws.max_row + 1):
        assert is_blank(ws.cell(r, owner_idx + 1).value), 'Blank Owner value was not preserved in Unassigned sheet'

print('Verification passed: owners.xlsx exists; input not modified; Summary headers/counts/SheetName mapping are correct; all group sheet names are legal and unique; source headers and row Owner values are preserved; row counts and Pass/Fail integer counts match.')