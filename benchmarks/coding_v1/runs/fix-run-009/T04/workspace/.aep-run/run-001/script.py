from pathlib import Path
import os
workspace = Path.cwd()
root = workspace / 'input' / 'files'
print('workspace:', workspace)
print('input/files exists:', root.exists(), 'is_dir:', root.is_dir())
if root.exists():
    files = sorted([p for p in root.rglob('*') if p.is_file()], key=lambda p: str(p.relative_to(root)).lower())
    print('file_count:', len(files))
    for p in files[:50]:
        rel = p.relative_to(root)
        print(f'FILE\t{rel}\tsize={p.stat().st_size}\tsuffix={p.suffix}')
    if len(files) > 50:
        print('... remaining:', len(files)-50)
else:
    print('input/files missing')