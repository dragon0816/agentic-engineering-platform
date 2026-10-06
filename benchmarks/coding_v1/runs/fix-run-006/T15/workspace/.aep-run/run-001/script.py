from pathlib import Path
workspace = Path.cwd()
print('workspace:', workspace)
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('input exists:', input_dir.exists())
print('output exists:', output_dir.exists())
print('input files:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)
log_path = input_dir / 'test.log'
print('test.log exists:', log_path.exists())
if log_path.exists():
    print('sample non-empty/raw lines:')
    with log_path.open('r', encoding='utf-8', errors='replace') as f:
        for i, line in zip(range(1, 11), f):
            print(f'{i}: {line.rstrip()}')