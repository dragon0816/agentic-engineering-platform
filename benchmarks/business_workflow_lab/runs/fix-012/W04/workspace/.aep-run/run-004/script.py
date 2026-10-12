from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Border, Alignment, Protection
from copy import copy
from decimal import Decimal, ROUND_HALF_UP
import csv, re, json
from datetime import datetime, timezone, timedelta

ws = Path.cwd()
infile = ws/'input'/'sales_template.xlsx'
outdir = ws/'output'
outdir.mkdir(exist_ok=True)
outfile = outdir/'sales_order_report_2026-09_open.xlsx'

# Data obtained from Lab ERP via browser operation: export CSV + detail pages.
orders = [
 {'OrderID':'0045000109','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P003','OrderDate':'2026-09-01','Status':'Open','Currency':'TWD','NetAmount':'150000.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET10'},
 {'OrderID':'0045000110','CustomerID':'C002','CustomerName':'台灣精密股份有限公司','ProjectID':'P002','OrderDate':'2026-09-02','Status':'Open','Currency':'TWD','NetAmount':'293572.50','CustomerContact':'張美玲 <mei@tw-precision.example>','PaymentTerms':'NET30'},
 {'OrderID':'0045000112','CustomerID':'C007','CustomerName':'Acme Precision Taiwan Limited','ProjectID':'P005','OrderDate':'2026-09-04','Status':'Open','Currency':'USD','NetAmount':'12311.00','CustomerContact':'Peter Ho <peter.ho@acme-limited.example>','PaymentTerms':'NET15'},
 {'OrderID':'0045000113','CustomerID':'C004','CustomerName':'藍海電子有限公司','ProjectID':'','OrderDate':'2026-09-05','Status':'Open','Currency':'TWD','NetAmount':'15390.00','CustomerContact':'','PaymentTerms':'NET15'},
 {'OrderID':'0045000115','CustomerID':'C005','CustomerName':'Pacific Test Systems Inc.','ProjectID':'','OrderDate':'2026-09-09','Status':'Open','Currency':'USD','NetAmount':'6391.00','CustomerContact':'Sam Patel <sam@pacifictest.example>','PaymentTerms':'NET20'},
 {'OrderID':'0045000116','CustomerID':'C008','CustomerName':'新竹量測科技','ProjectID':'','OrderDate':'2026-09-10','Status':'Open','Currency':'TWD','NetAmount':'29400.00','CustomerContact':'李建宏 <jh.lee@hsinchu-metrology.example>','PaymentTerms':'NET30'},
 {'OrderID':'0045000118','CustomerID':'C003','CustomerName':'Northwind Components GmbH','ProjectID':'P004','OrderDate':'2026-09-14','Status':'Open','Currency':'EUR','NetAmount':'17484.75','CustomerContact':'Jonas Krüger <jk@northwind.example>','PaymentTerms':'NET0'},
 {'OrderID':'0045000119','CustomerID':'C001','CustomerName':'Acme Precision Taiwan Ltd.','ProjectID':'P001','OrderDate':'2026-09-15','Status':'Open','Currency':'EUR','NetAmount':'8775.00','CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET30'},
 {'OrderID':'0045000120','CustomerID':'C006','CustomerName':'Helios Optics B.V.','ProjectID':'','OrderDate':'2026-09-16','Status':'Open','Currency':'EUR','NetAmount':'461.70','CustomerContact':'Eva de Vries <eva@helios.example>','PaymentTerms':'NET10'},
 {'OrderID':'0045000122','CustomerID':'C002','CustomerName':'台灣精密股份有限公司','ProjectID':'P002','OrderDate':'2026-09-21','Status':'Open','Currency':'USD','NetAmount':'4141.00','CustomerContact':'張美玲 <mei@tw-precision.example>','PaymentTerms':'NET5'},
 {'OrderID':'0045000124','CustomerID':'C004','CustomerName':'藍海電子有限公司','ProjectID':'','OrderDate':'2026-09-24','Status':'Open','Currency':'TWD','NetAmount':'45000.00','CustomerContact':'','PaymentTerms':'NET30'},
 {'OrderID':'0045000126','CustomerID':'C008','CustomerName':'新竹量測科技','ProjectID':'','OrderDate':'2026-09-28','Status':'Open','Currency':'USD','NetAmount':'9171.00','CustomerContact':'李建宏 <jh.lee@hsinchu-metrology.example>','PaymentTerms':'NET30'},
 {'OrderID':'0045000127','CustomerID':'C007','CustomerName':'Acme Precision Taiwan Limited','ProjectID':'P005','OrderDate':'2026-09-30','Status':'Open','Currency':'EUR','NetAmount':'2214.92','CustomerContact':'Peter Ho <peter.ho@acme-limited.example>','PaymentTerms':'NET30'},
 {'OrderID':'0045000128','CustomerID':'C003','CustomerName':'Northwind Components GmbH','ProjectID':'P004','OrderDate':'2026-09-30','Status':'Open','Currency':'TWD','NetAmount':'104160.00','CustomerContact':'Jonas Krüger <jk@northwind.example>','PaymentTerms':'NET5'},
]

# Sanity against exported list from the system.
export_path = ws/'output'/'downloads'/'orders_2026-09_open.csv'
with export_path.open(newline='', encoding='utf-8-sig') as f:
    exported = list(csv.DictReader(f))
export_ids = [r['OrderID'] for r in exported]
detail_ids = [r['OrderID'] for r in orders]
assert export_ids == detail_ids, (export_ids, detail_ids)
assert len(orders) == 14
assert len(set(detail_ids)) == len(detail_ids)
assert all(r['Status'] == 'Open' and '2026-09-01' <= r['OrderDate'] <= '2026-09-30' for r in orders)

# Load FX rates robustly (notes contain unquoted commas; first 2 columns matter).
rates = {}
with (ws/'input'/'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if len(row) >= 2:
            rates[row[0]] = Decimal(row[1])
print('FX rates:', rates)
q = Decimal('0.01')
def money(v):
    return Decimal(str(v)).quantize(q, rounding=ROUND_HALF_UP)
def twd(amount, currency):
    return (Decimal(str(amount)) * rates[currency]).quantize(q, rounding=ROUND_HALF_UP)

wb = load_workbook(infile)
report = wb['Report']
details = wb['Details']
summary = wb['Summary']

# Fill Report sheet metadata.
report['B3'] = '2026-09-01'
report['D3'] = '2026-09-30'
report['B4'] = 'Sales Orders: Status=Open; OrderDate 2026-09-01 through 2026-09-30'
# Use lab-provided today date and Taiwan offset; deterministic output for this test run.
report['B5'] = '2026-10-06T00:00:00+08:00'
report['B7'] = 'Lab ERP Sales Orders; fx_rates.csv'
report['D7'] = '2026-10-06T00:00:00+08:00'
report['B9'] = 'One session timeout occurred during export; re-login succeeded. Empty ProjectID/CustomerContact cells reflect source blanks.'

# Clear any existing detail/summary data rows, preserving template sheets.
for sh in (details, summary):
    if sh.max_row >= 5:
        sh.delete_rows(5, sh.max_row - 4)

# Fill Details from row 5.
headers = [details.cell(4, c).value for c in range(1, details.max_column+1)]
expected = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
assert headers == expected, headers
text_cols = {1,2,4,6,7,10,11}
num_cols = {8,9}
for i, r in enumerate(orders, start=5):
    values = [
        r['OrderID'], r['CustomerID'], r['CustomerName'], r['ProjectID'] or None,
        r['OrderDate'], r['Status'], r['Currency'], float(money(r['NetAmount'])),
        float(twd(r['NetAmount'], r['Currency'])), r['CustomerContact'] or None, r['PaymentTerms']
    ]
    for c, val in enumerate(values, start=1):
        cell = details.cell(i, c, val)
        # Preserve-ish layout by reusing row 4 alignment/border/protection and data formats.
        src = details.cell(4, c)
        cell.font = copy(src.font)
        cell.fill = copy(src.fill)
        cell.border = copy(src.border)
        cell.alignment = copy(src.alignment)
        cell.protection = copy(src.protection)
        if c in text_cols:
            cell.number_format = '@'
        elif c in num_cols:
            cell.number_format = '0.00'
        else:
            cell.number_format = src.number_format

last = 4 + len(orders)
summary['B2'] = f'=SUM(Details!I5:I{last})'
summary['B2'].number_format = '0.00'

# Summary: group by Status and Currency, with original currency amount plus TWD converted amount.
from collections import defaultdict
agg = defaultdict(lambda: {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0})
for r in orders:
    key = (r['Status'], '', r['Currency'])
    agg[key]['amount'] += Decimal(r['NetAmount'])
    agg[key]['twd'] += twd(r['NetAmount'], r['Currency'])
    agg[key]['count'] += 1
for row_idx, (key, val) in enumerate(sorted(agg.items(), key=lambda kv: kv[0][2]), start=5):
    status, subgroup, currency = key
    vals = [status, None, currency, float(val['amount'].quantize(q, rounding=ROUND_HALF_UP)), float(val['twd'].quantize(q, rounding=ROUND_HALF_UP)), val['count']]
    for c, v in enumerate(vals, start=1):
        cell = summary.cell(row_idx, c, v)
        src = summary.cell(4, c)
        cell.font = copy(src.font)
        cell.fill = copy(src.fill)
        cell.border = copy(src.border)
        cell.alignment = copy(src.alignment)
        cell.protection = copy(src.protection)
        if c in (4,5): cell.number_format = '0.00'
        elif c == 6: cell.number_format = '0'
        else: cell.number_format = '@'

# Keep autofilter definitions if present; if absent, set to used ranges below headers.
details.auto_filter.ref = f'A4:K{last}'
summary_last = 4 + len(agg)
summary.auto_filter.ref = f'A4:F{summary_last}'

wb.save(outfile)
print('wrote', outfile)
print('detail rows', len(orders), 'summary rows', len(agg))
print('detail total TWD', sum(twd(r['NetAmount'], r['Currency']) for r in orders))
for key, val in sorted(agg.items(), key=lambda kv: kv[0][2]):
    print('summary', key, val)

# Reopen and verify stated requirements.
wb2 = load_workbook(outfile, data_only=False)
assert wb2.sheetnames == ['Report', 'Details', 'Summary', 'Instructions']
d2 = wb2['Details']; s2=wb2['Summary']; r2=wb2['Report']
assert r2['B3'].value == '2026-09-01' and r2['D3'].value == '2026-09-30'
assert r2['B4'].value and 'Open' in r2['B4'].value
assert d2.max_row == 18, d2.max_row
assert [d2.cell(4,c).value for c in range(1,12)] == expected
ids = [d2.cell(i,1).value for i in range(5,19)]
assert ids == export_ids
assert all(isinstance(v, str) and v.startswith('0045') for v in ids)
assert all(d2.cell(i,6).value == 'Open' for i in range(5,19))
assert all('2026-09-01' <= d2.cell(i,5).value <= '2026-09-30' for i in range(5,19))
for i in range(5,19):
    assert isinstance(d2.cell(i,8).value, (int,float))
    assert isinstance(d2.cell(i,9).value, (int,float))
    calc = float(twd(str(d2.cell(i,8).value), d2.cell(i,7).value))
    assert abs(d2.cell(i,9).value - calc) < 0.005, (i, d2.cell(i,9).value, calc)
assert s2['B2'].value == '=SUM(Details!I5:I18)'
assert s2.max_row == 7
print('verified output workbook: sheets preserved, report metadata, 14 detail rows, text IDs, Open Sep-2026 filter, numeric amounts, TWD conversion, Summary formula/ranges')