from pathlib import Path
import json, csv
ws=Path.cwd()
inp=ws/'input'
print('workspace', ws)
print('input exists', inp.exists())
for p in sorted(inp.iterdir()):
    print('\nFILE', p.name, 'size', p.stat().st_size)
    text=p.read_text(encoding='utf-8-sig', errors='replace')
    print(text[:1000])
    if p.suffix.lower()=='.csv':
        with p.open('r', encoding='utf-8-sig', newline='') as f:
            r=csv.reader(f)
            for i,row in zip(range(5), r): print('CSVROW', row)
    elif p.suffix.lower()=='.json':
        try:
            data=json.loads(text)
            print('JSON type', type(data).__name__)
            print('JSON sample', json.dumps(data[:2] if isinstance(data,list) else data, ensure_ascii=False)[:1000])
        except Exception as e: print('json error', e)
