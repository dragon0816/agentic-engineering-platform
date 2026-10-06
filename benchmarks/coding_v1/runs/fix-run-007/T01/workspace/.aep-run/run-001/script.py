from pathlib import Path

workspace = Path.cwd()
texts = workspace / 'input' / 'texts'
print('workspace:', workspace)
print('input/texts exists:', texts.exists(), 'is_dir:', texts.is_dir())
if texts.exists():
    for p in sorted(texts.iterdir(), key=lambda x: x.name):
        kind = 'dir' if p.is_dir() else 'file'
        print(f'{kind}: {p.name}')
    txts = [p for p in texts.iterdir() if p.is_file() and p.suffix == '.txt']
    print('first-level .txt sorted:', [p.name for p in sorted(txts, key=lambda x: x.name)])