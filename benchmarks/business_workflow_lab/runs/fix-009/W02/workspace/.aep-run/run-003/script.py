from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
import csv, shutil

workspace = Path('.')
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(exist_ok=True)

source_template = input_dir / 'sales_template.xlsx'
orders_csv = output_dir / 'downloads' / 'orders_C001_2026-08-01_2026-10-31.csv'
fx_csv = input_dir / 'fx_rates.csv'
outfile = output_dir / 'sales_report_C001_2026-08-01_2026-10-31.xlsx'

# Detail data read from the ERP order detail pages in this run.
detail_headers = {
    '0045000101': {'OrderID':'0045000101','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-08-03','Status':'Closed','Currency':'TWD','NetAmount':'95895.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET15'},
    '0045000107': {'OrderID':'0045000107','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P003','OrderDate':'2026-08-27','Status':'Closed','Currency':'USD','NetAmount':'6250.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET30'},
    '0045000109': {'OrderID':'0045000109','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P003','OrderDate':'2026-09-01','Status':'Open','Currency':'TWD','NetAmount':'150000.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET10'},
    '0045000114': {'OrderID':'0045000114','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-09-08','Status':'Cancelled','Currency':'USD','NetAmount':'11956.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET5'},
    '0045000119': {'OrderID':'0045000119','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-09-15','Status':'Open','Currency':'EUR','NetAmount':'8775.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET30'},
    '0045000125': {'OrderID':'0045000125','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-09-25','Status':'Closed','Currency':'TWD','NetAmount':'386445.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET0'},
    '0045000129': {'OrderID':'0045000129','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-10-01','Status':'Open','Currency':'USD','NetAmount':'1602.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET30'},
    '0045000132': {'OrderID':'0045000132','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P003','OrderDate':'2026-10-09','Status':'Open','Currency':'TWD','NetAmount':'50400.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':''},
    '0045000136': {'OrderID':'0045000136','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-10-31','Status':'Open','Currency':'EUR','NetAmount':'2250.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET5'},
}

# Read downloaded list to verify the exact CustomerID/date filter and order set.
with open(orders_csv, newline='', encoding='utf-8-sig') as f:
    orders = list(csv.DictReader(f))
print('Downloaded orders:', len(orders), [r['OrderID'] for r in orders])

# Read FX rates; only first two columns are used because the Note column contains commas in the test data.
rates = {}
with open(fx_csv, newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(row[1])
print('FX rates:', rates)

# Validate source rows before writing.
for r in orders:
    assert r['CustomerID'] == 'C001', f"Non-C001 row found: {r}"
    assert '2026-08-01' <= r['OrderDate'] <= '2026-10-31', f"Out-of-period row found: {r}"
assert [r['OrderID'] for r in orders] == list(detail_headers.keys()), 'Detail/header order set does not match exported order list'
assert '0045000105' not in detail_headers, 'Similar-name C007 customer was incorrectly included'

TWOPLACES = Decimal('0.01')
def money_twd(amount, currency):
    return (Decimal(str(amount)) * rates[currency]).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def to_date(s):
    y,m,d = map(int, s.split('-'))
    return date(y,m,d)

shutil.copyfile(source_template, outfile)
wb = load_workbook(outfile)

report = wb['Report']
report['B3'] = '2026-08-01'
report['D3'] = '2026-10-31'
report['B4'] = 'Sales Orders; CustomerID exactly C001; OrderDate 2026-08-01 through 2026-10-31; all statuses; sort OrderID asc.'
report['B5'] = '2026-10-06T00:00:00+08:00'
report['B7'] = 'Lab ERP Sales Orders detail; fx_rates.csv'
report['D7'] = '2026-10-06T00:00:00+08:00'
report['B9'] = 'Missing data: PaymentTerms is blank for OrderID 0045000132. CustomerContact has no missing values. Exact CustomerID C001 filter used; similar-name C007 not included.'

# Clear any existing data rows while preserving header and sheets.
details = wb['Details']
if details.max_row >= 5:
    details.delete_rows(5, details.max_row - 4)

headers = [details.cell(4, c).value for c in range(1, details.max_column + 1)]
expected_headers = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
assert headers == expected_headers, headers

rows_for_summary = []
for idx, order in enumerate(orders, start=5):
    d = detail_headers[order['OrderID']]
    net = Decimal(d['NetAmount'])
    twd = money_twd(net, d['Currency'])
    values = [
        d['OrderID'], d['CustomerID'], d['CustomerName'], d.get('ProjectID') or None,
        to_date(d['OrderDate']), d['Status'], d['Currency'], float(net), float(twd),
        d.get('CustomerContact') or None, d.get('PaymentTerms') or None,
    ]
    for col, value in enumerate(values, start=1):
        cell = details.cell(idx, col, value)
        if col in (1,2,4):
            cell.number_format = '@'
        elif col == 5:
            cell.number_format = 'yyyy-mm-dd'
        elif col in (8,9):
            cell.number_format = '0.00'
        else:
            cell.number_format = '@' if col in (3,6,7,10,11) else cell.number_format
    rows_for_summary.append((d['Status'], d['Currency'], net, twd))

details.freeze_panes = details.freeze_panes
# Extend autofilter if the template has one; otherwise leave as-is except on the data table.
details.auto_filter.ref = f'A4:K{4 + len(orders)}'

summary = wb['Summary']
if summary.max_row >= 5:
    summary.delete_rows(5, summary.max_row - 4)
last_detail_row = 4 + len(orders) if orders else 5
summary['B2'] = f'=SUM(Details!I5:I{last_detail_row if orders else 5})'
summary['B2'].number_format = '0.00'

# Summary by Status + Currency so different currencies are not mixed in original amount.
group_order = []
groups = {}
for status, currency, amount, twd in rows_for_summary:
    key = (status, currency)
    if key not in groups:
        groups[key] = [Decimal('0'), Decimal('0'), 0]
        group_order.append(key)
    groups[key][0] += amount
    groups[key][1] += twd
    groups[key][2] += 1
for rix, key in enumerate(group_order, start=5):
    status, currency = key
    amount, twd, count = groups[key]
    vals = [status, None, currency, float(amount.quantize(TWOPLACES)), float(twd.quantize(TWOPLACES)), count]
    for col, value in enumerate(vals, start=1):
        cell = summary.cell(rix, col, value)
        if col in (4,5):
            cell.number_format = '0.00'
        elif col == 6:
            cell.number_format = '0'

wb.save(outfile)
print('Wrote', outfile)

# Reopen and check every requirement stated: output exists, template sheets/headers kept, exact C001 rows/date range, detail fields, blanks, numeric values and formulas.
wb2 = load_workbook(outfile, data_only=False)
assert set(wb2.sheetnames) == set(load_workbook(source_template, read_only=True).sheetnames), wb2.sheetnames
assert 'Instructions' in wb2.sheetnames
for sheet in ['Report','Details','Summary','Instructions']:
    assert sheet in wb2.sheetnames
rep = wb2['Report']
assert rep['B3'].value == '2026-08-01'
assert rep['D3'].value == '2026-10-31'
assert 'C001' in rep['B4'].value
assert '0045000132' in rep['B9'].value and 'PaymentTerms' in rep['B9'].value
assert 'C007' in rep['B9'].value

det = wb2['Details']
assert [det.cell(4,c).value for c in range(1,12)] == expected_headers
assert det.max_row == 13, det.max_row
seen=[]
missing_payment=[]
for row in range(5,14):
    oid = det.cell(row,1).value
    seen.append(oid)
    assert isinstance(oid, str) and oid.startswith('0045')
    assert det.cell(row,2).value == 'C001'
    assert det.cell(row,3).value == 'Acme Precision Taiwan Ltd.'
    assert det.cell(row,5).value >= date(2026,8,1) and det.cell(row,5).value <= date(2026,10,31)
    assert isinstance(det.cell(row,8).value, (int,float))
    assert isinstance(det.cell(row,9).value, (int,float))
    if det.cell(row,11).value in (None, ''):
        missing_payment.append(oid)
assert seen == list(detail_headers.keys()), seen
assert missing_payment == ['0045000132'], missing_payment
assert all(det.cell(r,10).value for r in range(5,14))

summ = wb2['Summary']
assert summ['B2'].value == '=SUM(Details!I5:I13)'
assert summ.max_row == 10, summ.max_row
assert abs(sum(float(summ.cell(r,5).value) for r in range(5,11)) - 1702471.00) < 0.001
assert all(isinstance(summ.cell(r,4).value, (int,float)) for r in range(5,11))
assert all(isinstance(summ.cell(r,5).value, (int,float)) for r in range(5,11))
print('Checked: workbook sheets preserved; Report fields filled; Details has 9 exact C001 rows only; OrderID/CustomerID text; dates in requested inclusive period; monetary values numeric with TWD conversion; PaymentTerms blank only for 0045000132; Summary formula and grouped totals verified.')
print('Output file:', outfile.resolve())