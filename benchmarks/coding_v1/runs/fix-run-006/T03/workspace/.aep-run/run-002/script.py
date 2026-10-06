from pathlib import Path
from collections import OrderedDict
import re
from openpyxl import load_workbook, Workbook

workspace = Path.cwd()
input_path = workspace / 'input' / 'tasks.xlsx'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'owners.xlsx'

# Read source workbook
src_wb = load_workbook(input_path, data_only=False)
if 'tasks' not in src_wb.sheetnames:
    raise ValueError('Input workbook does not contain a tasks worksheet')
src_ws = src_wb['tasks']
rows = list(src_ws.iter_rows(values_only=True))
if not rows:
    raise ValueError('tasks worksheet is empty')
headers = list(rows[0])
try:
    owner_idx = headers.index('Owner')
    status_idx = headers.index('Status')
except ValueError as exc:
    raise ValueError('tasks worksheet must contain Owner and Status columns') from exc

# Preserve source row values and group in first-seen Owner order. Blank/None owners group as Unassigned.
groups = OrderedDict()
for row in rows[1:]:
    # Normalize row length to header length for consistent output.
    row_values = list(row[:len(headers)]) + [None] * max(0, len(headers) - len(row))
    owner_value = row_values[owner_idx]
    if owner_value is None or str(owner_value).strip() == '':
        group_owner = 'Unassigned'
    else:
        group_owner = owner_value
    groups.setdefault(group_owner, []).append(row_values)

invalid_sheet_chars = re.compile(r'[\\/*?:\[\]]')
used_sheet_names = {'Summary'}

def legal_sheet_name(owner):
    text = str(owner) if owner is not None else 'Unassigned'
    text = invalid_sheet_chars.sub('_', text).strip()
    # Excel also dislikes empty sheet names and sheet names over 31 chars.
    if not text:
        text = 'Unassigned'
    # Avoid apostrophe-only edge cases and reserved Summary collision.
    base = text[:31]
    if not base:
        base = 'Sheet'
    candidate = base
    suffix_num = 1
    while candidate in used_sheet_names:
        suffix = f'_{suffix_num}'
        candidate = base[:31-len(suffix)] + suffix
        suffix_num += 1
    used_sheet_names.add(candidate)
    return candidate

sheet_for_owner = OrderedDict((owner, legal_sheet_name(owner)) for owner in groups.keys())

# Build output workbook
out_wb = Workbook()
summary_ws = out_wb.active
summary_ws.title = 'Summary'
summary_headers = ['Owner', 'SheetName', 'Total', 'Pass', 'Fail']
summary_ws.append(summary_headers)

for owner, group_rows in groups.items():
    sheet_name = sheet_for_owner[owner]
    ws = out_wb.create_sheet(title=sheet_name)
    ws.append(headers)
    total = len(group_rows)
    pass_count = 0
    fail_count = 0
    for row_values in group_rows:
        status = row_values[status_idx]
        if status == 'Pass':
            pass_count += 1
        elif status == 'Fail':
            fail_count += 1
        ws.append(row_values)
    summary_ws.append([owner, sheet_name, total, pass_count, fail_count])

out_wb.save(output_path)
src_wb.close()
out_wb.close()

# Verification: reopen saved output and check requirements from the produced file.
check_wb = load_workbook(output_path, data_only=False)
errors = []
if 'Summary' not in check_wb.sheetnames:
    errors.append('Missing Summary worksheet')
else:
    sws = check_wb['Summary']
    got_summary_headers = [c.value for c in sws[1]]
    if got_summary_headers != summary_headers:
        errors.append(f'Summary headers mismatch: {got_summary_headers}')
    summary_rows = list(sws.iter_rows(min_row=2, values_only=True))
    if len(summary_rows) != len(groups):
        errors.append(f'Summary row count {len(summary_rows)} != group count {len(groups)}')
    for owner, sheet_name, total, pass_count, fail_count in summary_rows:
        if sheet_name not in check_wb.sheetnames:
            errors.append(f'Summary sheet name {sheet_name!r} not found')
            continue
        if len(str(sheet_name)) > 31 or invalid_sheet_chars.search(str(sheet_name)):
            errors.append(f'Illegal sheet name in output: {sheet_name!r}')
        ws = check_wb[sheet_name]
        got_headers = [c.value for c in ws[1]]
        if got_headers != headers:
            errors.append(f'{sheet_name} headers changed: {got_headers}')
        data_rows = list(ws.iter_rows(min_row=2, values_only=True))
        if len(data_rows) != total:
            errors.append(f'{sheet_name} total mismatch: data rows {len(data_rows)} vs Summary {total}')
        data_pass = sum(1 for r in data_rows if r[status_idx] == 'Pass')
        data_fail = sum(1 for r in data_rows if r[status_idx] == 'Fail')
        if data_pass != pass_count or data_fail != fail_count:
            errors.append(f'{sheet_name} status counts mismatch')
        # Check rows belong to the owner group while preserving original Owner cells.
        for r in data_rows:
            original_owner = r[owner_idx]
            expected_group = 'Unassigned' if original_owner is None or str(original_owner).strip() == '' else original_owner
            if expected_group != owner:
                errors.append(f'{sheet_name} has row for owner {original_owner!r}, expected group {owner!r}')
                break
# Check all source data rows copied exactly once.
source_data_count = len(rows) - 1
group_sheet_data_count = 0
for name in check_wb.sheetnames:
    if name != 'Summary':
        group_sheet_data_count += max(0, check_wb[name].max_row - 1)
if group_sheet_data_count != source_data_count:
    errors.append(f'Total copied row count {group_sheet_data_count} != source rows {source_data_count}')
if len(set(check_wb.sheetnames)) != len(check_wb.sheetnames):
    errors.append('Duplicate worksheet names detected')

print('created:', output_path)
print('output sheets:', check_wb.sheetnames)
if 'Summary' in check_wb.sheetnames:
    print('Summary rows:')
    for row in check_wb['Summary'].iter_rows(values_only=True):
        print(row)
print('checked requirements: output file exists; Summary headers Owner/SheetName/Total/Pass/Fail; legal unique sheet names; source headers preserved on group sheets; blank Owner grouped as Unassigned; original Owner cell values preserved in copied rows; Pass/Fail counts and row counts match saved workbook.')
check_wb.close()
if errors:
    raise AssertionError('\n'.join(errors))