from pathlib import Path
workspace = Path.cwd()
input_root = workspace / 'input' / 'files'
print('workspace:', workspace)
print('input_root:', input_root)
print('input_root_exists:', input_root.exists())
if input_root.exists():
    files = [p for p in input_root.rglob('*') if p.is_file()]
    print('file_count:', len(files))
    for p in files[:50]:
        print(p.relative_to(workspace), 'size=', p.stat().st_size)
    if len(files) > 50:
        print('... truncated ...')
