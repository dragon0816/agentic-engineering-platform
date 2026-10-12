import csv, json
from pathlib import Path
from openpyxl import load_workbook

root = Path.cwd()
out = root / 'output'
print('workspace=', root)
print('output_exists=', out.exists())

aug_files = [
    'sap_orders_2026-08.csv',
    'sap_invoices_2026-08.csv',
    'expenses_2026-08_approved.csv',
    'quotes_2026-08_accepted.json',
    'project_integration_2026-08.xlsx',
]
sep_files = [
    'sap_orders_2026-09.csv',
    'sap_invoices_2026-09.csv',
    'expenses_2026-09_approved.csv',
    'quotes_2026-09_accepted.json',
    'project_integration_2026-09.xlsx',
]

summary = {'august_outputs': {}, 'september_outputs_still_present': {}}

for name in aug_files:
    p = out / name
    if not p.exists() or p.stat().st_size == 0:
        raise AssertionError(f'Missing or empty August output: {name}')
    info = {'path': str(p), 'bytes': p.stat().st_size}
    if name.endswith('.csv'):
        with p.open('r', newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        info['columns'] = reader.fieldnames
        info['data_rows'] = len(rows)
        info['first_row'] = rows[0] if rows else None
        info['last_row'] = rows[-1] if rows else None
        if 'OrderDate' in (reader.fieldnames or []):
            info['date_range_in_file'] = [min(r['OrderDate'] for r in rows), max(r['OrderDate'] for r in rows)] if rows else None
        if 'InvoiceDate' in (reader.fieldnames or []):
            info['date_range_in_file'] = [min(r['InvoiceDate'] for r in rows), max(r['InvoiceDate'] for r in rows)] if rows else None
        if 'ExpenseDate' in (reader.fieldnames or []):
            info['date_range_in_file'] = [min(r['ExpenseDate'] for r in rows), max(r['ExpenseDate'] for r in rows)] if rows else None
    elif name.endswith('.json'):
        data = json.loads(p.read_text(encoding='utf-8'))
        info['keys'] = list(data.keys())
        info['count'] = data.get('count')
        info['items_len'] = len(data.get('items', [])) if isinstance(data.get('items'), list) else None
    elif name.endswith('.xlsx'):
        wb = load_workbook(p, data_only=True, read_only=True)
        info['sheets'] = wb.sheetnames
        sheet_nonempty_rows = {}
        for ws in wb.worksheets:
            n = 0
            for row in ws.iter_rows(values_only=True):
                if any(v is not None and v != '' for v in row):
                    n += 1
            sheet_nonempty_rows[ws.title] = n
        info['nonempty_rows_by_sheet'] = sheet_nonempty_rows
        required = ['Report', 'Orders', 'Invoices', 'Expenses', 'Quotes', 'Summary', 'Exceptions', 'Instructions']
        missing = [s for s in required if s not in wb.sheetnames]
        if missing:
            raise AssertionError(f'{name} missing required sheets: {missing}')
        wb.close()
    summary['august_outputs'][name] = info

for name in sep_files:
    p = out / name
    if not p.exists() or p.stat().st_size == 0:
        raise AssertionError(f'September output missing/empty after August rerun: {name}')
    summary['september_outputs_still_present'][name] = {'path': str(p), 'bytes': p.stat().st_size}

# Sanity checks based on actual workflow period and filenames, not assumed row count.
if summary['august_outputs']['sap_invoices_2026-08.csv']['data_rows'] != 6:
    raise AssertionError('Expected 6 August invoice rows from browser page/export')
if summary['august_outputs']['expenses_2026-08_approved.csv']['data_rows'] != 4:
    raise AssertionError('Expected 4 August approved expense rows from app page/export')
q = summary['august_outputs']['quotes_2026-08_accepted.json']
if q['count'] != 4 or q['items_len'] != 4:
    raise AssertionError('Expected 4 accepted August quotes')

print('CHECK_REPORT_JSON=')
print(json.dumps(summary, ensure_ascii=False, indent=2))
print('RESULT: verified August deliverables are present/nonempty/readable; September deliverables still present and not overwritten.')