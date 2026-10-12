from pathlib import Path

workspace = Path.cwd()
input_files = workspace / 'input' / 'files'
print('workspace:', workspace)
print('input/files exists:', input_files.exists())
if input_files.exists():
    all_paths = sorted([p for p in input_files.rglob('*')])
    files = [p for p in all_paths if p.is_file()]
    dirs = [p for p in all_paths if p.is_dir()]
    print('directory count under input/files:', len(dirs))
    print('file count under input/files:', len(files))
    print('sample files:')
    for p in files[:50]:
        print(' -', p.relative_to(workspace), 'size=', p.stat().st_size)
else:
    print('input/files is missing')
