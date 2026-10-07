from pathlib import Path
import csv, json

base = Path('input')
print('Workspace input exists:', base.exists())
for p in sorted(base.iterdir()):
    print('\nFILE:', p.name, 'suffix=', p.suffix, 'size=', p.stat().st_size)
    try:
        if p.suffix.lower() == '.csv':
            with p.open('r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                print('CSV headers:', reader.fieldnames)
                for i, row in zip(range(5), reader):
                    print('CSV sample', i+1, row)
        elif p.suffix.lower() == '.json':
            text = p.read_text(encoding='utf-8-sig')
            data = json.loads(text)
            print('JSON type:', type(data).__name__)
            if isinstance(data, dict):
                print('JSON keys:', list(data.keys())[:20])
                sample = data
                # show likely lists
                for k, v in data.items():
                    if isinstance(v, list):
                        print('JSON list key:', k, 'len=', len(v), 'first items=', v[:3])
            elif isinstance(data, list):
                print('JSON len:', len(data), 'first items:', data[:3])
        elif p.suffix.lower() in {'.md', '.markdown'}:
            lines = p.read_text(encoding='utf-8-sig').splitlines()
            print('Markdown first 30 lines:')
            for line in lines[:30]:
                print(repr(line))
        else:
            print('First 500 chars:', p.read_text(encoding='utf-8-sig', errors='replace')[:500])
    except Exception as e:
        print('ERROR inspecting', p.name, type(e).__name__, str(e))
