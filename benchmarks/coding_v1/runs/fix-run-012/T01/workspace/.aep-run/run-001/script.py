from pathlib import Path
workspace = Path.cwd()
texts = workspace / 'input' / 'texts'
print('workspace:', workspace)
print('input/texts exists:', texts.exists(), 'is_dir:', texts.is_dir())
if texts.exists():
    print('First-level entries sorted by name:')
    for p in sorted(texts.iterdir(), key=lambda x: x.name):
        kind = 'dir' if p.is_dir() else 'file'
        print(f'- {p.name} [{kind}] suffix={p.suffix!r}')
        if p.is_file() and p.suffix == '.txt':
            data = p.read_text(encoding='utf-8')
            sample = data[:120].replace('\n', '\\n')
            print(f'  txt chars={len(data)} sample={sample!r}')
