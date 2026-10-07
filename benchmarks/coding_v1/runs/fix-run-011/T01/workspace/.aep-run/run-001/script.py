from pathlib import Path
workspace = Path.cwd()
texts = workspace / 'input' / 'texts'
print('workspace:', workspace)
print('texts exists:', texts.exists(), 'is_dir:', texts.is_dir())
if texts.exists():
    print('first-level entries:')
    for p in sorted(texts.iterdir(), key=lambda x: x.name):
        kind = 'dir' if p.is_dir() else 'file'
        print(f'- {p.name} [{kind}]')
    txts = sorted([p for p in texts.iterdir() if p.is_file() and p.suffix == '.txt'], key=lambda x: x.name)
    print('selected .txt files sorted:')
    for p in txts:
        data = p.read_bytes()
        preview = data[:80].decode('utf-8', errors='replace').replace('\n', '\\n')
        print(f'- {p.name}: {len(data)} bytes, preview={preview!r}')