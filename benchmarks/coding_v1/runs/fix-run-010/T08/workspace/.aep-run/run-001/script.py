from pathlib import Path
import csv, json

base = Path.cwd()
inp = base / 'input'
print('workspace:', base)
print('input exists:', inp.exists())
print('files:')
for p in sorted(inp.iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
    text = p.read_text(encoding='utf-8', errors='replace')
    if p.suffix.lower() == '.csv':
        rows = list(csv.reader(text.splitlines()))
        print('  csv rows preview:', rows[:5])
    elif p.suffix.lower() == '.json':
        try:
            data = json.loads(text)
            print('  json type:', type(data).__name__)
            if isinstance(data, list):
                print('  json sample:', data[:3])
            elif isinstance(data, dict):
                print('  json keys:', list(data.keys()))
                for k,v in data.items():
                    print('   ', k, 'type=', type(v).__name__, 'sample=', (v[:2] if isinstance(v, list) else v))
        except Exception as e:
            print('  json parse error:', e)
            print('  text preview:', text[:500])
    elif p.suffix.lower() in ['.md', '.markdown']:
        print('  markdown preview:')
        print('\n'.join(text.splitlines()[:12]))
    else:
        print('  text preview:', text[:500])