from pathlib import Path
import json, re, ast

ws = Path.cwd()
input_dir = ws / 'input'
output_dir = ws / 'output'
print('workspace:', ws)
print('input files:', sorted(p.name for p in input_dir.iterdir()) if input_dir.exists() else [])
print('output files:', sorted(p.name for p in output_dir.iterdir()) if output_dir.exists() else [])

sop = input_dir / 'login_sop.md'
assert sop.exists(), 'missing input/login_sop.md'
sop_text = sop.read_text(encoding='utf-8', errors='replace')
print('login_sop.md size:', sop.stat().st_size)
print('login_sop required max-3 line present:', '最多嘗試 3 次' in sop_text or '最多嘗試3次' in sop_text)
print('login_sop required wait line present:', '0.1' in sop_text)
print('login_sop required no-data-on-failure line present:', '不可呼叫 /data' in sop_text)

data_file = output_dir / 'data.json'
worker_file = output_dir / 't09_worker.py'
print('data.json exists:', data_file.exists(), 'size:', data_file.stat().st_size if data_file.exists() else None)
print('t09_worker.py exists:', worker_file.exists(), 'size:', worker_file.stat().st_size if worker_file.exists() else None)
assert data_file.exists() and data_file.stat().st_size > 0, 'output/data.json missing or empty'
assert worker_file.exists() and worker_file.stat().st_size > 0, 'output/t09_worker.py missing or empty'

data = json.loads(data_file.read_text(encoding='utf-8'))
print('data.json JSON type:', type(data).__name__)
if isinstance(data, dict):
    print('data.json keys:', sorted(data.keys()))
assert bool(data), 'data.json JSON content is empty'

worker = worker_file.read_text(encoding='utf-8', errors='replace')
print('worker relevant lines:')
for i, line in enumerate(worker.splitlines(), 1):
    if any(s in line for s in ['LIMIT', 'PAUSE', 'login', 'data', 'range', 'sleep', 'attempt', 'SystemExit', '/login', '/data']):
        print(f'{i:03d}: {line}')

# Resolve simple integer constants and confirm the retry loop is exactly 3 attempts.
tree = ast.parse(worker)
constants = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        if isinstance(node.value, ast.Constant):
            constants[node.targets[0].id] = node.value.value
print('worker constants:', {k: constants[k] for k in sorted(constants) if k in ('LIMIT','PAUSE')})

def eval_int_expr(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Name) and isinstance(constants.get(node.id), int):
        return constants[node.id]
    if isinstance(node, ast.BinOp):
        left = eval_int_expr(node.left)
        right = eval_int_expr(node.right)
        if left is not None and right is not None:
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
    return None

has_three_attempt_loop = False
for node in ast.walk(tree):
    if isinstance(node, ast.For) and isinstance(node.iter, ast.Call):
        func = node.iter.func
        if isinstance(func, ast.Name) and func.id == 'range':
            vals = [eval_int_expr(arg) for arg in node.iter.args]
            print('found range args:', vals)
            if len(vals) == 1 and vals[0] == 3:
                has_three_attempt_loop = True
            elif len(vals) >= 2 and vals[0] is not None and vals[1] is not None and vals[1] - vals[0] == 3:
                has_three_attempt_loop = True

checks = {
    'runtime produced output/data.json as non-empty valid JSON': bool(data),
    'worker posts to /login': '/login' in worker and re.search(r'\bpost\b', worker, re.I) is not None,
    'worker gets /data only after token path': '/data' in worker and re.search(r'\bget\b', worker, re.I) is not None and worker.find('if tk is None') < worker.find('call_json("GET", URL_B'),
    'worker loop is bounded to exactly 3 attempts': has_three_attempt_loop,
    'worker waits 0.1 seconds between failed attempts': constants.get('PAUSE') == 0.1 and 'time.sleep(PAUSE)' in worker,
    'worker stops and reports if all login attempts fail': 'login failed after' in worker and '/data not requested' in worker and 'raise SystemExit' in worker,
}
for name, ok in checks.items():
    print(f'check - {name}:', ok)
assert all(checks.values()), 'one or more verification checks failed'

print('CHECK PASSED: output/data.json and output/t09_worker.py satisfy the requested workflow behavior. This verification did not call /login or /data again.')