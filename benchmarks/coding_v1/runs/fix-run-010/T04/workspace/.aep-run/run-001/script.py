from pathlib import Path
import os
workspace = Path.cwd()
input_files = workspace / 'input' / 'files'
print('workspace:', workspace)
print('input_files exists:', input_files.exists(), 'is_dir:', input_files.is_dir())
if input_files.exists():
    files = sorted([p for p in input_files.rglob('*') if p.is_file()])
    dirs = sorted([p for p in input_files.rglob('*') if p.is_dir()])
    print('directory count under input/files:', len(dirs))
    print('file count under input/files:', len(files))
    print('sample files:')
    for p in files[:20]:
        rel = p.relative_to(input_files)
        print(' -', rel, '| suffix:', p.suffix, '| size:', p.stat().st_size)
else:
    print('input/files not found')
