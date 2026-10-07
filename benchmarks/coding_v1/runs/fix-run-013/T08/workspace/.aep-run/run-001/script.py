from pathlib import Path
import csv, json

base = Path('input')
print('Workspace input files:')
for p in sorted(base.iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
    suffix = p.suffix.lower()
    try:
        if suffix == '.csv':
            with p.open('r', encoding='utf-8-sig', newline='') as f:
                reader = csv.reader(f)
                rows = []
                for i, row in enumerate(reader):
                    rows.append(row)
                    if i >= 5:
                        break
                print('  CSV sample rows:')
                for row in rows:
                    print('   ', row)
        elif suffix == '.json':
            text = p.read_text(encoding='utf-8-sig')
            data = json.loads(text)
            print('  JSON top type:', type(data).__name__)
            if isinstance(data, dict):
                print('  JSON keys:', list(data.keys()))
                sample = data
                for key, val in data.items():
                    if isinstance(val, list):
                        print('  list key:', key, 'length:', len(val), 'first items:', val[:3])
                        break
            elif isinstance(data, list):
                print('  JSON length:', len(data), 'first items:', data[:3])
        elif suffix in ('.md', '.markdown'):
            lines = p.read_text(encoding='utf-8-sig').splitlines()
            print('  Markdown first lines:')
            for line in lines[:12]:
                print('   ', line)
        else:
            print('  Unknown extension; first bytes:', p.read_bytes()[:80])
    except Exception as e:
        print('  ERROR reading sample:', repr(e))