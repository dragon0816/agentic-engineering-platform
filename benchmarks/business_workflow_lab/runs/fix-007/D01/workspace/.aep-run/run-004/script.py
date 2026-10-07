from pathlib import Path
import csv
p=Path.cwd()/'output'/'expense_export_E001_2026-09-01_2026-09-30.csv'
print('file', p, p.stat().st_size)
with open(p, newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('rows', len(rows))
print('fieldnames', rows[0].keys() if rows else [])
for r in rows[:5]: print(r)
print('employees', sorted(set(r['EmployeeID'] for r in rows)))
print('dates', min(r['ExpenseDate'] for r in rows), max(r['ExpenseDate'] for r in rows))