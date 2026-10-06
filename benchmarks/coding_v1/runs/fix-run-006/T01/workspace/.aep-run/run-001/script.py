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
    print('first-level .txt files sorted:', [p.name for p in txts])
    for p in txts[:5]:
        data = p.read_text(encoding='utf-8')
        print(f'--- sample {p.name} length={len(data)} ---')
        print(data[:200].replace('\r','\\r').replace('\n','\\n'))