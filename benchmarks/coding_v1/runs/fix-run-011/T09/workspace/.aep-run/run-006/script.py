from pathlib import Path
import json, os, datetime
root = Path.cwd()
out = root / 'output'
print('workspace:', root)
print('output exists:', out.exists())
print('output files:')
for p in sorted(out.iterdir() if out.exists() else []):
    st = p.stat()
    print(f'- {p.relative_to(root)} bytes={st.st_size} mtime={datetime.datetime.fromtimestamp(st.st_mtime).isoformat()}')

# Reopen data.json if present and validate it, but do not modify anything.
data_path = out / 'data.json'
if data_path.exists():
    raw = data_path.read_text(encoding='utf-8')
    print('data.json raw length:', len(raw))
    try:
        data = json.loads(raw)
        print('data.json valid_json: True')
        print('data.json top_level:', type(data).__name__)
        if isinstance(data, dict):
            print('data.json keys:', sorted(data.keys()))
            print('data.json item_count:', len(data.get('items', [])) if isinstance(data.get('items'), list) else 'items-not-list')
    except Exception as e:
        print('data.json valid_json: False', repr(e))
else:
    print('data.json exists: False')

# Check worker exists and contains the guarded failure behavior markers.
worker = out / 't09_worker.py'
if worker.exists():
    text = worker.read_text(encoding='utf-8')
    print('t09_worker.py exists: True')
    print('worker contains no-data-on-failure marker:', '/data was not requested' in text)
    print('worker contains max_try=3 marker:', 'max_try = 3' in text or 'max_try=3' in text)
else:
    print('t09_worker.py exists: False')
