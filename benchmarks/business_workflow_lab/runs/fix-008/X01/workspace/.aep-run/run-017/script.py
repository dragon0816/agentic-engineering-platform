from pathlib import Path
import json
base=Path.cwd()
p=base/'output/quotes_2026-09-01_2026-09-30_accepted.json'
print('exists', p.exists(), 'size', p.stat().st_size if p.exists() else None)
obj=json.loads(p.read_text(encoding='utf-8'))
print('top type:', type(obj).__name__)
if isinstance(obj, dict):
    print('keys:', list(obj.keys()))
    for k,v in obj.items():
        print('key', repr(k), 'type', type(v).__name__, 'len', len(v) if hasattr(v,'__len__') else 'n/a')
        if isinstance(v, list):
            print('first:', v[0] if v else None)
        elif isinstance(v, dict):
            print('nested keys:', list(v.keys()))
else:
    print('len', len(obj) if hasattr(obj,'__len__') else 'n/a')
    print('first', obj[0] if isinstance(obj,list) and obj else None)
print('raw preview:', p.read_text(encoding='utf-8')[:1000])
