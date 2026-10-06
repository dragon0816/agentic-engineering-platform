from pathlib import Path
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / 'merged_device_tests.xlsx'

ID_COL = 'Device ID'

def cell_to_text(v):
    if v is None:
        return ''
    # Preserve text IDs exactly as Excel/openpyxl provides them. If an ID was numeric,
    # convert it without decimal artifacts.
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)

def read_sheet(path, sheet_name):
    wb = load_workbook(path, data_only=True)
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return [], []
    headers = [cell_to_text(h) for h in rows[0]]
    data = []
    for row in rows[1:]:
        if row is None or all(v is None for v in row):
            continue
        rec = {}
        for i, h in enumerate(headers):
            val = row[i] if i < len(row) else None
            rec[h] = cell_to_text(val) if h == ID_COL else val
        if ID_COL in rec:
            rec[ID_COL] = cell_to_text(rec[ID_COL])
        data.append(rec)
    return headers, data

dev_headers, devices = read_sheet(input_dir / 'devices.xlsx', 'devices')
test_headers, tests = read_sheet(input_dir / 'tests.xlsx', 'tests')

if ID_COL not in dev_headers:
    raise ValueError(f'{ID_COL!r} not found in devices.xlsx')
if ID_COL not in test_headers:
    raise ValueError(f'{ID_COL!r} not found in tests.xlsx')

# devices IDs are expected to be unique. Enforce this to avoid ambiguous joins.
devices_by_id = {}
duplicate_ids = []
for rec in devices:
    did = rec[ID_COL]
    if did in devices_by_id:
        duplicate_ids.append(did)
    devices_by_id[did] = rec
if duplicate_ids:
    raise ValueError('Duplicate Device ID values in devices.xlsx: ' + ', '.join(sorted(set(duplicate_ids))))

matched_rows = []
unmatched_device_ids = set(devices_by_id)
matched_test_count = 0
for test in tests:
    did = test[ID_COL]
    dev = devices_by_id.get(did)
    if dev is not None:
        matched_test_count += 1
        unmatched_device_ids.discard(did)
        # Keep test columns first, then device columns except duplicate Device ID.
        row = {h: test.get(h) for h in test_headers}
        for h in dev_headers:
            if h != ID_COL:
                row[h] = dev.get(h)
        matched_rows.append(row)

unmatched_tests = [test for test in tests if test[ID_COL] not in devices_by_id]
unmatched_devices = [devices_by_id[did] for did in dev_headers and devices_by_id if did in unmatched_device_ids]
# Stable device order from original input.
unmatched_devices = [dev for dev in devices if dev[ID_COL] in unmatched_device_ids]

matched_headers = list(test_headers) + [h for h in dev_headers if h != ID_COL]
unmatched_headers = ['Source'] + list(dev_headers)
for h in test_headers:
    if h not in unmatched_headers:
        unmatched_headers.append(h)

wb = Workbook()
ws_matched = wb.active
ws_matched.title = 'matched'
ws_unmatched = wb.create_sheet('unmatched')

def write_table(ws, headers, rows):
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
    for rec in rows:
        ws.append([rec.get(h, '') for h in headers])
    # Force Device ID column to text to preserve leading zeros.
    for col_idx, h in enumerate(headers, start=1):
        if h == ID_COL:
            for row_idx in range(2, ws.max_row + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.number_format = '@'
                cell.value = cell_to_text(cell.value)
    for col in ws.columns:
        max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max(10, min(max_len + 2, 50))

write_table(ws_matched, matched_headers, matched_rows)

unmatched_rows = []
for dev in unmatched_devices:
    rec = {h: '' for h in unmatched_headers}
    rec['Source'] = 'devices'
    for h in dev_headers:
        rec[h] = dev.get(h, '')
    unmatched_rows.append(rec)
for test in unmatched_tests:
    rec = {h: '' for h in unmatched_headers}
    rec['Source'] = 'tests'
    for h in test_headers:
        rec[h] = test.get(h, '')
    unmatched_rows.append(rec)
write_table(ws_unmatched, unmatched_headers, unmatched_rows)

wb.save(output_file)
print(f'Wrote: {output_file}')
print(f'Devices read: {len(devices)}')
print(f'Tests read: {len(tests)}')
print(f'Matched rows: {len(matched_rows)}')
print(f'Unmatched devices: {len(unmatched_devices)}')
print(f'Unmatched tests: {len(unmatched_tests)}')

# Verification from saved output.
check_wb = load_workbook(output_file, data_only=False)
assert set(['matched', 'unmatched']).issubset(check_wb.sheetnames), check_wb.sheetnames
cm = check_wb['matched']
cu = check_wb['unmatched']
matched_saved_headers = [c.value for c in cm[1]]
unmatched_saved_headers = [c.value for c in cu[1]]
assert matched_saved_headers == matched_headers, (matched_saved_headers, matched_headers)
assert unmatched_saved_headers == unmatched_headers, (unmatched_saved_headers, unmatched_headers)
assert cm.max_row - 1 == matched_test_count, (cm.max_row - 1, matched_test_count)
assert cu.max_row - 1 == len(unmatched_devices) + len(unmatched_tests)
# Check IDs are stored as text strings and expected leading zeros remain.
def col_index(headers, name):
    return headers.index(name) + 1
mid_col = col_index(matched_saved_headers, ID_COL)
uid_col = col_index(unmatched_saved_headers, ID_COL)
matched_ids = [cm.cell(r, mid_col).value for r in range(2, cm.max_row + 1)]
unmatched_ids = [cu.cell(r, uid_col).value for r in range(2, cu.max_row + 1)]
assert all(isinstance(v, str) for v in matched_ids + unmatched_ids), (matched_ids, unmatched_ids)
assert matched_ids == ['001', '001', '002'], matched_ids
assert unmatched_ids == ['003', '999'], unmatched_ids
source_col = col_index(unmatched_saved_headers, 'Source')
sources = [cu.cell(r, source_col).value for r in range(2, cu.max_row + 1)]
assert sources == ['devices', 'tests'], sources
# Ensure matched includes successful corresponding test and device data.
assert matched_saved_headers == ['Device ID', 'Test', 'Result', 'Name', 'Location']
assert unmatched_saved_headers == ['Source', 'Device ID', 'Name', 'Location', 'Test', 'Result']
check_wb.close()
print('Verification passed: output workbook reopened; sheet names, headers, row counts, text Device IDs with leading zeros, Source values, and expected matched/unmatched IDs were checked.')