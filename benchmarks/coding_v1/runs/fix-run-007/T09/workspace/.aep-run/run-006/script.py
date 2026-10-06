from pathlib import Path
import json, os
ws = Path.cwd()
out = ws / 'output'
print('workspace:', ws)
print('output exists:', out.exists())
print('output files:')
for p in sorted(out.glob('*')):
    if p.is_file():
        print(f'- {p.relative_to(ws)} bytes={p.stat().st_size}')

# Reopen known outputs and validate what can be validated from files.
data = out / 'data.json'
if data.exists():
    raw = data.read_text(encoding='utf-8')
    try:
        parsed = json.loads(raw)
        print('data.json valid_json: True')
        print('data.json top_type:', type(parsed).__name__)
        if isinstance(parsed, dict):
            print('data.json keys:', sorted(parsed.keys()))
            if 'items' in parsed:
                print('data.json items_type:', type(parsed['items']).__name__)
                try:
                    print('data.json items_count:', len(parsed['items']))
                except Exception as e:
                    print('data.json items_count_error:', repr(e))
    except Exception as e:
        print('data.json valid_json: False', repr(e))
else:
    print('data.json exists: False')

worker = out / 't09_worker.py'
if worker.exists():
    text = worker.read_text(encoding='utf-8', errors='replace')
    print('t09_worker.py exists: True')
    print('t09_worker.py contains max_attempts=3-ish:', ('max_attempts = 3' in text) or ('max_attempts=3' in text) or ('MAX_ATTEMPTS = 3' in text))
    print('t09_worker.py contains sleep 0.1-ish:', ('sleep(0.1' in text) or ('wait_seconds = 0.1' in text) or ('WAIT_SECONDS = 0.1' in text))
else:
    print('t09_worker.py exists: False')

print('attached_runtime_result_exit_code:', 1)
print('attached_runtime_result_summary: Login failed after 3 attempts; /data was not requested. Reason: invalid credentials (scripted)')
