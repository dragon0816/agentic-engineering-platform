from pathlib import Path
import json, csv
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace=', workspace)
print('input exists=', input_dir.exists())
for p in sorted(input_dir.iterdir()):
    print('\nFILE', p.name, 'size', p.stat().st_size)
    text = p.read_text(encoding='utf-8-sig')
    print('first 1000 chars:')
    print(text[:1000])
    if p.suffix.lower() == '.csv':
        try:
            with p.open('r', encoding='utf-8-sig', newline='') as f:
                reader = csv.reader(f)
                rows = [next(reader) for _ in range(5)]
            print('csv sample rows=', rows)
        except Exception as e:
            print('csv read error=', repr(e))
    elif p.suffix.lower() == '.json':
        try:
            data = json.loads(text)
            print('json type=', type(data).__name__)
            if isinstance(data, dict):
                print('json keys=', list(data.keys()))
                for k, v in data.items():
                    if isinstance(v, list):
                        print('list key', k, 'len', len(v), 'first=', v[0] if v else None)
                        break
            elif isinstance(data, list):
                print('json len=', len(data), 'first=', data[0] if data else None)
        except Exception as e:
            print('json read error=', repr(e))