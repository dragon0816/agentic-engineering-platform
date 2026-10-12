from pathlib import Path
import json, os, datetime
root=Path.cwd()
print('workspace=', root)
print('input files=', [p.name for p in (root/'input').iterdir()] if (root/'input').exists() else 'missing')
print('output exists=', (root/'output').exists())
if (root/'output').exists():
    for p in sorted((root/'output').iterdir()):
        st=p.stat()
        print('OUTPUT', p.relative_to(root), 'bytes=', st.st_size, 'mtime=', datetime.datetime.fromtimestamp(st.st_mtime).isoformat())
        if p.name == 'data.json':
            try:
                obj=json.loads(p.read_text(encoding='utf-8'))
                print('data.json valid json type=', type(obj).__name__, 'keys=', list(obj.keys()) if isinstance(obj, dict) else None)
                print('data.json content=', json.dumps(obj, ensure_ascii=False, sort_keys=True))
            except Exception as e:
                print('data.json invalid:', repr(e))
# inspect latest aep run folders for context (metadata only)
ar=root/'.aep-run'
if ar.exists():
    runs=sorted([p for p in ar.iterdir() if p.is_dir()], key=lambda p:p.stat().st_mtime)
    print('aep run dirs=', [p.name for p in runs[-5:]])
    for p in runs[-3:]:
        print('RUN_DIR', p.name, 'mtime=', datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(), 'files=', [x.name for x in p.iterdir()])