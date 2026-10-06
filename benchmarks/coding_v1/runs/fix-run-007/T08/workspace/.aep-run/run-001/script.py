from pathlib import Path
import csv, json

base = Path('input')
print('Workspace input exists:', base.exists())
for p in sorted(base.iterdir()):
    print('\nFILE:', p.name, 'size=', p.stat().st_size)
    suffix = p.suffix.lower()
    try:
        if suffix == '.csv':
            with p.open('r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                print('CSV headers:', reader.fieldnames)
                for i, row in zip(range(5), reader):
                    print('CSV sample', i+1, row)
        elif suffix == '.json':
            data = json.load(p.open('r', encoding='utf-8-sig'))
            print('JSON type:', type(data).__name__)
            if isinstance(data, list):
                print('JSON length:', len(data))
                for i, item in enumerate(data[:5], 1): print('JSON sample', i, item)
            elif isinstance(data, dict):
                print('JSON keys:', list(data.keys()))
                for k, v in data.items():
                    print('JSON key sample:', k, type(v).__name__, v[:2] if isinstance(v, list) else v)
                    break
        elif suffix in ('.md', '.markdown'):
            text = p.read_text(encoding='utf-8-sig')
            print('Markdown first 30 lines:')
            for i, line in enumerate(text.splitlines()[:30], 1):
                print(f'{i:02d}: {line}')
        else:
            print('First bytes:', p.read_bytes()[:200])
    except Exception as e:
        print('ERROR reading', p.name, repr(e))