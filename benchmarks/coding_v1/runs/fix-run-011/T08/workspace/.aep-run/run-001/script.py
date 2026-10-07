from pathlib import Path
import csv, json
workspace = Path.cwd()
input_dir = workspace/'input'
print('workspace:', workspace)
print('input exists:', input_dir.exists())
for p in sorted(input_dir.iterdir()):
    print('\nFILE:', p.name, 'suffix:', p.suffix, 'size:', p.stat().st_size)
    text = p.read_text(encoding='utf-8-sig')
    if p.suffix.lower() == '.csv':
        rows = list(csv.reader(text.splitlines()))
        print('CSV rows preview:')
        for r in rows[:5]: print(r)
    elif p.suffix.lower() == '.json':
        data = json.loads(text)
        print('JSON type:', type(data).__name__)
        if isinstance(data, list):
            print('JSON length:', len(data))
            print('JSON sample:', data[:3])
        elif isinstance(data, dict):
            print('JSON keys:', list(data.keys()))
            for k,v in list(data.items())[:3]: print(k, type(v).__name__, v if not isinstance(v,(list,dict)) else (v[:2] if isinstance(v,list) else list(v.items())[:2]))
    else:
        print('TEXT preview:')
        for line in text.splitlines()[:20]: print(repr(line))