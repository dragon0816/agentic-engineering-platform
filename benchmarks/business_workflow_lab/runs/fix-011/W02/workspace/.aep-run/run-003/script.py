from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Alignment, Protection
from copy import copy
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import csv, json, os

ws = Path.cwd()
input_dir = ws / 'input'
out_dir = ws / 'output'
out_dir.mkdir(exist_ok=True)

# Data fetched from Lab ERP via browser: filtered exactly by CustomerID=C001 and date range.
orders = [
    {"OrderID":"0045000101","CustomerID":"C001","CustomerName":"Acme Precision Taiwan Ltd.","ProjectID":"P001","OrderDate":"2026-08-03","Status":"Closed","Currency":"TWD","NetAmount":"95895.00","CustomerContact":"Grace Lin <grace.lin@acme-precision.example>","PaymentTerms":"NET15"},
    {"OrderID":"0045000107","CustomerID":"C001","CustomerName":"Acme Precision Taiwan Ltd.","ProjectID":"P003","OrderDate":"2026-08-27","Status":"Closed","Currency":"USD","NetAmount":"6250.00","CustomerContact":"Grace Lin <grace.lin@acme-precision.example>","PaymentTerms":"NET30"},
    {"OrderID":"0045000109","CustomerID":"C001","CustomerName":"Acme Precision Taiwan Ltd.","ProjectID":"P003","OrderDate":"2026-09-01","Status":"Open","Currency":"TWD","NetAmount":"150000.00","CustomerContact":"Grace Lin <grace.lin@acme-precision.example>","PaymentTerms":"NET10"},
    {"OrderID":"0045000114","CustomerID":"C001","CustomerName":"Acme Precision Taiwan Ltd.","ProjectID":"P001","OrderDate":"2026-09-08","Status":"Cancelled","Currency":"USD","NetAmount":"11956.00","CustomerContact":"Grace Lin <grace.lin@acme-precision.example>","PaymentTerms":"NET5"},
    {"OrderID":"0045000119","CustomerID":"C001","CustomerName":"Acme Precision Taiwan Ltd.","ProjectID":"P001","OrderDate":"2026-09-15","Status":"Open","Currency":"EUR","NetAmount":"8775.00","CustomerContact":"Grace Lin <grace.lin@acme-precision.example>","PaymentTerms":"NET30"},
    {"OrderID":"0045000125","CustomerID":"C001","CustomerName":"Acme Precision Taiwan Ltd.","ProjectID":"P001","OrderDate":"2026-09-25","Status":"Closed","Currency":"TWD","NetAmount":"386445.00","CustomerContact":"Grace Lin <grace.lin@acme-precision.example>","PaymentTerms":"NET0"},
    {"OrderID":"0045000129","CustomerID":"C001","CustomerName":"Acme Precision Taiwan Ltd.","ProjectID":"P001","OrderDate":"2026-10-01","Status":"Open","Currency":"USD","NetAmount":"1602.00","CustomerContact":"Grace Lin <grace.lin@acme-precision.example>","PaymentTerms":"NET30"},
    {"OrderID":"0045000132","CustomerID":"C001","CustomerName":"Acme Precision Taiwan Ltd.","ProjectID":"P003","OrderDate":"2026-10-09","Status":"Open","Currency":"TWD","NetAmount":"50400.00","CustomerContact":"Grace Lin <grace.lin@acme-precision.example>","PaymentTerms":""},
    {"OrderID":"0045000136","CustomerID":"C001","CustomerName":"Acme Precision Taiwan Ltd.","ProjectID":"P001","OrderDate":"2026-10-31","Status":"Open","Currency":"EUR","NetAmount":"2250.00","CustomerContact":"Grace Lin <grace.lin@acme-precision.example>","PaymentTerms":"NET5"},
]

# Read FX rates, using first two CSV columns only because Note contains commas in test file.
rates = {}
with open(input_dir / 'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(row[1])
print('FX rates loaded:', rates)

for o in orders:
    amt = Decimal(o['NetAmount'])
    rate = rates[o['Currency']]
    o['NetAmountTWD'] = (amt * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Load template copy and fill it; never modify input file.
tpl = input_dir / 'sales_template.xlsx'
wb = load_workbook(tpl)

# Helper to clear rows below header without changing sheet names or merged cells.
def clear_data_rows(sh, min_row, max_col):
    if sh.max_row >= min_row:
        for row in sh.iter_rows(min_row=min_row, max_row=sh.max_row, max_col=max_col):
            for cell in row:
                cell.value = None

# Report sheet
report = wb['Report']
report['B3'] = '2026-08-01'
report['D3'] = '2026-10-31'
report['B4'] = 'CustomerID = C001; Sales Orders by OrderDate 2026-08-01 to 2026-10-31 inclusive; exact customer ID match only'
# Use the supplied today date context in generated/fetched timestamp.
generated_at = '2026-10-06T00:00:00+08:00'
report['B5'] = generated_at
report['B7'] = 'Lab ERP Sales Orders; detail pages; fx_rates.csv'
report['D7'] = generated_at
missing_notes = []
for o in orders:
    for fld in ['CustomerContact','PaymentTerms','ProjectID']:
        if o.get(fld,'') == '':
            missing_notes.append(f"{o['OrderID']} missing {fld}")
report['B9'] = '; '.join(missing_notes) if missing_notes else 'No missing source fields.'

# Details
sh = wb['Details']
headers = [sh.cell(4, c).value for c in range(1, 12)]
print('Details headers:', headers)
clear_data_rows(sh, 5, 11)
cols = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
for idx, o in enumerate(orders, start=5):
    for c, key in enumerate(cols, start=1):
        cell = sh.cell(idx, c)
        if key in ['NetAmount','NetAmountTWD']:
            cell.value = float(Decimal(o[key]) if key == 'NetAmountTWD' else Decimal(o[key]))
            cell.number_format = '0.00'
        else:
            cell.value = o[key]
            if key == 'OrderDate':
                cell.number_format = 'yyyy-mm-dd'
            else:
                cell.number_format = '@'
# Ensure text IDs as strings and leading zeros retained
for row in range(5, 5 + len(orders)):
    for col in [1,2,4]:
        sh.cell(row, col).number_format = '@'

# Update autofilter if present or define a sensible range without altering layout.
last_detail_row = 4 + len(orders)
sh.auto_filter.ref = f"A4:K{last_detail_row}"

# Summary: group by Status and Currency to avoid mixing currencies, with AmountTWD separately calculated.
sumsh = wb['Summary']
clear_data_rows(sumsh, 5, 6)
sumsh['B2'] = f"=SUM(Details!I5:I{last_detail_row})" if orders else '=SUM(Details!I5:I5)'
summary = {}
for o in orders:
    key = (o['Status'], '', o['Currency'])
    if key not in summary:
        summary[key] = {'amount': Decimal('0.00'), 'amount_twd': Decimal('0.00'), 'count': 0}
    summary[key]['amount'] += Decimal(o['NetAmount'])
    summary[key]['amount_twd'] += Decimal(o['NetAmountTWD'])
    summary[key]['count'] += 1
for r, (key, val) in enumerate(sorted(summary.items()), start=5):
    status, subgroup, currency = key
    values = [status, subgroup, currency, float(val['amount']), float(val['amount_twd']), val['count']]
    for c, v in enumerate(values, start=1):
        cell = sumsh.cell(r, c)
        cell.value = v
        if c in [4,5]:
            cell.number_format = '0.00'
        elif c == 6:
            cell.number_format = '0'
        else:
            cell.number_format = '@'
sumsh.auto_filter.ref = f"A4:F{4+len(summary)}"

# Save output
out_path = out_dir / 'sales_template_filled_C001_2026-08-01_to_2026-10-31.xlsx'
wb.save(out_path)

# Also write a small machine-readable summary for audit.
audit = {
    'customer_id': 'C001',
    'date_from': '2026-08-01',
    'date_to': '2026-10-31',
    'order_count': len(orders),
    'order_ids': [o['OrderID'] for o in orders],
    'excluded_similar_customer_note': 'Filtered by exact CustomerID C001 only; no C007/Acme Precision Taiwan Limited rows included.',
    'missing_fields': missing_notes,
    'output_workbook': str(out_path),
}
(out_dir / 'sales_template_filled_C001_summary.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
print('Wrote', out_path)
print('Missing:', missing_notes)
print('Order count:', len(orders))
print('Order IDs:', ', '.join(audit['order_ids']))

# Verification: reopen saved output and assert requirements.
wb2 = load_workbook(out_path, data_only=False)
assert wb2.sheetnames == ['Report', 'Details', 'Summary', 'Instructions'], wb2.sheetnames
det = wb2['Details']
read_rows = []
for r in range(5, 5+len(orders)):
    vals = [det.cell(r,c).value for c in range(1,12)]
    read_rows.append(vals)
# Confirm row count and no extra data immediately after.
assert len(read_rows) == 9
assert all(row[1] == 'C001' for row in read_rows), read_rows
assert all(row[0] in audit['order_ids'] and isinstance(row[0], str) and row[0].startswith('00') for row in read_rows)
assert not any(row[1] == 'C007' or row[2] == 'Acme Precision Taiwan Limited' for row in read_rows)
assert det.cell(14,1).value is None, 'Unexpected extra detail row'
# Exact PaymentTerms missing only at 0045000132 and is blank.
missing_payment = [row[0] for row in read_rows if row[10] in (None, '')]
assert missing_payment == ['0045000132'], missing_payment
assert all(row[9] not in (None,'') for row in read_rows), 'CustomerContact missing unexpectedly'
# Numeric types and formulas.
assert all(isinstance(row[7], (int,float)) and isinstance(row[8], (int,float)) for row in read_rows)
assert wb2['Summary']['B2'].value == '=SUM(Details!I5:I13)'
assert wb2['Report']['B3'].value == '2026-08-01'
assert wb2['Report']['D3'].value == '2026-10-31'
assert '0045000132 missing PaymentTerms' in wb2['Report']['B9'].value
print('CHECK PASSED: workbook reopened; details row count=9; all CustomerID=C001; similar C007 excluded; text IDs retained; numeric amount columns; Summary formula range; missing PaymentTerms noted.')
print('Files in output:')
for p in sorted(out_dir.glob('*')):
    print(p.relative_to(ws), p.stat().st_size)
