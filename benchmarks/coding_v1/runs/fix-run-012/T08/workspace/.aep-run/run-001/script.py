from pathlib import Path
import json, csv

base = Path.cwd()
inp = base / 'input'
out = base / 'output'
print('workspace:', base)
print('input exists:', inp.exists())
print('output exists:', out.exists())
print('input files:')
for p in sorted(inp.iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)
    suffix = p.suffix.lower()
    try:
        if suffix == '.csv':
            with p.open('r', encoding='utf-8-sig', newline='') as f:
                reader = csv.reader(f)
                for i, row in zip(range(5), reader):
                    print('   csv row', i, row)
        elif suffix == '.json':
            data = json.loads(p.read_text(encoding='utf-8-sig'))
            print('   json type:', type(data).__name__)
            if isinstance(data, list):
                print('   list length:', len(data))
                print('   sample:', data[:3])
            elif isinstance(data, dict):
                print('   keys:', list(data.keys()))
                for k, v in data.items():
                    print('   key sample', k, 'type', type(v).__name__, 'value', (v[:3] if isinstance(v, list) else v))
                    break
        elif suffix in {'.md', '.markdown'}:
            lines = p.read_text(encoding='utf-8-sig').splitlines()
            print('   markdown first lines:')
            for i, line in enumerate(lines[:12]):
                print(f'   {i}: {line}')
        else:
            print('   first bytes:', p.read_bytes()[:80])
    except Exception as e:
        print('   ERROR reading:', repr(e))