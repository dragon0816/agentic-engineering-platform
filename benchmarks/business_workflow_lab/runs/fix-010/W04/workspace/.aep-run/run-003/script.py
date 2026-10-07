from pathlib import Path
from openpyxl import load_workbook
from copy import copy
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
import csv, json, shutil

workspace = Path.cwd()
outdir = workspace / 'output'
outdir.mkdir(exist_ok=True)

# Read FX rates
fx = {}
with open(workspace/'input'/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if len(row) >= 2:
            fx[row[0]] = Decimal(row[1])
print('FX rates:', fx)

# Data collected from Lab ERP detail pages via browser operation.
details = [
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

# Verify list uniqueness and filters before writing.
ids = [d['OrderID'] for d in details]
assert len(ids) == len(set(ids)) == 14, (len(ids), len(set(ids)))
assert all(d['Status'] == 'Open' and '2026-09-01' <= d['OrderDate'] <= '2026-09-30' for d in details)
assert ids == sorted(ids), 'Expected orders sorted ascending by OrderID'

# Compute TWD amounts ROUND_HALF_UP.
for d in details:
    amount = Decimal(d['NetAmount'])
    rate = fx[d['Currency']]
    d['NetAmountTWD'] = (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Fill a copy of the provided template.
wb = load_workbook(workspace/'input'/'sales_template.xlsx')
report = wb['Report']
ws = wb['Details']
summary = wb['Summary']

now = datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()
report['B3'] = '2026-09-01'
report['D3'] = '2026-09-30'
report['B4'] = 'Sales Orders: Status = Open; OrderDate 2026-09-01 to 2026-09-30 inclusive; sorted by OrderID asc'
report['B5'] = now
report['B7'] = 'Lab ERP (synthetic SAP-like web query); fx_rates.csv'
report['D7'] = now
report['B9'] = '14 unique Open orders fetched. Re-login performed once after session timeout. Empty source values are left blank. Detail page also contains SalesRep and line items, but this template has columns only for CustomerContact and PaymentTerms.'

# Clear old data rows below row 4 if any, preserving row 4 headers and styles.
for row in range(5, max(ws.max_row, 5) + 1):
    for col in range(1, ws.max_column + 1):
        ws.cell(row=row, column=col).value = None

headers = [ws.cell(row=4, column=c).value for c in range(1, ws.max_column+1)]
expected = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
assert headers == expected, headers

# Copy row 5 style template from row 4 where needed? Use row 4 styles for data cells conservatively.
for r_idx, d in enumerate(details, start=5):
    values = [
        d['OrderID'], d['CustomerID'], d['CustomerName'], d['ProjectID'] or None, d['OrderDate'], d['Status'], d['Currency'],
        float(Decimal(d['NetAmount'])), float(d['NetAmountTWD']), d['CustomerContact'] or None, d['PaymentTerms'] or None
    ]
    for c_idx, val in enumerate(values, start=1):
        cell = ws.cell(row=r_idx, column=c_idx, value=val)
        # Preserve existing/formatted appearance using row 4 as base.
        src = ws.cell(row=4, column=c_idx)
        if src.has_style:
            cell.font = copy(src.font); cell.fill = copy(src.fill); cell.border = copy(src.border)
            cell.alignment = copy(src.alignment); cell.protection = copy(src.protection)
        if c_idx in (1,2,3,4,5,6,7,10,11):
            cell.number_format = '@'
        elif c_idx in (8,9):
            cell.number_format = '0.00'

# Summary: group by Status and Currency, since all requested records are Open and currencies must not be mixed.
for row in range(5, max(summary.max_row, 5) + 1):
    for col in range(1, summary.max_column + 1):
        summary.cell(row=row, column=col).value = None

summary['B2'] = f'=SUM(Details!I5:I{4+len(details)})'
# totals per status/currency
from collections import defaultdict
agg = defaultdict(lambda: {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0})
for d in details:
    key = (d['Status'], d['Currency'])
    agg[key]['amount'] += Decimal(d['NetAmount'])
    agg[key]['twd'] += d['NetAmountTWD']
    agg[key]['count'] += 1
for r_idx, ((status, currency), vals) in enumerate(sorted(agg.items(), key=lambda kv: kv[0][1]), start=5):
    row_vals = ['Status', status, currency, float(vals['amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), float(vals['twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), vals['count']]
    for c_idx, val in enumerate(row_vals, start=1):
        cell = summary.cell(row=r_idx, column=c_idx, value=val)
        src = summary.cell(row=4, column=c_idx)
        if src.has_style:
            cell.font = copy(src.font); cell.fill = copy(src.fill); cell.border = copy(src.border)
            cell.alignment = copy(src.alignment); cell.protection = copy(src.protection)
        if c_idx in (4,5): cell.number_format = '0.00'

# Apply autofilter to filled ranges if present? Preserve existing if already set; set reasonable refs.
ws.auto_filter.ref = f'A4:K{4+len(details)}'
summary.auto_filter.ref = f'A4:F{4+len(agg)}'

output_path = outdir/'sales_orders_open_2026-09_filled.xlsx'
wb.save(output_path)
print('Wrote', output_path)
print('Detail rows', len(details))
print('Summary groups', {str(k): v for k,v in agg.items()})
print('Total TWD', sum((d['NetAmountTWD'] for d in details), Decimal('0')).quantize(Decimal('0.01')))
