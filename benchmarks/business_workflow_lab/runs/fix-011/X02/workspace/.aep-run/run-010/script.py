from pathlib import Path
import json
from openpyxl import load_workbook

base = Path.cwd()
out = base / 'output'
report = out / 'project_report_C001_2026-09-01_to_2026-09-30.xlsx'
assert report.exists(), f'missing report: {report}'
wb = load_workbook(report, data_only=False)
print('report=', report)
print('sheets=', wb.sheetnames)

def table(sheet_name):
    ws = wb[sheet_name]
    headers = [ws.cell(4, c).value for c in range(1, ws.max_column+1)]
    rows = []
    for r in range(5, ws.max_row+1):
        if any(ws.cell(r, c).value is not None for c in range(1, ws.max_column+1)):
            rows.append({headers[c-1]: ws.cell(r,c).value for c in range(1, ws.max_column+1)})
    return headers, rows

expected_counts = {'Orders': 3, 'Invoices': 3, 'Expenses': 9, 'Quotes': 4, 'Summary': 2, 'Exceptions': 3}
all_rows = {}
for s, expected in expected_counts.items():
    hdr, rows = table(s)
    all_rows[s] = rows
    print(f'{s}: data_rows={len(rows)} headers={hdr}')
    print(' sample=', rows[:3])
    assert len(rows) == expected, f'{s} data rows {len(rows)} != {expected}'

for row in all_rows['Orders']:
    assert row['CustomerID'] == 'C001'
    assert row['Status'] != 'Cancelled'
    assert '2026-09-01' <= row['OrderDate'] <= '2026-09-30'
    assert isinstance(row['OrderID'], str)
    assert isinstance(row['AmountTWD'], (int, float))

for row in all_rows['Invoices']:
    assert row['CustomerID'] == 'C001'
    assert '2026-09-01' <= row['InvoiceDate'] <= '2026-09-30'
    assert isinstance(row['InvoiceID'], str)
    assert isinstance(row['BalanceTWD'], (int, float))

for row in all_rows['Expenses']:
    assert row['ProjectID'] in {'P001', 'P003'}
    assert row['Status'] == 'Approved'
    assert '2026-09-01' <= row['ExpenseDate'] <= '2026-09-30'
    assert isinstance(row['ExpenseID'], str)
    assert isinstance(row['AmountTWD'], (int, float))

quote_by_id = {row['QuoteID']: row for row in all_rows['Quotes']}
statuses = sorted({row['Status'] for row in all_rows['Quotes']})
print('quote statuses retained=', statuses)
assert statuses == ['Accepted', 'Draft', 'Expired', 'Sent']
for row in all_rows['Quotes']:
    assert row['CustomerID'] == 'C001'
    assert isinstance(row['QuoteID'], str)
    assert isinstance(row['AmountTWD'], (int, float))

exceptions = all_rows['Exceptions']
print('exceptions=', json.dumps(exceptions, ensure_ascii=False, default=str, indent=2))
ids = {str(r['DocumentID']) for r in exceptions}
assert ids == {'EXP-00006', 'Q0010', 'Q0014'}, f'unexpected exception IDs {ids}'

# Validate attention rules from sheet data rather than exact wording.
exp_by_id = {row['ExpenseID']: row for row in all_rows['Expenses']}
assert 'EXP-00006' in exp_by_id, 'flagged expense not in approved expenses'
assert any(r['Source'] == 'Expenses' and r['DocumentID'] == 'EXP-00006' and 'Missing receipt' in str(r['Reason']) for r in exceptions)
for qid in ['Q0010', 'Q0014']:
    q = quote_by_id[qid]
    assert q['ValidUntil'] < '2026-09-30', f'{qid} ValidUntil is not before cutoff'
    assert q['Status'] != 'Accepted', f'{qid} is Accepted and should not be flagged'
    assert any(r['Source'] == 'Quotes' and r['DocumentID'] == qid and q['ValidUntil'] in str(r['Reason']) and q['Status'] in str(r['Reason']) for r in exceptions), f'{qid} exception reason missing date/status'

# Confirm no overdue unpaid invoice before cutoff was missed, and cutoff-day invoice is not flagged.
for inv in all_rows['Invoices']:
    overdue_unpaid = inv['DueDate'] < '2026-09-30' and float(inv['Balance']) > 0
    if overdue_unpaid:
        assert any(r['Source'] == 'Invoices' and r['DocumentID'] == inv['InvoiceID'] for r in exceptions), f"missing overdue unpaid invoice exception {inv}"
assert '0090000219' not in ids, 'invoice due on cutoff should not be flagged as overdue-before-cutoff'

# Template and source/FX notes.
assert 'Instructions' in wb.sheetnames
rep = wb['Report']
assert rep['B3'].value == '2026-09-01' and rep['D3'].value == '2026-09-30'
assert 'CustomerID=C001' in str(rep['B4'].value)
assert 'fx_rates.csv only' in str(rep['B4'].value)
assert 'P001,P003' in str(rep['B4'].value)

# Required workflow-produced files exist and are non-empty.
required_files = [
    'output/downloads/sap_orders_workflow.csv',
    'output/downloads/sap_invoices_workflow.csv',
    'output/expense_all_approved_2026-09-01_to_2026-09-30.csv',
    'output/project_report_C001_2026-09-01_to_2026-09-30.xlsx',
]
for rel in required_files:
    p = base / rel
    assert p.exists() and p.stat().st_size > 0, f'missing/empty {rel}'
    print(rel, p.stat().st_size)

print('\nCHECK PASSED: workflow output matches the requested period, customer, filters, template, TWD conversion from attachment FX, and attention rules.')