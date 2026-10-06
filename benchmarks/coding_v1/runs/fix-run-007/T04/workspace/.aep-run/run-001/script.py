from pathlib import Path
import os

workspace = Path.cwd()
input_dir = workspace / 'input' / 'files'
print('workspace:', workspace)
print('input_dir exists:', input_dir.exists(), input_dir)
if input_dir.exists():
    files = sorted([p for p in input_dir.rglob('*') if p.is_file()], key=lambda p: str(p.relative_to(input_dir)).lower())
    print('file_count:', len(files))
    for p in files[:50]:
        rel = p.relative_to(input_dir)
        print('sample:', rel, 'suffix=', p.suffix, 'size=', p.stat().st_size)
    if len(files) > 50:
        print('... remaining:', len(files)-50)
else:
    print('No input/files directory found')
print('output_dir:', workspace / 'output')