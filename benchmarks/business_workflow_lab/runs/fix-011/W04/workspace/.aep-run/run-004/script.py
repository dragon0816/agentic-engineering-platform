from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from copy import copy
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
import csv, json, re

workspace = Path.cwd()
infile = workspace/'input'/'sales_template.xlsx'
outfile = workspace/'output'/'sales_template_filled.xlsx'
workspace.joinpath('output').mkdir(exist_ok=True)

# Data acquired through browser operations from Lab ERP detail pages; order list came from exported all-filtered CSV.
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

# Read exported CSV to verify scope and sequence.
export_path = workspace/'output'/'downloads'/'orders_2026-09_open.csv'
with open(export_path, newline='', encoding='utf-8-sig') as f:
    exported = list(csv.DictReader(f))
print('exported_rows', len(exported))
print('export_order_ids', [r['OrderID'] for r in exported])
print('detail_order_ids', [r['OrderID'] for r in details])
assert [r['OrderID'] for r in exported] == [r['OrderID'] for r in details]
assert len(set(r['OrderID'] for r in details)) == len(details)

# Read FX rates. csv is imperfectly quoted in Note; DictReader still gets first two fields reliably.
rates = {}
with open(workspace/'input'/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not row: continue
        rates[row[0]] = Decimal(row[1])
print('rates', rates)

def money2(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

wb = load_workbook(infile)
wsr = wb['Report']
wsd = wb['Details']
wss = wb['Summary']

# Report metadata
now = datetime.now().astimezone().replace(microsecond=0).isoformat()
wsr['B3'] = '2026-09-01'
wsr['D3'] = '2026-09-30'
wsr['B4'] = 'Sales Orders; Status=Open; OrderDate 2026-09-01 to 2026-09-30 inclusive'
wsr['B5'] = now
wsr['B7'] = 'Lab ERP (synthetic SAP-like system); fx_rates.csv'
wsr['D7'] = now
wsr['B9'] = 'Retrieved 14 open orders and their detail records. Session expired once and was restored successfully. Blank ProjectID/CustomerContact cells indicate missing source values.'

# Clear data rows while preserving header/template style; no data present but be safe.
for row in range(5, max(wsd.max_row, 5)+1):
    for col in range(1, 12):
        wsd.cell(row, col).value = None

# Copy style from row 5 if exists else row 4 for data rows.
style_row = 5 if wsd.max_row >= 5 else 4
for i, rec in enumerate(details, start=5):
    net = money2(rec['NetAmount'])
    twd = money2(net * rates[rec['Currency']])
    values = [
        rec['OrderID'], rec['CustomerID'], rec['CustomerName'], rec['ProjectID'] or None,
        rec['OrderDate'], rec['Status'], rec['Currency'], float(net), float(twd),
        rec['CustomerContact'] or None, rec['PaymentTerms']
    ]
    for col, value in enumerate(values, start=1):
        cell = wsd.cell(i, col)
        if i != style_row:
            # preserve layout/font/fill/border/alignment from header/data exemplar as closely as possible
            src = wsd.cell(style_row, col)
            cell.font = copy(src.font); cell.fill = copy(src.fill); cell.border = copy(src.border)
            cell.alignment = copy(src.alignment); cell.protection = copy(src.protection)
        cell.value = value
        if col in (1,2,4):
            cell.number_format = '@'
        elif col == 5:
            cell.number_format = 'yyyy-mm-dd'
        elif col in (8,9):
            cell.number_format = '0.00'
        else:
            cell.number_format = '@' if col in (3,6,7,10,11) else cell.number_format

# Summary: group by Status and Currency (keeps original currency amounts separate).
# Clear previous summary rows from 5 onward.
for row in range(5, max(wss.max_row, 5)+1):
    for col in range(1, 7):
        wss.cell(row, col).value = None

summary = {}
for rec in details:
    key = (rec['Status'], '', rec['Currency'])
    net = money2(rec['NetAmount'])
    twd = money2(net * rates[rec['Currency']])
    if key not in summary:
        summary[key] = {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0}
    summary[key]['amount'] += net
    summary[key]['twd'] += twd
    summary[key]['count'] += 1

for idx, (key, vals) in enumerate(sorted(summary.items()), start=5):
    row_values = [key[0], key[1] or None, key[2], float(money2(vals['amount'])), float(money2(vals['twd'])), vals['count']]
    for col, value in enumerate(row_values, start=1):
        cell = wss.cell(idx, col)
        src = wss.cell(5 if wss.max_row >=5 else 4, col)
        cell.font = copy(src.font); cell.fill = copy(src.fill); cell.border = copy(src.border)
        cell.alignment = copy(src.alignment); cell.protection = copy(src.protection)
        cell.value = value
        if col in (4,5): cell.number_format = '0.00'
        if col == 6: cell.number_format = '0'

last_detail_row = 4 + len(details)
wss['B2'] = f'=SUM(Details!I5:I{last_detail_row})'
wss['B2'].number_format = '0.00'

# Preserve auto filters if any; set Details filter over filled data if template did not have one.
wsd.auto_filter.ref = f'A4:K{last_detail_row}'
wss.auto_filter.ref = f'A4:F{4+len(summary)}'

wb.save(outfile)
print('saved', outfile)

# Verification pass: reopen and check each stated requirement.
wb2 = load_workbook(outfile, data_only=False)
wsr2, wsd2, wss2 = wb2['Report'], wb2['Details'], wb2['Summary']
checks = []
checks.append(('sheets_unchanged', wb2.sheetnames == ['Report','Details','Summary','Instructions']))
checks.append(('report_dates', wsr2['B3'].value == '2026-09-01' and wsr2['D3'].value == '2026-09-30'))
checks.append(('condition_mentions_open', 'Open' in str(wsr2['B4'].value)))
headers = [wsd2.cell(4,c).value for c in range(1,12)]
expected_headers = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
checks.append(('details_headers', headers == expected_headers))
rows = []
for r in range(5, wsd2.max_row+1):
    if wsd2.cell(r,1).value is not None:
        rows.append([wsd2.cell(r,c).value for c in range(1,12)])
checks.append(('details_row_count_14', len(rows) == 14))
checks.append(('order_ids_match_export', [str(r[0]) for r in rows] == [r['OrderID'] for r in exported]))
checks.append(('ids_are_text_format', all(wsd2.cell(r,c).number_format == '@' for r in range(5,19) for c in (1,2,4))))
checks.append(('order_ids_keep_leading_zero', all(str(r[0]).startswith('00') and len(str(r[0]))==10 for r in rows)))
checks.append(('all_status_open', all(r[5] == 'Open' for r in rows)))
checks.append(('all_dates_in_sep_2026', all('2026-09-01' <= str(r[4]) <= '2026-09-30' for r in rows)))
checks.append(('amounts_numeric', all(isinstance(r[7], (int,float)) and isinstance(r[8], (int,float)) for r in rows)))
# verify TWD conversions
calc_ok = True
for r in rows:
    net = Decimal(str(r[7])).quantize(Decimal('0.01'))
    expected = money2(net * rates[r[6]])
    got = Decimal(str(r[8])).quantize(Decimal('0.01'))
    if got != expected:
        print('bad_twd', r[0], got, expected)
        calc_ok = False
checks.append(('twd_conversion_round_half_up', calc_ok))
checks.append(('summary_formula_extended', wss2['B2'].value == '=SUM(Details!I5:I18)'))
# Missing values blank check for known blanks
blank_ok = (wsd2['D8'].value is None and wsd2['J8'].value is None and wsd2['D9'].value is None)
checks.append(('missing_values_blank', blank_ok))

for name, ok in checks:
    print(f'CHECK {name}:', 'OK' if ok else 'FAIL')
assert all(ok for _, ok in checks)

# Print totals for final reporting
total_twd = sum(Decimal(str(r[8])).quantize(Decimal('0.01')) for r in rows)
print('detail_rows', len(rows))
print('total_twd', total_twd)
print('summary_rows', len(summary))
print('output_file', outfile)
