from pathlib import Path
import json

workspace = Path.cwd()
out = workspace / 'output'
print('workspace:', workspace)
print('output files:')
for p in sorted(out.iterdir()):
    if p.is_file():
        print(f'- {p.relative_to(workspace)} ({p.stat().st_size} bytes)')

data_path = out / 'data.json'
assert data_path.exists(), 'output/data.json does not exist'
raw = data_path.read_text(encoding='utf-8')
print('data.json raw:', raw)
obj = json.loads(raw)
print('data.json top-level type:', type(obj).__name__)
print('data.json keys:', sorted(obj.keys()) if isinstance(obj, dict) else None)

# Confirm it is valid JSON and was not an error-only login failure artifact.
assert isinstance(obj, dict), 'data.json must contain a JSON object'
assert obj, 'data.json must not be empty'
print('CHECK PASSED: output/data.json exists, is valid JSON, and contains a non-empty object.')