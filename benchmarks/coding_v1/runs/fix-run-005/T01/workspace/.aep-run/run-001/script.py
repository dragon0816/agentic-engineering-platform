from pathlib import Path
workspace = Path.cwd()
input_dir = workspace / 'input' / 'texts'
print('workspace:', workspace)
print('input_dir exists:', input_dir.exists(), input_dir)
if input_dir.exists():
    print('first-level entries sorted:')
    for p in sorted(input_dir.iterdir(), key=lambda x: x.name):
        kind = 'DIR' if p.is_dir() else 'FILE'
        print(f'- {kind}: {p.name}')
    txts = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix == '.txt'], key=lambda x: x.name)
    print('first-level .txt files to merge:', [p.name for p in txts])
    for p in txts[:3]:
        data = p.read_text(encoding='utf-8')
        print(f'--- sample {p.name} length={len(data)} ---')
        print(data[:300].replace('\r','\\r').replace('\n','\\n\n'))