from pathlib import Path
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input files:', [p.name for p in input_dir.iterdir() if p.is_file()])
log_path = input_dir / 'test.log'
print('test.log exists:', log_path.exists())
if log_path.exists():
    text = log_path.read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines()
    print('line_count:', len(lines))
    for i, line in enumerate(lines[:10], start=1):
        print(f'sample {i}: {line!r}')
