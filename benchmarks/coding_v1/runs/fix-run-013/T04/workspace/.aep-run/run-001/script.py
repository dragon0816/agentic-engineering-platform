from pathlib import Path

workspace = Path.cwd()
input_dir = workspace / 'input' / 'files'
output_dir = workspace / 'output'
print('workspace:', workspace)
print('input_dir exists:', input_dir.exists(), input_dir)
print('output_dir exists:', output_dir.exists(), output_dir)
if not input_dir.exists():
    raise SystemExit('input/files does not exist')
files = [p for p in input_dir.rglob('*') if p.is_file()]
print('file_count:', len(files))
for p in files[:50]:
    rel = p.relative_to(workspace)
    print(str(rel), 'size=', p.stat().st_size)
if len(files) > 50:
    print('... truncated, remaining:', len(files)-50)
