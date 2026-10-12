from pathlib import Path
import json, re, ast

ws = Path.cwd()
input_dir = ws / 'input'
output_dir = ws / 'output'
print('workspace:', ws)
print('input files:', sorted(p.name for p in input_dir.iterdir()) if input_dir.exists() else [])
print('output files:', sorted(p.name for p in output_dir.iterdir()) if output_dir.exists() else [])

# First inspect the real inputs/outputs.
sop = input_dir / 'login_sop.md'
if not sop.exists():
    raise SystemExit('FAIL: missing input/login_sop.md')
sop_text = sop.read_text(encoding='utf-8', errors='replace')
print('login_sop.md size:', sop.stat().st_size)
print('login_sop first lines:')
for line in sop_text.splitlines()[:8]:
    print('  ', line)

data_file = output_dir / 'data.json'
worker_file = output_dir / 't09_worker.py'
print('data.json exists:', data_file.exists(), 'size:', data_file.stat().st_size if data_file.exists() else None)
print('t09_worker.py exists:', worker_file.exists(), 'size:', worker_file.stat().st_size if worker_file.exists() else None)
if not data_file.exists() or data_file.stat().st_size == 0:
    raise SystemExit('FAIL: output/data.json missing or empty')

# Validate output file.
try:
    data = json.loads(data_file.read_text(encoding='utf-8'))
except Exception as e:
    raise SystemExit(f'FAIL: output/data.json invalid JSON: {e}')
print('data.json JSON type:', type(data).__name__)
print('data.json keys:', sorted(data.keys()) if isinstance(data, dict) else None)
if not data:
    raise SystemExit('FAIL: output/data.json JSON content is empty')

# Inspect worker controls without re-calling the service.
if not worker_file.exists() or worker_file.stat().st_size == 0:
    raise SystemExit('FAIL: output/t09_worker.py missing or empty')
worker = worker_file.read_text(encoding='utf-8', errors='replace')
print('worker relevant lines:')
for i, line in enumerate(worker.splitlines(), 1):
    if any(s in line for s in ['login', 'data', 'range', 'sleep', 'attempt', 'MAX', 'max', 'SystemExit', '/login', '/data']):
        print(f'{i:03d}: {line}')

# Parse AST for an actual loop bounded to 3 attempts.
try:
    tree = ast.parse(worker)
except Exception as e:
    raise SystemExit(f'FAIL: cannot parse worker script: {e}')

has_three_attempt_loop = False
for node in ast.walk(tree):
    if isinstance(node, ast.For) and isinstance(node.iter, ast.Call):
        func = node.iter.func
        if isinstance(func, ast.Name) and func.id == 'range':
            nums = []
            for arg in node.iter.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                    nums.append(arg.value)
            # Accept range(3), range(1,4), or range(any, any) whose count is 3 when literal.
            if nums == [3] or nums == [1, 4] or (len(nums) >= 2 and nums[1] - nums[0] == 3):
                has_three_attempt_loop = True

checks = {
    'output data.json is non-empty valid JSON': bool(data),
    'worker posts to /login': '/login' in worker and re.search(r'\bpost\b', worker, re.I) is not None,
    'worker gets /data': '/data' in worker and re.search(r'\bget\b', worker, re.I) is not None,
    'worker has loop bounded to 3 attempts': has_three_attempt_loop,
    'worker waits 0.1 seconds after failed login': 'sleep' in worker and '0.1' in worker,
    'worker stops on repeated login failure': ('SystemExit' in worker or 'raise' in worker) and ('failed' in worker.lower() or '失敗' in worker),
}
for name, ok in checks.items():
    print(f'check - {name}:', ok)
if not all(checks.values()):
    raise SystemExit('FAIL: one or more checks failed')

print('CHECK PASSED: runtime outputs and worker logic match requested workflow behavior; no additional /data request was made by this check.')