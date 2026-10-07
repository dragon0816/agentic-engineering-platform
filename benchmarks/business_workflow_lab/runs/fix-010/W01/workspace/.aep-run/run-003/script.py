from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font
from decimal import Decimal, ROUND_HALF_UP
import csv, shutil, datetime

ws=Path.cwd()
out=ws/'output'
out.mkdir(exist_ok=True)
print('inputs available:', sorted(p.name for p in (ws/'input').iterdir()))
print('downloads available:', sorted(p.name for p in (out/'downloads').iterdir()) if (out/'downloads').exists() else [])

# Load downloaded all-filtered CSV from browser export (all rows, not just current page)
csv_path=out/'downloads'/'september_open_orders_export.csv'
with open(csv_path, newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('export headers:', rows[0].keys() if rows else [])
print('export row count:', len(rows))
print('export sample:', rows[:2])

# Detail fields read from SAP order detail pages via browser operation
details = {
"0045000109": {"CustomerContact": "Grace Lin <grace.lin@acme-precision.example>", "PaymentTerms": "NET10"},
"0045000110": {"CustomerContact": "張美玲 <mei@tw-precision.example>", "PaymentTerms": "NET30"},
"0045000112": {"CustomerContact": "Peter Ho <peter.ho@acme-limited.example>", "PaymentTerms": "NET15"},
"0045000113": {"CustomerContact": "", "PaymentTerms": "NET15"},
"0045000115": {"CustomerContact": "Sam Patel <sam@pacifictest.example>", "PaymentTerms": "NET20"},
"0045000116": {"CustomerContact": "李建宏 <jh.lee@hsinchu-metrology.example>", "PaymentTerms": "NET30"},
"0045000118": {"CustomerContact": "Jonas Krüger <jk@northwind.example>", "PaymentTerms": "NET0"},
"0045000119": {"CustomerContact": "Grace Lin <grace.lin@acme-precision.example>", "PaymentTerms": "NET30"},
"0045000120": {"CustomerContact": "Eva de Vries <eva@helios.example>", "PaymentTerms": "NET10"},
"0045000122": {"CustomerContact": "張美玲 <mei@tw-precision.example>", "PaymentTerms": "NET5"},
"0045000124": {"CustomerContact": "", "PaymentTerms": "NET30"},
"0045000126": {"CustomerContact": "李建宏 <jh.lee@hsinchu-metrology.example>", "PaymentTerms": "NET30"},
"0045000127": {"CustomerContact": "Peter Ho <peter.ho@acme-limited.example>", "PaymentTerms": "NET30"},
"0045000128": {"CustomerContact": "Jonas Krüger <jk@northwind.example>", "PaymentTerms": "NET5"},
}

# Load FX rates
rates={}
with open(ws/'input'/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    reader=csv.reader(f)
    header=next(reader)
    print('fx header:', header)
    for row in reader:
        if not row: continue
        rates[row[0]]=Decimal(row[1])
print('rates:', rates)

# Validate/filter/sort
start='2026-09-01'; end='2026-09-30'; status='Open'
for r in rows:
    assert start <= r['OrderDate'] <= end, r
    assert r['Status'] == status, r
rows=sorted(rows, key=lambda r: r['OrderID'])
assert len(rows)==14
assert all(r['OrderID'] in details for r in rows)

# Copy and fill template
src=ws/'input'/'sales_template.xlsx'
outfile=out/'september_open_orders.xlsx'
shutil.copyfile(src, outfile)
wb=load_workbook(outfile)
rep=wb['Report']; det=wb['Details']; summ=wb['Summary']
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')
rep['B3']=start
rep['D3']=end
rep['B4']=f'Sales Orders; Status={status}; Sort=OrderID asc'
rep['B5']=now
rep['B7']='Lab ERP (synthetic SAP-like)'
rep['D7']=now
rep['B9']='Export CSV (all filtered rows) used for all matching rows; order detail pages used for CustomerContact and PaymentTerms; blank source values left blank.'

# Clear old possible data rows without disturbing row 4 headers
for sh in [det, summ]:
    maxr=sh.max_row
    if maxr>=5:
        sh.delete_rows(5, maxr-4)

# Fill details row 5+
headers=[det.cell(4,c).value for c in range(1, det.max_column+1)]
expected=['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
assert headers[:11]==expected, headers
q=Decimal('0.01')
for idx,r in enumerate(rows, start=5):
    cur=r['Currency']
    net=Decimal(r['NetAmount'])
    twd=(net*rates[cur]).quantize(q, rounding=ROUND_HALF_UP)
    vals=[r['OrderID'], r['CustomerID'], r['CustomerName'], r['ProjectID'] or None, r['OrderDate'], r['Status'], cur, float(net), float(twd), details[r['OrderID']]['CustomerContact'] or None, details[r['OrderID']]['PaymentTerms'] or None]
    for c,v in enumerate(vals, start=1):
        cell=det.cell(idx,c,value=v)
    for c in [1,2,3,4,5,6,7,10,11]:
        det.cell(idx,c).number_format='@'
    for c in [8,9]:
        det.cell(idx,c).number_format='0.00'

last=4+len(rows)
summ['B2']=f'=SUM(Details!I5:I{last})' if rows else '=SUM(Details!I5:I5)'
# Summary by currency plus total TWD row
from collections import defaultdict
amount=defaultdict(Decimal); amount_twd=defaultdict(Decimal); count=defaultdict(int)
for r in rows:
    cur=r['Currency']; net=Decimal(r['NetAmount']); twd=(net*rates[cur]).quantize(q, rounding=ROUND_HALF_UP)
    amount[cur]+=net; amount_twd[cur]+=twd; count[cur]+=1
sum_row=5
for cur in sorted(amount.keys()):
    vals=['Currency','',cur,float(amount[cur].quantize(q)),float(amount_twd[cur].quantize(q)),count[cur]]
    for c,v in enumerate(vals,1): summ.cell(sum_row,c,value=v)
    summ.cell(sum_row,4).number_format='0.00'; summ.cell(sum_row,5).number_format='0.00'; summ.cell(sum_row,6).number_format='0'
    sum_row+=1
total=sum(amount_twd.values(), Decimal('0')).quantize(q)
vals=['Total','All','TWD',None,float(total),len(rows)]
for c,v in enumerate(vals,1): summ.cell(sum_row,c,value=v)
summ.cell(sum_row,5).number_format='0.00'; summ.cell(sum_row,6).number_format='0'

# Basic autofilter extension if present
try:
    det.auto_filter.ref=f'A4:K{last}'
    summ.auto_filter.ref=f'A4:F{sum_row}'
except Exception as e:
    print('autofilter note:', e)

wb.save(outfile)
print('saved', outfile)

# Re-open and verify saved output
wb2=load_workbook(outfile, data_only=False)
rep2=wb2['Report']; det2=wb2['Details']; summ2=wb2['Summary']
assert rep2['B3'].value==start and rep2['D3'].value==end
assert rep2['B4'].value==f'Sales Orders; Status={status}; Sort=OrderID asc'
assert [det2.cell(4,c).value for c in range(1,12)]==expected
saved_rows=[]
for r in range(5, det2.max_row+1):
    if det2.cell(r,1).value:
        saved_rows.append([det2.cell(r,c).value for c in range(1,12)])
assert len(saved_rows)==14, len(saved_rows)
assert [r[0] for r in saved_rows]==sorted(r[0] for r in saved_rows)
assert all(isinstance(r[0], str) and r[0].startswith('00') for r in saved_rows)
assert all(r[4] >= start and r[4] <= end and r[5]==status for r in saved_rows)
assert all(isinstance(r[7], (int,float)) and isinstance(r[8], (int,float)) for r in saved_rows)
assert summ2['B2'].value==f'=SUM(Details!I5:I{last})'
# compute from saved and compare summary currency rows and total row
print('checked rows:', len(saved_rows))
print('detail OrderIDs:', [r[0] for r in saved_rows])
print('summary B2:', summ2['B2'].value)
for r in range(5, summ2.max_row+1):
    vals=[summ2.cell(r,c).value for c in range(1,7)]
    if any(v is not None for v in vals): print('summary row', r, vals)
print('total_twd', total)
