from pathlib import Path
import csv, json, os
from openpyxl import load_workbook

ws = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\runs\fix-005\X02\workspace')
out = ws/'output'
print('WORKSPACE', ws)
print('OUTPUT_EXISTS', out.exists())
print('OUTPUT_FILES')
for p in sorted(out.rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(ws), p.stat().st_size)

report = out/'project_C001_2026-09_report.xlsx'
if not report.exists():
    raise SystemExit('Missing report workbook')

wb = load_workbook(report, data_only=False)
print('WORKBOOK_SHEETS', wb.sheetnames)
expected_sheets = ['Summary','Orders','Invoices','Expenses','Quotes','Exceptions']
missing = [s for s in expected_sheets if s not in wb.sheetnames]
if missing:
    raise SystemExit(f'Missing sheets: {missing}')

for s in expected_sheets:
    sh = wb[s]
    headers = [sh.cell(1,c).value for c in range(1, sh.max_column+1)]
    rows = sh.max_row - 1
    print(f'SHEET {s}: rows={rows}, cols={sh.max_column}, headers={headers}')

# Verify key files are readable and counts match workbook where applicable.
def csv_count(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return sum(1 for _ in csv.DictReader(f))

files = {
    'orders': out/'downloads'/'orders_C001_2026-09.csv',
    'invoices': out/'downloads'/'invoices_C001_2026-09.csv',
    'expenses_p001': out/'expenses_P001_2026-09.csv',
    'expenses_p003': out/'expenses_P003_2026-09.csv',
    'quotes_csv': out/'quotes_C001_2026-09.csv',
    'quotes_json': out/'quotes_C001_2026-09.json',
}
for name, path in files.items():
    print('FILE_CHECK', name, path.exists(), path.stat().st_size if path.exists() else None)
    if not path.exists():
        raise SystemExit(f'Missing file: {path}')

orders_n = csv_count(files['orders'])
invoices_n = csv_count(files['invoices'])
expenses_n = csv_count(files['expenses_p001']) + csv_count(files['expenses_p003'])
quotes_n = csv_count(files['quotes_csv'])
print('SOURCE_COUNTS', {'orders': orders_n, 'invoices': invoices_n, 'expenses': expenses_n, 'quotes': quotes_n})

sheet_counts = {s: wb[s].max_row - 1 for s in ['Orders','Invoices','Expenses','Quotes']}
print('WORKBOOK_COUNTS', sheet_counts)
assert sheet_counts['Orders'] == orders_n, 'Orders count mismatch'
assert sheet_counts['Invoices'] == invoices_n, 'Invoices count mismatch'
assert sheet_counts['Expenses'] == expenses_n, 'Expenses count mismatch'
assert sheet_counts['Quotes'] == quotes_n, 'Quotes count mismatch'

# Spot-check ID cells as text where sheets have ID columns.
for s in ['Orders','Invoices','Expenses','Quotes']:
    sh = wb[s]
    headers = [sh.cell(1,c).value for c in range(1, sh.max_column+1)]
    id_cols = [i+1 for i,h in enumerate(headers) if h and str(h).lower().endswith('id')]
    for c in id_cols:
        for r in range(2, min(sh.max_row, 5)+1):
            v = sh.cell(r,c).value
            if v is not None and not isinstance(v, str):
                raise AssertionError(f'{s} {headers[c-1]} row {r} is not text: {v!r}')
print('ID_TEXT_CHECK passed')

# Exceptions should not be empty and attention rows should have yellow fill in detail sheets if present.
exc_rows = wb['Exceptions'].max_row - 1
print('EXCEPTIONS_ROWS', exc_rows)
if exc_rows <= 0:
    raise AssertionError('Exceptions sheet is empty')

print('CHECK_COMPLETE report and source exports are readable and internally consistent')