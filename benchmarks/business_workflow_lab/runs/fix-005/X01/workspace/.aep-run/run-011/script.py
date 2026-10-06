from pathlib import Path
import csv
ws=Path.cwd()
err=ws/'.aep-run'/'run-009'/'output.txt'
print('RUN-009 OUTPUT EXISTS', err.exists(), 'bytes', err.stat().st_size if err.exists() else None)
if err.exists():
    txt=err.read_text(encoding='utf-8', errors='replace')
    print(txt)
print('\nCSV SUMMARIES')
for rel in ['output/project_summary.csv','output/orders_normalized.csv','output/invoices_normalized.csv','output/expenses_normalized.csv','output/quotes_normalized.csv','output/exceptions.csv']:
    p=ws/rel
    print('\n---', rel, 'exists', p.exists(), 'bytes', p.stat().st_size if p.exists() else None)
    if p.exists():
        with p.open(newline='', encoding='utf-8-sig') as f:
            rows=list(csv.DictReader(f))
        print('fieldnames', rows[0].keys() if rows else [])
        print('row_count', len(rows))
        for row in rows[:5]: print(row)
