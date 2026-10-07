from pathlib import Path
workspace = Path.cwd()
input_dir = workspace / 'input' / 'files'
print('workspace:', workspace)
print('input_dir:', input_dir)
print('input_dir_exists:', input_dir.exists())
if input_dir.exists():
    entries = []
    for p in sorted(input_dir.rglob('*')):
        rel = p.relative_to(input_dir)
        entries.append((str(rel), 'dir' if p.is_dir() else 'file', p.stat().st_size if p.is_file() else ''))
    print('entry_count:', len(entries))
    print('sample_entries:')
    for row in entries[:50]:
        print(row)
else:
    print('No input/files directory found')