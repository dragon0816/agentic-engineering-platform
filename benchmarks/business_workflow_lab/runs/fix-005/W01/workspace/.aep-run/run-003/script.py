from pathlib import Path
import csv
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from openpyxl import load_workbook
from openpyxl.styles import numbers

base=Path('.')
in_template=base/'input'/'sales_template.xlsx'
fx_path=base/'input'/'fx_rates.csv'
csv_path=base/'output'/'downloads'/'september_open_orders_export.csv'
out_path=base/'output'/'september_open_orders.xlsx'

# Details captured via browser detail pages
browser_details = {
'0045000109': {'OrderID': '0045000109', 'CustomerID': 'C001', 'CustomerName': 'Acme Precision Taiwan Ltd.', 'ProjectID': 'P003', 'OrderDate': '2026-09-01', 'Status': 'Open', 'Currency': 'TWD', 'NetAmount': '150000.00', 'CustomerContact': 'Grace Lin <grace.lin@acme-precision.example>', 'PaymentTerms': 'NET10'},
'0045000110': {'OrderID': '0045000110', 'CustomerID': 'C002', 'CustomerName': '台灣精密股份有限公司', 'ProjectID': 'P002', 'OrderDate': '2026-09-02', 'Status': 'Open', 'Currency': 'TWD', 'NetAmount': '293572.50', 'CustomerContact': '張美玲 <mei@tw-precision.example>', 'PaymentTerms': 'NET30'},
'0045000112': {'OrderID': '0045000112', 'CustomerID': 'C007', 'CustomerName': 'Acme Precision Taiwan Limited', 'ProjectID': 'P005', 'OrderDate': '2026-09-04', 'Status': 'Open', 'Currency': 'USD', 'NetAmount': '12311.00', 'CustomerContact': 'Peter Ho <peter.ho@acme-limited.example>', 'PaymentTerms': 'NET15'},
'0045000113': {'OrderID': '0045000113', 'CustomerID': 'C004', 'CustomerName': '藍海電子有限公司', 'ProjectID': '', 'OrderDate': '2026-09-05', 'Status': 'Open', 'Currency': 'TWD', 'NetAmount': '15390.00', 'CustomerContact': '', 'PaymentTerms': 'NET15'},
'0045000115': {'OrderID': '0045000115', 'CustomerID': 'C005', 'CustomerName': 'Pacific Test Systems Inc.', 'ProjectID': '', 'OrderDate': '2026-09-09', 'Status': 'Open', 'Currency': 'USD', 'NetAmount': '6391.00', 'CustomerContact': 'Sam Patel <sam@pacifictest.example>', 'PaymentTerms': 'NET20'},
'0045000116': {'OrderID': '0045000116', 'CustomerID': 'C008', 'CustomerName': '新竹量測科技', 'ProjectID': '', 'OrderDate': '2026-09-10', 'Status': 'Open', 'Currency': 'TWD', 'NetAmount': '29400.00', 'CustomerContact': '李建宏 <jh.lee@hsinchu-metrology.example>', 'PaymentTerms': 'NET30'},
'0045000118': {'OrderID': '0045000118', 'CustomerID': 'C003', 'CustomerName': 'Northwind Components GmbH', 'ProjectID': 'P004', 'OrderDate': '2026-09-14', 'Status': 'Open', 'Currency': 'EUR', 'NetAmount': '17484.75', 'CustomerContact': 'Jonas Krüger <jk@northwind.example>', 'PaymentTerms': 'NET0'},
'0045000119': {'OrderID': '0045000119', 'CustomerID': 'C001', 'CustomerName': 'Acme Precision Taiwan Ltd.', 'ProjectID': 'P001', 'OrderDate': '2026-09-15', 'Status': 'Open', 'Currency': 'EUR', 'NetAmount': '8775.00', 'CustomerContact': 'Grace Lin <grace.lin@acme-precision.example>', 'PaymentTerms': 'NET30'},
'0045000120': {'OrderID': '0045000120', 'CustomerID': 'C006', 'CustomerName': 'Helios Optics B.V.', 'ProjectID': '', 'OrderDate': '2026-09-16', 'Status': 'Open', 'Currency': 'EUR', 'NetAmount': '461.70', 'CustomerContact': 'Eva de Vries <eva@helios.example>', 'PaymentTerms': 'NET10'},
'0045000122': {'OrderID': '0045000122', 'CustomerID': 'C002', 'CustomerName': '台灣精密股份有限公司', 'ProjectID': 'P002', 'OrderDate': '2026-09-21', 'Status': 'Open', 'Currency': 'USD', 'NetAmount': '4141.00', 'CustomerContact': '張美玲 <mei@tw-precision.example>', 'PaymentTerms': 'NET5'},
'0045000124': {'OrderID': '0045000124', 'CustomerID': 'C004', 'CustomerName': '藍海電子有限公司', 'ProjectID': '', 'OrderDate': '2026-09-24', 'Status': 'Open', 'Currency': 'TWD', 'NetAmount': '45000.00', 'CustomerContact': '', 'PaymentTerms': 'NET30'},
'0045000126': {'OrderID': '0045000126', 'CustomerID': 'C008', 'CustomerName': '新竹量測科技', 'ProjectID': '', 'OrderDate': '2026-09-28', 'Status': 'Open', 'Currency': 'USD', 'NetAmount': '9171.00', 'CustomerContact': '李建宏 <jh.lee@hsinchu-metrology.example>', 'PaymentTerms': 'NET30'},
'0045000127': {'OrderID': '0045000127', 'CustomerID': 'C007', 'CustomerName': 'Acme Precision Taiwan Limited', 'ProjectID': 'P005', 'OrderDate': '2026-09-30', 'Status': 'Open', 'Currency': 'EUR', 'NetAmount': '2214.92', 'CustomerContact': 'Peter Ho <peter.ho@acme-limited.example>', 'PaymentTerms': 'NET30'},
'0045000128': {'OrderID': '0045000128', 'CustomerID': 'C003', 'CustomerName': 'Northwind Components GmbH', 'ProjectID': 'P004', 'OrderDate': '2026-09-30', 'Status': 'Open', 'Currency': 'TWD', 'NetAmount': '104160.00', 'CustomerContact': 'Jonas Krüger <jk@northwind.example>', 'PaymentTerms': 'NET5'},
}

print('Inputs:', in_template, fx_path, csv_path)
# Read fx
rates={}
with fx_path.open(newline='', encoding='utf-8-sig') as f:
    reader=csv.DictReader(f)
    for r in reader:
        rates[r['Currency']]=Decimal(r['RateToTWD'])
print('FX rates', rates)

with csv_path.open(newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('CSV rows', len(rows), 'headers', list(rows[0].keys()) if rows else [])

# Merge and sort
out_rows=[]
for r in rows:
    oid=str(r['OrderID'])
    d=browser_details.get(oid, {})
    merged={**r}
    merged['CustomerContact']=d.get('CustomerContact','')
    merged['PaymentTerms']=d.get('PaymentTerms','')
    amt=Decimal(str(merged['NetAmount']))
    rate=rates[merged['Currency']]
    merged['NetAmountTWD']=(amt*rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    merged['NetAmountDecimal']=amt
    out_rows.append(merged)
out_rows.sort(key=lambda x: x['OrderID'])

wb=load_workbook(in_template)
wsr=wb['Report']; wsd=wb['Details']; wss=wb['Summary']
# Report cells
now=datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()
wsr['B3']='2026-09-01'; wsr['D3']='2026-09-30'
wsr['B4']='Sales Orders; Status=Open; Sort by OrderID asc'
wsr['B5']=now
wsr['B7']='Lab ERP (synthetic SAP-like web); fx_rates.csv'
wsr['D7']=now

headers=[wsd.cell(4,c).value for c in range(1, wsd.max_column+1)]
# clear old rows from 5 down
for row in wsd.iter_rows(min_row=5, max_row=max(wsd.max_row, 5+len(out_rows)+5), max_col=len(headers)):
    for cell in row:
        cell.value=None

for i,r in enumerate(out_rows, start=5):
    values={
        'OrderID': r['OrderID'],
        'CustomerID': r['CustomerID'],
        'CustomerName': r['CustomerName'],
        'ProjectID': r['ProjectID'],
        'OrderDate': r['OrderDate'],
        'Status': r['Status'],
        'Currency': r['Currency'],
        'NetAmount': float(r['NetAmountDecimal']),
        'NetAmountTWD': float(r['NetAmountTWD']),
        'CustomerContact': r['CustomerContact'],
        'PaymentTerms': r['PaymentTerms'],
    }
    for c,h in enumerate(headers, start=1):
        cell=wsd.cell(i,c)
        cell.value=values.get(h)
        if h=='OrderID':
            cell.number_format='@'
        elif h in ('NetAmount','NetAmountTWD'):
            cell.number_format='#,##0.00'

# Summary: clear rows >=5 and create currency lines plus total
for row in wss.iter_rows(min_row=2, max_row=max(wss.max_row, 20), max_col=6):
    for cell in row:
        cell.value=None
wss['A2']='總計 TWD Totals'
wss['B2']=sum(Decimal(str(r['NetAmountTWD'])) for r in out_rows)
wss['B2'].number_format='#,##0.00'
wss['A4']='Group'; wss['B4']='SubGroup'; wss['C4']='Currency'; wss['D4']='Amount'; wss['E4']='AmountTWD'; wss['F4']='Count'
cur_order=sorted(set(r['Currency'] for r in out_rows))
for idx,cur in enumerate(cur_order, start=5):
    cr=[r for r in out_rows if r['Currency']==cur]
    orig=sum(Decimal(str(r['NetAmountDecimal'])) for r in cr)
    twd=sum(Decimal(str(r['NetAmountTWD'])) for r in cr)
    wss.cell(idx,1).value='Status'
    wss.cell(idx,2).value='Open'
    wss.cell(idx,3).value=cur
    wss.cell(idx,4).value=float(orig)
    wss.cell(idx,5).value=float(twd)
    wss.cell(idx,6).value=len(cr)
    wss.cell(idx,4).number_format='#,##0.00'
    wss.cell(idx,5).number_format='#,##0.00'

wb.save(out_path)
print('Saved', out_path)

# Reopen and validate
wb2=load_workbook(out_path, data_only=False)
wsd2=wb2['Details']; wss2=wb2['Summary']; wsr2=wb2['Report']
headers2=[wsd2.cell(4,c).value for c in range(1,12)]
records=[]
for rr in range(5, 5+len(out_rows)):
    rec={headers2[c-1]: wsd2.cell(rr,c).value for c in range(1,12)}
    records.append(rec)
print('Validation headers', headers2)
print('Validation detail row count', len(records))
print('Validation first/last OrderID', records[0]['OrderID'], records[-1]['OrderID'])
print('Validation sorted', [r['OrderID'] for r in records] == sorted(r['OrderID'] for r in records))
print('Validation all status Open', all(r['Status']=='Open' for r in records))
print('Validation all date in Sep 2026', all('2026-09-01' <= r['OrderDate'] <= '2026-09-30' for r in records))
print('Validation OrderID as text-like strings', all(isinstance(r['OrderID'], str) and r['OrderID'].startswith('00') for r in records))
print('Validation numeric amounts', all(isinstance(r['NetAmount'], (int,float)) and isinstance(r['NetAmountTWD'], (int,float)) for r in records))
print('Validation contacts/payment filled or source blank preserved', [(r['OrderID'], r['CustomerContact'], r['PaymentTerms']) for r in records])
summary=[]
for rr in range(5, 5+len(cur_order)):
    summary.append([wss2.cell(rr,c).value for c in range(1,7)])
print('Validation summary rows', summary)
print('Validation summary total B2', wss2['B2'].value)
print('Expected total', float(sum(Decimal(str(r['NetAmountTWD'])) for r in out_rows)))
