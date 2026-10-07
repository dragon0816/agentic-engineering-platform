from pathlib import Path
import csv, json

base = Path('input')
print('INPUT FILES:')
for p in sorted(base.iterdir()):
    print('-', p.name, p.stat().st_size, 'bytes')
    suffix = p.suffix.lower()
    try:
        if suffix == '.csv':
            with p.open(newline='', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                rows = [row for _, row in zip(range(4), reader)]
            print('  CSV sample:')
            for row in rows:
                print('   ', row)
        elif suffix == '.json':
            text = p.read_text(encoding='utf-8-sig')
            data = json.loads(text)
            print('  JSON type:', type(data).__name__)
            sample = data[:3] if isinstance(data, list) else (list(data.items())[:5] if isinstance(data, dict) else data)
            print('  JSON sample:', json.dumps(sample, ensure_ascii=False)[:1000])
        elif suffix in ('.md', '.markdown'):
            lines = p.read_text(encoding='utf-8-sig').splitlines()
            print('  Markdown first lines:')
            for line in lines[:12]:
                print('   ', line)
        else:
            print('  First bytes:', p.read_bytes()[:100])
    except Exception as e:
        print('  ERROR reading sample:', repr(e))
