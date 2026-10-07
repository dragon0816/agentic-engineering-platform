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
log = input_dir / 'test.log'
print('test.log exists:', log.exists())
if log.exists():
    print('first 20 physical lines:')
    with log.open('r', encoding='utf-8', errors='replace') as f:
        for i, line in zip(range(1, 21), f):
            print(f'{i}: {line.rstrip()}')