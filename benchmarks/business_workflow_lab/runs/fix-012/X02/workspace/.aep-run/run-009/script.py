import os, json
from pathlib import Path
from datetime import datetime
from openpyxl import load_workbook

ws = Path.cwd()
input_dir = ws/'input'
out = ws/'output'
print('workspace=', ws)
print('input files=', sorted(p.name for p in input_dir.glob('*')))
print('output files=')
for p in sorted(out.rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(ws), 'bytes=', p.stat().st_size, 'mtime=', datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec='seconds'))

# Files produced by the approved workflow run use date range in file names.
report = out/'project_report_C001_2026-09-01_2026-09-30.xlsx'
quotes_json = out/'quotes_C001_2026-09-01_2026-09-30.json'
orders_export = out/'downloads'/'sap_orders_export.csv'
invoices_export = out/'downloads'/'sap_invoices_export.csv'
expenses_export = out/'expenses_all_approved_export.csv'

checks = []
errors = []

def add_check(name, ok, detail):
    checks.append({'check': name, 'ok': bool(ok), 'detail': detail})
    print(('PASS' if ok else 'FAIL'), name, detail)
    if not ok:
        errors.append(f'{name}: {detail}')

for label, path in [('report', report), ('quotes_json', quotes_json), ('orders_export', orders_export), ('invoices_export', invoices_export), ('expenses_export', expenses_export)]:
    add_check(f'{label}_exists_nonempty', path.exists() and path.stat().st_size > 0, f'{path} bytes={path.stat().st_size if path.exists() else "missing"}')

if report.exists():
    wb = load_workbook(report, data_only=False)
    print('workbook_sheets=', wb.sheetnames)
    expected_sheets = ['Report','Orders','Invoices','Expenses','Quotes','Summary','Exceptions','Instructions']
    add_check('expected_sheets_present', all(s in wb.sheetnames for s in expected_sheets), wb.sheetnames)

    def find_header(sheet_name, required_first=None):
        sh = wb[sheet_name]
        for r in range(1, min(sh.max_row, 25)+1):
            vals = [sh.cell(r,c).value for c in range(1, sh.max_column+1)]
            if required_first and vals and vals[0] == required_first:
                last = max(i for i,v in enumerate(vals, start=1) if v is not None)
                return r, vals[:last]
            if not required_first and sum(v is not None for v in vals) >= 2:
                last = max(i for i,v in enumerate(vals, start=1) if v is not None)
                return r, vals[:last]
        return None, []

    def rows_with_header(sheet_name, required_first=None):
        sh = wb[sheet_name]
        hr, headers = find_header(sheet_name, required_first)
        if hr is None:
            return [], []
        data = []
        for r in range(hr+1, sh.max_row+1):
            vals = [sh.cell(r,c).value for c in range(1, len(headers)+1)]
            if any(v is not None for v in vals):
                data.append(dict(zip(headers, vals)))
        return headers, data

    sheet_header_first = {
        'Orders': 'OrderID',
        'Invoices': 'InvoiceID',
        'Expenses': 'ExpenseID',
        'Quotes': 'QuoteID',
        'Exceptions': 'Source',
        'Summary': 'ProjectID',
    }
    data_by_sheet = {}
    for s in ['Orders','Invoices','Expenses','Quotes','Exceptions','Summary']:
        h, data = rows_with_header(s, sheet_header_first[s])
        data_by_sheet[s] = data
        print(f'{s}: headers={h} rows={len(data)} sample={data[:2]}')

    add_check('orders_count', len(data_by_sheet['Orders']) == 3, len(data_by_sheet['Orders']))
    add_check('invoices_count', len(data_by_sheet['Invoices']) == 3, len(data_by_sheet['Invoices']))
    add_check('expenses_count', len(data_by_sheet['Expenses']) == 9, len(data_by_sheet['Expenses']))
    add_check('quotes_count_all_retained', len(data_by_sheet['Quotes']) == 4, len(data_by_sheet['Quotes']))
    add_check('exceptions_count', len(data_by_sheet['Exceptions']) == 4, len(data_by_sheet['Exceptions']))

    orders = data_by_sheet['Orders']
    invoices = data_by_sheet['Invoices']
    expenses = data_by_sheet['Expenses']
    quotes = data_by_sheet['Quotes']
    exceptions = data_by_sheet['Exceptions']
    summary = data_by_sheet['Summary']

    add_check('orders_exclude_cancelled', all(str(r.get('Status') or '') != 'Cancelled' for r in orders), sorted(set(str(r.get('Status')) for r in orders)))
    add_check('orders_customer_scope', all(str(r.get('CustomerID')) == 'C001' for r in orders), sorted(set(str(r.get('CustomerID')) for r in orders)))
    add_check('invoices_customer_scope', all(str(r.get('CustomerID')) == 'C001' for r in invoices), sorted(set(str(r.get('CustomerID')) for r in invoices)))
    add_check('expenses_approved_only', all(str(r.get('Status') or '') == 'Approved' for r in expenses), sorted(set(str(r.get('Status')) for r in expenses)))
    add_check('expenses_project_scope', all(str(r.get('ProjectID')) in {'P001','P003'} for r in expenses), sorted(set(str(r.get('ProjectID')) for r in expenses)))
    add_check('quotes_customer_scope', all(str(r.get('CustomerID')) == 'C001' for r in quotes), sorted(set(str(r.get('CustomerID')) for r in quotes)))

    # Confirm C001 projects summarized
    add_check('summary_projects', sorted(str(r.get('ProjectID')) for r in summary if str(r.get('ProjectID')).startswith('P')) == ['P001','P003'], summary)

    # Check ID fields are strings in workbook rows.
    id_text = []
    id_text_ok = True
    for sheet, col in [('Orders','OrderID'),('Invoices','InvoiceID'),('Expenses','ExpenseID'),('Quotes','QuoteID'),('Exceptions','DocumentID')]:
        for r in data_by_sheet[sheet]:
            v = r.get(col)
            if v is not None:
                id_text.append((sheet, col, v, type(v).__name__))
                if not isinstance(v, str):
                    id_text_ok = False
                break
    add_check('id_fields_are_text', id_text_ok, id_text)

    # TWD values numeric (or formulas in Summary totals) and two-decimal-compatible.
    twd_ok = True
    twd_samples = []
    for sheet in ['Orders','Invoices','Expenses','Quotes','Summary']:
        for r in data_by_sheet[sheet]:
            for k, v in r.items():
                if k and 'TWD' in str(k).upper():
                    twd_samples.append((sheet, k, v, type(v).__name__))
                    if v is not None and not isinstance(v, (int, float)) and not (isinstance(v, str) and v.startswith('=')):
                        twd_ok = False
    add_check('twd_amounts_numeric_or_formula', twd_ok, twd_samples[:30])

    # Requested attention conditions
    exc_text = '\n'.join(json.dumps(r, ensure_ascii=False, default=str) for r in exceptions)
    expected_exc = ['0090000219','EXP-00006','Q0010','Q0014']
    add_check('expected_exception_items', all(x in exc_text for x in expected_exc), exc_text)
    add_check('invoice_exception_reason', 'Overdue unpaid invoice as of 2026-09-30' in exc_text and '386445.00 TWD' in exc_text, exc_text)
    add_check('expense_exception_reason', 'Approved expense missing receipt' in exc_text, exc_text)
    add_check('quote_exception_reason', 'ValidUntil before 2026-09-30 and status is not Accepted' in exc_text, exc_text)

if quotes_json.exists():
    with open(quotes_json, encoding='utf-8') as f:
        q = json.load(f)
    print('quotes_json_type=', type(q).__name__, 'len=', len(q) if isinstance(q, list) else 'n/a', 'sample=', q[:2] if isinstance(q,list) else q)
    add_check('quotes_json_four_records', isinstance(q, list) and len(q) == 4, len(q) if isinstance(q, list) else type(q).__name__)
    add_check('quotes_json_customer_scope', isinstance(q, list) and all(str(r.get('CustomerID')) == 'C001' for r in q), sorted(set(str(r.get('CustomerID')) for r in q)) if isinstance(q, list) else 'not list')

print('CHECKS_JSON=', json.dumps(checks, ensure_ascii=False, indent=2, default=str))
if errors:
    print('ERRORS=', json.dumps(errors, ensure_ascii=False, indent=2))
    raise SystemExit(1)
print('All verification checks passed.')