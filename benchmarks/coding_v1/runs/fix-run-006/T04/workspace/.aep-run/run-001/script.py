from pathlib import Path
workspace=Path.cwd()
input_dir=workspace/'input'/'files'
print('workspace:', workspace)
print('input/files exists:', input_dir.exists())
if input_dir.exists():
    files=[p for p in input_dir.rglob('*') if p.is_file()]
    print('file_count:', len(files))
    for p in files[:50]:
        print('FILE', p.relative_to(workspace), 'size', p.stat().st_size)
    if len(files)>50:
        print('... remaining:', len(files)-50)