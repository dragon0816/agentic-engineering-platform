from pathlib import Path
import json, os, datetime

workspace = Path.cwd()
print('workspace:', workspace)
print('input files:', [p.name for p in (workspace/'input').iterdir()] if (workspace/'input').exists() else 'no input dir')
print('output files:', [str(p.relative_to(workspace)) for p in (workspace/'output').rglob('*') if p.is_file()] if (workspace/'output').exists() else 'no output dir')

out = workspace / 'output' / 'data.json'
print('data.json exists:', out.exists())
if out.exists():
    stat = out.stat()
    print('data.json bytes:', stat.st_size)
    print('data.json mtime:', datetime.datetime.fromtimestamp(stat.st_mtime).isoformat())
    try:
        data = json.loads(out.read_text(encoding='utf-8'))
        print('data.json json valid: yes')
        print('data.json top-level type:', type(data).__name__)
        print('data.json content:', json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print('data.json json valid: no')
        print('error:', repr(e))

run4 = workspace / '.aep-run' / 'run-004' / 'script.py'
print('run-004 script exists:', run4.exists())
if run4.exists():
    text = run4.read_text(encoding='utf-8', errors='replace')
    print('run-004 script first 20 lines:')
    print('\n'.join(text.splitlines()[:20]))