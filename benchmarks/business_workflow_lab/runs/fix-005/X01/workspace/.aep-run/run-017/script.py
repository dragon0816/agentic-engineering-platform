import os
from pathlib import Path
ws=Path.cwd()
for rel in [
    'output/expense_approved.csv',
    'output/project_integration_report.xlsx',
    'output/project_summary.csv',
    'output/orders_normalized.csv',
    'output/invoices_normalized.csv',
    'output/expenses_normalized.csv',
    'output/quotes_normalized.csv',
    'output/exceptions.csv',
]:
    p=ws/rel
    if p.exists():
        p.unlink()
        print('deleted', rel)
print('cleanup complete')
