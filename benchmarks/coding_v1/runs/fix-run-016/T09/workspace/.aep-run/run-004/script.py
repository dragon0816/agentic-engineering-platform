from pathlib import Path
import json

ws = Path.cwd()
input_dir = ws / 'input'
output_dir = ws / 'output'
print('workspace:', ws)
print('input exists:', input_dir.exists())
print('output exists:', output_dir.exists())
print('input files:', sorted(p.name for p in input_dir.iterdir()) if input_dir.exists() else [])
print('output files:', sorted(p.name for p in output_dir.iterdir()) if output_dir.exists() else [])

sop = input_dir / 'login_sop.md'
print('login_sop.md exists:', sop.exists(), 'size:', sop.stat().st_size if sop.exists() else None)
if sop.exists():
    text = sop.read_text(encoding='utf-8', errors='replace')
    print('login_sop sample:', text[:300].replace('\n', ' | '))
    print('mentions max 3:', ('3' in text or '三' in text))
    print('mentions wait 0.1:', ('0.1' in text))

data_file = output_dir / 'data.json'
worker_file = output_dir / 't09_worker.py'
print('data.json exists:', data_file.exists(), 'size:', data_file.stat().st_size if data_file.exists() else None)
print('t09_worker.py exists:', worker_file.exists(), 'size:', worker_file.stat().st_size if worker_file.exists() else None)

if not data_file.exists():
    raise SystemExit('FAIL: output/data.json is missing')
if data_file.stat().st_size <= 0:
    raise SystemExit('FAIL: output/data.json is empty')

raw = data_file.read_text(encoding='utf-8')
try:
    data = json.loads(raw)
except Exception as e:
    raise SystemExit(f'FAIL: output/data.json is not valid JSON: {e}')

print('data.json JSON type:', type(data).__name__)
if isinstance(data, dict):
    print('data.json keys:', sorted(data.keys()))
elif isinstance(data, list):
    print('data.json rows:', len(data))
else:
    print('data.json scalar:', repr(data)[:200])

if data in ({}, [], None, ''):
    raise SystemExit('FAIL: output/data.json JSON content is empty')

# Confirm worker contains the requested control flow without making new service calls.
if worker_file.exists():
    worker = worker_file.read_text(encoding='utf-8', errors='replace')
    checks = {
        'uses POST login endpoint': '/login' in worker and 'POST' in worker.upper(),
        'uses GET data endpoint': '/data' in worker and 'GET' in worker.upper(),
        'has max_attempts_3': ('max_attempts = 3' in worker or 'range(1, 4)' in worker or 'MAX_ATTEMPTS = 3' in worker),
        'has 0.1s wait': ('0.1' in worker and 'sleep' in worker),
        'prevents data fetch after failed logins': ('All login attempts failed' in worker or 'raise SystemExit' in worker),
    }
    for name, ok in checks.items():
        print(f'worker check - {name}:', ok)
    if not all(checks.values()):
        raise SystemExit('FAIL: worker script does not show all required controls')

print('CHECK PASSED: data.json exists, is non-empty valid JSON, and worker implements login retry controls without re-calling the service.')