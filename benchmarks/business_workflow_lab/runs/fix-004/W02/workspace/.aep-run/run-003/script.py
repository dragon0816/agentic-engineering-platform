from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Protection
from copy import copy
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
import csv

ws = Path.cwd()
input_xlsx = ws / 'input' / 'sales_template.xlsx'
fx_csv = ws / 'input' / 'fx_rates.csv'
out_dir = ws / 'output'
out_dir.mkdir(exist_ok=True)
out_xlsx = out_dir / 'sales_template.xlsx'

print('Inputs used:', input_xlsx.name, fx_csv.name)

# Load fixed test FX rates (only first two CSV columns are needed; notes may contain commas in the lab file).
rates = {}
with fx_csv.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(row[1])
print('FX rates:', rates)

orders = [
    {'OrderID':'0045000101','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-08-03','Status':'Closed','Currency':'TWD','NetAmount':'95895.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET15'},
    {'OrderID':'0045000107','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P003','OrderDate':'2026-08-27','Status':'Closed','Currency':'USD','NetAmount':'6250.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET30'},
    {'OrderID':'0045000109','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P003','OrderDate':'2026-09-01','Status':'Open','Currency':'TWD','NetAmount':'150000.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET10'},
    {'OrderID':'0045000114','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-09-08','Status':'Cancelled','Currency':'USD','NetAmount':'11956.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET5'},
    {'OrderID':'0045000119','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-09-15','Status':'Open','Currency':'EUR','NetAmount':'8775.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET30'},
    {'OrderID':'0045000125','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-09-25','Status':'Closed','Currency':'TWD','NetAmount':'386445.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET0'},
    {'OrderID':'0045000129','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-10-01','Status':'Open','Currency':'USD','NetAmount':'1602.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET30'},
    {'OrderID':'0045000132','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P003','OrderDate':'2026-10-09','Status':'Open','Currency':'TWD','NetAmount':'50400.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':''},
    {'OrderID':'0045000136','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-10-31','Status':'Open','Currency':'EUR','NetAmount':'2250.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET5'},
]

# Compute TWD amounts with ROUND_HALF_UP to 2 decimals.
for o in orders:
    amount = Decimal(o['NetAmount'])
    rate = rates[o['Currency']]
    o['NetAmountTWD'] = (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

wb = load_workbook(input_xlsx)
report = wb['Report']
details = wb['Details']
summary = wb['Summary']

# Fill report sheet.
generated_at = '2026-10-06T00:00:00+08:00'
report['B3'] = '2026-08-01'
report['D3'] = '2026-10-31'
report['B4'] = 'CustomerID = C001 (exact match); OrderDate 2026-08-01..2026-10-31; Sales Orders only'
report['B5'] = generated_at
report['B7'] = 'Lab ERP Sales Orders list/detail; input/fx_rates.csv'
report['D7'] = generated_at
missing_notes = ['PaymentTerms missing for OrderID 0045000132']
report['B9'] = 'Missing data: ' + '; '.join(missing_notes) + '. Similar-name customer C007 was excluded by exact CustomerID filter.'

# Clear any prior data rows below header in Details and Summary without deleting rows/structure.
def clear_sheet_rows(sh, start_row, max_col):
    for row in sh.iter_rows(min_row=start_row, max_row=sh.max_row, max_col=max_col):
        for cell in row:
            cell.value = None

clear_sheet_rows(details, 5, 11)
clear_sheet_rows(summary, 5, 6)

# Helpers to preserve existing template styles where possible.
def copy_row_style(sh, source_row, target_row, max_col):
    for col in range(1, max_col + 1):
        src = sh.cell(source_row, col)
        dst = sh.cell(target_row, col)
        if src.has_style:
            dst._style = copy(src._style)
        if src.number_format:
            dst.number_format = src.number_format
        if src.alignment:
            dst.alignment = copy(src.alignment)

# Fill Details from row 5.
headers = [details.cell(4, c).value for c in range(1, 12)]
print('Details headers:', headers)
for idx, o in enumerate(orders, start=5):
    copy_row_style(details, 4, idx, 11)
    values = [
        o['OrderID'], o['CustomerID'], o['CustomerName'], o['ProjectID'], o['OrderDate'],
        o['Status'], o['Currency'], float(o['NetAmount']), float(o['NetAmountTWD']),
        o['CustomerContact'], o['PaymentTerms'] if o['PaymentTerms'] else None,
    ]
    for col, value in enumerate(values, start=1):
        details.cell(idx, col).value = value
    # text IDs
    for col in [1,2,4]:
        details.cell(idx, col).number_format = '@'
    details.cell(idx, 5).number_format = 'yyyy-mm-dd'
    for col in [8,9]:
        details.cell(idx, col).number_format = '0.00'

last_detail_row = 4 + len(orders)
summary['B2'] = f'=SUM(Details!I5:I{last_detail_row})' if orders else '=SUM(Details!I5:I5)'

# Summary by Status and Currency. Group=Status, SubGroup blank, Currency=original currency.
summary_rows = []
seen_order = []
acc = {}
for o in orders:
    key = (o['Status'], '', o['Currency'])
    if key not in acc:
        acc[key] = {'Amount': Decimal('0.00'), 'AmountTWD': Decimal('0.00'), 'Count': 0}
        seen_order.append(key)
    acc[key]['Amount'] += Decimal(o['NetAmount'])
    acc[key]['AmountTWD'] += o['NetAmountTWD']
    acc[key]['Count'] += 1
for key in seen_order:
    group, subgroup, curr = key
    item = acc[key]
    summary_rows.append([group, subgroup, curr, item['Amount'].quantize(Decimal('0.01')), item['AmountTWD'].quantize(Decimal('0.01')), item['Count']])

for idx, rowvals in enumerate(summary_rows, start=5):
    copy_row_style(summary, 4, idx, 6)
    for col, value in enumerate(rowvals, start=1):
        summary.cell(idx, col).value = float(value) if isinstance(value, Decimal) else (None if value == '' else value)
    summary.cell(idx, 4).number_format = '0.00'
    summary.cell(idx, 5).number_format = '0.00'
    summary.cell(idx, 6).number_format = '0'

wb.save(out_xlsx)
print('Wrote:', out_xlsx)

# Reopen and verify saved output against requested requirements.
wb2 = load_workbook(out_xlsx, data_only=False)
d = wb2['Details']
s = wb2['Summary']
r = wb2['Report']
errors = []
# Check headers preserved.
expected_headers = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
actual_headers = [d.cell(4,c).value for c in range(1,12)]
if actual_headers != expected_headers:
    errors.append(f'Details headers changed: {actual_headers}')
# Check rows and exact C001 only.
actual_rows = []
for row in range(5, d.max_row + 1):
    if d.cell(row,1).value is not None:
        actual_rows.append(row)
if len(actual_rows) != 9:
    errors.append(f'Details row count is {len(actual_rows)}, expected 9')
ids = []
for row in actual_rows:
    oid = d.cell(row,1).value
    cid = d.cell(row,2).value
    ids.append(oid)
    if not isinstance(oid, str) or not oid.startswith('00'):
        errors.append(f'OrderID not stored as text with leading zeros at row {row}: {oid!r}')
    if cid != 'C001':
        errors.append(f'Non-C001 CustomerID at row {row}: {cid!r}')
    if d.cell(row,3).value == 'Acme Precision Taiwan Limited' or cid == 'C007':
        errors.append(f'Similar customer mixed in at row {row}')
    if not isinstance(d.cell(row,8).value, (int,float)):
        errors.append(f'NetAmount not numeric at row {row}: {d.cell(row,8).value!r}')
    if not isinstance(d.cell(row,9).value, (int,float)):
        errors.append(f'NetAmountTWD not numeric at row {row}: {d.cell(row,9).value!r}')
# Check known missing value is blank.
for row in actual_rows:
    if d.cell(row,1).value == '0045000132':
        if d.cell(row,11).value is not None:
            errors.append('PaymentTerms for 0045000132 is not blank')
# Check formula and sums.
if s['B2'].value != '=SUM(Details!I5:I13)':
    errors.append(f'Summary B2 formula wrong: {s["B2"].value}')
expected_total = 1702471.00
saved_total = sum(float(d.cell(row,9).value) for row in actual_rows)
if round(saved_total,2) != expected_total:
    errors.append(f'NetAmountTWD total {saved_total}, expected {expected_total}')
if r['B3'].value != '2026-08-01' or r['D3'].value != '2026-10-31':
    errors.append('Report date range not filled correctly')
if '0045000132' not in str(r['B9'].value) or 'C007' not in str(r['B9'].value):
    errors.append('Report notes do not mention missing PaymentTerms and C007 exclusion')
# Check summary rows totals equal details.
sum_rows = [row for row in range(5, s.max_row+1) if s.cell(row,1).value is not None]
summary_twd = sum(float(s.cell(row,5).value) for row in sum_rows)
summary_count = sum(int(s.cell(row,6).value) for row in sum_rows)
if round(summary_twd,2) != expected_total or summary_count != 9:
    errors.append(f'Summary rows do not reconcile: twd={summary_twd}, count={summary_count}')

print('Saved Details row count:', len(actual_rows))
print('Saved OrderIDs:', ids)
print('Saved TWD total:', f'{saved_total:.2f}')
print('Summary grouped rows:', len(sum_rows), 'count:', summary_count, 'TWD:', f'{summary_twd:.2f}')
print('Blank/missing data noted:', r['B9'].value)
if errors:
    print('VERIFY FAILED')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print('VERIFY OK')
