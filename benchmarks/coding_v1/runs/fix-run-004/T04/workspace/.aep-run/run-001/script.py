from pathlib import Path
import os
workspace = Path.cwd()
base = workspace / 'input' / 'files'
print('workspace:', workspace)
print('input/files exists:', base.exists(), 'is_dir:', base.is_dir())
if base.exists():
    files = sorted([p for p in base.rglob('*') if p.is_file()])
    print('file_count:', len(files))
    for p in files[:50]:
        rel = p.relative_to(workspace).as_posix()
        print(rel, 'size=', p.stat().st_size)
    if len(files) > 50:
        print('... remaining:', len(files)-50)
print('output exists:', (workspace/'output').exists())