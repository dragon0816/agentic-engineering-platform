from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.formula.translate import Translator
from decimal import Decimal, ROUND_HALF_UP
import csv, shutil, datetime, json, os, re

ws=Path.cwd()
in_dir=ws/'input'
out_dir=ws/'output'
download=out_dir/'downloads'/'orders_export.csv'
template=in_dir/'sales_template.xlsx'
fx_path=in_dir/'fx_rates.csv'
out_path=out_dir/'september_open_orders.xlsx'

print('Inputs:')
for p in [template, fx_path, download]:
    print(p, 'exists=', p.exists(), 'bytes=', p.stat().st_size if p.exists() else None)

# Read CSV from browser export (all filtered rows per manual)
rows=[]
with open(download, encoding='utf-8-sig', newline='') as f:
    rdr=csv.DictReader(f)
    print('Export headers:', rdr.fieldnames)
    for row in rdr:
        rows.append(row)
print('Export row count:', len(rows))
print('Export sample:', rows[:3])

# Details read from SAP detail pages via browser tool.
detail_extra = {
 '0045000109': {'CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET10'},
 '0045000110': {'CustomerContact':'張美玲 <mei@tw-precision.example>','PaymentTerms':'NET30'},
 '0045000112': {'CustomerContact':'Peter Ho <peter.ho@acme-limited.example>','PaymentTerms':'NET15'},
 '0045000113': {'CustomerContact':'','PaymentTerms':'NET15'},
 '0045000115': {'CustomerContact':'Sam Patel <sam@pacifictest.example>','PaymentTerms':'NET20'},
 '0045000116': {'CustomerContact':'李建宏 <jh.lee@hsinchu-metrology.example>','PaymentTerms':'NET30'},
 '0045000118': {'CustomerContact':'Jonas Krüger <jk@northwind.example>','PaymentTerms':'NET0'},
 '0045000119': {'CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET30'},
 '0045000120': {'CustomerContact':'Eva de Vries <eva@helios.example>','PaymentTerms':'NET10'},
 '0045000122': {'CustomerContact':'張美玲 <mei@tw-precision.example>','PaymentTerms':'NET5'},
 '0045000124': {'CustomerContact':'','PaymentTerms':'NET30'},
 '0045000126': {'CustomerContact':'李建宏 <jh.lee@hsinchu-metrology.example>','PaymentTerms':'NET30'},
 '0045000127': {'CustomerContact':'Peter Ho <peter.ho@acme-limited.example>','PaymentTerms':'NET30'},
 '0045000128': {'CustomerContact':'Jonas Krüger <jk@northwind.example>','PaymentTerms':'NET5'},
}

# Read rates; note column contains commas, only first two columns matter.
rates={}
with open(fx_path, encoding='utf-8-sig', newline='') as f:
    rdr=csv.reader(f)
    header=next(rdr)
    print('FX headers:', header)
    for row in rdr:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(row[1])
print('Rates:', rates)

# Validate/filter/sort; export should already be filtered, but enforce requested rules.
from_date='2026-09-01'
to_date='2026-09-30'
status='Open'
filtered=[]
for r in rows:
    if from_date <= r['OrderDate'] <= to_date and r['Status'] == status:
        filtered.append(r)
filtered.sort(key=lambda r: r['OrderID'])
print('Filtered/sorted row count:', len(filtered))
print('First/last OrderID:', filtered[0]['OrderID'] if filtered else None, filtered[-1]['OrderID'] if filtered else None)

# Load template, preserve sheets and formatting as much as possible.
wb=load_workbook(template)
report=wb['Report']; details=wb['Details']; summary=wb['Summary']

# Clear prior data rows while keeping header row. Remove rows after existing row 4 if any (none in template).
if details.max_row > 4:
    details.delete_rows(5, details.max_row-4)
if summary.max_row > 4:
    summary.delete_rows(5, summary.max_row-4)

# Report cells
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).replace(microsecond=0).isoformat()
report['B3']=from_date
report['D3']=to_date
report['B4']=f'Sales Orders; Status={status}; Sort by OrderID asc'
report['B5']=now
report['B7']='Lab ERP synthetic SAP-like web system'
report['D7']=now
report['B9']='Export CSV (all filtered rows) used; SAP detail pages read for CustomerContact and PaymentTerms. fx_rates.csv fixed test rates used.'

# Helper for two decimals ROUND_HALF_UP
def q2(x):
    return Decimal(x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

detail_columns=['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
# Copy style from row 5 if exists else row 4; use row 4 style for data reasonably.
for idx,r in enumerate(filtered, start=5):
    cur=r['Currency']
    if cur not in rates:
        raise ValueError(f'Missing FX rate for {cur}')
    amt=Decimal(r['NetAmount'])
    twd=q2(amt*rates[cur])
    extra=detail_extra.get(r['OrderID'], {'CustomerContact':'','PaymentTerms':''})
    vals=[r['OrderID'], r['CustomerID'], r['CustomerName'], r.get('ProjectID',''), r['OrderDate'], r['Status'], cur, float(amt), float(twd), extra.get('CustomerContact',''), extra.get('PaymentTerms','')]
    for col,val in enumerate(vals, start=1):
        c=details.cell(idx,col)
        c.value=val
        # apply basic formats
        if col in (1,2,4,5,6,7,10,11):
            c.number_format='@' if col in (1,2,4) else 'yyyy-mm-dd' if col==5 else 'General'
        if col in (8,9):
            c.number_format='0.00'
        # Preserve template row 4 visual style lightly
        src=details.cell(4,col)
        c.font=src.font.copy(); c.fill=src.fill.copy(); c.border=src.border.copy(); c.alignment=src.alignment.copy()

# Summary formula B2
last_row=4+len(filtered) if filtered else 5
summary['B2']=f'=SUM(Details!I5:I{last_row if filtered else 5})'

# Build summary rows by currency, then total TWD row
by_cur={}
for r in filtered:
    cur=r['Currency']; amt=Decimal(r['NetAmount']); twd=q2(amt*rates[cur])
    rec=by_cur.setdefault(cur, {'amount':Decimal('0.00'), 'twd':Decimal('0.00'), 'count':0})
    rec['amount'] += amt
    rec['twd'] += twd
    rec['count'] += 1
sum_rows=[]
for cur in sorted(by_cur):
    rec=by_cur[cur]
    sum_rows.append(['Currency', cur, cur, float(q2(rec['amount'])), float(q2(rec['twd'])), rec['count']])
total_twd=sum((rec['twd'] for rec in by_cur.values()), Decimal('0.00'))
total_count=sum((rec['count'] for rec in by_cur.values()), 0)
sum_rows.append(['Total', 'All currencies', 'TWD', None, float(q2(total_twd)), total_count])

for idx, vals in enumerate(sum_rows, start=5):
    for col,val in enumerate(vals, start=1):
        c=summary.cell(idx,col)
        c.value=val
        src=summary.cell(4,col)
        c.font=src.font.copy(); c.fill=src.fill.copy(); c.border=src.border.copy(); c.alignment=src.alignment.copy()
        if col in (4,5):
            c.number_format='0.00'
        if col == 6:
            c.number_format='0'

# Autofilter ranges if present desired? Preserve existing; set to data area for Details/Summary.
details.auto_filter.ref=f'A4:K{last_row}'
summary.auto_filter.ref=f'A4:F{4+len(sum_rows)}'

# Save
out_path.parent.mkdir(parents=True, exist_ok=True)
wb.save(out_path)
print('Saved:', out_path, out_path.stat().st_size)

# Reopen and validate stated requirements
wb2=load_workbook(out_path, data_only=False)
assert wb2.sheetnames == ['Report','Details','Summary','Instructions']
rd=wb2['Details']; sm=wb2['Summary']; rp=wb2['Report']
headers=[rd.cell(4,c).value for c in range(1,12)]
print('Output detail headers:', headers)
assert headers == detail_columns
out_rows=[]
for i in range(5, 5+len(filtered)):
    out_rows.append([rd.cell(i,c).value for c in range(1,12)])
assert len(out_rows)==14
assert [r[0] for r in out_rows] == sorted([r[0] for r in out_rows])
assert all(isinstance(r[0], str) and re.match(r'^\d{10}$', r[0]) for r in out_rows)
assert all(r[5]=='Open' for r in out_rows)
assert all(from_date <= r[4] <= to_date for r in out_rows)
assert all(isinstance(r[7], (int,float)) and isinstance(r[8], (int,float)) for r in out_rows)
# Check TWD conversion exactly to 2dp via Decimal from cell strings
for row in out_rows:
    cur=row[6]
    expected=q2(Decimal(str(row[7]))*rates[cur])
    got=q2(Decimal(str(row[8])))
    assert got==expected, (row[0], got, expected)
print('Report B3/D3/B4:', rp['B3'].value, rp['D3'].value, rp['B4'].value)
print('Summary B2 formula:', sm['B2'].value)
summary_values=[]
for i in range(5, 5+len(sum_rows)):
    summary_values.append([sm.cell(i,c).value for c in range(1,7)])
print('Summary rows:', summary_values)
assert sm['B2'].value == '=SUM(Details!I5:I18)'
assert summary_values[-1][0]=='Total' and summary_values[-1][2]=='TWD'
# File names and folders
assert out_path.name == 'september_open_orders.xlsx'
print('Validation OK: file name, sheets, detail columns, 14 rows, OrderID text/sorted, status/date filters, numeric amounts, FX conversion, summary rows, B2 formula.')
