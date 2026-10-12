from pathlib import Path

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('workspace:', workspace)
print('input_dir exists:', input_dir.exists())
print('output_dir exists:', output_dir.exists())
print('input files:')
for p in sorted(input_dir.iterdir() if input_dir.exists() else []):
    print(' -', p.name, 'size=', p.stat().st_size)

log_path = input_dir / 'test.log'
if log_path.exists():
    print('\nFirst 10 physical lines of test.log:')
    with log_path.open('r', encoding='utf-8', errors='replace') as f:
        for i, line in zip(range(1, 11), f):
            print(f'{i}: {line.rstrip()}')
else:
    print('test.log not found')