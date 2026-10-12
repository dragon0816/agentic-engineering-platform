from pathlib import Path
from openpyxl import load_workbook, Workbook

base = Path.cwd()
input_dir = base / 'input'
output_dir = base / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / 'merged_devices_tests.xlsx'

DEVICES_FILE = input_dir / 'devices.xlsx'
TESTS_FILE = input_dir / 'tests.xlsx'
ID_COL = 'Device ID'


def load_sheet_records(path: Path):
    wb = load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    headers = [str(c.value).strip() if c.value is not None else '' for c in ws[1]]
    records = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        # Skip completely empty rows.
        if all(v is None for v in row):
            continue
        rec = {}
        for h, v in zip(headers, row):
            if h == ID_COL and v is not None:
                # Treat IDs as text. str() preserves leading zeroes already present in Excel text cells.
                rec[h] = str(v)
            else:
                rec[h] = v
        records.append(rec)
    wb.close()
    return headers, records


dev_headers, devices = load_sheet_records(DEVICES_FILE)
test_headers, tests = load_sheet_records(TESTS_FILE)

if ID_COL not in dev_headers:
    raise ValueError(f'{DEVICES_FILE.name} missing required column {ID_COL!r}')
if ID_COL not in test_headers:
    raise ValueError(f'{TESTS_FILE.name} missing required column {ID_COL!r}')

# Validate stated condition: devices has unique IDs.
seen = set()
dups = []
for rec in devices:
    did = rec.get(ID_COL)
    if did in seen:
        dups.append(did)
    seen.add(did)
if dups:
    raise ValueError(f'devices.xlsx has duplicate Device ID values: {dups}')

device_by_id = {rec.get(ID_COL): rec for rec in devices}
test_ids = {rec.get(ID_COL) for rec in tests}

# matched: one row per successful test-to-device match.
matched_headers = list(test_headers) + [h for h in dev_headers if h != ID_COL]
matched_rows = []
matched_device_ids = set()
for test in tests:
    tid = test.get(ID_COL)
    dev = device_by_id.get(tid)
    if dev is not None:
        matched_device_ids.add(tid)
        row = []
        for h in test_headers:
            row.append(test.get(h))
        for h in dev_headers:
            if h != ID_COL:
                row.append(dev.get(h))
        matched_rows.append(row)

# unmatched: devices with no matching test ID, and tests with no matching device ID.
unmatched_headers = ['Source'] + list(test_headers) + [h for h in dev_headers if h != ID_COL]
unmatched_rows = []
for dev in devices:
    did = dev.get(ID_COL)
    if did not in test_ids:
        row = ['devices']
        for h in test_headers:
            if h == ID_COL:
                row.append(dev.get(ID_COL))
            else:
                row.append(None)
        for h in dev_headers:
            if h != ID_COL:
                row.append(dev.get(h))
        unmatched_rows.append(row)

for test in tests:
    tid = test.get(ID_COL)
    if tid not in device_by_id:
        row = ['tests']
        for h in test_headers:
            row.append(test.get(h))
        for h in dev_headers:
            if h != ID_COL:
                row.append(None)
        unmatched_rows.append(row)

wb_out = Workbook()
ws_m = wb_out.active
ws_m.title = 'matched'
ws_m.append(matched_headers)
for row in matched_rows:
    ws_m.append(row)

ws_u = wb_out.create_sheet('unmatched')
ws_u.append(unmatched_headers)
for row in unmatched_rows:
    ws_u.append(row)

# Make Device ID cells explicit text in both sheets.
def force_id_text(ws):
    header_map = {cell.value: idx for idx, cell in enumerate(ws[1], start=1)}
    col_idx = header_map.get(ID_COL)
    if col_idx:
        for row_idx in range(2, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value is not None:
                cell.value = str(cell.value)
                cell.number_format = '@'

force_id_text(ws_m)
force_id_text(ws_u)

# Simple readable widths.
for ws in [ws_m, ws_u]:
    for col in ws.columns:
        max_len = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 2, 10), 40)

wb_out.save(output_file)
print('Wrote:', output_file)
print('matched headers:', matched_headers)
print('matched data rows:', len(matched_rows))
print('unmatched headers:', unmatched_headers)
print('unmatched data rows:', len(unmatched_rows))
print('unmatched sources:', [r[0] for r in unmatched_rows])

# Verification: reopen output and confirm requirements.
check_wb = load_workbook(output_file, data_only=False)
assert check_wb.sheetnames == ['matched', 'unmatched'], check_wb.sheetnames
cm = check_wb['matched']
cu = check_wb['unmatched']
assert [c.value for c in cm[1]] == matched_headers
assert [c.value for c in cu[1]] == unmatched_headers
assert cm.max_row - 1 == len(matched_rows)
assert cu.max_row - 1 == len(unmatched_rows)
assert cu.cell(row=1, column=1).value == 'Source'
# ID text and leading zero checks.
for ws in [cm, cu]:
    id_col = [c.value for c in ws[1]].index(ID_COL) + 1
    for r in range(2, ws.max_row + 1):
        v = ws.cell(r, id_col).value
        if v is not None:
            assert isinstance(v, str), (ws.title, r, v, type(v))
            assert ws.cell(r, id_col).number_format == '@', (ws.title, r, ws.cell(r, id_col).number_format)
# Expected IDs based on input sample and merge logic.
matched_ids = [cm.cell(r, 1).value for r in range(2, cm.max_row + 1)]
unmatched_sources_ids = [(cu.cell(r, 1).value, cu.cell(r, 2).value) for r in range(2, cu.max_row + 1)]
print('check matched IDs:', matched_ids)
print('check unmatched Source/Device ID:', unmatched_sources_ids)
print('verification: output reopened; sheets, headers, row counts, Source values, and text Device ID cells confirmed')
check_wb.close()
