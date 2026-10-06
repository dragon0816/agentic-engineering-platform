from pathlib import Path
import csv, openpyxl
ws=Path('.')
print('workspace', ws.resolve())
for p in sorted((ws/'input').iterdir()):
    print('INPUT', p.name, p.stat().st_size)
    if p.suffix.lower()=='.csv':
        with p.open(newline='', encoding='utf-8-sig') as f:
            r=csv.reader(f)
            for i,row in zip(range(5), r): print(' ', row)
    elif p.suffix.lower()=='.md':
        txt=p.read_text(encoding='utf-8')
        print(txt[:1200].replace('\r',''))
    elif p.suffix.lower()=='.xlsx':
        wb=openpyxl.load_workbook(p, data_only=False)
        print(' sheets', wb.sheetnames)
        for sh in wb.worksheets:
            print(' sheet', sh.title, sh.max_row, sh.max_column)
            for row in sh.iter_rows(min_row=1, max_row=min(5, sh.max_row), values_only=True): print(' ', row)
