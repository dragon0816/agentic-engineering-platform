from pathlib import Path

workspace = Path.cwd()
input_files = workspace / 'input' / 'files'
print('workspace:', workspace)
print('input/files exists:', input_files.exists())
print('input/files is_dir:', input_files.is_dir())
if input_files.exists():
    all_paths = sorted([p for p in input_files.rglob('*')])
    files = [p for p in all_paths if p.is_file()]
    dirs = [p for p in all_paths if p.is_dir()]
    print('directory count under input/files:', len(dirs))
    print('file count under input/files:', len(files))
    print('first 30 files:')
    for p in files[:30]:
        print(' -', p.relative_to(workspace), 'suffix=', p.suffix)
