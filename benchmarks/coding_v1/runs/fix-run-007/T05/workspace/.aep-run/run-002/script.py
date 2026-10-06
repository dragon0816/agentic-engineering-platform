from pathlib import Path
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font

base = Path.cwd()
input_dir = base / 'input'
output_dir = base / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
out_path = output_dir / 'merged.xlsx'

DEV_FILE = input_dir / 'devices.xlsx'
TEST_FILE = input_dir / 'tests.xlsx'
KEY = 'Device ID'


def read_first_sheet(path):
    wb = load_workbook(path, data_only=True, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        raise ValueError(f'{path.name} is empty')
    headers = [str(v).strip() if v is not None else '' for v in rows[0]]
    if KEY not in headers:
        raise ValueError(f'{path.name} missing {KEY!r} column; headers={headers}')
    records = []
    for row in rows[1:]:
        # Skip completely empty rows
        if row is None or all(v is None for v in row):
            continue
        rec = {}
        for i, h in enumerate(headers):
            v = row[i] if i < len(row) else None
            if h == KEY:
                rec[h] = '' if v is None else str(v)
            else:
                rec[h] = v
        records.append(rec)
    return headers, records


def write_sheet(wb, title, headers, records):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for rec in records:
        ws.append([rec.get(h, None) for h in headers])
    # Device ID and Source as text; preserve all textual IDs including leading zeroes
    for col_idx, header in enumerate(headers, start=1):
        if header in (KEY, 'Source'):
            for row_idx in range(1, ws.max_row + 1):
                ws.cell(row_idx, col_idx).number_format = '@'
    # Basic width
    for col_idx, header in enumerate(headers, start=1):
        max_len = len(str(header))
        for row_idx in range(2, ws.max_row + 1):
            val = ws.cell(row_idx, col_idx).value
            max_len = max(max_len, len(str(val)) if val is not None else 0)
        ws.column_dimensions[ws.cell(1, col_idx).column_letter].width = min(max_len + 2, 40)


dev_headers, devices = read_first_sheet(DEV_FILE)
test_headers, tests = read_first_sheet(TEST_FILE)

# Validate devices uniqueness as stated; fail visibly if violated.
seen = set()
dupes = []
for d in devices:
    did = d[KEY]
    if did in seen:
        dupes.append(did)
    seen.add(did)
if dupes:
    raise ValueError(f'devices contains duplicate Device ID values: {dupes}')

devices_by_id = {d[KEY]: d for d in devices}
tests_by_id = {}
for t in tests:
    tests_by_id.setdefault(t[KEY], []).append(t)

matched_records = []
for t in tests:
    did = t[KEY]
    if did in devices_by_id:
        rec = {}
        # One ID column, then all non-key test fields, then all non-key device fields.
        rec[KEY] = did
        for h in test_headers:
            if h != KEY:
                rec[h] = t.get(h)
        for h in dev_headers:
            if h != KEY:
                rec[h] = devices_by_id[did].get(h)
        matched_records.append(rec)

unmatched_records = []
# Devices with no matching tests
for d in devices:
    did = d[KEY]
    if did not in tests_by_id:
        rec = {'Source': 'devices', KEY: did}
        for h in test_headers:
            if h != KEY:
                rec[h] = None
        for h in dev_headers:
            if h != KEY:
                rec[h] = d.get(h)
        unmatched_records.append(rec)
# Tests with no matching device; tests may have repeated unmatched IDs, keep every test row
for t in tests:
    did = t[KEY]
    if did not in devices_by_id:
        rec = {'Source': 'tests', KEY: did}
        for h in test_headers:
            if h != KEY:
                rec[h] = t.get(h)
        for h in dev_headers:
            if h != KEY:
                rec[h] = None
        unmatched_records.append(rec)

matched_headers = [KEY] + [h for h in test_headers if h != KEY] + [h for h in dev_headers if h != KEY]
unmatched_headers = ['Source'] + matched_headers

wb = Workbook()
# Remove default sheet
ws_default = wb.active
wb.remove(ws_default)
write_sheet(wb, 'matched', matched_headers, matched_records)
write_sheet(wb, 'unmatched', unmatched_headers, unmatched_records)
wb.save(out_path)

print('Wrote:', out_path)
print('Devices rows:', len(devices), 'Tests rows:', len(tests))
print('Matched rows:', len(matched_records), 'Unmatched rows:', len(unmatched_records))
print('Matched headers:', matched_headers)
print('Unmatched headers:', unmatched_headers)

# Verification: reopen output and assert stated requirements.
check_wb = load_workbook(out_path, data_only=False)
assert set(check_wb.sheetnames) == {'matched', 'unmatched'}, check_wb.sheetnames
mws = check_wb['matched']
uws = check_wb['unmatched']
assert [c.value for c in mws[1]] == matched_headers
assert [c.value for c in uws[1]] == unmatched_headers
assert mws.max_row - 1 == 3, f'matched row count {mws.max_row - 1}'
assert uws.max_row - 1 == 2, f'unmatched row count {uws.max_row - 1}'
# Device ID values are text strings and leading zeros are preserved.
matched_ids = [mws.cell(r, 1).value for r in range(2, mws.max_row + 1)]
unmatched_ids = [uws.cell(r, 2).value for r in range(2, uws.max_row + 1)]
assert matched_ids == ['001', '001', '002'], matched_ids
assert unmatched_ids == ['003', '999'], unmatched_ids
assert all(isinstance(v, str) for v in matched_ids + unmatched_ids)
assert [uws.cell(r, 1).value for r in range(2, uws.max_row + 1)] == ['devices', 'tests']
# Confirm matched contains test and device columns with expected values.
matched_rows = [[mws.cell(r, c).value for c in range(1, mws.max_column + 1)] for r in range(2, mws.max_row + 1)]
unmatched_rows = [[uws.cell(r, c).value for c in range(1, uws.max_column + 1)] for r in range(2, uws.max_row + 1)]
print('Verified sheets, headers, row counts, text IDs, leading zeros, Source labels.')
print('Matched rows:', matched_rows)
print('Unmatched rows:', unmatched_rows)
check_wb.close()