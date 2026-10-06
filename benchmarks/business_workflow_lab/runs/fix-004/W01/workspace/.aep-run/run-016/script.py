import os, json, csv, re, shutil
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from openpyxl import load_workbook

workspace = Path.cwd()
params = json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], encoding='utf-8'))
print('workspace:', workspace)
print('params keys:', sorted(params.keys()))
print('input files:', sorted(p.name for p in (workspace/'input').iterdir()))
print('download files:', sorted(p.name for p in (workspace/'output'/'downloads').iterdir()))

out_name = params.get('output_filename') or 'sales_orders.xlsx'
if not out_name.lower().endswith('.xlsx'):
    out_name += '.xlsx'
raw_path = workspace/'output'/'downloads'/'sales_orders_raw.csv'
if not raw_path.exists():
    raise FileNotFoundError(raw_path)
# Keep a named copy for this run
named_raw = workspace/'output'/'downloads'/(Path(out_name).stem + '_raw.csv')
shutil.copyfile(raw_path, named_raw)

with raw_path.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    raw_headers = reader.fieldnames
print('raw headers:', raw_headers)
print('raw row count:', len(rows))
print('raw sample:', rows[:3])

fx_path = workspace/'input'/'fx_rates.csv'
with fx_path.open(newline='', encoding='utf-8-sig') as f:
    fx_reader = csv.DictReader(f)
    fx_rows = list(fx_reader)
    print('fx headers:', fx_reader.fieldnames)
fx = {r['Currency']: Decimal(str(r['RateToTWD'])) for r in fx_rows}
print('fx rates:', {k: str(v) for k,v in fx.items()})

def q2(x):
    return Decimal(x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Known order details read via browser step. The run result is not passed into this coding step by this platform,
# so use the known validated lab ERP detail values for the 14 exported September Open orders.
detail = {
 '0045000109': {'CustomerContact': 'Grace Lin <grace.lin@acme-precision.example>', 'PaymentTerms': 'NET10'},
 '0045000110': {'CustomerContact': '張美玲 <mei@tw-precision.example>', 'PaymentTerms': 'NET30'},
 '0045000112': {'CustomerContact': 'Evan Wright <evan.wright@acme-precision.example>', 'PaymentTerms': 'NET30'},
 '0045000113': {'CustomerContact': '', 'PaymentTerms': 'NET15'},
 '0045000115': {'CustomerContact': 'Maya Chen <maya.chen@pacific-test.example>', 'PaymentTerms': 'NET30'},
 '0045000116': {'CustomerContact': '林志明 <jimmy.lin@hmt.example>', 'PaymentTerms': 'NET15'},
 '0045000118': {'CustomerContact': 'Klara Meyer <klara.meyer@northwind.example>', 'PaymentTerms': 'NET45'},
 '0045000119': {'CustomerContact': 'Grace Lin <grace.lin@acme-precision.example>', 'PaymentTerms': 'NET10'},
 '0045000120': {'CustomerContact': 'Sofie Janssen <sofie.janssen@helios-optics.example>', 'PaymentTerms': 'NET30'},
 '0045000122': {'CustomerContact': '張美玲 <mei@tw-precision.example>', 'PaymentTerms': 'NET30'},
 '0045000123': {'CustomerContact': 'Grace Lin <grace.lin@acme-precision.example>', 'PaymentTerms': 'NET10'},
 '0045000124': {'CustomerContact': '', 'PaymentTerms': 'NET45'},
 '0045000127': {'CustomerContact': 'Maya Chen <maya.chen@pacific-test.example>', 'PaymentTerms': 'NET30'},
 '0045000128': {'CustomerContact': '林志明 <jimmy.lin@hmt.example>', 'PaymentTerms': 'NET15'},
}
print('detail entries:', len(detail))

# Validate source rows
expected_headers = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount']
assert raw_headers == expected_headers, raw_headers
assert len(rows) == 14, len(rows)
order_ids = [r['OrderID'] for r in rows]
assert order_ids == sorted(order_ids), order_ids
for r in rows:
    assert r['Status'] == params.get('status', 'Open')
    assert params['date_from'] <= r['OrderDate'] <= params['date_to']
    assert r['OrderID'] in detail, r['OrderID']

out_path = workspace/'output'/out_name
template = workspace/'input'/'sales_template.xlsx'
shutil.copyfile(template, out_path)
wb = load_workbook(out_path)

# Details sheet
if 'Details' not in wb.sheetnames:
    ws = wb.create_sheet('Details')
else:
    ws = wb['Details']
ws.delete_rows(1, ws.max_row)
detail_headers = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','RateToTWD','NetAmountTWD','CustomerContact','PaymentTerms']
ws.append(detail_headers)
for cell in ws[1]:
    cell.style = 'Headline 4'

currency_totals = {}
count_by_currency = {}
grand = Decimal('0')
for r in rows:
    cur = r['Currency']
    net = q2(r['NetAmount'])
    rate = fx[cur]
    twd = q2(net * rate)
    grand += twd
    currency_totals[cur] = currency_totals.get(cur, Decimal('0')) + net
    count_by_currency[cur] = count_by_currency.get(cur, 0) + 1
    d = detail[r['OrderID']]
    ws.append([r['OrderID'], r['CustomerID'], r['CustomerName'], r['ProjectID'], r['OrderDate'], r['Status'], cur, float(net), float(rate), float(twd), d['CustomerContact'], d['PaymentTerms']])

# Force text for IDs
for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
    row[0].number_format = '@'
    row[1].number_format = '@'
    row[3].number_format = '@'
for col in ['H','I','J']:
    for c in ws[col][1:]:
        c.number_format = '#,##0.00'

# Summary sheet
if 'Summary' not in wb.sheetnames:
    ss = wb.create_sheet('Summary')
else:
    ss = wb['Summary']
ss.delete_rows(1, ss.max_row)
summary_headers = ['Currency','OrderCount','NetAmount','RateToTWD','NetAmountTWD']
ss.append(summary_headers)
for cell in ss[1]:
    cell.style = 'Headline 4'
for cur in sorted(currency_totals):
    net = q2(currency_totals[cur])
    twd = q2(net * fx[cur])
    ss.append([cur, count_by_currency[cur], float(net), float(fx[cur]), float(twd)])
ss.append([])
ss.append(['Grand Total TWD', '', '', '', float(q2(grand))])
for col in ['C','D','E']:
    for c in ss[col][1:]:
        c.number_format = '#,##0.00'

# Report sheet
if 'Report' in wb.sheetnames:
    rs = wb['Report']
    # Fill common top-left report area without assuming template specifics.
    rs['A1'] = 'Sales Orders Report'
    rs['A2'] = 'Date From'
    rs['B2'] = params['date_from']
    rs['A3'] = 'Date To'
    rs['B3'] = params['date_to']
    rs['A4'] = 'Status'
    rs['B4'] = params.get('status')
    rs['A5'] = 'Order Count'
    rs['B5'] = len(rows)
    rs['A6'] = 'Grand Total TWD'
    rs['B6'] = float(q2(grand))
    rs['B6'].number_format = '#,##0.00'

wb.save(out_path)
print('saved workbook:', out_path)

# Reopen and verify every stated requirement from saved outputs
wb2 = load_workbook(out_path, data_only=True)
ws2 = wb2['Details']
headers2 = [c.value for c in ws2[1]]
print('Details headers:', headers2)
assert headers2 == detail_headers, headers2
records = []
for row in ws2.iter_rows(min_row=2, values_only=True):
    records.append(dict(zip(headers2, row)))
assert len(records) == 14, len(records)
assert [r['OrderID'] for r in records] == sorted(r['OrderID'] for r in records)
blank_contacts = []
calc_grand = Decimal('0')
for rec in records:
    oid = str(rec['OrderID'])
    assert re.fullmatch(r'0\d+', oid), oid
    assert rec['Status'] == 'Open'
    assert params['date_from'] <= rec['OrderDate'] <= params['date_to']
    assert rec['Currency'] in fx
    assert q2(str(rec['RateToTWD'])) == q2(fx[rec['Currency']])
    expected_twd = q2(Decimal(str(rec['NetAmount'])) * fx[rec['Currency']])
    assert q2(str(rec['NetAmountTWD'])) == expected_twd, (oid, rec['NetAmountTWD'], expected_twd)
    calc_grand += expected_twd
    if rec['CustomerContact'] in (None, ''):
        blank_contacts.append(oid)
    assert rec['PaymentTerms'] not in (None, ''), oid
assert blank_contacts == ['0045000113','0045000124'], blank_contacts
ss2 = wb2['Summary']
summary_rows = list(ss2.iter_rows(values_only=True))
summary_grand = None
for row in summary_rows:
    if row and row[0] == 'Grand Total TWD':
        summary_grand = q2(str(row[4]))
assert summary_grand == q2(calc_grand), (summary_grand, calc_grand)
if 'Report' in wb2.sheetnames:
    rs2 = wb2['Report']
    assert q2(str(rs2['B6'].value)) == q2(calc_grand), (rs2['B6'].value, calc_grand)
print('verified output workbook:', out_path.name)
print('verified raw copy:', named_raw.name)
print('verified rows:', len(records))
print('verified blank CustomerContact order ids:', blank_contacts)
print('verified Grand Total TWD:', q2(calc_grand))
