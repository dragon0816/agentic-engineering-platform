from pathlib import Path

workspace = Path.cwd()
input_dir = workspace / 'input' / 'texts'
print('workspace:', workspace)
print('input/texts exists:', input_dir.exists(), 'is_dir:', input_dir.is_dir())
if input_dir.exists():
    print('first-level entries sorted by name:')
    for p in sorted(input_dir.iterdir(), key=lambda x: x.name):
        kind = 'dir' if p.is_dir() else 'file'
        print(f'- {p.name} [{kind}] suffix={p.suffix!r}')
    txt_files = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix == '.txt'], key=lambda x: x.name)
    print('first-level .txt files to merge:', [p.name for p in txt_files])
    for p in txt_files[:5]:
        data = p.read_text(encoding='utf-8')
        print(f'--- sample {p.name} length={len(data)} ---')
        print(data[:200].replace('\n', '\\n'))
