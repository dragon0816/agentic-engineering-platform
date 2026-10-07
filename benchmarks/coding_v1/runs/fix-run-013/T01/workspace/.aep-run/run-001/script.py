from pathlib import Path
workspace = Path.cwd()
texts = workspace / 'input' / 'texts'
print(f'Workspace: {workspace}')
print(f'Input texts exists: {texts.exists()} is_dir: {texts.is_dir()}')
if texts.exists():
    print('First-level entries in input/texts:')
    for p in sorted(texts.iterdir(), key=lambda x: x.name):
        kind = 'dir' if p.is_dir() else 'file'
        print(f'- {p.name} [{kind}]')
    txt_files = sorted([p for p in texts.iterdir() if p.is_file() and p.suffix == '.txt'], key=lambda x: x.name)
    print('First-level .txt files to combine, sorted by filename:')
    for p in txt_files:
        sample = p.read_text(encoding='utf-8', errors='replace')[:120].replace('\n', '\\n')
        print(f'- {p.name}: {p.stat().st_size} bytes; sample={sample!r}')