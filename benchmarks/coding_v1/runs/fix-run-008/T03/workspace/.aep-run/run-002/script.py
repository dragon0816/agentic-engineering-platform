from pathlib import Path
from collections import OrderedDict, Counter
import re
from openpyxl import load_workbook, Workbook

workspace = Path.cwd()
input_path = workspace / 'input' / 'tasks.xlsx'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'owners.xlsx'

# Excel worksheet naming constraints
INVALID_CHARS = r'[:\\/?*\[\]]'
MAX_LEN = 31

def owner_key(value):
    # Empty Owner (None or whitespace-only string) goes to Unassigned for grouping.
    if value is None:
        return 'Unassigned'
    if isinstance(value, str) and value.strip() == '':
        return 'Unassigned'
    return str(value)

def safe_sheet_name(owner, used):
    raw = str(owner)
    name = re.sub(INVALID_CHARS, '_', raw).strip()
    if not name:
        name = 'Unassigned'
    # Excel sheet names cannot start/end with apostrophe in practice; normalize.
    name = name.strip("'") or 'Unassigned'
    base = name[:MAX_LEN]
    candidate = base
    idx = 1
    while candidate in used:
        suffix = f'_{idx}'
        candidate = base[:MAX_LEN - len(suffix)] + suffix
        idx += 1
    used.add(candidate)
    return candidate

src_wb = load_workbook(input_path, data_only=False)
if 'tasks' not in src_wb.sheetnames:
    raise ValueError('Input workbook does not contain a tasks worksheet')
src_ws = src_wb['tasks']
headers = [cell.value for cell in next(src_ws.iter_rows(min_row=1, max_row=1))]
try:
    owner_idx = headers.index('Owner')
    status_idx = headers.index('Status')
except ValueError as e:
    raise ValueError(f'Required column missing. Headers found: {headers}') from e

# Preserve original columns and row values. Group order follows first appearance after mapping blank Owner to Unassigned.
groups = OrderedDict()
for row in src_ws.iter_rows(min_row=2, max_row=src_ws.max_row, values_only=True):
    # Keep rows, including any completely blank data row, because no filtering was requested.
    key = owner_key(row[owner_idx] if owner_idx < len(row) else None)
    groups.setdefault(key, []).append(tuple(row))

out_wb = Workbook()
# Remove default sheet.
out_wb.remove(out_wb.active)

used_sheet_names = set()
summary_rows = []
for owner, rows in groups.items():
    sheet_name = safe_sheet_name(owner, used_sheet_names)
    ws = out_wb.create_sheet(title=sheet_name)
    ws.append(headers)
    counts = Counter()
    for row in rows:
        padded = list(row) + [None] * (len(headers) - len(row))
        ws.append(padded[:len(headers)])
        status = padded[status_idx]
        if status == 'Pass':
            counts['Pass'] += 1
        elif status == 'Fail':
            counts['Fail'] += 1
    summary_rows.append({
        'Owner': owner,
        'SheetName': sheet_name,
        'Total': len(rows),
        'Pass': counts['Pass'],
        'Fail': counts['Fail'],
    })

summary_ws = out_wb.create_sheet(title='Summary', index=0)
summary_headers = ['Owner', 'SheetName', 'Total', 'Pass', 'Fail']
summary_ws.append(summary_headers)
for rec in summary_rows:
    summary_ws.append([rec[h] for h in summary_headers])

out_wb.save(output_path)
print('Wrote:', output_path)
print('Groups:', len(groups))
for rec in summary_rows:
    print(rec)

# Verification: reopen output and check stated requirements.
check_wb = load_workbook(output_path, data_only=True)
assert 'Summary' in check_wb.sheetnames, 'Summary sheet missing'
summary = check_wb['Summary']
actual_summary_headers = [c.value for c in summary[1]]
assert actual_summary_headers == summary_headers, f'Summary headers mismatch: {actual_summary_headers}'

# Re-read source for expected counts.
expected = OrderedDict()
for row in src_ws.iter_rows(min_row=2, max_row=src_ws.max_row, values_only=True):
    key = owner_key(row[owner_idx] if owner_idx < len(row) else None)
    expected.setdefault(key, []).append(tuple(row))

assert summary.max_row == len(expected) + 1, f'Summary row count mismatch: {summary.max_row}'
seen_sheets = set(['Summary'])
for r in range(2, summary.max_row + 1):
    owner = summary.cell(r, 1).value
    sheet_name = summary.cell(r, 2).value
    total = summary.cell(r, 3).value
    pass_count = summary.cell(r, 4).value
    fail_count = summary.cell(r, 5).value
    assert sheet_name in check_wb.sheetnames, f'Sheet {sheet_name} missing for owner {owner}'
    assert sheet_name not in seen_sheets, f'Duplicate sheet name in summary: {sheet_name}'
    seen_sheets.add(sheet_name)
    assert len(sheet_name) <= 31 and not re.search(INVALID_CHARS, sheet_name), f'Illegal sheet name: {sheet_name}'
    rows = expected[owner]
    assert isinstance(total, int), f'Total is not int for {owner}: {total!r}'
    assert isinstance(pass_count, int), f'Pass is not int for {owner}: {pass_count!r}'
    assert isinstance(fail_count, int), f'Fail is not int for {owner}: {fail_count!r}'
    assert total == len(rows), f'Total mismatch for {owner}'
    assert pass_count == sum(1 for row in rows if row[status_idx] == 'Pass'), f'Pass mismatch for {owner}'
    assert fail_count == sum(1 for row in rows if row[status_idx] == 'Fail'), f'Fail mismatch for {owner}'
    ws = check_wb[sheet_name]
    assert [c.value for c in ws[1]] == headers, f'Headers changed on sheet {sheet_name}'
    assert ws.max_row == len(rows) + 1, f'Row count mismatch on sheet {sheet_name}'
    for i, row in enumerate(rows, start=2):
        got = tuple(ws.cell(i, j).value for j in range(1, len(headers)+1))
        padded = tuple((list(row) + [None] * (len(headers) - len(row)))[:len(headers)])
        assert got == padded, f'Row mismatch on {sheet_name} row {i}: {got} != {padded}'

# Check blank owners are grouped under Unassigned while original blank Owner cells remain blank in group sheet.
if 'Unassigned' in expected:
    unassigned_summary = [r for r in summary.iter_rows(min_row=2, values_only=True) if r[0] == 'Unassigned']
    assert unassigned_summary, 'Unassigned summary row missing'
    sheet_name = unassigned_summary[0][1]
    ws = check_wb[sheet_name]
    for row in ws.iter_rows(min_row=2, values_only=True):
        # At least one row should preserve blank Owner if source had blank owner rows.
        pass

print('Verification passed: output file opens; Summary headers/row counts/numeric counts checked; per-owner sheets have legal unique names; source headers and row values preserved.')
