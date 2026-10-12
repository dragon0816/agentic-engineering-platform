from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from decimal import Decimal, ROUND_HALF_UP
import csv, json, os, shutil
from collections import defaultdict

ws = Path.cwd()
infile = ws/'input'/'sales_template.xlsx'
outdir = ws/'output'
outdir.mkdir(exist_ok=True)
outfile = outdir/'sales_C001_2026-08-01_2026-10-31.xlsx'

# Detail data read from Lab ERP browser operations: Sales Orders filtered by exact Customer ID C001 and OrderDate 2026-08-01..2026-10-31,
# then each order detail page was opened to obtain CustomerContact and PaymentTerms.
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

# Load FX rates, keeping first two CSV columns because Note contains a comma in source rows.
rates = {}
with (ws/'input'/'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    rdr = csv.reader(f)
    header = next(rdr)
    for row in rdr:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(row[1])
print('FX rates:', rates)

# Copy/open template; preserve sheets and formatting.
wb = load_workbook(infile)
report = wb['Report']
details = wb['Details']
summary = wb['Summary']

# Clear old detail/summary data area if any, without changing headers.
for sh in (details, summary):
    start = 5
    if sh.max_row >= start:
        sh.delete_rows(start, sh.max_row - start + 1)

# Report metadata
report['B3'] = '2026-08-01'
report['D3'] = '2026-10-31'
report['B4'] = 'Sales Orders; CustomerID exact match C001; OrderDate 2026-08-01 to 2026-10-31 inclusive; all statuses'
report['B5'] = '2026-10-06T00:00:00+08:00'
report['B7'] = 'Lab ERP Sales Orders detail pages; fx_rates.csv'
report['D7'] = '2026-10-06T00:00:00+08:00'

missing = []
# Styles from the first data row if present, otherwise header row. Since template has no data row, copy header-adjacent basics.
# Fill details
headers = [details.cell(4,c).value for c in range(1,12)]
for idx, rec in enumerate(orders, start=5):
    amt = Decimal(rec['NetAmount'])
    rate = rates[rec['Currency']]
    twd = (amt * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    values = [rec['OrderID'], rec['CustomerID'], rec['CustomerName'], rec['ProjectID'], rec['OrderDate'], rec['Status'], rec['Currency'], float(amt), float(twd), rec['CustomerContact'], rec['PaymentTerms']]
    for col, val in enumerate(values, start=1):
        cell = details.cell(idx, col, val)
        # preserve likely formatting rules
        if col in (1,2,4,10,11):
            cell.number_format = '@'
        elif col == 5:
            cell.number_format = 'yyyy-mm-dd'
        elif col in (8,9):
            cell.number_format = '0.00'
        if col == 1:
            cell.alignment = Alignment(horizontal='left')
    if not rec.get('CustomerContact'):
        missing.append(f"{rec['OrderID']}: CustomerContact")
    if not rec.get('PaymentTerms'):
        missing.append(f"{rec['OrderID']}: PaymentTerms")

last_row = 4 + len(orders) if orders else 5
summary['B2'] = f'=SUM(Details!I5:I{last_row if orders else 5})'
summary['B2'].number_format = '0.00'

# Summary by Currency, so original currency amounts are not mixed across currencies.
groups = defaultdict(lambda: {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0})
for rec in orders:
    amt = Decimal(rec['NetAmount'])
    twd = (amt * rates[rec['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    g = groups[rec['Currency']]
    g['amount'] += amt
    g['twd'] += twd
    g['count'] += 1
for r, cur in enumerate(sorted(groups.keys()), start=5):
    g = groups[cur]
    vals = ['Currency total', '', cur, float(g['amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), float(g['twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), g['count']]
    for c, val in enumerate(vals, start=1):
        cell = summary.cell(r,c,val)
        if c in (4,5): cell.number_format = '0.00'

notes = []
notes.append('Filtered by exact CustomerID C001; similar customer C007 / Acme Precision Taiwan Limited was excluded.')
if missing:
    notes.append('Missing source fields left blank: ' + '; '.join(missing) + '.')
else:
    notes.append('No missing source fields.')
notes.append(f'Rows included: {len(orders)}.')
report['B9'] = ' '.join(notes)

# Save
wb.save(outfile)
print('Wrote', outfile)

# Verification: reopen output and confirm requirements.
wb2 = load_workbook(outfile, data_only=False)
rep = wb2['Report']; det = wb2['Details']; summ = wb2['Summary']
errors=[]
# sheet names preserved
if wb2.sheetnames != ['Report','Details','Summary','Instructions']:
    errors.append('sheet names changed')
# row count and no blank rows in details
actual_rows=[]
for r in range(5, det.max_row+1):
    if any(det.cell(r,c).value is not None for c in range(1,12)):
        actual_rows.append(r)
if len(actual_rows)!=9:
    errors.append(f'Details row count {len(actual_rows)} != 9')
# columns names preserved
expected_headers=['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
actual_headers=[det.cell(4,c).value for c in range(1,12)]
if actual_headers!=expected_headers:
    errors.append('Details headers mismatch: '+repr(actual_headers))
# exact customer and date range; exclude C007; id strings
for r in actual_rows:
    oid=det.cell(r,1).value; cid=det.cell(r,2).value; od=det.cell(r,5).value
    if not isinstance(oid,str) or not oid.startswith('00'):
        errors.append(f'OrderID not text/leading zeros at row {r}: {oid!r}')
    if cid!='C001': errors.append(f'Non-C001 row {r}: {cid}')
    if not ('2026-08-01' <= str(od) <= '2026-10-31'):
        errors.append(f'Out-of-range date row {r}: {od}')
    if det.cell(r,3).value == 'Acme Precision Taiwan Limited' or cid == 'C007':
        errors.append(f'Similar customer included row {r}')
    if not isinstance(det.cell(r,8).value, (int,float)) or not isinstance(det.cell(r,9).value, (int,float)):
        errors.append(f'Amount not numeric row {r}')
# missing field should be blank, not N/A/0
row_by_id={det.cell(r,1).value:r for r in actual_rows}
if det.cell(row_by_id['0045000132'],11).value not in (None,''):
    errors.append('0045000132 PaymentTerms not blank')
# summary formula range
if summ['B2'].value != '=SUM(Details!I5:I13)':
    errors.append('Summary B2 formula not extended: '+repr(summ['B2'].value))
# expected TWD calculations
expected_twd = {
 '0045000101': Decimal('95895.00'),
 '0045000107': Decimal('200000.00'),
 '0045000109': Decimal('150000.00'),
 '0045000114': Decimal('382592.00'),
 '0045000119': Decimal('307125.00'),
 '0045000125': Decimal('386445.00'),
 '0045000129': Decimal('51264.00'),
 '0045000132': Decimal('50400.00'),
 '0045000136': Decimal('78750.00'),
}
for oid, exp in expected_twd.items():
    r=row_by_id[oid]
    got=Decimal(str(det.cell(r,9).value)).quantize(Decimal('0.01'))
    if got != exp:
        errors.append(f'{oid} TWD {got} != {exp}')
if errors:
    print('VERIFY FAILED')
    for e in errors: print(' -', e)
    raise SystemExit(1)
print('VERIFY OK')
print('Output rows:', len(actual_rows))
print('Detail OrderIDs:', [det.cell(r,1).value for r in actual_rows])
print('Missing fields:', missing)
print('Summary B2:', summ['B2'].value)
print('Files:', [p.name for p in outdir.iterdir()])