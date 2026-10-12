import csv, json, os
from pathlib import Path
from openpyxl import load_workbook

root = Path.cwd()
out = root / 'output'
print('workspace=', root)
print('output_exists=', out.exists())
print('output_files=')
for p in sorted(out.rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(root), p.stat().st_size)

expected_aug = [
    'sap_orders_2026-08.csv',
    'sap_invoices_2026-08.csv',
    'expenses_2026-08_approved.csv',
    'quotes_2026-08_accepted.json',
    'project_integration_2026-08.xlsx',
]
expected_sep = [
    'sap_orders_2026-09.csv',
    'sap_invoices_2026-09.csv',
    'expenses_2026-09_approved.csv',
    'quotes_2026-09_accepted.json',
    'project_integration_2026-09.xlsx',
]

report = {'august': {}, 'september_still_present': {}, 'checks': []}

def check_file(name):
    p = out / name
    exists = p.exists()
    size = p.stat().st_size if exists else 0
    return p, exists, size

for name in expected_aug:
    p, exists, size = check_file(name)
    info = {'exists': exists, 'size': size, 'nonempty': exists and size > 0}
    if not info['nonempty']:
        raise AssertionError(f'Missing or empty August output: {name}')
    if name.endswith('.csv'):
        with p.open('r', newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            info['columns'] = reader.fieldnames
            info['rows'] = len(rows)
            info['sample'] = rows[:2]
    elif name.endswith('.json'):
        data = json.loads(p.read_text(encoding='utf-8'))
        info['keys'] = list(data.keys())
        info['count'] = data.get('count')
        info['items_len'] = len(data.get('items', [])) if isinstance(data.get('items'), list) else None
    elif name.endswith('.xlsx'):
        wb = load_workbook(p, data_only=False, read_only=False)
        info['sheets'] = wb.sheetnames
        # count non-empty data rows for key sheets (header excluded where present)
        sheet_counts = {}
        for ws_name in wb.sheetnames:
            ws = wb[ws_name]
            nonempty_rows = 0
            for row in ws.iter_rows(values_only=True):
                if any(v is not None and v != '' for v in row):
                    nonempty_rows += 1
            sheet_counts[ws_name] = nonempty_rows
        info['nonempty_rows_by_sheet'] = sheet_counts
        wb.close()
    report['august'][name] = info

for name in expected_sep:
    p, exists, size = check_file(name)
    info = {'exists': exists, 'size': size, 'nonempty': exists and size > 0}
    if not info['nonempty']:
        raise AssertionError(f'September file missing after August rerun: {name}')
    report['september_still_present'][name] = info

# Assert expected August row counts from workflow output.
expected_rows = {
    'sap_orders_2026-08.csv': 7,
    'sap_invoices_2026-08.csv': 6,
    'expenses_2026-08_approved.csv': 4,
}
for name, expected_count in expected_rows.items():
    actual = report['august'][name]['rows']
    if actual != expected_count:
        raise AssertionError(f'{name}: expected {expected_count} rows, got {actual}')

q = report['august']['quotes_2026-08_accepted.json']
if q.get('count') != 4 or q.get('items_len') != 4:
    raise AssertionError(f'quotes_2026-08_accepted.json expected count/items_len 4, got {q}')

xlsx_info = report['august']['project_integration_2026-08.xlsx']
required_sheets = ['Report', 'Orders', 'Invoices', 'Expenses', 'Quotes', 'Summary', 'Exceptions', 'Instructions']
missing_sheets = [s for s in required_sheets if s not in xlsx_info['sheets']]
if missing_sheets:
    raise AssertionError(f'Workbook missing sheets: {missing_sheets}')

print('\nCHECK_REPORT_JSON=')
print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
print('\nRESULT: all August deliverables verified, and September deliverables still present.')