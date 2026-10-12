from pathlib import Path
import os

ws = Path.cwd()
input_files = ws / 'input' / 'files'
print('WORKSPACE:', ws)
print('INPUT_FILES_EXISTS:', input_files.exists())
print('INPUT_FILES_IS_DIR:', input_files.is_dir())
if input_files.exists():
    files = [p for p in input_files.rglob('*') if p.is_file()]
    dirs = [p for p in input_files.rglob('*') if p.is_dir()]
    print('DIR_COUNT_UNDER_INPUT_FILES:', len(dirs))
    print('FILE_COUNT_UNDER_INPUT_FILES:', len(files))
    print('SAMPLE_FILES:')
    for p in files[:20]:
        print(' -', p.relative_to(ws), 'size=', p.stat().st_size)
    print('EXTENSION_COUNTS:')
    counts = {}
    for p in files:
        counts[p.suffix.lower()] = counts.get(p.suffix.lower(), 0) + 1
    for ext, count in sorted(counts.items()):
        print(repr(ext), count)
